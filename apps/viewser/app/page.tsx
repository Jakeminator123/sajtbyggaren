"use client";

import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat-panel";
import {
  ProjectInputPicker,
  type ProjectInputOption,
} from "@/components/project-input-picker";
import { RunHistory, type RunHistoryItem } from "@/components/run-history";
import { TokenMeter } from "@/components/token-meter";
import { ViewerPanel } from "@/components/viewer-panel";

type RunsApiPayload = {
  runs?: RunHistoryItem[];
  projectInputs?: ProjectInputOption[];
  error?: string;
};

export default function Home() {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [projectInputs, setProjectInputs] = useState<ProjectInputOption[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState("painter-palma");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("Laddar runs och project inputs...");

  async function refreshRuns() {
    const response = await fetch("/api/runs", { cache: "no-store" });
    const payload = (await response.json()) as RunsApiPayload;
    if (!response.ok || payload.error) {
      throw new Error(payload.error ?? "Kunde inte läsa /api/runs.");
    }

    const nextRuns = payload.runs ?? [];
    const nextInputs = payload.projectInputs ?? [];
    setRuns(nextRuns);
    setProjectInputs(nextInputs);

    if (!selectedRunId && nextRuns.length > 0) {
      setSelectedRunId(nextRuns[0].runId);
    }
    if (!nextInputs.find((item) => item.siteId === selectedSiteId) && nextInputs.length) {
      setSelectedSiteId(nextInputs[0].siteId);
    }
    setStatusText("Redo. Localhost-only operator-prototype.");
  }

  useEffect(() => {
    void refreshRuns().catch((error) => {
      const message = error instanceof Error ? error.message : "Kunde inte läsa initial data.";
      setStatusText(message);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="flex min-h-screen flex-col gap-4 p-4">
      <header className="grid gap-3 md:grid-cols-[1fr_auto]">
        <div className="flex flex-col justify-center">
          <h1 className="text-2xl font-semibold">Viewser MVP</h1>
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
        />
      </section>

      <section className="grid flex-1 gap-4 md:grid-cols-2">
        <ChatPanel
          siteId={selectedSiteId}
          onBuildDone={(runId) => {
            setSelectedRunId(runId);
            setStatusText(`Build klar: ${runId}`);
            void refreshRuns().catch((error) => {
              const message = error instanceof Error ? error.message : "Kunde inte uppdatera runs.";
              setStatusText(message);
            });
          }}
        />
        <ViewerPanel runId={selectedRunId} />
      </section>
    </main>
  );
}
