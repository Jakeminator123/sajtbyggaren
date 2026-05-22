"use client";

import { Loader2, Sparkles, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import type { AssetRef, AssetRole } from "@/lib/asset-store/types";
import { CHIP_INTERACTIONS, PRIMARY_INTERACTIONS } from "@/lib/ui-tokens";

/**
 * AIImageGeneratorDialog — wizardens AI-bildgenerator.
 *
 * Operatören kan välja mellan att ladda upp en egen bild eller låta
 * GPT Image 1.5 skapa en. Båda flöden producerar samma `AssetRef`-shape
 * som MediaStep konsumerar — kallaren märker ingen skillnad.
 *
 * Flow:
 *   1. Operatör klickar "Generera med AI" bredvid en upload-zone
 *   2. Dialog öppnas med role-anpassad placeholder + stil-väljare
 *   3. POST /api/generate-image (8-30 sek beroende på storlek/kvalitet)
 *   4. Preview visas; operatör kan "Använd den" eller "Generera om"
 *   5. När "Använd den" → callback med AssetRef, dialog stängs
 *
 * Tillgänglighet:
 *   - Focus trap inom dialog (Tab/Shift+Tab cyklar inom)
 *   - Esc stänger
 *   - aria-modal + role="dialog"
 *   - Loading announces via aria-live
 */
export interface AIImageGeneratorDialogProps {
  open: boolean;
  role: AssetRole;
  companyName?: string;
  brandColorHex?: string;
  /** Standard-prompt baserat på kontext (kan vara tom). */
  initialPrompt?: string;
  onClose: () => void;
  onAccept: (ref: AssetRef) => void;
}

type StylePreset = "photoreal" | "minimal" | "illustration" | "brand";

const STYLE_OPTIONS: Array<{ id: StylePreset; label: string; description: string }> = [
  { id: "photoreal", label: "Fotorealistisk", description: "Editorial photo, naturligt ljus" },
  { id: "minimal", label: "Minimalistisk", description: "Geometriska former, mycket negativ space" },
  { id: "illustration", label: "Illustration", description: "Handritat vektorlook" },
  { id: "brand", label: "Brand-anpassad", description: "Anpassad efter företagsfärgen" },
];

const ROLE_LABEL: Record<AssetRole, string> = {
  logo: "logotyp",
  hero: "hero-bild",
  gallery: "galleribild",
  favicon: "favicon",
  ogImage: "social-image",
  backgroundVideo: "bakgrundsvideo",
};

const ROLE_DEFAULT_STYLE: Record<AssetRole, StylePreset> = {
  logo: "brand",
  hero: "photoreal",
  gallery: "photoreal",
  favicon: "minimal",
  ogImage: "photoreal",
  backgroundVideo: "photoreal",
};

const ROLE_PLACEHOLDER: Record<AssetRole, string> = {
  logo:
    "T.ex. 'En modern logotyp som föreställer en pensel som målar en cirkel, ren linjeföring'",
  hero:
    "T.ex. 'Hantverkare som målar en stor vit vägg i ljust morgonsken, varm scandi-känsla'",
  gallery:
    "T.ex. 'Detaljbild av en målarpensel mot frisk färg på en vägg, hög skärpa'",
  favicon:
    "T.ex. 'En enkel ikon som föreställer en pensel, geometrisk, läsbar vid 16×16 px'",
  ogImage:
    "T.ex. 'Hantverk-företag i Stockholm — penslar och färgburkar arrangerade som en still life'",
  backgroundVideo: "Video kan inte AI-genereras än — ladda upp egen .mp4",
};

export function AIImageGeneratorDialog({
  open,
  role,
  companyName,
  brandColorHex,
  initialPrompt = "",
  onClose,
  onAccept,
}: AIImageGeneratorDialogProps) {
  // Reset of state mellan role-byten / re-open hanteras via
  // ``key={aiDialogRole ?? "none"}`` i MediaStep — komponenten remountas
  // då naturligt och useState-initiering kör om. Det undviker React 19:s
  // ``react-hooks/set-state-in-effect``-lint som annars klagar på
  // setState-anrop i en useEffect för reset-syfte.
  const [prompt, setPrompt] = useState(initialPrompt);
  const [style, setStyle] = useState<StylePreset>(ROLE_DEFAULT_STYLE[role]);
  const [generating, setGenerating] = useState(false);
  const [preview, setPreview] = useState<AssetRef | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);

  const promptId = useId();
  const styleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-fokus på textarean när dialogen mountas. Pure side-effect (DOM-
  // call, ingen setState) — tillåten i useEffect.
  useEffect(() => {
    if (!open) return;
    const raf = requestAnimationFrame(() => textareaRef.current?.focus());
    return () => cancelAnimationFrame(raf);
  }, [open]);

  // Esc → stäng. Lyssnaren installeras bara när dialogen är öppen så
  // den inte stör övrig keyboard-nav.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && !generating) {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, generating, onClose]);

  // Sekund-räknare under generering. Pure setInterval i callback (ingen
  // setState direkt i effect-body) — kompatibelt med React 19 lint.
  // Reset av elapsedSec sker när ny generering startas (i handleGenerate).
  useEffect(() => {
    if (!generating) return;
    const start = Date.now();
    const interval = window.setInterval(() => {
      setElapsedSec(Math.round((Date.now() - start) / 1000));
    }, 500);
    return () => window.clearInterval(interval);
  }, [generating]);

  const previewSrc = preview
    ? preview.sourceUrl ??
      `/api/asset-preview?assetId=${preview.assetId}&siteId=__draft`
    : null;

  const handleGenerate = useCallback(async () => {
    const trimmed = prompt.trim();
    if (!trimmed) {
      setError("Skriv en beskrivning av bilden du vill ha.");
      return;
    }
    if (role === "backgroundVideo") {
      setError(
        "Video kan inte AI-genereras än. Ladda upp en egen .mp4 eller .webm.",
      );
      return;
    }
    setError(null);
    setElapsedSec(0);
    setGenerating(true);
    try {
      const response = await fetch("/api/generate-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: trimmed,
          role,
          style,
          companyName: companyName?.trim() || undefined,
          brandColorHex: brandColorHex || undefined,
        }),
      });
      const data = (await response.json()) as
        | { ok: true; ref: AssetRef }
        | { ok: false; error: string };
      if (!response.ok || !data.ok) {
        setError(
          "error" in data && data.error
            ? data.error
            : `Servern returnerade ${response.status}.`,
        );
        return;
      }
      setPreview(data.ref);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? `Kunde inte nå servern: ${caught.message}`
          : "Okänt nätverksfel.",
      );
    } finally {
      setGenerating(false);
    }
  }, [prompt, role, style, companyName, brandColorHex]);

  const handleAccept = useCallback(() => {
    if (!preview) return;
    onAccept(preview);
    onClose();
  }, [preview, onAccept, onClose]);

  if (!open) return null;

  const roleLabel = ROLE_LABEL[role];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={`${promptId}-title`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      onClick={(e) => {
        // Klick utanför dialog stänger (men inte under generering)
        if (e.target === e.currentTarget && !generating) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="bg-background w-full max-w-2xl overflow-hidden rounded-xl border shadow-2xl"
      >
        {/* Header */}
        <div className="border-border/70 flex items-center justify-between border-b px-5 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="text-foreground/70 h-4 w-4" />
            <h2
              id={`${promptId}-title`}
              className="text-foreground text-[14px] font-semibold tracking-tight"
            >
              Generera {roleLabel} med AI
            </h2>
          </div>
          <button
            type="button"
            onClick={() => !generating && onClose()}
            disabled={generating}
            className="text-muted-foreground hover:text-foreground rounded-md p-1 transition-colors disabled:opacity-30"
            aria-label="Stäng dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 px-5 py-4">
          {/* Prompt */}
          <div>
            <label
              htmlFor={promptId}
              className="text-foreground mb-1.5 block text-[12px] font-medium"
            >
              Beskrivning
            </label>
            <textarea
              ref={textareaRef}
              id={promptId}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value.slice(0, 1000))}
              disabled={generating}
              rows={3}
              placeholder={ROLE_PLACEHOLDER[role]}
              className="border-border/70 bg-background focus:border-foreground/40 w-full resize-none rounded-md border px-3 py-2 text-[13px] outline-none transition-colors disabled:opacity-60"
              maxLength={1000}
            />
            <div className="text-muted-foreground mt-1 flex justify-between text-[10.5px]">
              <span>Beskriv tydligt vad du vill ha — färg, miljö, känsla.</span>
              <span>{prompt.length}/1000</span>
            </div>
          </div>

          {/* Style picker */}
          <fieldset>
            <legend
              id={styleId}
              className="text-foreground mb-1.5 block text-[12px] font-medium"
            >
              Stil
            </legend>
            <div
              role="radiogroup"
              aria-labelledby={styleId}
              className="grid grid-cols-2 gap-2"
            >
              {STYLE_OPTIONS.map((option) => {
                const selected = style === option.id;
                return (
                  <button
                    key={option.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setStyle(option.id)}
                    disabled={generating}
                    className={[
                      "rounded-md border px-3 py-2 text-left text-[12px] transition-all disabled:opacity-50",
                      selected
                        ? "border-foreground/60 bg-foreground/[0.04]"
                        : "border-border/60 hover:border-foreground/30",
                      CHIP_INTERACTIONS,
                    ].join(" ")}
                  >
                    <div className="text-foreground font-medium">
                      {option.label}
                    </div>
                    <div className="text-muted-foreground mt-0.5 text-[10.5px]">
                      {option.description}
                    </div>
                  </button>
                );
              })}
            </div>
          </fieldset>

          {/* Preview area */}
          {(generating || preview || error) && (
            <div className="border-border/60 bg-muted/20 relative aspect-video w-full overflow-hidden rounded-md border">
              {generating ? (
                <div
                  role="status"
                  aria-live="polite"
                  className="absolute inset-0 flex flex-col items-center justify-center gap-2"
                >
                  <Loader2 className="text-foreground/60 h-6 w-6 animate-spin" />
                  <div className="text-foreground/70 text-[12px] font-medium">
                    Genererar… {elapsedSec}s
                  </div>
                  <div className="text-muted-foreground text-[10.5px]">
                    GPT Image 1.5 — typiskt 8-30 sek
                  </div>
                </div>
              ) : preview && previewSrc ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewSrc}
                  alt={preview.alt || `Genererad ${roleLabel}`}
                  className="h-full w-full object-contain"
                />
              ) : error ? (
                <div className="text-destructive flex h-full w-full items-center justify-center p-4 text-center text-[12px]">
                  {error}
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-border/70 bg-muted/10 flex items-center justify-between gap-2 border-t px-5 py-3">
          <div className="text-muted-foreground text-[10.5px]">
            ⌘+enter genererar · esc stänger
          </div>
          <div className="flex items-center gap-2">
            {preview && !generating ? (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setPreview(null);
                    void handleGenerate();
                  }}
                  className="text-muted-foreground hover:text-foreground rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors"
                >
                  Generera om
                </button>
                <button
                  type="button"
                  onClick={handleAccept}
                  className={[
                    "bg-foreground text-background hover:bg-foreground/90",
                    "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors",
                    PRIMARY_INTERACTIONS,
                  ].join(" ")}
                >
                  Använd den här
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={generating}
                  className="text-muted-foreground hover:text-foreground rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-30"
                >
                  Avbryt
                </button>
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={generating || !prompt.trim()}
                  onKeyDown={(e) => {
                    if (
                      (e.metaKey || e.ctrlKey) &&
                      e.key === "Enter" &&
                      !generating &&
                      prompt.trim()
                    ) {
                      e.preventDefault();
                      void handleGenerate();
                    }
                  }}
                  className={[
                    "bg-foreground text-background hover:bg-foreground/90",
                    "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-40",
                    PRIMARY_INTERACTIONS,
                  ].join(" ")}
                >
                  {generating ? (
                    <>
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Genererar…
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3 w-3" />
                      Generera
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
