import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

// Skiva 1b (UI half): spawn scripts/run_openclaw_followup.py and parse its
// stdout into a schema-stable OpenClawDecision JSON object. Mirrors
// router-classify-runner.ts / prompt-runner.ts / build-runner.ts so apps/viewser
// never imports packages/ directly (repo-boundaries.v1.json) — the Python script
// in scripts/ owns the import on viewser's behalf.
//
// Deterministic + read-only by contract: the script wraps OpenClaw Core V0
// (classify_message -> assemble_context -> decide), uses NO LLM fallback,
// touches no disk and starts no build/preview, so this adds no per-prompt
// OPENAI_API_KEY cost. We cap it with a short timeout and ALWAYS degrade to
// null on any failure so /api/prompt's existing build flow can never be broken
// by this read-only decision step.
const OPENCLAW_TIMEOUT_MS = 15_000;

function repoRoot(): string {
  // ``...up`` (spread av variabel-array) gör resultatet opakt för Turbopacks
  // statiska analys, så python-spawn mot ``.venv``-pathen inte viks ihop till
  // fil/dir-asset-referenser. Samma mönster som router-classify-runner.ts.
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
 * OpenClaw Core V0's decision for one follow-up message. Shape mirrors
 * ``OpenClawDecision.model_dump()`` (packages/generation/orchestration/openclaw/
 * models.py): { action, answer, clarifyingQuestion, plan[], patchPlanRequest:
 * { targetSummary, status, blockedBy }, appliedVisibleEffect, rationale,
 * router{...}, context{...} }. Kept as a loose record because this bridge passes
 * the Python dump through verbatim and FloatingChat branches only on a few
 * fields via extractOpenClawDecision.
 */
export type OpenClawDecisionPayload = Record<string, unknown>;

export type OpenClawFollowupOptions = {
  /** Optional siteId passed as RouterContext metadata (never read from disk). */
  siteId?: string;
  /** Optional baseRunId to iterate from; forwarded to context assembly. */
  baseRunId?: string;
};

/**
 * Run the read-only OpenClaw follow-up decision for a single user message via
 * the deterministic Python seam. Returns the parsed JSON object, or ``null``
 * when the message is empty or the helper fails/times out — callers treat
 * ``null`` as "no OpenClaw opinion available" and fall back to unchanged
 * behaviour (the existing build summary / routerDecision line).
 */
export async function runOpenClawFollowup(
  message: string,
  options: OpenClawFollowupOptions = {},
): Promise<OpenClawDecisionPayload | null> {
  const trimmed = message.trim();
  if (!trimmed) return null;

  const scriptPath = path.join(
    repoRoot(),
    "scripts",
    "run_openclaw_followup.py",
  );
  const args = [scriptPath];
  if (options.siteId) args.push("--site-id", options.siteId);
  if (options.baseRunId) args.push("--base-run-id", options.baseRunId);
  // The `--` separator stops argparse from treating a message that starts with
  // `-`/`--` as a CLI option (same guard as router-classify-runner.ts).
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
  // stderr is intentionally drained but ignored: a decision failure must never
  // surface as a 500 on the prompt route — it just yields null.
  child.stderr.on("data", () => {});

  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    child.kill();
  }, OPENCLAW_TIMEOUT_MS);

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
      return parsed as OpenClawDecisionPayload;
    }
    return null;
  } catch {
    return null;
  }
}
