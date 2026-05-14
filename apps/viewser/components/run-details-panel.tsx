"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

type RunDetailsPanelProps = {
  runId: string | null;
};

type ArtefactBundle = {
  runId: string;
  buildResult: Record<string, unknown> | null;
  qualityResult: Record<string, unknown> | null;
  repairResult: Record<string, unknown> | null;
  siteBrief: Record<string, unknown> | null;
  missingArtefacts: string[];
};

const STATUS_COLORS: Record<string, string> = {
  ok: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  passed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  "not-needed": "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  degraded: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  "no-fix-applied": "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  failed: "bg-red-500/15 text-red-700 dark:text-red-300",
  skipped: "bg-muted text-muted-foreground",
  unknown: "bg-muted text-muted-foreground",
  "mock-complete": "bg-sky-500/15 text-sky-700 dark:text-sky-300",
};

function StatusBadge({ status }: { status: string }) {
  const className = STATUS_COLORS[status] ?? "bg-muted text-muted-foreground";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${className}`}>
      {status}
    </span>
  );
}

function MissingNote({ label }: { label: string }) {
  return (
    <p className="text-xs italic text-muted-foreground">{label}</p>
  );
}

function asString(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

type CheckResult = {
  name: string;
  status: string;
  findings?: string[];
};

type RepairFix = {
  name?: string;
  status?: string;
  description?: string;
};

type NpmStep = {
  name?: string;
  ok?: boolean;
  seconds?: number;
  logExcerpt?: string;
};

function BuildSection({ build }: { build: Record<string, unknown> | null }) {
  if (!build) {
    return (
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Build</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <MissingNote label="build-result.json saknas i denna run." />
        </CardContent>
      </Card>
    );
  }

  const status = asString(build.status, "unknown");
  const siteId = asString(build.siteId, "saknas i äldre run");
  const briefSource = asString(build.briefSource, "unknown");
  const generatedFilesDir = asString(build.generatedFilesDir, "saknas i äldre run");
  const devPreviewDir = asString(build.devPreviewDir, "saknas i äldre run");
  const runDurationMs = asNumber(build.runDurationMs, 0);
  const routes = Array.isArray(build.routes) ? (build.routes as string[]) : [];
  const npmSteps = Array.isArray(build.npmSteps) ? (build.npmSteps as NpmStep[]) : [];
  const buildSource = asString(build.buildSource, "unknown");

  return (
    <Card size="sm">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Build</span>
          <StatusBadge status={status} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-3 text-xs">
        <p className="text-muted-foreground">
          Runner: <span className="font-mono">{buildSource}</span>
          {" · "}briefSource: <span className="font-mono">{briefSource}</span>
          {runDurationMs > 0 ? ` · ${(runDurationMs / 1000).toFixed(1)} s` : null}
        </p>
        <p>
          <span className="text-muted-foreground">siteId:</span>{" "}
          <span className="font-mono">{siteId}</span>
        </p>
        <p>
          <span className="text-muted-foreground">generatedFilesDir:</span>{" "}
          <span className="font-mono break-all">{generatedFilesDir}</span>
        </p>
        <p>
          <span className="text-muted-foreground">devPreviewDir:</span>{" "}
          <span className="font-mono break-all">{devPreviewDir}</span>
        </p>
        {routes.length > 0 ? (
          <div>
            <p className="text-muted-foreground">routes:</p>
            <ul className="ml-4 list-disc">
              {routes.map((route) => (
                <li key={route} className="font-mono">
                  {route}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <MissingNote label="routes saknas i äldre run (dev_generate-pipeline)." />
        )}
        {npmSteps.length > 0 ? (
          <div>
            <p className="text-muted-foreground">npmSteps:</p>
            <ul className="ml-4 list-disc">
              {npmSteps.map((step, index) => (
                <li key={`${step.name ?? "step"}-${index}`}>
                  <span className="font-mono">{step.name ?? "?"}</span>
                  {" — "}
                  {step.ok ? "ok" : "failed"}
                  {typeof step.seconds === "number"
                    ? ` (${step.seconds.toFixed(1)} s)`
                    : null}
                  {step.logExcerpt ? (
                    <pre className="mt-1 whitespace-pre-wrap rounded bg-muted p-2 text-[11px] text-muted-foreground">
                      {step.logExcerpt}
                    </pre>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <MissingNote label="npmSteps saknas (dev_generate-pipeline kör inte npm)." />
        )}
      </CardContent>
    </Card>
  );
}

function QualitySection({ quality }: { quality: Record<string, unknown> | null }) {
  if (!quality) {
    return (
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Quality Gate</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <MissingNote label="quality-result.json saknas i denna run (pre-Sprint 3A eller partial run-dir)." />
        </CardContent>
      </Card>
    );
  }

  const status = asString(quality.status, "unknown");
  const checks = Array.isArray(quality.checks) ? (quality.checks as CheckResult[]) : [];

  return (
    <Card size="sm">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Quality Gate</span>
          <StatusBadge status={status} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-3 text-xs">
        {checks.length === 0 ? (
          <MissingNote label="Inga checks rapporterade." />
        ) : (
          <ul className="space-y-2">
            {checks.map((check) => (
              <li key={check.name} className="rounded border border-border/40 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono">{check.name}</span>
                  <StatusBadge status={check.status} />
                </div>
                {check.findings && check.findings.length > 0 ? (
                  <ul className="mt-1 ml-4 list-disc text-muted-foreground">
                    {check.findings.slice(0, 5).map((finding, index) => (
                      <li key={`${check.name}-finding-${index}`}>{finding}</li>
                    ))}
                    {check.findings.length > 5 ? (
                      <li className="italic">
                        ... och {check.findings.length - 5} till
                      </li>
                    ) : null}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function RepairSection({ repair }: { repair: Record<string, unknown> | null }) {
  if (!repair) {
    return (
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Repair Pipeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <MissingNote label="repair-result.json saknas i denna run (pre-Sprint 3A eller partial run-dir)." />
        </CardContent>
      </Card>
    );
  }

  const status = asString(repair.status, "unknown");
  const iterations = asNumber(repair.iterations, 0);
  const mechanicalFixesApplied = Array.isArray(repair.mechanicalFixesApplied)
    ? (repair.mechanicalFixesApplied as RepairFix[])
    : [];
  const remainingErrors = Array.isArray(repair.remainingErrors)
    ? (repair.remainingErrors as string[])
    : [];
  const qualityStatusBefore = typeof repair.qualityStatusBefore === "string"
    ? repair.qualityStatusBefore
    : null;

  return (
    <Card size="sm">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Repair Pipeline</span>
          <StatusBadge status={status} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-3 text-xs">
        <p className="text-muted-foreground">
          iterations: {iterations}
          {qualityStatusBefore
            ? ` · pre-repair Quality Gate: ${qualityStatusBefore}`
            : null}
        </p>
        {mechanicalFixesApplied.length === 0 ? (
          <MissingNote label="Inga mekaniska fixes körda." />
        ) : (
          <div>
            <p className="text-muted-foreground">mechanicalFixesApplied:</p>
            <ul className="ml-4 list-disc">
              {mechanicalFixesApplied.map((fix, index) => (
                <li key={`${fix.name ?? "fix"}-${index}`}>
                  <span className="font-mono">{fix.name ?? "?"}</span>
                  {fix.status ? ` — ${fix.status}` : null}
                  {fix.description ? ` (${fix.description})` : null}
                </li>
              ))}
            </ul>
          </div>
        )}
        {remainingErrors.length > 0 ? (
          <div>
            <p className="text-muted-foreground">remainingErrors:</p>
            <ul className="ml-4 list-disc text-red-600 dark:text-red-400">
              {remainingErrors.slice(0, 5).map((err, index) => (
                <li key={`err-${index}`}>{err}</li>
              ))}
              {remainingErrors.length > 5 ? (
                <li className="italic">
                  ... och {remainingErrors.length - 5} till
                </li>
              ) : null}
            </ul>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function CodegenSection({ build }: { build: Record<string, unknown> | null }) {
  const codegen = build && typeof build.codegen === "object" && build.codegen !== null
    ? (build.codegen as Record<string, unknown>)
    : null;

  if (!codegen) {
    return (
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Codegen</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <MissingNote label="codegen-fältet saknas i denna run (pre-Sprint 3A eller äldre runner)." />
        </CardContent>
      </Card>
    );
  }

  const source = asString(codegen.source, "unknown");
  const modelUsed = asString(codegen.modelUsed, "unknown");
  const fileCount = asNumber(codegen.fileCount, 0);
  const rationale = typeof codegen.rationale === "string" ? codegen.rationale : null;
  const riskNotes = Array.isArray(codegen.riskNotes)
    ? (codegen.riskNotes as string[])
    : [];
  const error = typeof codegen.error === "string" ? codegen.error : null;

  return (
    <Card size="sm">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Codegen</span>
          <StatusBadge status={source} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-3 text-xs">
        <p className="text-muted-foreground">
          modelUsed: <span className="font-mono">{modelUsed}</span> ·{" "}
          fileCount: {fileCount}
        </p>
        {rationale ? (
          <div>
            <p className="text-muted-foreground">rationale:</p>
            <p className="rounded bg-muted/50 p-2 italic">{rationale}</p>
          </div>
        ) : (
          <MissingNote label="rationale saknas (deterministic / mock-pipeline)." />
        )}
        {riskNotes.length > 0 ? (
          <div>
            <p className="text-muted-foreground">riskNotes:</p>
            <ul className="ml-4 list-disc">
              {riskNotes.map((note, index) => (
                <li key={`risk-${index}`}>{note}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {error ? (
          <p className="rounded bg-red-500/10 p-2 text-red-700 dark:text-red-300">
            error: {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

type ByRoleEntry =
  | null
  | {
      promptTokens?: number;
      completionTokens?: number;
      totalTokens?: number;
    };

function ModelsSection({ build }: { build: Record<string, unknown> | null }) {
  const usage = build && typeof build.modelUsage === "object" && build.modelUsage !== null
    ? (build.modelUsage as Record<string, unknown>)
    : null;

  if (!usage) {
    return (
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Models</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <MissingNote label="modelUsage saknas i denna run (pre-3C-lite)." />
        </CardContent>
      </Card>
    );
  }

  const source = asString(usage.source, "unknown");
  const totalIn = asNumber(usage.totalInputTokens, 0);
  const totalOut = asNumber(usage.totalOutputTokens, 0);
  const totalCost = asNumber(usage.totalCostUsd, 0);
  const byRole = (usage.byRole && typeof usage.byRole === "object"
    ? (usage.byRole as Record<string, ByRoleEntry>)
    : {}) as Record<string, ByRoleEntry>;

  const roles: Array<["briefModel" | "planningModel" | "codegenModel", string]> = [
    ["briefModel", "Brief Model"],
    ["planningModel", "Planning Model"],
    ["codegenModel", "Codegen Model"],
  ];

  return (
    <Card size="sm">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          <span>Models</span>
          <StatusBadge status={source} />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-3 text-xs">
        <p className="text-muted-foreground">
          envelope: in {totalIn} / out {totalOut} tokens · ${totalCost.toFixed(4)}
        </p>
        <ul className="space-y-1">
          {roles.map(([key, label]) => {
            const entry = byRole[key];
            if (!entry) {
              return (
                <li key={key} className="flex justify-between">
                  <span className="font-mono">{label}</span>
                  <span className="text-muted-foreground italic">ej spårad än</span>
                </li>
              );
            }
            return (
              <li key={key} className="flex justify-between">
                <span className="font-mono">{label}</span>
                <span>
                  in {asNumber(entry.promptTokens, 0)} / out{" "}
                  {asNumber(entry.completionTokens, 0)} ={" "}
                  {asNumber(entry.totalTokens, 0)} tokens
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

export function RunDetailsPanel({ runId }: RunDetailsPanelProps) {
  const [bundle, setBundle] = useState<ArtefactBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      // All setState calls live inside this async IIFE so the React 19
      // `react-hooks/set-state-in-effect` rule sees them as
      // subscription-style (i.e. they happen after the effect body has
      // returned and React has committed). Synchronous setState calls
      // directly in the effect body would trigger cascading renders.
      if (!runId) {
        if (cancelled) return;
        setBundle(null);
        setError(null);
        setLoading(false);
        return;
      }

      if (cancelled) return;
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/runs/${runId}/artifacts`);
        const payload = (await response.json()) as ArtefactBundle & { error?: string };
        if (!response.ok || payload.error) {
          throw new Error(payload.error ?? "Kunde inte hämta artefakter.");
        }
        if (!cancelled) {
          setBundle(payload);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : "Okänt fel.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (!runId) {
    return (
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Run Details</CardTitle>
        </CardHeader>
        <CardContent className="pt-3 text-sm text-muted-foreground">
          Välj en run i Run History eller starta en ny via Build.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center justify-between gap-2 text-base">
          <span>Run Details</span>
          <span className="font-mono text-xs text-muted-foreground">{runId}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-3">
        {loading ? (
          <p className="text-sm text-muted-foreground">Laddar artefakter...</p>
        ) : null}
        {error ? (
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        ) : null}
        {bundle ? (
          <>
            {bundle.missingArtefacts.length > 0 ? (
              <p className="text-xs italic text-muted-foreground">
                Saknar i denna run: {bundle.missingArtefacts.join(", ")}
              </p>
            ) : null}
            <ScrollArea className="h-[60vh] rounded-md border p-2">
              <div className="space-y-3 pr-2">
                <BuildSection build={bundle.buildResult} />
                <QualitySection quality={bundle.qualityResult} />
                <RepairSection repair={bundle.repairResult} />
                <CodegenSection build={bundle.buildResult} />
                <ModelsSection build={bundle.buildResult} />
              </div>
            </ScrollArea>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
