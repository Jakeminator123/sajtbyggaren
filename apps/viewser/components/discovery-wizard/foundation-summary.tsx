"use client";

import {
  Boxes,
  Layers,
  PaintBucket,
  Sparkles,
  Type,
  Workflow,
} from "lucide-react";

import {
  BUSINESS_FAMILIES,
  branchForFamily,
  findVibe,
  RECOMMENDED_FUNCTIONS_BY_FAMILY,
  type BusinessFamilyId,
} from "./wizard-constants";
import {
  contrastingTextColor,
  typographyPreviewFamily,
  VibeSwatchRow,
} from "./visual-preview-card";

/**
 * FoundationSummary — visas i foundation-steget när operatören har valt
 * en BusinessFamily OCH skrivit en offer-text. Panelen är en transparens-
 * vy som direkt avslöjar vilka beslut backend kommer att fatta baserat
 * på operatorens val ENDAST i steg 1, så hen ser värdet av sina val
 * innan hen klickat sig vidare.
 *
 * ALIGNMENT: alla värden härleds från
 *   - BUSINESS_FAMILIES (samma källa som wizard-payload.ts:buildDiscoveryPayload)
 *   - findVibe (samma källa som visual-step + composeMasterPrompt)
 *   - branchForFamily (samma källa som wizard-payload.ts:buildDiscoveryPayload)
 *   - RECOMMENDED_FUNCTIONS_BY_FAMILY (samma källa som functions-step)
 *
 * Inga nya WizardAnswers-fält, ingen ny backend-kommunikation. Vad
 * operatören ser HÄR är exakt vad backend kommer få via directives
 * när hen klickar "Skapa sajt" (förutsatt att hen inte överstyr i
 * senare steg).
 */
export function FoundationSummary({
  businessFamily,
  companyName,
  offer,
}: {
  businessFamily: BusinessFamilyId | "";
  companyName: string;
  offer: string;
}) {
  if (!businessFamily) return null;
  if (!offer.trim()) return null;
  const family = BUSINESS_FAMILIES.find((f) => f.id === businessFamily);
  if (!family) return null;
  const vibe = findVibe(family.defaultVariantId);
  if (!vibe) return null;

  const branch = branchForFamily(businessFamily);
  const recommendedFunctionCount =
    RECOMMENDED_FUNCTIONS_BY_FAMILY[businessFamily]?.length ?? 0;
  const fontStack = typographyPreviewFamily(vibe.defaultTypographyFeel);
  const previewTitle = companyName.trim() || family.label;

  return (
    <section
      aria-labelledby="foundation-summary-heading"
      className="border-border/60 bg-card mt-2 overflow-hidden rounded-2xl border"
    >
      {/* Hero-band: speglar vibens hero-känsla med titel + företagsnamn. */}
      <div
        className="relative flex items-end justify-between gap-3 px-5 py-4"
        style={{
          background: vibe.background,
          color: contrastingTextColor(vibe.background),
        }}
      >
        <div className="min-w-0 flex-1">
          <p
            id="foundation-summary-heading"
            className="font-mono text-[9.5px] tracking-[0.22em] uppercase"
            style={{ opacity: 0.7 }}
          >
            Så här tolkar vi dina val
          </p>
          <p
            className="mt-1 line-clamp-1 text-[16px] font-semibold tracking-tight"
            style={{ color: vibe.primarySwatch, fontFamily: fontStack }}
          >
            {previewTitle}
          </p>
          <p
            className="line-clamp-1 text-[11.5px] leading-snug opacity-80"
            style={{ fontFamily: fontStack }}
          >
            {family.label}
          </p>
        </div>
        <VibeSwatchRow
          primary={vibe.primarySwatch}
          accent={vibe.accentSwatch}
          background={vibe.background}
          size={14}
        />
      </div>

      {/* Detalj-rader: vad backend faktiskt får i directives. */}
      <dl className="divide-border/40 grid grid-cols-1 divide-y sm:grid-cols-2 sm:divide-x sm:divide-y-0">
        <SummaryRow
          icon={Boxes}
          label="Scaffold"
          value={family.scaffoldHint}
          mono
        />
        <SummaryRow
          icon={Layers}
          label="Branch"
          value={branch}
          mono
        />
        <SummaryRow
          icon={PaintBucket}
          label="Default-vibe"
          value={vibe.label}
        />
        <SummaryRow
          icon={Type}
          label="Typografi"
          value={typographyLabel(vibe.defaultTypographyFeel)}
        />
        <SummaryRow
          icon={Workflow}
          label="Förvalda funktioner"
          value={
            recommendedFunctionCount > 0
              ? `${recommendedFunctionCount} st`
              : "Ingen"
          }
        />
        <SummaryRow
          icon={Sparkles}
          label="Sub-kategorier"
          value={`${family.subCategories.length} möjliga`}
        />
      </dl>
    </section>
  );
}

function SummaryRow({
  icon: Icon,
  label,
  value,
  mono,
}: {
  icon: typeof Boxes;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5 px-4 py-2.5">
      <Icon className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
      <div className="flex min-w-0 flex-1 items-baseline justify-between gap-3">
        <dt className="text-muted-foreground text-[11px]">{label}</dt>
        <dd
          className={
            mono
              ? "text-foreground truncate font-mono text-[11px]"
              : "text-foreground truncate text-[12px] font-medium"
          }
          title={value}
        >
          {value}
        </dd>
      </div>
    </div>
  );
}

function typographyLabel(feel: string): string {
  switch (feel) {
    case "modern-sans":
      return "Modern sans";
    case "classic-serif":
      return "Klassisk serif";
    case "geometric":
      return "Geometrisk";
    case "organic":
      return "Organisk";
    default:
      return feel || "—";
  }
}
