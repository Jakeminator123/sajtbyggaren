import { promises as fs } from "node:fs";
import path from "node:path";

const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

export type RunMeta = {
  runId: string;
  status: string;
  siteId: string;
  projectId?: string;
  version?: number | null;
  createdAt: string;
};

function repoRoot(): string {
  return path.resolve(process.cwd(), "..", "..");
}

export function runsDir(): string {
  const configured = process.env.VIEWSER_RUNS_DIR ?? "../../data/runs";
  return path.resolve(process.cwd(), configured);
}

function promptInputsDir(): string {
  return path.resolve(repoRoot(), "data", "prompt-inputs");
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
        const result = await readJsonFile<{
          status?: string;
          siteId?: string;
          projectId?: unknown;
          version?: unknown;
        }>(buildResultPath);
        const inputMeta = await readRunInputMeta(runId);
        const promptMeta = await readPromptMeta(result.siteId);
        const projectId =
          stringOrUndefined(result.projectId) ??
          inputMeta.projectId ??
          promptMeta.projectId;
        const version =
          numberOrNull(result.version) ?? inputMeta.version ?? promptMeta.version;
        const stats = await fs.stat(path.join(dir, runId));
        const meta: RunMeta = {
          runId,
          status: result.status ?? "unknown",
          siteId: result.siteId ?? "unknown",
          version,
          createdAt: stats.birthtime.toISOString(),
        };
        if (projectId) {
          meta.projectId = projectId;
        }
        return meta;
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

function stringOrUndefined(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

async function readRunInputMeta(
  runId: string,
): Promise<{ projectId?: string; version: number | null }> {
  try {
    const runDir = await runDirFromId(runId);
    const input = await readJsonFile<{
      projectId?: unknown;
      version?: unknown;
    }>(path.join(runDir, "input.json"));
    return {
      projectId: stringOrUndefined(input.projectId),
      version: numberOrNull(input.version),
    };
  } catch {
    return { version: null };
  }
}

async function readPromptMeta(
  siteId: string | undefined,
): Promise<{ projectId?: string; version: number | null }> {
  if (!siteId || siteId === "unknown" || !SITE_ID_PATTERN.test(siteId)) {
    return { version: null };
  }

  try {
    const meta = await readJsonFile<{
      projectId?: unknown;
      siteId?: unknown;
      version?: unknown;
    }>(path.join(promptInputsDir(), `${siteId}.meta.json`));
    if (typeof meta.siteId === "string" && meta.siteId !== siteId) {
      return { version: null };
    }
    return {
      projectId: stringOrUndefined(meta.projectId),
      version: numberOrNull(meta.version),
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return { version: null };
    }
    return { version: null };
  }
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

/**
 * Defensive reader: returns parsed JSON or null when the artefact is
 * missing. Builder UX MVP needs to render older runs (pre-Sprint 3A) and
 * partial run-dirs (Phase 3 schema-validator failure leaves Phase 1+2
 * artefakter on disk) without 500-ing the API. The caller decides how
 * to surface "saknas i äldre run" / "ej spårad än" labels in UI.
 */
export async function readArtefactOrNull(
  runId: string,
  filename: string,
): Promise<Record<string, unknown> | null> {
  try {
    const runDir = await runDirFromId(runId);
    return await readJsonFile(path.join(runDir, filename));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return null;
    }
    throw error;
  }
}

export type RunArtefactBundle = {
  runId: string;
  buildResult: Record<string, unknown> | null;
  qualityResult: Record<string, unknown> | null;
  repairResult: Record<string, unknown> | null;
  siteBrief: Record<string, unknown> | null;
  missingArtefacts: string[];
};

/**
 * Read the four artefakter Builder UX MVP needs to render a run-detail
 * view, defensively. Any missing file is recorded in `missingArtefacts`
 * so the UI can show "saknas i äldre run" instead of crashing.
 */
export async function readRunArtefacts(runId: string): Promise<RunArtefactBundle> {
  // runDirFromId throws on path-escape / missing dir, which is a 4xx-
  // worthy hard error - bubble it up. Per-file misses are soft.
  await runDirFromId(runId);

  const filenames = [
    "build-result.json",
    "quality-result.json",
    "repair-result.json",
    "site-brief.json",
  ] as const;
  const [buildResult, qualityResult, repairResult, siteBrief] = await Promise.all(
    filenames.map((name) => readArtefactOrNull(runId, name)),
  );

  const missingArtefacts: string[] = [];
  if (!buildResult) missingArtefacts.push("build-result.json");
  if (!qualityResult) missingArtefacts.push("quality-result.json");
  if (!repairResult) missingArtefacts.push("repair-result.json");
  if (!siteBrief) missingArtefacts.push("site-brief.json");

  return {
    runId,
    buildResult,
    qualityResult,
    repairResult,
    siteBrief,
    missingArtefacts,
  };
}

/**
 * Resolve the canonical Project Input file for a given siteId.
 *
 * Note: siteId callers MUST validate via `assertSafeSiteId` (see
 * `lib/project-inputs.ts`) before passing to this helper, so a crafted siteId
 * cannot path-escape `examples/`.
 */
export function projectInputAbsolutePath(siteId: string): string {
  return path.join(repoRoot(), "examples", `${siteId}.project-input.json`);
}
