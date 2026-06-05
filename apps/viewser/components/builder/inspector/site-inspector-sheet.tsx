"use client";

import { RefreshCw, ScanSearch } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BriefTab } from "@/components/builder/inspector/brief-tab";
import { DossiersTab } from "@/components/builder/inspector/dossiers-tab";
import { PagesTab } from "@/components/builder/inspector/pages-tab";
import { QualityTab } from "@/components/builder/inspector/quality-tab";
import { TokensTab } from "@/components/builder/inspector/tokens-tab";
import { useRunArtefacts } from "@/components/builder/inspector/use-run-artefacts";
import { VariantsTab } from "@/components/builder/inspector/variants-tab";
import { VersionsTab } from "@/components/builder/inspector/versions-tab";
import { useFollowupBuild } from "@/components/builder/use-followup-build";
import type {
  PendingBaseRunIdState,
  PendingBuildState,
} from "@/components/builder/use-pending-build";
import type { PromptBuildOutcome } from "@/components/prompt-builder";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/**
 * Site Inspector — Nivå 3 av builderns UX-stack.
 *
 * Slide-in från höger som ger operatören strukturerad insyn i den
 * aktiva run:en + per-sektion-snabbprompts kopplade till samma
 * follow-up-bygg-pipeline som FloatingChat och Nivå 2-dialogerna
 * använder.
 *
 * Inspectorn renderar sju tabs:
 *
 *   1. Sidor       — routePlan + pageIntentWarnings
 *   2. Brief & Plan — företag, ton, tjänster, scaffold/variant
 *   3. Variants    — live-switch mellan registrerade scaffold-variants
 *   4. Versioner   — site-scoped versionshistorik + A/B-diff mellan runs
 *   5. Färger      — runtime token-overrides + commit-flow
 *   6. Dossiers    — required/recommended/conditional/rejected
 *   7. Kvalitet    — buildResult + qualityResult + repairResult
 *
 * All data kommer från `/api/runs/[runId]/artifacts`. Vi har inget
 * polling — operatören får en refresh-knapp i headern och inspectorn
 * re-fetchar automatiskt när `runId` ändras (vilket sker efter varje
 * lyckat bygge eftersom page.tsx uppdaterar selectedRunId).
 */

type SiteInspectorSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  runId: string | null;
  isBuilding: boolean;
  /**
   * Pending build-state från Live Build Sync. Skickas vidare till
   * Versions-tab så den kan rendera en optimistisk "Bygger…"-rad
   * högst upp i listan medan build pågår.
   */
  pendingBuild?: PendingBuildState | null;
  /**
   * Operator-vald baseRunId. Skickas vidare till Versions-tab så
   * "Iterera från denna" kan markera vald rad och uppdatera state.
   */
  pendingBaseRunId?: PendingBaseRunIdState | null;
  onSetPendingBaseRunId?: (
    runId: string | null,
    version?: number | null,
  ) => void;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
};

export function SiteInspectorSheet({
  open,
  onOpenChange,
  siteId,
  runId,
  isBuilding,
  pendingBuild,
  pendingBaseRunId,
  onSetPendingBaseRunId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
}: SiteInspectorSheetProps) {
  const { state, refresh } = useRunArtefacts(runId, open);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  // Aktiv tab lyfts till komponent-scope (i st.f. Tabs defaultValue) så valet
  // överlever att <Tabs> av-/återmonteras när artefakter refreshas
  // (status ok→loading→ok). Tidigare återställdes tabben till "Sidor" varje
  // gång operatören tryckte uppdatera eller ett bygge landade.
  const [activeTab, setActiveTab] = useState("pages");
  const {
    runFollowup,
    error: buildError,
    clearError,
  } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
  });

  // Rensa inline-byggfelet när panelen stängs. Annars överlevde ett fel
  // sheet-stängningen och dök upp igen nästa gång operatören öppnade
  // inspectorn — trots att det hörde till en sedan länge avslutad run.
  useEffect(() => {
    if (!open) clearError();
  }, [open, clearError]);

  // Skicka en följdprompt direkt från en quick-knapp i någon tab.
  // Inspectorn stängs när bygget startar så operatören ser preview-
  // uppdateringen istället för panelens innehåll. Run-id byts av
  // page.tsx vid lyckat bygge → nästa öppning re-fetchar artefakter
  // automatiskt (useRunArtefacts har runId i deps).
  const handlePrompt = useCallback(
    async (prompt: string) => {
      if (isBuilding) return;
      setPendingPrompt(prompt);
      try {
        const result = await runFollowup(prompt);
        if (result.ok) onOpenChange(false);
      } finally {
        setPendingPrompt(null);
      }
    },
    [isBuilding, runFollowup, onOpenChange],
  );

  const sharedTabProps = {
    isBuilding,
    pendingPrompt,
    onPrompt: handlePrompt,
  };

  // På mobil renderas inspector som bottom-sheet (drag-handle,
  // rounded-top, max-h-[90dvh]) istället för side-drawer. Sido-
  // drawern tog 75% bredd på 375px-skärmar och thumb-reach mot
  // höger-edge är dålig på stora telefoner. Tabs-raden får också
  // horisontell scroll under md: så de 7 triggers inte overflowar.
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="max-md:pb-safe w-full max-w-[560px] gap-0 p-0 max-md:!inset-x-0 max-md:!top-auto max-md:!right-0 max-md:!bottom-0 max-md:!left-0 max-md:!h-[90dvh] max-md:!w-full max-md:!max-w-none max-md:!rounded-t-3xl max-md:!border-t max-md:!border-l-0 sm:max-w-[560px]"
      >
        {/* Bottom-sheet drag-handle (mobile only). Endast visuell —
            informerar operatören att panelen är swipe:bar (faktisk
            drag-to-dismiss skickas till framtida P2-arbete, men
            handle:n är ett standardiserat bottom-sheet-affordance
            som matchar SheetContent side="bottom"-pattern. md:hidden
            så den inte syns i desktop-side-drawer. */}
        <div aria-hidden className="bottom-sheet-handle md:hidden" />
        <SheetHeader className="border-border/60 flex flex-row items-start justify-between gap-3 border-b p-5 max-md:pt-2">
          <div className="flex min-w-0 flex-col gap-1">
            <SheetTitle className="flex items-center gap-2 text-[16px] tracking-tight">
              <ScanSearch className="h-4 w-4" aria-hidden />
              Inspektera sajten
            </SheetTitle>
            <SheetDescription className="text-[11.5px]">
              Strukturerad vy av denna run.{" "}
              {runId ? (
                <code className="text-muted-foreground bg-muted/50 rounded px-1 py-0.5 font-mono text-[10px]">
                  {runId.slice(0, 36)}…
                </code>
              ) : null}
            </SheetDescription>
          </div>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={refresh}
            disabled={state.status === "loading"}
            aria-label="Uppdatera artefakter"
            title="Uppdatera artefakter"
            className="min-tap sm:min-tap-0 mr-9 shrink-0"
          >
            <RefreshCw
              aria-hidden
              className={`h-3.5 w-3.5 ${state.status === "loading" ? "animate-spin" : ""}`}
            />
          </Button>
        </SheetHeader>

        <div className="flex-1 overflow-hidden">
          {state.status === "loading" || (state.status === "idle" && runId) ? (
            // idle + giltig runId = fetch är på väg (useRunArtefacts-effekten
            // sätter loading efter en mikrotask). Visa skelett direkt så vi
            // inte blinkar "Ingen aktiv run" en frame innan hämtningen börjar.
            <InspectorLoadingSkeleton />
          ) : state.status === "error" ? (
            <div className="p-5">
              <p
                role="alert"
                className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
              >
                {state.error}
              </p>
            </div>
          ) : state.status !== "ok" || !runId ? (
            <div className="text-muted-foreground flex h-full items-center justify-center px-6 text-center text-[12px]">
              <span>
                Ingen aktiv run.
                <br />
                Bygg en sajt först — sedan kan du inspektera den här.
              </span>
            </div>
          ) : (
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex h-full flex-col gap-0"
            >
              {/* overflow-x-auto + scrollbar-hidden gör att de 7
                  triggers kan scrolla horisontellt på smala viewports
                  utan visuell scrollbar. På desktop ryms alla. */}
              <TabsList
                variant="line"
                className="border-border/60 scrollbar-hidden w-full justify-start gap-1 overflow-x-auto border-b px-4 pt-2 pb-2"
              >
                <TabsTrigger value="pages" className="min-tap md:min-tap-0">
                  Sidor
                </TabsTrigger>
                <TabsTrigger value="brief" className="min-tap md:min-tap-0">
                  Brief &amp; Plan
                </TabsTrigger>
                <TabsTrigger value="variants" className="min-tap md:min-tap-0">
                  Variants
                </TabsTrigger>
                <TabsTrigger value="versions" className="min-tap md:min-tap-0">
                  Versioner
                </TabsTrigger>
                <TabsTrigger value="tokens" className="min-tap md:min-tap-0">
                  Färger
                </TabsTrigger>
                <TabsTrigger value="dossiers" className="min-tap md:min-tap-0">
                  Dossiers
                </TabsTrigger>
                <TabsTrigger value="quality" className="min-tap md:min-tap-0">
                  Kvalitet
                </TabsTrigger>
              </TabsList>
              <div className="flex-1 overflow-y-auto px-5 py-4">
                <TabsContent value="pages">
                  <PagesTab bundle={state.bundle} {...sharedTabProps} />
                </TabsContent>
                <TabsContent value="brief">
                  <BriefTab bundle={state.bundle} {...sharedTabProps} />
                </TabsContent>
                <TabsContent value="variants">
                  <VariantsTab bundle={state.bundle} {...sharedTabProps} />
                </TabsContent>
                <TabsContent value="versions">
                  {/* key={siteId} re-mountar VersionsTab när operatören
                      byter aktiv sajt så A/B-compareval inte spiller
                      över till en annan sajts runs. */}
                  <VersionsTab
                    key={siteId}
                    bundle={state.bundle}
                    siteId={siteId}
                    currentRunId={runId}
                    isBuilding={isBuilding}
                    pendingBuild={pendingBuild ?? null}
                    pendingBaseRunId={pendingBaseRunId ?? null}
                    onSetPendingBaseRunId={onSetPendingBaseRunId}
                    onCloseInspector={() => onOpenChange(false)}
                  />
                </TabsContent>
                <TabsContent value="tokens">
                  <TokensTab {...sharedTabProps} />
                </TabsContent>
                <TabsContent value="dossiers">
                  <DossiersTab bundle={state.bundle} {...sharedTabProps} />
                </TabsContent>
                <TabsContent value="quality">
                  <QualityTab bundle={state.bundle} {...sharedTabProps} />
                </TabsContent>
              </div>
            </Tabs>
          )}
        </div>

        {buildError ? (
          <div className="border-border/60 border-t p-3">
            <p
              role="alert"
              className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
            >
              {buildError}
            </p>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

// Skeleton för Inspector-laddningstillståndet. Mimic:ar tab-strippen +
// 3 kort så operatören ser strukturen som kommer dyka upp istället för
// en tom canvas + spinner. ``role="status"`` + ``aria-live="polite"``
// + en sr-only-text säger till skärmläsare att vi laddar.
function InspectorLoadingSkeleton() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="flex h-full flex-col gap-0"
    >
      <span className="sr-only">Läser artefakter…</span>
      {/* Tab-strip-skeleton (sju triggers, samma höjd som riktiga
          TabsList:en så layouten inte hoppar när data landar). */}
      <div className="border-border/60 flex w-full items-center gap-3 border-b px-4 pt-2 pb-3">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-14 shrink-0 rounded-md" />
        ))}
      </div>
      {/* Tre kort som approximerar typisk tab-content. */}
      <div className="flex flex-col gap-3 px-5 py-4">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-16 w-full rounded-lg" />
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-12 w-full rounded-lg" />
        <Skeleton className="h-12 w-full rounded-lg" />
      </div>
    </div>
  );
}
