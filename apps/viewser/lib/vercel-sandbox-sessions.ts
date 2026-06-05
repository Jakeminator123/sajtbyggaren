/**
 * vercel-sandbox-sessions — in-memory registry over aktiva Vercel Sandbox-
 * previews per ``siteId``.
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
 * Registret är medvetet INTE i ``vercel-sandbox-runner.ts``: runnern är
 * spike-agnostisk och delas med CLI:t (``scripts/spike_vercel_sandbox.ts``),
 * som äger sin egen lifecycle och inte ska auto-tracka sessioner.
 */

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
}

/**
 * In-memory ``Map<siteId, SandboxSession>``. Per Viewser-process; sessioner
 * överlever inte en omstart (och behöver inte göra det — TTL städar ändå).
 */
const sessionsBySite = new Map<string, SandboxSession>();

/**
 * Registrera (eller ersätt) den aktiva sandbox-sessionen för ``siteId``.
 * Anropas efter en lyckad ``createSandboxPreview``.
 */
export function recordSandboxSession(
  siteId: string,
  sandboxId: string,
  url: string,
): SandboxSession {
  const session: SandboxSession = {
    siteId,
    sandboxId,
    url,
    createdAt: new Date().toISOString(),
  };
  sessionsBySite.set(siteId, session);
  return session;
}

/**
 * Hämta den aktiva sandbox-sessionen för ``siteId`` om en finns. Används av
 * ``GET /api/preview/<siteId>`` i vercel-sandbox-läge för status-rapport utan
 * att skapa något nytt.
 */
export function getSandboxSession(siteId: string): SandboxSession | null {
  return sessionsBySite.get(siteId) ?? null;
}

/**
 * Stoppa den aktiva sandboxen för ``siteId`` om en är registrerad och ta bort
 * den ur registret. Idempotent och icke-kastande: returnerar ``false`` om ingen
 * session fanns (vanligt fall i ``local-next``-läge där registret är tomt — så
 * callers som ``build-runner`` får en no-op och oförändrat beteende).
 *
 * Vi tar bort entry:t INNAN ``stopSandboxPreview`` await:as så ett samtidigt
 * nytt bygge för samma ``siteId`` inte ser en redan-stoppande session.
 */
export async function stopSandboxSessionForSite(siteId: string): Promise<boolean> {
  const session = sessionsBySite.get(siteId);
  if (!session) return false;
  sessionsBySite.delete(siteId);
  await stopSandboxPreview(session.sandboxId);
  return true;
}

/** Lista alla aktiva sandbox-sessioner (admin/diagnostik). */
export function listSandboxSessions(): SandboxSession[] {
  return Array.from(sessionsBySite.values());
}
