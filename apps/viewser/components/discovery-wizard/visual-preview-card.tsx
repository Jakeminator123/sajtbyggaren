"use client";

import type { TypographyFeelId, Vibe } from "./wizard-constants";

/**
 * visual-preview-card — delad rendering-bibliotek för wizardens
 * foundation + visual-steg. Den gemensamma punkten är att båda stegen
 * vill visa SAMMA visuella signaler (vibens swatches, hero-layout-
 * glyph, typografi-känsla) i sina kort. Att lyfta logiken hit
 * garanterar att foundation:s FamilyCard och visual:s VibeCard
 * renderar identiskt mot samma vibe-data (single source of truth).
 *
 * VIKTIGT — alignment: dessa komponenter LÄSER bara från Vibe / WizardAnswers.
 * De ändrar ingen state och driver inget API-anrop. Output:en till
 * backend bestäms uteslutande av wizard-payload.ts → composeMasterPrompt /
 * deriveWizardDirectives, vilka denna fil inte rör.
 */

/**
 * Hero-layout-glyph — mini-SVG i 80×40-box som visar layouten visuellt.
 * Tom sträng = "Auto" (tre prickar). Används både av visual-step:s
 * hero-layout-väljare OCH av foundation-step:s FamilyCard (där vi visar
 * default-vibens hero-känsla utan att operatören valt något själv).
 */
export function HeroLayoutGlyph({
  variant,
  className,
}: {
  variant: "" | "gradient" | "centered" | "split";
  className?: string;
}) {
  const cls = className ?? "text-muted-foreground/60 h-10 w-full";
  if (variant === "centered") {
    return (
      <svg viewBox="0 0 80 40" className={cls} fill="currentColor">
        <rect
          x="0"
          y="0"
          width="80"
          height="40"
          rx="3"
          className="fill-current opacity-10"
        />
        <rect x="22" y="9" width="36" height="3" rx="1.5" />
        <rect x="28" y="16" width="24" height="2" rx="1" className="opacity-50" />
        <rect
          x="30"
          y="22"
          width="20"
          height="4"
          rx="2"
          className="text-foreground fill-current"
        />
      </svg>
    );
  }
  if (variant === "split") {
    return (
      <svg viewBox="0 0 80 40" className={cls} fill="currentColor">
        <rect
          x="0"
          y="0"
          width="80"
          height="40"
          rx="3"
          className="fill-current opacity-10"
        />
        <rect x="6" y="10" width="22" height="3" rx="1.5" />
        <rect x="6" y="16" width="28" height="2" rx="1" className="opacity-50" />
        <rect
          x="6"
          y="22"
          width="16"
          height="4"
          rx="2"
          className="text-foreground fill-current"
        />
        <rect x="44" y="6" width="30" height="28" rx="3" className="opacity-30" />
      </svg>
    );
  }
  if (variant === "gradient") {
    return (
      <svg viewBox="0 0 80 40" className={cls} fill="currentColor">
        <defs>
          <linearGradient id="heroGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.05" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.25" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="80" height="40" rx="3" fill="url(#heroGradient)" />
        <rect x="6" y="12" width="32" height="3" rx="1.5" />
        <rect x="6" y="18" width="44" height="2" rx="1" className="opacity-50" />
        <rect
          x="6"
          y="24"
          width="18"
          height="4"
          rx="2"
          className="text-foreground fill-current"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 80 40" className={cls} fill="currentColor">
      <rect
        x="0"
        y="0"
        width="80"
        height="40"
        rx="3"
        className="fill-current opacity-10"
      />
      <circle cx="30" cy="20" r="3" />
      <circle cx="40" cy="20" r="3" className="opacity-60" />
      <circle cx="50" cy="20" r="3" className="opacity-30" />
    </svg>
  );
}

/**
 * Mini swatch-rad för vibe-color-preview. Visar 2-3 färger som
 * runda chips. Används i FamilyCard (foundation) och ContextChips
 * (visual). När `accent` saknas visas bara primary.
 */
export function VibeSwatchRow({
  primary,
  accent,
  background,
  size = 12,
  className,
}: {
  primary: string;
  accent?: string;
  background?: string;
  size?: number;
  className?: string;
}) {
  const px = `${size}px`;
  return (
    <div className={`flex items-center gap-1 ${className ?? ""}`} aria-hidden>
      <span
        title={`Primary ${primary}`}
        className="border-border/40 rounded-full border"
        style={{ background: primary, width: px, height: px }}
      />
      {accent ? (
        <span
          title={`Accent ${accent}`}
          className="border-border/40 rounded-full border"
          style={{ background: accent, width: px, height: px }}
        />
      ) : null}
      {background ? (
        <span
          title={`Background ${background}`}
          className="border-border/40 rounded-full border"
          style={{ background, width: px, height: px }}
        />
      ) : null}
    </div>
  );
}

/**
 * Plocka en sane font-stack per typografi-känsla. Används bara för
 * preview-rendering i kort — riktiga typsnitt sätts av variant CSS i
 * den genererade sajten.
 */
export function typographyPreviewFamily(feel: TypographyFeelId | ""): string {
  switch (feel) {
    case "classic-serif":
      return "Georgia, 'Times New Roman', serif";
    case "geometric":
      return "'Futura', 'Trebuchet MS', sans-serif";
    case "organic":
      return "'Brush Script MT', 'Snell Roundhand', cursive";
    case "modern-sans":
    case "":
    default:
      return "'Inter', system-ui, -apple-system, sans-serif";
  }
}

/**
 * Returnerar svart eller vitt baserat på bakgrundens upplevda
 * luminance — så texten alltid är läsbar mot vibe-bakgrunden.
 */
export function contrastingTextColor(hex: string): string {
  const cleaned = hex.replace("#", "");
  if (cleaned.length !== 6) return "#0f172a";
  const r = parseInt(cleaned.slice(0, 2), 16);
  const g = parseInt(cleaned.slice(2, 4), 16);
  const b = parseInt(cleaned.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? "#0f172a" : "#fafafa";
}

/**
 * Liten micro-sajt-mock för vibe-preview-kort. Renderar en hero-yta
 * med rubrik + 2 chips + en CTA-knapp, allt målat med variantens
 * tokens. Används av visual-stegets VibeCard och kan återanvändas
 * av foundation-stegets FamilyCard om vi vill visa default-vibens
 * känsla i bredare format. Helt inline (zero HTTP) → renderar
 * instant även med 20 kort på skärmen.
 */
export function VibeMicroPreview({
  vibe,
  heading,
  height = 86,
  showTypography = true,
}: {
  vibe: Pick<
    Vibe,
    "label" | "background" | "primarySwatch" | "accentSwatch" | "defaultTypographyFeel"
  >;
  /** Override-rubrik. Default = vibens egen label. */
  heading?: string;
  height?: number;
  showTypography?: boolean;
}) {
  const textColor = contrastingTextColor(vibe.background);
  const fontStack = typographyPreviewFamily(vibe.defaultTypographyFeel);
  const title = heading ?? vibe.label;
  return (
    <div
      className="relative w-full overflow-hidden"
      style={{ height: `${height}px`, background: vibe.background, color: textColor }}
    >
      <div className="flex h-full flex-col justify-between p-3">
        <div className="flex items-start justify-between gap-2">
          <span
            className="line-clamp-1 text-[12.5px] font-semibold tracking-tight"
            style={{ color: vibe.primarySwatch, fontFamily: fontStack }}
          >
            {title}
          </span>
          {showTypography ? (
            <span
              aria-hidden
              className="rounded-md border px-1.5 py-0.5 font-mono text-[9px]"
              style={{
                color: textColor,
                borderColor: `${textColor}33`,
                fontFamily: fontStack,
              }}
            >
              Aa
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="rounded-md px-1.5 py-0.5 text-[9.5px] font-medium"
            style={{ background: vibe.primarySwatch, color: vibe.background }}
          >
            Boka
          </span>
          <span
            className="rounded-full px-1.5 py-0.5 text-[9px] font-medium"
            style={{ background: `${vibe.accentSwatch}22`, color: vibe.accentSwatch }}
          >
            Nyhet
          </span>
        </div>
      </div>
    </div>
  );
}
