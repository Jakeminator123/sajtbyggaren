"use client";

import {
  ArrowRight,
  CircleCheck,
  Clock,
  Copy,
  Eye,
  GitBranch,
  GitCompare,
  Layers,
  Loader2,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import {
  type ComponentType,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  computeRunDiff,
  type RunArtefactBundleLike,
} from "@/components/builder/inspector/run-diff";
import {
  CompareEmptyHint,
  ComparePreviewLoadError,
  DiffView,
  VersionsEmptyState,
} from "@/components/builder/inspector/versions-tab/diff-view";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";
import type {
  PendingBaseRunIdState,
  PendingBuildState,
} from "@/components/builder/use-pending-build";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SECONDARY_INTERACTIONS } from "@/lib/ui-tokens";
import { cn } from "@/lib/utils";

/**
 * Props-shape för den lazy-laddade jämförelsemodalen. Inlinad här så ingen
 * ``import``-rad (varken runtime eller typ) binder VersionsTab-modulen till
 * ``compare-preview-modal`` (och dess StackBlitz-graf).
 */
type ComparePreviewModalComponentProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  runIdA: string;
  runIdB: string;
  versionA: number | null | undefined;
  versionB: number | null | undefined;
};

/**
 * ``ComparePreviewModal`` laddas LAZY via en RUNTIME ``import()`` i en
 * EVENT-HANDLER (``openComparePreview`` nedan) — MEDVETET INTE via top-level
 * ``next/dynamic``.
 *
 * Modalen drar in StackBlitz-modulgrafen (``compare-preview-modal`` använder
 * ``await import("@stackblitz/sdk")`` i sina paneler). En top-level
 * ``dynamic(() => import("compare-preview-modal"))`` får Next/Turbopack att
 * STATISKT pre-scripta den grafens chunks (inkl. SDK-vendor-chunken) som
 * ``<script async>`` i studio.html — exakt den eager bundle-bloat vi vill bli
 * av med. Genom att i stället anropa ``import()`` först när operatören klickar
 * "Visuell jämförelse" ligger referensen utanför den eager-analyserade grafen
 * och SDK-chunken hämtas först när modalen faktiskt öppnas.
 */
const COMPARE_PREVIEW_MODAL_IMPORT = () =>
  import("@/components/builder/inspector/compare-preview-modal");

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
  // `aborted` = dödat bygge (stale-pending). Röd som failed; speglar
  // run-history.tsx-paletten så de två versionsvyerna är konsekventa.
  aborted: "bg-destructive",
  // `pending` = bygget pågår faktiskt. Egen sky-färg + puls (se dotClass)
  // så det inte ser ut som de grå terminal-statusarna.
  pending: "bg-sky-400",
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

// Absolut tidsstämpel för title-tooltip på relativa tiden (samma mönster
// som run-history.tsx). Operatören hovrar och ser exakt datum/tid.
function formatAbsolute(createdAt: string): string {
  const ts = Date.parse(createdAt);
  if (!Number.isFinite(ts)) return "";
  return new Date(ts).toLocaleString("sv-SE", {
    dateStyle: "medium",
    timeStyle: "short",
  });
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
  /**
   * Operator-vald baseRunId. Highlight:ar motsvarande rad så
   * operatören ser vilken version "Iterera från denna" är aktiv på.
   */
  pendingBaseRunId?: PendingBaseRunIdState | null;
  /**
   * Sätt baseRunId från en versions-rad. När angiven aktiverar UI
   * direkt-iterate (FloatingChat skickar baseRunId i fetch). När
   * undefined faller vi tillbaka till clipboard-workaround så
   * Versions-tab kan användas både i denna PR och vid eventuell
   * future split.
   */
  onSetPendingBaseRunId?: (
    runId: string | null,
    version?: number | null,
  ) => void;
  /**
   * Stänger Site Inspector så operatören får synlig FloatingChat
   * efter klick på "Iterera från denna". Inspectorn täcker annars
   * chat-rutan på smal viewport.
   */
  onCloseInspector?: () => void;
}

export function VersionsTab({
  bundle,
  siteId,
  currentRunId,
  isBuilding,
  pendingBuild,
  pendingBaseRunId,
  onSetPendingBaseRunId,
  onCloseInspector,
}: VersionsTabProps) {
  const [allRuns, setAllRuns] = useState<RunMeta[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [compareA, setCompareA] = useState<string | null>(null);
  const [compareB, setCompareB] = useState<string | null>(null);
  // Sida-vid-sida visuell preview-modal. Aktiveras när operatören klickar
  // "Visuell jämförelse"-knappen i CompareControls och båda A+B är valda.
  // Modal-state lever lokalt här eftersom det är en peer-yta till diff-
  // panelen — inte en globalt delad state. (GAP-viewser-side-by-side-preview.)
  const [comparePreviewOpen, setComparePreviewOpen] = useState(false);
  // Den lazy-laddade jämförelsemodalen. Laddas via en runtime ``import()`` i
  // ``openComparePreview`` (aldrig top-level ``dynamic()``) först när operatören
  // öppnar den; stannar sedan monterad så öppna/stäng-animationen är oförändrad.
  const [ComparePreviewModalComp, setComparePreviewModalComp] =
    useState<ComponentType<ComparePreviewModalComponentProps> | null>(null);
  // Sätts om jämförelsemodalens lazy ``import()`` failar (annars tyst död knapp).
  const [comparePreviewError, setComparePreviewError] = useState<string | null>(
    null,
  );

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
        // Site-scoped fetch: server filtrerar och expanderar slice-fönstret
        // (limit*4) för rätt site så att äldre versioner inte tappas bort
        // när andra sajter dominerar de senaste 20 globala runsen
        // (GAP-backend-build-trace-endpoint, server-filter i lib/runs.ts).
        const response = await fetch(
          `/api/runs?siteId=${encodeURIComponent(siteId)}`,
        );
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
  }, [reloadToken, siteId]);

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

  // "Iterera från denna" — primär väg är att sätta baseRunId så
  // FloatingChat skickar det i nästa /api/prompt-fetch
  // (GAP-backend-build-trace-endpoint). Vi behåller en clipboard-
  // fallback för säkerhets skull (om callback saknas eller direkt-
  // läge inte är aktivt) — det skadar inte ens när direct-mode är
  // aktivt eftersom feedback bara visas vid clipboard-fall.
  const [copyFeedback, setCopyFeedback] = useState<{
    runId: string;
    kind: "success" | "failure";
    prefix: string;
  } | null>(null);
  const copyFeedbackTimerRef = useRef<number | null>(null);
  const handleIterateFrom = useCallback(
    async (runId: string, version: number | null | undefined) => {
      // Direct mode (PR scope): sätt baseRunId, stäng Inspectorn så
      // FloatingChat blir synlig, klart. Ingen clipboard-skrivning.
      if (onSetPendingBaseRunId) {
        // Toggle: klick på samma rad avmarkerar.
        if (pendingBaseRunId?.baseRunId === runId) {
          onSetPendingBaseRunId(null);
          return;
        }
        onSetPendingBaseRunId(runId, version ?? null);
        onCloseInspector?.();
        return;
      }

      // Fallback (om denna komponent används utan callback): kopiera
      // prompt-prefix till clipboard och visa en bekräftelse. Operatören
      // klistrar in i chat-rutan manuellt.
      const versionLabel = version ?? "?";
      const prefix = `Utgå från version ${versionLabel}: `;
      let kind: "success" | "failure" = "failure";
      try {
        if (
          typeof navigator !== "undefined" &&
          navigator.clipboard?.writeText
        ) {
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
    [onSetPendingBaseRunId, onCloseInspector, pendingBaseRunId?.baseRunId],
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

  // Highlighten ska bara döljas medan bygget för DENNA sajt pågår — om
  // operatören har en pågående build för en annan sajt (t.ex. byter
  // mellan sajter i ConsoleDrawer) ska iterations-indikatorn för den
  // här sajten fortfarande synas. `pendingForThisSite` gör redan
  // siteId-jämförelsen ovan så vi återanvänder den.
  const activeBaseRunId =
    pendingBaseRunId && !pendingForThisSite ? pendingBaseRunId.baseRunId : null;

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
    // Stäng den visuella jämförelsen också — annars står comparePreviewOpen
    // kvar true och modalen poppar upp igen så fort A+B väljs på nytt.
    setComparePreviewOpen(false);
  }, []);

  // Öppna jämförelsemodalen och ladda dess komponent via en runtime ``import()``
  // (event-handler, inte top-level dynamic()). Failar importen visas ett fel.
  const openComparePreview = useCallback(() => {
    setComparePreviewError(null);
    setComparePreviewOpen(true);
    if (ComparePreviewModalComp) return;
    void COMPARE_PREVIEW_MODAL_IMPORT()
      .then((mod) => {
        setComparePreviewModalComp(() => mod.ComparePreviewModal);
      })
      .catch(() => {
        // Importen kan faila (nät/utgången deploy) → kort fel, inte tyst blankt.
        setComparePreviewOpen(false);
        setComparePreviewError("Visuell jämförelse kunde inte laddas.");
      });
  }, [ComparePreviewModalComp]);

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
      <div
        role="status"
        aria-live="polite"
        aria-busy="true"
        className="flex flex-col gap-3"
      >
        <span className="sr-only">Läser versioner…</span>
        {/* Approximerar version-listans header + 4 rader. Höjd 56px
            speglar den verkliga radens kompakta höjd (badge + timestamp
            + status + actions). Layouten hoppar inte när data landar. */}
        <Skeleton className="h-4 w-40" />
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
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
          <ul className="border-border/60 bg-card overflow-hidden rounded-lg border">
            <PendingRunRow pending={pendingForThisSite} />
          </ul>
        </div>
      );
    }
    return (
      <VersionsEmptyState
        title="Inga versioner ännu"
        body="När du skickar följdprompter dyker varje ny version upp här. Den senaste 20 syns alltid (äldre rullar ut)."
      />
    );
  }

  // Slå upp version-tal för A/B från siteRuns så modalen kan visa
  // "v3 vs v5" i stället för rena runIds. Saknas runId i listan
  // (osannolikt — A/B kan bara väljas från siteRuns) faller version
  // tillbaka till null och modalen visar "v?".
  const versionForA =
    compareA != null
      ? (siteRuns.find((run) => run.runId === compareA)?.version ?? null)
      : null;
  const versionForB =
    compareB != null
      ? (siteRuns.find((run) => run.runId === compareB)?.version ?? null)
      : null;
  const canOpenComparePreview =
    compareA !== null && compareB !== null && compareA !== compareB;

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
        canOpenComparePreview={canOpenComparePreview}
        onOpenComparePreview={openComparePreview}
      />

      {comparePreviewError ? (
        <ComparePreviewLoadError message={comparePreviewError} />
      ) : null}

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
        activeBaseRunId={activeBaseRunId}
        copyFeedback={copyFeedback}
        onIterateFrom={handleIterateFrom}
        isBuilding={isBuilding}
      />

      {compareA && compareB && compareA !== compareB ? (
        <CompareSection
          runIdA={compareA}
          runIdB={compareB}
          currentRunId={currentRunId}
          currentBundle={bundle}
        />
      ) : (
        <CompareEmptyHint hasA={compareA !== null} hasB={compareB !== null} />
      )}

      {ComparePreviewModalComp && canOpenComparePreview && compareA && compareB ? (
        <ComparePreviewModalComp
          open={comparePreviewOpen}
          onOpenChange={setComparePreviewOpen}
          runIdA={compareA}
          runIdB={compareB}
          versionA={versionForA}
          versionB={versionForB}
        />
      ) : null}
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
        högerkolumnen för <strong>B</strong>. När båda är valda visas en diff
        längst ned.
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
        <RotateCcw aria-hidden className="h-3.5 w-3.5" />
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
  canOpenComparePreview,
  onOpenComparePreview,
}: {
  compareA: string | null;
  compareB: string | null;
  onReset: () => void;
  onCompareLatestTwo: () => void;
  canCompareLatestTwo: boolean;
  canOpenComparePreview: boolean;
  onOpenComparePreview: () => void;
}) {
  return (
    <div className="border-border/60 bg-card flex flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2">
      <div className="flex min-w-0 flex-1 items-center gap-2 text-[11.5px]">
        <CompareBadge label="A" value={compareA} tone="rose" />
        <ArrowRight
          aria-hidden
          className="text-muted-foreground/60 h-3 w-3 shrink-0"
        />
        <CompareBadge label="B" value={compareB} tone="emerald" />
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1">
        <button
          type="button"
          onClick={onOpenComparePreview}
          disabled={!canOpenComparePreview}
          title={
            canOpenComparePreview
              ? "Öppna sida-vid-sida visuell jämförelse"
              : "Välj A och B först"
          }
          className={cn(
            "text-foreground/80 hover:text-foreground border-foreground/30 hover:border-foreground/60 hover:bg-foreground/5",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors disabled:opacity-40",
            SECONDARY_INTERACTIONS,
          )}
        >
          <Eye aria-hidden className="h-3 w-3" />
          Visuell jämförelse
        </button>
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
      <span className="truncate">{value ? shortRunId(value) : "ej valt"}</span>
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
  activeBaseRunId,
  copyFeedback,
  onIterateFrom,
  isBuilding,
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
  activeBaseRunId: string | null;
  copyFeedback: CopyFeedback;
  onIterateFrom: (runId: string, version: number | null | undefined) => void;
  isBuilding: boolean;
}) {
  return (
    <ul className="border-border/60 divide-border/40 bg-card divide-y overflow-hidden rounded-lg border">
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
            isActiveBase={activeBaseRunId === run.runId}
            copyFeedback={feedbackForRow}
            isBuilding={isBuilding}
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
  const elapsedSeconds = Math.max(
    1,
    Math.round((now - pending.startedAt) / 1000),
  );
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
      className="flex items-stretch gap-0 border-b border-dashed border-amber-400/30 bg-amber-500/[0.06] last:border-b-0"
    >
      <div className="min-w-0 flex-1 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span
            aria-hidden
            className="inline-block h-2 w-2 shrink-0 animate-pulse rounded-full bg-amber-500"
          />
          <span className="text-foreground/85 text-[12px] font-medium">
            {versionLabel}
          </span>
          <Loader2
            aria-hidden
            className="h-3 w-3 shrink-0 animate-spin text-amber-600 dark:text-amber-400"
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
  isActiveBase,
  copyFeedback,
  isBuilding,
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
  isActiveBase: boolean;
  copyFeedback: CopyFeedback;
  isBuilding: boolean;
  onSelectA: () => void;
  onSelectB: () => void;
  onIterateFrom: () => void;
}) {
  const dotClass = STATUS_DOT_COLORS[run.status] ?? "bg-muted-foreground/40";
  // Bara `pending` pulserar (faktiskt pågående bygge). motion-safe så
  // reduced-motion-användare ser en stilla prick.
  const dotPulse =
    run.status === "pending" ? "motion-safe:animate-pulse" : undefined;
  // Spärra "Iterera" under pågående bygge: pendingBaseRunId rensas av
  // page.tsx när bygget är klart, så ett klick mitt i bygget skulle
  // sättas och sedan tystas. Bättre att hindra interaktionen helt än
  // att låta operatören tro att deras val konsumerades. (H3 i bug-hunt
  // 2026-05-25 för GAP-backend-build-trace-endpoint.)
  const iterateDisabled = isCurrent || isBuilding;
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
        isActiveBase
          ? "bg-sky-500/[0.08] ring-1 ring-sky-500/40 ring-inset"
          : "",
      )}
    >
      <div className="min-w-0 flex-1 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span
            aria-label={`status: ${run.status}`}
            className={cn(
              "inline-block size-2 rounded-full",
              dotClass,
              dotPulse,
            )}
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
          {isActiveBase ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-sky-500/50 bg-sky-500/[0.10] px-1.5 py-0.5 font-mono text-[9px] tracking-wider text-sky-700 uppercase dark:text-sky-300">
              <GitBranch aria-hidden className="h-2.5 w-2.5" />
              Iterera
            </span>
          ) : null}
        </div>
        <div className="text-muted-foreground mt-0.5 flex items-center gap-1.5 pl-4 text-[10.5px]">
          <Clock aria-hidden className="h-2.5 w-2.5" />
          <span title={formatAbsolute(run.createdAt)}>
            {formatRelative(run.createdAt)}
          </span>
          {run.version ? ` · v${run.version}` : ""}
          {run.status ? ` · ${run.status}` : ""}
        </div>
        {rationale ? (
          <p className="text-muted-foreground mt-1 line-clamp-2 pl-4 text-[10.5px] leading-snug italic">
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
            isCurrent
              ? "Senaste versionen — chatten utgår alltid härifrån"
              : isBuilding
                ? "Vänta tills nuvarande bygge är klart"
                : isActiveBase
                  ? "Aktiv som bas för nästa följdprompt — klicka igen för att avmarkera"
                  : `Iterera från version ${run.version ?? "?"}`
          }
          aria-label={
            isCurrent
              ? `Senaste versionen ${shortRunId(run.runId)}`
              : isBuilding
                ? `Iterera från version ${run.version ?? "?"} (inaktiverad under bygge)`
                : `Iterera från version ${run.version ?? "?"}`
          }
          aria-pressed={isActiveBase}
          className={cn(
            "flex w-9 items-center justify-center transition-colors",
            "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:outline-none",
            iterateDisabled
              ? "text-muted-foreground/40 cursor-not-allowed"
              : isActiveBase
                ? "bg-sky-500/[0.12] text-sky-700 hover:bg-sky-500/[0.18] dark:text-sky-300"
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

  // Signal som ändrar identitet när den AKTIVA runens bundle byggs om/
  // refreshas OCH den deltar i jämförelsen. Tidigare re-kördes fetch-effekten
  // bara på id-byten → om ena sidan var aktiv run och dess bundle uppdaterades
  // (manuell refresh / klart bygge med samma runId) visade diffen den gamla
  // bundlen. När ingen sida är aktiv run förblir signalen null så vi behåller
  // optimeringen (ingen onödig laddnings-flash vid parent-refresh).
  const activeBundleSignal = useMemo(
    () =>
      runIdA === currentRunId || runIdB === currentRunId ? currentBundle : null,
    [runIdA, runIdB, currentRunId, currentBundle],
  );

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
    // activeBundleSignal: re-fetcha diffen när den aktiva runens bundle
    // ändrats (annars stale diff). currentBundleRef läses inuti, så vi
    // behöver inte själva bundle-objektet i deps utöver signalen.
  }, [runIdA, runIdB, currentRunId, activeBundleSignal]);

  if (state.status === "loading" || state.status === "idle") {
    return (
      <div
        role="status"
        aria-live="polite"
        aria-busy="true"
        className="border-border/40 bg-muted/10 flex flex-col gap-2 rounded-lg border p-3"
      >
        <span className="sr-only">Räknar diff…</span>
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-2/3" />
        <Skeleton className="h-3 w-1/2" />
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
