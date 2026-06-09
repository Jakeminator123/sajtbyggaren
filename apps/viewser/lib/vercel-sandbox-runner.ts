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

const TTL_ENV = "VIEWSER_SANDBOX_SPIKE_TTL_MS";

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

/** Kataloger som aldrig kopieras in (rebuildas/installeras i sandboxen). */
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
 * Resolverar var ``build_site.py`` skrivit den genererade sajten. Speglar
 * ``apps/viewser/lib/local-preview-server.ts:resolveGeneratedDir`` men
 * re-implementeras här så runnern är fristående.
 */
function resolveGeneratedDir(): string {
  // cwd-OBEROENDE: härled repo-roten från denna fils plats, inte
  // process.cwd(). Filen ligger på ``<repo>/apps/viewser/lib/<fil>.ts`` →
  // tre nivåer upp från ``lib/`` är repo-roten.
  const moduleDir = path.dirname(fileURLToPath(import.meta.url));
  const repoRoot = path.resolve(moduleDir, "..", "..", "..");
  const envOverride = process.env.SAJTBYGGAREN_GENERATED_DIR;
  if (envOverride && envOverride.trim()) {
    const raw = envOverride.trim();
    // En RELATIV env-väg resolvas mot REPO-ROTEN så den matchar
    // Python-sidans ``resolve_generated_dir`` (REPO_ROOT / relative); en
    // absolut väg används oförändrad.
    return path.isAbsolute(raw)
      ? path.resolve(raw)
      : path.resolve(repoRoot, raw);
  }
  return path.join(repoRoot, "..", "sajtbyggaren-output", ".generated");
}

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
 * Samla in alla käll-filer under ``rootDir`` (utom ``SKIP_DIRS``,
 * ``.env*``-filer och symlinks) som ``writeFiles``-deskriptorer med
 * POSIX-relativa paths. Kastar om projektet är orimligt stort (oftast ett
 * tecken på att ``node_modules`` inte exkluderades) så vi aldrig laddar upp
 * gigabyte. ``.env*`` blockeras (utom ``.env.example``) så inga secrets
 * läcker till den publika sandboxen.
 */
function collectSource(rootDir: string): CollectedSource {
  const files: { relPath: string; content: Buffer }[] = [];
  const dirSet = new Set<string>();
  let totalBytes = 0;

  const walk = (absDir: string): void => {
    for (const entry of readdirSync(absDir, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        if (SKIP_DIRS.has(entry.name)) continue;
        walk(path.join(absDir, entry.name));
        continue;
      }
      // Symlinks hoppas över: ``Dirent.isFile()`` är ``false`` för en
      // symlink (typen speglar katalog-entryn, inte målet).
      if (!entry.isFile()) continue;
      // Säkerhet (samma B54/B58-mönster som stackblitz-files.ts): ladda
      // ALDRIG upp ``.env*`` till den publika sandboxen — bara
      // ``.env.example`` (ofarlig placeholder) är tillåten. Case-insensitivt
      // så ``.ENV``/``.Env.Local`` också fångas.
      const lowerName = entry.name.toLowerCase();
      if (lowerName.startsWith(".env") && lowerName !== ".env.example") {
        continue;
      }
      const absPath = path.join(absDir, entry.name);
      const relPath = path.relative(rootDir, absPath).split(path.sep).join("/");
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

  walk(rootDir);
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
 * Spike-agnostisk: konsumenter (CLI vs adapter) ansvarar för sin egen gating.
 */
export async function createSandboxPreview(
  request: SandboxPreviewRequest,
): Promise<SandboxPreviewResult> {
  const logs: string[] = [];

  const siteIdError = validateSiteId(request.siteId ?? "");
  if (siteIdError) {
    return failed(`Ogiltigt siteId: ${siteIdError}`);
  }

  const credentials = resolveCredentials();
  if (!credentials) {
    return failed(
      "Vercel-credentials saknas. Sätt antingen VERCEL_OIDC_TOKEN (via " +
        "`vercel link` + `vercel env pull`) eller trion VERCEL_TOKEN + " +
        "VERCEL_TEAM_ID + VERCEL_PROJECT_ID. Runnern degraderar hellre ärligt " +
        "än kraschar.",
    );
  }
  logs.push(`Auth-läge: ${credentials.mode}.`);

  const sourceDir = resolveSourceDir(request.siteId);
  if (!sourceDir) {
    return failed(
      `Hittade ingen byggd sajt för siteId="${request.siteId}" under ` +
        `${resolveGeneratedDir()}. Kör build_site.py först.`,
      logs,
    );
  }
  logs.push(`Käll-katalog: ${sourceDir}.`);

  const sdk = await loadSandboxSdk();
  if (!sdk) {
    return failed(
      "@vercel/sandbox är inte installerad i apps/viewser. Kör " +
        "`cd apps/viewser && npm install` (paketet ligger i package.json). " +
        "Runnern degraderar ärligt istället för att krascha.",
      logs,
    );
  }
  const { Sandbox } = sdk;

  let collected: CollectedSource;
  try {
    collected = collectSource(sourceDir);
  } catch (error) {
    return failed(messageFromError(error), logs);
  }
  logs.push(
    `Samlade ${collected.files.length} filer ` +
      `(${Math.round(collected.totalBytes / 1024)} kB) för upload.`,
  );

  const ttlMs = clampTtl(request.ttlMs);
  const sandboxName = `sajtbyggaren-preview-${slug(request.siteId)}-${Date.now()}`;

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

    const tInstall = Date.now();
    const install = await sandbox.runCommand({
      cmd: "npm",
      args: ["install", "--no-audit", "--no-fund", "--loglevel", "warn"],
      stdout: process.stdout,
      stderr: process.stderr,
    });
    installMs = Date.now() - tInstall;
    if (install.exitCode !== 0) {
      await safeStop(sandbox);
      return failed(
        `npm install misslyckades (exit ${install.exitCode}) i sandboxen.`,
        logs,
      );
    }
    logs.push(`npm install klar på ${installMs} ms.`);

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
      return failed(
        `next build misslyckades (exit ${build.exitCode}) i sandboxen.`,
        logs,
      );
    }
    logs.push(`next build klar på ${buildMs} ms.`);

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
      return failed(
        `next start svarade inte på ${url} inom ` +
          `${Math.round(READY_POLL_TIMEOUT_MS / 1000)} s. Sandbox stoppad.`,
        logs,
      );
    }

    const totalMs = Date.now() - t0;
    logs.push(`Preview live på ${url} (cold-start totalt ${totalMs} ms).`);

    return {
      status: "ready",
      url,
      sandboxId: sandbox.name,
      ttlMs,
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
    };
  } catch (error) {
    if (sandbox) await safeStop(sandbox);
    return failed(messageFromError(error), logs);
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
