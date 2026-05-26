"use client";

import { useEffect, useRef, useState } from "react";

import { DiscoveryWizard } from "@/components/discovery-wizard/discovery-wizard";
import {
  buildDiscoveryPayload,
  composeMasterPrompt,
} from "@/components/discovery-wizard/wizard-payload";
import type { discoveryOption } from "@/components/discovery-wizard/discovery-options";
import type { WizardAnswers } from "@/components/discovery-wizard/wizard-types";
import type { ProjectInputOption } from "@/components/project-input-picker";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { RunHistoryItem } from "@/components/run-history";

export type PromptStage =
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
  onBuildDone: (runId: string, outcome: PromptBuildOutcome, siteId: string) => void;
  /**
   * Lyfter prompt-stage upp till page.tsx så ViewerPanel kan visa
   * en central laddnings-card under "thinking" och "building".
   * Komponenten döljer sin lilla inline-status-pill när bygget pågår,
   * eftersom cardet i ViewerPanel visar samma information större och
   * mer dominant.
   */
  onStageChange?: (stage: PromptStage) => void;
  /**
   * När `true` döljs hela prompt-strippen visuellt — men komponenten
   * stannar mountad. Detta är kritiskt: fetch-anropet mot /api/prompt,
   * setTimeout som flyttar stage `thinking`→`building`, och alla
   * state-updates måste leva vidare under hela bygget. Att unmounta
   * komponenten via conditional rendering här triggade en bugg där
   * BuildProgressCard fastnade på steg 1 eftersom `onStageChange`
   * inte längre kunde rapportera nya stages från den döda komponenten.
   */
  hidden?: boolean;
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
  onStageChange,
  hidden = false,
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
  /**
   * Wizardens state. När operatorn klickar "Bygg" i `init`-läge öppnas
   * `DiscoveryWizard` istället för att direkt POSTa till /api/prompt;
   * promptens text bevaras tills wizarden är klar och skickas då som
   * en del av discovery-payload:en.
   */
  const [wizardOpen, setWizardOpen] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState("");
  // Wizard session key — bumpas varje gång operatören öppnar wizarden
  // så ``DiscoveryWizard`` remountas med fresh state (answers, stepIndex,
  // isSubmitting). Etablerat mönster i kodbasen istället för set-state-
  // in-effect (B3+B4 i scout-review 2026-05-24).
  const [wizardSession, setWizardSession] = useState(0);
  const stageTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const localBusy = stage === "thinking" || stage === "building";
  const disabled = isBusy || localBusy;
  const selectedRun = runs.find((run) => run.runId === selectedRunId);
  const runSiteIdUnknown =
    !!selectedRunId &&
    !!selectedRun &&
    (!selectedRun.siteId || selectedRun.siteId === "unknown");
  const targetSiteId =
    runSiteIdUnknown
      ? ""
      : selectedRun?.siteId && selectedRun.siteId !== "unknown"
        ? selectedRun.siteId
        : selectedSiteId;
  const targetInput = projectInputs.find(
    (input) => input.siteId === targetSiteId,
  );
  const followupReady =
    !runSiteIdUnknown &&
    targetSiteId.trim().length > 0 &&
    targetSiteId !== "unknown" &&
    targetInput?.source === "prompt-inputs";

  useEffect(() => {
    return () => {
      if (stageTimerRef.current) {
        clearTimeout(stageTimerRef.current);
      }
    };
  }, []);

  // Lyft stage-ändringar uppåt så page.tsx kan dirigera ViewerPanel:s
  // build-progress-card. Vi rapporterar varje stage-flip exakt en gång.
  useEffect(() => {
    onStageChange?.(stage);
  }, [stage, onStageChange]);

  /**
   * Faktisk POST mot /api/prompt + state-uppdateringar. Anropas både
   * från follow-up-vägen (direkt utan wizard) och från wizardens
   * `onComplete` med berikad discovery-payload.
   */
  async function executeBuild(args: {
    cleanedPrompt: string;
    submissionMode: PromptMode;
    discovery?: ReturnType<typeof buildDiscoveryPayload>;
  }) {
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
          prompt: args.cleanedPrompt,
          mode: args.submissionMode,
          siteId: args.submissionMode === "followup" ? targetSiteId : undefined,
          discovery: args.discovery,
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
      setPrompt("");
      setPendingPrompt("");
      onBuildDone(payload.runId, outcome, payload.siteId);
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

  /**
   * Operatorn klickade "Skicka". I `init`-läge öppnar vi discovery-
   * wizarden istället för att direkt bygga — operatorn får komplettera
   * företagsinfo, kategori, sidor osv. innan StackBlitz tänds. I
   * `followup`-läge bygger vi direkt utan wizard.
   */
  function submitPrompt() {
    const cleaned = prompt.trim();
    if (!cleaned || disabled) return;
    if (mode === "followup") {
      if (runSiteIdUnknown) {
        setError(
          "Vald run saknar siteId — follow-up kan inte skickas till rätt sajt.",
        );
        return;
      }
      if (!followupReady) {
        setError("Välj en prompt-genererad run eller siteId först.");
        return;
      }
      void executeBuild({ cleanedPrompt: cleaned, submissionMode: "followup" });
      return;
    }
    setPendingPrompt(cleaned);
    setError(null);
    setWizardSession((n) => n + 1);
    setWizardOpen(true);
  }

  function handleWizardComplete(
    answers: WizardAnswers,
    discoveryOptions: readonly discoveryOption[],
  ) {
    setWizardOpen(false);
    const cleaned = pendingPrompt.trim();
    if (!cleaned) return;
    // Skicka en master-prompt till backend som innehåller wizardens
    // alla svar i sektion-baserad form. briefModel (i
    // `packages/generation/brief/extract.py`) ser då full kontext
    // för att extrahera tone, target_audience, requested_capabilities,
    // conversion_goals och notes_for_planner — i stället för att bara
    // gissa från operatörens första rad. Discovery-objektet skickas
    // separately; the backend Discovery Resolver owns scaffold and
    // variant decisions from governance.
    let discovery: ReturnType<typeof buildDiscoveryPayload>;
    try {
      discovery = buildDiscoveryPayload(cleaned, answers, discoveryOptions);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Discovery-svaren kunde inte valideras.",
      );
      return;
    }
    const masterPrompt = composeMasterPrompt(cleaned, answers, discoveryOptions);
    void executeBuild({
      cleanedPrompt: masterPrompt,
      submissionMode: "init",
      discovery,
    });
  }

  // Dölj inline-statuspillen under thinking/building eftersom
  // ViewerPanel:s BuildProgressCard visar samma info större och mer
  // dominant. Behåll pillen för error/success/degraded så operatören
  // ser slutresultatet direkt vid prompt-rutan.
  const isBuilding = stage === "thinking" || stage === "building";
  const showStrip = (stage !== "idle" || !!error) && !isBuilding;

  return (
    <>
      <DiscoveryWizard
        key={wizardSession}
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        initialPrompt={pendingPrompt}
        onComplete={handleWizardComplete}
      />
      <div
        className={`pointer-events-none absolute inset-x-0 bottom-0 z-30 flex justify-center px-3 pb-5 sm:pb-7 ${hidden ? "hidden" : ""}`}
        aria-hidden={hidden}
      >
      <div className="pointer-events-auto flex w-full max-w-[720px] flex-col gap-2">
        {showStrip ? (
          <PromptStatusStrip stage={stage} error={error} lastResult={lastResult} />
        ) : null}

        <div className="hover-lift relative overflow-hidden rounded-2xl border border-border/70 bg-card/90 shadow-2xl backdrop-blur-xl">
          <Textarea
            ref={textareaRef}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={
              mode === "followup"
                ? "Beskriv ändringen du vill göra på den valda sajten…"
                : "Beskriv din sajt — företag, känsla, mål, ton…"
            }
            rows={2}
            maxLength={4000}
            disabled={disabled}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                void submitPrompt();
              }
            }}
            className="min-h-[64px] resize-none border-0 bg-transparent px-4 py-3 text-base leading-relaxed shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 sm:text-[15px]"
          />
          <div className="flex items-center justify-between gap-2 border-t border-border/40 px-2 py-2">
            <ModeSwitcher
              mode={mode}
              onChange={setMode}
              disabled={disabled}
              followupReady={followupReady}
            />
            <div className="flex items-center gap-2">
              <span className="hidden font-mono text-[10px] text-muted-foreground/70 sm:inline">
                ⌘ + ↵
              </span>
              <Button
                disabled={
                  disabled ||
                  prompt.trim().length === 0 ||
                  (mode === "followup" && !followupReady)
                }
                onClick={() => void submitPrompt()}
                variant="default"
                size="sm"
                className="min-tap sm:min-tap-0 rounded-full p-0 active:scale-95 sm:size-9"
                aria-label={localBusy ? "Bygger sajt" : "Bygg sajt"}
              >
                {localBusy ? (
                  <span className="inline-block size-2 animate-pulse rounded-full bg-background" />
                ) : (
                  <ArrowUpIcon />
                )}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
    </>
  );
}

function ArrowUpIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 19V5" />
      <path d="m5 12 7-7 7 7" />
    </svg>
  );
}

function ModeSwitcher({
  mode,
  onChange,
  disabled,
  followupReady,
}: {
  mode: PromptMode;
  onChange: (next: PromptMode) => void;
  disabled: boolean;
  followupReady: boolean;
}) {
  return (
    <div
      role="tablist"
      aria-label="Bygg-läge"
      className="inline-flex rounded-full bg-muted/60 p-0.5 text-[11px]"
    >
      <ModePill
        active={mode === "init"}
        disabled={disabled}
        onClick={() => onChange("init")}
      >
        Ny sajt
      </ModePill>
      <ModePill
        active={mode === "followup"}
        disabled={disabled || !followupReady}
        onClick={() => onChange("followup")}
        aria-label="Följdprompt på vald run/siteId"
      >
        Följdprompt
      </ModePill>
    </div>
  );
}

function ModePill({
  children,
  active,
  disabled,
  onClick,
  "aria-label": ariaLabel,
}: {
  children: React.ReactNode;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  "aria-label"?: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-full px-3 py-1.5 text-[12px] font-medium transition active:scale-95 disabled:opacity-40 sm:px-2.5 sm:py-1 sm:text-[11px] ${
        active
          ? "bg-background text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function PromptStatusStrip({
  stage,
  error,
  lastResult,
}: {
  stage: PromptStage;
  error: string | null;
  lastResult: {
    runId: string;
    siteId: string;
    version: number | null;
    briefSource: string | null;
    buildStatus: string | null;
    outcome: PromptBuildOutcome;
  } | null;
}) {
  if (error) {
    return (
      <StripCard tone="danger">
        <span className="truncate">{error}</span>
      </StripCard>
    );
  }
  if (stage === "thinking") {
    return (
      <StripCard tone="info">
        <PulseDot />
        Kör briefModel och bygger Project Input…
      </StripCard>
    );
  }
  if (stage === "building") {
    return (
      <StripCard tone="info">
        <PulseDot />
        Kör build_site.py — npm install + build (5–60 sek).
      </StripCard>
    );
  }
  if (stage === "success" && lastResult) {
    return (
      <StripCard tone="success">
        <span>
          Build klar:{" "}
          <code className="font-mono">{shortRun(lastResult.runId)}</code>
        </span>
      </StripCard>
    );
  }
  if (stage === "degraded" && lastResult) {
    const headline =
      lastResult.outcome === "degraded"
        ? "Build klar med varning"
        : "Build klar med okänd status";
    return (
      <StripCard tone="warning">
        <span>
          {headline}:{" "}
          <code className="font-mono">{shortRun(lastResult.runId)}</code>
        </span>
      </StripCard>
    );
  }
  if (stage === "failed") {
    if (lastResult && lastResult.outcome === "failed") {
      return (
        <StripCard tone="danger">
          <span>
            Build misslyckades:{" "}
            <code className="font-mono">{shortRun(lastResult.runId)}</code>
          </span>
        </StripCard>
      );
    }
    return (
      <StripCard tone="danger">
        <span>Prompt-bygget misslyckades.</span>
      </StripCard>
    );
  }
  return null;
}

function shortRun(runId: string): string {
  return runId.length > 28 ? `${runId.slice(0, 28)}…` : runId;
}

function PulseDot() {
  return (
    <span className="inline-block size-1.5 animate-pulse rounded-full bg-foreground/70" />
  );
}

function StripCard({
  tone,
  children,
}: {
  tone: "info" | "success" | "warning" | "danger";
  children: React.ReactNode;
}) {
  const toneClass =
    tone === "success"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
      : tone === "warning"
        ? "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300"
        : tone === "danger"
          ? "border-destructive/40 bg-destructive/10 text-destructive"
          : "border-border/60 bg-card/85 text-muted-foreground";
  return (
    <div
      className={`flex items-center gap-2 self-center rounded-full border px-3 py-1.5 text-xs shadow-sm backdrop-blur ${toneClass}`}
    >
      {children}
    </div>
  );
}
