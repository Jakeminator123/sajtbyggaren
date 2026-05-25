"use client";

/**
 * use-build-trace-polling — Live Build Sync polling-hook.
 *
 * Ersätter den gamla hårdkodade FOLLOWUP_BUILD_STEPS-kedjan i
 * floating-chat.tsx (5s/7s/14s/60s setTimeout) med riktig polling
 * mot trace-endpointen från GAP-backend-build-trace-endpoint:
 *
 *   1. Så fort en build startar pollas /api/runs?siteId=X för att hitta
 *      den nyaste pending run för denna site (UI vet inte runId förrän
 *      /api/prompt returnerar, men pending-raden dyker upp i listRuns
 *      så fort scripts/build_site.py skapat run-katalogen).
 *
 *   2. När pending run upptäckts switchas pollingen till
 *      /api/runs/[runId]/trace?since=<iso> så vi tickar incrementellt
 *      fram trace-events (phase, event, status) i takt med att de
 *      skrivs till data/runs/<runId>/trace.ndjson.
 *
 *   3. När runStatus inte längre är "pending" stoppas pollingen.
 *      /api/prompt-fetchen i floating-chat.tsx levererar slutbubblan
 *      separat — denna hook ger bara mellanstegen.
 *
 * Designprinciper:
 *
 * - Backoff i två steg: 1500 ms tills pending hittats (max 60 s
 *   timeout — efter det antar vi att bygget redan klart eller
 *   misslyckades innan pending-raden hann landa). Sedan 1500 ms i 30 s
 *   och 3000 ms därefter.
 * - AbortController på alla in-flight fetches så att unmount/disable
 *   inte triggar setState efter unmount.
 * - Hooken returnerar bara state — den triggar inga callbacks. Det är
 *   floating-chat.tsx som binder `label` till pending-bubblans content.
 * - Inga skrivningar mot disk eller mot någon annan tab — read-only
 *   poll-loop.
 */

import { useEffect, useRef, useState } from "react";

import type { RunMeta, RunStatus, RunTraceResponse } from "@/lib/runs";

export type BuildPhase = "understand" | "plan" | "build" | "unknown";

export type BuildTraceState = {
  /** Det runId vi för tillfället pollar trace för. null tills pending hittats. */
  runId: string | null;
  /**
   * Senast kända status. null tills pending hittats. Slutar polla
   * automatiskt när status blir terminal (ok/degraded/failed/skipped).
   */
  runStatus: RunStatus | null;
  /** Senaste phase från trace.ndjson, översatt för UI:s skull. */
  currentPhase: BuildPhase;
  /** Senaste event-id (för debug/observability — inte alltid människovänligt). */
  currentEvent: string | null;
  /** Mänsklig label som operatören ska se i pending-bubblan. */
  label: string;
  /** True medan vi aktivt pollar (har inte sett terminal status). */
  isPending: boolean;
};

const INITIAL_LABEL = "Bygger om sajten…";

const PHASE_LABELS: Record<BuildPhase, string> = {
  understand: "Förstår din instruktion…",
  plan: "Planerar ändringarna…",
  build: "Genererar och bygger sajten…",
  unknown: INITIAL_LABEL,
};

const POLL_FAST_MS = 1500;
const POLL_SLOW_MS = 3000;
const POLL_FAST_DURATION_MS = 30_000;
const PENDING_DISCOVERY_TIMEOUT_MS = 60_000;
const RUNS_LIST_LIMIT = 5;

function normalizePhase(phase: string | undefined | null): BuildPhase {
  if (phase === "understand" || phase === "plan" || phase === "build") {
    return phase;
  }
  return "unknown";
}

function emptyState(): BuildTraceState {
  return {
    runId: null,
    runStatus: null,
    currentPhase: "unknown",
    currentEvent: null,
    label: INITIAL_LABEL,
    isPending: false,
  };
}

type RunsApiResponse = {
  runs?: RunMeta[];
};

export function useBuildTracePolling(
  siteId: string,
  options: { enabled: boolean },
): BuildTraceState {
  const [state, setState] = useState<BuildTraceState>(emptyState);
  // Vi spårar startTime så vi kan välja fast/slow polling. Dessutom
  // sparar vi senaste event-timestamp så ?since= bara ger oss nya
  // events vid varje incremental fetch.
  const startedAtRef = useRef<number | null>(null);
  const sinceRef = useRef<string | null>(null);
  // runId i state uppdateras async via setState — refen ger en
  // synkron läsbar version som timer-callbacken kan använda utan
  // att behöva re-renderas.
  const runIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!options.enabled) {
      // React 19 set-state-in-effect-rule kräver att synkrona setState
      // i useEffect skjuts till nästa tick. Samma mönster som
      // use-pending-build.ts använder för pendingBaseRunId-clear.
      const cancelToken = window.setTimeout(() => {
        setState(emptyState());
      }, 0);
      startedAtRef.current = null;
      sinceRef.current = null;
      runIdRef.current = null;
      return () => {
        window.clearTimeout(cancelToken);
      };
    }

    startedAtRef.current = Date.now();
    sinceRef.current = null;
    runIdRef.current = null;
    const initToken = window.setTimeout(() => {
      setState({ ...emptyState(), isPending: true });
    }, 0);

    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | null = null;

    const scheduleNext = () => {
      if (controller.signal.aborted) return;
      const elapsed = startedAtRef.current
        ? Date.now() - startedAtRef.current
        : 0;
      const interval =
        elapsed > POLL_FAST_DURATION_MS ? POLL_SLOW_MS : POLL_FAST_MS;
      timer = setTimeout(() => {
        void poll();
      }, interval);
    };

    const stop = () => {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const poll = async () => {
      if (controller.signal.aborted) return;
      try {
        if (!runIdRef.current) {
          // Steg 1: leta efter pending run för denna site. Vi tar de
          // RUNS_LIST_LIMIT senaste och plockar den första med
          // siteId-match som har runStatus === "pending".
          const response = await fetch(
            `/api/runs?siteId=${encodeURIComponent(siteId)}`,
            { signal: controller.signal },
          );
          if (!response.ok) {
            // 4xx från ?siteId= är operator-bug (ogiltig site). 5xx
            // är temporärt — i båda fallen schedulerar vi ändå nästa
            // poll så att en transient hicka inte fryser bygg-bubblan.
            scheduleNext();
            return;
          }
          const payload = (await response.json()) as RunsApiResponse;
          if (controller.signal.aborted) return;
          const runs = (payload.runs ?? [])
            .filter((run) => run.siteId === siteId)
            .slice(0, RUNS_LIST_LIMIT);
          // RunMeta använder fältnamnet `status` (inte `runStatus`) —
          // /api/runs återanvänder samma RunMeta-typ för pending och
          // färdiga runs. Värdet "pending" sätts i lib/runs.ts:listRuns
          // när build-result.json saknas, så stränggräncen håller här.
          const pending = runs.find((run) => run.status === "pending");
          if (pending) {
            runIdRef.current = pending.runId;
            setState((prev) => ({
              ...prev,
              runId: pending.runId,
              runStatus: "pending",
              currentPhase: normalizePhase(pending.currentPhase),
              currentEvent: pending.currentEvent ?? null,
              label: PHASE_LABELS[normalizePhase(pending.currentPhase)],
              isPending: true,
            }));
            scheduleNext();
            return;
          }
          const elapsed = startedAtRef.current
            ? Date.now() - startedAtRef.current
            : 0;
          if (elapsed > PENDING_DISCOVERY_TIMEOUT_MS) {
            // Bygget avslutades innan pending-raden upptäcktes (för
            // snabbt — eller misslyckades så tidigt att trace.ndjson
            // aldrig skapades). Stoppa polling och låt
            // /api/prompt-fetchen leverera slutresultatet.
            return;
          }
          scheduleNext();
          return;
        }

        // Steg 2: incremental trace-polling för upptäckt runId.
        const traceUrl = new URL(
          `/api/runs/${runIdRef.current}/trace`,
          window.location.origin,
        );
        if (sinceRef.current) {
          traceUrl.searchParams.set("since", sinceRef.current);
        }
        traceUrl.searchParams.set("limit", "50");
        const response = await fetch(traceUrl.toString(), {
          signal: controller.signal,
        });
        if (!response.ok) {
          // 404 betyder att run-katalogen försvunnit (osannolikt mid-
          // build, men hanteras): stoppa och låt /api/prompt-fetchen
          // ge slutbubblan. 5xx schedulerar vi om med backoff.
          if (response.status === 404 || response.status === 400) {
            return;
          }
          scheduleNext();
          return;
        }
        const trace = (await response.json()) as RunTraceResponse;
        if (controller.signal.aborted) return;

        const lastEvent = trace.events.at(-1);
        if (lastEvent) {
          sinceRef.current = lastEvent.timestamp;
          const phase = normalizePhase(lastEvent.phase);
          setState({
            runId: trace.runId,
            runStatus: trace.runStatus,
            currentPhase: phase,
            currentEvent: lastEvent.event,
            label: PHASE_LABELS[phase],
            isPending: trace.runStatus === "pending",
          });
        } else {
          // Inga nya events sedan ?since=, men runStatus kan ändå ha
          // bytt — uppdatera bara status så vi inte missar terminal.
          setState((prev) => ({
            ...prev,
            runStatus: trace.runStatus,
            isPending: trace.runStatus === "pending",
          }));
        }

        if (trace.runStatus !== "pending") {
          // Build klar (ok/degraded/failed/skipped/unknown) — stoppa.
          // /api/prompt-fetchen i floating-chat.tsx levererar slut-
          // bubblan separat med summary + outcome. Vi rensar inte
          // state här eftersom enabled=false-effekten kommer rensa
          // när isSending blir false.
          return;
        }

        scheduleNext();
      } catch (error) {
        if ((error as { name?: string }).name === "AbortError") return;
        // Nätverksfel eller JSON-parse-fel: schedulera om så att en
        // transient hicka inte fryser bubblan. Vid persistent fel
        // tar enabled=false-rensningen över när isSending blir false.
        scheduleNext();
      }
    };

    void poll();

    return () => {
      window.clearTimeout(initToken);
      controller.abort();
      stop();
    };
  }, [options.enabled, siteId]);

  return state;
}
