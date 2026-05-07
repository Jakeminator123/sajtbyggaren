import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";

import { assertDossierExists } from "@/lib/dossiers";
import { readBuildResult, runDirFromId, runsDir } from "@/lib/runs";

const BUILD_TIMEOUT_MS = 180_000;
const RUN_ID_PATTERN = /runId:\s*([a-zA-Z0-9._-]+)/;

function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

function pythonCommand(): string {
  return process.platform === "win32" ? "python" : "python3";
}

export async function runBuild(dossierId: string): Promise<{
  runId: string;
  buildResult: Record<string, unknown>;
  stderr: string;
}> {
  const dossierPath = await assertDossierExists(dossierId);
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
  child.stdout.on("data", (chunk: Buffer) => stdoutChunks.push(chunk.toString("utf-8")));
  child.stderr.on("data", (chunk: Buffer) => stderrChunks.push(chunk.toString("utf-8")));

  const timeout = setTimeout(() => {
    child.kill();
  }, BUILD_TIMEOUT_MS);

  const exitCode = await new Promise<number>((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code) => resolve(code ?? 1));
  });
  clearTimeout(timeout);

  const stdout = stdoutChunks.join("");
  const stderr = stderrChunks.join("");
  if (exitCode !== 0) {
    throw new Error(`build_site.py misslyckades (${exitCode}).\n${stderr || stdout}`);
  }

  const runIdMatch = stdout.match(RUN_ID_PATTERN);
  const runId = runIdMatch?.[1] ?? (await detectLatestRunId());
  if (!runId) {
    throw new Error("Kunde inte hitta runId från build-resultatet.");
  }

  await runDirFromId(runId);
  const buildResult = await readBuildResult(runId);
  return { runId, buildResult, stderr };
}

async function detectLatestRunId(): Promise<string | null> {
  const root = runsDir();
  const entries = await fs.readdir(root, { withFileTypes: true });
  const dirs = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  if (!dirs.length) {
    return null;
  }
  return dirs.sort().at(-1) ?? null;
}
