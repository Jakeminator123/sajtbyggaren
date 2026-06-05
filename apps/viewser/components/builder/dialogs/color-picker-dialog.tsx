"use client";

import { Loader2, Palette } from "lucide-react";
import { useCallback, useState } from "react";

import { useFollowupBuild } from "@/components/builder/use-followup-build";
import type { PromptBuildOutcome } from "@/components/prompt-builder";
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
 * Byt primärfärg i sajten genom att skicka en strukturerad
 * follow-up-prompt. Vi gör inget magiskt på frontenden — backend-
 * pipelinen tolkar prompten ("ändra primärfärgen till #2D5F3F")
 * och uppdaterar Project Input + bygger om.
 *
 * UX: 6 förvalda svatch-rutor för snabb iteration + native HTML
 * color input för fri lek. Båda uppdaterar samma `color`-state.
 * Hex-textfält gör att operatören kan klistra in ett varumärkes-
 * värde direkt.
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

type ColorPickerDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
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
  const [color, setColor] = useState<string>("#2D5F3F");
  const [hexInput, setHexInput] = useState<string>("#2D5F3F");
  const { runFollowup, isBusy, error } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const handlePresetClick = useCallback((hex: string) => {
    setColor(hex);
    setHexInput(hex);
  }, []);

  const handleHexChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const raw = event.target.value;
      setHexInput(raw);
      if (HEX_PATTERN.test(raw)) {
        setColor(raw);
      }
    },
    [],
  );

  const handleNativePickerChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const next = event.target.value;
      setColor(next);
      setHexInput(next);
    },
    [],
  );

  const handleSubmit = useCallback(async () => {
    if (!HEX_PATTERN.test(hexInput)) return;
    const prompt = `Ändra sajtens primärfärg till ${color}. Behåll övrig design intakt, men uppdatera knapp-, länk- och accentfärger så de matchar.`;
    const result = await runFollowup(prompt);
    if (result.ok) onOpenChange(false);
  }, [color, hexInput, runFollowup, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Byt primärfärg</DialogTitle>
          <DialogDescription>
            Välj en färg så bygger vi om sajten med uppdaterade knappar, länkar
            och accenter.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div>
            <Label className="text-muted-foreground mb-2 block text-[11px] tracking-tight uppercase">
              Förslag
            </Label>
            <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
              {PRESET_PALETTE.map((preset) => {
                const isActive =
                  color.toLowerCase() === preset.hex.toLowerCase();
                return (
                  <button
                    key={preset.hex}
                    type="button"
                    onClick={() => handlePresetClick(preset.hex)}
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
                value={color}
                onChange={handleNativePickerChange}
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
            disabled={isBusy || !HEX_PATTERN.test(hexInput)}
          >
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <Palette className="h-4 w-4" />
                Använd färg
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
