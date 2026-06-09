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
import { existsSync, readFileSync } from "node:fs";
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
  // Viewser körs från apps/viewser/ så två steg upp = repo-roten.
  const repoRoot = path.resolve(process.cwd(), "..", "..");
  const envOverride = process.env.SAJTBYGGAREN_GENERATED_DIR;
  if (envOverride && envOverride.trim()) {
    const raw = envOverride.trim();
    // En RELATIV env-väg resolvas mot REPO-ROTEN (inte process.cwd()) så
    // den matchar Python-sidans ``resolve_generated_dir`` (REPO_ROOT /
    // relative). Utan detta skrev build_site.py till ``<repo>/<rel>`` medan
    // preview letade i ``<repo>/apps/viewser/<rel>`` → olika mappar och
    // "Genererad sajt saknas". Absoluta värden används oförändrade.
    return path.isAbsolute(raw)
      ? path.resolve(raw)
      : path.resolve(repoRoot, raw);
  }
  // Default: ../sajtbyggaren-output/.generated/ relativt repo-roten.
  return path.join(repoRoot, "..", "sajtbyggaren-output", ".generated");
}

// Build id format YYYYMMDDTHHMMSSZ with an optional -NN collision suffix.
// Validated before joining to a path so a tampered or corrupt current.json
// cannot trigger directory traversal (no slash/backslash/dot-dot can match).
const BUILD_ID_RE = /^\d{8}T\d{6}Z(?:-\d{2,})?$/;

/**
 * Läs ``<siteRoot>/current.json`` och returnera absolut sökväg till den
 * aktiva build-katalogen, eller ``null`` om pekaren saknas/är ogiltig.
 *
 * Speglar ``packages/generation/build/immutable_builds.py:read_active_build_dir``
 * fast på TS-sidan (B157 nivå 4 Stage A). Builder:n bygger numera till
 * ``<siteRoot>/builds/<buildId>/`` och publicerar aktiv build via en atomär
 * ``current.json``-pekare; preview ska köra mot den katalogen, aldrig mot en
 * dir som Builder:n samtidigt skriver till.
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
  // Cross-validate the decorative buildPath against activeBuildId (mirror of
  // immutable_builds.read_active_build_dir): a present-but-mismatching buildPath
  // means the pointer is inconsistent (tampered/half-updated), so reject it.
  // B-Codex 2026-06-01: mirror Python's ``build_path is not None and
  // build_path != f"builds/{build_id}"`` EXACTLY — a present buildPath of ANY
  // type (number, object, mismatching string) rejects; only absent (undefined)
  // or JSON-null is allowed. The previous ``typeof === "string"`` guard let a
  // present non-string buildPath slip through (TS/Python parity gap).
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
 * Resolverar vilken katalog ``next start`` ska köras i för en redan byggd
 * sajt under ``<generated>/<siteId>/``.
 *
 *   1. Föredra den immutable build:en som ``current.json`` pekar på (om den
 *      finns och har en ``.next/``-output) — det nya nivå-4-layoutet.
 *   2. Annars: bakåtkompatibel fallback till det gamla flata layoutet
 *      ``<siteRoot>/.next`` (sajter byggda före nivå 4, plus det första
 *      migreringsfönstret innan nästa rebuild skapat en pekare).
 *
 * Returnerar ``null`` när varken pekad build eller flat ``.next`` finns, så
 * callern kan kasta det befintliga "build-artefakter saknas"-felet.
 */
function resolveActivePreviewDir(siteRoot: string): string | null {
  const activeBuildDir = readActiveBuildDir(siteRoot);
  if (activeBuildDir && existsSync(path.join(activeBuildDir, ".next"))) {
    return activeBuildDir;
  }
  if (existsSync(path.join(siteRoot, ".next"))) {
    return siteRoot;
  }
  return null;
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
      // Tree-kill, inte bara entry.process.kill(): på Windows dödar
      // ChildProcess.kill() bara npx-parenten och lämnar ``next start``-
      // barnet som orphan (samma B157-klass som killProcessTree fixar i
      // rebuild-pathen). Fire-and-forget är OK även precis före
      // process.exit(0) eftersom spawn("taskkill") skapar OS-processen
      // synkront — den lever vidare och reapar trädet efter att viewser
      // exitat. POSIX faller tillbaka på child.kill(signal) i helpern.
      void killProcessTree(entry.process, "SIGTERM");
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
 * Windows-safe tree-kill av en spawned process + alla dess descendants.
 *
 * **Bakgrund (B157 round 3, 2026-05-28):** Node.js ``ChildProcess.kill()``
 * på Windows mappar internt till ``TerminateProcess(handle)``, som
 * **bara dödar direct PID — INTE descendants**. Det betyder att när
 * vi spawnar preview-servern via ``npx next start`` så blir process-
 * trädet ``npx (parent)`` → ``next start (child)``. ``child.kill()``
 * dödar bara npx-shellen — ``next start``-barnet lever vidare och
 * håller fil-lås på native ``.node``-binaries i
 * ``node_modules/@next/swc-*-msvc/``. Caller (``copy_starter()``-
 * ``shutil.rmtree``) får då ``PermissionError: [WinError 5]`` trots
 * att ``stopAndWaitPreviewServer`` returnerat ``true``.
 *
 * Lösning: spawna ``taskkill /PID <pid> /T /F`` som följer hela
 * Windows-process-trädet. ``/T`` = "tree" (alla descendants),
 * ``/F`` = "force" (motsvarar SIGKILL — Windows har ingen graceful
 * variant via taskkill). På POSIX (Linux/macOS) skickar vi signalen
 * till den direkta child-PID:en. OBS: ``child.kill()`` på POSIX dödar
 * INTE descendants (``npx`` → ``next start``, eller ``python`` → ``npm``
 * → ``next``) — full POSIX-tree-kill kräver ``detached``-spawn +
 * ``process.kill(-pid)`` (killpg) och tas som egen Linux-verifierad
 * sprint. På POSIX är kvarvarande grand-children en process/port-läcka,
 * inte ett hårt fil-lås (inode-räknaren släpper filen vid sista handle),
 * så B157-klassen (Windows ``.node``-lås) drabbar inte operatören.
 *
 * Async + non-throwing: returnerar när taskkill exitar (max 2s)
 * eller efter timeout. Errors sväljs eftersom tree-kill är best-
 * effort — viktigare att inte hänga än att rapportera misslyckande.
 *
 * Detta löser den kvarstående B157-orphanen som ``stopAndWaitPreviewServer``-
 * round-2-fixen (697cf4f) inte fångade. Verifierad reproduktion
 * 2026-05-28 ~01:08: ``next start (PID 31472)`` levde kvar efter
 * att Viewser:s ``child.kill("SIGKILL")`` skickats till
 * ``npx (PID 27976)``-parent.
 */
export async function killProcessTree(
  child: ChildProcess,
  signal: NodeJS.Signals,
): Promise<void> {
  if (process.platform !== "win32") {
    // POSIX best-effort: signalera den direkta child-PID:en. Se JSDoc ovan
    // om descendant-läckan (kräver detached + killpg för full tree-kill).
    try {
      child.kill(signal);
    } catch {
      // Race: process kan ha exitat mellan check och kill.
    }
    return;
  }

  if (typeof child.pid !== "number") {
    return;
  }

  await new Promise<void>((resolve) => {
    let settled = false;
    const finalize = () => {
      if (settled) return;
      settled = true;
      resolve();
    };

    const tk = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    tk.once("exit", finalize);
    tk.once("error", finalize);
    // Hard cap så vi aldrig hänger om taskkill själv hänger.
    setTimeout(finalize, 2_000);
  });
}

/**
 * Stoppa preview-servern för ``siteId`` om den körs. Idempotent.
 *
 * Eldsnabb fire-and-forget: tree-kill + ta bort från map. Väntar INTE
 * in att processen exitar. Använd ``stopAndWaitPreviewServer`` om
 * caller måste säkra att OS släppt filsystem-lås innan nästa steg
 * (t.ex. ``shutil.rmtree(node_modules)`` i ``build_site.py``).
 */
export function stopPreviewServer(siteId: string): boolean {
  const entry = servers.get(siteId);
  if (!entry) return false;
  // Fire-and-forget tree-kill. Caller bryr sig inte om timing/exit-event.
  // ``void`` markerar medvetet att vi inte väntar in promisen.
  void killProcessTree(entry.process, "SIGTERM");
  servers.delete(siteId);
  return true;
}

/**
 * Stoppa preview-servern för ``siteId`` och VÄNTA in att processen
 * faktiskt exitar + OS-level file-lock-release. Idempotent — returnerar
 * ``false`` om ingen server körde.
 *
 * **Varför detta finns (B157):** ``build_site.py:copy_starter()`` kör
 * ``shutil.rmtree()`` på ``.generated/<siteId>/``-dirs när lockfile
 * driftar (``_npm_install_inputs_changed=True``). På Windows håller
 * en live ``next start``-process hårda fil-lås på native
 * ``node_modules/@next/swc-win32-*-msvc/next-swc.*.node``-binaries
 * (de är DLL-liknande). ``rmtree`` failar då med
 * ``PermissionError: [WinError 5]`` mellan ``poll()`` och faktisk
 * delete. På Linux/macOS skulle aggressive delete oftast lyckas (inode-
 * räknaren håller filen tills sista handle stänger) men anti-patternet
 * att rebuilda ovanpå live preview-katalog kvarstår.
 *
 * Fixen: build-runner anropar denna helper FÖRE ``build_site.py``
 * spawnas så preview-processen är garanterat död + Windows har
 * frigjort .node-binary-låsen.
 *
 * Sekvens:
 *   1. Ta bort entry från ``servers``-map (nästa spawn re-skapar).
 *   2. **Windows-fast-path** (round 3, 2026-05-28): direkt
 *      ``taskkill /T /F`` på hela process-trädet (npx + next start +
 *      descendants), vänta in ``exit``-event med reap-cap, sedan
 *      200ms file-lock-release-wait. Hoppar över graceful SIGTERM-
 *      fönstret eftersom Node.js på Windows ändå mappar SIGTERM →
 *      TerminateProcess (force) — det finns ingen graceful path att
 *      förlora.
 *   3. **POSIX-graceful-path**: SIGTERM + vänta in ``exit``-event,
 *      timeout-fallback till SIGKILL efter ``timeoutMs``, sedan
 *      reap-cap-vänta för faktisk exit. Process groups respekteras
 *      naturligt av ``child.kill()`` på POSIX.
 *
 * Detta är **temporär fix** (gap-spec laddare nivå 1, ``docs/gaps/
 * GAP-windows-safe-rebuild-pipeline.md``). Rätt arkitektur är
 * immutable build-dir + manifest-pointer-swap så vi aldrig rebuildar
 * ovanpå live output. Tas i egen sprint.
 *
 * Round-historik:
 *   - Round 1 (`adba139`, akut): ``stopAndWaitPreviewServer``-helper
 *     med SIGTERM + timeout + SIGKILL + 200ms Windows-wait.
 *   - Round 2 (`697cf4f`, reap-fix): ``sigkillSent``-flag + sekundär
 *     ``Promise.race([exited, REAP_TIMEOUT_MS])`` så vi väntar på
 *     faktiskt exit-event efter SIGKILL.
 *   - Round 3 (denna commit): ``killProcessTree``-helper + Windows-
 *     fast-path som dödar npx-spawned descendants. Round 1 + 2 läste
 *     fel rotorsak — race i ``Promise.race`` var en aspekt, men
 *     huvudproblemet var att ``child.kill()`` på Windows aldrig nådde
 *     ``next start``-barnprocessen.
 */
export async function stopAndWaitPreviewServer(
  siteId: string,
  timeoutMs = 5_000,
): Promise<boolean> {
  const entry = servers.get(siteId);
  if (!entry) return false;

  const child = entry.process;
  servers.delete(siteId);

  // Redan dead → bara file-lock-release-wait (om Windows).
  if (child.killed || child.exitCode !== null) {
    if (process.platform === "win32") {
      await new Promise((r) => setTimeout(r, 200));
    }
    return true;
  }

  // exit-event-promise. Resolvar omedelbart om processen redan har
  // exitat mellan check ovan och här (mikro-race).
  const exited = new Promise<void>((resolve) => {
    if (child.exitCode !== null) {
      resolve();
      return;
    }
    child.once("exit", () => resolve());
  });

  // Windows-fast-path: direkt tree-kill via taskkill /T /F + vänta
  // in exit-event med reap-cap + Windows file-lock-release-wait.
  // Se ``killProcessTree``-jsdoc för bakgrund (B157 round 3).
  if (process.platform === "win32") {
    const REAP_TIMEOUT_MS = 2_000;
    await killProcessTree(child, "SIGKILL");
    await Promise.race([
      exited,
      new Promise<void>((r) => setTimeout(r, REAP_TIMEOUT_MS)),
    ]);
    // Extra wait så OS hinner släppa file-handles på native .node-binaries.
    await new Promise((r) => setTimeout(r, 200));
    return true;
  }

  // POSIX-graceful-path: SIGTERM med timeout-fallback till SIGKILL.
  // ``child.kill()`` respekterar process groups på POSIX så vi
  // behöver inte tree-kill här.
  try {
    child.kill("SIGTERM");
  } catch {
    // Process kan ha exitat mellan checken och kill.
  }

  // Steg 1: vänta på SIGTERM-exit eller ``timeoutMs``.
  // Om timeout vinner racet skickar callback:en SIGKILL och resolvar
  // ``timeoutPromise``. Vi noterar att SIGKILL har skickats så vi
  // i steg 2 kan vänta YTTERLIGARE på faktiskt exit-event.
  let sigkillSent = false;
  let timeoutHandle: NodeJS.Timeout | undefined;
  const timeoutPromise = new Promise<void>((resolve) => {
    timeoutHandle = setTimeout(() => {
      if (!child.killed && child.exitCode === null) {
        try {
          child.kill("SIGKILL");
          sigkillSent = true;
        } catch {
          // Process kan ha exitat under race.
        }
      }
      resolve();
    }, timeoutMs);
  });

  await Promise.race([exited, timeoutPromise]);
  if (timeoutHandle) clearTimeout(timeoutHandle);

  // Steg 2: om SIGKILL skickades måste vi VÄNTA på faktiskt exit-event
  // innan vi returnerar — annars bryter vi kontraktet att caller kan
  // köra fil-IO direkt efter return. SIGKILL är synkron från
  // avsändarens sida men kerneln behöver ms-tid att reapa processen
  // + frigöra fil-handles.
  //
  // ``REAP_TIMEOUT_MS`` är hard-floor för kernel-reap. Om processen
  // fortfarande inte exitat efter SIGKILL+REAP_TIMEOUT_MS är något
  // katastrofalt fel (kernel-blockad i D-state e.d.) och caller får
  // ett pessimistiskt return ändå — bättre att signalera "stopped"
  // efter rimlig vänta än att hänga viewser-build-pipeline för evigt.
  const REAP_TIMEOUT_MS = 2_000;
  if (sigkillSent && child.exitCode === null) {
    let reapHandle: NodeJS.Timeout | undefined;
    const reapTimeout = new Promise<void>((resolve) => {
      reapHandle = setTimeout(() => resolve(), REAP_TIMEOUT_MS);
    });
    await Promise.race([exited, reapTimeout]);
    if (reapHandle) clearTimeout(reapHandle);
  }

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
export function startPreviewServer(siteId: string): Promise<PreviewServerInfo> {
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
  if (
    existing &&
    !existing.process.killed &&
    existing.process.exitCode === null
  ) {
    await existing.ready;
    return {
      siteId,
      port: existing.port,
      url: `http://localhost:${existing.port}`,
      status: "ready",
      uptimeMs: Date.now() - existing.startedAt,
    };
  }

  const siteRoot = path.join(resolveGeneratedDir(), siteId);
  if (!existsSync(siteRoot)) {
    throw new Error(
      `Genererad sajt saknas: ${siteRoot} — kör build_site.py först.`,
    );
  }
  // B157 nivå 4 Stage A: kör preview mot den aktiva immutable build:en
  // (current.json-pekaren) med fallback till det gamla flata ``.next``-
  // layoutet. ``siteDir`` är därmed antingen ``builds/<buildId>/`` eller
  // site-roten — aldrig en katalog Builder:n samtidigt bygger i.
  const siteDir = resolveActivePreviewDir(siteRoot);
  if (!siteDir) {
    throw new Error(
      `Build-artefakter saknas: ${siteRoot}/.next/ — kör npm run build i sajtkatalogen.`,
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
    status: (entry.resolvedReady ? "ready" : "starting") as
      | "starting"
      | "ready",
    uptimeMs: Date.now() - entry.startedAt,
  }));
}
