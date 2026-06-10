/**
 * vercel-sandbox-runner — server-only Vercel Sandbox-runner.
 *
 * Detta är den ÅTERANVÄNDBARA, spike-agnostiska runnern: den tar en redan-
 * genererad sajt (`siteId`/`runId`), skapar en isolerad Vercel Sandbox, kör
 * `npm install` + `next build` + `next start` med publicerad port, och
 * returnerar `{ url, sandboxId, status, ... }`. Den lever i app-lagret
 * (`apps/viewser/lib`) eftersom `@vercel/sandbox`-SDK:n enligt ADR 0030 aldrig
 * får importeras i `packages/preview-runtime/` eller `packages/generation/`.
 *
 * Två konsumenter delar denna runner:
 *   1. `vercel-sandbox-spike.ts` — flag-gated CLI/PoC (kräver
 *      `VIEWSER_SANDBOX_SPIKE=1`).
 *   2. `vercel-sandbox` PreviewRuntime-adaptern via DI i
 *      `preview-runtime-server.ts` — opt-in via `VIEWSER_PREVIEW_MODE=
 *      vercel-sandbox` + närvaron av Vercel-auth (ADR 0033).
 *
 * Runnern själv har INGEN spike-flagga; gatingen ligger hos konsumenterna så
 * produktadaptern aldrig importerar från en `*-spike.ts`-fil.
 *
 * Förhållande till ADR 0030: den genererade sajten kopieras in OFÖRÄNDRAD och
 * körs som vanlig Next.js. Runnern degraderar ärligt (`status: "failed"` med
 * pedagogisk text, mönster `local.ts:missingHandler`) när auth/`@vercel/sandbox`/
 * bygget saknas — den kraschar aldrig.
 *
 * STEP 0 — verifierat mot officiella Vercel-docs (`@vercel/sandbox` v2,
 * https://vercel.com/docs/vercel-sandbox, 2026-06-01):
 *   - Auth: OIDC (`VERCEL_OIDC_TOKEN`) eller access-token-trion
 *     (`VERCEL_TOKEN` + `VERCEL_TEAM_ID` + `VERCEL_PROJECT_ID`).
 *   - Runtime `node24`; publik URL via `ports: [3000]` + `sandbox.domain(3000)`;
 *     TTL via `timeout` (ms); cleanup via `sandbox.stop()` (+ best-effort
 *     `delete()`); reconnect via `Sandbox.get({ name })`; filer via
 *     `writeFiles([{ path, content: Buffer }])` (+ `mkdir -p`).
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { resolveGeneratedDir } from "./generated-dir";
import {
  blobPrefixForSite,
  collectSourceFromBlob,
  type CollectedBlobSource,
} from "./generated-blob-source";
import {
  decodeJwtExpirySeconds,
  ensureFreshVercelOidcToken,
  OIDC_REFRESH_MARGIN_SECONDS,
  readVercelOidcTokenFromFile,
} from "./vercel-oidc-refresh.mjs";

const TTL_ENV = "VIEWSER_SANDBOX_SPIKE_TTL_MS";

/**
 * Kill-switch för pre-built-vägen (B3). Default är AUTO: när den aktiva
 * immutable builden redan har en färdig ``.next/`` på disk laddas den upp och
 * ``next build`` hoppas över i sandboxen (~10 s + dev-deps-install sparas per
 * preview). ``VIEWSER_SANDBOX_UPLOAD_BUILT=0`` återställer dagens fulla väg
 * (full npm install + next build i sandboxen).
 */
const UPLOAD_BUILT_ENV = "VIEWSER_SANDBOX_UPLOAD_BUILT";

const PREVIEW_PORT = 3000;
const SANDBOX_RUNTIME = "node24";

/** TTL-grindar. Hobby-tak är 45 min; Pro/Enterprise klarar 5 h. */
const DEFAULT_TTL_MS = 15 * 60_000;
const MIN_TTL_MS = 5 * 60_000;
const MAX_TTL_MS = 45 * 60_000;

/** Readiness-poll mot publik URL efter ``next start``. */
const READY_POLL_TIMEOUT_MS = 150_000;
const READY_POLL_INTERVAL_MS = 2_500;

/** Skydd så vi aldrig råkar ladda upp ett helt ``node_modules``-träd. */
const MAX_FILES = 4_000;
const MAX_TOTAL_BYTES = 64 * 1024 * 1024;

/**
 * Kataloger som aldrig kopieras in (rebuildas/installeras i sandboxen).
 * Kirurgiskt undantag (B3): i pre-built-läget följer rot-nivåns ``.next/``
 * med upp (det är hela poängen) — men aldrig ``.next/cache`` (webpack-cache,
 * ~95 % av .next-bytes, behövs aldrig av ``next start``) och aldrig
 * ``.next/trace`` (build-telemetri med operatörens absoluta paths).
 */
const SKIP_DIRS = new Set([
  "node_modules",
  ".next",
  ".git",
  ".turbo",
  ".vercel",
  ".cache",
  "out",
]);

/** Build-id-format YYYYMMDDTHHMMSSZ (+ ev. ``-NN``-kollisionssuffix). */
const BUILD_ID_RE = /^\d{8}T\d{6}Z(?:-\d{2,})?$/;

export interface SandboxPreviewRequest {
  /** ``siteId`` under ``.generated/<siteId>/`` (krävs). */
  siteId: string;
  /** Logisk run-referens (valfri, bara för loggning/spårbarhet). */
  runId?: string;
  /** TTL i ms; klampas till [5 min, 45 min]. Default 15 min. */
  ttlMs?: number;
}

export interface SandboxPreviewResult {
  status: "ready" | "failed";
  /** Publik https-URL till previewn (när ``ready``). */
  url?: string;
  /** Hållbar handle för cleanup === ``sandbox.name``. */
  sandboxId?: string;
  /** Pedagogisk text när ``failed``. */
  error?: string;
  /** TTL i ms som sattes på sandboxen. */
  ttlMs?: number;
  /**
   * True när previewn serverades via pre-built-vägen (B3): färdig ``.next/``
   * uppladdad, ``next build`` hoppad i sandboxen.
   */
  prebuilt?: boolean;
  /** Fas-timing för cold-start-analys (ms). */
  timings?: {
    createMs?: number;
    uploadMs?: number;
    installMs?: number;
    buildMs?: number;
    readyMs?: number;
    totalMs?: number;
  };
  /** Kostnadssignal vid create (faktisk CPU/nätverk syns först vid stop). */
  cost?: {
    runtime?: string;
    vcpus?: number;
    memoryMb?: number;
    ttlMs?: number;
    fileCount?: number;
    uploadBytes?: number;
  };
  /** Korta operatör-loggar. */
  logs?: string[];
}

export interface SandboxStopResult {
  status: "stopped" | "failed";
  sandboxId?: string;
  error?: string;
  /** Faktisk kostnadssignal från ``sandbox.stop()``. */
  cost?: {
    activeCpuMs?: number;
    ingressBytes?: number;
    egressBytes?: number;
    snapshotId?: string;
  };
  logs?: string[];
}

/**
 * Vercel-auth-nycklar som ``vercel env pull`` skriver. Next auto-laddar
 * ``.env.local`` men INTE ``.env.vercel.local`` (filen ``vercel env pull``
 * default-skapar för OIDC-token, gitignored, ~12 h TTL lokalt). Den körande
 * viewser-dev-processen behöver därför en explicit broms-broms-laddning av just
 * dessa nycklar för att sandbox-runnern ska hitta auth (Bite C auth-wiring).
 */
const VERCEL_ENV_LOCAL_FILE = ".env.vercel.local";
const VERCEL_AUTH_ENV_KEYS = [
  "VERCEL_OIDC_TOKEN",
  "VERCEL_TOKEN",
  "VERCEL_TEAM_ID",
  "VERCEL_PROJECT_ID",
] as const;

let vercelEnvLocalLoaded = false;

/**
 * Ladda ``apps/viewser/.env.vercel.local`` EN gång och fyll bara de
 * Vercel-auth-nycklar som ännu inte finns i ``process.env`` (process.env och
 * Next-laddad ``.env.local`` vinner alltid — samma precedens som dotenv).
 *
 * cwd-OBEROENDE: filen resolvas relativt denna moduls plats
 * (``apps/viewser/lib/<fil>.ts`` → ``apps/viewser/.env.vercel.local``), inte
 * ``process.cwd()``. Icke-kastande: saknad fil → no-op, och ``resolveCredentials``
 * degraderar då ärligt (``null``). Värden tål omslutande citat (``vercel env
 * pull`` quotar token-strängen).
 */
function ensureVercelEnvLocalLoaded(): void {
  if (vercelEnvLocalLoaded) return;
  vercelEnvLocalLoaded = true;
  const moduleDir = path.dirname(fileURLToPath(import.meta.url));
  const envPath = path.resolve(moduleDir, "..", VERCEL_ENV_LOCAL_FILE);
  let raw: string;
  try {
    raw = readFileSync(envPath, "utf-8");
  } catch {
    return;
  }
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    if (!(VERCEL_AUTH_ENV_KEYS as readonly string[]).includes(key)) continue;
    if (process.env[key] && process.env[key]?.trim()) continue;
    let value = trimmed.slice(eq + 1).trim();
    const quoted = value.match(/^(['"])([\s\S]*)\1$/);
    if (quoted) value = quoted[2];
    if (value) process.env[key] = value;
  }
}

/**
 * Resolverar Vercel-credentials. OIDC vinner om ``VERCEL_OIDC_TOKEN`` finns
 * (SDK:n läser den automatiskt → vi spreadar ingenting). Annars krävs hela
 * access-token-trion. Returnerar ``null`` om ingen auth är tillgänglig.
 *
 * Laddar först ``.env.vercel.local`` (best-effort) så OIDC-token från
 * ``vercel env pull`` hittas även om Next inte auto-laddade den filen.
 */
function resolveCredentials():
  | { mode: "oidc"; create: Record<string, never> }
  | { mode: "token"; create: { token: string; teamId: string; projectId: string } }
  | null {
  ensureVercelEnvLocalLoaded();
  if (process.env.VERCEL_OIDC_TOKEN && process.env.VERCEL_OIDC_TOKEN.trim()) {
    return { mode: "oidc", create: {} };
  }
  const token = process.env.VERCEL_TOKEN?.trim();
  const teamId = process.env.VERCEL_TEAM_ID?.trim();
  const projectId = process.env.VERCEL_PROJECT_ID?.trim();
  if (token && teamId && projectId) {
    return { mode: "token", create: { token, teamId, projectId } };
  }
  return null;
}

/**
 * True om Vercel-auth finns (OIDC eller access-token-trion). Används av
 * adapterns `isAvailable()` så den degraderar ärligt utan att kasta.
 */
export function hasVercelSandboxAuth(): boolean {
  return resolveCredentials() !== null;
}

/**
 * B1a — token-hållbarhet: OIDC-token från ``vercel env pull`` lever ~12 h
 * lokalt. En lång viewser-session överlever den gränsen, och utan denna
 * guard dör previews mitt i med ett kryptiskt SDK-fel. Anropas FÖRE
 * ``Sandbox.create`` när OIDC-vägen används:
 *
 *   - > 1 h kvar på JWT-exp → no-op (ingen pull-kostnad i normalfallet).
 *   - < 1 h kvar / oläsbar exp → kör den DELADE refreshen
 *     (``vercel-oidc-refresh.mjs``, samma logik som scripts/dev.mjs predev)
 *     och adoptera en fräschare token från ``.env.vercel.local`` in i
 *     ``process.env`` (det är därifrån SDK:n läser ``VERCEL_OIDC_TOKEN``;
 *     ``ensureVercelEnvLocalLoaded`` fyller bara TOMMA nycklar en gång per
 *     process och hjälper inte här).
 *   - Refresh misslyckades men token lever fortfarande → fortsätt ärligt
 *     med varningslogg (previewn hinner förmodligen klart).
 *   - Refresh misslyckades och token är död/saknas → ärligt fel med
 *     expiresIn + hur-fixar-info (klassas som ``vercel_auth`` av preview-
 *     routen — meddelandet innehåller "VERCEL_OIDC_TOKEN").
 */
function ensureFreshOidcTokenBeforeCreate(
  logs: string[],
): { ok: true } | { ok: false; error: string } {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const currentExp = decodeJwtExpirySeconds(process.env.VERCEL_OIDC_TOKEN);
  if (currentExp !== null && currentExp - nowSeconds > OIDC_REFRESH_MARGIN_SECONDS) {
    return { ok: true };
  }
  ensureFreshVercelOidcToken({
    log: (message: string) => logs.push(`OIDC-refresh: ${message}`),
    warn: (message: string) => logs.push(`OIDC-refresh: ${message}`),
  });
  const fileToken = readVercelOidcTokenFromFile();
  if (fileToken) {
    const fileExp = decodeJwtExpirySeconds(fileToken);
    if (fileExp !== null && (currentExp === null || fileExp > currentExp)) {
      process.env.VERCEL_OIDC_TOKEN = fileToken;
    }
  }
  const effectiveExp = decodeJwtExpirySeconds(process.env.VERCEL_OIDC_TOKEN);
  if (effectiveExp !== null && effectiveExp > nowSeconds) {
    const minutesLeft = Math.round((effectiveExp - nowSeconds) / 60);
    if (effectiveExp - nowSeconds <= OIDC_REFRESH_MARGIN_SECONDS) {
      logs.push(
        "Varning: OIDC-refresh misslyckades — fortsätter på nuvarande token " +
          `(~${minutesLeft} min kvar).`,
      );
    } else {
      logs.push(`OIDC-token färsk (~${minutesLeft} min kvar).`);
    }
    return { ok: true };
  }
  const expiresIn =
    effectiveExp === null
      ? "okänd (token saknas eller har oläsbar exp)"
      : `${effectiveExp - nowSeconds} s (utgången)`;
  return {
    ok: false,
    error:
      "VERCEL_OIDC_TOKEN är utgången och kunde inte uppdateras automatiskt " +
      `(expiresIn: ${expiresIn}). Kör \`vercel env pull ` +
      "apps/viewser/.env.vercel.local` (kräver `vercel link` + inloggad " +
      "vercel-CLI) och försök igen — en färsk token gäller ~12 h.",
  };
}

// Var ``build_site.py`` skrivit den genererade sajten resolveras av den
// DELADE ``resolveGeneratedDir`` i ``./generated-dir`` (en enda resolver för
// både local-preview-servern och denna runner, med samma regler som Pythons
// ``resolve_generated_dir``: cwd-oberoende repo-rot, repo-root-relativ
// resolution av relativa värden, repo-rotens ``.env`` som single source).

/**
 * Läs ``<siteRoot>/current.json`` och returnera den aktiva immutable
 * build-katalogen (B157 nivå 4). Speglar
 * ``local-preview-server.ts:readActiveBuildDir`` på TS-sidan; validerar
 * build-id mot path-traversal.
 */
function readActiveBuildDir(siteRoot: string): string | null {
  const pointerPath = path.join(siteRoot, "current.json");
  let raw: string;
  try {
    raw = readFileSync(pointerPath, "utf-8");
  } catch {
    return null;
  }
  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof payload !== "object" || payload === null) return null;
  const activeBuildId = (payload as { activeBuildId?: unknown }).activeBuildId;
  if (typeof activeBuildId !== "string" || !BUILD_ID_RE.test(activeBuildId)) {
    return null;
  }
  const buildPath = (payload as { buildPath?: unknown }).buildPath;
  if (
    buildPath !== undefined &&
    buildPath !== null &&
    buildPath !== `builds/${activeBuildId}`
  ) {
    return null;
  }
  const buildDir = path.join(siteRoot, "builds", activeBuildId);
  return existsSync(buildDir) ? buildDir : null;
}

/**
 * Validerar ``siteId`` med samma regel som ``/api/preview/[siteId]``
 * (a-z, 0-9, bindestreck, max 64 tecken, ingen slash/punkt). Returnerar
 * ett pedagogiskt felmeddelande eller ``null`` om värdet är giltigt.
 */
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

function validateSiteId(siteId: string): string | null {
  if (!siteId || !siteId.trim()) return "siteId saknas.";
  if (siteId.length > 64) return "siteId är för långt (max 64 tecken).";
  if (!SITE_ID_PATTERN.test(siteId)) {
    return "siteId får bara innehålla a-z, 0-9 och bindestreck.";
  }
  return null;
}

/**
 * Resolverar käll-katalogen för en genererad sajt: föredra den aktiva
 * immutable build:en (``current.json``), annars det gamla flata layoutet
 * ``<siteRoot>/``. Returnerar ``null`` om sajten inte finns på disk.
 *
 * ``siteId`` valideras av callern (``validateSiteId``); här ligger dessutom
 * en resolve-/containment-check så ``siteRoot`` aldrig kan hamna utanför
 * generated-roten även om regex:en någon gång skulle luckras upp.
 */
function resolveSourceDir(siteId: string): string | null {
  const generatedRoot = resolveGeneratedDir();
  const siteRoot = path.resolve(generatedRoot, siteId);
  const rel = path.relative(generatedRoot, siteRoot);
  if (rel === "" || rel.startsWith("..") || path.isAbsolute(rel)) {
    return null;
  }
  if (!existsSync(siteRoot)) return null;
  const activeBuildDir = readActiveBuildDir(siteRoot);
  if (activeBuildDir && existsSync(path.join(activeBuildDir, "package.json"))) {
    return activeBuildDir;
  }
  if (existsSync(path.join(siteRoot, "package.json"))) {
    return siteRoot;
  }
  return null;
}

/**
 * Lista de siteId:n under generated-roten som ser byggbara ut (giltigt
 * siteId-format + en upplösbar käll-katalog). CLI-bekvämlighet så operatören
 * slipper leta mappen manuellt. Icke-kastande: tom lista om roten saknas.
 */
export function listGeneratedSiteIds(): string[] {
  const generatedRoot = resolveGeneratedDir();
  const out: string[] = [];
  try {
    for (const entry of readdirSync(generatedRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      if (validateSiteId(entry.name)) continue;
      if (resolveSourceDir(entry.name)) out.push(entry.name);
    }
  } catch {
    return [];
  }
  return out.sort();
}

interface CollectedSource {
  files: { relPath: string; content: Buffer }[];
  dirs: string[];
  totalBytes: number;
}

/**
 * True om pre-built-upload (B3) är aktiverad. Default AUTO (på); kill-switch
 * ``VIEWSER_SANDBOX_UPLOAD_BUILT=0`` återställer dagens fulla väg.
 */
function prebuiltUploadEnabled(): boolean {
  return process.env[UPLOAD_BUILT_ENV] !== "0";
}

/**
 * True om käll-katalogen har en FÄRDIG ``next build``-output. ``BUILD_ID``
 * skrivs sist i en lyckad build, så dess närvaro är readiness-signalen
 * (samma kontrakt som ``local-preview-server.ts`` förlitar sig på).
 * Immutable-build-kontraktet respekteras: vi LÄSER bara — build-katalogen
 * på disk muteras aldrig.
 */
function hasCompletedNextBuild(sourceDir: string): boolean {
  return existsSync(path.join(sourceDir, ".next", "BUILD_ID"));
}

/**
 * Samla in alla käll-filer under ``rootDir`` (utom ``SKIP_DIRS``,
 * ``.env*``-filer och symlinks) som ``writeFiles``-deskriptorer med
 * POSIX-relativa paths. Kastar om projektet är orimligt stort (oftast ett
 * tecken på att ``node_modules`` inte exkluderades) så vi aldrig laddar upp
 * gigabyte. ``.env*`` blockeras (utom ``.env.example``) så inga secrets
 * läcker till den publika sandboxen.
 *
 * ``includeBuiltNext`` (B3): tar med rot-nivåns färdiga ``.next/`` så
 * sandboxen kan köra ``next start`` direkt utan ``next build``. Kirurgiska
 * undantag inom ``.next``: ``cache/`` (webpack-disk-cache, 60+ MB, aldrig
 * läst av ``next start``) och ``trace`` (build-telemetri med operatörens
 * absoluta paths) hoppas alltid över.
 *
 * Windows→Linux-portabilitet (verifierad mot faktisk genererad ``.next``):
 * runtime-manifesten (``pages-manifest``, ``app-paths-manifest``,
 * ``routes-manifest`` m.fl.) använder POSIX-relativa paths även när bygget
 * skedde på Windows. De absoluta Windows-paths som FINNS i
 * ``server/chunks/*`` och ``*client-reference-manifest*`` är opaka modul-ID-
 * strängar som bara matchas mot varandra (RSC-proxy ↔ manifest, byggda
 * ihop) — de resolvas aldrig mot filsystemet av ``next start``.
 * ``required-server-files.json`` läses bara av standalone-läget (används ej
 * här). Om något ändå skiljer: den ärliga fallbacken i
 * ``createSandboxPreview`` tar fulla vägen.
 */
function collectSource(rootDir: string, includeBuiltNext = false): CollectedSource {
  const files: { relPath: string; content: Buffer }[] = [];
  const dirSet = new Set<string>();
  let totalBytes = 0;

  const walk = (absDir: string, relDir: string): void => {
    for (const entry of readdirSync(absDir, { withFileTypes: true })) {
      const relPath = relDir ? `${relDir}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        if (SKIP_DIRS.has(entry.name)) {
          // Kirurgiskt B3-undantag: BARA rot-nivåns ``.next`` släpps igenom,
          // och bara i pre-built-läget. Nästlade ``.next``/övriga SKIP_DIRS
          // skippas precis som förr.
          if (!(includeBuiltNext && relPath === ".next")) continue;
        }
        if (includeBuiltNext && relPath === ".next/cache") continue;
        walk(path.join(absDir, entry.name), relPath);
        continue;
      }
      // Symlinks hoppas över: ``Dirent.isFile()`` är ``false`` för en
      // symlink (typen speglar katalog-entryn, inte målet).
      if (!entry.isFile()) continue;
      if (includeBuiltNext && relPath === ".next/trace") continue;
      // Säkerhet (samma B54/B58-mönster som stackblitz-files.ts): ladda
      // ALDRIG upp ``.env*`` till den publika sandboxen — bara
      // ``.env.example`` (ofarlig placeholder) är tillåten. Case-insensitivt
      // så ``.ENV``/``.Env.Local`` också fångas.
      const lowerName = entry.name.toLowerCase();
      if (lowerName.startsWith(".env") && lowerName !== ".env.example") {
        continue;
      }
      const absPath = path.join(absDir, entry.name);
      const size = statSync(absPath).size;
      totalBytes += size;
      if (files.length >= MAX_FILES || totalBytes > MAX_TOTAL_BYTES) {
        throw new Error(
          `Käll-trädet är orimligt stort (>${MAX_FILES} filer eller ` +
            `>${Math.round(MAX_TOTAL_BYTES / 1024 / 1024)} MB). Kontrollera ` +
            "att node_modules/.next exkluderades innan upload.",
        );
      }
      const dir = path.posix.dirname(relPath);
      if (dir && dir !== ".") dirSet.add(dir);
      files.push({ relPath, content: readFileSync(absPath) });
    }
  };

  walk(rootDir, "");
  return { files, dirs: Array.from(dirSet).sort(), totalBytes };
}

/** Dynamisk import så en saknad ``@vercel/sandbox`` degraderar ärligt. */
async function loadSandboxSdk(): Promise<
  typeof import("@vercel/sandbox") | null
> {
  try {
    return await import("@vercel/sandbox");
  } catch {
    return null;
  }
}

function clampTtl(requested: number | undefined): number {
  const fromEnv = Number(process.env[TTL_ENV]);
  const base =
    typeof requested === "number" && Number.isFinite(requested)
      ? requested
      : Number.isFinite(fromEnv) && fromEnv > 0
        ? fromEnv
        : DEFAULT_TTL_MS;
  return Math.min(MAX_TTL_MS, Math.max(MIN_TTL_MS, Math.round(base)));
}

function failed(error: string, logs: string[] = []): SandboxPreviewResult {
  return { status: "failed", error, logs };
}

/** Poll publik URL tills Next.js svarar eller timeout. Mäter cold-start. */
async function waitForPublicUrl(url: string): Promise<boolean> {
  const deadline = Date.now() + READY_POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, {
        method: "GET",
        signal: AbortSignal.timeout(5_000),
        redirect: "manual",
      });
      if (res.status > 0) return true;
    } catch {
      // Ännu inte uppe — vänta och försök igen.
    }
    await new Promise((r) => setTimeout(r, READY_POLL_INTERVAL_MS));
  }
  return false;
}

/**
 * Skapa + servera en isolerad preview av en redan-genererad sajt i en Vercel
 * Sandbox. Stoppar INTE sandboxen vid lyckad start — URL:en lever tills TTL
 * löper ut eller ``stopSandboxPreview`` anropas. Vid fel städas en redan
 * skapad sandbox upp så vi inte läcker kostnad.
 *
 * Pre-built-vägen (B3): när disk-källan har en färdig ``.next/`` laddas den
 * upp och sandboxen kör bara ``npm install --omit=dev`` + ``next start``
 * (ingen ``next build``). Failar pre-built-vägen i sandboxen loggas det
 * ärligt och fulla vägen körs om EN gång — ingen loop.
 *
 * Spike-agnostisk: konsumenter (CLI vs adapter) ansvarar för sin egen gating.
 */
export async function createSandboxPreview(
  request: SandboxPreviewRequest,
): Promise<SandboxPreviewResult> {
  const first = await createSandboxPreviewAttempt(request, true);
  if (first.fallbackEligible && first.result.status === "failed") {
    const honestLog =
      "Pre-built .next misslyckades i sandboxen — faller ärligt tillbaka " +
      "till fulla vägen (npm install + next build) EN gång, ingen loop.";
    const second = await createSandboxPreviewAttempt(request, false);
    return {
      ...second.result,
      logs: [...(first.result.logs ?? []), honestLog, ...(second.result.logs ?? [])],
    };
  }
  return first.result;
}

/**
 * Intern attempt-körning. ``fallbackEligible`` är true bara när pre-built-
 * vägen faktiskt valdes OCH felet uppstod i en pre-built-beroende fas
 * (collect/sandbox-exekvering) — auth-/valideringsfel skulle faila identiskt
 * på fulla vägen och får aldrig trigga en andra (kostsam) sandbox-körning.
 */
async function createSandboxPreviewAttempt(
  request: SandboxPreviewRequest,
  allowPrebuilt: boolean,
): Promise<{ result: SandboxPreviewResult; fallbackEligible: boolean }> {
  const logs: string[] = [];

  const siteIdError = validateSiteId(request.siteId ?? "");
  if (siteIdError) {
    return { result: failed(`Ogiltigt siteId: ${siteIdError}`), fallbackEligible: false };
  }

  const credentials = resolveCredentials();
  if (!credentials) {
    return {
      result: failed(
        "Vercel-credentials saknas. Sätt antingen VERCEL_OIDC_TOKEN (via " +
          "`vercel link` + `vercel env pull`) eller trion VERCEL_TOKEN + " +
          "VERCEL_TEAM_ID + VERCEL_PROJECT_ID. Runnern degraderar hellre ärligt " +
          "än kraschar.",
      ),
      fallbackEligible: false,
    };
  }
  logs.push(`Auth-läge: ${credentials.mode}.`);

  // Käll-filer: disk lokalt, blob hostat (FAS 2B, migrationsplanens G2). Disk-
  // vägen är byte-identisk med tidigare (pre-built-läget undantaget, B3).
  // Blob-vägen aktiveras bara när ingen byggd sajt finns på disk — det normala
  // fallet hostat på Vercel där det inte finns någon beständig repo-disk. En
  // redan byggd sajt görs förhandsvisbar hostat genom att snapshotta dess
  // generated-files till blob lokalt via scripts/snapshot-site-to-blob.mjs
  // (icke-publik operatör-CLI, #156).
  const sourceDir = resolveSourceDir(request.siteId);
  // Pre-built-vägen (B3) är disk-only: blob-snapshots innehåller ingen .next.
  const prebuilt =
    allowPrebuilt &&
    prebuiltUploadEnabled() &&
    sourceDir !== null &&
    hasCompletedNextBuild(sourceDir);
  let collected: CollectedSource;
  if (sourceDir) {
    logs.push(`Käll-katalog: ${sourceDir}.`);
    if (prebuilt) {
      logs.push(
        "Pre-built .next hittad (BUILD_ID) — laddar upp byggartefakter och " +
          `hoppar över next build i sandboxen (${UPLOAD_BUILT_ENV}=0 stänger av).`,
      );
    }
    try {
      collected = collectSource(sourceDir, prebuilt);
    } catch (error) {
      // Collect-fel i pre-built-läget (t.ex. fil-/byte-taket nås på grund av
      // .next-innehållet) kan lyckas på fulla vägen → fallback-berättigat.
      return { result: failed(messageFromError(error), logs), fallbackEligible: prebuilt };
    }
  } else {
    let fromBlob: CollectedBlobSource | null;
    try {
      fromBlob = await collectSourceFromBlob(request.siteId);
    } catch (error) {
      return { result: failed(messageFromError(error), logs), fallbackEligible: false };
    }
    if (!fromBlob) {
      return {
        result: failed(
          `Hittade ingen byggd sajt för siteId="${request.siteId}" — varken på ` +
            `disk (${resolveGeneratedDir()}) eller som blob-snapshot ` +
            `(${blobPrefixForSite(request.siteId)}). Kör build_site.py lokalt, ` +
            "eller snapshotta sajten till blob med scripts/snapshot-site-to-blob.mjs.",
          logs,
        ),
        fallbackEligible: false,
      };
    }
    collected = fromBlob;
    logs.push(
      `Käll: blob-snapshot ${blobPrefixForSite(request.siteId)} ` +
        `(${collected.files.length} filer).`,
    );
  }

  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return {
      result: failed(
        "@vercel/sandbox är inte installerad i apps/viewser. Kör " +
          "`cd apps/viewser && npm install` (paketet ligger i package.json). " +
          "Runnern degraderar ärligt istället för att krascha.",
        logs,
      ),
      fallbackEligible: false,
    };
  }
  const { Sandbox } = sdk;

  logs.push(
    `Samlade ${collected.files.length} filer ` +
      `(${Math.round(collected.totalBytes / 1024)} kB) för upload.`,
  );

  const ttlMs = clampTtl(request.ttlMs);
  const sandboxName = `sajtbyggaren-preview-${slug(request.siteId)}-${Date.now()}`;

  // B1a: håll OIDC-token färsk FÖRE Sandbox.create (refresh vid < 1 h kvar).
  // Auth-fel är aldrig fallback-berättigade — fulla vägen failar identiskt.
  if (credentials.mode === "oidc") {
    const oidcGuard = ensureFreshOidcTokenBeforeCreate(logs);
    if (!oidcGuard.ok) {
      return { result: failed(oidcGuard.error, logs), fallbackEligible: false };
    }
  }

  const t0 = Date.now();
  let createMs: number | undefined;
  let uploadMs: number | undefined;
  let installMs: number | undefined;
  let buildMs: number | undefined;
  let readyMs: number | undefined;

  // Vi håller en referens utanför try så catch kan städa upp.
  let sandbox: Awaited<ReturnType<typeof Sandbox.create>> | null = null;

  try {
    sandbox = await Sandbox.create({
      ...credentials.create,
      name: sandboxName,
      runtime: SANDBOX_RUNTIME,
      ports: [PREVIEW_PORT],
      timeout: ttlMs,
      // Ephemeral preview: ingen auto-snapshot på stop (sparar snapshot-storage).
      persistent: false,
    });
    createMs = Date.now() - t0;
    logs.push(`Sandbox skapad (${sandbox.name}) på ${createMs} ms.`);

    // Skapa kataloger innan writeFiles (writeFiles auto-skapar inte dirs).
    const tUpload = Date.now();
    if (collected.dirs.length > 0) {
      await sandbox.runCommand({
        cmd: "mkdir",
        args: ["-p", ...collected.dirs],
      });
    }
    await sandbox.writeFiles(
      collected.files.map((f) => ({ path: f.relPath, content: f.content })),
    );
    uploadMs = Date.now() - tUpload;
    logs.push(`Filer uppladdade på ${uploadMs} ms.`);

    // ``next start`` behöver node_modules (next/react/react-dom + runtime-
    // deps — ett node_modules-träd går inte att ladda upp, det spränger
    // fil-taket många gånger om). I pre-built-läget räcker prod-deps:
    // ``--omit=dev`` hoppar över typescript/tailwind/eslint m.fl. som bara
    // behövs av ``next build`` (next.config.ts transpileras av Nexts egna
    // bundlade tooling vid start, kräver inte typescript-paketet).
    const tInstall = Date.now();
    const installArgs = prebuilt
      ? ["install", "--omit=dev", "--no-audit", "--no-fund", "--loglevel", "warn"]
      : ["install", "--no-audit", "--no-fund", "--loglevel", "warn"];
    const install = await sandbox.runCommand({
      cmd: "npm",
      args: installArgs,
      stdout: process.stdout,
      stderr: process.stderr,
    });
    installMs = Date.now() - tInstall;
    if (install.exitCode !== 0) {
      await safeStop(sandbox);
      return {
        result: failed(
          `npm install misslyckades (exit ${install.exitCode}) i sandboxen.`,
          logs,
        ),
        fallbackEligible: prebuilt,
      };
    }
    logs.push(`npm install${prebuilt ? " --omit=dev" : ""} klar på ${installMs} ms.`);

    if (!prebuilt) {
      const tBuild = Date.now();
      const build = await sandbox.runCommand({
        cmd: "npx",
        args: ["next", "build"],
        stdout: process.stdout,
        stderr: process.stderr,
      });
      buildMs = Date.now() - tBuild;
      if (build.exitCode !== 0) {
        await safeStop(sandbox);
        return {
          result: failed(
            `next build misslyckades (exit ${build.exitCode}) i sandboxen.`,
            logs,
          ),
          fallbackEligible: false,
        };
      }
      logs.push(`next build klar på ${buildMs} ms.`);
    } else {
      logs.push("Hoppar över next build — pre-built .next används (B3).");
    }

    // Detached: ``next start`` håller porten öppen tills TTL löper ut.
    await sandbox.runCommand({
      cmd: "npx",
      args: ["next", "start", "-p", String(PREVIEW_PORT)],
      detached: true,
    });

    const url = sandbox.domain(PREVIEW_PORT);
    const tReady = Date.now();
    const isUp = await waitForPublicUrl(url);
    readyMs = Date.now() - tReady;
    if (!isUp) {
      await safeStop(sandbox);
      // Pre-built-läget: en .next som av någon anledning inte är portabel
      // (t.ex. framtida Next-version som bakar in resolvade paths) yttrar
      // sig exakt här — ``next start`` svarar aldrig. Ärlig fallback.
      return {
        result: failed(
          `next start svarade inte på ${url} inom ` +
            `${Math.round(READY_POLL_TIMEOUT_MS / 1000)} s. Sandbox stoppad.` +
            (prebuilt ? " (pre-built-läge — fulla vägen provas en gång)" : ""),
          logs,
        ),
        fallbackEligible: prebuilt,
      };
    }

    const totalMs = Date.now() - t0;
    logs.push(
      `Preview live på ${url} (cold-start totalt ${totalMs} ms` +
        `${prebuilt ? ", pre-built .next" : ""}).`,
    );

    return {
      result: {
        status: "ready",
        url,
        sandboxId: sandbox.name,
        ttlMs,
        prebuilt,
        timings: { createMs, uploadMs, installMs, buildMs, readyMs, totalMs },
        cost: {
          runtime: SANDBOX_RUNTIME,
          vcpus: sandbox.vcpus,
          memoryMb: sandbox.memory,
          ttlMs,
          fileCount: collected.files.length,
          uploadBytes: collected.totalBytes,
        },
        logs,
      },
      fallbackEligible: false,
    };
  } catch (error) {
    // Kast FÖRE en lyckad Sandbox.create (sandbox === null, t.ex. auth/nät)
    // är inte pre-built-specifika och skulle faila identiskt på fulla vägen
    // — ingen fallback då. Kast efter create (upload/kommandon) kan vara det.
    const fallbackEligible = prebuilt && sandbox !== null;
    if (sandbox) await safeStop(sandbox);
    return { result: failed(messageFromError(error), logs), fallbackEligible };
  }
}

/**
 * Stoppa en preview separat (manuell verifiering, TTL-städning eller explicit
 * anrop). Idempotent och icke-kastande. ``sandboxId`` är ``sandbox.name`` från
 * ``createSandboxPreview``.
 */
export async function stopSandboxPreview(
  sandboxId: string,
): Promise<SandboxStopResult> {
  const logs: string[] = [];

  if (!sandboxId || !sandboxId.trim()) {
    return { status: "failed", error: "stopSandboxPreview kräver ett sandboxId." };
  }

  const credentials = resolveCredentials();
  if (!credentials) {
    return {
      status: "failed",
      error:
        "Vercel-credentials saknas (VERCEL_OIDC_TOKEN eller VERCEL_TOKEN + " +
        "VERCEL_TEAM_ID + VERCEL_PROJECT_ID).",
    };
  }

  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return {
      status: "failed",
      error: "@vercel/sandbox är inte installerad i apps/viewser.",
    };
  }

  try {
    const sandbox = await sdk.Sandbox.get({
      ...credentials.create,
      name: sandboxId,
    });
    await sandbox.stop();
    logs.push(`Sandbox ${sandboxId} stoppad.`);
    // Läs kostnadssignalen DEFENSIVT från instans-accessorerna (populeras
    // efter stop). Vi rör INTE ``stop()``-returvärdet: docs/SDK-versioner
    // skiljer sig (vissa anger ``Promise<void>``), så vi förlitar oss bara
    // på de stabila accessorerna. Läs dem INNAN ev. delete() — efter delete
    // blir instansen inert.
    const cost = {
      activeCpuMs: sandbox.activeCpuUsageMs,
      ingressBytes: sandbox.networkTransfer?.ingress,
      egressBytes: sandbox.networkTransfer?.egress,
      snapshotId: sandbox.currentSnapshotId,
    };
    // Best-effort: ta även bort själva sandbox-recordet så inget ligger kvar.
    // ``stop()`` är huvud-cleanup (räcker med ``persistent:false`` + TTL);
    // ``delete()`` får ALDRIG blockera eller kasta — vid fel/avsaknad
    // rapporterar vi ändå stop-resultatet.
    try {
      await sandbox.delete();
      logs.push(`Sandbox ${sandboxId} raderad (record borttaget).`);
    } catch {
      logs.push(
        `Sandbox ${sandboxId} stoppad; delete() misslyckades — ` +
          "stop()+persistent:false+TTL är ändå tillräcklig cleanup.",
      );
    }
    return { status: "stopped", sandboxId, cost, logs };
  } catch (error) {
    return {
      status: "failed",
      sandboxId,
      error: messageFromError(error),
      logs,
    };
  }
}

async function safeStop(
  sandbox: { stop: () => Promise<unknown> },
): Promise<void> {
  try {
    await sandbox.stop();
  } catch {
    // Best-effort cleanup — svälj så vi aldrig maskerar det ursprungliga felet.
  }
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "site";
}

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Okänt fel i Vercel Sandbox-runnern.";
}
