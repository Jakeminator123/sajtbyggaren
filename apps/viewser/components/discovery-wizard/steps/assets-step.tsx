"use client";

import { useCallback, useState } from "react";

import { AssetDropzone } from "@/components/discovery-wizard/asset-dropzone";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AssetPlacement, AssetRef } from "@/lib/asset-store/types";

import {
  FieldLabel,
  FieldStack,
  HelperText,
  SectionHeader,
} from "./step-primitives";
import type { WizardAnswers, WizardAssets } from "../wizard-types";

/**
 * AssetsStep — wizardens 6:e steg. Tre stack-block:
 *   1. Logotyp (1 fil, helst SVG/PNG transparent)
 *   2. Hero-bild (1 fil, landskap rekommenderas)
 *   3. Galleri (multi, drag eller välj flera)
 *
 * Varje uppladdad bild visas som thumbnail med:
 *   - alt-text-input (förifylld från GPT Vision)
 *   - placement-dropdown (förifylld från Vision, override:bar)
 *   - "Ta bort"-knapp
 *
 * Bilderna är redan sparade på disk i `data/uploads/__draft/<assetId>/`
 * när AssetsStep tar emot dem; flytt till rätt siteId-mapp sker i
 * `copy_operator_uploads` när build körs.
 */

const PLACEMENT_OPTIONS: { value: AssetPlacement; label: string }[] = [
  { value: "home", label: "Startsidan" },
  { value: "about", label: "Om oss" },
  { value: "services", label: "Tjänster" },
  { value: "projects", label: "Projekt" },
  { value: "products", label: "Produkter" },
  { value: "gallery", label: "Galleri" },
];

function ThumbnailPreview({ asset }: { asset: AssetRef }) {
  // VIKTIGT: vi får INTE använda `event.currentTarget.style.display = "none"`
  // i onError — det muterar DOM:en permanent och React behåller mutationen
  // när elementet återanvänds vid re-render (t.ex. när operatören byter
  // steg i wizarden eller efter cache-revalidering). Det orsakade tidigare
  // buggen där bilderna "kom fram men försvann en stund efter".
  // Istället håller vi failure-state i React; ny `assetId` återställer den
  // automatiskt eftersom `useState` initierar om vid key-byte.
  const [failed, setFailed] = useState(false);
  return (
    <div className="border-border/70 bg-muted/30 flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-lg border">
      {failed ? (
        <span
          aria-label="Förhandsvisning saknas"
          className="text-muted-foreground text-[10px] font-medium tracking-wider uppercase"
        >
          {asset.filename.slice(0, 2)}
        </span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`/api/asset-preview?assetId=${asset.assetId}&siteId=__draft`}
          alt={asset.alt || asset.filename}
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
          onLoad={() => setFailed(false)}
        />
      )}
    </div>
  );
}

function VisionBadge({ asset }: { asset: AssetRef }) {
  const confidence = asset.visionConfidence;
  if (!confidence) return null;
  const styles =
    confidence === "high"
      ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
      : confidence === "medium"
        ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
        : "bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-medium tracking-wide uppercase ${styles}`}
      title={
        asset.visionSubject
          ? `GPT Vision: ${asset.visionSubject}`
          : "AI-förslag"
      }
    >
      AI · {confidence}
    </span>
  );
}

function AssetCard({
  asset,
  showPlacement,
  onChange,
  onRemove,
}: {
  asset: AssetRef;
  showPlacement: boolean;
  onChange: (next: AssetRef) => void;
  onRemove: () => void;
}) {
  return (
    <div className="border-border/70 bg-card/60 flex items-start gap-3 rounded-xl border p-3">
      <ThumbnailPreview asset={asset} />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-foreground truncate text-[11px] font-medium">
            {asset.filename}
          </span>
          <VisionBadge asset={asset} />
        </div>
        <Input
          value={asset.alt}
          placeholder="Alt-text (vad bilden visar)"
          onChange={(event) =>
            onChange({ ...asset, alt: event.target.value.slice(0, 160) })
          }
          className="h-7 text-[12px]"
        />
        {showPlacement ? (
          <select
            value={asset.placement ?? "gallery"}
            onChange={(event) =>
              onChange({
                ...asset,
                placement: event.target.value as AssetPlacement,
              })
            }
            className="border-input bg-background text-foreground h-7 w-full rounded-md border px-2 text-[12px]"
          >
            {PLACEMENT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="h-7 text-[11px]"
        onClick={onRemove}
      >
        Ta bort
      </Button>
    </div>
  );
}

export type AssetsStepProps = {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
};

/**
 * Auto-hero-pick från galleri.
 *
 * När operatorn laddar upp galleri-bilder och inte har en explicit hero
 * än, picker vi bästa kandidaten utifrån GPT Vision-klassificeringen
 * som redan körs av upload-asset/api (AssetRef.placement +
 * AssetRef.visionConfidence). Detta uppfyller operatorns krav:
 *
 *   "GPT Vision ska beräkna vilken av bilderna som passar bäst [som
 *   hero] från dom bilderna/filmerna som kunden laddar upp i
 *   mediamaterial."
 *
 * Prio-ordning:
 *   1. placement === "home" och visionConfidence === "high"
 *   2. placement === "home" och visionConfidence === "medium"
 *   3. placement === "home" (oavsett confidence)
 *   4. Första bilden i listan som fallback
 *
 * Auto-promote sker BARA om operatorn inte redan har en hero — om hen
 * tar bort hero efter promoten promoteras INTE nya bilder igen (vi
 * antar att operator-handlingen är medveten).
 */
function pickHeroFromGallery(gallery: WizardAssets["gallery"]) {
  if (gallery.length === 0) return null;
  const high = gallery.find(
    (item) => item.placement === "home" && item.visionConfidence === "high",
  );
  if (high) return high;
  const medium = gallery.find(
    (item) => item.placement === "home" && item.visionConfidence === "medium",
  );
  if (medium) return medium;
  const anyHome = gallery.find((item) => item.placement === "home");
  if (anyHome) return anyHome;
  return gallery[0] ?? null;
}

export function AssetsStep({ answers, onChange }: AssetsStepProps) {
  const updateAssets = useCallback(
    (mutator: (current: WizardAssets) => WizardAssets) => {
      onChange({ assets: mutator(answers.assets) });
    },
    [answers.assets, onChange],
  );

  return (
    <FieldStack>
      <div>
        <SectionHeader>Logotyp</SectionHeader>
        <HelperText>
          Vi använder logotypen högst upp och längst ner på sidan. SVG ger
          skarpast resultat; PNG med transparent bakgrund fungerar också.
        </HelperText>
      </div>
      {answers.assets.logo ? (
        <AssetCard
          asset={answers.assets.logo}
          showPlacement={false}
          onChange={(next) => updateAssets((a) => ({ ...a, logo: next }))}
          onRemove={() => updateAssets((a) => ({ ...a, logo: null }))}
        />
      ) : (
        <AssetDropzone
          role="logo"
          mode="single"
          emptyLabel="Släpp logotypen här eller klicka för att välja"
          hintLabel="SVG / PNG / WebP, max 10 MB"
          onUploaded={(refs) => {
            const next = refs[0];
            if (next) updateAssets((a) => ({ ...a, logo: next }));
          }}
        />
      )}

      <div>
        <SectionHeader>Toppbild</SectionHeader>
        <HelperText>
          Stor bild högst upp på startsidan. En liggande bild i hög kvalitet av
          lokalen, produkten, kunden eller resultatet fungerar bäst.
        </HelperText>
      </div>
      {answers.assets.heroImage ? (
        <AssetCard
          asset={answers.assets.heroImage}
          showPlacement={false}
          onChange={(next) => updateAssets((a) => ({ ...a, heroImage: next }))}
          onRemove={() => updateAssets((a) => ({ ...a, heroImage: null }))}
        />
      ) : (
        <AssetDropzone
          role="hero"
          mode="single"
          emptyLabel="Släpp toppbilden här"
          hintLabel="Liggande format, minst 1200 px bred. JPG/WebP rekommenderas."
          onUploaded={(refs) => {
            const next = refs[0];
            if (next) updateAssets((a) => ({ ...a, heroImage: next }));
          }}
        />
      )}

      <div>
        <SectionHeader>Galleri</SectionHeader>
        <HelperText>
          AI:n föreslår var varje bild passar bäst (Om oss, Galleri, Projekt
          etc.) — du kan ändra placering per bild.
        </HelperText>
      </div>
      <div className="space-y-2">
        {answers.assets.gallery.map((galleryItem) => (
          <AssetCard
            key={galleryItem.assetId}
            asset={galleryItem}
            showPlacement
            onChange={(next) =>
              updateAssets((a) => ({
                ...a,
                gallery: a.gallery.map((item) =>
                  item.assetId === next.assetId ? next : item,
                ),
              }))
            }
            onRemove={() =>
              updateAssets((a) => {
                const nextGallery = a.gallery.filter(
                  (item) => item.assetId !== galleryItem.assetId,
                );
                // Om hero auto-pickades från just denna galleri-rad (samma
                // assetId) — nolla hero också. Annars pekade hero kvar på en
                // bild som inte längre finns i galleriet och payloaden bar en
                // spök-referens. Explicit hero-upload har eget assetId och
                // rörs inte.
                const heroFromThisRow =
                  a.heroImage?.assetId === galleryItem.assetId;
                return {
                  ...a,
                  gallery: nextGallery,
                  heroImage: heroFromThisRow ? null : a.heroImage,
                };
              })
            }
          />
        ))}
      </div>
      <AssetDropzone
        role="gallery"
        mode="multi"
        emptyLabel="Släpp galleribilder eller filmer här"
        hintLabel="Upp till ~20 bilder. Vi väljer automatiskt bästa toppbilden om du inte laddat upp en separat."
        onUploaded={(refs) =>
          updateAssets((a) => {
            const nextGallery = [...a.gallery, ...refs];
            // Auto-hero-pick från galleri (GPT Vision-driven). Endast när
            // operatorn inte redan har en hero — vi överskriver INTE en
            // explicit upload eller en tidigare auto-pick som operatorn
            // medvetet tagit bort. Se `pickHeroFromGallery` ovan för
            // prio-ordningen (placement + visionConfidence).
            if (!a.heroImage) {
              const candidate = pickHeroFromGallery(nextGallery);
              if (candidate) {
                // Klona kandidaten så hero INTE delar objektreferens med
                // galleri-raden. Annars pekade båda på samma objekt: en
                // alt/placement-redigering av hero forkade tyst bort från
                // galleriet (eller tvärtom). assetId behålls så removal-
                // detekteringen ovan fortfarande matchar källraden.
                return {
                  ...a,
                  gallery: nextGallery,
                  heroImage: { ...candidate },
                };
              }
            }
            return { ...a, gallery: nextGallery };
          })
        }
      />

      <FieldLabel optional>Tips</FieldLabel>
      <HelperText>
        Du kan hoppa över hela steget och få en text-only sajt med ett
        bokstavs-monogram som logo.
      </HelperText>
    </FieldStack>
  );
}
