"use client";

import { useEffect, useState } from "react";

import {
  ProjectInputPicker,
  type ProjectInputOption,
} from "@/components/project-input-picker";
import { PromptBuilder } from "@/components/prompt-builder";
import { RunDetailsPanel } from "@/components/run-details-panel";
import { RunHistory, type RunHistoryItem } from "@/components/run-history";
import { TokenMeter } from "@/components/token-meter";
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
  const [statusText, setStatusText] = useState("Laddar runs och project inputs...");
  const [building, setBuilding] = useState(false);

  function applyRunsData({ nextRuns, nextInputs }: FetchedRunsPayload) {
    setRuns(nextRuns);
    setProjectInputs(nextInputs);
    if (!selectedRunId && nextRuns.length > 0) {
      setSelectedRunId(nextRuns[0].runId);
    }
    if (!nextInputs.find((item) => item.siteId === selectedSiteId) && nextInputs.length) {
      setSelectedSiteId(nextInputs[0].siteId);
    }
    setStatusText("Sajtbyggaren — localhost-only operator-prototype.");
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
    <main className="flex min-h-screen flex-col gap-4 p-4">
      <header className="grid gap-3 md:grid-cols-[1fr_auto]">
        <div className="flex flex-col justify-center">
          <h1 className="text-2xl font-semibold">Sajtbyggaren</h1>
          <p className="text-sm text-muted-foreground">{statusText}</p>
        </div>
        <TokenMeter />
      </header>

      <section className="grid gap-3 md:grid-cols-2">
        <ProjectInputPicker
          inputs={projectInputs}
          selectedSiteId={selectedSiteId}
          onSelect={setSelectedSiteId}
        />
        <RunHistory
          runs={runs}
          selectedRunId={selectedRunId}
          onSelect={(runId) => setSelectedRunId(runId)}
          isBuilding={building}
        />
      </section>

      <section>
        <PromptBuilder
          isBusy={building}
          onBuildStart={() => setBuilding(true)}
          onBuildEnd={() => setBuilding(false)}
          onBuildDone={(runId) => {
            setSelectedRunId(runId);
            setStatusText(`Build klar via prompt: ${runId}`);
            void fetchRuns()
              .then(applyRunsData)
              .catch((error) => {
                const message = error instanceof Error ? error.message : "Kunde inte uppdatera runs.";
                setStatusText(message);
              });
          }}
        />
      </section>

      <section className="grid flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ViewerPanel runId={selectedRunId} />
        <RunDetailsPanel runId={selectedRunId} />
      </section>
    </main>
  );
}
