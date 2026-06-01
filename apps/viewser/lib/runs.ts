import { promises as fs } from "node:fs";
import type { Dirent } from "node:fs";
import type { Stats } from "node:fs";
import path from "node:path";

const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/**
 * Run-status surfaced by `/api/runs` and `/api/runs/[runId]/trace`.
 *
 *   - `pending`  – run finns på disk men `build-result.json` saknas än.
 *                  UI ritar en optimistisk "pågår"-rad. (GAP-backend-build-trace-endpoint.)
 *   - `ok` / `degraded` / `failed` / `skipped` – speglar `build-result.json:status`.
 *   - `unknown` – run-mappen finns men varken build-result eller trace
 *                 hittades; UI väljer själv hur den vill rendera.
 */
export type RunStatus = "pending" | "ok" | "degraded" | "failed" | "skipped" | "unknown";

export type RunMeta = {
  runId: string;
  status: string;
  siteId: string;
  projectId?: string;
  version?: number | null;
  createdAt: string;
  /** Sätts bara på pending-runs (inläst från sista trace-event). */
  currentPhase?: string;
  /** Sätts bara på pending-runs (inläst från sista trace-event). */
  currentEvent?: string;
};

export type TraceEvent = {
  runId: string;
  phase: string;
  event: string;
  status: string;
  message: string;
  timestamp: string;
  payloadPath: string | null;
};

export type RunTraceResponse = {
  runId: string;
  runStatus: RunStatus;
  events: TraceEvent[];
  artefactsPresent: string[];
  /** True om trace.ndjson finns men inte kunde parsas helt — UI kan visa varning. */
  traceCorrupt?: boolean;
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

export async function listRuns(
  limit = 20,
  options: { siteId?: string } = {},
): Promise<RunMeta[]> {
  const dir = runsDir();
  let entries: Dirent[];
  try {
    entries = await fs.readdir(dir, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return [];
    }
    throw error;
  }
  const directories = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);

  const liveDirectories = (
    await Promise.all(
      directories.map(async (runId) => {
        try {
          const stats = await fs.stat(path.join(dir, runId));
          return { runId, stats };
        } catch {
          return null;
        }
      }),
    )
  )
    .filter((entry): entry is { runId: string; stats: Stats } => entry !== null)
    .sort((a, b) => b.stats.mtimeMs - a.stats.mtimeMs)
    // B72-lock: slice MUST happen before any JSON read so /api/runs stays
    // O(limit) JSON reads regardless of how many runs sit on disk. When
    // a siteId filter is active we expand the candidate window to limit*4
    // so the post-filter slice-to-limit still has a fair chance of
    // finding the operator's site. The expansion is bounded — not O(N).
    .slice(0, options.siteId ? Math.max(limit * 4, limit) : limit);

  const metas = await Promise.all(
    liveDirectories.map(async ({ runId, stats }) => {
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
        const meta: RunMeta = {
          runId,
          status: result.status ?? "unknown",
          siteId: result.siteId ?? inputMeta.siteId ?? "unknown",
          version,
          createdAt: stats.birthtime.toISOString(),
        };
        if (projectId) {
          meta.projectId = projectId;
        }
        return meta;
      } catch (error) {
        // build-result.json saknas → kandidat för pending-detection.
        // ENOENT är förväntat under en pågående build; allt annat
        // (parse-fel, permission-denied) gör vi tysta så listRuns inte
        // 500:ar för en korrupt run-mapp.
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
          return null;
        }
        return await buildPendingMeta(runId, stats);
      }
    }),
  );

  const sorted = metas
    .filter((meta): meta is RunMeta => meta !== null)
    .sort((a, b) => (a.createdAt > b.createdAt ? -1 : 1));

  const filtered = options.siteId
    ? sorted.filter((meta) => meta.siteId === options.siteId)
    : sorted;
  return filtered.slice(0, limit);
}

async function buildPendingMeta(runId: string, stats: Stats): Promise<RunMeta | null> {
  const inputMeta = await readRunInputMeta(runId);
  // Vi ger upp tyst om input.json saknas också — det är då en helt tom
  // run-mapp och ska inte rapporteras som pending.
  if (inputMeta.version === null && !inputMeta.projectId && !inputMeta.siteId) {
    return null;
  }
  const lastTrace = await readLastTraceEvent(runId);
  const promptMeta = await readPromptMeta(inputMeta.siteId);
  const meta: RunMeta = {
    runId,
    status: "pending",
    siteId: inputMeta.siteId ?? promptMeta.siteId ?? "unknown",
    version: inputMeta.version ?? promptMeta.version,
    createdAt: stats.birthtime.toISOString(),
  };
  const projectId = inputMeta.projectId ?? promptMeta.projectId;
  if (projectId) {
    meta.projectId = projectId;
  }
  if (lastTrace?.phase) {
    meta.currentPhase = lastTrace.phase;
  }
  if (lastTrace?.event) {
    meta.currentEvent = lastTrace.event;
  }
  return meta;
}

async function readLastTraceEvent(runId: string): Promise<TraceEvent | null> {
  try {
    const runDir = path.resolve(runsDir(), runId);
    const tracePath = path.join(runDir, "trace.ndjson");
    const raw = await fs.readFile(tracePath, "utf-8");
    const lines = raw.split("\n").filter((line) => line.trim());
    if (lines.length === 0) return null;
    return parseTraceLine(lines[lines.length - 1]);
  } catch {
    return null;
  }
}

function parseTraceLine(line: string): TraceEvent | null {
  try {
    const parsed = JSON.parse(line) as Partial<TraceEvent>;
    if (
      typeof parsed.runId !== "string" ||
      typeof parsed.phase !== "string" ||
      typeof parsed.event !== "string" ||
      typeof parsed.status !== "string" ||
      typeof parsed.timestamp !== "string"
    ) {
      return null;
    }
    return {
      runId: parsed.runId,
      phase: parsed.phase,
      event: parsed.event,
      status: parsed.status,
      message: typeof parsed.message === "string" ? parsed.message : "",
      timestamp: parsed.timestamp,
      payloadPath:
        typeof parsed.payloadPath === "string" ? parsed.payloadPath : null,
    };
  } catch {
    return null;
  }
}

function stringOrUndefined(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) ? value : null;
}

async function readRunInputMeta(
  runId: string,
): Promise<{ projectId?: string; siteId?: string; version: number | null }> {
  try {
    const runDir = await runDirFromId(runId);
    const input = await readJsonFile<{
      projectId?: unknown;
      siteId?: unknown;
      version?: unknown;
      dossierPath?: unknown;
    }>(path.join(runDir, "input.json"));
    return {
      projectId: stringOrUndefined(input.projectId),
      // Some build_site.py versions write `siteId` directly; older ones
      // only store `dossierPath` and we derive siteId from the filename.
      siteId:
        stringOrUndefined(input.siteId) ?? siteIdFromDossierPath(input.dossierPath),
      version: numberOrNull(input.version),
    };
  } catch {
    return { version: null };
  }
}

function siteIdFromDossierPath(dossierPath: unknown): string | undefined {
  if (typeof dossierPath !== "string") return undefined;
  const base = path.basename(dossierPath);
  // Filename pattern: <siteId>.project-input.json (with optional .vN. variant
  // for follow-up snapshots in data/prompt-inputs/).
  const match = base.match(/^([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)(?:\.v\d+)?\.project-input\.json$/);
  return match?.[1];
}

async function readPromptMeta(
  siteId: string | undefined,
): Promise<{ projectId?: string; siteId?: string; version: number | null }> {
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
      siteId,
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
  sitePlan: Record<string, unknown> | null;
  missingArtefacts: string[];
};

/**
 * Read the five artefakter Builder UX MVP needs to render a run-detail
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
    "site-plan.json",
  ] as const;
  const [buildResult, qualityResult, repairResult, siteBrief, sitePlan] = await Promise.all(
    filenames.map((name) => readArtefactOrNull(runId, name)),
  );

  const missingArtefacts: string[] = [];
  if (!buildResult) missingArtefacts.push("build-result.json");
  if (!qualityResult) missingArtefacts.push("quality-result.json");
  if (!repairResult) missingArtefacts.push("repair-result.json");
  if (!siteBrief) missingArtefacts.push("site-brief.json");
  if (!sitePlan) missingArtefacts.push("site-plan.json");

  return {
    runId,
    buildResult,
    qualityResult,
    repairResult,
    siteBrief,
    sitePlan,
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

const TRACE_DEFAULT_LIMIT = 50;
const TRACE_MAX_LIMIT = 500;

/**
 * Read the tail of `data/runs/<runId>/trace.ndjson` and return the last N
 * events as JSON, plus an explicit `runStatus` (pending if build-result
 * has not landed, otherwise the build-result status). UI uses this for
 * Live Build Sync — see `GAP-backend-build-trace-endpoint.md`.
 *
 * - Read-only; never writes to data/runs.
 * - `since` filters to events strictly after the given ISO timestamp so
 *   UI can poll incrementally without accumulating duplicates.
 * - Corrupt lines are skipped silently and reflected via `traceCorrupt:true`
 *   so the UI may show a soft warning without breaking the page.
 */
export async function readRunTrace(
  runId: string,
  options: { since?: string; limit?: number } = {},
): Promise<RunTraceResponse> {
  const runDir = await runDirFromId(runId);
  const limit = clampLimit(options.limit);
  const sinceMs = parseSinceTimestamp(options.since);
  if (options.since && sinceMs === null) {
    throw new Error("Ogiltigt since-timestamp.");
  }

  const tracePath = path.join(runDir, "trace.ndjson");
  let traceCorrupt = false;
  let events: TraceEvent[] = [];
  try {
    const raw = await fs.readFile(tracePath, "utf-8");
    const lines = raw.split("\n");
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const parsed = parseTraceLine(trimmed);
      if (parsed === null) {
        traceCorrupt = true;
        continue;
      }
      if (sinceMs !== null) {
        const ts = Date.parse(parsed.timestamp);
        if (!Number.isFinite(ts)) {
          // Korrupt timestamp i en annars välformad rad: hade vi släppt
          // igenom den hade varje incremental-poll dragit den igen och
          // UI:et fått upprepade fantom-events. Skippa istället och
          // markera trace som corrupt så pollern kan visa en hint.
          traceCorrupt = true;
          continue;
        }
        if (ts <= sinceMs) continue;
      }
      events.push(parsed);
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      // Permission or other I/O issue: degrade gracefully so a single
      // unreadable trace.ndjson doesn't 500 the endpoint.
      traceCorrupt = true;
    }
  }
  if (events.length > limit) {
    events = events.slice(events.length - limit);
  }

  const buildResult = await readArtefactOrNull(runId, "build-result.json");
  let runStatus: RunStatus = "pending";
  if (buildResult) {
    const value = (buildResult as { status?: unknown }).status;
    if (
      value === "ok" ||
      value === "degraded" ||
      value === "failed" ||
      value === "skipped"
    ) {
      runStatus = value;
    } else {
      runStatus = "unknown";
    }
  }

  const artefactsPresent = await listArtefactNames(runDir);

  const response: RunTraceResponse = {
    runId,
    runStatus,
    events,
    artefactsPresent,
  };
  if (traceCorrupt) {
    response.traceCorrupt = true;
  }
  return response;
}

function clampLimit(raw: number | undefined): number {
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw <= 0) {
    return TRACE_DEFAULT_LIMIT;
  }
  return Math.min(Math.floor(raw), TRACE_MAX_LIMIT);
}

function parseSinceTimestamp(raw: string | undefined): number | null {
  if (!raw) return null;
  const ms = Date.parse(raw);
  return Number.isFinite(ms) ? ms : null;
}

async function listArtefactNames(runDir: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(runDir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile())
      .map((entry) => entry.name)
      .sort();
  } catch {
    return [];
  }
}
