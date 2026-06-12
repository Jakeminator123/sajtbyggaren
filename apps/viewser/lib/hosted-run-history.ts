/**
 * hosted-run-history — hostad run-historik + artefakt-läsning (B199 v2).
 *
 * Lokalt läser /api/runs och /api/runs/[runId]/{artifacts,trace} direkt från
 * disk (data/runs/). Hostat finns ingen persistent disk — men sedan #307
 * (B199) tarballas varje lyckat hostat bygges data/runs/<runId>/ till blob,
 * och sedan B199 v2 skriver orkestrerings-skriptet dessutom ett durabelt
 * KV-index (se hosted-build-runner.ts: hostedRunIndexKey/hostedRunVersionKey).
 * Den här modulen är läs-sidan av det kontraktet:
 *
 *   1. ``listHostedRunsForSite`` — per-versions-posterna för EN sajt, mappade
 *      till samma RunMeta-form som lokala listRuns. siteId är medvetet
 *      capability-nyckeln (samma åtkomstmodell som B196:s siteId-bundna
 *      status-route): det finns ingen global publik listning av alla sajters
 *      runs hostat — det vore en integritetsläcka på en oautentiserad route.
 *   2. ``resolveHostedRunEntry`` — kanonisk runId → indexpost, med ärlig
 *      fallback via orkestrerings-UUID:t (äldre flikar/sessioner väljer det).
 *   3. ``fetchHostedRunArtefactsTar`` + ``hostedRunArtefactBundle`` +
 *      ``hostedRunTrace`` — hämtar versionens run-artifacts.tar.gz från blob,
 *      packar upp i minnet (gunzip + minimal ustar-läsare; tarballen skapas
 *      av vårt eget skript med korta paths) och serverar samma bundle-/
 *      trace-former som de lokala läsarna.
 *
 * Allt är best-effort och ärligt degraderande: saknade indexposter eller
 * o-hämtbara tarballs blir null (→ 404 i routen), aldrig påhittade data.
 */

import { gunzipSync } from "node:zlib";

import {
  hostedRunIndexKey,
  hostedRunKey,
  hostedRunStateKey,
  type HostedBuildRunStatus,
  type HostedRunIndexEntry,
  type HostedRunStatePointer,
} from "./hosted-build-runner";
import { getKvStore, kvGetJson } from "./kv-store";
import type { ProjectInputInfo } from "./project-inputs";
import {
  parseTraceLine,
  type RunArtefactBundle,
  type RunMeta,
  type RunStatus,
  type RunTraceResponse,
  type TraceEvent,
} from "./runs";

const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/** Tak för antal indexnycklar vi läser per listning (skydd mot KV-svulst). */
const MAX_VERSION_KEYS = 100;
/** Tak för uppackad tarball (run-artefakterna är JSON + trace — små). */
const MAX_TAR_BYTES = 64 * 1024 * 1024;
/** Tak för antal tar-entries (defense-in-depth mot trasig tarball). */
const MAX_TAR_ENTRIES = 2_000;
/** Hämtningstimeout mot blob (artefakt-tarball + project-input). */
const BLOB_FETCH_TIMEOUT_MS = 10_000;

const TRACE_DEFAULT_LIMIT = 50;
const TRACE_MAX_LIMIT = 500;

/**
 * Liten TTL-cache för listningarna: trace-pollern frågar /api/runs?siteId=
 * med några sekunders mellanrum under ett bygge, och varje listning kostar
 * en KV-SCAN + N GET. 5 s är kort nog att en nyss klar build syns snabbt
 * (klienten har dessutom session-fallbacken i builderTarget under tiden).
 */
const LIST_CACHE_TTL_MS = 5_000;
const listCache = new Map<
  string,
  { at: number; runs: RunMeta[]; entries: HostedRunIndexEntry[] }
>();

/** Tarballs är versions-scopade och immutabla → cachas per URL (FIFO, max 8). */
const tarCache = new Map<string, Map<string, Buffer>>();
const TAR_CACHE_MAX = 8;

/** Project-input-blobbar är versions-scopade och immutabla → cache per URL. */
const projectInputCache = new Map<string, ProjectInputInfo>();
const PROJECT_INPUT_CACHE_MAX = 64;

function isValidEntry(value: unknown): value is HostedRunIndexEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Partial<HostedRunIndexEntry>;
  return (
    typeof entry.runId === "string" &&
    entry.runId.length > 0 &&
    RUN_ID_PATTERN.test(entry.runId) &&
    typeof entry.siteId === "string" &&
    SITE_ID_PATTERN.test(entry.siteId) &&
    typeof entry.updatedAt === "string"
  );
}

/** Pekarens senaste version som indexpost (för sajter byggda före B199 v2). */
function entryFromPointer(
  siteId: string,
  pointer: HostedRunStatePointer | null,
): HostedRunIndexEntry | null {
  if (!pointer || typeof pointer.runId !== "string" || !pointer.runId) {
    return null;
  }
  const entry: HostedRunIndexEntry = {
    runId: pointer.runId,
    siteId,
    version: typeof pointer.version === "number" ? pointer.version : null,
    updatedAt: typeof pointer.updatedAt === "string" ? pointer.updatedAt : "",
  };
  if (typeof pointer.buildId === "string" && pointer.buildId) {
    entry.buildId = pointer.buildId;
  }
  if (typeof pointer.buildStatus === "string" && pointer.buildStatus) {
    entry.buildStatus = pointer.buildStatus;
  }
  if (
    typeof pointer.runArtifactsUrl === "string" &&
    pointer.runArtifactsUrl.startsWith("https://")
  ) {
    entry.runArtifactsUrl = pointer.runArtifactsUrl;
  }
  return entry;
}

async function loadSiteEntries(siteId: string): Promise<HostedRunIndexEntry[]> {
  const store = getKvStore();
  // Samma namnrymd som hostedRunVersionKey — prefixet utan versionssiffran.
  const prefix = `viewser:site:${siteId}:run:v`;
  let keys: string[] = [];
  try {
    keys = await store.listKeys(prefix);
  } catch {
    keys = [];
  }
  const versionKeys = keys
    .filter((key) => /:run:v\d+$/.test(key))
    .slice(0, MAX_VERSION_KEYS);
  const rawEntries = await Promise.all(
    versionKeys.map((key) => kvGetJson<HostedRunIndexEntry>(store, key)),
  );
  const entries = rawEntries.filter(
    (entry): entry is HostedRunIndexEntry =>
      isValidEntry(entry) && entry.siteId === siteId,
  );
  // Sajter byggda före B199 v2 saknar per-versions-poster men har (efter
  // #307) en run-state-pekare med runId — syntetisera senaste versionen så
  // historiken inte är tom för befintliga hostade sajter.
  const pointer = await kvGetJson<HostedRunStatePointer>(
    store,
    hostedRunStateKey(siteId),
  );
  const synthesized = entryFromPointer(siteId, pointer);
  if (synthesized && !entries.some((entry) => entry.runId === synthesized.runId)) {
    entries.push(synthesized);
  }
  entries.sort((a, b) => {
    const versionA = typeof a.version === "number" ? a.version : -1;
    const versionB = typeof b.version === "number" ? b.version : -1;
    if (versionA !== versionB) return versionB - versionA;
    return a.updatedAt > b.updatedAt ? -1 : 1;
  });
  return entries;
}

function entryToRunMeta(entry: HostedRunIndexEntry): RunMeta {
  return {
    runId: entry.runId,
    status: entry.buildStatus ?? "unknown",
    siteId: entry.siteId,
    version: typeof entry.version === "number" ? entry.version : null,
    createdAt: entry.updatedAt,
  };
}

/**
 * Den hostade motsvarigheten till ``listRuns(limit, { siteId })``: sajtens
 * per-versions-poster ur KV, nyaste först, i samma RunMeta-form som lokalt.
 */
export async function listHostedRunsForSite(
  siteId: string,
  limit = 20,
): Promise<{ runs: RunMeta[]; entries: HostedRunIndexEntry[] }> {
  if (!SITE_ID_PATTERN.test(siteId)) return { runs: [], entries: [] };
  const cached = listCache.get(siteId);
  if (cached && Date.now() - cached.at < LIST_CACHE_TTL_MS) {
    return { runs: cached.runs.slice(0, limit), entries: cached.entries };
  }
  const entries = await loadSiteEntries(siteId);
  const runs = entries.map(entryToRunMeta);
  listCache.set(siteId, { at: Date.now(), runs, entries });
  if (listCache.size > 64) {
    const oldest = listCache.keys().next().value;
    if (oldest !== undefined) listCache.delete(oldest);
  }
  return { runs: runs.slice(0, limit), entries };
}

/**
 * Hostad ProjectInputInfo för en sajt: läses ur run-state-pekarens
 * project-input-blob (immutabel versions-URL → cache). ``source`` är
 * "prompt-inputs" så builderTarget-grinden i studio-sidan fungerar
 * identiskt hostat och lokalt. Fallback: minimal post med siteId som namn
 * (ärligt — hellre en grå rad än ingen followup-yta alls).
 */
export async function hostedProjectInputForSite(
  siteId: string,
): Promise<ProjectInputInfo | null> {
  if (!SITE_ID_PATTERN.test(siteId)) return null;
  const store = getKvStore();
  const pointer = await kvGetJson<HostedRunStatePointer>(
    store,
    hostedRunStateKey(siteId),
  );
  if (!pointer) return null;
  const fallback: ProjectInputInfo = {
    siteId,
    companyName: siteId,
    scaffoldId: "",
    variantId: "",
    language: "sv",
    source: "prompt-inputs",
  };
  const url = pointer.projectInputUrl;
  if (typeof url !== "string" || !url.startsWith("https://")) {
    return fallback;
  }
  const cached = projectInputCache.get(url);
  if (cached) return cached;
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(BLOB_FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return fallback;
    const parsed = (await response.json()) as {
      siteId?: unknown;
      scaffoldId?: unknown;
      variantId?: unknown;
      language?: unknown;
      company?: { name?: unknown };
    };
    const info: ProjectInputInfo = {
      siteId,
      companyName:
        typeof parsed.company?.name === "string" && parsed.company.name
          ? parsed.company.name
          : siteId,
      scaffoldId: typeof parsed.scaffoldId === "string" ? parsed.scaffoldId : "",
      variantId: typeof parsed.variantId === "string" ? parsed.variantId : "",
      language: typeof parsed.language === "string" ? parsed.language : "sv",
      source: "prompt-inputs",
    };
    projectInputCache.set(url, info);
    if (projectInputCache.size > PROJECT_INPUT_CACHE_MAX) {
      const oldest = projectInputCache.keys().next().value;
      if (oldest !== undefined) projectInputCache.delete(oldest);
    }
    return info;
  } catch {
    return fallback;
  }
}

/**
 * Kanonisk runId → indexpost. Fallback för orkestrerings-UUID:t (äldre
 * flikar väljer det efter init-byggen före B199 v2): UUID-statusdoken bär
 * siteId + buildId, och buildId matchas mot sajtens poster.
 */
export async function resolveHostedRunEntry(
  runId: string,
): Promise<HostedRunIndexEntry | null> {
  if (!RUN_ID_PATTERN.test(runId) || runId.length > 200) return null;
  const store = getKvStore();
  const direct = await kvGetJson<HostedRunIndexEntry>(
    store,
    hostedRunIndexKey(runId),
  );
  if (isValidEntry(direct)) return direct;
  const status = await kvGetJson<HostedBuildRunStatus>(
    store,
    hostedRunKey(runId),
  );
  if (
    !status ||
    typeof status.siteId !== "string" ||
    !SITE_ID_PATTERN.test(status.siteId) ||
    typeof status.buildId !== "string" ||
    !status.buildId
  ) {
    return null;
  }
  const entries = await loadSiteEntries(status.siteId);
  return entries.find((entry) => entry.buildId === status.buildId) ?? null;
}

function readCString(block: Buffer, offset: number, length: number): string {
  const slice = block.subarray(offset, offset + length);
  const nul = slice.indexOf(0);
  return slice.toString("utf-8", 0, nul === -1 ? slice.length : nul);
}

/**
 * Minimal ustar/gnu-tar-läsare för tarballs VI själva skapar i sandboxen
 * (korta paths under <runId>/, inga symlänkar). Stödet är medvetet smalt:
 * filer ('0'/NUL), kataloger ('5', hoppas över), GNU longname ('L') och
 * pax-huvuden ('x'/'g', hoppas över). Allt annat ignoreras tyst.
 */
function extractTarEntries(tar: Buffer): Map<string, Buffer> {
  const files = new Map<string, Buffer>();
  let offset = 0;
  let pendingLongName: string | null = null;
  let entriesSeen = 0;
  while (offset + 512 <= tar.length && entriesSeen < MAX_TAR_ENTRIES) {
    const block = tar.subarray(offset, offset + 512);
    offset += 512;
    if (block.every((byte) => byte === 0)) break;
    entriesSeen += 1;
    const rawName = readCString(block, 0, 100);
    const sizeRaw = readCString(block, 124, 12).trim();
    const size = Number.parseInt(sizeRaw || "0", 8);
    const safeSize = Number.isFinite(size) && size > 0 ? size : 0;
    const typeByte = block[156];
    const prefix = readCString(block, 345, 155);
    const data = tar.subarray(offset, offset + safeSize);
    offset += Math.ceil(safeSize / 512) * 512;
    if (typeByte === 0x4c) {
      // GNU longname ('L'): nästa entrys namn ligger i datablocket.
      pendingLongName = data.toString("utf-8").replace(/\0+$/, "");
      continue;
    }
    if (typeByte === 0x78 || typeByte === 0x67) continue; // pax-huvuden
    const name = (
      pendingLongName ?? (prefix ? `${prefix}/${rawName}` : rawName)
    ).replace(/^\.\//, "");
    pendingLongName = null;
    if (typeByte === 0x35) continue; // katalog
    if (typeByte !== 0x30 && typeByte !== 0x00) continue;
    if (!name || name.includes("..")) continue;
    files.set(name, Buffer.from(data));
  }
  return files;
}

/**
 * Hämta + packa upp versionens run-artifacts.tar.gz. null vid saknad URL,
 * nätverksfel, för stor tarball eller trasig gzip — callern svarar 404.
 */
export async function fetchHostedRunArtefactsTar(
  entry: HostedRunIndexEntry,
): Promise<Map<string, Buffer> | null> {
  const url = entry.runArtifactsUrl;
  if (typeof url !== "string" || !url.startsWith("https://")) return null;
  const cached = tarCache.get(url);
  if (cached) return cached;
  try {
    const response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(BLOB_FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return null;
    const compressed = Buffer.from(await response.arrayBuffer());
    const tar = gunzipSync(compressed, { maxOutputLength: MAX_TAR_BYTES });
    const files = extractTarEntries(tar);
    if (files.size === 0) return null;
    tarCache.set(url, files);
    if (tarCache.size > TAR_CACHE_MAX) {
      const oldest = tarCache.keys().next().value;
      if (oldest !== undefined) tarCache.delete(oldest);
    }
    return files;
  } catch {
    return null;
  }
}

function readTarJson(
  files: Map<string, Buffer>,
  runId: string,
  filename: string,
): Record<string, unknown> | null {
  const raw = files.get(`${runId}/${filename}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw.toString("utf-8")) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Samma bundle-form som lokala ``readRunArtefacts`` — ur tarballen. */
export function hostedRunArtefactBundle(
  entry: HostedRunIndexEntry,
  files: Map<string, Buffer>,
): RunArtefactBundle {
  const buildResult = readTarJson(files, entry.runId, "build-result.json");
  const qualityResult = readTarJson(files, entry.runId, "quality-result.json");
  const repairResult = readTarJson(files, entry.runId, "repair-result.json");
  const siteBrief = readTarJson(files, entry.runId, "site-brief.json");
  const sitePlan = readTarJson(files, entry.runId, "site-plan.json");
  const missingArtefacts: string[] = [];
  if (!buildResult) missingArtefacts.push("build-result.json");
  if (!qualityResult) missingArtefacts.push("quality-result.json");
  if (!repairResult) missingArtefacts.push("repair-result.json");
  if (!siteBrief) missingArtefacts.push("site-brief.json");
  if (!sitePlan) missingArtefacts.push("site-plan.json");
  return {
    runId: entry.runId,
    buildResult,
    qualityResult,
    repairResult,
    siteBrief,
    sitePlan,
    missingArtefacts,
  };
}

function clampTraceLimit(raw: number | undefined): number {
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw <= 0) {
    return TRACE_DEFAULT_LIMIT;
  }
  return Math.min(Math.floor(raw), TRACE_MAX_LIMIT);
}

/**
 * Samma trace-form som lokala ``readRunTrace`` — ur tarballen. Hostade
 * poster finns bara för FÄRDIGA byggen, så runStatus kommer alltid från
 * build-result (aldrig pending/aborted-heuristiken).
 */
export function hostedRunTrace(
  entry: HostedRunIndexEntry,
  files: Map<string, Buffer>,
  options: { since?: string; limit?: number } = {},
): RunTraceResponse {
  const limit = clampTraceLimit(options.limit);
  const sinceMs = options.since ? Date.parse(options.since) : null;
  if (options.since && !Number.isFinite(sinceMs)) {
    throw new Error("Ogiltigt since-timestamp.");
  }
  let traceCorrupt = false;
  let events: TraceEvent[] = [];
  const raw = files.get(`${entry.runId}/trace.ndjson`);
  if (raw) {
    for (const line of raw.toString("utf-8").split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const parsed = parseTraceLine(trimmed);
      if (parsed === null) {
        traceCorrupt = true;
        continue;
      }
      if (sinceMs !== null && Number.isFinite(sinceMs)) {
        const ts = Date.parse(parsed.timestamp);
        if (!Number.isFinite(ts)) {
          traceCorrupt = true;
          continue;
        }
        if (ts <= sinceMs) continue;
      }
      events.push(parsed);
    }
  }
  if (events.length > limit) {
    events = events.slice(events.length - limit);
  }
  const buildResult = readTarJson(files, entry.runId, "build-result.json");
  let runStatus: RunStatus = "unknown";
  const statusValue = buildResult?.status;
  if (
    statusValue === "ok" ||
    statusValue === "degraded" ||
    statusValue === "failed" ||
    statusValue === "skipped"
  ) {
    runStatus = statusValue;
  }
  const runPrefix = `${entry.runId}/`;
  const artefactsPresent = Array.from(files.keys())
    .filter((name) => name.startsWith(runPrefix))
    .map((name) => name.slice(runPrefix.length))
    .filter((name) => name.length > 0 && !name.includes("/"))
    .sort();
  const response: RunTraceResponse = {
    runId: entry.runId,
    runStatus,
    events,
    artefactsPresent,
  };
  if (traceCorrupt) {
    response.traceCorrupt = true;
  }
  return response;
}
