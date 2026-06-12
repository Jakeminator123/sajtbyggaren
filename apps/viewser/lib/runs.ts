import { promises as fs } from "node:fs";
import type { Dirent } from "node:fs";
import type { Stats } from "node:fs";
import path from "node:path";

const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/**
 * Run-status surfaced by `/api/runs` and `/api/runs/[runId]/trace`.
 *
 *   - `pending`  – run finns på disk men `build-result.json` saknas än OCH
 *                  run-mappen har varit aktiv nyligen. UI ritar en optimistisk
 *                  "pågår"-rad. (GAP-backend-build-trace-endpoint.)
 *   - `aborted`  – `build-result.json` saknas men run-mappen har varit inaktiv
 *                  längre än `STALE_PENDING_TIMEOUT_MS`. Builder-kontraktet skriver
 *                  ALLTID build-result.json (även vid fel), så en saknad fil efter
 *                  rimlig byggtid = hård kill (flik stängd, Cursor-omstart), inte
 *                  ett pågående bygge. Rapporteras ärligt som avbrutet i st.f. att
 *                  hänga `pending`/grå för evigt och vilseleda operatören.
 *   - `ok` / `degraded` / `failed` / `skipped` – speglar `build-result.json:status`.
 *   - `unknown` – run-mappen finns men varken build-result eller trace
 *                 hittades; UI väljer själv hur den vill rendera.
 */
export type RunStatus =
  | "pending"
  | "aborted"
  | "ok"
  | "degraded"
  | "failed"
  | "skipped"
  | "unknown";

// Ett bygge som dödas mitt i (flik stängd, Cursor-omstart, avbruten session)
// hinner aldrig skriva `build-result.json` eller promota `current.json`. Utan
// en tidsgräns rapporteras en sådan run som `pending` för evigt (grå prick),
// vilket vilseleder operatören att tro att ett bygge fortfarande pågår. Efter
// den här timeouten utan aktivitet (sista trace-event eller run-mappens
// birthtime) rapporterar vi den ärligt som `aborted` i stället. Gränsen är
// medvetet generös (> npm install + next build) så ett legitimt långsamt bygge
// aldrig felflaggas. `VIEWSER_STALE_PENDING_MS` kan justera den.
const DEFAULT_STALE_PENDING_TIMEOUT_MS = 15 * 60 * 1000;

function stalePendingTimeoutMs(): number {
  const raw = Number(process.env.VIEWSER_STALE_PENDING_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_STALE_PENDING_TIMEOUT_MS;
}

/**
 * En pending run (ingen build-result.json) är "stale" — och alltså avbruten,
 * inte pågående — om dess senaste aktivitet är äldre än timeouten. Vi mäter
 * aktivitet som det senare av sista trace-event och run-mappens birthtime
 * (millisekunder). `lastActivityMs <= 0` (okänd) behandlas konservativt som
 * INTE stale så vi aldrig felflaggar en run vi saknar tidsdata för.
 */
function isStalePending(lastActivityMs: number, now: number = Date.now()): boolean {
  if (!Number.isFinite(lastActivityMs) || lastActivityMs <= 0) return false;
  return now - lastActivityMs > stalePendingTimeoutMs();
}

export type RunMeta = {
  runId: string;
  status: string;
  siteId: string;
  projectId?: string;
  version?: number | null;
  createdAt: string;
  /** Sätts bara på pending/aborted-runs (inläst från sista trace-event). */
  currentPhase?: string;
  /** Sätts bara på pending/aborted-runs (inläst från sista trace-event). */
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
  // ``...up`` (spread av variabel-array) gör resultatet opakt för Turbopacks
  // statiska analys, så repo-rot-baserade path.join() inte viks ihop till
  // fil/dir-asset-referenser. Med ``turbopack.root`` = repo-roten (krävs för
  // att resolva ``@preview-runtime``) skulle annars output-tracern kunna panika
  // på symlänkar (t.ex. ``.venv``) som pekar ut ur repo-roten. Detta är rent
  // runtime-logik, aldrig en modul.
  const up = ["..", ".."];
  return path.resolve(process.cwd(), ...up);
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
  // Senaste aktivitet = det senare av sista trace-event och run-mappens
  // birthtime. Ett dött bygge (saknad build-result.json) som varit inaktivt
  // längre än timeouten rapporteras som `aborted`, inte `pending` — annars
  // hänger den grå för evigt och vilseleder operatören (preview promotas
  // aldrig). Ett legitimt pågående/nyss startat bygge har färsk aktivitet och
  // förblir `pending`.
  const lastTraceMs = lastTrace ? Date.parse(lastTrace.timestamp) : Number.NaN;
  const lastActivityMs = Number.isFinite(lastTraceMs)
    ? Math.max(lastTraceMs, stats.birthtimeMs)
    : stats.birthtimeMs;
  const meta: RunMeta = {
    runId,
    status: isStalePending(lastActivityMs) ? "aborted" : "pending",
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

// Exporterad så den hostade trace-läsningen (lib/hosted-run-history.ts)
// delar EXAKT samma radparsning som den lokala disk-vägen.
export function parseTraceLine(line: string): TraceEvent | null {
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
    // Spread gör sökvägen opak för Turbopacks statiska analys så den inte
    // bygger en bred ``require.context``-liknande modul över data/runs (med
    // ``turbopack.root`` = repo-roten skulle ett literalt ``path.join`` annars
    // matcha tusentals run-artefakter och blåsa upp route-bundlen).
    const artefactPath = path.join(...[runDir, filename]);
    return await readJsonFile(artefactPath);
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
 * B155 path B (ADR 0034): strikt typad copy-direktiv som FloatingChat
 * härleder en svensk success-rad från ("Jag ändrade företagsnamnet
 * till '...'."). Schema-låst i
 * ``governance/schemas/project-input.schema.json:directives.copyDirectives``;
 * fält bortom dessa fyra ignoreras medvetet av readern så en framtida
 * v2-utbyggnad inte spiller obekant data ut till UI:t.
 */
export type AppliedCopyDirective = {
  target: "company-name" | "tagline" | "about-text" | "services";
  operation: "replace-text" | "include-token";
  payload: string;
  // Krävs av schemat när target=services (pekar ut services[].id|label som
  // direktivet träffar). Utelämnas för övriga targets.
  targetRef?: string;
  source?: "prompt-rule" | "llm" | "explicit";
};

const COPY_DIRECTIVE_TARGETS = new Set([
  "company-name",
  "tagline",
  "about-text",
  "services",
] as const);
const COPY_DIRECTIVE_OPERATIONS = new Set([
  "replace-text",
  "include-token",
] as const);
const COPY_DIRECTIVE_SOURCES = new Set([
  "prompt-rule",
  "llm",
  "explicit",
] as const);

function isStringIn<T extends string>(
  value: unknown,
  set: ReadonlySet<T>,
): value is T {
  return typeof value === "string" && (set as ReadonlySet<string>).has(value);
}

/**
 * Read ``directives.copyDirectives`` from the project-input snapshot
 * that was the actual input to ``runId``. Returns ``[]`` for init
 * builds, builds without directives, and unparseable artefakter — UI
 * decides how to surface "no directives applied".
 *
 * Auktoritetskedja per Jakobs PR-#136-handoff: ``data/runs/<runId>/
 * input.json:dossierPath`` pekar på exakt den versionens project-
 * input-snapshot (``data/prompt-inputs/<siteId>.vN.project-input.json``
 * för follow-ups). Vi läser DEN filen — inte den senaste på disk —
 * så snabba parallella followups inte blandar ihop direktiv mellan
 * versioner.
 *
 * Säkerhet:
 *   - ``runId`` valideras genom ``runDirFromId`` (path-traversal-skydd).
 *   - Den absoluta dossier-pathen begränsas till repo-root + ``data/
 *     prompt-inputs/`` ELLER repo-root + ``examples/`` (init-fallback).
 *     Andra paths kastas så en stulen ``input.json`` inte kan dirigera
 *     UI:t att läsa godtyckliga filer.
 *   - Varje directive valideras mot schema-enums; okända fält
 *     ignoreras (defense in depth — schemavalideringen i
 *     packages/generation körs redan på write-sidan).
 */
export async function readAppliedCopyDirectives(
  runId: string,
): Promise<AppliedCopyDirective[]> {
  let runDir: string;
  try {
    runDir = await runDirFromId(runId);
  } catch {
    // Tystar runDirFromId: det här är en presentations-helper. Hårda
    // path-fel surface:as redan av artefakt-routerna; här är "inga
    // directives" rätt UX-fallback.
    return [];
  }

  let inputJson: { dossierPath?: unknown };
  try {
    inputJson = await readJsonFile<{ dossierPath?: unknown }>(
      path.join(runDir, "input.json"),
    );
  } catch {
    return [];
  }

  const dossierPath = inputJson.dossierPath;
  if (typeof dossierPath !== "string" || !dossierPath.trim()) {
    return [];
  }

  const root = repoRoot();
  const absoluteDossier = path.isAbsolute(dossierPath)
    ? path.resolve(dossierPath)
    : path.resolve(root, dossierPath);

  const allowedRoots = [
    path.resolve(root, "data", "prompt-inputs"),
    path.resolve(root, "examples"),
  ];
  const insideAllowed = allowedRoots.some((allowed) => {
    const rel = path.relative(allowed, absoluteDossier);
    return !rel.startsWith("..") && !path.isAbsolute(rel);
  });
  if (!insideAllowed) {
    return [];
  }

  let snapshot: Record<string, unknown>;
  try {
    snapshot = await readJsonFile<Record<string, unknown>>(absoluteDossier);
  } catch {
    return [];
  }

  const directives = (snapshot.directives ?? null) as
    | Record<string, unknown>
    | null;
  if (!directives || typeof directives !== "object") {
    return [];
  }

  const raw = (directives.copyDirectives ?? null) as unknown;
  if (!Array.isArray(raw)) {
    return [];
  }

  const result: AppliedCopyDirective[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const candidate = item as Record<string, unknown>;
    if (!isStringIn(candidate.target, COPY_DIRECTIVE_TARGETS)) continue;
    if (!isStringIn(candidate.operation, COPY_DIRECTIVE_OPERATIONS)) continue;
    if (typeof candidate.payload !== "string" || candidate.payload.length === 0) {
      continue;
    }
    // Schema-cap är 600 tecken (about-text); defense-in-depth här så en
    // framtida schema-bump inte oavsiktligt sänker UI-radens budget. Per-target-
    // capparna (company-name 80, tagline 140, about-text 600, services 300) görs
    // redan på write-sidan i packages/generation.
    if (candidate.payload.length > 600) continue;
    // targetRef: schemat kräver en icke-tom referens (services[].id|label,
    // max 80 tecken) när target=services och utelämnar den annars. Validera
    // en gång och återanvänd både för drop-regeln och själva fältet.
    const rawTargetRef =
      typeof candidate.targetRef === "string" ? candidate.targetRef : "";
    const targetRefValid =
      rawTargetRef.trim().length > 0 && rawTargetRef.length <= 80;
    // services UTAN giltig targetRef bryter mot schemat
    // (project-input.schema.json:226-234, ``then.required: targetRef``).
    // Utan den kan UI:t inte säga VILKEN tjänst som ändrades och apply-sidan
    // no-op:ar ändå — släng direktivet i stället för att visa den generiska
    // "uppdaterade en tjänst"-raden som tappar operatörskontext.
    if (candidate.target === "services" && !targetRefValid) continue;
    // about-text/services stödjer bara replace-text per schemat; readern
    // speglar dock bara — apply-sidan i packages/generation äger den semantiska
    // operation-valideringen, så vi normaliserar inte operation här.
    const directive: AppliedCopyDirective = {
      target: candidate.target,
      operation: candidate.operation,
      payload: candidate.payload,
    };
    if (targetRefValid) {
      directive.targetRef = rawTargetRef;
    }
    if (isStringIn(candidate.source, COPY_DIRECTIVE_SOURCES)) {
      directive.source = candidate.source;
    }
    result.push(directive);
    // Schema cap är 8; klipp på samma siffra så vi inte blåser upp
    // FloatingChat-bubblan om någon framtid testar listan utan limits.
    if (result.length >= 8) break;
  }
  return result;
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
  } else {
    // Ingen build-result.json: pending tills bygget skriver den, men markera
    // ärligt som `aborted` om run-mappen varit inaktiv längre än timeouten.
    // Måste matcha listRuns/buildPendingMeta så Run History och trace-pollern
    // är överens — annars skulle use-build-trace-polling polla ett dött bygge
    // (`runStatus === "pending"`) i all oändlighet. Aktivitet = senare av sista
    // trace-event och run-mappens birthtime.
    let lastActivityMs = 0;
    const lastTrace = await readLastTraceEvent(runId);
    const lastTraceMs = lastTrace ? Date.parse(lastTrace.timestamp) : Number.NaN;
    if (Number.isFinite(lastTraceMs)) {
      lastActivityMs = lastTraceMs;
    }
    try {
      const dirStats = await fs.stat(runDir);
      lastActivityMs = Math.max(lastActivityMs, dirStats.birthtimeMs);
    } catch {
      // birthtime ej läsbar — förlita oss på trace-timestampen ovan (om någon).
    }
    if (isStalePending(lastActivityMs)) {
      runStatus = "aborted";
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
