"use client";

import { Globe, Info, Settings2, Square, Video, X } from "lucide-react";
import { useState } from "react";

import { AssetDropzone } from "@/components/discovery-wizard/asset-dropzone";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { ContentOrchestratorStep } from "./steps/content-orchestrator";
import {
  AdvancedDisclosure,
  ChipRow,
  Chip,
  FieldStack,
  TextField,
  TextareaField,
} from "./steps/step-primitives";
import { CTA_OPTIONS } from "./wizard-constants";
import type { ContentBranch } from "./wizard-constants";
import type { WizardAnswers, WizardMedia } from "./wizard-types";

/**
 * MoreInfoDialog \u2014 popup som \u00f6ppnas fr\u00e5n "Ange information"-knappen
 * p\u00e5 tab 3 (Funktioner). Fyra flikar h\u00f6gst upp s\u00e5 alla djupare f\u00e4lt
 * f\u00e5r yta utan att huvud-wizarden blir r\u00f6rig:
 *
 *   - Inneh\u00e5ll \u2014 ContentOrchestratorStep (branch-aware: produkter, meny,
 *     tj\u00e4nster, team, projekt) + om-/historia-/vision-/m\u00e5lgruppstexter.
 *   - Kontakt \u2014 telefon, e-post, adress, \u00f6ppettider.
 *   - Bilder & media \u2014 favicon, OG-bild, bakgrundsvideo. Logo + hero +
 *     galleri ligger fortfarande p\u00e5 tab 3 (functions) som AssetsStep.
 *   - Avancerat \u2014 USP:er, prim\u00e4r CTA, special\u00f6nskem\u00e5l, ord att undvika.
 *
 * Backend-payload p\u00e5verkas inte \u2014 alla f\u00e4lt skrivs till samma
 * `WizardAnswers`-objekt som `buildDiscoveryPayload` redan l\u00e4ser.
 */

type MoreInfoTabId = "content" | "contact" | "media" | "advanced";

const TABS: ReadonlyArray<{
  id: MoreInfoTabId;
  label: string;
}> = [
  { id: "content", label: "Inneh\u00e5ll" },
  { id: "contact", label: "Kontakt" },
  { id: "media", label: "Media" },
  { id: "advanced", label: "Avancerat" },
];

export type MoreInfoDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  branch: ContentBranch;
};

export function MoreInfoDialog({
  open,
  onOpenChange,
  answers,
  onChange,
  branch,
}: MoreInfoDialogProps) {
  const [activeTab, setActiveTab] = useState<MoreInfoTabId>("content");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="border-border/60 bg-background grid h-[min(100dvh-3rem,720px)] !w-[min(100vw-2rem,960px)] !max-w-[min(100vw-2rem,960px)] grid-rows-[auto_auto_1fr_auto] gap-0 overflow-hidden border p-0 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] sm:!max-w-[min(100vw-2rem,960px)] sm:rounded-3xl"
        showCloseButton={false}
      >
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="St\u00e4ng"
          className="text-muted-foreground hover:bg-foreground/5 hover:text-foreground min-tap sm:min-tap-0 absolute top-3 right-3 z-10 inline-flex items-center justify-center rounded-full transition-colors active:scale-95 sm:top-4 sm:right-4 sm:h-8 sm:w-8"
        >
          <X className="h-4 w-4" />
        </button>

        <DialogHeader className="space-y-0 px-5 pt-5 pb-3 text-left sm:px-8 sm:pt-6 sm:pb-3">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <DialogTitle className="text-foreground text-[16px] leading-tight font-semibold tracking-tight sm:text-[17px]">
              Mer information
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-[12.5px] leading-relaxed">
              Detaljer fr\u00e5n din nuvarande hemsida fylls i automatiskt. Allt \u00e4r valfritt.
            </DialogDescription>
          </div>
        </DialogHeader>

        <div
          role="tablist"
          aria-label="Mer information-flikar"
          className="border-border/60 flex w-full items-stretch gap-0 border-b px-5 sm:px-8"
        >
          {TABS.map((tab) => {
            const isActive = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                className={[
                  "min-tap sm:min-tap-0 relative -mb-px inline-flex flex-1 items-center justify-center gap-1.5 border-b-2 px-3 py-2.5 text-[12.5px] font-medium tracking-tight transition-colors sm:flex-none sm:justify-start sm:px-4",
                  isActive
                    ? "text-foreground border-foreground"
                    : "text-muted-foreground hover:text-foreground border-transparent",
                ].join(" ")}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-8 sm:py-6">
          <div className="mx-auto max-w-2xl">
            {activeTab === "content" ? (
              <ContentOrchestratorStep
                answers={answers}
                onChange={onChange}
                branch={branch}
              />
            ) : null}
            {activeTab === "contact" ? (
              <ContactBlock answers={answers} onChange={onChange} />
            ) : null}
            {activeTab === "media" ? (
              <MediaExtrasBlock answers={answers} onChange={onChange} />
            ) : null}
            {activeTab === "advanced" ? (
              <AdvancedBlock answers={answers} onChange={onChange} />
            ) : null}
          </div>
        </div>

        <div className="border-border/60 bg-background/95 flex items-center justify-end gap-2 border-t px-4 py-3 pb-safe-or-4 sm:px-6 sm:py-4">
          <Button
            type="button"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="bg-foreground text-background hover:bg-foreground/90 min-tap sm:min-tap-0 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm"
          >
            Klar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Telefon, e-post, adress, \u00f6ppettider. Tidigare i foundation-step. */
function ContactBlock({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const updateContact = (field: keyof WizardAnswers["contact"], value: string) => {
    onChange({ contact: { ...answers.contact, [field]: value } });
  };
  return (
    <FieldStack>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextField
          label="Telefon"
          type="tel"
          optional
          value={answers.contact.phone}
          onChange={(value) => updateContact("phone", value)}
          placeholder="08-123 45 67"
        />
        <TextField
          label="E-post"
          type="email"
          optional
          value={answers.contact.email}
          onChange={(value) => updateContact("email", value)}
          placeholder="hej@dittforetag.se"
        />
        <TextField
          label="Adress"
          optional
          value={answers.contact.address}
          onChange={(value) => updateContact("address", value)}
          placeholder="Storgatan 1, 111 22 Stockholm"
        />
        <TextField
          label="\u00d6ppettider"
          optional
          value={answers.contact.openingHours}
          onChange={(value) => updateContact("openingHours", value)}
          placeholder="M\u00e5n\u2013Fre 09\u201317"
        />
      </div>
    </FieldStack>
  );
}

/**
 * Subset av MediaStep \u2014 bara favicon + OG-bild + bakgrundsvideo. Logo,
 * hero och galleri ligger p\u00e5 tab 3 (functions) i huvud-wizarden, s\u00e5 vi
 * dubblerar inte dem h\u00e4r.
 */
function MediaExtrasBlock({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const updateMedia = (mutator: (current: WizardMedia) => WizardMedia) => {
    onChange({ media: mutator(answers.media) });
  };

  return (
    <FieldStack>
      <p className="text-muted-foreground/85 flex items-start gap-2 text-[12px] leading-relaxed">
        <Info className="text-muted-foreground/60 mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span>
          L\u00e4mna tomt och vi genererar favicon fr\u00e5n monogrammet och OG-bild fr\u00e5n din brand-f\u00e4rg. Bakgrundsvideo \u00e4r ren bonus.
        </span>
      </p>

      <MediaCard
        icon={<Square className="h-4 w-4" />}
        title="Favicon"
        description="Ikonen i browser-fliken."
      >
        {answers.media.favicon ? (
          <div className="border-border/60 bg-background flex items-center gap-3 rounded-md border px-3 py-2">
            <span className="text-foreground/80 truncate text-[12px]">
              {answers.media.favicon.filename}
            </span>
            <button
              type="button"
              onClick={() => updateMedia((m) => ({ ...m, favicon: null }))}
              className="text-muted-foreground hover:text-foreground ml-auto shrink-0 text-[11px]"
            >
              Ta bort
            </button>
          </div>
        ) : (
          <AssetDropzone
            role="favicon"
            mode="single"
            emptyLabel="Sl\u00e4pp favicon h\u00e4r"
            hintLabel="Kvadratisk PNG eller SVG, minst 256\u00d7256 px."
            onUploaded={(refs) => {
              const next = refs[0];
              if (next) updateMedia((m) => ({ ...m, favicon: next }));
            }}
          />
        )}
      </MediaCard>

      <MediaCard
        icon={<Globe className="h-4 w-4" />}
        title="OG-bild"
        description="Social f\u00f6rhandsvisning (Facebook, LinkedIn, SMS)."
      >
        {answers.media.ogImage ? (
          <div className="border-border/60 bg-background flex items-center gap-3 rounded-md border px-3 py-2">
            <span className="text-foreground/80 truncate text-[12px]">
              {answers.media.ogImage.filename}
            </span>
            <button
              type="button"
              onClick={() => updateMedia((m) => ({ ...m, ogImage: null }))}
              className="text-muted-foreground hover:text-foreground ml-auto shrink-0 text-[11px]"
            >
              Ta bort
            </button>
          </div>
        ) : (
          <AssetDropzone
            role="ogImage"
            mode="single"
            emptyLabel="Sl\u00e4pp social-image h\u00e4r"
            hintLabel="Liggande bild \u2014 vi croppar till 1200\u00d7630."
            onUploaded={(refs) => {
              const next = refs[0];
              if (next) updateMedia((m) => ({ ...m, ogImage: next }));
            }}
          />
        )}
      </MediaCard>

      <MediaCard
        icon={<Video className="h-4 w-4" />}
        title="Bakgrundsvideo"
        description="Loop bakom hero-texten. Hero-bilden visas som fallback."
      >
        {answers.media.backgroundVideo ? (
          <div className="border-border/60 bg-background flex items-center gap-3 rounded-md border px-3 py-2">
            <span className="text-foreground/80 truncate text-[12px]">
              {answers.media.backgroundVideo.filename}
            </span>
            <button
              type="button"
              onClick={() =>
                updateMedia((m) => ({ ...m, backgroundVideo: null }))
              }
              className="text-muted-foreground hover:text-foreground ml-auto shrink-0 text-[11px]"
            >
              Ta bort
            </button>
          </div>
        ) : (
          <AssetDropzone
            role="backgroundVideo"
            mode="single"
            emptyLabel="Sl\u00e4pp video h\u00e4r (.mp4 / .webm)"
            hintLabel="5\u201315 sekunder, max ~50 MB."
            onUploaded={(refs) => {
              const next = refs[0];
              if (next) updateMedia((m) => ({ ...m, backgroundVideo: next }));
            }}
          />
        )}
      </MediaCard>
    </FieldStack>
  );
}

/**
 * Avancerade brand-/copy-f\u00e4lt. F\u00e4lten finns redan i WizardAnswers; vi
 * skickar dem vidare till `buildDiscoveryPayload` p\u00e5 samma s\u00e4tt som
 * f\u00f6rut \u2014 popupen \u00e4ndrar bara HUR operat\u00f6ren matar in dem.
 */
function AdvancedBlock({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const updateBrand = (
    field: keyof WizardAnswers["brand"],
    value: string,
  ) => {
    onChange({ brand: { ...answers.brand, [field]: value } });
  };
  return (
    <FieldStack>
      <p className="text-muted-foreground/85 flex items-start gap-2 text-[12px] leading-relaxed">
        <Settings2 className="text-muted-foreground/60 mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span>
          Finjustering f\u00f6r operat\u00f6rer som vill ha exakt kontroll. Tom f\u00e4lt \u2014 backend l\u00f6ser det sj\u00e4lv.
        </span>
      </p>

      <TextField
        label="Prim\u00e4r CTA"
        optional
        value={answers.primaryCta}
        onChange={(value) => onChange({ primaryCta: value })}
        placeholder="t.ex. Boka m\u00f6te, Hitta hit, Kontakta oss"
      />
      <div>
        <span className="text-muted-foreground mb-2 inline-flex font-mono text-[10px] tracking-[0.2em] uppercase">
          F\u00f6rslag
        </span>
        <ChipRow>
          {CTA_OPTIONS.map((option) => (
            <Chip
              key={option}
              label={option}
              selected={answers.primaryCta === option}
              onToggle={() =>
                onChange({
                  primaryCta:
                    answers.primaryCta === option ? "" : option,
                })
              }
            />
          ))}
        </ChipRow>
      </div>

      <TextareaField
        label="USP:er (unika s\u00e4ljargument)"
        optional
        value={answers.uniqueSellingPoints.join("\n")}
        onChange={(value) =>
          onChange({
            uniqueSellingPoints: value
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean),
          })
        }
        placeholder={"En USP per rad, t.ex.\n\u2022 Vi bygger p\u00e5 plats inom 48h\n\u2022 14 dagars garanti"}
        rows={3}
      />

      <TextareaField
        label="Special\u00f6nskem\u00e5l"
        optional
        value={answers.specialRequests}
        onChange={(value) => onChange({ specialRequests: value })}
        placeholder="N\u00e5got specifikt vi b\u00f6r ta h\u00e4nsyn till?"
        rows={2}
      />

      <AdvancedDisclosure
        id="more-info-brand-style"
        label="Tonalitet & ord att undvika"
        hint="Hj\u00e4lper copy-modellen tr\u00e4ffa r\u00e4tt r\u00f6st."
        count={2}
        activeCount={
          (answers.brand.designStyle.trim() ? 1 : 0) +
          (answers.brand.wordsToAvoid.trim() ? 1 : 0)
        }
      >
        <TextField
          label="Designstil-not"
          optional
          value={answers.brand.designStyle}
          onChange={(value) => updateBrand("designStyle", value)}
          placeholder="t.ex. enkelt, lekfullt, premium"
        />
        <TextareaField
          label="Ord att undvika"
          optional
          value={answers.brand.wordsToAvoid}
          onChange={(value) => updateBrand("wordsToAvoid", value)}
          placeholder="Ord eller fraser AI:n ska inte anv\u00e4nda."
          rows={2}
        />
      </AdvancedDisclosure>
    </FieldStack>
  );
}

function MediaCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-border/70 bg-card/40 rounded-xl border p-4">
      <div className="mb-3 flex items-start gap-3">
        <span className="bg-foreground/[0.05] inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <span className="text-foreground text-[13.5px] font-semibold tracking-tight">
            {title}
          </span>
          <p className="text-muted-foreground mt-0.5 text-[11.5px] leading-snug">
            {description}
          </p>
        </div>
      </div>
      {children}
    </div>
  );
}
