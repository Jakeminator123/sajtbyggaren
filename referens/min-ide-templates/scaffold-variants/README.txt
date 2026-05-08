Detta i denna mapp är enbart varianter, alltså de filer som finns i respektive mapp visar hur respektive
 `scaffold` kan avvika som standard beroende på användarprompten. Detta är endast ett exempel, nota bene.


Jag kommer återkomma till i en beskrivning till hur "Deep Breef" ska "svara på frågor". Osäker på om det är typ såhär som nean, men jag
VILL FRAMFÖLRALLT ATT DU TÄNKER TILL DETTQA ÄR ETT VAGT FÖRSLAG BARA:

: "/**
 * Compact variant summary for Brief-LLM consumption.
 *
 * Used by the "pre-match" step in create-chat-stream-post: a fast,
 * keyword-only scaffold+variant pick that runs *before* brief generation
 * so the Brief-LLM can harmonize its design choices with the variant's
 * defaults (fonts, color mode, motif, curated style rules).
 *
 * The pre-match is a hint — the real scaffold/variant selection runs
 * later in resolveOrchestrationBase / finalizeOrchestrationPrompts with
 * full embedding + brief context.
 */

import type { ScaffoldVariant, ScaffoldVariantThemeTokens } from "./types";
import type { ScaffoldManifest } from "../scaffolds/types";

/**
 * Compact theme-token snapshot passed to Brief-LLM as exact starting values
 * for `visualDirection.colorPalette`. Brief schema uses 5 hex/CSS colors
 * (background/text/primary/secondary/accent), men variantens fulla token-set
 * speglas här så briefen ser hela paletten variant-curatorn valt — annars
 * dyker secondary/muted/card upp som "ifrån luften" i codegen.
 */
export interface VariantThemeTokenHints {
  background?: string;
  foreground?: string;
  card?: string;
  cardForeground?: string;
  primary?: string;
  primaryForeground?: string;
  secondary?: string;
  secondaryForeground?: string;
  muted?: string;
  mutedForeground?: string;
  accent?: string;
  accentForeground?: string;
  border?: string;
  ring?: string;
  radius?: string;
  bodyBackgroundImage?: string;
}

export interface VariantHints {
  scaffoldLabel: string;
  colorMode: string;
  signatureMotif: string;
  fontPairing: string | null;
  /** All available font pairings so brief can pick a secondary if motif demands. */
  fontPairings: Array<{ heading: string; body: string }>;
  promptHints: string[];
  /** 2-3 most distinctive layouts from signaturePatterns (compact for brief). */
  signatureLayouts: string[];
  /** 2 most distinctive motifs from signaturePatterns. */
  signatureMotifs: string[];
  /**
   * Concrete theme tokens (OKLCH / CSS colors) the brief should copy verbatim
   * into `visualDirection.colorPalette` when the user prompt has no explicit
   * color demands. Calibrated per variant — do not "improve".
   */
  themeTokens: VariantThemeTokenHints | null;
}

function pickTokenHints(
  tokens: ScaffoldVariantThemeTokens | undefined,
): VariantThemeTokenHints | null {
  if (!tokens) return null;
  const projected: VariantThemeTokenHints = {};
  if (tokens.background) projected.background = tokens.background;
  if (tokens.foreground) projected.foreground = tokens.foreground;
  if (tokens.card) projected.card = tokens.card;
  if (tokens.cardForeground) projected.cardForeground = tokens.cardForeground;
  if (tokens.primary) projected.primary = tokens.primary;
  if (tokens.primaryForeground) projected.primaryForeground = tokens.primaryForeground;
  if (tokens.secondary) projected.secondary = tokens.secondary;
  if (tokens.secondaryForeground) projected.secondaryForeground = tokens.secondaryForeground;
  if (tokens.muted) projected.muted = tokens.muted;
  if (tokens.mutedForeground) projected.mutedForeground = tokens.mutedForeground;
  if (tokens.accent) projected.accent = tokens.accent;
  if (tokens.accentForeground) projected.accentForeground = tokens.accentForeground;
  if (tokens.border) projected.border = tokens.border;
  if (tokens.ring) projected.ring = tokens.ring;
  if (tokens.radius) projected.radius = tokens.radius;
  if (tokens.bodyBackgroundImage) projected.bodyBackgroundImage = tokens.bodyBackgroundImage;
  return Object.keys(projected).length > 0 ? projected : null;
}

export function buildVariantHintsForBrief(
  scaffold: ScaffoldManifest | null,
  variant: ScaffoldVariant | null,
): VariantHints | null {
  if (!variant) return null;
  return {
    scaffoldLabel: scaffold?.label ?? variant.scaffoldId,
    colorMode: variant.colorMode,
    signatureMotif: variant.signatureMotif,
    fontPairing: variant.fontPairings[0]
      ? `${variant.fontPairings[0].heading} + ${variant.fontPairings[0].body}`
      : null,
    fontPairings: variant.fontPairings.map((p) => ({ heading: p.heading, body: p.body })),
    promptHints: variant.promptHints.slice(0, 3),
    signatureLayouts: variant.signaturePatterns?.layouts.slice(0, 3) ?? [],
    signatureMotifs: variant.signaturePatterns?.motifs.slice(0, 2) ?? [],
    themeTokens: pickTokenHints(variant.themeTokens),
  };
}

export function formatVariantHintsForPrompt(hints: VariantHints): string {
  const lines = [
    "Scaffold variant hint (use as design starting point, adjust when user intent differs):",
    `- Scaffold: ${hints.scaffoldLabel}`,
    `- Color mode: ${hints.colorMode}`,
    `- Signature motif: ${hints.signatureMotif}`,
  ];
  if (hints.fontPairing) lines.push(`- Suggested font pairing: ${hints.fontPairing}`);
  if (hints.fontPairings.length > 1) {
    const alternates = hints.fontPairings
      .slice(1)
      .map((p) => `${p.heading} + ${p.body}`)
      .join(" | ");
    lines.push(`- Alternate font pairings: ${alternates}`);
  }
  if (hints.promptHints.length > 0) lines.push(`- Style cues: ${hints.promptHints.join(", ")}`);
  if (hints.signatureLayouts.length > 0) {
    lines.push(`- Signature layouts: ${hints.signatureLayouts.join(" | ")}`);
  }
  if (hints.signatureMotifs.length > 0) {
    lines.push(`- Signature motifs: ${hints.signatureMotifs.join(" | ")}`);
  }
  if (hints.themeTokens) {
    const t = hints.themeTokens;
    lines.push(
      "- Variant theme tokens (use as EXACT starting values for visualDirection.colorPalette and typography unless the prompt explicitly overrides colors):",
    );
    if (t.background) lines.push(`  - background: ${t.background}`);
    if (t.foreground) lines.push(`  - foreground (text): ${t.foreground}`);
    if (t.card) lines.push(`  - card: ${t.card}`);
    if (t.cardForeground) lines.push(`  - cardForeground: ${t.cardForeground}`);
    if (t.primary) lines.push(`  - primary: ${t.primary}`);
    if (t.primaryForeground) lines.push(`  - primaryForeground: ${t.primaryForeground}`);
    if (t.secondary) lines.push(`  - secondary: ${t.secondary}`);
    if (t.secondaryForeground) lines.push(`  - secondaryForeground: ${t.secondaryForeground}`);
    if (t.muted) lines.push(`  - muted: ${t.muted}`);
    if (t.mutedForeground) lines.push(`  - mutedForeground: ${t.mutedForeground}`);
    if (t.accent) lines.push(`  - accent: ${t.accent}`);
    if (t.accentForeground) lines.push(`  - accentForeground: ${t.accentForeground}`);
    if (t.border) lines.push(`  - border: ${t.border}`);
    if (t.ring) lines.push(`  - ring: ${t.ring}`);
    if (t.radius) lines.push(`  - radius: ${t.radius}`);
    if (t.bodyBackgroundImage) {
      lines.push(`  - bodyBackgroundImage (apply on body in app/globals.css): ${t.bodyBackgroundImage}`);
    }
  }
  return lines.join("\n");
}
"...