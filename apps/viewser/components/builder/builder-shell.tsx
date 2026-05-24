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
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  onNewSite,
  onOpenConsole,
  onOpenHistory,
}: BuilderShellProps) {
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
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
        onBuildDone={onBuildDone}
      />
      <BuilderActions actions={actions} pulsing={isBuilding} side="left" />

      <VariantPickerDialog
        open={openDialog === "variant"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
        onBuildDone={onBuildDone}
      />
      <ColorPickerDialog
        open={openDialog === "color"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
        onBuildDone={onBuildDone}
      />
      <AssetUploaderDialog
        open={openDialog === "asset"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
        onBuildDone={onBuildDone}
      />
      <ScrapeUrlDialog
        open={openDialog === "scrape"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
        onBuildDone={onBuildDone}
      />
      <RebuildDialog
        open={openDialog === "rebuild"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
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
        onBuildStart={onBuildStart}
        onBuildEnd={onBuildEnd}
        onBuildDone={onBuildDone}
      />
    </>
  );
}
