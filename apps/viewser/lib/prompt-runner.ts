import { spawn } from "node:child_process";
import path from "node:path";

const PROMPT_TIMEOUT_MS = 90_000;

const SITE_ID_LINE = /^siteId:\s*(.+)$/m;
const PROJECT_ID_LINE = /^projectId:\s*(.+)$/m;
const DOSSIER_PATH_LINE = /^dossierPath:\s*(.+)$/m;
const META_PATH_LINE = /^metaPath:\s*(.+)$/m;
const BRIEF_SOURCE_LINE = /^briefSource:\s*(.+)$/m;

function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

function pythonCommand(): string {
  return process.platform === "win32" ? "python" : "python3";
}

export type PromptHelperResult = {
  siteId: string;
  projectId: string;
  dossierPath: string;
  metaPath: string;
  briefSource: string | null;
  stderr: string;
};

/**
 * Spawn `scripts/prompt_to_project_input.py` and parse its stdout.
 *
 * Mirrors the spawn pattern in build-runner.ts (we already shell out to
 * Python for build_site.py) so the two tools share one mental model:
 * apps/viewser/ never writes to data/ or examples/ itself per
 * repo-boundaries.v1.json - the Python script in scripts/ does the
 * writing on viewser's behalf, exactly the same way build_site.py does
 * for `data/runs/` + `.generated/`.
 *
 * Concurrency control lives one layer up in build-runner.ts: this
 * helper deliberately stays single-purpose so it can be unit-tested
 * without the build mutex.
 */
export async function runPromptToProjectInput(
  prompt: string,
): Promise<PromptHelperResult> {
  const trimmed = prompt.trim();
  if (!trimmed) {
    throw new Error("Prompt får inte vara tom.");
  }

  const scriptPath = path.join(repoRoot(), "scripts", "prompt_to_project_input.py");
  // The `--` separator stops argparse from interpreting a prompt that
  // happens to start with `-` or `--` (e.g. a pasted bullet list like
  // "- skapa en sajt...") as a CLI option. Without it the spawn fails
  // before the helper can write a Project Input.
  const child = spawn(pythonCommand(), [scriptPath, "--", trimmed], {
    cwd: repoRoot(),
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  const stdoutChunks: string[] = [];
  const stderrChunks: string[] = [];
  let totalStdoutBytes = 0;
  let totalStderrBytes = 0;
  const MAX_STREAM_BYTES = 256 * 1024;

  child.stdout.on("data", (chunk: Buffer) => {
    if (totalStdoutBytes >= MAX_STREAM_BYTES) return;
    totalStdoutBytes += chunk.byteLength;
    stdoutChunks.push(chunk.toString("utf-8"));
  });
  child.stderr.on("data", (chunk: Buffer) => {
    if (totalStderrBytes >= MAX_STREAM_BYTES) return;
    totalStderrBytes += chunk.byteLength;
    stderrChunks.push(chunk.toString("utf-8"));
  });

  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    child.kill();
    setTimeout(() => {
      if (!child.killed) {
        try {
          child.kill("SIGKILL");
        } catch {
          // ignore
        }
      }
    }, 5_000).unref?.();
  }, PROMPT_TIMEOUT_MS);

  const exitCode = await new Promise<number>((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code) => resolve(code ?? 1));
  });
  clearTimeout(timeout);

  const stdout = stdoutChunks.join("");
  const stderr = stderrChunks.join("");

  if (timedOut) {
    throw new Error(
      `prompt_to_project_input.py överskred ${PROMPT_TIMEOUT_MS}ms och avbröts. stderr=${stderr.slice(-500)}`,
    );
  }
  if (exitCode !== 0) {
    throw new Error(
      `prompt_to_project_input.py misslyckades (exit ${exitCode}).\n${(stderr || stdout).slice(-2000)}`,
    );
  }

  const siteId = stdout.match(SITE_ID_LINE)?.[1]?.trim();
  const projectId = stdout.match(PROJECT_ID_LINE)?.[1]?.trim();
  const dossierPath = stdout.match(DOSSIER_PATH_LINE)?.[1]?.trim();
  const metaPath = stdout.match(META_PATH_LINE)?.[1]?.trim();
  const briefSource = stdout.match(BRIEF_SOURCE_LINE)?.[1]?.trim() ?? null;

  if (!siteId || !projectId || !dossierPath || !metaPath) {
    throw new Error(
      `prompt_to_project_input.py output saknar siteId/projectId/dossierPath/metaPath:\n${stdout.slice(0, 1000)}`,
    );
  }

  return {
    siteId,
    projectId,
    dossierPath,
    metaPath,
    briefSource: briefSource === "None" ? null : briefSource,
    stderr,
  };
}
