"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  hostedRunNoticeFromResponse,
  knownHostedRunNotice,
} from "@/lib/hosted-run-artefacts";

type RunDetailsPanelProps = {
  runId: string | null;
};

type ArtefactBundle = {
  runId: string;
  buildResult: Record<string, unknown> | null;
  qualityResult: Record<string, unknown> | null;
  repairResult: Record<string, unknown> | null;
  siteBrief: Record<string, unknown> | null;
  sitePlan: Record<string, unknown> | null;
  missingArtefacts: string[];
};

const STATUS_TONE: Record<
  string,
  "ok" | "warn" | "fail" | "info" | "neutral"
> = {
  ok: "ok",
  passed: "ok",
  "not-needed": "ok",
  degraded: "warn",
  warning: "warn",
  "no-fix-applied": "warn",
  failed: "fail",
  // `aborted` = bygget dödades innan build-result.json skrevs (lib/runs.ts
  // stale-pending). Ärligt ett misslyckat bygge → röd `fail`-ton, inte neutral.
  aborted: "fail",
  skipped: "neutral",
  unknown: "neutral",
  "mock-complete": "info",
};

function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? "neutral";
  const toneClass =
    tone === "ok"
      ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30"
      : tone === "warn"
        ? "bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/30"
        : tone === "fail"
          ? "bg-destructive/15 text-destructive border-destructive/30"
          : tone === "info"
            ? "bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30"
            : "bg-muted text-muted-foreground border-border";
  return (
    <Badge variant="outline" className={`font-mono text-[10px] ${toneClass}`}>
      {status}
    </Badge>
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
  kind?: string;
  target?: string;
  detail?: string;
  success?: boolean;
};

type NpmStep = {
  name?: string;
  ok?: boolean;
  seconds?: number;
  logExcerpt?: string;
};

type RoutePlanEntry = {
  id?: string;
  path?: string;
  purpose?: string;
};

// B144 (2026-05-21): defensive parsing of site-plan.json warning fields.
// pageCountWarning + intentGuardWarnings + pageIntentWarnings are written
// by produce_site_plan() and scripts/build_site.py:_intent_guard_warnings
// (Builder-sprint 2026-05-21, sköldpaddssoppa case). Older runs (pre-
// B138 / pre-Intent-Guard-light) lack the fields entirely; the parsers
// return null/[] so SitePlanSection skips the amber block rather than
// crashing on missing/malformed data. Inline return-type literals keep
// these helpers from registering new canonical type names while still
// giving the renderer narrow shapes to read from.
function parsePageCountWarning(value: unknown): {
  requestedPageCount: number | null;
  scaffoldDefaultCount: number | null;
  emittedRouteCount: number | null;
  reason: string;
} | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const obj = value as Record<string, unknown>;
  const reason = typeof obj.reason === "string" ? obj.reason : null;
  if (!reason) {
    return null;
  }
  return {
    requestedPageCount:
      typeof obj.requestedPageCount === "number" ? obj.requestedPageCount : null,
    scaffoldDefaultCount:
      typeof obj.scaffoldDefaultCount === "number" ? obj.scaffoldDefaultCount : null,
    emittedRouteCount:
      typeof obj.emittedRouteCount === "number" ? obj.emittedRouteCount : null,
    reason,
  };
}

function parseIntentGuardWarnings(value: unknown): Array<{
  categoryId: string;
  conflictingTerm: string;
  reason: string;
  businessTypeGuess: string | null;
}> {
  if (!Array.isArray(value)) {
    return [];
  }
  const out: Array<{
    categoryId: string;
    conflictingTerm: string;
    reason: string;
    businessTypeGuess: string | null;
  }> = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const obj = item as Record<string, unknown>;
    const categoryId = typeof obj.categoryId === "string" ? obj.categoryId : null;
    const conflictingTerm =
      typeof obj.conflictingTerm === "string" ? obj.conflictingTerm : null;
    const reason = typeof obj.reason === "string" ? obj.reason : null;
    if (!categoryId || !conflictingTerm || !reason) continue;
    const businessTypeGuess =
      typeof obj.businessTypeGuess === "string" && obj.businessTypeGuess.length > 0
        ? obj.businessTypeGuess
        : null;
    out.push({ categoryId, conflictingTerm, reason, businessTypeGuess });
  }
  return out;
}

function parsePageIntentWarnings(value: unknown): Array<{
  page: string;
  expectedPath: string;
  reason: string;
}> {
  if (!Array.isArray(value)) {
    return [];
  }
  const out: Array<{ page: string; expectedPath: string; reason: string }> = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const obj = item as Record<string, unknown>;
    const page = typeof obj.page === "string" ? obj.page : null;
    const expectedPath =
      typeof obj.expectedPath === "string" ? obj.expectedPath : null;
    const reason = typeof obj.reason === "string" ? obj.reason : null;
    if (!page || !expectedPath || !reason) continue;
    out.push({ page, expectedPath, reason });
  }
  return out;
}

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
  // B133 (2026-05-19): scripts/build_site.py writes placeholderContactFields
  // only when scripts/prompt_to_project_input.py's _placeholder_contact
  // filled at least one contact slot with a B88 dummy value
  // (e.g. "+46 8 000 00 00", "kontakt@example.se", "Adress lämnas på
  // förfrågan") and neither wizard nor scrape overwrote it. As of
  // B158/B159 (2026-06-01, 2e0c55f) the published site no longer renders
  // those dummy values — it suppresses them and shows an honest generic
  // contact CTA ("Hör av dig") instead. The warning therefore tells the
  // operator that real contact info is still MISSING (so the site lacks a
  // direct phone/email), not that dummies are being shown to visitors.
  const placeholderContactFields = Array.isArray(build.placeholderContactFields)
    ? (build.placeholderContactFields as string[]).filter(
        (field) => typeof field === "string" && field.length > 0,
      )
    : [];

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
        {placeholderContactFields.length > 0 ? (
          <div
            data-testid="placeholder-contact-warning"
            className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-2 text-amber-900 dark:text-amber-200"
          >
            <p className="font-medium">
              {`\u26A0 Kontakt-fält är platshållare: ${placeholderContactFields.join(", ")}.`}
            </p>
            <p className="mt-1 text-[11px] text-amber-900/80 dark:text-amber-200/80">
              Sajten döljer fälten publikt och visar en allmän kontaktknapp —
              fyll i riktiga uppgifter så får besökarna en direkt kontaktväg.
            </p>
          </div>
        ) : null}
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

function SitePlanSection({ sitePlan }: { sitePlan: Record<string, unknown> | null }) {
  if (!sitePlan) {
    return (
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle className="text-sm">Site Plan</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-3">
          <MissingNote label="site-plan.json saknas i denna run." />
        </CardContent>
      </Card>
    );
  }

  const scaffoldId = asString(sitePlan.scaffoldId, "unknown");
  const variantId = asString(sitePlan.variantId, "unknown");
  const starterId = asString(sitePlan.starterId, "unknown");
  const routePlan = Array.isArray(sitePlan.routePlan)
    ? (sitePlan.routePlan as RoutePlanEntry[])
    : [];

  // B144 (2026-05-21): site-plan.json är canonical källa för
  // pageCountWarning (B138 — brief.pageCount trim) + intentGuardWarnings
  // (Intent Guard light — wizard categoryId vs brief businessTypeGuess /
  // servicesMentioned) + pageIntentWarnings (B132 — wizard mustHave
  // saknar scaffold-route). Builder skrev fälten i sprinten 2026-05-21
  // men Run Details renderade dem inte; operatören saknade synlig signal
  // efter Reviewer 2026-05-21 (~7/10) — verifierat live mot sköldpaddssoppa
  // där intentGuardWarnings flaggade categoryId='fitness' vs
  // conflictingTerm='mat'. Mirror placeholderContactFields-amber-blocket
  // i BuildSection. Äldre runs som saknar fälten faller naturligt ur
  // defensive parsing och visar inte blocket.
  const pageCountWarning = parsePageCountWarning(sitePlan.pageCountWarning);
  const intentGuardWarnings = parseIntentGuardWarnings(sitePlan.intentGuardWarnings);
  const pageIntentWarnings = parsePageIntentWarnings(sitePlan.pageIntentWarnings);
  const hasSitePlanWarnings =
    pageCountWarning !== null ||
    intentGuardWarnings.length > 0 ||
    pageIntentWarnings.length > 0;

  return (
    <Card size="sm">
      <CardHeader className="border-b">
        <CardTitle className="text-sm">Site Plan</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-3 text-xs">
        <p className="text-muted-foreground">
          scaffold: <span className="font-mono">{scaffoldId}</span>
          {" · "}variant: <span className="font-mono">{variantId}</span>
          {" · "}starter: <span className="font-mono">{starterId}</span>
        </p>
        {hasSitePlanWarnings ? (
          <div
            data-testid="site-plan-warnings"
            className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-2 text-amber-900 dark:text-amber-200"
          >
            <p className="font-medium">{"\u26A0 Site Plan-varningar"}</p>
            <ul className="mt-1 ml-4 list-disc space-y-1 text-[11px] text-amber-900/80 dark:text-amber-200/80">
              {pageCountWarning ? (
                <li>
                  <span className="font-mono">page-count:</span>{" "}
                  {`prompt bad om ${
                    pageCountWarning.requestedPageCount ?? "?"
                  } sidor, scaffold-default ${
                    pageCountWarning.scaffoldDefaultCount ?? "?"
                  }, route plan emitterar ${
                    pageCountWarning.emittedRouteCount ?? "?"
                  } (${pageCountWarning.reason}).`}
                </li>
              ) : null}
              {intentGuardWarnings.map((warning, index) => (
                <li key={`intent-guard-${index}`}>
                  <span className="font-mono">intent-guard:</span>{" "}
                  {`kategori ${warning.categoryId} krockar med termen ${warning.conflictingTerm}`}
                  {warning.businessTypeGuess
                    ? ` (briefens businessTypeGuess: ${warning.businessTypeGuess})`
                    : ""}
                  {` — ${warning.reason}.`}
                </li>
              ))}
              {pageIntentWarnings.map((warning, index) => (
                <li key={`page-intent-${index}`}>
                  <span className="font-mono">page-intent:</span>{" "}
                  {`wizard-sidan ${warning.page} förväntade route ${warning.expectedPath} — ${warning.reason}.`}
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-amber-900/80 dark:text-amber-200/80">
              Build blockas inte; planner och Intent Guard signalerar att
              site-plan.json fångade en konflikt eller trim.
            </p>
          </div>
        ) : null}
        {routePlan.length > 0 ? (
          <div>
            <p className="text-muted-foreground">routePlan:</p>
            <ul className="ml-4 list-disc">
              {routePlan.map((route, index) => (
                <li key={`${route.path ?? "route"}-${index}`}>
                  <span className="font-mono">{route.path ?? "?"}</span>
                  {route.id ? ` — ${route.id}` : null}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <MissingNote label="routePlan saknas i denna run." />
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
                  {typeof fix.success === "boolean"
                    ? ` — ${fix.success ? "fixad" : "misslyckades"}`
                    : null}
                  {fix.target ? ` · ${fix.target}` : null}
                  {fix.detail ? ` (${fix.detail})` : null}
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
  // Hostad vy: artefakt-endpointen är en medveten 404 + hostedNotice
  // (artefakter ligger på lokal disk). Eget state så vi visar en lugn
  // notis i stället för den röda fel-rutan.
  const [hostedNotice, setHostedNotice] = useState<string | null>(null);
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
        setHostedNotice(null);
        setLoading(false);
        return;
      }

      if (cancelled) return;
      setError(null);
      setHostedNotice(null);

      // Känt hostat läge: skippa anropet helt (tystar browserns 404-rad
      // i konsolen) och visa notisen direkt.
      const known = knownHostedRunNotice();
      if (known) {
        setBundle(null);
        setHostedNotice(known);
        setLoading(false);
        return;
      }
      // Stale-artefakt-skydd: nollställ bundle omedelbart före ny fetch så
      // panelen aldrig visar förra runens kort under laddning.
      setBundle(null);
      setLoading(true);

      try {
        const response = await fetch(`/api/runs/${runId}/artifacts`);
        const payload = (await response.json()) as ArtefactBundle & { error?: string };
        // Svarsformsbaserad hosted-detektering (om latchen inte var armad):
        // lugn notis, aldrig error-state.
        const fromResponse = hostedRunNoticeFromResponse(
          response.status,
          payload,
        );
        if (fromResponse) {
          if (!cancelled) {
            setHostedNotice(fromResponse);
          }
          return;
        }
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
        <CardHeader className="border-b border-border/60 pb-3">
          <CardTitle className="text-base">Run Details</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
            Välj en run i Run History eller starta en ny via prompt-fältet ovan.
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border/60 pb-3">
        <CardTitle className="text-base">Run Details</CardTitle>
        <Badge variant="outline" className="font-mono text-[10px]">
          {runId.length > 26 ? `${runId.slice(0, 26)}…` : runId}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        {loading ? (
          <div
            role="status"
            aria-live="polite"
            aria-busy="true"
            className="flex flex-col gap-2"
          >
            <span className="sr-only">Laddar artefakter…</span>
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-3 w-2/3" />
            <Skeleton className="h-20 w-full rounded-md" />
            <Skeleton className="h-20 w-full rounded-md" />
          </div>
        ) : null}
        {hostedNotice ? (
          // Medveten hostad degradering — lugn info-ruta, inte fel-röd.
          <p
            role="status"
            className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
          >
            {hostedNotice}
          </p>
        ) : null}
        {error ? (
          <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        {bundle ? (
          <>
            {bundle.missingArtefacts.length > 0 ? (
              <p className="text-xs italic text-muted-foreground">
                Saknar i denna run: {bundle.missingArtefacts.join(", ")}
              </p>
            ) : null}
            <ScrollArea className="h-[58vh] rounded-lg border border-border/60 bg-background/40 p-2">
              <div className="space-y-3 pr-2">
                <BuildSection build={bundle.buildResult} />
                <SitePlanSection sitePlan={bundle.sitePlan} />
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
