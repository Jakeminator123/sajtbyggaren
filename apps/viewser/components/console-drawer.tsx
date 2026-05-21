"use client";

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
  statusText,
}: ConsoleDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex h-full w-full flex-col gap-0 overflow-hidden p-0 sm:max-w-md"
      >
        <SheetHeader className="border-b border-border/60 px-5 py-4">
          <SheetTitle>Konsol</SheetTitle>
          <SheetDescription className="font-mono text-[11px] text-muted-foreground">
            {statusText}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-4">
            <RunHistory
              runs={runs}
              selectedRunId={selectedRunId}
              onSelect={(runId) => {
                onSelectRunId(runId);
                onOpenChange(false);
              }}
              isBuilding={isBuilding}
            />

            <ProjectInputPicker
              inputs={projectInputs}
              selectedSiteId={selectedSiteId}
              onSelect={onSelectSiteId}
              runSiteId={runSiteId}
              runSiteIdUnknown={runSiteIdUnknown}
            />

            <RunDetailsPanel runId={selectedRunId} />

            <TokenMeter />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
