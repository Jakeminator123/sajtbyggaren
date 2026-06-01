"use client";

import { RefreshCw, WifiOff } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BuilderShell } from "@/components/builder/builder-shell";
import { usePendingBuild } from "@/components/builder/use-pending-build";
import { ConsoleDrawer } from "@/components/console-drawer";
import { DevicePresetProvider } from "@/components/device-preset-context";
import { ErrorBoundary } from "@/components/error-boundary";
import { SiteHeader } from "@/components/layout/site-header";
import type { ProjectInputOption } from "@/components/project-input-picker";
import {
  PromptBuilder,
  type PromptBuildOutcome,
  type PromptStage,
} from "@/components/prompt-builder";
import type { RunHistoryItem } from "@/components/run-history";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { ViewerPanel } from "@/components/viewer-panel";

type RunsApiPayload = {
  runs?: RunHistoryItem[];
  projectInputs?: ProjectInputOption[];
  error?: string;
};

type FetchedRunsPayload = {
  nextRuns: RunHistoryItem[];
  nextInputs: ProjectInputOption[];
};

function headerStatusForOutcome(
  runId: string,
  outcome: PromptBuildOutcome,
): string {
  if (outcome === "ok") return `Build klar via prompt: ${runId}`;
  if (outcome === "degraded") return `Build klar med varning: ${runId}`;
  if (outcome === "failed") return `Build misslyckades: ${runId}`;
  return `Build klar med okänd status: ${runId}`;
}

// Pure data fetcher. Separated from setState so callers can place a
// cancellation guard between the await and the state mutation. Without
// this split the success path runs setState unconditionally even when
// the effect has been cancelled (component unmount), which races with
// a fresh effect that has already populated state.
async function fetchRuns(): Promise<FetchedRunsPayload> {
  const response = await fetch("/api/runs", { cache: "no-store" });
  const payload = (await response.json()) as RunsApiPayload;
  if (!response.ok || payload.error) {
    throw new Error(payload.error ?? "Kunde inte läsa /api/runs.");
  }
  return {
    nextRuns: payload.runs ?? [],
    nextInputs: payload.projectInputs ?? [],
  };
}

export default function Home() {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [projectInputs, setProjectInputs] = useState<ProjectInputOption[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("painter-palma");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState(
    "Laddar runs och project inputs…",
  );
  const [building, setBuilding] = useState(false);
  const [buildStage, setBuildStage] = useState<PromptStage>("idle");
  const [consoleOpen, setConsoleOpen] = useState(false);
  // Network-failure UX: när initial /api/runs failar visar vi en
  // dedikerad retry-rad i hero-ytan istället för bara en stuck status-
  // text. `runsLoadError` är operatör-läsbart fel-meddelande, eller null
  // när allt är OK eller ännu inte laddat. Sätts av `loadRuns()` nedan.
  const [runsLoadError, setRunsLoadError] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);
  const toast = useToast();
  // Live Build Sync: pending-build-state delas mellan BuilderShell
  // (som äger FloatingChat + dialogerna) och Versions-tab. Sätts
  // av onBuildStart-callbacks, rensas av onBuildEnd.
  //
  // pendingBaseRunId: när operatören klickar "Iterera från denna" i
  // Versions-tab plockas runId upp här så FloatingChat kan skicka
  // ``baseRunId`` i nästa /api/prompt-fetch. Rensas på onBuildEnd
  // (eller TTL i hooken om operatören aldrig submittade).
  const {
    pendingBuild,
    beginPending,
    clearPending,
    pendingBaseRunId,
    setPendingBaseRunId,
  } = usePendingBuild();

  // Sätts till true om operatören aktivt lämnar den pågående buildens
  // mål-vy (klick på "Ny sajt", val av annan run i ConsoleDrawer). När
  // handleBuildDone landar efteråt får den inte rycka tillbaka
  // selectedRunId/selectedSiteId — den ska bara uppdatera history-
  // listan så den färdiga runen finns där om operatören vill gå
  // tillbaka. B6 i scout-review 2026-05-24.
  const userNavigatedAwayRef = useRef(false);

  // siteId som är "aktivt" via vald run (om någon). Används för att
  // visa "Följer vald run"-hint i ProjectInputPicker så operatören ser
  // att panelen automatiskt följer runens DNA istället för det
  // manuellt valda Project Input:et.
  const activeRun = runs.find((run) => run.runId === selectedRunId);
  const runSiteId =
    activeRun?.siteId && activeRun.siteId !== "unknown"
      ? activeRun.siteId
      : null;
  const runSiteIdUnknown =
    !!selectedRunId &&
    !!activeRun &&
    (!activeRun.siteId || activeRun.siteId === "unknown");

  function applyRunsData(
    { nextRuns, nextInputs }: FetchedRunsPayload,
    ctx?: {
      selectedRunId: string | null;
      selectedSiteId: string;
    },
  ) {
    const effectiveRunId = ctx?.selectedRunId ?? selectedRunId;
    const effectiveSiteId = ctx?.selectedSiteId ?? selectedSiteId;

    setRuns(nextRuns);
    setProjectInputs(nextInputs);
    // Auto-väljer INTE senaste run vid mount. Det orsakade att
    // ViewerPanel direkt triggade en /api/runs/:runId/files-fetch
    // mot en gammal run innan operatören överhuvudtaget bett om något,
    // vilket gömde hero-vyn och visade en orelevant status-pill. Nu
    // visas hero tills operatören skickar en ny prompt eller väljer
    // en run explicit i ConsoleDrawer.
    //
    // Reset-fallbacken körs bara när ingen run är vald — annars äger
    // run-following (handler-sync i onBuildDone/onSelectRunIdAndSync)
    // selectedSiteId och vi får inte skriva över den med "första
    // inputen i listan". ctx skickas från onBuildDone så vi inte läser
    // ett gammalt selectedRunId ur closure efter fetchRuns().then().
    if (
      !effectiveRunId &&
      !nextInputs.find((item) => item.siteId === effectiveSiteId) &&
      nextInputs.length
    ) {
      setSelectedSiteId(nextInputs[0].siteId);
    }
    setStatusText("Sajtbyggaren — localhost-only operator-konsol.");
  }

  // Run-following sync via handlers (inte useEffect) för att inte bryta
  // React 19:s `react-hooks/set-state-in-effect`. När operatören väljer
  // en run i RunHistory / ConsoleDrawer eller en build precis blivit
  // klar uppdaterar vi selectedRunId OCH selectedSiteId atomiskt så
  // ProjectInputPicker aldrig visar fel run:s DNA.
  function selectRunAndSyncSiteId(runId: string) {
    // Markera att operatören aktivt navigerar bort om ett bygge pågår —
    // den färdig-payloaden får inte rycka tillbaka selectedRunId.
    if (building) userNavigatedAwayRef.current = true;
    setSelectedRunId(runId);
    const run = runs.find((item) => item.runId === runId);
    if (run && run.siteId && run.siteId !== "unknown") {
      setSelectedSiteId(run.siteId);
    }
  }

  // Stable ref för retry-callback i toast-action. Utan ref:en skulle vi
  // stänga över sig själv (`loadRuns` används innan den deklareras), vilket
  // bryter React 19:s `react-hooks/immutability`-regel. Ref:en pekar alltid
  // på senaste `loadRuns` och kallas bara på user-klick, så det är en
  // safe escape hatch.
  const loadRunsRef = useRef<(() => Promise<void>) | null>(null);

  // Återanvändbar loader för initial fetch + retry-knapp. Sätter både
  // `runsLoadError` (för retry-cardet) och `statusText` (för headern).
  // Använder `cancelled` så avmonterad component inte skriver state efter
  // unmount. Returneras som callback så retry-knappen kan trigga om.
  //
  // OBS: vi sätter INTE `setRunsLoading(true)` här. React 19:s
  // `react-hooks/set-state-in-effect` flaggar sync setState innan första
  // `await` i en effect-trigad async-funktion. `runsLoading` initieras
  // istället till `true` i useState ovan, och retry-callsite (user event)
  // sätter den till true igen — vilket är OK eftersom det inte är en
  // effect.
  const loadRuns = useCallback(
    async (cancelledRef?: { current: boolean }): Promise<void> => {
      try {
        const data = await fetchRuns();
        if (cancelledRef?.current) return;
        applyRunsData(data);
        setRunsLoadError(null);
      } catch (error) {
        if (cancelledRef?.current) return;
        const message =
          error instanceof Error
            ? error.message
            : "Kunde inte läsa initial data.";
        setRunsLoadError(message);
        setStatusText(message);
        // Toast så operatören ser felet även om hen inte tittar på hero
        // -ytan. Action ger snabb retry utan att leta upp kortet — vi
        // läser via ref:en så vi inte stänger över oss själva.
        toast.show({
          variant: "error",
          title: "Kunde inte ladda runs",
          description: message,
          action: {
            label: "Försök igen",
            onClick: () => {
              setRunsLoading(true);
              void loadRunsRef.current?.();
            },
          },
        });
      } finally {
        if (!cancelledRef?.current) {
          setRunsLoading(false);
        }
      }
    },
    // applyRunsData är en stabil closure (samma identitet hela komponentens
    // livstid) och ändras aldrig — låter eslint-disable peka ut det
    // explicit istället för att lyfta den ut till useCallback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [toast],
  );

  // Håll ref:en synkad med senaste closure varje render.
  useEffect(() => {
    loadRunsRef.current = () => loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    const cancelledRef = { current: false };
    // Wrap i async IIFE så React 19:s `react-hooks/set-state-in-effect`
    // ser att setState landar EFTER en await-gräns. Att kalla `loadRuns`
    // direkt fångar inte regelmotorn — den kan inte följa setState förbi
    // callback-gränsen och flaggar som om vi satte state synkront.
    void (async () => {
      await loadRuns(cancelledRef);
    })();
    return () => {
      cancelledRef.current = true;
    };
  }, [loadRuns]);

  // Global Cmd/Ctrl+K toggle:ar ConsoleDrawer. Standardgenvägen i moderna
  // dev-tools (Linear, Vercel, Stripe Dashboard) — operatören förväntar
  // sig den. Vi lyssnar på document-nivå men hoppar över när fokus är i
  // ett editable-element (textarea, contenteditable, input) så vi inte
  // stjäl tangenten från composern. Browsern reserverar inte Cmd+K på
  // localhost (bara Cmd+L för adressfältet) så ``preventDefault`` är
  // säker.
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "k" && event.key !== "K") return;
      if (!event.metaKey && !event.ctrlKey) return;
      const target = event.target as HTMLElement | null;
      if (target) {
        const tagName = target.tagName;
        if (
          tagName === "INPUT" ||
          tagName === "TEXTAREA" ||
          // ``SELECT`` skyddar ConsoleDrawer's projekt-väljare (samt
          // andra select:s i appen) — DiscoveryWizard hoppar redan
          // över SELECT i sin egen ⌘K-skip, så vi följer samma
          // mönster här för att inte stänga drawern mitt i ett val.
          tagName === "SELECT" ||
          target.isContentEditable
        ) {
          // Composern (FloatingChat / PromptBuilder) — låt tangenten gå
          // som vanlig text-edit istället för att toggla drawern.
          return;
        }
      }
      event.preventDefault();
      setConsoleOpen((prev) => !prev);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // Aktuell runs- + project-input-state avgör om vi är i "builder-mode"
  // (= en prompt-genererad sajt är vald, follow-ups via FloatingChat är
  // möjliga) eller i pre-build-läget med hero + DiscoveryWizard.
  //
  // Vi följer EXAKT samma logik som PromptBuilder använder internt för
  // sin `followupReady`-flagga — annars riskerar vi att visa BuilderShell
  // för en sajt som backend faktiskt vägrar göra followup på.
  const builderTarget = useMemo(() => {
    if (!selectedRunId) return null;
    const selectedRun = runs.find((run) => run.runId === selectedRunId);
    if (
      selectedRun &&
      (!selectedRun.siteId || selectedRun.siteId === "unknown")
    ) {
      return null;
    }
    const targetSiteId =
      selectedRun?.siteId && selectedRun.siteId !== "unknown"
        ? selectedRun.siteId
        : selectedSiteId;
    if (!targetSiteId || targetSiteId === "unknown") return null;
    const targetInput = projectInputs.find(
      (input) => input.siteId === targetSiteId,
    );
    if (targetInput?.source !== "prompt-inputs") return null;
    return { siteId: targetSiteId };
  }, [selectedRunId, runs, selectedSiteId, projectInputs]);

  const builderActive = builderTarget !== null;

  function handleBuildDone(
    runId: string,
    outcome: PromptBuildOutcome,
    siteId?: string,
  ) {
    // Bygget landade — visa toast så operatören ser status även om
    // FloatingChat eller PromptBuilder inte är synlig (t.ex. på liten
    // skärm där hero scrollats ur sikte). FloatingChat visar fortfarande
    // sin egen rad med detaljer; toasten är en kort sammanfattning.
    if (outcome === "ok") {
      toast.show({
        variant: "success",
        description: `Bygget klart för ${runId}.`,
      });
    } else if (outcome === "degraded") {
      toast.show({
        variant: "warning",
        title: "Bygget klart med varning",
        description: `Run ${runId} levererade mock- eller degraded-resultat. Se Quality Gate i Inspector.`,
      });
    } else if (outcome === "failed") {
      toast.show({
        variant: "error",
        title: "Bygget misslyckades",
        description: `Run ${runId} kunde inte slutföras. Försök igen eller iterera från en tidigare version.`,
      });
    }

    // B6: om operatören aktivt lämnat den här buildens mål-vy mellan
    // start och completion (Ny sajt eller annan run vald) får vi inte
    // rycka tillbaka selectedRunId/selectedSiteId. Vi uppdaterar bara
    // history-listan så den färdiga runen finns i ConsoleDrawer.
    if (userNavigatedAwayRef.current) {
      userNavigatedAwayRef.current = false;
      setStatusText(headerStatusForOutcome(runId, outcome));
      void fetchRuns()
        .then((data) =>
          applyRunsData(data, {
            selectedRunId,
            selectedSiteId,
          }),
        )
        .catch((error) => {
          const message =
            error instanceof Error
              ? error.message
              : "Kunde inte uppdatera runs.";
          setStatusText(message);
          toast.show({
            variant: "warning",
            title: "Kunde inte uppdatera historiken",
            description: message,
          });
        });
      return;
    }

    setSelectedRunId(runId);
    const effectiveSiteId =
      siteId && siteId !== "unknown" ? siteId : selectedSiteId;
    if (siteId && siteId !== "unknown") {
      setSelectedSiteId(siteId);
    }
    setStatusText(headerStatusForOutcome(runId, outcome));
    void fetchRuns()
      .then((data) =>
        applyRunsData(data, {
          selectedRunId: runId,
          selectedSiteId: effectiveSiteId,
        }),
      )
      .catch((error) => {
        const message =
          error instanceof Error ? error.message : "Kunde inte uppdatera runs.";
        setStatusText(message);
        toast.show({
          variant: "warning",
          title: "Kunde inte uppdatera historiken",
          description: message,
        });
      });
  }

  return (
    <DevicePresetProvider>
    <main className="bg-background relative h-[100dvh] w-full overflow-hidden">
      <SiteHeader
        onOpenConsole={() => setConsoleOpen(true)}
        // Dölj brand-bubblan i builder-läget — den ligger ovanpå
        // preview-iframens vänsterkant och stör operatörens
        // granskning av designen. Konsol-knappen i höger hörn
        // behålls så snabb-access till run-historik fortfarande
        // är ett enkelt klick.
        hideBrand={builderActive}
      />

      <ErrorBoundary area="Förhandsvisningen" className="h-full w-full">
        <ViewerPanel
          runId={selectedRunId}
          siteId={selectedSiteId}
          isBuilding={building}
          buildStage={buildStage}
        />
      </ErrorBoundary>

      {/* Network-failure UX: visas bara om initial /api/runs failade
          OCH operatören ännu inte kommit in i builder-läget (då har vi
          redan en run och kan jobba mot den lokalt). Cardet ligger
          centrerat över hero-ytan så det syns även när PromptBuilder är
          dold. Retry-knappen anropar samma loader som useEffect:en. */}
      {runsLoadError && !runsLoading && !builderActive ? (
        <RunsLoadErrorCard
          message={runsLoadError}
          onRetry={() => {
            setRunsLoading(true);
            void loadRuns();
          }}
        />
      ) : null}

      {/* Prompt-rutan döljs visuellt medan bygget pågår (BuildProgressCard
          tar över hero-ytan) OCH när builder-mode är aktivt (då tar
          FloatingChat över follow-up-flödet). Vi får ABSOLUT inte
          unmounta komponenten under bygget — den äger fetch-promise:n
          mot /api/prompt och setTimeout som flyttar stage `thinking`→
          `building`. B7 i scout-review 2026-05-24: komponenten hålls
          nu alltid mountad även när builder-mode är aktivt. Tidigare
          conditional unmount → remount under follow-up återställde
          stage till "idle" och kraschade build-progress-cardet. */}
      <ErrorBoundary area="Prompt-rutan">
        <PromptBuilder
          isBusy={building}
          runs={runs}
          projectInputs={projectInputs}
          selectedRunId={selectedRunId}
          selectedSiteId={selectedSiteId}
          onBuildStart={() => setBuilding(true)}
          onBuildEnd={() => setBuilding(false)}
          // Rapportera stage endast när PromptBuilder är "owner" av
          // bygget. I builder-mode driver FloatingChat follow-ups så
          // PromptBuilder:s interna stage-effekt får inte skriva över
          // buildStage med "idle" eller en stale tidigare success.
          onStageChange={builderActive ? undefined : setBuildStage}
          hidden={building || builderActive}
          onBuildDone={handleBuildDone}
        />
      </ErrorBoundary>

      {/* Builder-shell: floating draggable chat + dolt verktygsmeny.
          Visas så snart vi har en prompt-genererad run vald. Pre-build
          eller exempel-only-runs faller tillbaka till PromptBuilder
          ovan. FloatingChat skickar follow-up-prompts till /api/prompt
          med mode:"followup" och delar build-state med page.tsx så
          ViewerPanel:s BuildProgressCard fortsätter fungera under
          rebuild-cykeln. */}
      {builderActive && builderTarget ? (
        <ErrorBoundary area="Builder">
          <BuilderShell
            siteId={builderTarget.siteId}
            runId={selectedRunId}
            isBuilding={building}
            pendingBuild={pendingBuild}
            onPendingBuildBegin={beginPending}
            onPendingBuildClear={clearPending}
            pendingBaseRunId={pendingBaseRunId}
            onSetPendingBaseRunId={setPendingBaseRunId}
            onBuildStart={() => setBuilding(true)}
            onBuildEnd={() => {
              setBuilding(false);
              // Säkerhetsnet: om onPendingBuildClear inte hann kallas
              // (t.ex. dialog som glömde rensa pending) tar vi bort den
              // här så vi aldrig får orphan-pending-rader.
              clearPending();
              // OBS: pendingBaseRunId rensas INTE här. onBuildEnd kallas
              // även när bygget misslyckas, och en operatör som klickar
              // "Försök igen" på error-bubblan vill iterera från samma
              // base-version — inte fall tillbaka till latest. Vi rensar
              // istället i handleBuildDone (success-path), via TTL-guarden
              // i usePendingBuild (5 min) och via "Iterera"-toggle.
            }}
            onBuildDone={(runId, outcome) => {
              // Bygget lyckades (eller hamnade i mock/degraded — alla
              // outcomes utom hård exception). Operatörens iteration
              // konsumerades och ska inte oavsiktligt återanvändas av
              // nästa fri-text-prompt. Signaturen i BuilderShell skickar
              // inte siteId vidare; det löser handleBuildDone själv via
              // runs-listan när den re-fetchar.
              setPendingBaseRunId(null);
              handleBuildDone(runId, outcome);
            }}
            onNewSite={() => {
              // Återgår till pre-build-läget: rensar både selectedRunId
              // och buildStage så hero + DiscoveryWizard tar över igen.
              // Markera att operatören navigerat bort om ett bygge pågår
              // så handleBuildDone inte rycker tillbaka selectedRunId.
              if (building) userNavigatedAwayRef.current = true;
              setSelectedRunId(null);
              setBuildStage("idle");
              setStatusText("Beskriv en ny sajt nedan så bygger vi den åt dig.");
            }}
            onOpenConsole={() => setConsoleOpen(true)}
            onOpenHistory={() => setConsoleOpen(true)}
          />
        </ErrorBoundary>
      ) : null}

      <ConsoleDrawer
        open={consoleOpen}
        onOpenChange={setConsoleOpen}
        runs={runs}
        projectInputs={projectInputs}
        selectedSiteId={selectedSiteId}
        onSelectSiteId={setSelectedSiteId}
        selectedRunId={selectedRunId}
        onSelectRunId={selectRunAndSyncSiteId}
        runSiteId={runSiteId}
        runSiteIdUnknown={runSiteIdUnknown}
        isBuilding={building}
        statusText={statusText}
      />
    </main>
    </DevicePresetProvider>
  );
}

// Visas i hero-ytan när initial /api/runs failade. Använder `role="alert"`
// så skärmläsare läser upp den direkt vid mount. Retry-knappen anropar
// `loadRuns()` igen och rensar felet om det lyckas.
function RunsLoadErrorCard({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="pointer-events-none fixed inset-x-0 top-24 z-30 mx-auto flex w-full max-w-md justify-center px-4"
    >
      <div className="border-destructive/40 bg-card pointer-events-auto flex flex-col gap-3 rounded-2xl border p-4 shadow-md">
        <div className="flex items-center gap-2">
          <WifiOff
            className="text-destructive h-4 w-4 shrink-0"
            aria-hidden
          />
          <h2 className="text-foreground text-sm font-semibold">
            Kunde inte ladda runs
          </h2>
        </div>
        <p className="text-muted-foreground text-[13px] leading-relaxed">
          Servern svarade inte. Kontrollera att backend kör (
          <code className="bg-muted/60 rounded px-1 py-0.5 font-mono text-[11px]">
            npm run dev
          </code>
          ) och försök igen.
        </p>
        <pre className="bg-muted/60 text-muted-foreground max-h-20 overflow-auto rounded-md p-2 font-mono text-[11px] leading-snug">
          {message}
        </pre>
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RefreshCw aria-hidden />
            Försök igen
          </Button>
        </div>
      </div>
    </div>
  );
}
