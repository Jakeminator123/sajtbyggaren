"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

export type RunHistoryItem = {
  runId: string;
  status: string;
  siteId: string;
  projectId?: string;
  version?: number | null;
  createdAt: string;
};

type RunHistoryProps = {
  runs: RunHistoryItem[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  isBuilding?: boolean;
};

const STATUS_DOT_COLORS: Record<string, string> = {
  ok: "bg-emerald-500",
  passed: "bg-emerald-500",
  "mock-complete": "bg-sky-500",
  degraded: "bg-amber-500",
  warning: "bg-amber-500",
  failed: "bg-red-500",
  skipped: "bg-muted-foreground/40",
  unknown: "bg-muted-foreground/40",
};

function shortRun(runId: string): string {
  return runId.length > 28 ? `${runId.slice(0, 28)}...` : runId;
}

function StatusDot({ status }: { status: string }) {
  const className = STATUS_DOT_COLORS[status] ?? "bg-muted-foreground/40";
  return (
    <span
      aria-label={`status: ${status}`}
      className={`inline-block size-2 rounded-full ${className}`}
    />
  );
}

export function RunHistory({
  runs,
  selectedRunId,
  onSelect,
  isBuilding = false,
}: RunHistoryProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Run History</span>
          <span className="text-xs text-muted-foreground">
            {runs.length} {runs.length === 1 ? "run" : "runs"}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {isBuilding ? (
          <div className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
            <span className="inline-block size-2 animate-pulse rounded-full bg-amber-500" />
            Build pågår... ny run dyker upp när scripts/build_site.py är klar.
          </div>
        ) : null}
        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Inga runs än. Klicka Build för att skapa en.
          </p>
        ) : (
          <ScrollArea className="h-44 rounded-md border">
            <ul className="divide-y divide-border/40">
              {runs.map((run) => {
                const selected = run.runId === selectedRunId;
                return (
                  <li key={run.runId}>
                    <button
                      type="button"
                      onClick={() => onSelect(run.runId)}
                      className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs transition-colors ${
                        selected
                          ? "bg-muted text-foreground"
                          : "hover:bg-muted/50"
                      }`}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <StatusDot status={run.status} />
                        <span className="truncate font-mono">
                          {shortRun(run.runId)}
                        </span>
                      </span>
                      <span className="flex shrink-0 flex-col text-right text-muted-foreground">
                        <span>
                          {run.siteId} · {run.status}
                        </span>
                        {run.projectId ? (
                          <span className="font-mono text-[10px]">
                            {shortRun(run.projectId)}
                            {run.version ? ` · v${run.version}` : ""}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
