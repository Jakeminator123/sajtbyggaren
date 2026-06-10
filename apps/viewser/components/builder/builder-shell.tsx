"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  BuilderActions,
  type BuilderAction,
} from "@/components/builder/builder-actions";
import {
  AddModuleDialog,
  AskAiDialog,
  AssetUploaderDialog,
  ColorPickerDialog,
  RebuildDialog,
  ScrapeUrlDialog,
  VariantPickerDialog,
} from "@/components/builder/dialogs";
import { FloatingChat } from "@/components/builder/floating-chat";
import { SiteInspectorSheet } from "@/components/builder/inspector";
import type { OnFollowupBuildDone } from "@/components/builder/use-followup-build";
import type {
  PendingBaseRunIdState,
  PendingBuildBegin,
  PendingBuildState,
} from "@/components/builder/use-pending-build";
import type { PromptStage } from "@/components/prompt-builder";
import { usePreviewInspector } from "@/components/preview-inspector-context";

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
  // Bär nu den optionella visible-effect-signalen (dialog-vägen) så studio-
  // toasten kan vara ärlig; FloatingChat anropar fortfarande 2-arg (oförändrat).
  onBuildDone: OnFollowupBuildDone;
  /**
   * Rapporterar bygg-stage uppåt så page.tsx kan driva BuildProgressCard
   * under follow-ups. FloatingChat förfinar via trace.ndjson; alla
   * bygg-triggers (dialoger m.fl.) återställer stage till "thinking" via
   * handleBuildStart så stegmarkören aldrig visar föregående bygges
   * sista stage.
   */
  onStageChange?: (stage: PromptStage) => void;
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
  | "module"
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
  onStageChange,
  onNewSite,
  onOpenConsole,
  onOpenHistory,
}: BuilderShellProps) {
  // Preview-inspector-state — destruktureras före handleBuildEnd som
  // refererar setPlacementBuildActive i sin deps-array.
  const {
    placementPickResolvedSignal,
    placementRequester,
    lastPlacementPick,
    previewUrl: inspectorPreviewUrl,
    inspectModeActive,
    setInspectModeActive,
    setPlacementBuildActive,
  } = usePreviewInspector();

  // Wrappar onBuildStart så den även registrerar pending-build-state
  // åt Versions-tab. Föräldern (page.tsx) får en utvidgad signatur som
  // innehåller siteId + ev. prompt-snippet. Befintliga dialoger som
  // bara vill säga "ett bygge startade" passerar tom snippet.
  const handleBuildStart = useCallback(
    (init?: { promptSnippet?: string; estimatedVersion?: number | null }) => {
      onBuildStart();
      // Återställ stegmarkören vid varje byggstart (FloatingChat ELLER en
      // dialog) så BuildProgressCard inte fryser på föregående bygges
      // sista stage. FloatingChat förfinar sedan till "building" via trace.
      onStageChange?.("thinking");
      onPendingBuildBegin({
        siteId,
        promptSnippet: init?.promptSnippet,
        estimatedVersion: init?.estimatedVersion ?? null,
      });
    },
    [onBuildStart, onStageChange, onPendingBuildBegin, siteId],
  );

  // Wrappar onBuildEnd så vi alltid rensar pending-state samtidigt
  // som föräldern markeras klar. Om bygget misslyckas hamnar vi
  // också här eftersom useFollowupBuild/FloatingChat alltid anropar
  // onBuildEnd i finally. OBS: placerings-banner-flaggan nollas INTE
  // här — ViewerPanel äger den (bannern ska leva genom finalize-fasen
  // tills previewn tagit över, annars studsar UI:t via stegkortet).
  const handleBuildEnd = useCallback(() => {
    onPendingBuildClear();
    onBuildEnd();
  }, [onBuildEnd, onPendingBuildClear]);

  // UX-glue (msg-0050 b): när ett bygge från en ANNAN yta än FloatingChat
  // (dialog/inspector) blir klart vill vi surfa chatten så operatören kan
  // skriva nästa följdprompt direkt. Vi bumpar en signal som FloatingChat
  // lyssnar på (expanderar ur minimerat läge + flyttar focus till composern).
  // FloatingChat:s egna byggen går via den råa onBuildDone och bumpar alltså
  // inte signalen (composern har redan focus där). Misslyckade byggen surfar
  // inte heller — då är felbubblan/feltoasten primär, inte iterera-vidare.
  const [focusComposerSignal, setFocusComposerSignal] = useState(0);
  const handleSurfaceBuildDone = useCallback<OnFollowupBuildDone>(
    (runId, outcome, visibleEffect) => {
      onBuildDone(runId, outcome, visibleEffect);
      if (outcome !== "failed") {
        setFocusComposerSignal((n) => n + 1);
      }
    },
    [onBuildDone],
  );
  const [openDialog, setOpenDialog] = useState<DialogId | null>(null);

  // Peka-i-previewn (platsval): dialogen stänger sig själv när draget
  // startar. När picken avslutas bumpar contexten
  // placementPickResolvedSignal — två utfall (operatörskrav 2026-06-10:
  // bekräftad placering ska INTE studsa tillbaka till dialogen):
  //
  //   - Bekräftad ("Placera här", lastPlacementPick satt): dialogen
  //     förblir stängd — den är fortfarande monterad och konsumerar
  //     picken + startar bygget i bakgrunden. Vi visar i stället den
  //     nordiska 0–100-bannern över previewn tills bygget är klart.
  //   - Avbruten (Esc/X, lastPlacementPick null): öppna dialogen igen
  //     så operatören landar där den var.
  //
  // setState:n deferras via setTimeout för React 19:s
  // react-hooks/set-state-in-effect-regel (samma mönster som
  // DevicePresetProvider-hydreringen).
  const lastPlacementSignalRef = useRef(placementPickResolvedSignal);
  useEffect(() => {
    if (placementPickResolvedSignal === lastPlacementSignalRef.current) return;
    lastPlacementSignalRef.current = placementPickResolvedSignal;
    if (lastPlacementPick) {
      const timerId = window.setTimeout(
        () => setPlacementBuildActive(true),
        0,
      );
      return () => window.clearTimeout(timerId);
    }
    const dialogId: DialogId = placementRequester === "asset" ? "asset" : "module";
    const timerId = window.setTimeout(() => setOpenDialog(dialogId), 0);
    return () => window.clearTimeout(timerId);
  }, [
    placementPickResolvedSignal,
    placementRequester,
    lastPlacementPick,
    setPlacementBuildActive,
  ]);

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
      // Peka i previewn (preview-inspector): togglar hover-inspektionen
      // ovanpå preview-iframen. Medvetet INGEN permanent knapp på
      // canvasen (operatörskrav 2026-06-10: ren preview-yta) — läget
      // startas härifrån och stängs med Esc/X i overlayns statusrad.
      // disabled när ingen server-nåbar preview-URL finns (StackBlitz-
      // läget publicerar ingen) eller medan ett bygge pågår.
      {
        id: "preview-inspect",
        label: inspectModeActive ? "Stäng granskningen" : "Granska previewn",
        description: inspectModeActive
          ? "Stänger hover-inspektionen"
          : "Hovra och identifiera element",
        icon: "preview-inspect",
        group: "Inspektera",
        onSelect: () => setInspectModeActive(!inspectModeActive),
        disabled: !inspectorPreviewUrl || isBuilding,
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
        id: "module",
        label: "Lägg till modul",
        description: "Dra in en sektion på en sida",
        icon: "module",
        group: "Innehåll",
        onSelect: openDialogFactory("module"),
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
      // OBS: tidigare fanns även ett "Versioner"-objekt här som öppnade
      // EXAKT samma console-drawer som "Konsol" (båda → setConsoleOpen(true))
      // — en dubblett som lovade två ingångar men gav en. Versions-bläddring
      // bor numera entydigt i inspector-panelens Versioner-tab samt i
      // hinten "Visa versioner" i FloatingChat (onShowVersions=onOpenHistory).
      // Konsolen behåller sin egen ärliga etikett (runs/inputs/tokens).
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
      openDialogFactory,
      onOpenConsole,
      onNewSite,
      inspectModeActive,
      setInspectModeActive,
      inspectorPreviewUrl,
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
        onStageChange={onStageChange}
        // Driver "Visa versioner" i första-gångs-hinten — samma ingång
        // som "Versioner" i Verktyg-menyn (ConsoleDrawer-historiken).
        onShowVersions={onOpenHistory}
        // Surfa chatten (expandera + fokusera composern) när ett bygge från
        // en dialog/inspector blir klart, så operatören kan iterera direkt.
        focusComposerSignal={focusComposerSignal}
        tools={
          <BuilderActions
            actions={actions}
            pulsing={isBuilding}
            variant="inline"
          />
        }
      />

      <VariantPickerDialog
        open={openDialog === "variant"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={handleSurfaceBuildDone}
        isBuilding={isBuilding}
        baseRunId={pendingBaseRunId?.baseRunId ?? null}
      />
      <ColorPickerDialog
        open={openDialog === "color"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={handleSurfaceBuildDone}
        isBuilding={isBuilding}
        baseRunId={pendingBaseRunId?.baseRunId ?? null}
      />
      <AssetUploaderDialog
        open={openDialog === "asset"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={handleSurfaceBuildDone}
        isBuilding={isBuilding}
        baseRunId={pendingBaseRunId?.baseRunId ?? null}
      />
      <AddModuleDialog
        open={openDialog === "module"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={handleSurfaceBuildDone}
        isBuilding={isBuilding}
        baseRunId={pendingBaseRunId?.baseRunId ?? null}
      />
      <ScrapeUrlDialog
        open={openDialog === "scrape"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={handleSurfaceBuildDone}
        isBuilding={isBuilding}
        baseRunId={pendingBaseRunId?.baseRunId ?? null}
      />
      <RebuildDialog
        open={openDialog === "rebuild"}
        onOpenChange={closeDialog}
        siteId={siteId}
        onBuildStart={handleBuildStart}
        onBuildEnd={handleBuildEnd}
        onBuildDone={handleSurfaceBuildDone}
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
        onBuildDone={handleSurfaceBuildDone}
      />
    </>
  );
}
