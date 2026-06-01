/**
 * vercel-sandbox-spike — flag-gated PoC (spike), INTE en PreviewRuntime-adapter.
 *
 * Syfte (operatör-direktiv 2026-06-01): bevisa minsta möjliga sandbox som
 * kan SKAPA + VISA en isolerad preview av en redan-genererad sajt, stabilt
 * och länge nog att faktiskt öppna och bedöma (mobilkänsla, cold-start).
 * Detta är en spik bakom ``VIEWSER_SANDBOX_SPIKE=1`` — den wirear sig INTE
 * in i någon produktionsroute, utökar INTE ``PreviewRuntimeKind`` och rör
 * INTE ``packages/preview-runtime/``. Promotion till en riktig
 * ``vercel-sandbox`` PreviewRuntime-adapter kräver egen ADR (kandidat 0033)
 * + naming-bump + DI-wiring per ADR 0030.
 *
 * Förhållande till ADR 0030 (preview-provider-portability):
 *   - Den genererade sajten kopieras in OFÖRÄNDRAD och körs som vanlig
 *     Next.js (``npm install`` + ``next build`` + ``next start``). Ingen
 *     leverantörsspecifik kod injiceras i outputen (Regel 1).
 *   - Helpern degraderar ärligt (``status: "failed"`` med pedagogisk text,
 *     mönster: ``packages/preview-runtime/src/adapters/local.ts``-
 *     ``missingHandler``) när flaggan är av, tokens saknas, ``@vercel/sandbox``
 *     inte är installerad, eller bygget på disk saknas. Den kraschar aldrig.
 *
 * STEP 0 — verifierat mot officiella Vercel-docs (``@vercel/sandbox`` v2,
 * https://vercel.com/docs/vercel-sandbox, 2026-06-01):
 *   - Auth: OIDC-token (``VERCEL_OIDC_TOKEN``, auto på Vercel / via
 *     ``vercel link`` + ``vercel env pull`` lokalt) ELLER access-token-trion
 *     ``VERCEL_TOKEN`` + ``VERCEL_TEAM_ID`` + ``VERCEL_PROJECT_ID`` som
 *     spreadas in i ``Sandbox.create``.
 *   - Runtime: ``node24`` (default), även ``node22`` / ``node26`` /
 *     ``python3.13``. Vi väljer ``node24`` (matchar Viewser-stacken).
 *   - Publik URL: deklarera porten i ``ports: [3000]`` vid create, hämta
 *     sedan publik https-URL via ``sandbox.domain(3000)``. (Prior skiss
 *     antog en ``--publish-port``-flagga — det stämmer INTE; vi följer docs.)
 *   - TTL: ``timeout`` (ms) vid create, default 5 min, max 45 min Hobby /
 *     5 h Pro. ``sandbox.extendTimeout(ms)`` förlänger. Auto-stop vid utgång.
 *   - Cleanup: ``sandbox.stop()`` avslutar sessionen (returnerar
 *     CPU-/nätverks-/snapshot-metadata för kostnadssignal). Reconnect sker
 *     via ``Sandbox.get({ name })`` — i v2 är ``name`` den hållbara handeln.
 *     Vi exponerar den som ``sandboxId`` i PoC-kontraktet (se nedan).
 *   - Filer: ``sandbox.writeFiles([{ path, content: Buffer }])`` (kataloger
 *     skapas separat via ``mkdir -p``). Käll-filerna kopieras in; ``next``-
 *     bygget körs i sandboxen.
 *
 * Kontrakts-not: ``sandboxId`` i resultatet === ``sandbox.name`` i
 * ``@vercel/sandbox`` v2 (v1 hade ett separat ``sandboxId`` som nu backfillas
 * som ``name``). Cleanup-entryn tar emot detta värde och kör
 * ``Sandbox.get({ name })`` + ``stop()``.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const SPIKE_FLAG = "VIEWSER_SANDBOX_SPIKE";
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

function spikeEnabled(): boolean {
  return process.env[SPIKE_FLAG] === "1";
}

/**
 * Resolverar Vercel-credentials. OIDC vinner om ``VERCEL_OIDC_TOKEN`` finns
 * (SDK:n läser den automatiskt → vi spreadar ingenting). Annars krävs hela
 * access-token-trion. Returnerar ``null`` om ingen auth är tillgänglig.
 */
function resolveCredentials():
  | { mode: "oidc"; create: Record<string, never> }
  | { mode: "token"; create: { token: string; teamId: string; projectId: string } }
  | null {
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
 * Resolverar var ``build_site.py`` skrivit den genererade sajten. Speglar
 * ``apps/viewser/lib/local-preview-server.ts:resolveGeneratedDir`` men
 * re-implementeras här så spiken är fristående (vi rör inte den filen).
 */
function resolveGeneratedDir(): string {
  const envOverride = process.env.SAJTBYGGAREN_GENERATED_DIR;
  if (envOverride && envOverride.trim()) {
    return path.resolve(envOverride.trim());
  }
  const repoRoot = path.resolve(process.cwd(), "..", "..");
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
 * Resolverar käll-katalogen för en genererad sajt: föredra den aktiva
 * immutable build:en (``current.json``), annars det gamla flata layoutet
 * ``<siteRoot>/``. Returnerar ``null`` om sajten inte finns på disk.
 */
function resolveSourceDir(siteId: string): string | null {
  const siteRoot = path.join(resolveGeneratedDir(), siteId);
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

interface CollectedSource {
  files: { relPath: string; content: Buffer }[];
  dirs: string[];
  totalBytes: number;
}

/**
 * Samla in alla käll-filer under ``rootDir`` (utom ``SKIP_DIRS``) som
 * ``writeFiles``-deskriptorer med POSIX-relativa paths. Kastar om projektet
 * är orimligt stort (oftast ett tecken på att ``node_modules`` inte
 * exkluderades) så vi aldrig laddar upp gigabyte.
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
      if (!entry.isFile()) continue;
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
 */
export async function createSandboxPreview(
  request: SandboxPreviewRequest,
): Promise<SandboxPreviewResult> {
  const logs: string[] = [];

  if (!spikeEnabled()) {
    return failed(
      `Vercel-sandbox-spiken är avstängd. Sätt ${SPIKE_FLAG}=1 för att ` +
        "aktivera PoC:n. Detta är en konfigurations-grind, inte ett fel.",
    );
  }

  if (!request.siteId || !request.siteId.trim()) {
    return failed("createSandboxPreview kräver ett siteId.");
  }

  const credentials = resolveCredentials();
  if (!credentials) {
    return failed(
      "Vercel-credentials saknas. Sätt antingen VERCEL_OIDC_TOKEN (via " +
        "`vercel link` + `vercel env pull`) eller trion VERCEL_TOKEN + " +
        "VERCEL_TEAM_ID + VERCEL_PROJECT_ID. PoC:n degraderar hellre ärligt " +
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
        "PoC:n degraderar ärligt istället för att krascha.",
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
  const sandboxName = `sajtbyggaren-spike-${slug(request.siteId)}-${Date.now()}`;

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
      // Ephemeral PoC: ingen auto-snapshot på stop (sparar snapshot-storage).
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
 * Stoppa en spike-preview separat (manuell verifiering, TTL-städning eller
 * explicit anrop). Idempotent och icke-kastande. ``sandboxId`` är
 * ``sandbox.name`` från ``createSandboxPreview``.
 */
export async function stopSandboxPreview(
  sandboxId: string,
): Promise<SandboxStopResult> {
  const logs: string[] = [];

  if (!spikeEnabled()) {
    return {
      status: "failed",
      error: `Vercel-sandbox-spiken är avstängd. Sätt ${SPIKE_FLAG}=1.`,
    };
  }
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
    const result = await sandbox.stop();
    logs.push(`Sandbox ${sandboxId} stoppad.`);
    // CPU-/nätverks-siffrorna populeras på instans-accessorerna först EFTER
    // att VM:en stoppat (docs: "Only populated after the VM stops").
    return {
      status: "stopped",
      sandboxId,
      cost: {
        activeCpuMs: sandbox.activeCpuUsageMs,
        ingressBytes: sandbox.networkTransfer?.ingress,
        egressBytes: sandbox.networkTransfer?.egress,
        snapshotId: result.snapshot?.id ?? sandbox.currentSnapshotId,
      },
      logs,
    };
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
  return error instanceof Error ? error.message : "Okänt fel i vercel-sandbox-spiken.";
}
