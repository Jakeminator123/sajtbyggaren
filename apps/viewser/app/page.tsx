"use client";

import { useEffect, useState } from "react";

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

function headerStatusForOutcome(runId: string, outcome: PromptBuildOutcome): string {
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
  const [statusText, setStatusText] = useState("Laddar runs och project inputs…");
  const [building, setBuilding] = useState(false);
  const [buildStage, setBuildStage] = useState<PromptStage>("idle");
  const [consoleOpen, setConsoleOpen] = useState(false);

  function applyRunsData({ nextRuns, nextInputs }: FetchedRunsPayload) {
    setRuns(nextRuns);
    setProjectInputs(nextInputs);
    // Auto-väljer INTE senaste run vid mount. Det orsakade att
    // ViewerPanel direkt triggade en /api/runs/:runId/files-fetch
    // mot en gammal run innan operatören överhuvudtaget bett om något,
    // vilket gömde hero-vyn och visade en orelevant status-pill. Nu
    // visas hero tills operatören skickar en ny prompt eller väljer
    // en run explicit i ConsoleDrawer.
    if (!nextInputs.find((item) => item.siteId === selectedSiteId) && nextInputs.length) {
      setSelectedSiteId(nextInputs[0].siteId);
    }
    setStatusText("Sajtbyggaren — localhost-only operator-konsol.");
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
        const message = error instanceof Error ? error.message : "Kunde inte läsa initial data.";
        setStatusText(message);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="relative h-[100dvh] w-full overflow-hidden bg-background">
      <SiteHeader onOpenConsole={() => setConsoleOpen(true)} />

      <ViewerPanel
        runId={selectedRunId}
        isBuilding={building}
        buildStage={buildStage}
      />

      {/* Prompt-rutan döljs visuellt medan bygget pågår (BuildProgressCard
          tar över hero-ytan). Vi får ABSOLUT inte unmounta komponenten
          — den äger fetch-promise:n mot /api/prompt och setTimeout som
          flyttar stage `thinking`→`building`. Om vi unmountar tappar
          vi alla stage-rapporter och cardet fastnar på första steget.
          Därför skickar vi `hidden` istället för att conditional renda. */}
      <PromptBuilder
        isBusy={building}
        runs={runs}
        projectInputs={projectInputs}
        selectedRunId={selectedRunId}
        selectedSiteId={selectedSiteId}
        onBuildStart={() => setBuilding(true)}
        onBuildEnd={() => setBuilding(false)}
        onStageChange={setBuildStage}
        hidden={building}
        onBuildDone={(runId, outcome) => {
          setSelectedRunId(runId);
          // B44: never claim "Build klar" for a structured failure or
          // an unknown status. PromptBuilder classifies the outcome
          // from build-result.json:status; the header copy reflects
          // whichever bucket the run landed in so a failed run does
          // not look successful in the page status.
          setStatusText(headerStatusForOutcome(runId, outcome));
          void fetchRuns()
            .then(applyRunsData)
            .catch((error) => {
              const message =
                error instanceof Error
                  ? error.message
                  : "Kunde inte uppdatera runs.";
              setStatusText(message);
            });
        }}
      />

      <ConsoleDrawer
        open={consoleOpen}
        onOpenChange={setConsoleOpen}
        runs={runs}
        projectInputs={projectInputs}
        selectedSiteId={selectedSiteId}
        onSelectSiteId={setSelectedSiteId}
        selectedRunId={selectedRunId}
        onSelectRunId={setSelectedRunId}
        isBuilding={building}
        statusText={statusText}
      />
    </main>
  );
}
