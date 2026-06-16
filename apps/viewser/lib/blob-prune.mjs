/**
 * blob-prune — delad kärna för att inspektera, radera och auto-pruna den
 * HOSTADE lagringen (Vercel Blob + Upstash KV) per genererad sajt.
 *
 * Den här modulen är medvetet plain ESM (``.mjs``) så att BÅDE operatör-CLI:t
 * ``apps/viewser/scripts/blob-admin.mjs`` (kört direkt med ``node``) OCH
 * cron-routen ``app/api/cron/prune-blob/route.ts`` (Next/TypeScript) kan
 * importera EXAKT samma raderingslogik utan duplicering. Routen får typer via
 * JSDoc-annoteringarna nedan (tsconfig ``allowJs``).
 *
 * build-context/ (Python-motorns tarball) är INTE en sajt och får ALDRIG
 * raderas — det skyddas med en explicit grind (``assertSafeSiteId`` +
 * mål-kontroll i ``deleteSite``).
 *
 * Token-upplösning (samma mönster som blob-admin/upload-build-context):
 * process.env vinner; annars repo-rotens .env; sist apps/viewser/.env.vercel.local.
 */

import { del, list } from "@vercel/blob";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Topp-prefix som är sajt-scopade som ``<prefix>/<siteId>/...``. */
export const SITE_PREFIXES = [
  "generated/",
  "run-artifacts/",
  "run-state/",
  "preview-bundles/",
];

/** Python-motorns tarball-prefix. Aldrig sajt-scopad, aldrig raderbar. */
export const BUILD_CONTEXT_PREFIX = "build-context/";

export const SITE_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;

/** Default-retention i dagar när ``RETENTION_DAYS`` inte är satt. */
export const DEFAULT_RETENTION_DAYS = 14;

const BLOB_DELETE_CHUNK = 100;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * @typedef {Object} BlobObject
 * @property {string} pathname
 * @property {string} url
 * @property {number} [size]
 * @property {string|Date} [uploadedAt]
 */

/**
 * @typedef {Object} SiteSummary
 * @property {string} siteId
 * @property {number} totalObjects
 * @property {number} totalBytes
 * @property {Record<string, {objects:number, bytes:number}>} prefixes
 * @property {number} newestUploadedAt  Epoch-ms för sajtens senaste blob-objekt (0 = okänt).
 */

/**
 * @typedef {Object} PrunePlanEntry
 * @property {string} siteId
 * @property {number} totalObjects
 * @property {number} totalBytes
 * @property {number} freshnessMs
 * @property {number} ageDays
 */

/**
 * @typedef {Object} DeleteSiteResult
 * @property {string} siteId
 * @property {number} deletedBlobs
 * @property {number} deletedBytes
 * @property {number} kvKeysDeleted
 * @property {string[]} kvKeys
 * @property {string} [kvError]
 */

// ---------------------------------------------------------------------------
// Env-upplösning (porterad från blob-admin.mjs, oförändrad semantik)
// ---------------------------------------------------------------------------

function repoRoot() {
  const scriptDir = path.dirname(fileURLToPath(import.meta.url));
  // lib/ -> apps/viewser -> apps -> <repo-rot>
  return path.resolve(scriptDir, "..", "..", "..");
}

function readEnvFileVar(envPath, name) {
  if (!existsSync(envPath)) return undefined;
  let text;
  try {
    text = readFileSync(envPath, "utf8");
  } catch {
    return undefined;
  }
  for (const rawLine of text.split(/\r?\n/)) {
    let line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice(7).trimStart();
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    if (line.slice(0, eq).trim() !== name) continue;
    let value = line.slice(eq + 1).trim();
    const quoted = value.match(/^(['"])((?:[^\\]|\\.)*?)\1\s*(?:#.*)?$/);
    if (quoted) return quoted[2];
    const comment = value.match(/\s+#.*$/);
    if (comment) value = value.slice(0, comment.index).trimEnd();
    return value;
  }
  return undefined;
}

/**
 * Lös upp en env-variabel: process.env vinner, annars repo-rotens .env, sist
 * apps/viewser/.env.vercel.local. Hostat finns allt i process.env.
 * @param {string} name
 * @returns {string|undefined}
 */
export function resolveEnvVar(name) {
  const fromProcess = process.env[name]?.trim();
  if (fromProcess) return fromProcess;
  const root = repoRoot();
  const fromRootEnv = readEnvFileVar(path.join(root, ".env"), name)?.trim();
  if (fromRootEnv) return fromRootEnv;
  return readEnvFileVar(
    path.join(root, "apps", "viewser", ".env.vercel.local"),
    name,
  )?.trim();
}

function resolveKvRestUrl() {
  return (
    resolveEnvVar("VIEWSER_KV_REST_URL") ||
    resolveEnvVar("KV_REST_API_URL") ||
    resolveEnvVar("UPSTASH_REDIS_REST_URL")
  );
}

function resolveKvRestToken() {
  return (
    resolveEnvVar("VIEWSER_KV_REST_TOKEN") ||
    resolveEnvVar("KV_REST_API_TOKEN") ||
    resolveEnvVar("UPSTASH_REDIS_REST_TOKEN")
  );
}

// ---------------------------------------------------------------------------
// KV (Upstash REST)
// ---------------------------------------------------------------------------

async function kvCommand(command) {
  const url = resolveKvRestUrl();
  const token = resolveKvRestToken();
  if (!url || !token) {
    throw new Error("KV-env saknas (KV_REST_API_URL/KV_REST_API_TOKEN).");
  }
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
  });
  if (!res.ok) throw new Error(`KV HTTP ${res.status}`);
  const payload = await res.json();
  if (payload && payload.error) throw new Error(`KV-fel: ${payload.error}`);
  return payload ? payload.result : null;
}

async function kvScan(match) {
  let cursor = "0";
  const keys = [];
  do {
    const res = await kvCommand(["SCAN", cursor, "MATCH", match, "COUNT", "200"]);
    cursor = String(res[0]);
    for (const key of res[1]) keys.push(key);
  } while (cursor !== "0");
  return keys;
}

// ---------------------------------------------------------------------------
// Blob-listning + klassificering
// ---------------------------------------------------------------------------

/**
 * Lista ALLA blob-objekt (paginerat).
 * @param {string} token
 * @returns {Promise<BlobObject[]>}
 */
export async function listAllBlobs(token) {
  const blobs = [];
  let cursor;
  do {
    const res = await list({ token, limit: 1000, cursor });
    blobs.push(...res.blobs);
    cursor = res.cursor;
  } while (cursor);
  return blobs;
}

/**
 * Klassificera ett blob-objekt till ``{prefix, siteId}``. build-context/ och
 * andra icke-sajt-prefix ger ``siteId = null``.
 * @param {string} pathname
 * @returns {{prefix:string, siteId:string|null}}
 */
export function classify(pathname) {
  const parts = pathname.split("/");
  const prefix = `${parts[0]}/`;
  if (SITE_PREFIXES.includes(prefix) && parts[1]) {
    return { prefix, siteId: parts[1] };
  }
  return { prefix, siteId: null };
}

function chunk(items, size) {
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

function uploadedAtMs(blob) {
  if (!blob || blob.uploadedAt == null) return 0;
  const ms = new Date(blob.uploadedAt).getTime();
  return Number.isFinite(ms) ? ms : 0;
}

// ---------------------------------------------------------------------------
// Audit + sajt-gruppering
// ---------------------------------------------------------------------------

/**
 * Översikt över hela storen (totalt + per topp-prefix).
 * @param {string} token
 */
export async function auditBlobs(token) {
  const blobs = await listAllBlobs(token);
  const byPrefix = {};
  let totalBytes = 0;
  for (const b of blobs) {
    const { prefix } = classify(b.pathname);
    const group = (byPrefix[prefix] ||= { objects: 0, bytes: 0 });
    group.objects += 1;
    group.bytes += b.size || 0;
    totalBytes += b.size || 0;
  }
  return { totalObjects: blobs.length, totalBytes, byPrefix };
}

/**
 * Gruppera blob-objekt per sajt (build-context/ ignoreras — siteId === null).
 * @param {BlobObject[]} blobs
 * @returns {SiteSummary[]}
 */
export function groupSites(blobs) {
  /** @type {Record<string, SiteSummary>} */
  const sites = {};
  for (const b of blobs) {
    const { prefix, siteId } = classify(b.pathname);
    if (!siteId) continue;
    const site = (sites[siteId] ||= {
      siteId,
      totalObjects: 0,
      totalBytes: 0,
      prefixes: {},
      newestUploadedAt: 0,
    });
    const p = (site.prefixes[prefix] ||= { objects: 0, bytes: 0 });
    p.objects += 1;
    p.bytes += b.size || 0;
    site.totalObjects += 1;
    site.totalBytes += b.size || 0;
    const ms = uploadedAtMs(b);
    if (ms > site.newestUploadedAt) site.newestUploadedAt = ms;
  }
  return Object.values(sites).sort((a, b) => b.totalBytes - a.totalBytes);
}

/**
 * Lista hostade sajter (samma yttre shape som CLI:ts ``list-sites``).
 * @param {string} token
 */
export async function listSites(token) {
  const sites = groupSites(await listAllBlobs(token));
  return { count: sites.length, sites };
}

// ---------------------------------------------------------------------------
// Skydd: build-context/ får ALDRIG raderas
// ---------------------------------------------------------------------------

/**
 * Hård grind: validera att ``siteId`` är en riktig sajt och ALDRIG pekar på
 * build-context/ (Python-motorn). Kastar vid ogiltigt/skyddat id.
 * @param {string} siteId
 */
export function assertSafeSiteId(siteId) {
  if (!siteId || !SITE_ID_PATTERN.test(siteId)) {
    throw new Error(`Ogiltigt siteId: ${JSON.stringify(siteId)}`);
  }
  // "build-context" är inte en sajt; ett siteId får aldrig peka på den mappen.
  if (
    siteId === "build-context" ||
    `${siteId}/`.startsWith(BUILD_CONTEXT_PREFIX)
  ) {
    throw new Error(
      `Skyddat prefix: build-context/ får aldrig raderas (siteId=${JSON.stringify(siteId)}).`,
    );
  }
}

// ---------------------------------------------------------------------------
// Radering av en sajt (porterad från blob-admin.mjs + build-context-grind)
// ---------------------------------------------------------------------------

/**
 * Radera ALLA blob-objekt för en sajt + dess KV-nycklar. ``options.blobs``
 * låter en redan-hämtad listning återanvändas (prune listar en gång och
 * raderar många).
 * @param {string} token
 * @param {string} siteId
 * @param {{ blobs?: BlobObject[] }} [options]
 * @returns {Promise<DeleteSiteResult>}
 */
export async function deleteSite(token, siteId, options = {}) {
  assertSafeSiteId(siteId);
  const blobs = options.blobs ?? (await listAllBlobs(token));
  const targets = blobs.filter((b) => classify(b.pathname).siteId === siteId);

  // Defense-in-depth: även om classify aldrig ger build-context/ ett siteId,
  // vägra om ett mål av någon anledning skulle ligga under det skyddade prefixet.
  for (const b of targets) {
    if (b.pathname.startsWith(BUILD_CONTEXT_PREFIX)) {
      throw new Error(
        "Skydd utlöst: build-context/ ingick i raderingsmålet — avbryter.",
      );
    }
  }

  const urls = targets.map((b) => b.url);
  const deletedBytes = targets.reduce((sum, b) => sum + (b.size || 0), 0);
  for (const part of chunk(urls, BLOB_DELETE_CHUNK)) {
    await del(part, { token });
  }

  let kvKeys = [];
  let kvError;
  try {
    const siteKeys = await kvScan(`viewser:site:${siteId}:*`);
    const runIds = new Set();
    for (const key of siteKeys) {
      if (!/:run:v\d+$/.test(key) && !key.endsWith(":run-state")) continue;
      const value = await kvCommand(["GET", key]);
      if (typeof value === "string" && value) {
        try {
          const doc = JSON.parse(value);
          if (doc && typeof doc.runId === "string" && doc.runId) {
            runIds.add(doc.runId);
          }
        } catch {
          // doc ej JSON — hoppa runId-indexet för den nyckeln
        }
      }
    }
    const toDelete = [
      ...siteKeys,
      `viewser:sandbox-session:${siteId}`,
      ...[...runIds].map((runId) => `viewser:run:${runId}`),
    ];
    if (toDelete.length > 0) {
      await kvCommand(["DEL", ...toDelete]);
      kvKeys = toDelete;
    }
  } catch (error) {
    kvError = error instanceof Error ? error.message : String(error);
  }

  return {
    siteId,
    deletedBlobs: urls.length,
    deletedBytes,
    kvKeysDeleted: kvKeys.length,
    kvKeys,
    ...(kvError ? { kvError } : {}),
  };
}

// ---------------------------------------------------------------------------
// Retention / staleness
// ---------------------------------------------------------------------------

/**
 * Bästa tillgängliga KV-uppdateringstid per sajt (pekaren
 * ``viewser:site:<siteId>:current``.updatedAt). Best-effort: alla fel ger {}.
 * @param {SiteSummary[]} sites
 * @returns {Promise<Record<string, number>>}
 */
async function collectRunStateUpdatedAt(sites) {
  /** @type {Record<string, number>} */
  const out = {};
  const wanted = new Set(sites.map((s) => s.siteId));
  if (wanted.size === 0) return out;
  let keys;
  try {
    keys = await kvScan("viewser:site:*:current");
  } catch {
    return out;
  }
  for (const key of keys) {
    const parts = key.split(":");
    // viewser:site:<siteId>:current
    const siteId = parts.length >= 4 ? parts[2] : null;
    if (!siteId || !wanted.has(siteId)) continue;
    try {
      const value = await kvCommand(["GET", key]);
      if (typeof value === "string" && value) {
        const doc = JSON.parse(value);
        const ms = doc?.updatedAt ? new Date(doc.updatedAt).getTime() : 0;
        if (Number.isFinite(ms) && ms > 0) out[siteId] = ms;
      }
    } catch {
      // enskild nyckel-fel påverkar inte resten
    }
  }
  return out;
}

/**
 * Ren funktion: bestäm vilka sajter som ska prunas. En sajt prunas när dess
 * FÄRSKHET (max av senaste blob-uploadedAt och run-state-pekarens updatedAt)
 * är äldre än ``retentionDays``. Sajter med okänd ålder (freshness 0) BEHÅLLS.
 * Eftersom färskheten är MAX behålls alltid en sajt vars senaste version är
 * nyare än retention — även om den även har gamla objekt.
 *
 * @param {SiteSummary[]} sites
 * @param {{ now:number, retentionDays:number, runStateUpdatedAt?: Record<string, number> }} options
 * @returns {{ prunedSites: PrunePlanEntry[], keptSites: PrunePlanEntry[], freedBytes:number, cutoffMs:number }}
 */
export function planPrune(sites, options) {
  const { now, retentionDays } = options;
  const runStateUpdatedAt = options.runStateUpdatedAt ?? {};
  const cutoffMs = now - retentionDays * MS_PER_DAY;
  /** @type {PrunePlanEntry[]} */
  const prunedSites = [];
  /** @type {PrunePlanEntry[]} */
  const keptSites = [];
  let freedBytes = 0;
  for (const site of sites) {
    const pointerMs = runStateUpdatedAt[site.siteId] ?? 0;
    const freshnessMs = Math.max(site.newestUploadedAt ?? 0, pointerMs);
    /** @type {PrunePlanEntry} */
    const entry = {
      siteId: site.siteId,
      totalObjects: site.totalObjects,
      totalBytes: site.totalBytes,
      freshnessMs,
      ageDays:
        freshnessMs > 0
          ? Math.round((now - freshnessMs) / MS_PER_DAY)
          : -1,
    };
    // Pruna BARA när vi säkert vet att sajten är äldre än retention.
    if (freshnessMs > 0 && freshnessMs < cutoffMs) {
      prunedSites.push(entry);
      freedBytes += site.totalBytes;
    } else {
      keptSites.push(entry);
    }
  }
  return { prunedSites, keptSites, freedBytes, cutoffMs };
}

/**
 * Auto-pruna gammal sajt-data. Listar blob EN gång, planerar via
 * ``planPrune`` och raderar (om inte ``dryRun``) varje för-gammal sajt med
 * EXAKT samma ``deleteSite``-logik som CLI:t. build-context/ rörs aldrig.
 *
 * @param {{ token:string, retentionDays?:number, now?:number, dryRun?:boolean }} options
 */
export async function pruneBlob(options) {
  const token = options.token;
  if (!token) throw new Error("BLOB_READ_WRITE_TOKEN saknas.");
  const retentionDays = options.retentionDays ?? DEFAULT_RETENTION_DAYS;
  const now = options.now ?? Date.now();
  const dryRun = options.dryRun ?? false;

  const blobs = await listAllBlobs(token);
  const sites = groupSites(blobs);
  const runStateUpdatedAt = await collectRunStateUpdatedAt(sites).catch(
    () => ({}),
  );
  const plan = planPrune(sites, { now, retentionDays, runStateUpdatedAt });

  /** @type {DeleteSiteResult[]} */
  const deleted = [];
  if (!dryRun) {
    // Sekventiellt med flit: en list-rundtur per prune (``blobs`` återanvänds)
    // och vänlig mot blob-/KV-API:t i stället för en parallell radera-storm.
    for (const entry of plan.prunedSites) {
      deleted.push(await deleteSite(token, entry.siteId, { blobs }));
    }
  }

  const deletedBytes = deleted.reduce((sum, d) => sum + (d.deletedBytes || 0), 0);
  return {
    dryRun,
    retentionDays,
    cutoffMs: plan.cutoffMs,
    totalSites: sites.length,
    prunedCount: plan.prunedSites.length,
    keptCount: plan.keptSites.length,
    prunedSites: plan.prunedSites.map((e) => e.siteId),
    keptSites: plan.keptSites.map((e) => e.siteId),
    // Frigjort: i dry-run det PLANERADE, annars faktiskt raderat.
    freedBytes: dryRun ? plan.freedBytes : deletedBytes,
    plan: plan.prunedSites,
    deleted,
  };
}

// ---------------------------------------------------------------------------
// Auth-grind för cron-routen (öppen-relä-lärdomen #156: aldrig oskyddad)
// ---------------------------------------------------------------------------

/**
 * Konstant-tids-jämförelse av två strängar (undviker timing-läckage på
 * secret-jämförelsen).
 * @param {string} a
 * @param {string} b
 */
function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Verifiera ``Authorization: Bearer <secret>`` mot ``CRON_SECRET``. Vercel
 * skickar headern automatiskt på cron-anrop NÄR ``CRON_SECRET`` är satt.
 * Saknad/tom secret ⇒ ALLTID false (deny-by-default — ingen publik
 * delete-relä). ``request`` behöver bara en ``headers.get``-metod.
 *
 * @param {{ headers: { get(name:string): string|null } }} request
 * @param {string|undefined|null} secret
 * @returns {boolean}
 */
export function isAuthorizedBearer(request, secret) {
  const trimmed = typeof secret === "string" ? secret.trim() : "";
  if (!trimmed) return false;
  const header = request?.headers?.get?.("authorization");
  if (!header) return false;
  return timingSafeEqual(header, `Bearer ${trimmed}`);
}

/**
 * Tolka ``RETENTION_DAYS`` (icke-negativt heltal). Ogiltigt/osatt ⇒ default.
 * @param {string|undefined|null} raw
 * @returns {number}
 */
export function resolveRetentionDays(raw) {
  const value = typeof raw === "string" ? raw.trim() : "";
  if (!value) return DEFAULT_RETENTION_DAYS;
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || String(parsed) !== value || parsed < 0) {
    return DEFAULT_RETENTION_DAYS;
  }
  return parsed;
}

/**
 * Är auto-prune påslagen? ``PRUNE_ENABLED`` default PÅ; ``0``/``false``/``off``/
 * ``no`` stänger av den utan redeploy (toggle i Vercel-dashboarden).
 * @param {string|undefined|null} raw
 * @returns {boolean}
 */
export function pruneEnabled(raw) {
  const value = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (!value) return true;
  return !(value === "0" || value === "false" || value === "off" || value === "no");
}
