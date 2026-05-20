"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Hook som fetchar /api/runs/[runId]/artifacts när inspectorn öppnas.
 * Returnerar siteBrief, sitePlan, buildResult, qualityResult,
 * repairResult i de paketerade `Record<string, unknown>`-formerna
 * från `readRunArtefacts`. Vi normaliserar inte här — varje tab
 * narrowar shapes som den faktiskt använder med små typer.
 *
 * Re-fetchar när `runId` ändras eller när inspectorn öppnas igen
 * (open false → true) så ny build-status syns direkt efter ett
 * "Bygg om".
 */

export type RunArtefactBundle = {
  runId: string;
  buildResult: Record<string, unknown> | null;
  qualityResult: Record<string, unknown> | null;
  repairResult: Record<string, unknown> | null;
  siteBrief: Record<string, unknown> | null;
  sitePlan: Record<string, unknown> | null;
  missingArtefacts: string[];
};

type FetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; bundle: RunArtefactBundle }
  | { status: "error"; error: string };

type UseRunArtefactsResult = {
  state: FetchState;
  refresh: () => void;
};

export function useRunArtefacts(
  runId: string | null,
  open: boolean,
): UseRunArtefactsResult {
  const [state, setState] = useState<FetchState>({ status: "idle" });
  const [reloadToken, setReloadToken] = useState(0);

  const refresh = useCallback(() => {
    setReloadToken((prev) => prev + 1);
  }, []);

  // Auto-fetch när runId/open ändras + manuell refresh via token.
  // setState körs efter `await` så vi följer samma mönster som
  // resten av builder-laget (undviker React 19:s set-state-in-effect-
  // rule som triggar på sync setState i effect-body).
  useEffect(() => {
    if (!open) return;
    if (!runId) {
      let cancelled = false;
      void (async () => {
        await Promise.resolve();
        if (cancelled) return;
        setState({ status: "idle" });
      })();
      return () => {
        cancelled = true;
      };
    }

    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setState({ status: "loading" });
      try {
        const response = await fetch(`/api/runs/${runId}/artifacts`);
        const raw = (await response.json()) as unknown;
        if (cancelled) return;
        const errorField =
          raw && typeof raw === "object" && "error" in raw
            ? (raw as { error: unknown }).error
            : null;
        if (!response.ok || typeof errorField === "string") {
          throw new Error(
            typeof errorField === "string"
              ? errorField
              : `HTTP ${response.status}`,
          );
        }
        setState({ status: "ok", bundle: raw as RunArtefactBundle });
      } catch (caught) {
        if (cancelled) return;
        setState({
          status: "error",
          error: caught instanceof Error ? caught.message : "Okänt fel.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId, open, reloadToken]);

  return { state, refresh };
}
