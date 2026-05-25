"use client";

import { Loader2, RefreshCw, ScanSearch } from "lucide-react";
import { useCallback, useState } from "react";

import { BriefTab } from "@/components/builder/inspector/brief-tab";
import { DossiersTab } from "@/components/builder/inspector/dossiers-tab";
import { PagesTab } from "@/components/builder/inspector/pages-tab";
import { QualityTab } from "@/components/builder/inspector/quality-tab";
import { TokensTab } from "@/components/builder/inspector/tokens-tab";
import { useRunArtefacts } from "@/components/builder/inspector/use-run-artefacts";
import { VariantsTab } from "@/components/builder/inspector/variants-tab";
import { VersionsTab } from "@/components/builder/inspector/versions-tab";
import { useFollowupBuild } from "@/components/builder/use-followup-build";
import type { PromptBuildOutcome } from "@/components/prompt-builder";
import { Button } from "@/components/ui/button";
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
  onBuildStart,
  onBuildEnd,
  onBuildDone,
}: SiteInspectorSheetProps) {
  const { state, refresh } = useRunArtefacts(runId, open);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const { runFollowup, error: buildError } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
  });

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

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full max-w-[560px] gap-0 p-0 sm:max-w-[560px]"
      >
        <SheetHeader className="border-border/60 flex flex-row items-start justify-between gap-3 border-b p-5">
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
            className="mr-9 shrink-0"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${state.status === "loading" ? "animate-spin" : ""}`}
            />
          </Button>
        </SheetHeader>

        <div className="flex-1 overflow-hidden">
          {state.status === "loading" ? (
            <div className="text-muted-foreground flex h-full items-center justify-center gap-2 text-[12px]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Läser artefakter…
            </div>
          ) : state.status === "error" ? (
            <div className="p-5">
              <p
                role="alert"
                className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
              >
                {state.error}
              </p>
            </div>
          ) : state.status === "idle" || !runId ? (
            <div className="text-muted-foreground flex h-full items-center justify-center px-6 text-center text-[12px]">
              <span>
                Ingen aktiv run.
                <br />
                Bygg en sajt först — sedan kan du inspektera den här.
              </span>
            </div>
          ) : (
            <Tabs defaultValue="pages" className="flex h-full flex-col gap-0">
              <TabsList
                variant="line"
                className="border-border/60 w-full justify-start gap-1 border-b px-4 pt-2 pb-2"
              >
                <TabsTrigger value="pages">Sidor</TabsTrigger>
                <TabsTrigger value="brief">Brief &amp; Plan</TabsTrigger>
                <TabsTrigger value="variants">Variants</TabsTrigger>
                <TabsTrigger value="versions">Versioner</TabsTrigger>
                <TabsTrigger value="tokens">Färger</TabsTrigger>
                <TabsTrigger value="dossiers">Dossiers</TabsTrigger>
                <TabsTrigger value="quality">Kvalitet</TabsTrigger>
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
