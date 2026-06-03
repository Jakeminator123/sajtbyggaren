"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

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
  /**
   * Initial /api/runs-laddning pågår. Visar en skeleton i st.f. tom-CTA:n
   * ("Inga runs än") så operatören inte ser ett falskt "tomt"-tillstånd
   * innan datan hunnit landa.
   */
  loading?: boolean;
};

function RunHistorySkeleton() {
  return (
    <div
      className="divide-border/40 overflow-hidden rounded-md border border-border/60 bg-background/40"
      aria-hidden
    >
      {[0, 1, 2].map((row) => (
        <div
          key={row}
          className="flex flex-col gap-1.5 border-b border-border/40 px-3 py-2 last:border-b-0"
        >
          <div className="flex items-center gap-2">
            <Skeleton className="size-2 rounded-full" />
            <Skeleton className="h-3 w-40" />
          </div>
          <Skeleton className="ml-4 h-2.5 w-28" />
        </div>
      ))}
    </div>
  );
}

// STATUS_DOT_COLORS locks the per-status color mapping for the Run
// History list. The exact constant name is asserted by
// tests/test_viewser_files.py::test_run_history_uses_status_dot_colors
// to prevent regressing to a plain text-only select.
const STATUS_DOT_COLORS: Record<string, string> = {
  ok: "bg-emerald-500",
  passed: "bg-emerald-500",
  "mock-complete": "bg-sky-500",
  degraded: "bg-amber-500",
  warning: "bg-amber-500",
  failed: "bg-destructive",
  // `aborted` = bygget dödades innan build-result.json skrevs (lib/runs.ts
  // stale-pending-detektion). Röd som `failed` — det är ärligt ett misslyckat
  // bygge, inte ett pågående. Skiljer sig från grå `pending` (faktiskt pågår).
  aborted: "bg-destructive",
  skipped: "bg-muted-foreground/40",
  unknown: "bg-muted-foreground/40",
};

function shortRun(runId: string): string {
  return runId.length > 22 ? `${runId.slice(0, 22)}…` : runId;
}

function StatusDot({ status }: { status: string }) {
  const dot = STATUS_DOT_COLORS[status] ?? "bg-muted-foreground/40";
  return (
    <span
      aria-label={`status: ${status}`}
      className={`inline-block size-2 rounded-full ${dot}`}
    />
  );
}

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

export function RunHistory({
  runs,
  selectedRunId,
  onSelect,
  isBuilding = false,
  loading = false,
}: RunHistoryProps) {
  return (
    <Card size="sm" className="hover-lift">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Run History</span>
          <span className="font-mono text-[11px] text-muted-foreground">
            {runs.length}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-1">
        {isBuilding ? (
          <div className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-800 dark:text-amber-300">
            <span className="inline-block size-2 animate-pulse rounded-full bg-amber-500" />
            Build pågår — ny run dyker upp när build_site.py är klar.
          </div>
        ) : null}

        {loading && runs.length === 0 ? (
          <RunHistorySkeleton />
        ) : runs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground">
            Inga runs än. Skicka en prompt i hero-fältet för att skapa en.
          </div>
        ) : (
          <ScrollArea className="h-[min(26rem,50dvh)] rounded-md border border-border/60 bg-background/40">
            <ul className="divide-y divide-border/40">
              {runs.map((run) => {
                const selected = run.runId === selectedRunId;
                return (
                  <li key={run.runId}>
                    <button
                      type="button"
                      onClick={() => onSelect(run.runId)}
                      aria-pressed={selected}
                      className={`flex w-full flex-col gap-1 px-3 py-2 text-left text-xs transition-colors ${
                        selected
                          ? "bg-muted text-foreground"
                          : "hover:bg-muted/50"
                      }`}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <StatusDot status={run.status} />
                        <span className="truncate font-mono text-[11px]">
                          {shortRun(run.runId)}
                        </span>
                      </span>
                      <span className="flex items-center justify-between gap-2 pl-4 text-[10px] text-muted-foreground">
                        <span className="truncate">
                          {run.siteId} · {run.status}
                          {run.version ? ` · v${run.version}` : ""}
                        </span>
                        <span className="shrink-0">{formatRelative(run.createdAt)}</span>
                      </span>
                      {run.projectId ? (
                        <span className="block truncate pl-4 font-mono text-[10px] text-muted-foreground/80">
                          {shortRun(run.projectId)}
                        </span>
                      ) : null}
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
