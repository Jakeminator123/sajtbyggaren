"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type RunHistoryItem = {
  runId: string;
  status: string;
  siteId: string;
  createdAt: string;
};

type RunHistoryProps = {
  runs: RunHistoryItem[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
};

function shortRun(runId: string): string {
  return runId.length > 26 ? `${runId.slice(0, 26)}...` : runId;
}

export function RunHistory({ runs, selectedRunId, onSelect }: RunHistoryProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Run History</CardTitle>
      </CardHeader>
      <CardContent>
        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">Inga runs än.</p>
        ) : (
          <select
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            value={selectedRunId ?? ""}
            onChange={(event) => onSelect(event.target.value)}
          >
            {runs.slice(0, 5).map((run) => (
              <option key={run.runId} value={run.runId}>
                {shortRun(run.runId)} | {run.siteId} | {run.status}
              </option>
            ))}
          </select>
        )}
      </CardContent>
    </Card>
  );
}
