import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

// KÖR-6a bridge: spawn scripts/classify_message.py and parse its stdout into a
// schema-valid RouterDecision JSON object. Mirrors the spawn pattern in
// prompt-runner.ts / build-runner.ts so apps/viewser never imports packages/
// directly (repo-boundaries.v1.json) — the Python script in scripts/ owns the
// import on viewser's behalf.
//
// Deterministic + read-only by contract: the script uses classify_message
// (NOT the LLM fallback), touches no disk and starts no build/preview, so this
// adds no per-prompt OPENAI_API_KEY cost. classify is fast, but we cap it with
// a short timeout and ALWAYS degrade to null on any failure so /api/prompt's
// existing build flow can never be broken by this read-only metadata step.
const CLASSIFY_TIMEOUT_MS = 15_000;

function repoRoot(): string {
  // ``...up`` (spread av variabel-array) gör resultatet opakt för Turbopacks
  // statiska analys, så python-spawn mot ``.venv``-pathen inte viks ihop till
  // fil/dir-asset-referenser. Samma mönster som prompt-runner.ts/build-runner.ts.
  const up = ["..", ".."];
  return path.resolve(process.cwd(), ...up);
}

function pythonCommand(): string {
  const venvPython = path.join(
    repoRoot(),
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
  if (existsSync(venvPython)) return venvPython;
  return process.platform === "win32" ? "python" : "python3";
}

/**
 * The router's structured decision for one message. Shape mirrors
 * governance/schemas/router-decision.schema.json; kept as a loose record here
 * because this bridge passes the Python ``RouterDecision.model_dump()`` through
 * verbatim and the route exposes it as read-only metadata (the operator UI
 * branches only on a few fields via floating-chat's extractRouterDecision).
 */
export type RouterDecisionPayload = Record<string, unknown>;

export type ClassifyMessageOptions = {
  /** Optional siteId passed as RouterContext metadata (never read from disk). */
  siteId?: string;
};

/**
 * Classify a single user message into a RouterDecision via the deterministic
 * Python router. Returns the parsed JSON object, or ``null`` when the message
 * is empty or the helper fails/times out — callers treat ``null`` as "no
 * router opinion available" and fall back to unchanged behaviour.
 */
export async function classifyMessage(
  message: string,
  options: ClassifyMessageOptions = {},
): Promise<RouterDecisionPayload | null> {
  const trimmed = message.trim();
  if (!trimmed) return null;

  const scriptPath = path.join(repoRoot(), "scripts", "classify_message.py");
  const args = [scriptPath];
  if (options.siteId) args.push("--site-id", options.siteId);
  // The `--` separator stops argparse from treating a prompt that starts with
  // `-`/`--` as a CLI option (same guard as prompt-runner.ts).
  args.push("--", trimmed);

  const child = spawn(pythonCommand(), args, {
    cwd: repoRoot(),
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const stdoutChunks: string[] = [];
  let totalStdoutBytes = 0;
  const MAX_STREAM_BYTES = 256 * 1024;
  child.stdout.on("data", (chunk: Buffer) => {
    if (totalStdoutBytes >= MAX_STREAM_BYTES) return;
    totalStdoutBytes += chunk.byteLength;
    stdoutChunks.push(chunk.toString("utf-8"));
  });
  // stderr is intentionally drained but ignored: a classification failure must
  // never surface as a 500 on the prompt route — it just yields null.
  child.stderr.on("data", () => {});

  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    child.kill();
  }, CLASSIFY_TIMEOUT_MS);

  let exitCode: number;
  try {
    exitCode = await new Promise<number>((resolve, reject) => {
      child.once("error", reject);
      child.once("close", (code) => resolve(code ?? 1));
    });
  } catch {
    clearTimeout(timeout);
    return null;
  }
  clearTimeout(timeout);

  if (timedOut || exitCode !== 0) return null;

  const stdout = stdoutChunks.join("").trim();
  if (!stdout) return null;

  try {
    const parsed: unknown = JSON.parse(stdout);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as RouterDecisionPayload;
    }
    return null;
  } catch {
    return null;
  }
}
