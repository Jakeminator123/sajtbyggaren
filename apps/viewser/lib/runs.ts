import { promises as fs } from "node:fs";
import path from "node:path";

const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;

export type RunMeta = {
  runId: string;
  status: string;
  siteId: string;
  createdAt: string;
};

function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

export function runsDir(): string {
  const configured = process.env.VIEWSER_RUNS_DIR ?? "../../data/runs";
  return path.resolve(process.cwd(), configured);
}

export function assertSafeRunId(runId: string): void {
  if (!RUN_ID_PATTERN.test(runId)) {
    throw new Error(`Ogiltigt runId: ${runId}`);
  }
}

export async function readJsonFile<T>(filePath: string): Promise<T> {
  const raw = await fs.readFile(filePath, "utf-8");
  return JSON.parse(raw) as T;
}

export async function listRuns(limit = 20): Promise<RunMeta[]> {
  const dir = runsDir();
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const directories = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);

  const metas = await Promise.all(
    directories.map(async (runId) => {
      const buildResultPath = path.join(dir, runId, "build-result.json");
      try {
        const result = await readJsonFile<{ status?: string; siteId?: string }>(buildResultPath);
        const stats = await fs.stat(path.join(dir, runId));
        return {
          runId,
          status: result.status ?? "unknown",
          siteId: result.siteId ?? "unknown",
          createdAt: stats.birthtime.toISOString(),
        };
      } catch {
        return null;
      }
    }),
  );

  return metas
    .filter((meta): meta is RunMeta => meta !== null)
    .sort((a, b) => (a.runId > b.runId ? -1 : 1))
    .slice(0, limit);
}

export async function runDirFromId(runId: string): Promise<string> {
  assertSafeRunId(runId);
  const candidate = path.resolve(runsDir(), runId);
  const relative = path.relative(runsDir(), candidate);

  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`runId pekar utanför runs-katalogen: ${runId}`);
  }

  const stats = await fs.stat(candidate);
  if (!stats.isDirectory()) {
    throw new Error(`runId saknar katalog: ${runId}`);
  }
  return candidate;
}

export async function readBuildResult(runId: string): Promise<Record<string, unknown>> {
  const runDir = await runDirFromId(runId);
  return readJsonFile(path.join(runDir, "build-result.json"));
}

export function dossierAbsolutePath(siteId: string): string {
  return path.join(repoRoot(), "examples", `${siteId}.site-dossier.json`);
}
