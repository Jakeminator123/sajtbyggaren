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
import {
  useFollowupBuild,
  type FollowupToolIntent,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
import type {
  PendingBaseRunIdState,
  PendingBuildBegin,
  PendingBuildState,
} from "@/components/builder/use-pending-build";
import type { PromptStage } from "@/components/prompt-builder";
import { usePreviewInspector } from "@/components/preview-inspector-context";
import { useToast } from "@/components/ui/toast";

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

/**
 * Substantivfras per flyttbar sektionstyp för sektionsmenyns flytt-
 * followup. Samma EMPIRISKT router-verifierade promptformat som
 * AddModuleDialog ("Lägg till <noun> <överst|längst ner>.") — ADR 0042
 * gör att en explicit position på en redan rendrad sektion blir en
 * FLYTT, aldrig en dubblett. Nycklarna är modul-id:n ur
 * MOVABLE_SECTION_TYPES i preview-inspector-overlay.tsx.
 */
const MOVE_PROMPT_NOUNS: Record<string, string> = {
  gallery: "en galleri-sektion",
  "opening-hours": "en öppettider-sektion",
};

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
    markModeActive,
    setMarkModeActive,
    setPlacementBuildActive,
    sectionActionRequest,
    clearSectionAction,
  } = usePreviewInspector();
  const toast = useToast();

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

  // Sektionsmenyns kontext till dialogerna: hint-text för bilddialogen
  // ("Bilden gäller sektionen …") resp. förvald grovposition för
  // moduldialogen. Nollas när dialogen stängs så vanliga öppningar via
  // Verktyg-menyn aldrig ärver en gammal sektionskontext.
  const [assetSectionHint, setAssetSectionHint] = useState<string | null>(
    null,
  );
  const [moduleInitialPosition, setModuleInitialPosition] = useState<
    "top" | "bottom" | null
  >(null);
  // Composer-prefill för "Ändra text"-åtgärden: text + monoton nonce så
  // FloatingChat kan skilja två likadana prefills åt. Chippen läggs
  // redan av overlayn (addMarkedSection) — här fylls bara composern.
  const [composerPrefill, setComposerPrefill] = useState<{
    text: string;
    nonce: number;
  } | null>(null);

  // Flytt-followup (sektionsmenyns "Flytta överst/nederst"): kör
  // section_add direkt via samma seam som dialogerna. ADR 0042 ger
  // move-semantik när sektionen redan finns. Fel ytas via toast —
  // BuilderShell har ingen egen dialog-yta att rendera dem i.
  const { runFollowup: runSectionMove } = useFollowupBuild({
    siteId,
    onBuildStart: handleBuildStart,
    onBuildEnd: handleBuildEnd,
    onBuildDone: handleSurfaceBuildDone,
    isBuilding,
    baseRunId: pendingBaseRunId?.baseRunId ?? null,
  });

  const openDialogFactory = useCallback(
    (id: DialogId) => () => setOpenDialog(id),
    [],
  );

  const closeDialog = useCallback((next: boolean) => {
    if (!next) {
      setOpenDialog(null);
      setAssetSectionHint(null);
      setModuleInitialPosition(null);
    }
  }, []);

  // Konsumera sektionsmenyns åtgärds-request (overlayn → contexten →
  // hit). setTimeout(0) deferar setState:n ur effektkroppen
  // (react-hooks/set-state-in-effect, samma mönster som placement-
  // effekten ovan). requestedAt-nonce + ref-jämförelse gör att samma
  // request aldrig konsumeras två gånger.
  const lastSectionActionRef = useRef(0);
  useEffect(() => {
    const request = sectionActionRequest;
    if (!request || request.requestedAt === lastSectionActionRef.current) {
      return;
    }
    lastSectionActionRef.current = request.requestedAt;
    const timerId = window.setTimeout(() => {
      clearSectionAction();
      const heading = request.ref.headingText?.trim();
      const label = heading || request.ref.sectionId;
      if (request.action === "prefill-copy") {
        setComposerPrefill((prev) => ({
          text: `Ändra texten i sektionen "${label}": `,
          nonce: (prev?.nonce ?? 0) + 1,
        }));
        return;
      }
      if (request.action === "asset") {
        setAssetSectionHint(`Bilden gäller sektionen "${label}".`);
        setOpenDialog("asset");
        return;
      }
      if (request.action === "module") {
        setModuleInitialPosition(request.position ?? "bottom");
        setOpenDialog("module");
        return;
      }
      // "move": kör followup direkt — overlayn visar bara alternativet
      // för sektioner i backend-allowlisten, men vi gate:ar ärligt en
      // gång till mot promptnoun-kartan i stället för att gissa.
      const sectionType = request.sectionType;
      const noun = sectionType ? MOVE_PROMPT_NOUNS[sectionType] : undefined;
      if (!sectionType || !noun) return;
      const position = request.position ?? "top";
      const prompt =
        `Lägg till ${noun} ` +
        `${position === "top" ? "överst" : "längst ner"}. ` +
        "Behåll övrig design, copy och struktur intakt.";
      const toolIntent: FollowupToolIntent = {
        tool: "section_add",
        params: { sectionType, position },
      };
      void runSectionMove(prompt, { toolIntent }).then((result) => {
        if (!result.ok) {
          toast.show({
            description: result.error,
            variant: result.isAnswer ? "info" : "error",
          });
        }
      });
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [sectionActionRequest, clearSectionAction, runSectionMove, toast]);

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
      // Markera modul (sektionsmarkering i preview): klick på en sektion
      // skapar en strukturerad markering {routeId, sectionId} som visas
      // som chip i chatten och följer med nästa följdprompt som
      // markedSections[]. Samma rena-canvas-princip som granskningen.
      {
        id: "preview-mark",
        label: markModeActive ? "Avsluta markeringen" : "Markera modul",
        description: markModeActive
          ? "Stänger modulmarkeringen"
          : "Klicka en sektion → chip i chatten",
        icon: "preview-inspect",
        group: "Inspektera",
        onSelect: () => setMarkModeActive(!markModeActive),
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
      markModeActive,
      setMarkModeActive,
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
        // Sektionsmenyns "Ändra text"-åtgärd: förifyll composern med en
        // promptstart för den klickade sektionen (chippen är redan lagd).
        composerPrefill={composerPrefill}
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
        initialHint={assetSectionHint}
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
        initialPositionId={moduleInitialPosition}
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
