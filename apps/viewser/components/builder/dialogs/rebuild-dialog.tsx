"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";

import { classifyBuildStatus } from "@/components/prompt-builder";
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

/**
 * Bygg om sajten utan att ändra något i Project Input. Anropar
 * `/api/build` som kör `runBuild(siteId)` — ren re-render av samma
 * PI mot Quality Gate + Next.js-bygget. Användbart när:
 *
 *   - en variant- eller starter-uppdatering har landat och du vill
 *     se den utan att skriva en följdprompt,
 *   - du vill kontrollera att Quality Gate faktiskt går grön igen
 *     (post-merge sanity check),
 *   - eller bara verifiera reproducerbarhet.
 *
 * Backend-anropet returnerar `{ runId, buildResult }` direkt — vi
 * mappar buildResult-status till PromptBuildOutcome med samma
 * classifier som FloatingChat så onBuildDone-callbacken får
 * konsistent format.
 */

type RebuildDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
};

type BuildApiResponse = {
  runId?: string;
  buildResult?: { status?: string | null } | null;
  error?: string;
};

export function RebuildDialog({
  open,
  onOpenChange,
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
}: RebuildDialogProps) {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = useCallback(async () => {
    if (isBusy || !siteId) return;
    setIsBusy(true);
    setError(null);
    onBuildStart();
    try {
      const response = await fetch("/api/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ siteId }),
      });
      const payload = (await response.json()) as BuildApiResponse;
      if (!response.ok || !payload.runId) {
        throw new Error(
          payload.error ??
            `Build-anropet misslyckades (HTTP ${response.status})`,
        );
      }
      const outcome = classifyBuildStatus(payload.buildResult?.status ?? null);
      onBuildDone(payload.runId, outcome);
      onOpenChange(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt fel.");
    } finally {
      setIsBusy(false);
      onBuildEnd();
    }
  }, [isBusy, siteId, onBuildStart, onBuildEnd, onBuildDone, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>Bygg om sajten</DialogTitle>
          <DialogDescription>
            Kör samma Project Input igen utan ändringar. Bra för att verifiera
            att Quality Gate fortfarande går grön eller plocka upp uppdaterade
            variants/starters.
          </DialogDescription>
        </DialogHeader>

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
          <Button type="button" onClick={handleConfirm} disabled={isBusy}>
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4" />
                Bygg om
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
