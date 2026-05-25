"use client";

import { useCallback, useState } from "react";

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

export function usePendingBuild() {
  const [pendingBuild, setPendingBuild] = useState<PendingBuildState | null>(
    null,
  );

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

  return { pendingBuild, beginPending, clearPending };
}
