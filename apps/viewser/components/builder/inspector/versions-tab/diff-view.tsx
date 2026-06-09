"use client";

import { ArrowRight, GitCompare } from "lucide-react";

import {
  formatDiffSummary,
  type RunDiff,
} from "@/components/builder/inspector/run-diff";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Diff-renderaren för VersionsTab. Extraherad ur ``versions-tab.tsx``
// (1438 rader → ~1010) som ren textextraktion — inga beteendeändringar.
// Alla helpers (ScalarChangeRow, ValueChip, ChipDiffRow, ChangeChip,
// CompareEmptyHint) följer med eftersom de bara används härinifrån.
//
// EmptyState bor här också, eftersom VersionsTab importerar den för
// run-list-tom-state och CompareEmptyHint är diff-rummets motsvarighet.
//
// Pure components — inga hooks, inga side-effects. Säker extraktion.

export function DiffView({ diff }: { diff: RunDiff }) {
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

export function CompareEmptyHint({
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

// Kort, ärligt fel när VersionsTab:s lazy runtime-``import()`` av
// jämförelsemodalen failar (nät-glapp/utgången deploy). Bor här (inte inline i
// versions-tab) så huvudfilen hålls under sin radgräns; samma alert-stil som
// VersionsTab:s ``loadError``.
export function ComparePreviewLoadError({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
    >
      {message}
    </p>
  );
}

export function VersionsEmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
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
