/**
 * Tunn auth-seam för marknadssajten. Idag finns ingen riktig inloggning —
 * "Logga in" och alla bygg-CTA:er navigerar bara in i studion (konsolen).
 * När Jakobs riktiga auth-backend landar slottas den in här bakom
 * AUTH_ENABLED utan att header/sidor behöver göras om.
 *
 * Identifierare på engelska, användarvänd text på svenska (AGENTS.md).
 */

/** Slås på när en riktig auth-backend finns. Tills dess: ren navigation. */
export const AUTH_ENABLED = false as const;

/** Dit studion (operatörskonsolen) bor efter route-group-spliten. */
export const STUDIO_HREF = "/studio" as const;

/** Mål för "Logga in" + bygg-CTA i v1: rakt in i studion. */
export const LOGIN_HREF: string = STUDIO_HREF;

/** Användarvänd etikett. Ärligt: inget konto skapas ännu. */
export const LOGIN_LABEL = "Logga in" as const;

/**
 * Ärlig hint (title/tooltip) på login-entry tills riktig auth finns: vi fejkar
 * inget konto-flöde, användaren landar rakt i studion. Tas bort/justeras när
 * AUTH_ENABLED slås på.
 */
export const LOGIN_HINT =
  "Konton kommer snart — tills dess landar du direkt i studion" as const;

/**
 * Enda källan till login-målet, så framtida auth (t.ex. /login bakom
 * AUTH_ENABLED) byter på ETT ställe.
 */
export function getLoginHref(): string {
  return AUTH_ENABLED ? "/login" : LOGIN_HREF;
}
