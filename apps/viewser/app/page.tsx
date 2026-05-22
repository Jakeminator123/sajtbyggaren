"use client";

import { useEffect, useMemo, useState } from "react";

import { BuilderShell } from "@/components/builder/builder-shell";
import { ConsoleDrawer } from "@/components/console-drawer";
import { SiteHeader } from "@/components/layout/site-header";
import type { ProjectInputOption } from "@/components/project-input-picker";
import {
  PromptBuilder,
  type PromptBuildOutcome,
  type PromptStage,
} from "@/components/prompt-builder";
import type { RunHistoryItem } from "@/components/run-history";
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
    setSelectedRunId(runId);
    const run = runs.find((item) => item.runId === runId);
    if (run && run.siteId && run.siteId !== "unknown") {
      setSelectedSiteId(run.siteId);
    }
  }

  useEffect(() => {
    let cancelled = false;
    // Wrap refresh in an async IIFE so the React 19
    // `react-hooks/set-state-in-effect` rule sees subscription-style
    // updates (after await) rather than synchronous-in-effect. The
    // cancelled-guards on BOTH success and catch paths mirror the
    // pattern in viewer-panel / run-details-panel: a stale resolution
    // arriving after unmount must not write setState.
    void (async () => {
      try {
        const data = await fetchRuns();
        if (cancelled) return;
        applyRunsData(data);
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof Error
            ? error.message
            : "Kunde inte läsa initial data.";
        setStatusText(message);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    setSelectedRunId(runId);
    // Run-following: bygget gav oss både runId och siteId i payloaden, så
    // vi syncar selectedSiteId direkt. Det går inte att gå via
    // selectRunAndSyncSiteId() här eftersom den nya run:en ännu inte
    // hunnit landa i `runs`-listan (fetchRuns körs först nedan), och
    // det är just den nya run:en vars siteId vi vill följa.
    const effectiveSiteId =
      siteId && siteId !== "unknown" ? siteId : selectedSiteId;
    if (siteId && siteId !== "unknown") {
      setSelectedSiteId(siteId);
    }
    // B44: never claim "Build klar" for a structured failure or
    // an unknown status. PromptBuilder/FloatingChat klassar outcome
    // från build-result.json:status; header-copyn reflekterar
    // resultatet så ett misslyckat bygge aldrig ser grönt ut.
    setStatusText(headerStatusForOutcome(runId, outcome));
    // Skicka ctx till applyRunsData så reset-fallbacken läser den
    // FRÄSCHA run-id/site-id-paret istället för closure-state från
    // innan setSelectedRunId/setSelectedSiteId. Mönstret kom från
    // origin/main:s inline-callback (PR #55, stale run-following fix).
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
      });
  }

  return (
    <main className="bg-background relative h-[100dvh] w-full overflow-hidden">
      <SiteHeader onOpenConsole={() => setConsoleOpen(true)} />

      <ViewerPanel
        runId={selectedRunId}
        siteId={selectedSiteId}
        isBuilding={building}
        buildStage={buildStage}
      />

      {/* Prompt-rutan döljs visuellt medan bygget pågår (BuildProgressCard
          tar över hero-ytan) OCH när builder-mode är aktivt (då tar
          FloatingChat över follow-up-flödet). Vi får ABSOLUT inte
          unmounta komponenten under bygget — den äger fetch-promise:n
          mot /api/prompt och setTimeout som flyttar stage `thinking`→
          `building`. Om vi unmountar mid-build tappar vi alla stage-
          rapporter och cardet fastnar på första steget. Därför skickar
          vi `hidden` istället för att conditional renda. När builder-
          mode är aktivt och inget initial-bygge pågår är det säkert
          att unmounta — då tar FloatingChat över helt. */}
      {builderActive && !building ? null : (
        <PromptBuilder
          isBusy={building}
          runs={runs}
          projectInputs={projectInputs}
          selectedRunId={selectedRunId}
          selectedSiteId={selectedSiteId}
          onBuildStart={() => setBuilding(true)}
          onBuildEnd={() => setBuilding(false)}
          onStageChange={setBuildStage}
          hidden={building || builderActive}
          onBuildDone={handleBuildDone}
        />
      )}

      {/* Builder-shell: floating draggable chat + dolt verktygsmeny.
          Visas så snart vi har en prompt-genererad run vald. Pre-build
          eller exempel-only-runs faller tillbaka till PromptBuilder
          ovan. FloatingChat skickar follow-up-prompts till /api/prompt
          med mode:"followup" och delar build-state med page.tsx så
          ViewerPanel:s BuildProgressCard fortsätter fungera under
          rebuild-cykeln. */}
      {builderActive && builderTarget ? (
        <BuilderShell
          siteId={builderTarget.siteId}
          runId={selectedRunId}
          isBuilding={building}
          onBuildStart={() => setBuilding(true)}
          onBuildEnd={() => setBuilding(false)}
          onBuildDone={handleBuildDone}
          onNewSite={() => {
            // Återgår till pre-build-läget: rensar både selectedRunId
            // och buildStage så hero + DiscoveryWizard tar över igen.
            setSelectedRunId(null);
            setBuildStage("idle");
            setStatusText("Beskriv en ny sajt nedan så bygger vi den åt dig.");
          }}
          onOpenConsole={() => setConsoleOpen(true)}
          onOpenHistory={() => setConsoleOpen(true)}
        />
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
  );
}
