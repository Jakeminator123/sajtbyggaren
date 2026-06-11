"use client";

import { Loader2, Palette } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import {
  useFollowupBuild,
  type FollowupToolIntent,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
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
 * Byt sajtens färger (Färg-fliken i ToolsPopover, fas 2 2026-06-11).
 *
 * Två mål — primärfärg (knappar/länkar/accenter) och accentfärg
 * (detaljer/highlights) — väljs via en segmented control; färgkartan,
 * hex-fältet och native-pickern redigerar det valda målet. Operatören
 * kan sätta båda innan hen bygger: prompten nämner varje satt mål
 * ("Ändra sajtens primärfärg till #x och accentfärgen till #y.").
 *
 * Prompten tolkas numera DETERMINISTISKT i Python
 * (theme_directives._resolve_hex_literals): hex-literal + närmaste
 * föregående målord → brand.primaryColorHex/accentColorHex. Tidigare
 * krävde hex-prompts styleDirectiveModel-LLM:en — utan OPENAI_API_KEY
 * var dialogen en tyst no-op.
 *
 * Den strukturerade ``toolIntent`` (theme_change) skickas också med:
 * backend utan dispatch strippar fältet tyst (prompten bär samma
 * information), med dispatch slipper den regex:a fram hex ur fritext.
 *
 * Målen speglar exakt vad byggaren renderar (--primary/--accent +
 * skalor i tokens.py). Text-/bakgrundsfärg per element är fas 3
 * (per-sektion style-overrides) och erbjuds inte här förrän backend
 * finns — ärlighet före knappar.
 */

const PRESET_PALETTE: ReadonlyArray<{ hex: string; label: string }> = [
  { hex: "#0F172A", label: "Mörk slate" },
  { hex: "#1E40AF", label: "Djup blå" },
  { hex: "#2D5F3F", label: "Skogsgrön" },
  { hex: "#B45309", label: "Höstambar" },
  { hex: "#9333EA", label: "Plommonlila" },
  { hex: "#DC2626", label: "Signalröd" },
];

const HEX_PATTERN = /^#([0-9a-fA-F]{6})$/;

type ColorTarget = "primary" | "accent";

const TARGET_OPTIONS: ReadonlyArray<{
  id: ColorTarget;
  label: string;
  hint: string;
}> = [
  { id: "primary", label: "Primärfärg", hint: "Knappar, länkar, accenter" },
  { id: "accent", label: "Accentfärg", hint: "Detaljer och highlights" },
];

type ColorPickerDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: OnFollowupBuildDone;
  /** C2 globalt bygg-lås + C1 "Iterera från denna"-pin (från BuilderShell). */
  isBuilding?: boolean;
  baseRunId?: string | null;
};

export function ColorPickerDialog({
  open,
  onOpenChange,
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
}: ColorPickerDialogProps) {
  const [target, setTarget] = useState<ColorTarget>("primary");
  // null = målet är orört och utelämnas ur prompten/intentet. Bara mål
  // som operatören aktivt satt skickas — annars skulle ett rent
  // accent-byte alltid släpa med en default-primär.
  const [chosen, setChosen] = useState<Record<ColorTarget, string | null>>({
    primary: null,
    accent: null,
  });
  const [hexInput, setHexInput] = useState<string>("");
  const { runFollowup, isBusy, error, answer } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const activeColor = chosen[target];

  const setColorForTarget = useCallback(
    (hex: string) => {
      setChosen((prev) => ({ ...prev, [target]: hex }));
      setHexInput(hex);
    },
    [target],
  );

  const handleTargetSwitch = useCallback(
    (next: ColorTarget) => {
      setTarget(next);
      setHexInput(chosen[next] ?? "");
    },
    [chosen],
  );

  const handleHexChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const raw = event.target.value;
      setHexInput(raw);
      if (HEX_PATTERN.test(raw)) {
        setChosen((prev) => ({ ...prev, [target]: raw }));
      }
    },
    [target],
  );

  const handleNativePickerChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setColorForTarget(event.target.value);
    },
    [setColorForTarget],
  );

  // Minst ett mål satt + hex-fältet får inte stå i ett halvskrivet,
  // ogiltigt läge (tomt är ok — då gäller senast klickade swatch).
  const canSubmit = useMemo(() => {
    const anyChosen = chosen.primary !== null || chosen.accent !== null;
    const hexFieldOk = hexInput === "" || HEX_PATTERN.test(hexInput);
    return anyChosen && hexFieldOk;
  }, [chosen, hexInput]);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    const parts: string[] = [];
    if (chosen.primary) parts.push(`primärfärg till ${chosen.primary}`);
    if (chosen.accent) parts.push(`accentfärg till ${chosen.accent}`);
    const prompt =
      `Ändra sajtens ${parts.join(" och ")}. ` +
      "Behåll övrig design intakt, men uppdatera knapp-, länk- och accentfärger så de matchar.";
    // Strukturerad intent bredvid prompten — backend med specialist-
    // dispatch går rakt till tema-pipelinen utan texttolkning.
    const toolIntent: FollowupToolIntent = {
      tool: "theme_change",
      params: {
        ...(chosen.primary ? { primaryColorHex: chosen.primary } : {}),
        ...(chosen.accent ? { accentColorHex: chosen.accent } : {}),
      },
    };
    const result = await runFollowup(prompt, { toolIntent });
    if (result.ok) onOpenChange(false);
  }, [canSubmit, chosen, runFollowup, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Byt färger</DialogTitle>
          <DialogDescription>
            Välj primär- och/eller accentfärg så bygger vi om sajten med
            uppdaterade knappar, länkar och detaljer.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Målväljare: vilket färgmål redigeras just nu. En liten
              swatch i knappen visar redan valda färger per mål. */}
          <div
            role="radiogroup"
            aria-label="Färgmål"
            className="grid grid-cols-2 gap-2"
          >
            {TARGET_OPTIONS.map((option) => {
              const isActive = target === option.id;
              const value = chosen[option.id];
              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  onClick={() => handleTargetSwitch(option.id)}
                  className={cn(
                    "flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left transition active:scale-[0.98]",
                    "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                    isActive
                      ? "border-foreground bg-foreground/[0.04]"
                      : "border-border/60 hover:border-border",
                  )}
                >
                  <span className="flex items-center gap-1.5 text-[12.5px] font-medium tracking-tight">
                    {value ? (
                      <span
                        aria-hidden
                        className="border-border/60 inline-block h-3 w-3 rounded-full border"
                        style={{ backgroundColor: value }}
                      />
                    ) : null}
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
                  activeColor?.toLowerCase() === preset.hex.toLowerCase();
                return (
                  <button
                    key={preset.hex}
                    type="button"
                    onClick={() => setColorForTarget(preset.hex)}
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
                htmlFor="builder-color-hex"
                className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase"
              >
                Hex-värde
              </Label>
              <Input
                id="builder-color-hex"
                value={hexInput}
                onChange={handleHexChange}
                placeholder="#2D5F3F"
                spellCheck={false}
                className="font-mono text-base md:text-sm"
              />
            </div>
            <div>
              <Label
                htmlFor="builder-color-picker"
                className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase"
              >
                Plocka
              </Label>
              <input
                id="builder-color-picker"
                type="color"
                value={activeColor ?? "#2D5F3F"}
                onChange={handleNativePickerChange}
                className="border-border/60 min-tap sm:min-tap-0 w-14 cursor-pointer rounded-md border bg-transparent p-1 sm:h-9 sm:w-12"
              />
            </div>
          </div>
        </div>

        {answer ? (
          // B192: answer-only-svar (inget bygge kördes) är info, inte fel.
          <p
            role="status"
            className="text-foreground bg-muted/60 border-border rounded-md border px-3 py-2 text-[12px]"
          >
            {answer}
          </p>
        ) : null}
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
          <Button type="button" onClick={handleSubmit} disabled={isBusy || !canSubmit}>
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <Palette className="h-4 w-4" />
                Använd färger
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
