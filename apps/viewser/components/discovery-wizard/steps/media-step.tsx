"use client";

import {
  Globe,
  Image as ImageIcon,
  ImagePlus,
  Mountain,
  Sparkles,
  Square,
  Video,
} from "lucide-react";
import { useState } from "react";

import { AIImageGeneratorDialog } from "@/components/discovery-wizard/ai-image-generator-dialog";
import { AssetDropzone } from "@/components/discovery-wizard/asset-dropzone";
import type { AssetRef, AssetRole } from "@/lib/asset-store/types";

import type { WizardAnswers, WizardAssets, WizardMedia } from "../wizard-types";
import { AssetsStep } from "./assets-step";
import { FieldStack, HelperText } from "./step-primitives";

/**
 * MediaStep — wizardens steg 5 (Pass 5: rik kort-layout per asset).
 *
 * Sektioner i ordning:
 *   1. Logotyp + Hero + Galleri — befintliga `AssetsStep` återanvänds.
 *   2. Favicon — preview som browser-flik-mockup.
 *   3. OG-image — preview i 1200×630-ratio.
 *   4. Bakgrundsvideo — preview som <video autoplay loop muted>.
 *
 * Varje extra-asset visas i ett `AssetCard` med ikon, titel, behöver-
 * backend-badge och egen dropzone/preview. Vi flyttade gamla AssetsStep
 * (logo/hero/gallery) in i samma sektion-layout via en wrapper-card.
 */
export function MediaStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const updateMedia = (mutator: (current: WizardMedia) => WizardMedia) => {
    onChange({ media: mutator(answers.media) });
  };

  // En enda dialog-state för alla roller — vi öppnar den med rätt role
  // baserat på vilken AICTA-knapp som klickades. Detta håller komponent-
  // trädet platt och slipper rendera 5 separata dialog-instanser.
  const [aiDialogRole, setAiDialogRole] = useState<AssetRole | null>(null);

  return (
    <FieldStack>
      <div>
        <HelperText>
          Alla bilder är valfria — om du hoppar över får sajten ett
          monogram-logo och text-baserade hero-sektioner. Du kan också
          generera bilder med AI (GPT Image 1.5) om du saknar egna.
        </HelperText>
      </div>

      {/* 1. Logo + Hero + Galleri (befintlig AssetsStep i en kort). */}
      <AssetCard
        icon={<ImagePlus className="h-4 w-4" />}
        title="Logotyp, hero och galleri"
        description="Huvudtillgångarna som syns på sajten. AI:n föreslår alt-text och placering."
      >
        <AssetsStepInline answers={answers} onChange={onChange} />
        {/* AI-knapprad för rollerna inne i AssetsStep — vi modifierar
            INTE AssetsStep (delas med Pass 1 och har egna tester),
            utan exponerar AI-shortcut här ovanför som ett komplement. */}
        <div className="border-border/60 mt-4 flex flex-wrap items-center gap-2 border-t pt-3">
          <span className="text-muted-foreground mr-1 text-[10.5px] tracking-wider uppercase">
            generera med ai:
          </span>
          {(["logo", "hero", "gallery"] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setAiDialogRole(r)}
              className="border-border/60 hover:border-foreground/40 hover:bg-foreground/[0.03] inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors"
            >
              <Sparkles className="h-3 w-3" />
              {r === "logo" ? "Logotyp" : r === "hero" ? "Hero" : "Galleribild"}
            </button>
          ))}
        </div>
      </AssetCard>

      {/* 2. Favicon. */}
      <AssetCard
        icon={<Square className="h-4 w-4" />}
        title="Favicon"
        description="Ikonen i browser-fliken och bokmärken."
      >
        {answers.media.favicon ? (
          <FaviconPreview
            asset={answers.media.favicon}
            companyName={answers.companyName}
            onRemove={() => updateMedia((m) => ({ ...m, favicon: null }))}
          />
        ) : (
          <UploadOrGenerate
            onGenerate={() => setAiDialogRole("favicon")}
          >
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
          </UploadOrGenerate>
        )}
      </AssetCard>

      {/* 3. OG-image. */}
      <AssetCard
        icon={<Globe className="h-4 w-4" />}
        title="OG-image"
        description="Förhandsvisning på Facebook, LinkedIn, Slack och SMS."
      >
        {answers.media.ogImage ? (
          <OgImagePreview
            asset={answers.media.ogImage}
            companyName={answers.companyName}
            offer={answers.offer}
            onRemove={() => updateMedia((m) => ({ ...m, ogImage: null }))}
          />
        ) : (
          <UploadOrGenerate
            onGenerate={() => setAiDialogRole("ogImage")}
          >
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
          </UploadOrGenerate>
        )}
      </AssetCard>

      {/* 4. Bakgrundsvideo. */}
      <AssetCard
        icon={<Video className="h-4 w-4" />}
        title="Bakgrundsvideo"
        description="Loop bakom hero-texten — tyst, kort, ger sajten liv."
      >
        {answers.media.backgroundVideo ? (
          <VideoPreview
            asset={answers.media.backgroundVideo}
            onRemove={() =>
              updateMedia((m) => ({ ...m, backgroundVideo: null }))
            }
          />
        ) : (
          <AssetDropzone
            role="backgroundVideo"
            mode="single"
            emptyLabel="Släpp video här (.mp4 / .webm)"
            hintLabel="5-15 sekunder, max ~50 MB. Hero-bilden visas som fallback."
            onUploaded={(refs) => {
              const next = refs[0];
              if (next)
                updateMedia((m) => ({ ...m, backgroundVideo: next }));
            }}
          />
        )}
      </AssetCard>

      {/* Singleton AI-image-dialog — öppnas med rätt role.
          `key` baserat på role gör att dialogen remountas vid byte,
          vilket nollställer prompt/style/preview-state utan att vi
          behöver setState-i-effect (förbjudet av React 19 lint). */}
      <AIImageGeneratorDialog
        key={aiDialogRole ?? "closed"}
        open={aiDialogRole !== null}
        role={aiDialogRole ?? "hero"}
        companyName={answers.companyName}
        brandColorHex={answers.brand?.primaryColorHex || undefined}
        onClose={() => setAiDialogRole(null)}
        onAccept={(ref) => {
          // Mappa AssetRef till rätt slot i WizardMedia/WizardAssets
          // baserat på role. Logo/hero/gallery hamnar i answers.assets
          // (legacy struktur), nya media-fält i answers.media.
          if (!aiDialogRole) return;
          if (aiDialogRole === "favicon") {
            updateMedia((m) => ({ ...m, favicon: ref }));
          } else if (aiDialogRole === "ogImage") {
            updateMedia((m) => ({ ...m, ogImage: ref }));
          } else if (aiDialogRole === "logo") {
            onChange({ assets: { ...answers.assets, logo: ref } });
          } else if (aiDialogRole === "hero") {
            onChange({ assets: { ...answers.assets, heroImage: ref } });
          } else if (aiDialogRole === "gallery") {
            onChange({
              assets: {
                ...answers.assets,
                gallery: [...(answers.assets.gallery ?? []), ref],
              },
            });
          }
        }}
      />
    </FieldStack>
  );
}

/**
 * UploadOrGenerate — wrappar en dropzone med en "Generera med AI"-
 * knapp ovanför. Ger operatören valet utan att tränga ihop båda
 * action:s i samma yta (vilket skulle skapa kollision mellan
 * drag-target och click-target).
 */
function UploadOrGenerate({
  children,
  onGenerate,
}: {
  children: React.ReactNode;
  onGenerate: () => void;
}) {
  return (
    <div className="space-y-2">
      {children}
      <div className="flex items-center gap-2">
        <div className="bg-border/60 h-px flex-1" />
        <span className="text-muted-foreground text-[10.5px] tracking-wider uppercase">
          eller
        </span>
        <div className="bg-border/60 h-px flex-1" />
      </div>
      <button
        type="button"
        onClick={onGenerate}
        className="border-border/60 hover:border-foreground/40 hover:bg-foreground/[0.03] inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed px-3 py-2 text-[12px] font-medium transition-colors"
      >
        <Sparkles className="h-3.5 w-3.5" />
        Generera med AI
      </button>
    </div>
  );
}

/**
 * AssetsStepInline — wrappar gamla AssetsStep utan dess section-headers
 * eftersom vi nu sätter dem från MediaStep-cards. Detta håller en
 * konsekvent visuell rytm i steg 5.
 */
function AssetsStepInline({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  // Vi använder samma AssetsStep från Pass 1 — den har egna section-
  // headers och tips-rad. För att passa in i nya kort-layouten passar
  // vi bara igenom datan utan extra wrapping; framtida iteration kan
  // refaktorera AssetsStep till hooks-only.
  return <AssetsStep answers={answers} onChange={onChange} />;
}

/* ── AssetCard wrapper ──────────────────────────────────────────── */

function AssetCard({
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

/* ── Previews ──────────────────────────────────────────────────── */

function FaviconPreview({
  asset,
  companyName,
  onRemove,
}: {
  asset: AssetRef;
  companyName: string;
  onRemove: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const label = companyName?.trim() || asset.filename;
  return (
    <div className="flex items-center gap-3">
      <div className="border-border/60 bg-background flex flex-1 items-center gap-2 rounded-md border px-2.5 py-1.5">
        <div className="bg-muted/50 flex h-4 w-4 shrink-0 items-center justify-center overflow-hidden rounded-sm">
          {failed ? (
            <ImageIcon className="text-muted-foreground h-2.5 w-2.5" />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`/api/asset-preview?assetId=${asset.assetId}&siteId=__draft`}
              alt={asset.alt || asset.filename}
              className="h-full w-full object-contain"
              onError={() => setFailed(true)}
            />
          )}
        </div>
        <span className="text-foreground/80 truncate text-[12px]">{label}</span>
        <span className="text-muted-foreground ml-auto text-[10px]">flik-preview</span>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="text-muted-foreground hover:text-foreground shrink-0 text-[11px]"
      >
        Ta bort
      </button>
    </div>
  );
}

function OgImagePreview({
  asset,
  companyName,
  offer,
  onRemove,
}: {
  asset: AssetRef;
  companyName: string;
  offer: string;
  onRemove: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const title = companyName?.trim() || "Företagets sajt";
  const description = offer?.trim() ? `${offer.trim().slice(0, 120)}…` : "Social preview";
  return (
    <div className="space-y-2">
      <div className="border-border/60 bg-background overflow-hidden rounded-lg border">
        <div className="bg-muted/30 relative aspect-[1200/630] w-full overflow-hidden">
          {failed ? (
            <div className="text-muted-foreground flex h-full w-full items-center justify-center">
              <Mountain className="h-6 w-6" />
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`/api/asset-preview?assetId=${asset.assetId}&siteId=__draft`}
              alt={asset.alt || asset.filename}
              className="h-full w-full object-cover"
              onError={() => setFailed(true)}
            />
          )}
        </div>
        <div className="border-border/60 border-t px-3 py-2">
          <div className="text-muted-foreground font-mono text-[9.5px] tracking-[0.2em] uppercase">
            facebook · linkedin · sms
          </div>
          <div className="text-foreground mt-0.5 truncate text-[12.5px] font-semibold">
            {title}
          </div>
          <div className="text-muted-foreground truncate text-[11px]">
            {description}
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onRemove}
          className="text-muted-foreground hover:text-foreground text-[11px]"
        >
          Ta bort
        </button>
      </div>
    </div>
  );
}

function VideoPreview({
  asset,
  onRemove,
}: {
  asset: AssetRef;
  onRemove: () => void;
}) {
  // VercelBlobAssetStore sätter `sourceUrl` på AssetRef:n vilket pekar
  // mot den publika blob:en. Då kan vi spela upp direkt utan att gå
  // genom /api/asset-stream. LocalAssetStore sätter ingen sourceUrl —
  // då går vi via /api/asset-preview som redirectar till disk-bytes
  // (eller blob-bytes om båda kombineras).
  const playbackUrl =
    asset.sourceUrl ??
    `/api/asset-preview?assetId=${asset.assetId}&siteId=__draft`;
  const sizeMb = (asset.sizeBytes / 1024 / 1024).toFixed(1);
  return (
    <div className="space-y-2">
      <div className="border-border/60 bg-background overflow-hidden rounded-lg border">
        <div className="bg-foreground/[0.04] relative aspect-video w-full overflow-hidden">
          <video
            src={playbackUrl}
            className="h-full w-full object-cover"
            autoPlay
            loop
            muted
            playsInline
          />
        </div>
        <div className="border-border/60 flex items-center gap-2 border-t px-3 py-2">
          <Video className="text-foreground/70 h-3.5 w-3.5 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-foreground truncate text-[12px] font-medium">
              {asset.filename}
            </div>
            <div className="text-muted-foreground text-[10px]">
              {asset.mimeType} · {sizeMb} MB
            </div>
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onRemove}
          className="text-muted-foreground hover:text-foreground text-[11px]"
        >
          Ta bort
        </button>
      </div>
    </div>
  );
}

// AssetsStepInline används med dessa typer.
void ({} as WizardAssets);
