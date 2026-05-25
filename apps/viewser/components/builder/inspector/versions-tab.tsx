"use client";

import {
  ArrowRight,
  CircleCheck,
  Clock,
  Copy,
  GitBranch,
  GitCompare,
  Layers,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  computeRunDiff,
  formatDiffSummary,
  type RunArtefactBundleLike,
  type RunDiff,
} from "@/components/builder/inspector/run-diff";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";
import type { PendingBuildState } from "@/components/builder/use-pending-build";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SECONDARY_INTERACTIONS } from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

/**
 * VersionsTab — site-scoped versionshistorik + jämförelse mellan två runs.
 *
 * Stänger gapet i kärnloopen "prompt → preview → följdprompt → ny version":
 * tidigare kunde operatören bara se ALLA runs över alla sajter via
 * ConsoleDrawer, utan filter och utan möjlighet att jämföra två versioner.
 * Här ser hen bara den aktuella sajtens runs och kan markera två (A/B)
 * för att se en exakt diff av scaffold/variant/routes/tone/capabilities/
 * quality.
 *
 * Pure UI-konsumtion av befintliga endpoints:
 *
 *   - /api/runs                         — lista runs (filteras klient-sidigt)
 *   - /api/runs/[runId]/artifacts       — per-run artefakter för diff-vy
 *
 * Diff-logiken lever i pure `run-diff.ts` så vi enkelt kan testa den
 * isolerat och återanvända den i framtida ytor.
 */

type RunMeta = {
  runId: string;
  status: string;
  siteId: string;
  projectId?: string;
  version?: number | null;
  createdAt: string;
};

type RunsApiResponse = {
  runs?: RunMeta[];
  error?: string;
};

const STATUS_DOT_COLORS: Record<string, string> = {
  ok: "bg-emerald-500",
  passed: "bg-emerald-500",
  "mock-complete": "bg-sky-500",
  degraded: "bg-amber-500",
  warning: "bg-amber-500",
  failed: "bg-destructive",
  skipped: "bg-muted-foreground/40",
  unknown: "bg-muted-foreground/40",
};

function formatRelative(createdAt: string): string {
  const ts = Date.parse(createdAt);
  if (!Number.isFinite(ts)) return "";
  const seconds = Math.max(1, Math.round((Date.now() - ts) / 1000));
  if (seconds < 60) return `${seconds}s sedan`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m sedan`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h sedan`;
  const days = Math.round(hours / 24);
  return `${days}d sedan`;
}

function shortRunId(runId: string): string {
  return runId.length > 22 ? `${runId.slice(0, 22)}…` : runId;
}

/**
 * Plocka en rationale-excerpt från artefakter om vi har dem cachad.
 * Faller tillbaka till "—" för runs där vi inte hunnit fetcha bundeln
 * (det är OK; bundle laddas on-demand när operatören valt A/B).
 */
function rationaleExcerpt(value: unknown): string | null {
  if (typeof value !== "string" || value.length === 0) return null;
  return value.length > 110 ? `${value.slice(0, 107)}…` : value;
}

export interface VersionsTabProps {
  bundle: RunArtefactBundle;
  siteId: string;
  currentRunId: string | null;
  isBuilding: boolean;
  /**
   * Live Build Sync: optimistisk pending-build-state. Sätts av
   * page.tsx via usePendingBuild när en follow-up triggas och
   * matchas mot siteId här så vi bara renderar pending-raden för
   * rätt sajt. null = ingen build pågår (eller bygger en annan sajt).
   */
  pendingBuild?: PendingBuildState | null;
}

export function VersionsTab({
  bundle,
  siteId,
  currentRunId,
  isBuilding,
  pendingBuild,
}: VersionsTabProps) {
  const [allRuns, setAllRuns] = useState<RunMeta[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [compareA, setCompareA] = useState<string | null>(null);
  const [compareB, setCompareB] = useState<string | null>(null);

  // Fetch /api/runs vid mount + manuell refresh. Cancel-flagga skyddar
  // mot setState efter unmount (samma mönster som use-run-artefacts).
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setAllRuns(null);
      setLoadError(null);
      try {
        const response = await fetch("/api/runs");
        const payload = (await response.json()) as RunsApiResponse;
        if (cancelled) return;
        if (!response.ok || !payload.runs) {
          throw new Error(payload.error ?? `HTTP ${response.status}`);
        }
        setAllRuns(payload.runs);
      } catch (caught) {
        if (cancelled) return;
        setLoadError(
          caught instanceof Error ? caught.message : "Okänt fel vid hämtning.",
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const refresh = useCallback(() => {
    setReloadToken((prev) => prev + 1);
  }, []);

  // Auto-refresh när ett bygge slutar — då finns en ny run på disk
  // som /api/runs kan returnera. Vi spårar föregående isBuilding-värde
  // via ref så vi bara triggar på övergången true → false (inte vid
  // mount eller varje render). setState körs via Promise.resolve()
  // för att respektera React 19:s set-state-in-effect-rule.
  const wasBuildingRef = useRef(isBuilding);
  useEffect(() => {
    const wasBuilding = wasBuildingRef.current;
    wasBuildingRef.current = isBuilding;
    if (!wasBuilding || isBuilding) return;
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setReloadToken((prev) => prev + 1);
    })();
    return () => {
      cancelled = true;
    };
  }, [isBuilding]);

  const siteRuns = useMemo<RunMeta[]>(() => {
    if (!allRuns) return [];
    return allRuns.filter((run) => run.siteId === siteId);
  }, [allRuns, siteId]);

  // Pending-build matchar denna sajt? Då renderar vi en optimistisk
  // "Bygger…"-rad högst upp i listan. Backend exponerar inte runId
  // förrän bygget är klart, så vi visar bara en placeholder utan
  // klickbarhet och utan radio-knappar.
  //
  // estimatedVersion: föräldern (BuilderShell/page.tsx) skickar inte
  // nödvändigtvis in en estimerad version eftersom FloatingChat-
  // flödet bara anropar onBuildStart() utan args. Som fallback
  // beräknar vi senaste kända version i siteRuns + 1 så pending-
  // raden visar "Bygger v3…" istället för bara "Bygger ny version…"
  // (H2 från bug-hunt).
  const fallbackEstimatedVersion = useMemo<number | null>(() => {
    const known = siteRuns
      .map((run) => run.version)
      .filter((value): value is number => typeof value === "number");
    if (known.length === 0) return null;
    return Math.max(...known) + 1;
  }, [siteRuns]);
  const pendingForThisSite = useMemo<PendingBuildState | null>(() => {
    if (!pendingBuild || pendingBuild.siteId !== siteId) return null;
    if (pendingBuild.estimatedVersion !== null) return pendingBuild;
    return {
      ...pendingBuild,
      estimatedVersion: fallbackEstimatedVersion,
    };
  }, [pendingBuild, siteId, fallbackEstimatedVersion]);

  // Auto-highlight: spåra tidigare run-id-set så vi kan upptäcka när
  // en ny run tillkommer (efter en build) och flagga den för en kort
  // fade-in-highlight. Vi använder en ref för "föregående set" så
  // jämförelsen sker utanför render, och en useState för current
  // highlight-id så vi kan rensa den efter 1.8s. setState körs via
  // Promise.resolve() för att respektera React 19:s
  // set-state-in-effect-rule (samma mönster som isBuilding-watchern).
  const previousRunIdsRef = useRef<Set<string>>(new Set());
  const [recentlyAddedRunId, setRecentlyAddedRunId] = useState<string | null>(
    null,
  );
  useEffect(() => {
    const previous = previousRunIdsRef.current;
    const next = new Set(siteRuns.map((run) => run.runId));
    previousRunIdsRef.current = next;
    if (previous.size === 0) return;
    const added = siteRuns.find((run) => !previous.has(run.runId));
    if (!added) return;
    let cancelled = false;
    let timer: number | null = null;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setRecentlyAddedRunId(added.runId);
      timer = window.setTimeout(() => {
        if (cancelled) return;
        setRecentlyAddedRunId(null);
      }, 1_800);
    })();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [siteRuns]);

  // Copy-to-clipboard fallback för "Iterera från denna"-knappen. Vi
  // rör inte floating-chat.tsx (1481 rader, högrisk) — istället
  // kopierar vi prompt-prefix till clipboard och visar en kort
  // bekräftelse. Operatören klistrar in i chat-rutan manuellt. När
  // backend stödjer baseRunId (se GAP-backend-build-trace-endpoint)
  // kan vi byta detta mot ett direkt anrop.
  //
  // Feedbacken speglar clipboard-resultatet: lyckas = "Prefix
  // kopierat", misslyckas = "Skriv: 'Utgå från version N:'" så vi
  // aldrig ljuger för operatören (M1 från bug-hunt).
  const [copyFeedback, setCopyFeedback] = useState<{
    runId: string;
    kind: "success" | "failure";
    prefix: string;
  } | null>(null);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const handleIterateFrom = useCallback(
    async (runId: string, version: number | null | undefined) => {
      const versionLabel = version ?? "?";
      const prefix = `Utgå från version ${versionLabel}: `;
      let kind: "success" | "failure" = "failure";
      try {
        if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(prefix);
          kind = "success";
        }
      } catch {
        kind = "failure";
      }
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
      setCopyFeedback({ runId, kind, prefix });
      copyFeedbackTimerRef.current = window.setTimeout(() => {
        setCopyFeedback(null);
        copyFeedbackTimerRef.current = null;
      }, 4_000);
    },
    [],
  );
  // Cleanup vid unmount så stale setState inte triggas efter att
  // tabben stängts.
  useEffect(() => {
    return () => {
      if (copyFeedbackTimerRef.current !== null) {
        window.clearTimeout(copyFeedbackTimerRef.current);
      }
    };
  }, []);

  // Mutual-exclusion-handlers — när en run väljs som A:
  //   * Om den redan är A → toggle av (null).
  //   * Om den är vald som B → flytta över till A (B töms).
  // Vi gör state-updates sekventiellt (inte sido-effekter inuti en
  // pure updater-funktion) så React 19 Strict Mode batchar korrekt.
  const handleSelectA = useCallback(
    (runId: string) => {
      if (compareA === runId) {
        setCompareA(null);
        return;
      }
      if (compareB === runId) setCompareB(null);
      setCompareA(runId);
    },
    [compareA, compareB],
  );

  const handleSelectB = useCallback(
    (runId: string) => {
      if (compareB === runId) {
        setCompareB(null);
        return;
      }
      if (compareA === runId) setCompareA(null);
      setCompareB(runId);
    },
    [compareA, compareB],
  );

  const handleResetCompare = useCallback(() => {
    setCompareA(null);
    setCompareB(null);
  }, []);

  // Quick-action: Jämför de två senaste runs för aktuell sajt.
  // siteRuns kommer från /api/runs som returnerar dem sorterat på
  // createdAt desc → index 0 är senaste, index 1 är näst-senaste.
  // Triggar via knapp i CompareControls så vi undviker React 19:s
  // set-state-in-effect-rule (en manuell action är OK, en effect-
  // driven auto-init är inte det).
  const canCompareLatestTwo = siteRuns.length >= 2;
  const handleCompareLatestTwo = useCallback(() => {
    if (siteRuns.length < 2) return;
    setCompareA(siteRuns[1].runId);
    setCompareB(siteRuns[0].runId);
  }, [siteRuns]);

  /* ── Render states ───────────────────────────────────────────── */

  if (loadError) {
    return (
      <div className="space-y-3">
        <p
          role="alert"
          className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
        >
          {loadError}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={refresh}>
          <RotateCcw className="h-3 w-3" />
          Försök igen
        </Button>
      </div>
    );
  }

  if (allRuns === null) {
    return (
      <div className="text-muted-foreground flex h-32 items-center justify-center gap-2 text-[12px]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Läser versioner…
      </div>
    );
  }

  if (siteRuns.length === 0) {
    // Specialfall: ingen historik men en pending-build pågår. Visa
    // pending-raden ensam så operatören får visuell bekräftelse på
    // att första bygget är igång.
    if (pendingForThisSite) {
      return (
        <div className="flex flex-col gap-5">
          <HeaderBar
            siteId={siteId}
            runCount={0}
            isBuilding={isBuilding}
            onRefresh={refresh}
          />
          <ul className="border-border/60 overflow-hidden rounded-lg border bg-card">
            <PendingRunRow pending={pendingForThisSite} />
          </ul>
        </div>
      );
    }
    return (
      <EmptyState
        title="Inga versioner ännu"
        body="När du skickar följdprompter dyker varje ny version upp här. Den senaste 20 syns alltid (äldre rullar ut)."
      />
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <HeaderBar
        siteId={siteId}
        runCount={siteRuns.length}
        isBuilding={isBuilding}
        onRefresh={refresh}
      />

      <CompareControls
        compareA={compareA}
        compareB={compareB}
        onReset={handleResetCompare}
        onCompareLatestTwo={handleCompareLatestTwo}
        canCompareLatestTwo={canCompareLatestTwo}
      />

      <RunList
        runs={siteRuns}
        currentRunId={currentRunId}
        currentBundle={bundle}
        compareA={compareA}
        compareB={compareB}
        onSelectA={handleSelectA}
        onSelectB={handleSelectB}
        pending={pendingForThisSite}
        recentlyAddedRunId={recentlyAddedRunId}
        copyFeedback={copyFeedback}
        onIterateFrom={handleIterateFrom}
      />

      {compareA && compareB && compareA !== compareB ? (
        <CompareSection
          runIdA={compareA}
          runIdB={compareB}
          currentRunId={currentRunId}
          currentBundle={bundle}
        />
      ) : (
        <CompareEmptyHint
          hasA={compareA !== null}
          hasB={compareB !== null}
        />
      )}
    </div>
  );
}

/* ── Header ──────────────────────────────────────────────────────── */

function HeaderBar({
  siteId,
  runCount,
  isBuilding,
  onRefresh,
}: {
  siteId: string;
  runCount: number;
  isBuilding: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="border-border/40 bg-foreground/[0.02] flex items-start gap-2.5 rounded-lg border p-3">
      <Layers
        aria-hidden
        className="text-foreground/70 mt-0.5 h-3.5 w-3.5 shrink-0"
      />
      <div className="text-foreground/85 flex-1 text-[12px] leading-relaxed">
        <strong>{runCount}</strong> versioner för{" "}
        <code className="bg-muted/60 rounded px-1 py-0.5 font-mono text-[11px]">
          {siteId}
        </code>
        . Klicka en rad för att markera den som <strong>A</strong>, eller
        högerkolumnen för <strong>B</strong>. När båda är valda visas en
        diff längst ned.
        {isBuilding ? (
          <span className="ml-1 inline-flex items-center gap-1 text-amber-700 dark:text-amber-300">
            <Sparkles aria-hidden className="h-3 w-3 animate-pulse" />
            Build pågår — ny version dyker upp när bygget är klart.
          </span>
        ) : null}
      </div>
      <Button
        type="button"
        size="icon-sm"
        variant="ghost"
        onClick={onRefresh}
        aria-label="Uppdatera lista"
        title="Uppdatera lista"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}

/* ── Compare-kontroller (A / B / reset) ──────────────────────────── */

function CompareControls({
  compareA,
  compareB,
  onReset,
  onCompareLatestTwo,
  canCompareLatestTwo,
}: {
  compareA: string | null;
  compareB: string | null;
  onReset: () => void;
  onCompareLatestTwo: () => void;
  canCompareLatestTwo: boolean;
}) {
  return (
    <div className="border-border/60 flex items-center justify-between gap-3 rounded-lg border bg-card px-3 py-2">
      <div className="flex min-w-0 flex-1 items-center gap-2 text-[11.5px]">
        <CompareBadge label="A" value={compareA} tone="rose" />
        <ArrowRight
          aria-hidden
          className="text-muted-foreground/60 h-3 w-3 shrink-0"
        />
        <CompareBadge label="B" value={compareB} tone="emerald" />
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button
          type="button"
          onClick={onCompareLatestTwo}
          disabled={!canCompareLatestTwo}
          title="Jämför de två senaste versionerna"
          className={cn(
            "text-foreground/80 hover:text-foreground border-border/60 hover:border-foreground/40 hover:bg-muted/40",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors disabled:opacity-40",
            SECONDARY_INTERACTIONS,
          )}
        >
          <GitCompare aria-hidden className="h-3 w-3" />
          Senaste två
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={!compareA && !compareB}
          className={cn(
            "text-muted-foreground hover:text-foreground border-border/60 hover:border-foreground/40 hover:bg-muted/40",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors disabled:opacity-40",
            SECONDARY_INTERACTIONS,
          )}
        >
          <RotateCcw aria-hidden className="h-3 w-3" />
          Rensa
        </button>
      </div>
    </div>
  );
}

function CompareBadge({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | null;
  tone: "rose" | "emerald";
}) {
  const toneClasses =
    tone === "rose"
      ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300"
      : "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  return (
    <span
      className={cn(
        "inline-flex min-w-0 items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10.5px]",
        toneClasses,
      )}
      title={value ?? `Inget val för ${label}`}
    >
      <span className="text-[9px] tracking-[0.18em] uppercase opacity-80">
        {label}
      </span>
      <span className="truncate">
        {value ? shortRunId(value) : "ej valt"}
      </span>
    </span>
  );
}

/* ── Lista med run-kort + radio-knappar för A/B ──────────────────── */

type CopyFeedback = {
  runId: string;
  kind: "success" | "failure";
  prefix: string;
} | null;

function RunList({
  runs,
  currentRunId,
  currentBundle,
  compareA,
  compareB,
  onSelectA,
  onSelectB,
  pending,
  recentlyAddedRunId,
  copyFeedback,
  onIterateFrom,
}: {
  runs: RunMeta[];
  currentRunId: string | null;
  currentBundle: RunArtefactBundle;
  compareA: string | null;
  compareB: string | null;
  onSelectA: (runId: string) => void;
  onSelectB: (runId: string) => void;
  pending: PendingBuildState | null;
  recentlyAddedRunId: string | null;
  copyFeedback: CopyFeedback;
  onIterateFrom: (runId: string, version: number | null | undefined) => void;
}) {
  return (
    <ul className="border-border/60 divide-y divide-border/40 overflow-hidden rounded-lg border bg-card">
      {pending ? <PendingRunRow pending={pending} /> : null}
      {runs.map((run) => {
        const isCurrent = run.runId === currentRunId;
        const rationale = isCurrent
          ? rationaleExcerpt(extractCodegenRationale(currentBundle))
          : null;
        const feedbackForRow =
          copyFeedback && copyFeedback.runId === run.runId
            ? copyFeedback
            : null;
        return (
          <RunRow
            key={run.runId}
            run={run}
            isCurrent={isCurrent}
            rationale={rationale}
            isA={compareA === run.runId}
            isB={compareB === run.runId}
            isRecentlyAdded={recentlyAddedRunId === run.runId}
            copyFeedback={feedbackForRow}
            onSelectA={() => onSelectA(run.runId)}
            onSelectB={() => onSelectB(run.runId)}
            onIterateFrom={() => onIterateFrom(run.runId, run.version)}
          />
        );
      })}
    </ul>
  );
}

/**
 * Optimistisk pending-rad. Renderas så fort en follow-up triggas
 * och innan backend hunnit returnera ett runId. Tar inte emot klick
 * (ingen radio-button, ingen iteration) eftersom det inte finns
 * något runId att binda mot ännu. Backend exponerar inte trace-
 * status under pågående build (GAP-backend-build-trace-endpoint),
 * så vi visar bara prompt-snippet + relativ tid.
 */
function PendingRunRow({ pending }: { pending: PendingBuildState }) {
  // Live relativ-tid: tickar var 5:e sekund så "för 5s sedan" inte
  // står kvar i två minuter. useState + setInterval i en effect är
  // safe här eftersom intervallet aldrig sätter samma värde två
  // gånger i rad (Date.now() är monotont stigande).
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const handle = window.setInterval(() => {
      setNow(Date.now());
    }, 5_000);
    return () => window.clearInterval(handle);
  }, []);
  const elapsedSeconds = Math.max(1, Math.round((now - pending.startedAt) / 1000));
  const elapsedLabel =
    elapsedSeconds < 60
      ? `${elapsedSeconds}s sedan`
      : `${Math.round(elapsedSeconds / 60)}m sedan`;
  const versionLabel =
    pending.estimatedVersion !== null
      ? `Bygger v${pending.estimatedVersion}…`
      : "Bygger ny version…";
  return (
    <li
      aria-live="polite"
      aria-busy="true"
      className="border-amber-400/30 bg-amber-500/[0.06] flex items-stretch gap-0 border-b border-dashed last:border-b-0"
    >
      <div className="min-w-0 flex-1 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span
            aria-hidden
            className="bg-amber-500 inline-block h-2 w-2 shrink-0 animate-pulse rounded-full"
          />
          <span className="text-foreground/85 text-[12px] font-medium">
            {versionLabel}
          </span>
          <Loader2
            aria-hidden
            className="text-amber-600 dark:text-amber-400 h-3 w-3 shrink-0 animate-spin"
          />
          <span className="text-muted-foreground ml-auto inline-flex items-center gap-1 text-[11px]">
            <Clock aria-hidden className="h-3 w-3" />
            {elapsedLabel}
          </span>
        </div>
        {pending.promptSnippet ? (
          <p className="text-muted-foreground mt-1 line-clamp-1 text-[11.5px] italic">
            “{pending.promptSnippet}”
          </p>
        ) : null}
      </div>
    </li>
  );
}

function extractCodegenRationale(bundle: RunArtefactBundle): unknown {
  const build = bundle.buildResult;
  if (!build || typeof build !== "object") return null;
  const codegen = (build as Record<string, unknown>).codegen;
  if (!codegen || typeof codegen !== "object") return null;
  return (codegen as Record<string, unknown>).rationale;
}

function RunRow({
  run,
  isCurrent,
  rationale,
  isA,
  isB,
  isRecentlyAdded,
  copyFeedback,
  onSelectA,
  onSelectB,
  onIterateFrom,
}: {
  run: RunMeta;
  isCurrent: boolean;
  rationale: string | null;
  isA: boolean;
  isB: boolean;
  isRecentlyAdded: boolean;
  copyFeedback: CopyFeedback;
  onSelectA: () => void;
  onSelectB: () => void;
  onIterateFrom: () => void;
}) {
  const dotClass = STATUS_DOT_COLORS[run.status] ?? "bg-muted-foreground/40";
  const iterateDisabled = isCurrent;
  return (
    <li
      // data-just-built triggar en kort fade-in highlight via inline
      // style nedan (eftersom Tailwind inte hanterar tids-fade i
      // arbiträra attribut). Cleanup sker när recentlyAddedRunId
      // nollställs i föräldern efter 1.8s.
      data-just-built={isRecentlyAdded ? "true" : undefined}
      className={cn(
        "flex items-stretch gap-0 transition-colors duration-700",
        isCurrent ? "bg-foreground/[0.03]" : "hover:bg-muted/30",
        isRecentlyAdded
          ? "bg-emerald-500/[0.10] dark:bg-emerald-400/[0.08]"
          : "",
      )}
    >
      <div className="min-w-0 flex-1 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span
            aria-label={`status: ${run.status}`}
            className={cn("inline-block size-2 rounded-full", dotClass)}
          />
          <span className="text-foreground/90 truncate font-mono text-[11px]">
            {shortRunId(run.runId)}
          </span>
          {isCurrent ? (
            <span className="border-foreground/40 text-foreground/80 inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 font-mono text-[9px] tracking-wider uppercase">
              <CircleCheck aria-hidden className="h-2.5 w-2.5" />
              Aktiv
            </span>
          ) : null}
        </div>
        <div className="text-muted-foreground mt-0.5 flex items-center gap-1.5 pl-4 text-[10.5px]">
          <Clock aria-hidden className="h-2.5 w-2.5" />
          {formatRelative(run.createdAt)}
          {run.version ? ` · v${run.version}` : ""}
          {run.status ? ` · ${run.status}` : ""}
        </div>
        {rationale ? (
          <p className="text-muted-foreground mt-1 line-clamp-2 pl-4 text-[10.5px] italic leading-snug">
            {rationale}
          </p>
        ) : null}
        {copyFeedback ? (
          <p
            role="status"
            aria-live="polite"
            className={cn(
              "mt-1 inline-flex items-center gap-1 pl-4 text-[10.5px] font-medium",
              copyFeedback.kind === "success"
                ? "text-emerald-700 dark:text-emerald-400"
                : "text-amber-700 dark:text-amber-400",
            )}
          >
            <Copy aria-hidden className="h-2.5 w-2.5" />
            {copyFeedback.kind === "success"
              ? "Prefix kopierat — klistra in i chatten"
              : `Klistra in manuellt: "${copyFeedback.prefix}"`}
          </p>
        ) : null}
      </div>
      <div className="border-border/40 flex shrink-0 items-stretch border-l">
        <button
          type="button"
          onClick={onIterateFrom}
          disabled={iterateDisabled}
          title={
            iterateDisabled
              ? "Senaste versionen — chatten utgår alltid härifrån"
              : `Iterera från version ${run.version ?? "?"} (kopierar prompt-prefix)`
          }
          aria-label={
            iterateDisabled
              ? `Senaste versionen ${shortRunId(run.runId)}`
              : `Iterera från version ${run.version ?? "?"}`
          }
          className={cn(
            "flex w-9 items-center justify-center transition-colors",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            iterateDisabled
              ? "text-muted-foreground/40 cursor-not-allowed"
              : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
          )}
        >
          <GitBranch aria-hidden className="h-3 w-3" />
        </button>
        <div className="bg-border/40 w-px" aria-hidden />
        <RadioButton
          label="A"
          tone="rose"
          active={isA}
          onClick={onSelectA}
          title="Markera som A i diff"
          ariaLabel={`Markera ${shortRunId(run.runId)} som A i diff`}
        />
        <div className="bg-border/40 w-px" aria-hidden />
        <RadioButton
          label="B"
          tone="emerald"
          active={isB}
          onClick={onSelectB}
          title="Markera som B i diff"
          ariaLabel={`Markera ${shortRunId(run.runId)} som B i diff`}
        />
      </div>
    </li>
  );
}

function RadioButton({
  label,
  tone,
  active,
  onClick,
  title,
  ariaLabel,
}: {
  label: string;
  tone: "rose" | "emerald";
  active: boolean;
  onClick: () => void;
  title: string;
  ariaLabel: string;
}) {
  const toneActive =
    tone === "rose"
      ? "bg-rose-500/15 text-rose-700 dark:text-rose-300"
      : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={ariaLabel}
      aria-pressed={active}
      className={cn(
        "flex w-9 items-center justify-center font-mono text-[10px] tracking-[0.18em] uppercase transition-colors",
        "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
        active
          ? toneActive
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

/* ── Compare-vy (laddar artefakter on-demand) ────────────────────── */

type CompareFetchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; a: RunArtefactBundleLike; b: RunArtefactBundleLike }
  | { status: "error"; error: string };

function CompareSection({
  runIdA,
  runIdB,
  currentRunId,
  currentBundle,
}: {
  runIdA: string;
  runIdB: string;
  currentRunId: string | null;
  currentBundle: RunArtefactBundle;
}) {
  const [state, setState] = useState<CompareFetchState>({ status: "idle" });

  // Håll en ref till currentBundle så effect-en inte triggar om bara
  // parent-bundlen refreshas (skulle ge en onödig laddnings-flash +
  // dubbla HTTP-anrop). Ref:en uppdateras i en separat effect så React
  // 19:s react-hooks/refs-rule (ingen mutation under render) respekteras.
  // Tajming OK eftersom fetch-effect-en nedan re-kör baserat på id-
  // ändringar, inte på bundle-referensen.
  const currentBundleRef = useRef(currentBundle);
  useEffect(() => {
    currentBundleRef.current = currentBundle;
  });

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (cancelled) return;
      setState({ status: "loading" });
      try {
        // Hämta artefakter parallellt. Återanvänd currentBundle om någon
        // av runs är den aktiva — sparar en HTTP-roundtrip.
        const [a, b] = await Promise.all([
          fetchBundle(runIdA, currentRunId, currentBundleRef.current),
          fetchBundle(runIdB, currentRunId, currentBundleRef.current),
        ]);
        if (cancelled) return;
        setState({ status: "ok", a, b });
      } catch (caught) {
        if (cancelled) return;
        setState({
          status: "error",
          error: caught instanceof Error ? caught.message : "Okänt fel.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runIdA, runIdB, currentRunId]);

  if (state.status === "loading" || state.status === "idle") {
    return (
      <div className="border-border/40 text-muted-foreground flex h-24 items-center justify-center gap-2 rounded-lg border bg-muted/20 text-[12px]">
        <Loader2 className="h-4 w-4 animate-spin" />
        Räknar diff…
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <p
        role="alert"
        className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
      >
        {state.error}
      </p>
    );
  }

  const diff = computeRunDiff(state.a, state.b);
  return <DiffView diff={diff} />;
}

async function fetchBundle(
  runId: string,
  currentRunId: string | null,
  currentBundle: RunArtefactBundle,
): Promise<RunArtefactBundleLike> {
  if (runId === currentRunId) {
    return currentBundle;
  }
  const response = await fetch(`/api/runs/${runId}/artifacts`);
  const raw = (await response.json()) as unknown;
  const errorField =
    raw && typeof raw === "object" && "error" in raw
      ? (raw as { error: unknown }).error
      : null;
  if (!response.ok || typeof errorField === "string") {
    throw new Error(
      typeof errorField === "string" ? errorField : `HTTP ${response.status}`,
    );
  }
  // Defensiv shape-validering — vi vill hellre fånga ett malformat
  // svar med ett tydligt fel än att låta diff-vyn rendera tomma
  // sektioner och förvirra operatören. Speglar pattern:et i
  // run-details-panel.tsx.
  if (!raw || typeof raw !== "object" || !("runId" in raw)) {
    throw new Error(
      "Artefakt-svar saknar förväntat shape (runId/buildResult/sitePlan).",
    );
  }
  const bundle = raw as RunArtefactBundleLike;
  if (typeof bundle.runId !== "string" || bundle.runId.length === 0) {
    throw new Error("Artefakt-svar har ogiltigt runId.");
  }
  return bundle;
}

/* ── Diff-render ─────────────────────────────────────────────────── */

function DiffView({ diff }: { diff: RunDiff }) {
  const summary = formatDiffSummary(diff);
  const hasChanges = summary !== "Inga ändringar";

  return (
    <section className="border-border/60 flex flex-col gap-3 rounded-lg border bg-card p-4">
      <header className="border-border/40 flex items-center justify-between gap-2 border-b pb-2">
        <h3 className="flex items-center gap-1.5 text-[12.5px] font-semibold tracking-tight">
          <GitCompare aria-hidden className="h-3.5 w-3.5" />
          Diff A → B
        </h3>
        <Badge
          variant="outline"
          className={cn(
            "font-mono text-[10px]",
            hasChanges
              ? "border-foreground/40 text-foreground"
              : "text-muted-foreground",
          )}
        >
          {summary}
        </Badge>
      </header>

      <ScalarChangeRow label="Scaffold" change={diff.scaffold} mono />
      <ScalarChangeRow label="Variant" change={diff.variant} mono />
      <ScalarChangeRow label="Starter" change={diff.starter} mono />
      <ScalarChangeRow
        label="Quality Gate"
        change={diff.qualityStatus}
        tone="status"
      />
      <ScalarChangeRow
        label="Build"
        change={diff.buildStatus}
        tone="status"
      />

      <ChipDiffRow
        label="Routes"
        added={diff.routesAdded}
        removed={diff.routesRemoved}
        emptyHint="Samma route-plan i båda versionerna."
        mono
      />
      <ChipDiffRow
        label="Tone-tags"
        added={diff.toneAdded}
        removed={diff.toneRemoved}
        emptyHint="Samma tonalitet."
      />
      <ChipDiffRow
        label="Capabilities"
        added={diff.capabilitiesAdded}
        removed={diff.capabilitiesRemoved}
        emptyHint="Samma efterfrågade funktioner."
      />
    </section>
  );
}

function ScalarChangeRow({
  label,
  change,
  mono,
  tone,
}: {
  label: string;
  change: { before: string | null; after: string | null; equal: boolean };
  mono?: boolean;
  tone?: "status";
}) {
  const noData = change.before === null && change.after === null;
  return (
    <div className="flex items-center justify-between gap-3 text-[11.5px]">
      <span className="text-muted-foreground font-medium">{label}</span>
      <div className="flex min-w-0 items-center gap-1.5">
        {noData ? (
          <span className="text-muted-foreground/70 italic">saknas i båda</span>
        ) : change.equal ? (
          <ValueChip
            value={change.after ?? "—"}
            mono={mono}
            tone={tone}
            equal
          />
        ) : (
          <>
            <ValueChip
              value={change.before ?? "saknas"}
              mono={mono}
              tone={tone}
              variant="before"
            />
            <ArrowRight
              aria-hidden
              className="text-muted-foreground/60 h-3 w-3 shrink-0"
            />
            <ValueChip
              value={change.after ?? "saknas"}
              mono={mono}
              tone={tone}
              variant="after"
            />
          </>
        )}
      </div>
    </div>
  );
}

function ValueChip({
  value,
  mono,
  tone,
  variant,
  equal,
}: {
  value: string;
  mono?: boolean;
  tone?: "status";
  variant?: "before" | "after";
  equal?: boolean;
}) {
  const STATUS_TONE: Record<string, string> = {
    ok: "bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-300",
    passed:
      "bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-300",
    "mock-complete":
      "bg-sky-500/15 text-sky-700 border-sky-500/30 dark:text-sky-300",
    degraded:
      "bg-amber-500/15 text-amber-800 border-amber-500/30 dark:text-amber-300",
    warning:
      "bg-amber-500/15 text-amber-800 border-amber-500/30 dark:text-amber-300",
    failed: "bg-destructive/15 text-destructive border-destructive/30",
    skipped: "bg-muted text-muted-foreground border-border",
    unknown: "bg-muted text-muted-foreground border-border",
  };

  const colorClass =
    tone === "status" && STATUS_TONE[value]
      ? STATUS_TONE[value]
      : equal
        ? "border-border/60 bg-muted/40 text-muted-foreground"
        : variant === "before"
          ? "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300"
          : "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";

  return (
    <span
      title={value}
      className={cn(
        "inline-block max-w-[160px] truncate rounded-md border px-1.5 py-0.5 text-[11px]",
        mono ? "font-mono" : "",
        colorClass,
      )}
    >
      {value}
    </span>
  );
}

function ChipDiffRow({
  label,
  added,
  removed,
  emptyHint,
  mono,
}: {
  label: string;
  added: string[];
  removed: string[];
  emptyHint: string;
  mono?: boolean;
}) {
  const isEmpty = added.length === 0 && removed.length === 0;
  return (
    <div className="border-border/40 flex flex-col gap-1.5 border-t pt-2.5 text-[11.5px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground font-medium">{label}</span>
        <span className="text-muted-foreground font-mono text-[10px]">
          +{added.length} −{removed.length}
        </span>
      </div>
      {isEmpty ? (
        <p className="text-muted-foreground/70 italic text-[11px]">
          {emptyHint}
        </p>
      ) : (
        <div className="flex flex-wrap gap-1">
          {added.map((item) => (
            <ChangeChip key={`add-${item}`} kind="add" value={item} mono={mono} />
          ))}
          {removed.map((item) => (
            <ChangeChip
              key={`rem-${item}`}
              kind="remove"
              value={item}
              mono={mono}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ChangeChip({
  kind,
  value,
  mono,
}: {
  kind: "add" | "remove";
  value: string;
  mono?: boolean;
}) {
  const toneClass =
    kind === "add"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
      : "border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300";
  const symbol = kind === "add" ? "+" : "−";
  return (
    <span
      title={`${symbol} ${value}`}
      className={cn(
        "inline-flex max-w-[200px] items-center gap-1 truncate rounded-md border px-1.5 py-0.5 text-[10.5px]",
        toneClass,
        mono ? "font-mono" : "",
      )}
    >
      <span aria-hidden className="opacity-80">
        {symbol}
      </span>
      <span className="truncate">{value}</span>
    </span>
  );
}

function CompareEmptyHint({
  hasA,
  hasB,
}: {
  hasA: boolean;
  hasB: boolean;
}) {
  const message =
    !hasA && !hasB
      ? "Välj två versioner (A + B) för att se diff."
      : hasA && !hasB
        ? "Välj B för att räkna diff mot A."
        : !hasA && hasB
          ? "Välj A för att räkna diff mot B."
          : "A och B är samma version — välj olika för att se diff.";
  return (
    <div className="border-border/40 text-muted-foreground flex items-center gap-2 rounded-lg border bg-muted/20 px-3 py-2.5 text-[11.5px]">
      <GitCompare aria-hidden className="h-3.5 w-3.5 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

/* ── Empty state ─────────────────────────────────────────────────── */

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-border/40 bg-foreground/[0.02] flex flex-col items-start gap-1.5 rounded-lg border p-4">
      <div className="text-foreground text-[12.5px] font-medium tracking-tight">
        {title}
      </div>
      <p className="text-muted-foreground text-[11.5px] leading-relaxed">
        {body}
      </p>
    </div>
  );
}
