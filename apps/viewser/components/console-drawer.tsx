"use client";

import { ProjectCompositionPanel } from "@/components/builder/project-composition-panel";
import {
  ProjectInputPicker,
  type ProjectInputOption,
} from "@/components/project-input-picker";
import { RunDetailsPanel } from "@/components/run-details-panel";
import { RunHistory, type RunHistoryItem } from "@/components/run-history";
import { TokenMeter } from "@/components/token-meter";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

type ConsoleDrawerProps = {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  runs: RunHistoryItem[];
  projectInputs: ProjectInputOption[];
  selectedSiteId: string;
  onSelectSiteId: (next: string) => void;
  selectedRunId: string | null;
  onSelectRunId: (next: string) => void;
  /**
   * siteId från den run operatören valt (eller null om ingen run är
   * vald). Skickas vidare till ProjectInputPicker så den kan visa
   * "Följer vald run" och varna när runens siteId saknar Project Input
   * på disk.
   */
  runSiteId: string | null;
  runSiteIdUnknown?: boolean;
  isBuilding: boolean;
  /** Initial /api/runs-laddning pågår — RunHistory visar skeleton. */
  runsLoading?: boolean;
  statusText: string;
};

export function ConsoleDrawer({
  open,
  onOpenChange,
  runs,
  projectInputs,
  selectedSiteId,
  onSelectSiteId,
  selectedRunId,
  onSelectRunId,
  runSiteId,
  runSiteIdUnknown = false,
  isBuilding,
  runsLoading = false,
  statusText,
}: ConsoleDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex h-full w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-md"
      >
        <SheetHeader className="border-border/60 pt-safe border-b px-5 py-4">
          <div className="flex items-center justify-between gap-2">
            <SheetTitle>Konsol</SheetTitle>
            <kbd
              aria-hidden
              className="border-border/60 bg-muted/40 text-muted-foreground rounded-md border px-1.5 py-0.5 font-mono text-[10px] tracking-tight"
              title="Tryck Cmd+K (eller Ctrl+K på Windows) för att öppna/stänga konsolen"
            >
              ⌘K
            </kbd>
          </div>
          <SheetDescription className="text-muted-foreground font-mono text-[11px]">
            {statusText}
          </SheetDescription>
        </SheetHeader>

        <div className="pb-safe-or-4 flex-1 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-4">
            <RunHistory
              runs={runs}
              selectedRunId={selectedRunId}
              onSelect={(runId) => {
                onSelectRunId(runId);
                // Stäng bara lådan på små skärmar där run-historik och Run
                // Details inte ryms samtidigt. På sm+ håller vi den öppen så
                // operatören ser detaljerna för den valda runen i samma
                // gest istället för att behöva öppna Konsolen igen.
                if (
                  typeof window !== "undefined" &&
                  window.matchMedia("(max-width: 639px)").matches
                ) {
                  onOpenChange(false);
                }
              }}
              isBuilding={isBuilding}
              loading={runsLoading}
            />

            <ProjectInputPicker
              inputs={projectInputs}
              selectedSiteId={selectedSiteId}
              onSelect={onSelectSiteId}
              runSiteId={runSiteId}
              runSiteIdUnknown={runSiteIdUnknown}
            />

            {/* Projektinnehåll: vad sajten består av (sidor, dossiers,
                komponenter, paket). Följer vald run-sajt, annars pickern. */}
            <ProjectCompositionPanel siteId={runSiteId ?? selectedSiteId} />

            <RunDetailsPanel runId={selectedRunId} />

            <TokenMeter />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
