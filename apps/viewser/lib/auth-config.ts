/**
 * Auth-seam för marknadssajten + konsolen. Sedan juni 2026 finns en RIKTIG,
 * egen inloggning (scrypt + cookie-sessioner + SQLite, se lib/auth/*). Den här
 * filen är medvetet client-säker: bara etiketter/hrefs och en ren funktion som
 * mappar inloggningsstatus → header-entry. Den auktoritativa "vem är inloggad?"
 * -frågan ställs server-side via lib/auth/session.ts (getCurrentUser) och
 * skickas in som ``authed``-prop till headern.
 *
 * Identifierare på engelska, användarvänd text på svenska (AGENTS.md).
 */

/**
 * Auth-ytan (login/registrera/konto/priser + header-entry + Stripe-köp) är en
 * OPT-IN feature bakom env-flaggan ``NEXT_PUBLIC_AUTH_ENABLED``. **Default AV:**
 * i en deploy som inte uttryckligen sätter "true" är auth/billing *dormant
 * groundwork* — sidorna 404:ar, header-entryn + Priser döljs, auth/checkout-API
 * svarar 404, och kärnloopen (`prompt → preview → följdprompt`) påverkas inte.
 * Operatören flippar på den när durable store + claim-token + kreditmätnings-
 * punkt är på plats. `NEXT_PUBLIC_` så samma värde är läsbart både i
 * klient-headern och i server-routes.
 */
export const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

/** Operatörskonsolen (bygg-studion). Bygg-CTA:er pekar hit. */
export const STUDIO_HREF = "/studio" as const;

/** Riktig inloggningssida. "Logga in" i headern går hit. */
export const LOGIN_HREF = "/login" as const;

/** Registreringssida ("Skapa konto"). */
export const REGISTER_HREF = "/registrera" as const;

/** Kontosida (profil, mina sajter, krediter, abonnemang). */
export const ACCOUNT_HREF = "/konto" as const;

export const LOGIN_LABEL = "Logga in" as const;
export const REGISTER_LABEL = "Skapa konto" as const;

/** Etikett + mål när besökaren ÄR inloggad ("Logga in" byts mot detta). */
export const ACCOUNT_LABEL = "Mitt konto" as const;

/**
 * Är besökaren inloggad? Tar emot den server-resolvade statusen (cookie-
 * sessionen läses i lib/auth/session.ts, inte här) och grindar den dessutom
 * bakom AUTH_ENABLED. Hålls som ren funktion så headern kan vara en
 * klientkomponent utan att importera server-only-kod.
 */
export function isAuthenticated(authed: boolean): boolean {
  return AUTH_ENABLED && authed;
}

export type HeaderAuthEntry = {
  href: string;
  label: string;
  hint?: string;
};

/** Header-entry: växlar mellan "Logga in" och "Mitt konto" beroende på auth. */
export function authHeaderEntry(authed: boolean): HeaderAuthEntry {
  return isAuthenticated(authed)
    ? { href: ACCOUNT_HREF, label: ACCOUNT_LABEL }
    : { href: LOGIN_HREF, label: LOGIN_LABEL };
}

/**
 * Är ``next``-parametern en säker, intern redirect-mål? Vi tillåter bara
 * rena interna paths. ``//evil.com`` och ``/\evil`` är protokoll-relativa
 * öppna redirects och måste avvisas (server- och klient-sida delar denna).
 */
export function isSafeNext(next: string | undefined | null): boolean {
  return (
    typeof next === "string" &&
    next.startsWith("/") &&
    !next.startsWith("//") &&
    !next.startsWith("/\\")
  );
}
