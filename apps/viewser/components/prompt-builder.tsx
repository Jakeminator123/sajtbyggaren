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
   * NDJSON-stream-läsaren som flyttar stage `thinking`→`building` när
   * Phase 1-eventet kommer, och alla state-updates måste leva vidare
   * under hela bygget (B122-fix 2026-05-27 ersatte den tidigare
   * setTimeout-baserade flippen). Att unmounta
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
  /**
   * Bygg-läget deriveras automatiskt: om en run/sajt är vald och redo
   * för iteration (followupReady) skickas prompten som en följdprompt
   * direkt mot /api/prompt; annars öppnas DiscoveryWizard för att
   * skapa en ny sajt. Tidigare visades två manuella pillar ("Ny sajt"
   * / "Följdprompt") under textarean — de togs bort i samband med
   * total minimalism eftersom valet är entydigt givet kontexten.
   */
  const mode: PromptMode = followupReady ? "followup" : "init";

  // B122-fix 2026-05-27: den 1500ms-baserade stage-transition-timern är
  // borta — `building`-eventet kommer nu från route:n via NDJSON-stream.
  // Inget kvar att städa vid unmount (om operatorn lämnar sidan mitt i
  // ett bygge fortsätter routen på server-sidan oavsett, samma som
  // tidigare).

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
      // B122-fix: route:n exponerar nu en NDJSON-stream när vi sätter
      // `Accept: application/x-ndjson`. Vi får två events: `building`
      // exakt när Phase 1 (prompt → Project Input) är klar och `done`
      // när Phase 2 (build_site.py) är klar. Det ersätter den gamla
      // gissade 1500ms-timer-flippen som tidigare visade falsk
      // "Bygger sajt" om svaret kom under 1.5s (cache hit, validation
      // failure) eller motsatt — hängde i "thinking" om Phase 1 tog
      // över 1.5s. Bakåtkompatibelt: andra callers (floating-chat,
      // use-followup-build) skickar inte Accept-headern och får
      // fortfarande synkron JSON.
      const response = await fetch("/api/prompt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-ndjson",
        },
        body: JSON.stringify({
          prompt: args.cleanedPrompt,
          mode: args.submissionMode,
          siteId: args.submissionMode === "followup" ? targetSiteId : undefined,
          discovery: args.discovery,
        }),
      });

      if (!response.ok || !response.body) {
        // Server kan välja att svara med plain JSON-fel före streamen
        // hinner öppnas (t.ex. 400 från zod-validering eller 500 vid
        // server-init). I så fall läser vi en sista JSON och kastar.
        const fallback = await response.json().catch(() => null);
        const fallbackError = fallback?.error as string | undefined;
        throw new Error(
          fallbackError ??
            `Prompt-anropet misslyckades (HTTP ${response.status}).`,
        );
      }

      let donePayload: PromptApiPayload | null = null;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // NDJSON: en JSON per rad, separerade med `\n`. Behåll den
        // sista (möjligen partiella) raden i bufferten tills nästa
        // chunk kommer.
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          // Inre try/catch så en enskild korrupt NDJSON-rad
          // (proxy-buffring, kortvarig disconnect, mid-line abort)
          // inte sprider en obegriplig "Unexpected token X in JSON at
          // position N" till operatören. Den korrupta raden loggas
          // för debugging och vi fortsätter läsa nästa rad — den
          // riktiga ``stage: "done"`` eller ``stage: "error"`` brukar
          // komma direkt efter.
          let event:
            | { stage: "building" }
            | ({ stage: "done" } & PromptApiPayload)
            | { stage: "error"; error: string };
          try {
            event = JSON.parse(line);
          } catch (parseError) {
            console.warn(
              "[prompt-builder] Ignorerar oparseable NDJSON-rad:",
              parseError,
              line.slice(0, 200),
            );
            continue;
          }
          if (event.stage === "building") {
            // RIKTIG signal från route:n. Phase 1 är klar, Phase 2
            // (build_site.py) har precis startat — visa "Bygger sajt".
            setStage("building");
          } else if (event.stage === "done") {
            donePayload = event;
          } else if (event.stage === "error") {
            throw new Error(event.error || "Prompt-anropet misslyckades.");
          }
        }
      }
      // Sista, eventuellt ofullständiga raden i buffern. NDJSON-
      // protokollet kräver inte trailing newline, så hantera även
      // det fall där `done`-eventet kom utan terminator.
      //
      // ``"building"`` tas med i typunion:en — servern skickar
      // visserligen ``building`` mitt i streamen idag, men om en
      // build är så snabb att Phase 1 och Phase 2 hinner emit:a inom
      // samma chunk kan båda hamna i final-buffer:n utan terminator.
      if (buffer.trim()) {
        let event:
          | { stage: "building" }
          | ({ stage: "done" } & PromptApiPayload)
          | { stage: "error"; error: string };
        try {
          event = JSON.parse(buffer);
        } catch (parseError) {
          // Ofullständig final-buffer = troligtvis avbruten stream
          // (timeout, server-restart). Behandla som "ingen slutsignal"
          // så outer error-check tar över med rätt felmeddelande
          // istället för att kasta SyntaxError.
          console.warn(
            "[prompt-builder] Final-buffer kunde inte parseas:",
            parseError,
            buffer.slice(0, 200),
          );
          event = { stage: "building" };
        }
        if (event.stage === "done") {
          donePayload = event;
        } else if (event.stage === "error") {
          throw new Error(event.error || "Prompt-anropet misslyckades.");
        }
      }

      if (!donePayload || !donePayload.runId || !donePayload.siteId) {
        throw new Error(
          donePayload?.error ??
            "Prompt-anropet returnerade ingen slutsignal.",
        );
      }

      // B44: classify build status from build-result.json so the
      // operator UI distinguishes ok / degraded / failed instead of
      // showing "Build klar" for a structured failure (build-runner.ts
      // returns a runId on failed builds so the run still appears in
      // Run History).
      const outcome = classifyBuildStatus(donePayload.buildStatus);
      setStage(outcomeToStage(outcome));
      setLastResult({
        runId: donePayload.runId,
        siteId: donePayload.siteId,
        version: donePayload.version ?? null,
        briefSource: donePayload.briefSource ?? null,
        buildStatus: donePayload.buildStatus ?? null,
        outcome,
      });
      setPrompt("");
      setPendingPrompt("");
      onBuildDone(donePayload.runId, outcome, donePayload.siteId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Okänt fel.");
      setStage("failed");
    } finally {
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
        // pb-safe-or-4 respekterar iPhone home-indicator (env safe-area-inset
        // -bottom) + minst 16px under composern. sm:pb-7 (28px) på desktop
        // där safe-area inte är relevant. Tidigare `pb-5 sm:pb-7` saknade
        // safe-area-koll och lät composer-knappar ligga 0px från home-indicator
        // på iPhone X+.
        className={`pointer-events-none absolute inset-x-0 bottom-0 z-30 flex justify-center px-3 pb-safe-or-4 sm:pb-7 ${hidden ? "hidden" : ""}`}
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
            className="min-h-[64px] resize-none border-0 bg-transparent px-4 py-3 text-base leading-relaxed shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 md:text-[15px]"
          />
          <div className="flex items-center justify-end gap-2 border-t border-border/40 px-2 py-2">
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
