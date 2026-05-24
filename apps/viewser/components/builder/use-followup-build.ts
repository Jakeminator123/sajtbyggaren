"use client";

import { useCallback, useState } from "react";

import {
  classifyBuildStatus,
  type PromptBuildOutcome,
} from "@/components/prompt-builder";

/**
 * Delad hook som alla builder-dialoger använder för att skicka en
 * follow-up-prompt till `/api/prompt` (mode: "followup"). Den
 * kapslar in fetch, error-handling och outcome-mapping så varje
 * dialog kan fokusera på sin egen UI istället för att duplicera
 * build-orchestration.
 *
 * FloatingChat har sin egen variant av samma flöde (med message-
 * tråd-state). Den lever kvar separat eftersom FloatingChat behöver
 * pending-meddelanden i en synlig logg, medan dialogerna stänger
 * sig själva när bygget startar och rapporterar via toast/inline-
 * error vid fel.
 *
 * Returnerar `{ runFollowup, isBusy, error, clearError }`.
 *
 * `runFollowup(prompt)` triggar onBuildStart innan fetchen, anropar
 * onBuildDone(runId, outcome) när bygget är klart, och garanterar
 * onBuildEnd i finally så page.tsx alltid får ren state oavsett
 * lyckat eller misslyckat bygge.
 */

type FollowupBuildOptions = {
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
};

type PromptApiResponse = {
  runId?: string;
  siteId?: string;
  version?: number | null;
  buildStatus?: string | null;
  briefSource?: string | null;
  error?: string;
};

export type RunFollowupResult =
  | {
      ok: true;
      runId: string;
      version: number | null;
      outcome: PromptBuildOutcome;
    }
  | { ok: false; error: string };

export function useFollowupBuild({
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
}: FollowupBuildOptions) {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const runFollowup = useCallback(
    async (prompt: string): Promise<RunFollowupResult> => {
      const trimmed = prompt.trim();
      if (!trimmed) {
        const msg = "Prompten är tom.";
        setError(msg);
        return { ok: false, error: msg };
      }
      if (isBusy) {
        const msg = "Ett bygge pågår redan.";
        setError(msg);
        return { ok: false, error: msg };
      }
      if (!siteId) {
        const msg = "Ingen aktiv sajt.";
        setError(msg);
        return { ok: false, error: msg };
      }

      setIsBusy(true);
      setError(null);
      onBuildStart();
      try {
        const response = await fetch("/api/prompt", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            prompt: trimmed,
            mode: "followup",
            siteId,
          }),
        });
        const payload = (await response.json()) as PromptApiResponse;
        if (!response.ok || !payload.runId) {
          const msg =
            payload.error ??
            `Prompt-anropet misslyckades (HTTP ${response.status})`;
          setError(msg);
          return { ok: false, error: msg };
        }
        const outcome = classifyBuildStatus(payload.buildStatus);
        onBuildDone(payload.runId, outcome);
        return {
          ok: true,
          runId: payload.runId,
          version: payload.version ?? null,
          outcome,
        };
      } catch (caught) {
        const msg = caught instanceof Error ? caught.message : "Okänt fel.";
        setError(msg);
        return { ok: false, error: msg };
      } finally {
        setIsBusy(false);
        onBuildEnd();
      }
    },
    [isBusy, siteId, onBuildStart, onBuildEnd, onBuildDone],
  );

  return { runFollowup, isBusy, error, clearError };
}
