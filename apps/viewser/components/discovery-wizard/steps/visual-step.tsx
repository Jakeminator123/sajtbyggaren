"use client";

import { useEffect, useMemo, useRef } from "react";

import { AssetDropzone } from "@/components/discovery-wizard/asset-dropzone";
import type { AssetRef } from "@/lib/asset-store/types";

import { PayloadAlignmentPopover } from "../payload-alignment-popover";
import {
  HeroLayoutGlyph,
  typographyPreviewFamily,
  VibeMicroPreview,
  VibeSwatchRow,
} from "../visual-preview-card";
import {
  BUSINESS_FAMILIES,
  branchForFamily,
  DESIGN_STYLE_OPTIONS,
  findVibe,
  TONE_OPTIONS,
  TYPOGRAPHY_FEEL_OPTIONS,
  type TypographyFeelId,
  type Vibe,
  vibesForScaffold,
} from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import {
  AdvancedDisclosure,
  Chip,
  ChipRow,
  FieldLabel,
  FieldStack,
  HelperText,
  SectionHeader,
  TextField,
  TextareaField,
} from "./step-primitives";

/**
 * VisualStep — wizardens steg 2 (Pass 2: rik vibe-UI).
 *
 * Layout:
 *   1. Vibe-grid (5 stora kort med live-preview, color-swatch och
 *      "Aa"-typografi-skiss).
 *   2. Färgmode (segmented control: vibens defaults vs egna färger)
 *      — färgväljarna visas bara om "egna" är valt.
 *   3. Typografi-känsla (4 chips med visuell preview).
 *   4. Tonarter + designstil-chips.
 *   5. Referensföretag (fritext).
 *   6. Ord att undvika.
 *   7. Mood-bilder (1-3 referensbilder via dropzone) — drivs av samma
 *      /api/upload-asset som assets-step så de hamnar i
 *      `data/uploads/__draft/<assetId>/` och kan användas av Vision-
 *      modellen som inspiration.
 *
 * Auto-default: när operatören valt en BusinessFamily i steg 1 men
 * ännu inte valt vibe, sätts familjens `defaultVariantId` som
 * förvalt vibe (effekt körs en gång per mount).
 */
export function VisualStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  // Bestäm scaffold-hint från family (om vald) eller fall tillbaka till
  // local-service-business som default.
  const family = BUSINESS_FAMILIES.find((f) => f.id === answers.businessFamily);
  const scaffoldHint = family?.scaffoldHint ?? "local-service-business";
  const vibes = useMemo(() => vibesForScaffold(scaffoldHint), [scaffoldHint]);
  const selectedVibe = useMemo(
    () => (answers.vibe.vibeId ? findVibe(answers.vibe.vibeId) : undefined),
    [answers.vibe.vibeId],
  );
  // Preview-rubrik = företagsnamn om ifyllt, annars vibens label —
  // ger operatören en personlig "så här ser det ut för MIN sajt"-känsla
  // när hen har skrivit företagsnamn i foundation.
  const previewHeading = answers.companyName.trim() || undefined;

  // Approximerad rawPrompt för PayloadAlignmentPopover. Vi använder
  // `offer` (= operatörens beskrivning av vad de gör) som proxy för
  // den ursprungliga prompten — det är vad backend själva matar in
  // som första källtext via composeMasterPrompt. Detta gör popoverns
  // language-detection och directives-output realistisk även när den
  // ursprungliga rawPrompt-prop:en inte är tillgänglig i VisualStep.
  const popoverRawPrompt = answers.offer;

  // Auto-defaulta vibe + typography när family väljs men vibe ej satt.
  // Effekten körs en gång per komponent-mount; om operatören aktivt
  // avmarkerat vibe (vibeId = "") så respekterar vi det.
  const autoDefaultRef = useRef(false);
  useEffect(() => {
    if (autoDefaultRef.current) return;
    if (!family) return;
    if (answers.vibe.vibeId) {
      autoDefaultRef.current = true;
      return;
    }
    const defaultVibe = findVibe(family.defaultVariantId);
    if (!defaultVibe) return;
    autoDefaultRef.current = true;
    onChange({
      vibe: {
        ...answers.vibe,
        vibeId: defaultVibe.id,
        typographyFeel:
          answers.vibe.typographyFeel || defaultVibe.defaultTypographyFeel,
      },
    });
    // Vi vill bara köra denna effekt en gång per mount. Family/vibe-id
    // styrs av operatören efter mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectVibe = (vibeId: string) => {
    const next = findVibe(vibeId);
    onChange({
      vibe: {
        ...answers.vibe,
        vibeId: answers.vibe.vibeId === vibeId ? "" : vibeId,
        // Auto-applicera vibens default-typografi om operatören inte
        // valt något själv.
        typographyFeel:
          answers.vibe.typographyFeel ||
          (next ? next.defaultTypographyFeel : ""),
      },
    });
  };

  const setTypographyFeel = (feel: TypographyFeelId) => {
    onChange({
      vibe: {
        ...answers.vibe,
        typographyFeel: answers.vibe.typographyFeel === feel ? "" : feel,
      },
    });
  };

  const setUseCustomColors = (use: boolean) => {
    onChange({ vibe: { ...answers.vibe, useCustomColors: use } });
  };

  const toggleTone = (label: string) => {
    const set = new Set(answers.brand.toneTags);
    if (set.has(label)) set.delete(label);
    else set.add(label);
    onChange({ brand: { ...answers.brand, toneTags: Array.from(set) } });
  };

  const setDesignStyle = (label: string) => {
    onChange({
      brand: {
        ...answers.brand,
        designStyle: answers.brand.designStyle === label ? "" : label,
      },
    });
  };

  const removeMoodImage = (assetId: string) => {
    onChange({
      moodImages: answers.moodImages.filter((img) => img.assetId !== assetId),
    });
  };

  const addMoodImages = (refs: AssetRef[]) => {
    // Begränsa till totalt 5 för att hålla payloaden hanterbar.
    const merged = [...answers.moodImages, ...refs].slice(0, 5);
    onChange({ moodImages: merged });
  };

  // Räkna ifyllda advanced-fält så badge:n visar progress.
  const advancedFilled =
    (answers.vibe.useCustomColors ? 1 : 0) +
    (answers.vibe.typographyFeel ? 1 : 0) +
    (answers.brand.designStyle ? 1 : 0) +
    (answers.vibe.layoutHint ? 1 : 0) +
    (answers.vibe.references.trim() ? 1 : 0) +
    (answers.brand.wordsToAvoid.trim() ? 1 : 0) +
    (answers.moodImages.length > 0 ? 1 : 0);

  return (
    <FieldStack>
      {/* CONTEXT-CHIPS — visar vad foundation har lett till (family →
          scaffold → default-vibe). Operatören ser direkt vilka steg-1-
          beslut som styr vad hen ser här. */}
      {family ? (
        <ContextChips
          familyLabel={family.label}
          scaffoldHint={family.scaffoldHint}
          defaultVibe={findVibe(family.defaultVariantId)?.label ?? family.defaultVariantId}
          selectedVibeLabel={selectedVibe?.label}
        />
      ) : null}

      {/* ESSENTIALS — vibe + tonarter ger 90% av personlighet. */}
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <SectionHeader>Vibe</SectionHeader>
            <HelperText>
              Välj den känsla som passar bäst — vibe styr färger, typografi och
              spacing automatiskt. Listan filtreras efter din verksamhetsfamilj
              {family ? ` (${family.label})` : ""} och branch
              {family ? ` (${branchForFamily(family.id)})` : ""}.
            </HelperText>
          </div>
          <PayloadAlignmentPopover
            answers={answers}
            rawPrompt={popoverRawPrompt}
          />
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {vibes.map((vibe) => (
            <VibeCard
              key={vibe.id}
              vibe={vibe}
              selected={answers.vibe.vibeId === vibe.id}
              onSelect={() => selectVibe(vibe.id)}
              previewHeading={previewHeading}
            />
          ))}
        </div>
        {vibes.length === 0 ? (
          <p className="text-muted-foreground mt-3 text-[12px]">
            Inga vibes för denna scaffold — välj en verksamhetsfamilj i steg 1.
          </p>
        ) : null}
      </div>

      <div>
        <SectionHeader>Tonarter</SectionHeader>
        <HelperText>
          Hur ska texten på sajten kännas? Välj en eller flera.
        </HelperText>
        <div className="mt-2">
          <ChipRow>
            {TONE_OPTIONS.map((tone) => (
              <Chip
                key={tone}
                label={tone}
                selected={answers.brand.toneTags.includes(tone)}
                onToggle={() => toggleTone(tone)}
              />
            ))}
          </ChipRow>
        </div>
      </div>

      {/* ADVANCED — färger, typografi, designstil, hero-layout, referenser,
       *   ord att undvika, mood-bilder. Vibe sätter intelligenta defaults
       *   för allt nedanför så de flesta operatörer behöver aldrig öppna. */}
      <AdvancedDisclosure
        id="visual-advanced"
        label="Designdetaljer"
        hint="Vibe sätter rimliga defaults. Öppna bara om du vill överstyra färger, typografi-känsla, hero-layout eller lägga in referenser/mood-bilder."
        count={7}
        activeCount={advancedFilled}
      >
      {/* Färgvalsläge. */}
      <div>
        <SectionHeader>Färger</SectionHeader>
        <HelperText>
          Vibens defaults är handvalda — välj egna färger bara om ni har en
          stark brand-identitet ni vill bevara.
        </HelperText>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => setUseCustomColors(false)}
            aria-pressed={!answers.vibe.useCustomColors}
            className={[
              "flex-1 rounded-lg border px-3 py-2 text-left text-[12px] transition-colors",
              !answers.vibe.useCustomColors
                ? "border-foreground bg-foreground/[0.04]"
                : "border-border/70 hover:border-foreground/40",
            ].join(" ")}
          >
            <span className="text-foreground font-medium">
              Använd vibens defaults
            </span>
            <span className="text-muted-foreground ml-1 text-[11px]">
              (rekommenderas)
            </span>
          </button>
          <button
            type="button"
            onClick={() => setUseCustomColors(true)}
            aria-pressed={answers.vibe.useCustomColors}
            className={[
              "flex-1 rounded-lg border px-3 py-2 text-left text-[12px] transition-colors",
              answers.vibe.useCustomColors
                ? "border-foreground bg-foreground/[0.04]"
                : "border-border/70 hover:border-foreground/40",
            ].join(" ")}
          >
            <span className="text-foreground font-medium">
              Välj egna färger
            </span>
            <span className="text-muted-foreground ml-1 text-[11px]">
              (skriver över vibens)
            </span>
          </button>
        </div>
        {answers.vibe.useCustomColors ? (
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <FieldLabel optional>Primärfärg (hex)</FieldLabel>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={answers.brand.primaryColorHex || "#0f172a"}
                  onChange={(event) =>
                    onChange({
                      brand: {
                        ...answers.brand,
                        primaryColorHex: event.target.value,
                      },
                    })
                  }
                  className="border-border h-9 w-12 cursor-pointer rounded-md border bg-transparent"
                />
                <TextField
                  label=""
                  value={answers.brand.primaryColorHex}
                  onChange={(value) =>
                    onChange({
                      brand: { ...answers.brand, primaryColorHex: value },
                    })
                  }
                  placeholder="#0f172a"
                />
              </div>
            </div>
            <div>
              <FieldLabel optional>Accentfärg (hex)</FieldLabel>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={answers.brand.accentColorHex || "#f59e0b"}
                  onChange={(event) =>
                    onChange({
                      brand: {
                        ...answers.brand,
                        accentColorHex: event.target.value,
                      },
                    })
                  }
                  className="border-border h-9 w-12 cursor-pointer rounded-md border bg-transparent"
                />
                <TextField
                  label=""
                  value={answers.brand.accentColorHex}
                  onChange={(value) =>
                    onChange({
                      brand: { ...answers.brand, accentColorHex: value },
                    })
                  }
                  placeholder="#f59e0b"
                />
              </div>
            </div>
            <p className="text-muted-foreground text-[11px] sm:col-span-2">
              Tips: dina hex-värden skrivs in i Project Input men kräver
              backend-stöd (Gap 1 i <code>docs/backend-handoff.md</code>) för
              att faktiskt skriva över vibens defaultfärger.
            </p>
          </div>
        ) : null}
      </div>

      {/* 3. Typografi-känsla. */}
      <div>
        <SectionHeader>Typografi-känsla</SectionHeader>
        <HelperText>
          Avgör om typsnittet ska kännas tidlöst, klassiskt, geometriskt eller
          organiskt.
        </HelperText>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {TYPOGRAPHY_FEEL_OPTIONS.map((option) => {
            const isSelected = answers.vibe.typographyFeel === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setTypographyFeel(option.id)}
                aria-pressed={isSelected}
                className={[
                  "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                  isSelected
                    ? "border-foreground bg-foreground/[0.04]"
                    : "border-border/70 hover:border-foreground/40",
                ].join(" ")}
              >
                <span
                  aria-hidden
                  className={[
                    "text-foreground inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border",
                    isSelected
                      ? "border-foreground bg-foreground/5"
                      : "border-border/70 bg-card",
                  ].join(" ")}
                  style={{
                    fontFamily: typographyPreviewFamily(option.id),
                    fontWeight: option.id === "geometric" ? 600 : 500,
                  }}
                >
                  Aa
                </span>
                <span className="flex flex-1 flex-col leading-tight">
                  <span className="text-foreground text-[12.5px] font-medium tracking-tight">
                    {option.label}
                  </span>
                  <span className="text-muted-foreground mt-0.5 text-[11px] leading-snug">
                    {option.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Designstil (fallback om vibe ej valts). */}
      <div>
        <SectionHeader>Designstil (fallback om vibe ej valts)</SectionHeader>
        <ChipRow>
          {DESIGN_STYLE_OPTIONS.map((style) => (
            <Chip
              key={style}
              label={style}
              selected={answers.brand.designStyle === style}
              onToggle={() => setDesignStyle(style)}
            />
          ))}
        </ChipRow>
      </div>

      {/* 5. Hero-layout (operator-override, valfritt). */}
      <div>
        <SectionHeader>Hero-layout (valfritt)</SectionHeader>
        <HelperText>
          Vill du överstyra automat-valet? Annars härleder vi layouten från
          din vibe (varma vibes blir centrerade, editorial blir split, etc).
          Skickas som <code>directives.layoutHint</code> till backend.
        </HelperText>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            { id: "" as const, label: "Auto", description: "Härled från vibe" },
            { id: "gradient" as const, label: "Gradient", description: "Klassisk, vänsterstaplad" },
            { id: "centered" as const, label: "Centrerat", description: "Lugnt, editorialt" },
            { id: "split" as const, label: "Split", description: "Text + bild eller blob" },
          ].map((option) => {
            const isSelected = answers.vibe.layoutHint === option.id;
            return (
              <button
                key={option.id || "auto"}
                type="button"
                onClick={() =>
                  onChange({
                    vibe: { ...answers.vibe, layoutHint: option.id },
                  })
                }
                aria-pressed={isSelected}
                className={[
                  "flex flex-col gap-2 rounded-lg border p-3 text-left transition-colors",
                  isSelected
                    ? "border-foreground bg-foreground/[0.04]"
                    : "border-border/70 hover:border-foreground/40",
                ].join(" ")}
              >
                <span aria-hidden className="block">
                  <HeroLayoutGlyph variant={option.id} />
                </span>
                <span className="flex flex-col leading-tight">
                  <span className="text-foreground text-[12.5px] font-medium tracking-tight">
                    {option.label}
                  </span>
                  <span className="text-muted-foreground mt-0.5 text-[11px] leading-snug">
                    {option.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 6. Referenser. */}
      <TextField
        label="Referenser ('tänk lite som…')"
        optional
        value={answers.vibe.references}
        onChange={(value) =>
          onChange({ vibe: { ...answers.vibe, references: value } })
        }
        placeholder="t.ex. apple.com, gant.se, en lokal kollega"
        helper="Vi använder detta som inspiration när vi skriver copy och väljer stil."
      />

      {/* 6. Ord att undvika. */}
      <TextareaField
        label="Ord och uttryck att undvika"
        optional
        value={answers.brand.wordsToAvoid}
        onChange={(value) =>
          onChange({ brand: { ...answers.brand, wordsToAvoid: value } })
        }
        placeholder="t.ex. 'världsbäst', 'revolutionerande', branschjargong vi tycker är slitet"
        rows={2}
        helper="Komma-separerad lista. Skickas till copy-modellen som tone.avoid[] så den undviker dessa formuleringar i all text."
      />

      {/* 7. Mood-bilder. */}
      <div>
        <SectionHeader>Mood-bilder (valfritt)</SectionHeader>
        <HelperText>
          1–5 referensbilder för stämning/färg. Används som inspiration — syns
          inte på sajten. Spara filer du gillar från Pinterest, andra sajter,
          eller egna foton.
        </HelperText>
        {answers.moodImages.length > 0 ? (
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {answers.moodImages.map((img) => (
              <MoodThumbnail
                key={img.assetId}
                asset={img}
                onRemove={() => removeMoodImage(img.assetId)}
              />
            ))}
          </div>
        ) : null}
        {answers.moodImages.length < 5 ? (
          <div className="mt-3">
            <AssetDropzone
              role="gallery"
              mode="multi"
              emptyLabel="Släpp mood-bilder här (max 5)"
              hintLabel="JPG, PNG eller WebP. Stora bilder är OK — vi optimerar dem."
              onUploaded={addMoodImages}
            />
          </div>
        ) : null}
      </div>
      </AdvancedDisclosure>
    </FieldStack>
  );
}

/**
 * VibeCard — rikt vibe-val-kort med micro-sajt-preview i Front 2.
 *
 * Visar (a) en VibeMicroPreview-mock med hero-rubrik + chips + Aa-glyph
 * (b) en swatch-rad med primary/accent/background, (c) vibens beskrivning.
 * Större (~140px) än det gamla text-band-kortet (~70px) så operatören
 * direkt ser känslan istället för att läsa en text-beskrivning.
 *
 * `previewHeading` används istället för vibens label om operatören har
 * skrivit ett företagsnamn i foundation-steget — vilket gör preview:n
 * personlig ("Ateljé Bird" istället för "Warm Craft").
 */
function VibeCard({
  vibe,
  selected,
  onSelect,
  previewHeading,
}: {
  vibe: Vibe;
  selected: boolean;
  onSelect: () => void;
  previewHeading?: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={[
        "group relative overflow-hidden rounded-xl border text-left transition-all",
        selected
          ? "border-foreground ring-foreground/10 shadow-md ring-2"
          : "border-border/70 hover:border-foreground/40 hover:shadow-sm",
      ].join(" ")}
    >
      <VibeMicroPreview vibe={vibe} heading={previewHeading} />
      <div className="bg-card flex flex-col gap-1.5 px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-foreground text-[12.5px] font-semibold tracking-tight">
            {vibe.label}
          </span>
          <VibeSwatchRow
            primary={vibe.primarySwatch}
            accent={vibe.accentSwatch}
            background={vibe.background}
            size={10}
          />
        </div>
        <p className="text-muted-foreground line-clamp-2 text-[11px] leading-snug">
          {vibe.description}
        </p>
      </div>
    </button>
  );
}

/**
 * ContextChips — visas högst upp i visual-steget. Berättar för
 * operatören vilka foundation-beslut som styr vibe-listan, scaffold-
 * mapping och default-vibe. Den enda "klickbara" effekten i denna
 * iteration är hover-tooltip — själva navigeringen tillbaka till
 * foundation sker via sidebar i wizardens chrome. Här fokuserar vi
 * på TRANSPARENS, inte navigation, så operatören INSTANT förstår
 * varför just dessa vibes visas.
 */
function ContextChips({
  familyLabel,
  scaffoldHint,
  defaultVibe,
  selectedVibeLabel,
}: {
  familyLabel: string;
  scaffoldHint: string;
  defaultVibe: string;
  selectedVibeLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <ContextChip label="Family" value={familyLabel} />
      <span className="text-muted-foreground/60 text-[10px]">→</span>
      <ContextChip label="Scaffold" value={scaffoldHint} mono />
      <span className="text-muted-foreground/60 text-[10px]">→</span>
      <ContextChip
        label={selectedVibeLabel ? "Vibe" : "Default-vibe"}
        value={selectedVibeLabel ?? defaultVibe}
        emphasis={!!selectedVibeLabel}
      />
    </div>
  );
}

function ContextChip({
  label,
  value,
  mono,
  emphasis,
}: {
  label: string;
  value: string;
  mono?: boolean;
  emphasis?: boolean;
}) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px]",
        emphasis
          ? "border-foreground/40 bg-foreground/[0.04] text-foreground"
          : "border-border/60 bg-muted/40 text-muted-foreground",
      ].join(" ")}
      title={`${label}: ${value}`}
    >
      <span className="font-mono text-[9px] tracking-[0.18em] uppercase opacity-70">
        {label}
      </span>
      <span
        className={
          mono
            ? "text-foreground font-mono text-[10.5px]"
            : "text-foreground font-medium"
        }
      >
        {value}
      </span>
    </span>
  );
}

function MoodThumbnail({
  asset,
  onRemove,
}: {
  asset: AssetRef;
  onRemove: () => void;
}) {
  return (
    <div className="border-border/60 group bg-muted/30 relative aspect-square overflow-hidden rounded-md border">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/api/asset-preview?assetId=${asset.assetId}&siteId=__draft`}
        alt={asset.alt || asset.filename}
        className="h-full w-full object-cover"
      />
      <button
        type="button"
        onClick={onRemove}
        aria-label="Ta bort mood-bild"
        className="absolute top-1 right-1 inline-flex h-5 w-5 items-center justify-center rounded-full bg-black/70 text-[10px] font-bold text-white opacity-0 transition-opacity group-hover:opacity-100"
      >
        ×
      </button>
    </div>
  );
}
