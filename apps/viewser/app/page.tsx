"use client";

import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat-panel";
import { DossierPicker, type DossierOption } from "@/components/dossier-picker";
import { RunHistory, type RunHistoryItem } from "@/components/run-history";
import { TokenMeter } from "@/components/token-meter";
import { ViewerPanel } from "@/components/viewer-panel";

type RunsApiPayload = {
  runs?: RunHistoryItem[];
  dossiers?: DossierOption[];
  error?: string;
};

export default function Home() {
  const [runs, setRuns] = useState<RunHistoryItem[]>([]);
  const [dossiers, setDossiers] = useState<DossierOption[]>([]);
  const [selectedDossierId, setSelectedDossierId] = useState("painter-palma");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("Laddar runs och dossiers...");

  async function refreshRuns() {
    const response = await fetch("/api/runs", { cache: "no-store" });
    const payload = (await response.json()) as RunsApiPayload;
    if (!response.ok || payload.error) {
      throw new Error(payload.error ?? "Kunde inte läsa /api/runs.");
    }

    const nextRuns = payload.runs ?? [];
    const nextDossiers = payload.dossiers ?? [];
    setRuns(nextRuns);
    setDossiers(nextDossiers);

    if (!selectedRunId && nextRuns.length > 0) {
      setSelectedRunId(nextRuns[0].runId);
    }
    if (!nextDossiers.find((item) => item.siteId === selectedDossierId) && nextDossiers.length) {
      setSelectedDossierId(nextDossiers[0].siteId);
    }
    setStatusText("Redo.");
  }

  useEffect(() => {
    void refreshRuns().catch((error) => {
      const message = error instanceof Error ? error.message : "Kunde inte läsa initial data.";
      setStatusText(message);
    });
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
        <DossierPicker
          dossiers={dossiers}
          selectedDossierId={selectedDossierId}
          onSelect={setSelectedDossierId}
        />
        <RunHistory
          runs={runs}
          selectedRunId={selectedRunId}
          onSelect={(runId) => setSelectedRunId(runId)}
        />
      </section>

      <section className="grid flex-1 gap-4 md:grid-cols-2">
        <ChatPanel
          dossierId={selectedDossierId}
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
