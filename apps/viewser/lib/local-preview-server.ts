/**
 * local-preview-server — startar och hanterar en lokal Next.js-server
 * per genererad siteId så ViewerPanel kan rendera sajten i en iframe
 * direkt mot ``http://localhost:<port>`` istället för att gå via
 * StackBlitz.
 *
 * Varför detta finns:
 *   - StackBlitz fungerar bara i Chromium (Safari/Firefox saknar
 *     credentialless-iframe-stöd). Fallback öppnar i nytt fönster på
 *     stackblitz.com vilket är fult, långsamt och förvirrande.
 *   - StackBlitz behöver boota WebContainer + npm install (~60s första
 *     gången). Lokal ``next start`` på redan-byggd ``.next/`` är klart
 *     på 1-2 sekunder.
 *   - För Sprint 5:s live token-editor är same-machine-iframe ett krav
 *     för att postMessage från Site Inspector ska nå runtime-listenern
 *     i layout.tsx — cross-origin StackBlitz-iframen levererar inte
 *     meddelandet.
 *
 * Arkitektur:
 *   - En in-memory ``Map<siteId, ServerEntry>`` håller spawnade
 *     processer.
 *   - Port-allokering: deterministisk hash av siteId modulo 100 inom
 *     intervallet 4100-4199 så samma siteId alltid får samma port.
 *     Vid kollision (extremt sällsynt med <50 sajter på samma maskin)
 *     prövas nästa lediga port.
 *   - Cleanup: process-handlern lyssnar på SIGTERM/SIGINT och dödar
 *     alla preview-servrar innan viewser stänger.
 *   - Health-check: server räknas som klar när en HTTP HEAD-request
 *     mot porten får svar (max 30 retries × 200ms = 6s timeout).
 *     Servern själv tar ~1-2s att starta på redan-byggd app.
 *
 * Säkerhet:
 *   - ``next start`` använder bara filerna i den specifika
 *     ``.generated/<siteId>/`` så ingen risk att läcka annan kod.
 *   - Vi lyssnar på ``127.0.0.1`` (default ``next start`` bind),
 *     inte ``0.0.0.0`` — preview-servrar är inte exponerade på LAN.
 *   - Localhost-guard på API-routen som triggar denna modul.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { createConnection } from "node:net";
import path from "node:path";

const PORT_BASE = 4100;
const PORT_RANGE = 100;
const HEALTH_RETRIES = 30;
const HEALTH_INTERVAL_MS = 200;

/**
 * Resolverar var ``build_site.py`` skrivit den genererade Next.js-
 * sajten. Speglar logiken i AGENTS.md ("default
 * ``../sajtbyggaren-output/.generated/<siteId>/``, kan overridas med
 * env ``SAJTBYGGAREN_GENERATED_DIR``"). På Cloud Agent VM:n resolveras
 * default-pathen till ``/sajtbyggaren-output/.generated/``.
 */
function resolveGeneratedDir(): string {
  const envOverride = process.env.SAJTBYGGAREN_GENERATED_DIR;
  if (envOverride && envOverride.trim()) {
    return path.resolve(envOverride.trim());
  }
  // Default: ../sajtbyggaren-output/.generated/ relativt repo-roten.
  // Viewser körs från apps/viewser/ så vi behöver kliva upp två steg
  // till repo-roten + ut och in i sajtbyggaren-output.
  const repoRoot = path.resolve(process.cwd(), "..", "..");
  return path.join(repoRoot, "..", "sajtbyggaren-output", ".generated");
}

interface ServerEntry {
  /** Port servern lyssnar på (``http://localhost:<port>``). */
  port: number;
  /** Spawnad child-process. ``kill()`` används för att stoppa servern. */
  process: ChildProcess;
  /** Wall-clock ms när servern spawnades. För TTL-checks. */
  startedAt: number;
  /** Promise som löses när health-check passerat. Återanvänds av samtidiga callers. */
  ready: Promise<void>;
  /** Sätts till ``true`` efter att ``ready``-promiset har resolvats. */
  resolvedReady: boolean;
}

const servers = new Map<string, ServerEntry>();
/**
 * In-flight ``startPreviewServer``-anrop per siteId. Två samtidiga
 * POST /api/preview/<siteId> (eller dubbelklick i UI:t) ska dela
 * samma spawn istället för att race:a och skapa två ``next start``-
 * processer där den första blir orphan. W1 i scout-review 2026-05-24.
 */
const startInFlight = new Map<string, Promise<PreviewServerInfo>>();
let cleanupHandlerInstalled = false;

/**
 * Probe om en port är ledig på OS-nivå via TCP-connect. Returnerar
 * ``true`` om inget lyssnar (connection refused), ``false`` om något
 * svarar. Används av ``allocatePort`` för att undvika portkrockar
 * med processer utanför vår ``servers``-map.
 */
function isPortFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = createConnection({ host: "127.0.0.1", port });
    // Timeout-skydd så ``allocatePort`` aldrig hänger om TCP-connecten
    // varken ``connect``ar eller ``error``ar inom rimlig tid (ovanligt
    // men möjligt vid t.ex. firewall-blockerad probe). Vi behandlar
    // timeout som "porten ej fri" — säkrare default eftersom vi då
    // bara hoppar vidare till nästa port istället för att låsa starten.
    const timer = setTimeout(() => {
      socket.destroy();
      resolve(false);
    }, 500);
    socket.once("connect", () => {
      clearTimeout(timer);
      socket.end();
      resolve(false);
    });
    socket.once("error", () => {
      clearTimeout(timer);
      socket.destroy();
      resolve(true);
    });
  });
}

/**
 * Deterministisk port-allokering: hash siteId → port i pool. Samma
 * siteId får alltid samma port vilket gör browser-cache och dev-flow
 * konsekvent (operatören kan bokmärka http://localhost:4137 för en
 * specifik sajt). Vid kollision (samma port redan upptagen av annan
 * siteId eller extern process) prövas nästa port i sekvens.
 */
async function allocatePort(siteId: string): Promise<number> {
  let hash = 0;
  for (let i = 0; i < siteId.length; i += 1) {
    hash = (hash * 31 + siteId.charCodeAt(i)) >>> 0;
  }
  const baseOffset = hash % PORT_RANGE;
  const usedPorts = new Set(
    Array.from(servers.values()).map((entry) => entry.port),
  );
  for (let i = 0; i < PORT_RANGE; i += 1) {
    const candidate = PORT_BASE + ((baseOffset + i) % PORT_RANGE);
    if (usedPorts.has(candidate)) continue;
    if (await isPortFree(candidate)) return candidate;
  }
  throw new Error(
    `Inga lediga preview-portar i ${PORT_BASE}-${PORT_BASE + PORT_RANGE - 1}. ` +
      `Stäng några gamla sajter via DELETE /api/preview/<siteId>.`,
  );
}

/**
 * HTTP-health-check: försök göra en HEAD-request mot porten och
 * returnera när Next.js svarar med valfri HTTP-status (200, 404 etc.).
 * Skiljer sig från en ren TCP-check genom att vi vet att det faktiskt
 * är en HTTP-server som svarar, inte en annan process som råkar
 * lyssna på porten.
 */
function waitForReady(port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const tryConnect = () => {
      attempts += 1;
      fetch(`http://127.0.0.1:${port}/`, {
        method: "HEAD",
        signal: AbortSignal.timeout(1000),
      })
        .then((res) => {
          if (res.ok || res.status === 404) {
            resolve();
          } else {
            throw new Error(`Unexpected status ${res.status}`);
          }
        })
        .catch(() => {
          if (attempts >= HEALTH_RETRIES) {
            reject(
              new Error(
                `Preview-servern på port ${port} svarade inte inom ${HEALTH_RETRIES * HEALTH_INTERVAL_MS}ms.`,
              ),
            );
            return;
          }
          setTimeout(tryConnect, HEALTH_INTERVAL_MS);
        });
    };
    tryConnect();
  });
}

function installCleanupHandler(): void {
  if (cleanupHandlerInstalled) return;
  cleanupHandlerInstalled = true;
  const stopAll = () => {
    for (const [siteId, entry] of servers.entries()) {
      try {
        entry.process.kill("SIGTERM");
      } catch {
        // Process kan redan ha exitat; ignorera.
      }
      servers.delete(siteId);
    }
  };
  process.once("SIGINT", () => {
    stopAll();
    process.exit(0);
  });
  process.once("SIGTERM", () => {
    stopAll();
    process.exit(0);
  });
  process.once("beforeExit", stopAll);
}

export interface PreviewServerInfo {
  siteId: string;
  port: number;
  url: string;
  /** ``"starting"`` medan health-check pågår, ``"ready"`` när HTTP-server svarar. */
  status: "starting" | "ready";
  /** ms sedan servern spawnades. */
  uptimeMs: number;
}

/**
 * Hämta info om preview-server för ``siteId`` om en finns. Returnerar
 * ``null`` om ingen server är spawnad. Används av GET-endpointen för
 * att rapportera status utan att starta något nytt.
 */
export function getPreviewServer(siteId: string): PreviewServerInfo | null {
  const entry = servers.get(siteId);
  if (!entry) return null;
  return {
    siteId,
    port: entry.port,
    url: `http://localhost:${entry.port}`,
    status: entry.resolvedReady ? "ready" : "starting",
    uptimeMs: Date.now() - entry.startedAt,
  };
}

/**
 * Stoppa preview-servern för ``siteId`` om den körs. Idempotent.
 */
export function stopPreviewServer(siteId: string): boolean {
  const entry = servers.get(siteId);
  if (!entry) return false;
  try {
    entry.process.kill("SIGTERM");
  } catch {
    // Process kan redan ha exitat.
  }
  servers.delete(siteId);
  return true;
}

/**
 * Starta (eller återanvänd) en lokal preview-server för ``siteId``.
 *
 * Idempotent: om en server redan körs för samma siteId returneras
 * dess info direkt utan att starta något nytt. Samtidiga callers
 * delar samma ``ready``-promise.
 *
 * Kastar om:
 *   - ``.generated/<siteId>/`` saknas (build har inte kört)
 *   - ``.next/`` saknas (npm run build failade)
 *   - ingen ledig port i poolen
 *   - health-check timeout (next start kraschar oftast med stdout)
 */
export function startPreviewServer(
  siteId: string,
): Promise<PreviewServerInfo> {
  // W1: per-siteId in-flight mutex. Två samtidiga startups för samma
  // siteId delar samma spawn-promise. Mutexen släpps automatiskt när
  // spawn:en klart resolvar (success eller fel).
  const existingFlight = startInFlight.get(siteId);
  if (existingFlight) return existingFlight;

  const flight = doStartPreviewServer(siteId).finally(() => {
    startInFlight.delete(siteId);
  });
  startInFlight.set(siteId, flight);
  return flight;
}

async function doStartPreviewServer(
  siteId: string,
): Promise<PreviewServerInfo> {
  installCleanupHandler();

  // Idempotent: returnera befintlig server om den fortfarande lever.
  const existing = servers.get(siteId);
  if (existing && !existing.process.killed && existing.process.exitCode === null) {
    await existing.ready;
    return {
      siteId,
      port: existing.port,
      url: `http://localhost:${existing.port}`,
      status: "ready",
      uptimeMs: Date.now() - existing.startedAt,
    };
  }

  const siteDir = path.join(resolveGeneratedDir(), siteId);
  if (!existsSync(siteDir)) {
    throw new Error(
      `Genererad sajt saknas: ${siteDir} — kör build_site.py först.`,
    );
  }
  if (!existsSync(path.join(siteDir, ".next"))) {
    throw new Error(
      `Build-artefakter saknas: ${siteDir}/.next/ — kör npm run build i sajtkatalogen.`,
    );
  }
  const port = await allocatePort(siteId);

  // ``next start`` lyfter porten från ``-p``-flaggan. Vi använder
  // ``npx next start`` snarare än ``npm start`` eftersom det undviker
  // att starta en hel npm-process-tree (snabbare + lättare att döda).
  const child = spawn("npx", ["next", "start", "-p", String(port)], {
    cwd: siteDir,
    env: {
      ...process.env,
      // Tvinga production-mode så Next.js inte försöker köra dev-server.
      NODE_ENV: "production",
      // Reset PORT om viewser-processen råkar ha satt den.
      PORT: String(port),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  // Logga stderr så operatören kan diagnosa om servern kraschar.
  // Lagra inte stdout i minne — kan bli stor över tid.
  const stderrChunks: string[] = [];
  child.stderr?.on("data", (chunk: Buffer) => {
    if (stderrChunks.length < 50) {
      stderrChunks.push(chunk.toString("utf-8"));
    }
  });

  child.once("exit", (code) => {
    if (code !== 0 && code !== null) {
      // Diagnostic log so operatören kan se i viewser-loggen varför
      // en preview-server kraschade (oftast saknade build-artefakter).
      console.warn(
        `[local-preview] ${siteId} exited with code ${code}:\n${stderrChunks.join("").slice(-1000)}`,
      );
    }
    // Rensa från map så nästa start kan re-spawna.
    if (servers.get(siteId)?.process === child) {
      servers.delete(siteId);
    }
  });

  const ready = waitForReady(port).catch((error) => {
    // Health-check timeout → döda processen och kasta uppåt så
    // API-routen kan returnera 500 med stderr som kontext.
    try {
      child.kill("SIGTERM");
    } catch {
      // ignore
    }
    servers.delete(siteId);
    const stderrTail = stderrChunks.join("").slice(-500);
    throw new Error(
      `${(error as Error).message}\nstderr: ${stderrTail || "(empty)"}`,
    );
  });

  const entry: ServerEntry = {
    port,
    process: child,
    startedAt: Date.now(),
    ready,
    resolvedReady: false,
  };
  servers.set(siteId, entry);

  await ready;
  entry.resolvedReady = true;

  return {
    siteId,
    port,
    url: `http://localhost:${port}`,
    status: "ready",
    uptimeMs: Date.now() - entry.startedAt,
  };
}

/**
 * Lista alla aktiva preview-servrar. Används av admin-endpoint för
 * att se vad som är spawnat på maskinen.
 */
export function listPreviewServers(): PreviewServerInfo[] {
  return Array.from(servers.entries()).map(([siteId, entry]) => ({
    siteId,
    port: entry.port,
    url: `http://localhost:${entry.port}`,
    status: (entry.resolvedReady ? "ready" : "starting") as "starting" | "ready",
    uptimeMs: Date.now() - entry.startedAt,
  }));
}
