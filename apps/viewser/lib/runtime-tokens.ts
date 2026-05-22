/**
 * runtime-tokens — CSS-token-overrides som operatören kan justera
 * direkt i Site Inspector utan att vänta på en ny build.
 *
 * Flöde i två lager:
 *
 *   1. ALLTID — Live mini-preview inne i TokensTab själv. Ett litet
 *      mock-card renderas med valda färger så operatören ser
 *      visuellt feedback innan hen committar något. Detta fungerar
 *      garanterat i alla browsers.
 *
 *   2. BÄSTA FALL — postMessage till den genererade sajtens runtime-
 *      lyssnare. scripts/build_site.py lägger ett <script> i
 *      layout.tsx som tar emot ``{ type: "sajtbyggaren:set-token",
 *      token, value }`` och anropar
 *      ``document.documentElement.style.setProperty(...)``. Hade vi
 *      lokal preview (same-origin iframe) hade detta fungerat direkt.
 *      För StackBlitz cross-origin är det ett försök som typ ingen
 *      gång blir hörd — men koden är harmless: worst case händer
 *      ingenting, sajten bygger fortfarande normalt på nästa
 *      follow-up.
 *
 *   3. COMMIT — operatören klickar "Använd dessa färger" och vi
 *      skickar en deterministisk prompt till FloatingChat ("Använd
 *      primärfärg #XXX och accentfärg #YYY") som triggar en riktig
 *      build via vanliga pipeline:n.
 *
 * Lager 1 + 3 ger garanterat värde idag; lager 2 är future-proofing.
 */

import type { Dispatch, SetStateAction } from "react";

/**
 * Tokens vi exponerar för operatören. Begränsat till färger som
 * faktiskt påverkar visuell upplevelse — typografi/spacing är
 * variant-styrt och skulle förvirra mer än hjälpa här.
 *
 * Värdena är hex (#RRGGBB). Tailwind/CSS-tokens i den genererade
 * sajten är i HSL-format (för dark-mode-fungering), så builder:n
 * konverterar hex → HSL vid commit. För runtime-preview använder
 * vi hex direkt — modern browsers accepterar båda formatet i
 * ``style.setProperty``.
 */
export type TokenId = "primary" | "accent" | "background" | "foreground";

/**
 * Default-värden om operatören öppnar TokensTab utan att tidigare
 * ha satt tokens. Matchar canonical-sajtens defaults i base.css så
 * preview-cardet visar "nuvarande" första gången tabben öppnas.
 */
export const TOKEN_DEFAULTS: Record<TokenId, string> = {
  primary: "#1a1a1a",
  accent: "#0066ff",
  background: "#ffffff",
  foreground: "#0a0a0a",
};

export const TOKEN_META: Record<TokenId, { label: string; description: string }> = {
  primary: {
    label: "Primärfärg",
    description: "Knappar, länkar och accent-kanter.",
  },
  accent: {
    label: "Accent",
    description: "Sekundära framhävningar — badges, hover-state.",
  },
  background: {
    label: "Bakgrund",
    description: "Huvudbakgrunden för sidor och sektioner.",
  },
  foreground: {
    label: "Text",
    description: "Huvudtextfärg — bör ha hög kontrast mot bakgrund.",
  },
};

/**
 * postMessage-event som builder:s runtime-script lyssnar på. Hålls
 * som konstant så frontend + builder-output använder exakt samma
 * sträng (typo-säkert).
 */
export const TOKEN_MESSAGE_TYPE = "sajtbyggaren:set-token";

export interface TokenMessage {
  type: typeof TOKEN_MESSAGE_TYPE;
  token: TokenId;
  /** Hex-färg ``#RRGGBB`` eller ``"reset"`` för att återställa till canonical. */
  value: string;
}

/**
 * Bredcast en token-override till alla iframes i sidan. Vi anropar
 * postMessage på varje child-iframe utan att veta vilken (om någon)
 * faktiskt lyssnar. Worst case är att inget händer; ingen risk för
 * krasch eftersom postMessage bara serialiserar payloaden och
 * skickar ut den i etern.
 *
 * Vi använder ``"*"`` som target-origin eftersom StackBlitz-iframens
 * exakta URL ändras (preview-tunneln har random subdomain). Detta
 * är OK för read-only style-anrop som denna — vi skickar ingen
 * sensitiv data, bara ett hex-färgvärde.
 */
export function broadcastTokenChange(token: TokenId, value: string): void {
  if (typeof window === "undefined") return;
  const message: TokenMessage = { type: TOKEN_MESSAGE_TYPE, token, value };
  const iframes = document.querySelectorAll("iframe");
  iframes.forEach((iframe) => {
    try {
      iframe.contentWindow?.postMessage(message, "*");
    } catch {
      // contentWindow kan vara null för same-origin-detached iframes
      // eller throw för cross-origin under vissa CSP-policies. Vi
      // ignorerar tyst — TokensTab har redan visuell feedback via
      // mini-preview oavsett.
    }
  });
}

/**
 * Bygg en quick-prompt-text som FloatingChat kan skicka direkt till
 * /api/prompt för att faktiskt committa token-overrides i nästa
 * build. Vi inkluderar bara tokens som skiljer sig från canonical
 * så prompten är så kort + specifik som möjligt.
 */
export function buildTokenCommitPrompt(
  current: Record<TokenId, string>,
  canonical: Record<TokenId, string> = TOKEN_DEFAULTS,
): string {
  const diffs: string[] = [];
  for (const id of Object.keys(current) as TokenId[]) {
    const value = current[id]?.toLowerCase();
    const baseline = canonical[id]?.toLowerCase();
    if (!value || value === baseline) continue;
    diffs.push(`${TOKEN_META[id].label.toLowerCase()} ${value}`);
  }
  if (diffs.length === 0) return "";
  return `Använd följande färger på sajten: ${diffs.join(", ")}.`;
}

/** React state-helpers så hooks-kallaren slipper definiera typer själv. */
export type TokenStateSetter = Dispatch<SetStateAction<Record<TokenId, string>>>;
