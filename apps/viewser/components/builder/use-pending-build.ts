"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * use-pending-build — delad pending-build-state mellan FloatingChat
 * och Versions-tab.
 *
 * Bakgrund: `/api/prompt` är synkront och returnerar `runId` först
 * när hela bygget är klart. Det innebär att UI saknar handle på
 * den pågående buildet under hela tiden den körs. Konsekvensen är
 * att Versions-tab inte kan visa "version N är på gång" förrän
 * `/api/runs` har en `build-result.json` att läsa.
 *
 * Den här hooken är en lokal workaround: så fort en follow-up
 * triggas registrerar föräldern (`page.tsx`) ett pending-objekt
 * (siteId + prompt-snippet + tidstämpel + estimerad version) som
 * Versions-tab läser och renderar som en optimistisk "Bygger…"-rad
 * högst upp i listan. När bygget är klart eller misslyckas
 * rensas pending-state och Versions-tab refresh:ar via befintlig
 * `isBuilding`-watcher.
 *
 * Inga API-anrop, inga nya backend-endpoints. Pure UI-koordination.
 *
 * Användning:
 *   const { pendingBuild, beginPending, clearPending } = usePendingBuild();
 *   <FloatingChat
 *     onBuildStart={() => { setBuilding(true); beginPending({ ... }); }}
 *     onBuildEnd={() => { setBuilding(false); clearPending(); }}
 *   />
 *   <VersionsTab pendingBuild={pendingBuild} />
 */

export type PendingBuildState = {
  /** Sajten som byggs (matchas mot Versions-tab `siteId`-filter). */
  siteId: string;
  /**
   * Operatörens prompt, kortad till max 60 tecken för att inte
   * dominera pending-raden. Tom sträng är OK (t.ex. när en dialog
   * triggar bygget utan fri text — då visar UI bara "Bygger…").
   */
  promptSnippet: string;
  /** Date.now() när bygget startade. Används för "för 5 sekunder sedan"-display. */
  startedAt: number;
  /**
   * Föregående version + 1 (best-effort). Om föräldern inte vet
   * version får den passera in `null` och pending-raden visar bara
   * "Bygger…" utan versionsnummer.
   */
  estimatedVersion: number | null;
};

export type PendingBuildBegin = {
  siteId: string;
  promptSnippet?: string;
  estimatedVersion?: number | null;
};

const MAX_SNIPPET_LENGTH = 60;

function truncateSnippet(text: string | undefined): string {
  if (!text) return "";
  const trimmed = text.trim();
  if (trimmed.length <= MAX_SNIPPET_LENGTH) return trimmed;
  return `${trimmed.slice(0, MAX_SNIPPET_LENGTH - 1).trimEnd()}…`;
}

/**
 * Operator-vald baseRunId från "Iterera från denna"-knappen i
 * Versions-tab. Vi lyfter den till samma scope som pending-build-state
 * eftersom den följer en likadan livscykel: sätts när operatören
 * väljer en historisk version, skickas till FloatingChat som prop, och
 * rensas när bygget är klart eller operatören avbryter.
 *
 * `clearAt` är en best-effort-vakt mot stale-state: om operatören sätter
 * baseRunId men aldrig submitterar, släpps den efter 5 minuter så nästa
 * follow-up inte oavsiktligt iterar från en gammal version.
 */
export type PendingBaseRunIdState = {
  baseRunId: string;
  baseVersion: number | null;
  setAt: number;
};

const PENDING_BASE_RUN_TTL_MS = 5 * 60 * 1000;

export function usePendingBuild() {
  const [pendingBuild, setPendingBuild] = useState<PendingBuildState | null>(
    null,
  );
  const [pendingBaseRunId, setPendingBaseRunIdState] =
    useState<PendingBaseRunIdState | null>(null);

  const beginPending = useCallback((init: PendingBuildBegin) => {
    setPendingBuild({
      siteId: init.siteId,
      promptSnippet: truncateSnippet(init.promptSnippet),
      startedAt: Date.now(),
      estimatedVersion: init.estimatedVersion ?? null,
    });
  }, []);

  const clearPending = useCallback(() => {
    setPendingBuild(null);
  }, []);

  const setPendingBaseRunId = useCallback(
    (runId: string | null, version: number | null = null) => {
      if (runId === null) {
        setPendingBaseRunIdState(null);
        return;
      }
      setPendingBaseRunIdState({
        baseRunId: runId,
        baseVersion: version,
        setAt: Date.now(),
      });
    },
    [],
  );

  // Stale-vakt: släpp baseRunId om operatören aldrig hann skicka in.
  // Vi schemalägger alltid via setTimeout (även när TTL redan har
  // passerat — då sätter vi delay = 0) så React 19:s
  // set-state-in-effect-rule är nöjd. setState körs i timer-callbacken
  // som körs efter render, inte synkront i effect-bodyn.
  useEffect(() => {
    if (!pendingBaseRunId) return;
    const elapsed = Date.now() - pendingBaseRunId.setAt;
    const remaining = Math.max(0, PENDING_BASE_RUN_TTL_MS - elapsed);
    const setAtSnapshot = pendingBaseRunId.setAt;
    const timer = window.setTimeout(() => {
      setPendingBaseRunIdState((prev) =>
        prev && prev.setAt === setAtSnapshot ? null : prev,
      );
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [pendingBaseRunId]);

  return {
    pendingBuild,
    beginPending,
    clearPending,
    pendingBaseRunId,
    setPendingBaseRunId,
  };
}
