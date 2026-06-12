/**
 * vercel-sandbox-sessions — durabelt registry over aktiva Vercel Sandbox-
 * previews per ``siteId``, lagrat i kv-store.
 *
 * Varför detta finns (livscykel + kostnad, ADR 0033): ``createSandboxPreview``
 * är keyad på ``siteId`` men returnerar ett ogenomskinligt ``sandboxId``
 * (= ``sandbox.name``) som ``stopSandboxPreview`` behöver för cleanup. Två
 * callers vill stoppa en sandbox men känner bara till ``siteId``, inte
 * ``sandboxId``:
 *
 *   1. ``build-runner.ts`` — ett nytt bygge/följdprompt ska stoppa den gamla
 *      sandboxen (samma ställe som ``stopAndWaitPreviewServer`` stoppar lokal
 *      preview innan rebuild).
 *   2. ``DELETE /api/preview/<siteId>`` — explicit stopp från UI/operatör.
 *
 * Den här modulen bryggar ``siteId -> sandboxId`` så de två callers kan stoppa
 * via ``siteId``. Sandboxar har ~15 min TTL och kostar ören per körning, så vi
 * får INTE läcka dem: ``preview-runtime-server.ts`` stoppar en ev. tidigare
 * session för samma ``siteId`` innan en ny skapas, och registrerar den nya.
 *
 * Lagring: registret är durabelt via kv-store (``getKvStore``). Lokalt utan
 * Redis-env blir det memory-drivern = exakt dagens per-process-beteende.
 * Hostat (Redis-driver) överlever sessionerna instansbyten, så en serverless-
 * instans kan stoppa en sandbox som en annan instans startade. Varje entry
 * lagras som JSON under ``viewser:sandbox-session:<siteId>`` med 45 min TTL —
 * sandboxar lever ~15 min, så 45 min ger marginal utan att döda entries läcker.
 *
 * Registret är medvetet INTE i ``vercel-sandbox-runner.ts``: runnern är
 * spike-agnostisk och delas med CLI:t (``scripts/spike_vercel_sandbox.ts``),
 * som äger sin egen lifecycle och inte ska auto-tracka sessioner.
 */

import { getKvStore, kvGetJson, kvSetJson } from "./kv-store";
import { stopSandboxPreview } from "./vercel-sandbox-runner";

export interface SandboxSession {
  /** ``siteId`` under ``.generated/<siteId>/``. */
  siteId: string;
  /** Hållbar handle för cleanup === ``sandbox.name``. */
  sandboxId: string;
  /** Publik https-URL (``…vercel.run``) till previewn. */
  url: string;
  /** ISO-timestamp när sessionen registrerades. */
  createdAt: string;
  /**
   * Byggets identitet som sandboxen serverar (Tier 2-invalidering,
   * 2026-06-12): den hostade ``viewser:site:<siteId>:current``-pekarens
   * ``buildId`` vid preview-starten. ``null``/utelämnad när ingen pekare
   * fanns (lokalt disk-läge, äldre sessioner) — då deltar sessionen inte i
   * buildId-snabbvägen och beteendet är som före invalideringen.
   */
  buildId?: string | null;
}

const SESSION_KEY_PREFIX = "viewser:sandbox-session:";

/** 45 min — sandboxens egen TTL är ~15 min, så detta städar utan läckage. */
const SESSION_TTL_SECONDS = 45 * 60;

function sessionKey(siteId: string): string {
  return `${SESSION_KEY_PREFIX}${siteId}`;
}

/**
 * Registrera (eller ersätt) den aktiva sandbox-sessionen för ``siteId``.
 * Anropas efter en lyckad ``createSandboxPreview``. ``buildId`` ska vara
 * pekarens värde LÄST FÖRE previewn samlade sin källa (preview-runtime-server
 * läser den en gång per request) — läses den efter kan ett bygge som blev
 * klart mitt under preview-starten ge sessionen NYA byggets id fast sandboxen
 * serverar det gamla innehållet, och invalideringen missar stale-sessionen.
 */
export async function recordSandboxSession(
  siteId: string,
  sandboxId: string,
  url: string,
  buildId: string | null = null,
): Promise<SandboxSession> {
  const session: SandboxSession = {
    siteId,
    sandboxId,
    url,
    createdAt: new Date().toISOString(),
    buildId,
  };
  await kvSetJson(getKvStore(), sessionKey(siteId), session, {
    ttlSeconds: SESSION_TTL_SECONDS,
  });
  return session;
}

/**
 * Hämta den aktiva sandbox-sessionen för ``siteId`` om en finns. Används av
 * ``GET /api/preview/<siteId>`` i vercel-sandbox-läge för status-rapport utan
 * att skapa något nytt.
 */
export async function getSandboxSession(
  siteId: string,
): Promise<SandboxSession | null> {
  return kvGetJson<SandboxSession>(getKvStore(), sessionKey(siteId));
}

/**
 * Stoppa den aktiva sandboxen för ``siteId`` om en är registrerad och ta bort
 * den ur registret. Idempotent och icke-kastande: returnerar ``false`` om ingen
 * session fanns (vanligt fall i ``local-next``-läge där registret är tomt — så
 * callers som ``build-runner`` får en no-op och oförändrat beteende).
 *
 * Vi tar bort KV-entryt INNAN ``stopSandboxPreview`` await:as så ett samtidigt
 * nytt bygge för samma ``siteId`` inte ser en redan-stoppande session.
 */
export async function stopSandboxSessionForSite(siteId: string): Promise<boolean> {
  let session: SandboxSession | null;
  try {
    const store = getKvStore();
    session = await kvGetJson<SandboxSession>(store, sessionKey(siteId));
    if (!session) return false;
    await store.delete(sessionKey(siteId));
  } catch (error) {
    // Icke-kastande kontrakt: ett KV-fel får inte fälla callers (build-runner,
    // DELETE-routen). Vi loggar och behandlar det som "ingen session".
    console.warn(
      `[vercel-sandbox-sessions] KV-fel vid stopp för ${siteId}:`,
      error instanceof Error ? error.message : error,
    );
    return false;
  }
  await stopSandboxPreview(session.sandboxId);
  return true;
}

/**
 * Den hostade build-pekarens KV-nyckel — samma nyckel som orkestrerings-
 * skriptet i ``hosted-build-runner.ts`` skriver efter varje lyckat bygge
 * (``{ buildId, blobPrefix, updatedAt }``, ingen TTL).
 */
export function hostedSiteCurrentKey(siteId: string): string {
  return `viewser:site:${siteId}:current`;
}

/**
 * Läs det aktuella hostade byggets ``buildId`` ur pekaren. ``null`` när ingen
 * pekare finns (sajt aldrig byggd hostat / lokalt memory-KV) eller vid
 * KV-fel — icke-kastande så preview-flödet aldrig faller på invalideringen.
 */
export async function getHostedCurrentBuildId(
  siteId: string,
): Promise<string | null> {
  try {
    const pointer = await kvGetJson<{ buildId?: unknown }>(
      getKvStore(),
      hostedSiteCurrentKey(siteId),
    );
    return typeof pointer?.buildId === "string" && pointer.buildId
      ? pointer.buildId
      : null;
  } catch {
    return null;
  }
}

/** Snabb liveness-probe mot sessionens publika URL (spegel av
 * ``waitForPublicUrl``-acceptansen: ok eller 404 = servern lyssnar; 5xx/429 =
 * edge-svar för en död/bootande sandbox). En enda GET, kort timeout — det här
 * är en snabbväg, inte en poll-loop. */
async function isSessionUrlAlive(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, {
      method: "GET",
      signal: AbortSignal.timeout(5_000),
      redirect: "manual",
    });
    return res.ok || res.status === 404;
  } catch {
    return false;
  }
}

/**
 * Tier 2-snabbvägen MED buildId-invalidering (operatörsbeslut 2026-06-12).
 *
 * Mekanismvalet (EN koherent livscykel, dokumenterat även i
 * ``hosted-build-runner.ts``): det hostade bygget stoppar preview-sessionen
 * vid BYGGSTART (primärmekanismen). Den här funktionen är snabbvägen +
 * backstoppen vid PREVIEW-POST: en session återanvänds BARA när dess
 * ``buildId`` matchar den aktuella pekaren OCH sandboxen bevisligen svarar —
 * annars stoppas den (invalidering) och callern tar fulla vägen. Det fångar
 * sessioner som startades efter byggstart-stoppet men före pekar-swappen.
 *
 *   - Ingen pekare (``currentBuildId === null``, t.ex. lokalt disk-läge) →
 *     ``null`` UTAN att röra sessionen: den lokala reuse-vägen
 *     (``tryReuseSandboxPreview``, re-upload mot varm sandbox) äger det
 *     fallet precis som före invalideringen.
 *   - Session saknas / saknar buildId / fel buildId / död URL → stoppa
 *     (best-effort) och returnera ``null`` → fulla vägen bygger nytt.
 *   - Match + levande URL → returnera sessionen (ingen SDK-rundtur alls).
 */
export async function tryReuseSessionPreview(
  siteId: string,
): Promise<SandboxSession | null> {
  const currentBuildId = await getHostedCurrentBuildId(siteId);
  if (!currentBuildId) return null;

  const session = await getSandboxSession(siteId);
  if (!session) return null;

  if (!session.buildId || session.buildId !== currentBuildId) {
    // Stale: sandboxen serverar ett annat (eller okänt) bygge än pekaren.
    await stopSandboxSessionForSite(siteId);
    return null;
  }
  if (!session.url || !(await isSessionUrlAlive(session.url))) {
    // Rätt bygge men sandboxen är död/utgången — städa och bygg ny.
    await stopSandboxSessionForSite(siteId);
    return null;
  }
  return session;
}

/** Lista alla aktiva sandbox-sessioner (admin/diagnostik). */
export async function listSandboxSessions(): Promise<SandboxSession[]> {
  const store = getKvStore();
  const keys = await store.listKeys(SESSION_KEY_PREFIX);
  const sessions = await Promise.all(
    keys.map((key) => kvGetJson<SandboxSession>(store, key)),
  );
  return sessions.filter((session): session is SandboxSession => session !== null);
}
