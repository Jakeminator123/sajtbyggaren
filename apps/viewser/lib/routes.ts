/**
 * Publika route-konstanter för marknadssajten + bygg-CTA:er. Medvetet
 * client-säker: bara rena href-strängar, ingen server-only-kod. Auth/billing-
 * specifika routes (login/registrera/konto/priser) är parkerade och bor inte
 * här — de återkommer med en egen auth-seam när operatören slår på den ytan.
 *
 * Identifierare på engelska, användarvänd text på svenska (AGENTS.md).
 */

/** Operatörskonsolen (bygg-studion). Alla bygg-CTA:er pekar hit. */
export const STUDIO_HREF = "/studio" as const;
