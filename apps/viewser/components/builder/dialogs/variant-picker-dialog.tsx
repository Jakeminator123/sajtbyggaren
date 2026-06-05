"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

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
import { cn } from "@/lib/utils";

/**
 * Visa alla aktiva discovery-kategorier (= scaffold + default-variant-
 * kombinationer) och låt operatören välja en ny grund-design. Vi
 * skickar valet som en strukturerad follow-up-prompt så briefModel
 * uppdaterar Project Input och builderns scaffold-router byter
 * scaffold/variant vid nästa bygge.
 *
 * Kategorierna kommer från `/api/discovery-options` som speglar
 * `governance/policies/discovery-taxonomy.v1.json` — samma källa
 * som DiscoveryWizards branschsteg använder. Inaktiva kategorier
 * (supportStatus !== "active") visas dimmat och kan inte väljas.
 */

type DiscoveryOption = {
  id: string;
  label: string;
  contentBranch: string;
  supportStatus: "active" | "fallback" | "planned" | "disabled";
  defaultVariantId: string;
  targetScaffoldLabel: string;
  fallbackLabel?: string;
};

type DiscoveryOptionsResponse = {
  options?: DiscoveryOption[];
  error?: string;
};

type VariantPickerDialogProps = {
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

export function VariantPickerDialog({
  open,
  onOpenChange,
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
}: VariantPickerDialogProps) {
  const [options, setOptions] = useState<DiscoveryOption[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { runFollowup, isBusy, error } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  // Hämta options när dialogen öppnas. Re-fetcha inte om vi redan
  // har dem — taxonomin är konstant per session.
  useEffect(() => {
    if (!open) return;
    if (options !== null) return;
    let cancelled = false;
    void (async () => {
      try {
        const response = await fetch("/api/discovery-options");
        const payload = (await response.json()) as DiscoveryOptionsResponse;
        if (cancelled) return;
        if (!response.ok || !payload.options) {
          throw new Error(payload.error ?? "Kunde inte ladda designval.");
        }
        setOptions(payload.options);
      } catch (caught) {
        if (cancelled) return;
        setLoadError(caught instanceof Error ? caught.message : "Okänt fel.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, options]);

  const handleSubmit = useCallback(async () => {
    if (!selectedId || !options) return;
    const chosen = options.find((o) => o.id === selectedId);
    if (!chosen) return;
    const prompt = `Byt sajtens design-grund till kategorin "${chosen.label}" (id: ${chosen.id}, scaffold: ${chosen.targetScaffoldLabel}, defaultVariantId: ${chosen.defaultVariantId}). Behåll allt innehåll, men anpassa layout, typografi och färgschema till den nya kategorins estetik.`;
    const result = await runFollowup(prompt);
    if (result.ok) {
      onOpenChange(false);
      setSelectedId(null);
    }
  }, [selectedId, options, runFollowup, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Byt designvariant</DialogTitle>
          <DialogDescription>
            Välj en ny design-grund. Innehållet behålls — bara scaffold, layout
            och variant byts.
          </DialogDescription>
        </DialogHeader>

        {loadError ? (
          <p
            role="alert"
            className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
          >
            {loadError}
          </p>
        ) : options === null ? (
          <div className="text-muted-foreground flex h-32 items-center justify-center gap-2 text-[12px]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Laddar designval…
          </div>
        ) : (
          <div className="max-h-[360px] overflow-y-auto pr-1">
            <ul className="flex flex-col gap-1.5">
              {options.map((option) => {
                const isActive = option.supportStatus === "active";
                const isSelected = option.id === selectedId;
                return (
                  <li key={option.id}>
                    <button
                      type="button"
                      disabled={!isActive || isBusy}
                      onClick={() => setSelectedId(option.id)}
                      className={cn(
                        "group flex w-full items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                        "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                        isSelected
                          ? "border-foreground bg-muted/60"
                          : "border-border/60 hover:border-border hover:bg-muted/40",
                        !isActive && "cursor-not-allowed opacity-50",
                      )}
                    >
                      <span
                        className={cn(
                          "mt-1 inline-flex h-3 w-3 shrink-0 items-center justify-center rounded-full border",
                          isSelected
                            ? "border-foreground bg-foreground"
                            : "border-border/80",
                        )}
                        aria-hidden
                      />
                      <span className="flex min-w-0 flex-1 flex-col leading-tight">
                        <span className="text-foreground text-[13px] font-medium tracking-tight">
                          {option.label}
                        </span>
                        <span className="text-muted-foreground mt-0.5 text-[11px]">
                          {option.targetScaffoldLabel}
                          {option.fallbackLabel
                            ? ` · fallback: ${option.fallbackLabel}`
                            : ""}
                        </span>
                      </span>
                      {!isActive ? (
                        <span className="text-muted-foreground bg-muted/60 mt-0.5 rounded-full px-2 py-0.5 font-mono text-[9px] tracking-wider uppercase">
                          {option.supportStatus}
                        </span>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

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
            disabled={isBusy || !selectedId}
          >
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Byt design
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
