"use client";

import { useCallback, useMemo, useState } from "react";

import {
  BuilderActions,
  type BuilderAction,
} from "@/components/builder/builder-actions";
import {
  AskAiDialog,
  AssetUploaderDialog,
  ColorPickerDialog,
  RebuildDialog,
  ScrapeUrlDialog,
  VariantPickerDialog,
} from "@/components/builder/dialogs";
import { FloatingChat } from "@/components/builder/floating-chat";
import { SiteInspectorSheet } from "@/components/builder/inspector";
import type {
  PendingBaseRunIdState,
  PendingBuildBegin,
  PendingBuildState,
} from "@/components/builder/use-pending-build";
import type { PromptBuildOutcome } from "@/components/prompt-builder";

/**
 * BuilderShell är compositionen som tar över hela kant-ytan när
 * användaren har en byggd sajt på skärmen. Den renderar inte
 * iframen själv (den lever kvar i `ViewerPanel` och fyller
 * canvasen), utan lägger ovanpå:
 *
 * 1. `FloatingChat`  — draggable + minimizable chat-ruta som
 *    skickar follow-up-prompts till `/api/prompt` med
 *    `mode: "followup"` + nuvarande siteId.
 * 2. `BuilderActions` — minimal "Verktyg"-pill som expanderar
 *    till en grupperad meny med builder-funktioner:
 *      - Designval (variant, primärfärg)
 *      - Innehåll (bilduppladdning, URL-scrape)
 *      - Bygg & versioner (re-build, versionshistorik, konsol)
 *      - AI-hjälp (Fråga utan att bygga)
 *      - Sajt (Ny sajt)
 * 3. Sex dialog-komponenter som öppnas via menyn — varje dialog
 *    äger sin egen UI och triggar antingen useFollowupBuild-hooken
 *    (för bygg-utlösande actions) eller bara läs-anrop (Fråga AI).
 *
 * Alla actions delegerar till befintliga API-endpoints. Inga nya
 * backend-anrop introduceras av builder-laget.
 */

type BuilderShellProps = {
  /** Sajten som chatten gör follow-ups på. */
  siteId: string;
  /** Aktiv run-id, används för pulsering + framtida actions. */
  runId: string | null;
  isBuilding: boolean;
  /**
   * Pending build-state (Live Build Sync). Sätts av föräldern via
   * onPendingBuildBegin när en follow-up triggas, rensas via
   * onPendingBuildClear när bygget är klart eller misslyckas.
   * Versions-tab läser pendingBuild för att rendera optimistisk
   * "Bygger…"-rad högst upp i listan.
   */
  pendingBuild: PendingBuildState | null;
  onPendingBuildBegin: (init: PendingBuildBegin) => void;
  onPendingBuildClear: () => void;
  /**
   * "Iterera från denna"-tillstånd. När operatören klickar på en
   * versions-rad sätter Versions-tab denna; FloatingChat plockar
   * upp `baseRunId` och skickar i nästa /api/prompt-fetch.
   */
  pendingBaseRunId: PendingBaseRunIdState | null;
  onSetPendingBaseRunId: (
    runId: string | null,
    version?: number | null,
  ) => void;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
  /** Triggar att operatören vill börja om från intake-wizarden. */
  onNewSite: () => void;
  /** Öppnar ConsoleDrawer i fullt läge (run-historik + project inputs + token-meter). */
  onOpenConsole: () => void;
  /** Öppnar ConsoleDrawer fokuserat på run-historik för aktuell sajt. */
  onOpenHistory: () => void;
};

type DialogId =
  | "variant"
  | "color"
  | "asset"
  | "scrape"
  | "rebuild"
  | "ask"
  | "inspect";

export function BuilderShell({
  siteId,
  runId,
  isBuilding,
  pendingBuild,
  onPendingBuildBegin,
  onPendingBuildClear,
  pendingBaseRunId,
  onSetPendingBaseRunId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  onNewSite,
  onOpenConsole,
  onOpenHistory,
}: BuilderShellProps) {
  // Wrappar onBuildStart så den även registrerar pending-build-state
  // åt Versions-tab. Föräldern (page.tsx) får en utvidgad signatur som
  // innehåller siteId + ev. prompt-snippet. Befintliga dialoger som
  // bara vill säga "ett bygge startade" passerar tom snippet.
  const handleBuildStart = useCallback(
    (init?: { promptSnippet?: string; estimatedVersion?: number | null }) => {
      onBuildStart();
      onPendingBuildBegin({
        siteId,
        promptSnippet: init?.promptSnippet,
        estimatedVersion: init?.estimatedVersion ?? null,
      });
    },
    [onBuildStart, onPendingBuildBegin, siteId],
  );

  // Wrappar onBuildEnd så vi alltid rensar pending-state samtidigt
  // som föräldern markeras klar. Om bygget misslyckas hamnar vi
  // också här eftersom useFollowupBuild/FloatingChat alltid anropar
  // onBuildEnd i finally.
  const handleBuildEnd = useCallback(() => {
    onPendingBuildClear();
    onBuildEnd();
  }, [onBuildEnd, onPendingBuildClear]);
  const [openDialog, setOpenDialog] = useState<DialogId | null>(null);

  const openDialogFactory = useCallback(
    (id: DialogId) => () => setOpenDialog(id),
    [],
  );

  const closeDialog = useCallback((next: boolean) => {
    if (!next) setOpenDialog(null);
  }, []);

  const actions = useMemo<BuilderAction[]>(
    () => [
      // Inspektera (Nivå 3) — överst eftersom det är den primära
      // ingången till struktur, snabbprompts per sida/sektion,
      // dossier-rejects och Quality-findings.
      {
        id: "inspect",
        label: "Inspektera sajten",
        description: "Sidor, brief, dossiers, kvalitet",
        icon: "inspect",
        group: "Inspektera",
        onSelect: openDialogFactory("inspect"),
      },
      // Design
      {
        id: "variant",
        label: "Byt designvariant",
        description: "Annan scaffold + känsla",
        icon: "design",
        group: "Design",
        onSelect: openDialogFactory("variant"),
        disabled: isBuilding,
      },
      {
        id: "color",
        label: "Byt primärfärg",
        description: "Knappar, länkar, accenter",
        icon: "palette",
        group: "Design",
        onSelect: openDialogFactory("color"),
        disabled: isBuilding,
      },
      // Innehåll
      {
        id: "asset",
        label: "Ladda upp bild",
        description: "Logo, hero eller galleri",
        icon: "image",
        group: "Innehåll",
        onSelect: openDialogFactory("asset"),
        disabled: isBuilding,
      },
      {
        id: "scrape",
        label: "Hämta från URL",
        description: "Skrapa info från en sajt",
        icon: "globe",
        group: "Innehåll",
        onSelect: openDialogFactory("scrape"),
        disabled: isBuilding,
      },
      // Bygg & versioner
      {
        id: "rebuild",
        label: "Bygg om utan ändring",
        description: "Verifiera Quality Gate",
        icon: "rebuild",
        group: "Bygg",
        onSelect: openDialogFactory("rebuild"),
        disabled: isBuilding,
      },
      {
        id: "history",
        label: "Versioner",
        description: runId ? `Aktiv: ${runId}` : "Tidigare bygg",
        icon: "history",
        group: "Bygg",
        onSelect: onOpenHistory,
      },
      {
        id: "console",
        label: "Konsol",
        description: "Runs, project inputs, tokens",
        icon: "console",
        group: "Bygg",
        onSelect: onOpenConsole,
      },
      // AI-hjälp
      {
        id: "ask",
        label: "Fråga utan att bygga",
        description: "Bolla idéer först",
        icon: "ask",
        group: "AI",
        onSelect: openDialogFactory("ask"),
      },
      // Sajt
      {
        id: "new-site",
        label: "Ny sajt",
        description: "Börja om från wizarden",
        icon: "new-site",
        group: "Sajt",
        onSelect: onNewSite,
      },
    ],
    [
      isBuilding,
      runId,
      openDialogFactory,
      onOpenHistory,
      onOpenConsole,
      onNewSite,
    ],
  );

  return (
    <>
      {/* key={siteId} re-monterar FloatingChat när operatören byter
          aktiv sajt. Det nollställer message-tråden + composer-input
          utan att vi behöver setState-i-effekt (React 19:s
          react-hooks/set-state-in-effect-rule skulle flagga annars). */}
      <FloatingChat
        key={siteId}
        siteId={siteId}
        isBuilding={isBuilding}
        pendingBaseRunId={pendingBaseRunId}
        onClearBaseRunId={() => onSetPendingBaseRunId(null)}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
      <BuilderActions actions={actions} pulsing={isBuilding} side="left" />

      <VariantPickerDialog
        open={openDialog === "variant"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
      <ColorPickerDialog
        open={openDialog === "color"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
      <AssetUploaderDialog
        open={openDialog === "asset"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
      <ScrapeUrlDialog
        open={openDialog === "scrape"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
      <RebuildDialog
        open={openDialog === "rebuild"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
      <AskAiDialog
        open={openDialog === "ask"}
        onOpenChange={closeDialog}
        siteId={siteId}
      />
      <SiteInspectorSheet
        open={openDialog === "inspect"}
        onOpenChange={closeDialog}
        siteId={siteId}
        runId={runId}
        isBuilding={isBuilding}
        pendingBuild={pendingBuild}
        pendingBaseRunId={pendingBaseRunId}
        onSetPendingBaseRunId={onSetPendingBaseRunId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={onBuildDone}
      />
    </>
  );
}
