"use client";

import { useEffect, useRef, useState } from "react";

import type { ProjectInputOption } from "@/components/project-input-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunHistoryItem } from "@/components/run-history";
import { Textarea } from "@/components/ui/textarea";

type PromptStage =
  | "idle"
  | "thinking"
  | "building"
  | "success"
  | "degraded"
  | "failed";
type PromptMode = "init" | "followup";

// PromptBuildOutcome mirrors the canonical statuses build_site.py and
// dev_generate.py write into build-result.json:status (see B44).
// Anything we cannot classify ("unknown") is surfaced as a degraded
// result so the operator never sees a false-success badge.
export type PromptBuildOutcome = "ok" | "degraded" | "failed" | "unknown";

type PromptApiPayload = {
  runId?: string;
  siteId?: string;
  projectId?: string;
  version?: number | null;
  briefSource?: string | null;
  buildStatus?: string | null;
  error?: string;
};

type PromptBuilderProps = {
  isBusy: boolean;
  runs: RunHistoryItem[];
  projectInputs: ProjectInputOption[];
  selectedRunId: string | null;
  selectedSiteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
};

// Map the wire `buildStatus` (any string from build-result.json) to
// the three operator-visible outcomes. "ok"/"mock-complete"/"skipped"
// count as success; "degraded" surfaces a warning; "failed" is an
// explicit failure; everything else (including null/missing) is
// reported as "unknown" and rendered as degraded so we never go green
// over an unrecognised status.
export function classifyBuildStatus(
  status: string | null | undefined,
): PromptBuildOutcome {
  if (status === "ok" || status === "mock-complete" || status === "skipped") {
    return "ok";
  }
  if (status === "degraded") return "degraded";
  if (status === "failed") return "failed";
  return "unknown";
}

function outcomeToStage(outcome: PromptBuildOutcome): PromptStage {
  if (outcome === "ok") return "success";
  if (outcome === "failed") return "failed";
  return "degraded";
}

export function PromptBuilder({
  isBusy,
  runs,
  projectInputs,
  selectedRunId,
  selectedSiteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
}: PromptBuilderProps) {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<PromptMode>("init");
  const [stage, setStage] = useState<PromptStage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<{
    runId: string;
    siteId: string;
    version: number | null;
    briefSource: string | null;
    buildStatus: string | null;
    outcome: PromptBuildOutcome;
  } | null>(null);
  const stageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const localBusy = stage === "thinking" || stage === "building";
  const disabled = isBusy || localBusy;
  const selectedRun = runs.find((run) => run.runId === selectedRunId);
  const targetSiteId =
    selectedRun?.siteId && selectedRun.siteId !== "unknown"
      ? selectedRun.siteId
      : selectedSiteId;
  const targetInput = projectInputs.find(
    (input) => input.siteId === targetSiteId,
  );
  const followupReady =
    targetSiteId.trim().length > 0 &&
    targetSiteId !== "unknown" &&
    targetInput?.source === "prompt-inputs";
  const idleButtonLabel =
    mode === "followup" ? "Skapa ny version" : "Bygg sajt från prompt";
  const buttonLabel = localBusy ? "Bygger sajt…" : idleButtonLabel;

  useEffect(() => {
    return () => {
      if (stageTimerRef.current) {
        clearTimeout(stageTimerRef.current);
      }
    };
  }, []);

  async function submitPrompt() {
    const cleaned = prompt.trim();
    if (!cleaned || disabled) return;
    if (mode === "followup" && !followupReady) {
      setError("Välj en prompt-genererad run eller siteId först.");
      return;
    }

    setError(null);
    setStage("thinking");
    onBuildStart();

    try {
      // The route does both phases sequentially: prompt -> Project Input
      // (runs briefModel) and then runs build_site.py. We expose two
      // visual stages so the operator can see which step is in flight
      // even though the network call is single-shot.
      if (stageTimerRef.current) {
        clearTimeout(stageTimerRef.current);
      }
      stageTimerRef.current = setTimeout(() => {
        stageTimerRef.current = null;
        setStage((current) =>
          current === "thinking" ? "building" : current,
        );
      }, 1500);

      const response = await fetch("/api/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: cleaned,
          mode,
          siteId: mode === "followup" ? targetSiteId : undefined,
        }),
      });
      const payload = (await response.json()) as PromptApiPayload;
      if (!response.ok || !payload.runId || !payload.siteId) {
        throw new Error(payload.error ?? "Prompt-anropet misslyckades.");
      }

      // B44: classify build status from build-result.json so the
      // operator UI distinguishes ok / degraded / failed instead of
      // showing "Build klar" for a structured failure (build-runner.ts
      // returns a runId on failed builds so the run still appears in
      // Run History).
      const outcome = classifyBuildStatus(payload.buildStatus);
      setStage(outcomeToStage(outcome));
      setLastResult({
        runId: payload.runId,
        siteId: payload.siteId,
        version: payload.version ?? null,
        briefSource: payload.briefSource ?? null,
        buildStatus: payload.buildStatus ?? null,
        outcome,
      });
      onBuildDone(payload.runId, outcome);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt fel.");
      setStage("failed");
    } finally {
      if (stageTimerRef.current) {
        clearTimeout(stageTimerRef.current);
        stageTimerRef.current = null;
      }
      onBuildEnd();
    }
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-base">Prompt → sajt</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 p-4">
        <p className="text-xs text-muted-foreground">
          Skriv en fri prompt så genererar vi minimal Project Input via
          briefModel och kör <code>scripts/build_site.py</code>. Välj ny sajt
          eller följdprompt på vald run/siteId. Generated Project Input + meta
          sparas i <code>data/prompt-inputs/</code>.
        </p>

        <div className="grid gap-2 rounded-md border bg-muted/30 p-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="prompt-mode"
              value="init"
              checked={mode === "init"}
              disabled={disabled}
              onChange={() => setMode("init")}
            />
            Ny sajt
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="prompt-mode"
              value="followup"
              checked={mode === "followup"}
              disabled={disabled}
              onChange={() => setMode("followup")}
            />
            Följdprompt på vald run/siteId
          </label>
          {mode === "followup" ? (
            <p className="text-xs text-muted-foreground">
              Målsajt: <code>{targetSiteId || "saknas"}</code>. Helpern kräver
              befintlig meta i <code>data/prompt-inputs/</code>.
              {followupReady ? null : " Välj en prompt-genererad siteId."}
            </p>
          ) : null}
        </div>

        <Textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Skapa en hemsida för en elektriker i Malmö som vill ha kontakt och offertförfrågan..."
          rows={4}
          maxLength={4000}
          disabled={disabled}
        />

        {error ? (
          <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        ) : null}

        <PromptStageIndicator stage={stage} lastResult={lastResult} />

        <Button
          disabled={
            disabled ||
            prompt.trim().length === 0 ||
            (mode === "followup" && !followupReady)
          }
          onClick={() => void submitPrompt()}
          variant="default"
          size="lg"
        >
          {buttonLabel}
        </Button>
      </CardContent>
    </Card>
  );
}

function PromptStageIndicator({
  stage,
  lastResult,
}: {
  stage: PromptStage;
  lastResult: {
    runId: string;
    siteId: string;
    version: number | null;
    briefSource: string | null;
    buildStatus: string | null;
    outcome: PromptBuildOutcome;
  } | null;
}) {
  if (stage === "thinking") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm text-sky-700 dark:text-sky-300">
        <span className="inline-block size-2 animate-pulse rounded-full bg-sky-500" />
        Kör briefModel och bygger Project Input…
      </div>
    );
  }
  if (stage === "building") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-sm text-sky-700 dark:text-sky-300">
        <span className="inline-block size-2 animate-pulse rounded-full bg-sky-500" />
        Kör scripts/build_site.py (npm install + npm run build kan ta 5–60 sek).
      </div>
    );
  }
  if (stage === "success" && lastResult) {
    return (
      <div className="flex flex-col gap-1 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-300">
        <p>
          Build klar: <code>{lastResult.runId}</code>
        </p>
        <ResultMeta lastResult={lastResult} />
      </div>
    );
  }
  if (stage === "degraded" && lastResult) {
    const headline =
      lastResult.outcome === "degraded"
        ? "Build klar med varning"
        : "Build klar med okänd status";
    const detail =
      lastResult.outcome === "degraded"
        ? "Quality Gate eller policy-kontroll markerade fynd. Inspektera Run Details."
        : `Okänd build-status (${lastResult.buildStatus ?? "saknas"}). Inspektera Run Details.`;
    return (
      <div className="flex flex-col gap-1 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-300">
        <p>
          {headline}: <code>{lastResult.runId}</code>
        </p>
        <p className="text-xs opacity-80">{detail}</p>
        <ResultMeta lastResult={lastResult} />
      </div>
    );
  }
  if (stage === "failed") {
    if (lastResult && lastResult.outcome === "failed") {
      return (
        <div className="flex flex-col gap-1 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
          <p>
            Build misslyckades: <code>{lastResult.runId}</code>
          </p>
          <p className="text-xs opacity-80">
            build-result.json status=failed (npm install/build eller Quality
            Gate). Se Run Details för detaljer.
          </p>
          <ResultMeta lastResult={lastResult} />
        </div>
      );
    }
    return (
      <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-300">
        Prompt-bygget misslyckades. Se felmeddelandet ovan.
      </div>
    );
  }
  return null;
}

function ResultMeta({
  lastResult,
}: {
  lastResult: {
    siteId: string;
    version: number | null;
    briefSource: string | null;
    buildStatus: string | null;
  };
}) {
  return (
    <p className="text-xs opacity-80">
      siteId: <code>{lastResult.siteId}</code>
      {lastResult.version ? (
        <>
          {" · "}version: <code>{lastResult.version}</code>
        </>
      ) : null}
      {lastResult.briefSource ? (
        <>
          {" · "}briefSource: <code>{lastResult.briefSource}</code>
        </>
      ) : null}
      {lastResult.buildStatus ? (
        <>
          {" · "}buildStatus: <code>{lastResult.buildStatus}</code>
        </>
      ) : null}
    </p>
  );
}
