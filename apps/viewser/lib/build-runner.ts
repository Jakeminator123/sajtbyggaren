import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";

import { assertProjectInputExists } from "@/lib/project-inputs";
import { readBuildResult, runDirFromId, runsDir } from "@/lib/runs";

const BUILD_TIMEOUT_MS = 180_000;
const RUN_ID_PATTERN = /runId:\s*([a-zA-Z0-9._-]+)/;

let inFlight: Promise<unknown> | null = null;

function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

function pythonCommand(): string {
  return process.platform === "win32" ? "python" : "python3";
}

async function detectLatestRunIdByMtime(): Promise<string | null> {
  const root = runsDir();
  const entries = await fs.readdir(root, { withFileTypes: true });
  const dirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  if (!dirs.length) return null;

  const stats = await Promise.all(
    dirs.map(async (name) => {
      try {
        const stat = await fs.stat(path.join(root, name));
        return { name, mtimeMs: stat.mtimeMs };
      } catch {
        return null;
      }
    }),
  );
  const live = stats.filter((entry): entry is { name: string; mtimeMs: number } => entry !== null);
  if (!live.length) return null;
  live.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return live[0].name;
}

async function runBuildOnce(siteId: string): Promise<{
  runId: string;
  buildResult: Record<string, unknown>;
  stderr: string;
}> {
  const dossierPath = await assertProjectInputExists(siteId);
  const scriptPath = path.join(repoRoot(), "scripts", "build_site.py");

  const child = spawn(
    pythonCommand(),
    [scriptPath, "--dossier", dossierPath],
    {
      cwd: repoRoot(),
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

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
  }, BUILD_TIMEOUT_MS);

  const exitCode = await new Promise<number>((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code) => resolve(code ?? 1));
  });
  clearTimeout(timeout);

  const stdout = stdoutChunks.join("");
  const stderr = stderrChunks.join("");
  if (timedOut) {
    throw new Error(
      `build_site.py överskred ${BUILD_TIMEOUT_MS}ms och avbröts. stderr=${stderr.slice(-500)}`,
    );
  }
  if (exitCode !== 0) {
    throw new Error(
      `build_site.py misslyckades (${exitCode}).\n${stderr || stdout}`.slice(0, 4000),
    );
  }

  const runIdMatch = stdout.match(RUN_ID_PATTERN);
  const runId = runIdMatch?.[1] ?? (await detectLatestRunIdByMtime());
  if (!runId) {
    throw new Error("Kunde inte hitta runId från build-resultatet.");
  }

  await runDirFromId(runId);
  const buildResult = await readBuildResult(runId);
  return { runId, buildResult, stderr };
}

/**
 * Run build_site.py for a given siteId. Concurrent invocations are serialized
 * with a single in-flight promise so two parallel POSTs do not race over the
 * same `.generated/<siteId>/` directory or confuse the "latest run" fallback.
 */
export async function runBuild(siteId: string): Promise<{
  runId: string;
  buildResult: Record<string, unknown>;
  stderr: string;
}> {
  while (inFlight) {
    try {
      await inFlight;
    } catch {
      // previous build failed; that's fine, fall through and start a new one
    }
  }

  const promise = runBuildOnce(siteId);
  inFlight = promise.finally(() => {
    if (inFlight === promise) {
      inFlight = null;
    }
  });
  return promise;
}
