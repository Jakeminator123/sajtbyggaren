import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

import { killProcessTree } from "@/lib/local-preview-server";
import { writeTextArgFile } from "@/lib/text-arg-file";

// Skiva 1b (UI half): spawn scripts/run_openclaw_followup.py and parse its
// stdout into a schema-stable OpenClawDecision JSON object. Mirrors
// router-classify-runner.ts / prompt-runner.ts / build-runner.ts so apps/viewser
// never imports packages/ directly (repo-boundaries.v1.json) — the Python script
// in scripts/ owns the import on viewser's behalf.
//
// Deterministic-first + read-only by contract: the script wraps OpenClaw Core
// V0 (classify -> assemble_context -> decide), touches no disk and starts no
// build/preview. Since 2026-06-11 the router half MAY escalate an ambiguous
// message (unclear/long/multi-intent) to routerModel (KÖR-6b) — at most ONE
// small model call per invocation, never for confident heuristic decisions,
// and OPENCLAW_ROUTER_LLM_FALLBACK=0 restores the pure-heuristic mode. The
// timeout budget covers venv spawn + that single call. We ALWAYS degrade to
// null on any failure so /api/prompt's existing build flow can never be broken
// by this read-only decision step.
const OPENCLAW_TIMEOUT_MS = 45_000;

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

// B174: the stable stdout contract line scripts/run_openclaw_followup.py emits
// as its FINAL line: `OPENCLAW_BRIDGE_JSON: {...}`. With --apply the KÖR-7
// chain (scripts/build_site.build) writes human progress ("runId: ...",
// "Copying starter ...", npm output) to the SAME stdout BEFORE the payload, so
// the previous blind JSON.parse of the whole stream threw on EVERY successful
// apply -> null -> /api/prompt's B164 recovery forced an unearned degraded
// status.
// Keep this literal in sync with BRIDGE_SENTINEL_PREFIX on the Python side.
const BRIDGE_SENTINEL_PREFIX = "OPENCLAW_BRIDGE_JSON:";

function parseJsonObjectCandidate(
  candidate: string,
): Record<string, unknown> | null {
  const trimmed = candidate.trim();
  if (!trimmed.startsWith("{")) return null;
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Not a clean JSON object line — the caller keeps scanning.
  }
  return null;
}

/**
 * Extract the helper's payload JSON object from a possibly noisy stdout
 * (B174). The payload is always the LAST thing the script prints, so both
 * passes scan the lines BACKWARDS (mirrors build-runner.ts, which also never
 * trusts build_site.py's stdout to be a single clean token):
 *
 *   1. sentinel pass — the explicit contract: the last line starting with
 *      `OPENCLAW_BRIDGE_JSON:` whose remainder parses to an object;
 *   2. bare-JSON fallback — backward compatible with the pre-sentinel format:
 *      the last line that itself parses cleanly to a JSON object.
 *
 * ``isExpectedShape`` guards the heuristic fallback against tool noise that
 * happens to be a JSON object (e.g. npm printing JSON progress lines).
 * Returns ``null`` when nothing matches (empty stdout / pure garbage), so the
 * callers' degrade-to-null contract is unchanged for genuine failures.
 */
function extractPayloadJson(
  stdout: string,
  isExpectedShape: (obj: Record<string, unknown>) => boolean,
): Record<string, unknown> | null {
  const lines = stdout.split(/\r?\n/);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim();
    if (!line.startsWith(BRIDGE_SENTINEL_PREFIX)) continue;
    const parsed = parseJsonObjectCandidate(
      line.slice(BRIDGE_SENTINEL_PREFIX.length),
    );
    if (parsed && isExpectedShape(parsed)) return parsed;
  }
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const parsed = parseJsonObjectCandidate(lines[i]);
    if (parsed && isExpectedShape(parsed)) return parsed;
  }
  return null;
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
  // B204: pass the message through a UTF-8 temp file instead of argv so a
  // non-ASCII leading char survives the Windows spawn hop intact (same
  // defensive transport as router-classify-runner.ts).
  const messageArg = writeTextArgFile(trimmed, "sb-openclaw-");
  args.push("--message-file", messageArg.path);

  const child = spawn(pythonCommand(), args, {
    cwd: repoRoot(),
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const stdoutChunks: Buffer[] = [];
  let totalStdoutBytes = 0;
  const MAX_STREAM_BYTES = 256 * 1024;
  child.stdout.on("data", (chunk: Buffer) => {
    stdoutChunks.push(chunk);
    totalStdoutBytes += chunk.byteLength;
    // B174: the payload is the LAST stdout line (sentinel contract), so an
    // overflowing stream must drop the OLDEST chunks. The previous cap kept
    // the head and dropped the tail — i.e. exactly the payload.
    while (
      stdoutChunks.length > 1 &&
      totalStdoutBytes - stdoutChunks[0].byteLength >= MAX_STREAM_BYTES
    ) {
      totalStdoutBytes -= stdoutChunks[0].byteLength;
      stdoutChunks.shift();
    }
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
    messageArg.cleanup();
    return null;
  }
  clearTimeout(timeout);
  messageArg.cleanup();

  if (timedOut || exitCode !== 0) return null;

  const stdout = Buffer.concat(stdoutChunks).toString("utf-8").trim();
  if (!stdout) return null;

  // B174: extract the decision robustly instead of a blind JSON.parse on the
  // whole stream. The decision payload always carries the ``action`` string
  // (OpenClawDecision.model_dump()), which guards the bare-JSON fallback.
  const parsed = extractPayloadJson(
    stdout,
    (obj) => typeof obj.action === "string",
  );
  if (!parsed) return null;
  return parsed as OpenClawDecisionPayload;
}

// The action-bridge build runs npm install + a targeted Next.js build inside the
// KÖR-7 chain — the same cost class as build-runner.ts — so we mirror its
// 10-minute budget instead of the 15-second read-only decision budget.
const OPENCLAW_APPLY_TIMEOUT_MS = 600_000;

/**
 * OpenClaw action-bridge outcome for one follow-up. Mirrors the ``bridge``
 * object emitted by ``scripts/run_openclaw_followup.py --apply``
 * (apply_followup_to_json). The KÖR-7 chain stays authoritative, so ``applied``
 * / ``previewShouldRefresh`` come straight from it — a no-op never fakes a
 * change. ``chain`` is the transient ``run_followup_chain`` summary; when
 * ``applied`` it carries ``runId`` / ``version`` / ``buildStatus`` / ``editKind``
 * that /api/prompt re-surfaces as the authoritative build result.
 */
export type OpenClawBridge = {
  status: string;
  applied: boolean;
  previewShouldRefresh: boolean;
  chain: Record<string, unknown> | null;
};

/**
 * The seam apps/viewser consumes from the ``--apply`` path:
 * ``{ decision: <OpenClawDecision>, bridge: <OpenClawBridge>, report }``.
 */
export type OpenClawApplyResult = {
  decision: OpenClawDecisionPayload;
  bridge: OpenClawBridge;
  // Operator finding 2026-06-16: a short, DETERMINISTIC, honest Swedish line
  // derived from decision + bridge (how the prompt was interpreted + what was
  // done or why not). /api/prompt uses it as the answerText floor when the LLM
  // chat helper produces nothing (no key / timeout), so an applied edit / honest
  // no-op is never stum. Null when the Python seam did not emit it (field-drift).
  report: string | null;
};

export type OpenClawApplyOptions = {
  /** Required: the apply bridge needs a concrete site to iterate on. */
  siteId: string;
  /** Optional baseRunId to iterate from; forwarded to the chain. */
  baseRunId?: string;
};

function coerceBridge(raw: unknown): OpenClawBridge {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return {
      status: "unknown",
      applied: false,
      previewShouldRefresh: false,
      chain: null,
    };
  }
  const obj = raw as Record<string, unknown>;
  const chain =
    obj.chain && typeof obj.chain === "object" && !Array.isArray(obj.chain)
      ? (obj.chain as Record<string, unknown>)
      : null;
  return {
    status: typeof obj.status === "string" ? obj.status : "unknown",
    applied: obj.applied === true,
    previewShouldRefresh: obj.previewShouldRefresh === true,
    chain,
  };
}

/**
 * OpenClaw action-bridge (skiva 1b, action half): run
 * ``run_openclaw_followup.py --apply`` so an ``edit_instruction`` actually
 * MATERIALISES a new version via the KÖR-7 chain (router -> context -> patch ->
 * apply -> targeted render). Read-only kinds (answer/clarification/plan_only)
 * and any unmapped/no-op edit NEVER build — the chain stops at an honest gate
 * and the bridge reports ``applied=false`` BEFORE any build, so /api/prompt can
 * fall back to the unchanged legacy build path with no double-build.
 *
 * Returns ``{decision, bridge}`` verbatim, or ``null`` when the message is empty
 * / no siteId / the helper fails or times out — callers treat ``null`` as "no
 * OpenClaw apply available" and fall back to unchanged behaviour.
 */
export async function runOpenClawFollowupApply(
  message: string,
  options: OpenClawApplyOptions,
): Promise<OpenClawApplyResult | null> {
  const trimmed = message.trim();
  if (!trimmed) return null;
  const siteId = options.siteId?.trim();
  if (!siteId) return null;

  const scriptPath = path.join(
    repoRoot(),
    "scripts",
    "run_openclaw_followup.py",
  );
  const args = [scriptPath, "--apply", "--site-id", siteId];
  if (options.baseRunId) args.push("--base-run-id", options.baseRunId);
  // B204: pass the message through a UTF-8 temp file instead of argv so a
  // non-ASCII leading char survives the Windows spawn hop intact (same
  // defensive transport as runOpenClawFollowup).
  const messageArg = writeTextArgFile(trimmed, "sb-openclaw-apply-");
  args.push("--message-file", messageArg.path);

  const child = spawn(pythonCommand(), args, {
    cwd: repoRoot(),
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const stdoutChunks: Buffer[] = [];
  let totalStdoutBytes = 0;
  const MAX_STREAM_BYTES = 512 * 1024;
  child.stdout.on("data", (chunk: Buffer) => {
    stdoutChunks.push(chunk);
    totalStdoutBytes += chunk.byteLength;
    // B174: --apply shares stdout with build()'s npm/progress noise and the
    // bridge payload is the LAST line, so an overflowing stream must drop the
    // OLDEST chunks (the previous head-keeping cap dropped the payload).
    while (
      stdoutChunks.length > 1 &&
      totalStdoutBytes - stdoutChunks[0].byteLength >= MAX_STREAM_BYTES
    ) {
      totalStdoutBytes -= stdoutChunks[0].byteLength;
      stdoutChunks.shift();
    }
  });
  child.stderr.on("data", () => {});

  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    // Unlike the read-only path, --apply spawns npm install + next build as
    // descendants of python. A plain child.kill() would orphan them (a
    // process/port leak, and on Windows the same .node file-lock class B157
    // fixed). Tree-kill via the shared helper (Windows: taskkill /T /F).
    void killProcessTree(child, "SIGTERM");
  }, OPENCLAW_APPLY_TIMEOUT_MS);

  let exitCode: number;
  try {
    exitCode = await new Promise<number>((resolve, reject) => {
      child.once("error", reject);
      child.once("close", (code) => resolve(code ?? 1));
    });
  } catch {
    clearTimeout(timeout);
    messageArg.cleanup();
    return null;
  }
  clearTimeout(timeout);
  messageArg.cleanup();

  if (timedOut || exitCode !== 0) return null;

  const stdout = Buffer.concat(stdoutChunks).toString("utf-8").trim();
  if (!stdout) return null;

  // B174 root-cause fix: the chain prints human progress ("runId: ...",
  // "Copying starter ...", npm output) to the SAME stdout BEFORE the bridge
  // JSON, so the previous blind JSON.parse of the whole stream threw on EVERY
  // successful apply and the B164 recovery forced an unearned degraded status.
  // Extract the payload robustly instead; the expected-shape guard requires
  // the ``decision`` object so npm JSON noise can never be mistaken for it.
  const obj = extractPayloadJson(
    stdout,
    (candidate) =>
      Boolean(
        candidate.decision &&
          typeof candidate.decision === "object" &&
          !Array.isArray(candidate.decision),
      ),
  );
  if (!obj) return null;
  const decision = obj.decision;
  if (!decision || typeof decision !== "object" || Array.isArray(decision)) {
    return null;
  }
  return {
    decision: decision as OpenClawDecisionPayload,
    bridge: coerceBridge(obj.bridge),
    report: typeof obj.report === "string" ? obj.report : null,
  };
}
