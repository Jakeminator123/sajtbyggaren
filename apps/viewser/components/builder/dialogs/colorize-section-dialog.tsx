"use client";

import { Loader2, PaintBucket } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import {
  useFollowupBuild,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
import type { MarkedSectionRef } from "@/components/preview-inspector-context";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * Färglägg en markerad sektion (sektionsmenyns "Färglägg sektionen",
 * Verktyg fas 3 2026-06-11).
 *
 * Öppnas från preview-markeringsläget med sektionskontexten
 * (routeId+sectionId) från klicket. Operatören väljer mål (bakgrund
 * eller text) + en färg; dialogen bygger en deterministisk prompt
 * ("Ändra bakgrundsfärgen i den markerade sektionen … till #hex") och
 * skickar markeringen strukturerat som ``markedSections`` (ADR 0046).
 * Python-sidan (followup/section_style.py) tolkar prompten utan LLM
 * och persisterar en per-sektion override i
 * ``directives.sectionStyleOverrides``; build_site.py renderar den som
 * CSS mot ``data-section-id``-markören.
 *
 * Ett mål per bygge — backend-extraktorn bär exakt ett direktiv per
 * prompt, och två snabba byggen är ärligare än en prompt extraktorn
 * bara halvförstår.
 */

const PRESET_PALETTE: ReadonlyArray<{ hex: string; label: string }> = [
  { hex: "#FFFFFF", label: "Vit" },
  { hex: "#F8FAFC", label: "Ljusgrå" },
  { hex: "#0F172A", label: "Mörk slate" },
  { hex: "#1E40AF", label: "Djup blå" },
  { hex: "#2D5F3F", label: "Skogsgrön" },
  { hex: "#B45309", label: "Höstambar" },
];

const HEX_PATTERN = /^#([0-9a-fA-F]{6})$/;

type SectionColorTarget = "background" | "text";

const TARGET_OPTIONS: ReadonlyArray<{
  id: SectionColorTarget;
  label: string;
  hint: string;
}> = [
  { id: "background", label: "Bakgrund", hint: "Hela sektionens yta" },
  { id: "text", label: "Text", hint: "Rubriker och brödtext" },
];

type ColorizeSectionDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  /** Sektionen som färgläggs — från sektionsmenyns klickkontext. */
  sectionRef: MarkedSectionRef | null;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: OnFollowupBuildDone;
  /** C2 globalt bygg-lås + C1 "Iterera från denna"-pin (från BuilderShell). */
  isBuilding?: boolean;
  baseRunId?: string | null;
};

export function ColorizeSectionDialog({
  open,
  onOpenChange,
  siteId,
  sectionRef,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
}: ColorizeSectionDialogProps) {
  const [target, setTarget] = useState<SectionColorTarget>("background");
  const [chosenHex, setChosenHex] = useState<string | null>(null);
  const [hexInput, setHexInput] = useState<string>("");
  const { runFollowup, isBusy, error } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const sectionLabel =
    sectionRef?.headingText?.trim() || sectionRef?.sectionId || "";

  const pickColor = useCallback((hex: string) => {
    setChosenHex(hex);
    setHexInput(hex);
  }, []);

  const handleHexChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const raw = event.target.value;
      setHexInput(raw);
      if (HEX_PATTERN.test(raw)) setChosenHex(raw);
    },
    [],
  );

  const canSubmit = useMemo(() => {
    const hexFieldOk = hexInput === "" || HEX_PATTERN.test(hexInput);
    return Boolean(sectionRef) && chosenHex !== null && hexFieldOk;
  }, [sectionRef, chosenHex, hexInput]);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit || !sectionRef || !chosenHex) return;
    // Exakt promptgrammatik som section_style.extract_section_style_directive
    // tolkar deterministiskt: sektionsreferens + explicit mål + hex.
    const targetNoun =
      target === "background" ? "bakgrundsfärgen" : "textfärgen";
    const prompt =
      `Ändra ${targetNoun} i den markerade sektionen "${sectionLabel}" ` +
      `till ${chosenHex}. Behåll övrig design, copy och struktur intakt.`;
    const result = await runFollowup(prompt, {
      markedSections: [
        { routeId: sectionRef.routeId, sectionId: sectionRef.sectionId },
      ],
    });
    if (result.ok) onOpenChange(false);
  }, [
    canSubmit,
    sectionRef,
    chosenHex,
    target,
    sectionLabel,
    runFollowup,
    onOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Färglägg sektionen</DialogTitle>
          <DialogDescription>
            {sectionLabel ? (
              <>
                Gäller sektionen{" "}
                <span className="text-foreground font-medium">
                  ”{sectionLabel}”
                </span>
                . Välj vad som ska färgas och med vilken färg.
              </>
            ) : (
              "Välj vad som ska färgas och med vilken färg."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div
            role="radiogroup"
            aria-label="Färgmål i sektionen"
            className="grid grid-cols-2 gap-2"
          >
            {TARGET_OPTIONS.map((option) => {
              const isActive = target === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  onClick={() => setTarget(option.id)}
                  className={cn(
                    "flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left transition active:scale-[0.98]",
                    "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                    isActive
                      ? "border-foreground bg-foreground/[0.04]"
                      : "border-border/60 hover:border-border",
                  )}
                >
                  <span className="text-[12.5px] font-medium tracking-tight">
                    {option.label}
                  </span>
                  <span className="text-muted-foreground text-[10.5px]">
                    {option.hint}
                  </span>
                </button>
              );
            })}
          </div>

          <div>
            <Label className="text-muted-foreground mb-2 block text-[11px] tracking-tight uppercase">
              Förslag
            </Label>
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
              {PRESET_PALETTE.map((preset) => {
                const isActive =
                  chosenHex?.toLowerCase() === preset.hex.toLowerCase();
                return (
                  <button
                    key={preset.hex}
                    type="button"
                    onClick={() => pickColor(preset.hex)}
                    title={preset.label}
                    aria-label={preset.label}
                    aria-pressed={isActive}
                    className={cn(
                      "relative min-tap sm:min-tap-0 rounded-md border transition-all active:scale-95 sm:h-10",
                      isActive
                        ? "border-foreground ring-foreground/40 ring-2 ring-offset-2"
                        : "border-border/60 hover:border-border",
                    )}
                    style={{ backgroundColor: preset.hex }}
                  />
                );
              })}
            </div>
          </div>

          <div className="flex items-end gap-3">
            <div className="flex-1">
              <Label
                htmlFor="colorize-section-hex"
                className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase"
              >
                Hex-värde
              </Label>
              <Input
                id="colorize-section-hex"
                value={hexInput}
                onChange={handleHexChange}
                placeholder="#F8FAFC"
                spellCheck={false}
                className="font-mono text-base md:text-sm"
              />
            </div>
            <div>
              <Label
                htmlFor="colorize-section-picker"
                className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase"
              >
                Plocka
              </Label>
              <input
                id="colorize-section-picker"
                type="color"
                value={chosenHex ?? "#F8FAFC"}
                onChange={(event) => pickColor(event.target.value)}
                className="border-border/60 min-tap sm:min-tap-0 w-14 cursor-pointer rounded-md border bg-transparent p-1 sm:h-9 sm:w-12"
              />
            </div>
          </div>
        </div>

        {error ? (
          <p
            role="alert"
            className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
          >
            {error}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isBusy}
          >
            Avbryt
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={isBusy || !canSubmit}
          >
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <PaintBucket className="h-4 w-4" />
                Färglägg
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
