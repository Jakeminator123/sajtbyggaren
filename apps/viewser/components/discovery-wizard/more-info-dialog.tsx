"use client";

import { Globe, Settings2, Square, Video, X } from "lucide-react";
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

import { ContentStep } from "./steps/content-step";
import {
  AdvancedDisclosure,
  Chip,
  ChipRow,
  FieldStack,
  TextField,
  TextareaField,
} from "./steps/step-primitives";
import { StoryEssentialsFields, StoryExtrasFields } from "./steps/story-step";
import { CTA_OPTIONS } from "./wizard-constants";
import type { ContentBranch } from "./wizard-constants";
import type { WizardAnswers, WizardMedia } from "./wizard-types";

/**
 * MoreInfoDialog — popup som öppnas från "Ange information"-knappen på
 * tab 3 (Funktioner). Fem smala flikar så varje skärmbild har lite att
 * fylla i istället för en lång scroll. Operatör-feedback (2026-05-26):
 *
 *   "Gör pop-up smalare med mindre spacing på sidorna. Alternativt
 *   behåll bredden och flytta upp så att man inte behöver skrolla så
 *   mycket. Hellre att det är fler steg/flikar och mindre att fylla i
 *   på varje än att man måste skrolla. Anpassa även för mobile."
 *
 * Flikar:
 *   - Om oss     — story (essentials + extras, vision/historia/målgrupp)
 *   - Innehåll   — branch-specifik ContentStep (produkter/meny/tjänster/team/projekt)
 *   - Kontakt    — telefon/e-post/adress/öppettider
 *   - Media      — favicon/OG/bakgrundsvideo (logo+hero+galleri ligger på tab 3)
 *   - Avancerat  — primär CTA, USP:er, specialönskemål, ord-att-undvika
 *
 * Backend-payload påverkas inte — alla fält skrivs till samma
 * `WizardAnswers`-objekt som `buildDiscoveryPayload` redan läser.
 *
 * Mobile: tab-baren scrollar horisontellt (overflow-x-auto + snap-x) så
 * de fem flikarna får plats även på 375px-skärmar. DialogDescription
 * göms på mobil för att spara vertikal yta.
 */

export type MoreInfoTabId =
  | "about"
  | "content"
  | "contact"
  | "media"
  | "advanced";

const TABS: ReadonlyArray<{
  id: MoreInfoTabId;
  label: string;
}> = [
  { id: "about", label: "Om oss" },
  { id: "content", label: "Innehåll" },
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
  /**
   * Flik som dialogen öppnas på (default "about"). Wizarden sätter den
   * till "contact" när den djuplänkar hit för att be om ett saknat
   * telefonnummer, så operatören inte oavsiktligt publicerar
   * platshållar-numret (+46 8 000 00 00).
   */
  initialTab?: MoreInfoTabId;
};

export function MoreInfoDialog({
  open,
  onOpenChange,
  answers,
  onChange,
  branch,
  initialTab = "about",
}: MoreInfoDialogProps) {
  const [activeTab, setActiveTab] = useState<MoreInfoTabId>(initialTab);

  // Nollställ aktiv flik till önskad ``initialTab`` varje gång dialogen
  // öppnas (false → true) OCH när ``initialTab`` byts medan dialogen redan
  // är öppen (t.ex. en framtida djuplänk som byter mål-flik utan att stänga
  // dialogen — annars hängde activeTab kvar på föregående flik). Render-tids
  // state-justering (Reacts "föregående props"-mönster via ``wasOpen`` +
  // ``trackedInitialTab``) istället för ``useEffect([open])``: dels ogillar
  // React 19:s ``react-hooks/set-state-in-effect`` effekt-driven setState,
  // dels är dialogen fullt parent-controlled — Radix routar aldrig
  // open-flanken genom onOpenChange, så en onOpenChange-wrapper skulle inte
  // hinna nollställa fliken vid öppning. Manuell flik-navigering ändrar
  // ``activeTab`` men inte ``initialTab``, så den skrivs aldrig över här.
  const [wasOpen, setWasOpen] = useState(open);
  const [trackedInitialTab, setTrackedInitialTab] =
    useState<MoreInfoTabId>(initialTab);
  if (open !== wasOpen) {
    setWasOpen(open);
    setTrackedInitialTab(initialTab);
    if (open) setActiveTab(initialTab);
  } else if (open && initialTab !== trackedInitialTab) {
    setTrackedInitialTab(initialTab);
    setActiveTab(initialTab);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="border-border/60 bg-background grid h-[min(100dvh-1.5rem,720px)] !w-[min(100vw-1rem,720px)] !max-w-[min(100vw-1rem,720px)] grid-rows-[auto_auto_1fr_auto] gap-0 overflow-hidden border p-0 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] sm:!max-w-[min(100vw-2rem,720px)] sm:rounded-3xl"
        showCloseButton={false}
      >
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Stäng"
          className="text-muted-foreground hover:bg-foreground/5 hover:text-foreground min-tap sm:min-tap-0 absolute top-2 right-2 z-10 inline-flex items-center justify-center rounded-full transition-colors active:scale-95 sm:top-3 sm:right-3 sm:h-8 sm:w-8"
        >
          <X className="h-4 w-4" />
        </button>

        <DialogHeader className="space-y-0 px-4 pt-4 pb-2 text-left sm:px-6 sm:pt-5 sm:pb-3">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 pr-10">
            <DialogTitle className="text-foreground text-[15px] leading-tight font-semibold tracking-tight sm:text-[17px]">
              Mer information
            </DialogTitle>
            <DialogDescription className="text-muted-foreground hidden text-[12.5px] leading-relaxed sm:inline">
              Detaljer fylls i automatiskt vid skrapning. Allt är valfritt.
            </DialogDescription>
          </div>
        </DialogHeader>

        <div
          role="tablist"
          aria-label="Mer information-flikar"
          className="border-border/60 flex w-full snap-x snap-mandatory items-stretch gap-0 overflow-x-auto border-b px-4 sm:px-6"
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
                  "min-tap sm:min-tap-0 relative -mb-px inline-flex shrink-0 snap-start items-center justify-center gap-1.5 border-b-2 px-3 py-2 text-[12.5px] font-medium tracking-tight transition-colors sm:px-4 sm:py-2.5",
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

        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          <div className="mx-auto max-w-xl">
            {activeTab === "about" ? (
              <AboutBlock answers={answers} onChange={onChange} />
            ) : null}
            {activeTab === "content" ? (
              <ContentStep answers={answers} onChange={onChange} branch={branch} />
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

        <div className="border-border/60 bg-background/95 flex items-center justify-end gap-2 border-t px-4 py-3 pb-safe-or-4 sm:px-5 sm:py-3">
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

/** Story-fält: om-oss, historia, vision, kontaktintro, målgrupp. */
function AboutBlock({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  return (
    <FieldStack>
      <StoryEssentialsFields answers={answers} onChange={onChange} />
      <StoryExtrasFields answers={answers} onChange={onChange} />
      <TextareaField
        label="Målgrupp"
        optional
        value={answers.targetAudience}
        onChange={(value) => onChange({ targetAudience: value })}
        placeholder="Ålder, bransch, behov, plats?"
        rows={2}
      />
    </FieldStack>
  );
}

/** Telefon, e-post, adress, öppettider. Tidigare i foundation-step. */
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
          label="Öppettider"
          optional
          value={answers.contact.openingHours}
          onChange={(value) => updateContact("openingHours", value)}
          placeholder="Mån–Fre 09–17"
        />
      </div>
    </FieldStack>
  );
}

/**
 * Subset av MediaStep — bara favicon + OG-bild + bakgrundsvideo. Logo,
 * hero och galleri ligger på tab 3 (functions) i huvud-wizarden.
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
      <MediaCard
        icon={<Square className="h-4 w-4" />}
        title="Favicon"
        description="Ikonen i browser-fliken. Lämna tomt så genererar vi från monogrammet."
      >
        {answers.media.favicon ? (
          <FileRow
            filename={answers.media.favicon.filename}
            onRemove={() => updateMedia((m) => ({ ...m, favicon: null }))}
          />
        ) : (
          <AssetDropzone
            role="favicon"
            mode="single"
            emptyLabel="Släpp favicon här"
            hintLabel="Kvadratisk PNG eller SVG, minst 256×256 px."
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
        description="Social förhandsvisning. Vi genererar en från brand-färgen om du lämnar tomt."
      >
        {answers.media.ogImage ? (
          <FileRow
            filename={answers.media.ogImage.filename}
            onRemove={() => updateMedia((m) => ({ ...m, ogImage: null }))}
          />
        ) : (
          <AssetDropzone
            role="ogImage"
            mode="single"
            emptyLabel="Släpp social-image här"
            hintLabel="Liggande bild — vi croppar till 1200×630."
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
          <FileRow
            filename={answers.media.backgroundVideo.filename}
            onRemove={() =>
              updateMedia((m) => ({ ...m, backgroundVideo: null }))
            }
          />
        ) : (
          <AssetDropzone
            role="backgroundVideo"
            mode="single"
            emptyLabel="Släpp video här (.mp4 / .webm)"
            hintLabel="5–15 sekunder, max ~50 MB."
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

/** USP:er, primär CTA, specialönskemål, brand-tonalitet. */
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
        <span>Finjustering. Tom fält — backend löser det själv.</span>
      </p>

      <TextField
        label="Primär CTA"
        optional
        value={answers.primaryCta}
        onChange={(value) => onChange({ primaryCta: value })}
        placeholder="t.ex. Boka möte"
      />
      <div>
        <span className="text-muted-foreground mb-2 inline-flex font-mono text-[10px] tracking-[0.2em] uppercase">
          Förslag
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
        label="USP:er (unika säljargument)"
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
        placeholder={"En USP per rad"}
        rows={3}
      />

      <TextareaField
        label="Specialönskemål"
        optional
        value={answers.specialRequests}
        onChange={(value) => onChange({ specialRequests: value })}
        placeholder="Något specifikt vi bör ta hänsyn till?"
        rows={2}
      />

      <AdvancedDisclosure
        id="more-info-brand-style"
        label="Tonalitet & ord att undvika"
        hint="Hjälper copy-modellen träffa rätt röst."
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
          placeholder="Ord eller fraser AI:n inte ska använda."
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
    <div className="border-border/70 bg-card/40 rounded-xl border p-3 sm:p-4">
      <div className="mb-3 flex items-start gap-3">
        <span className="bg-foreground/[0.05] inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <span className="text-foreground text-[13px] font-semibold tracking-tight">
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

function FileRow({ filename, onRemove }: { filename: string; onRemove: () => void }) {
  return (
    <div className="border-border/60 bg-background flex items-center gap-3 rounded-md border px-3 py-2">
      <span className="text-foreground/80 truncate text-[12px]">{filename}</span>
      <button
        type="button"
        onClick={onRemove}
        className="text-muted-foreground hover:text-foreground ml-auto shrink-0 text-[11px]"
      >
        Ta bort
      </button>
    </div>
  );
}
