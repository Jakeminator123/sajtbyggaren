"use client";

import {
  AlertCircle,
  CheckCircle2,
  Hammer,
  ShieldCheck,
  ShieldX,
  Sparkles,
} from "lucide-react";

import { QuickPromptButton } from "@/components/builder/inspector/quick-prompt-button";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";
import { cn } from "@/lib/utils";

/**
 * Kvalitet & Bygg-tab: visar status från build-result.json
 * (status + runDurationMs), quality-result.json (status, summary, checks[])
 * och repair-result.json (status, iterations, mechanicalFixesApplied[],
 * remainingErrors[]).
 *
 * Fälten speglar de canonical pydantic-shaparna i
 * `packages/generation/quality_gate/models.py` (QualityResult.checks[] med
 * name/status/findings/severity) och `packages/generation/repair/models.py`
 * (RepairResult.mechanicalFixesApplied[] / remainingErrors). Vi narrowar
 * shapes lokalt med små helpers istället för att hård-typa hela artefakten —
 * äldre runs som saknar fälten faller naturligt ur defensiv parsing.
 */

type QualityCheck = {
  name?: string;
  status?: string;
  detail?: string;
  severity?: string;
  durationMs?: number | null;
  findings: string[];
};

type RepairFix = {
  name?: string;
  kind?: string;
  target?: string;
  detail?: string;
  success?: boolean;
};

// kor-4a (deterministisk) + kor-4b (verifierModel) copy-kritik. Speglar
// governance/schemas/quality-result.schema.json:critic. VARNING-lane: påverkar
// aldrig top-level gate-status, så vi visar den som egen sektion utan att röra
// gate-badgen.
type CriticIssue = {
  severity?: string;
  type?: string;
  target?: string;
  message?: string;
  repairHint?: string;
};

type CriticResult = {
  score: number | null;
  source: string | null;
  issues: CriticIssue[];
};

// kor-5 blueprint-repair-telemetri. Speglar
// governance/schemas/repair-result.schema.json:$defs.blueprintRepair.
type BlueprintRepair = {
  issueType?: string;
  target?: string;
  field?: string;
  before?: string;
  after?: string;
  success?: boolean;
  detail?: string;
};

function asString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (entry): entry is string => typeof entry === "string" && entry.length > 0,
  );
}

function asChecks(value: unknown): QualityCheck[] {
  if (!Array.isArray(value)) return [];
  const out: QualityCheck[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const check: QualityCheck = { findings: asStringList(obj.findings) };
    if (typeof obj.name === "string") check.name = obj.name;
    if (typeof obj.status === "string") check.status = obj.status;
    if (typeof obj.detail === "string") check.detail = obj.detail;
    if (typeof obj.severity === "string") check.severity = obj.severity;
    check.durationMs = asNumber(obj.durationMs);
    out.push(check);
  }
  return out;
}

function asRepairFixes(value: unknown): RepairFix[] {
  if (!Array.isArray(value)) return [];
  const out: RepairFix[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const fix: RepairFix = {};
    if (typeof obj.name === "string") fix.name = obj.name;
    if (typeof obj.kind === "string") fix.kind = obj.kind;
    if (typeof obj.target === "string") fix.target = obj.target;
    if (typeof obj.detail === "string") fix.detail = obj.detail;
    if (typeof obj.success === "boolean") fix.success = obj.success;
    out.push(fix);
  }
  return out;
}

// quality-result.json:critic — defensiv parse (null när blueprintet inte kördes
// genom critic-lanen, eller på äldre runs som saknar fältet).
function asCritic(value: unknown): CriticResult | null {
  if (!value || typeof value !== "object") return null;
  const obj = value as Record<string, unknown>;
  const issues: CriticIssue[] = [];
  if (Array.isArray(obj.issues)) {
    for (const entry of obj.issues) {
      if (!entry || typeof entry !== "object") continue;
      const e = entry as Record<string, unknown>;
      const issue: CriticIssue = {};
      if (typeof e.severity === "string") issue.severity = e.severity;
      if (typeof e.type === "string") issue.type = e.type;
      if (typeof e.target === "string") issue.target = e.target;
      if (typeof e.message === "string") issue.message = e.message;
      if (typeof e.repairHint === "string") issue.repairHint = e.repairHint;
      issues.push(issue);
    }
  }
  return { score: asNumber(obj.score), source: asString(obj.source), issues };
}

function asBlueprintRepairs(value: unknown): BlueprintRepair[] {
  if (!Array.isArray(value)) return [];
  const out: BlueprintRepair[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const repair: BlueprintRepair = {};
    if (typeof obj.issueType === "string") repair.issueType = obj.issueType;
    if (typeof obj.target === "string") repair.target = obj.target;
    if (typeof obj.field === "string") repair.field = obj.field;
    if (typeof obj.before === "string") repair.before = obj.before;
    if (typeof obj.after === "string") repair.after = obj.after;
    if (typeof obj.detail === "string") repair.detail = obj.detail;
    if (typeof obj.success === "boolean") repair.success = obj.success;
    out.push(repair);
  }
  return out;
}

function statusBadge(status: string | null): {
  label: string;
  classes: string;
  Icon: typeof CheckCircle2;
} {
  if (
    status === "ok" ||
    status === "mock-complete" ||
    status === "skipped" ||
    status === "not-needed" ||
    status === "fixed"
  ) {
    return {
      label: status,
      classes:
        "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-400/40",
      Icon: CheckCircle2,
    };
  }
  if (
    status === "degraded" ||
    status === "partial-fix" ||
    status === "no-fix-applied"
  ) {
    return {
      label: status,
      classes:
        "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-400/40",
      Icon: AlertCircle,
    };
  }
  if (status === "failed") {
    return {
      label: status,
      classes: "bg-destructive/10 text-destructive border-destructive/40",
      Icon: ShieldX,
    };
  }
  return {
    label: status ?? "unknown",
    classes: "bg-muted/40 text-muted-foreground border-border/40",
    Icon: ShieldCheck,
  };
}

function checkTone(check: QualityCheck): string {
  if (check.status === "failed") {
    return check.severity === "warning"
      ? "text-amber-700 dark:text-amber-400 border-amber-400/30 bg-amber-50/40 dark:bg-amber-950/10"
      : "text-destructive border-destructive/40 bg-destructive/5";
  }
  return "text-muted-foreground border-border/40 bg-card/40";
}

// Critic-fynd är alltid VARNING (aldrig blockerande) men severity styr
// score-straffet (high=20/medium=10/low=5) → spegla i tonen utan att låna
// gate-failed-rött för low/medium.
function criticTone(severity: string | undefined): string {
  if (severity === "high") {
    return "text-destructive border-destructive/40 bg-destructive/5";
  }
  if (severity === "medium") {
    return "text-amber-700 dark:text-amber-400 border-amber-400/30 bg-amber-50/40 dark:bg-amber-950/10";
  }
  return "text-muted-foreground border-border/40 bg-card/40";
}

type QualityTabProps = {
  bundle: RunArtefactBundle;
  isBuilding: boolean;
  pendingPrompt: string | null;
  onPrompt: (prompt: string) => void;
};

export function QualityTab({
  bundle,
  isBuilding,
  pendingPrompt,
  onPrompt,
}: QualityTabProps) {
  const buildResult = bundle.buildResult ?? {};
  const qualityResult = bundle.qualityResult ?? {};
  const repairResult = bundle.repairResult ?? {};

  const buildStatus = asString(buildResult.status);
  const buildDuration = asNumber(buildResult.runDurationMs);
  const buildBadge = statusBadge(buildStatus);
  const BuildIcon = buildBadge.Icon;

  // quality-result.json: canonical shape är { status, summary, checks[] }
  // (packages/generation/quality_gate/models.py). Varje check har name,
  // status (ok/failed/skipped), severity (blocking/warning) och findings[].
  const gateStatus = asString(qualityResult.status);
  const gateSummary = asString(qualityResult.summary);
  const checks = asChecks(qualityResult.checks);
  const failedChecks = checks.filter((check) => check.status === "failed");
  // kor-4a/4b copy-kritik (warning-lane; null när blueprintet inte kördes
  // genom critic). Egen sektion — rör aldrig gate-status/badge.
  const critic = asCritic(qualityResult.critic);

  // repair-result.json: { status, reason, iterations, mechanicalFixesApplied[],
  // llmFixesApplied[], remainingErrors[], qualityStatusBefore/After,
  // blueprintRepairs[] } (packages/generation/repair).
  const repairStatus = asString(repairResult.status);
  const repairReason = asString(repairResult.reason);
  const repairFixes = asRepairFixes(repairResult.mechanicalFixesApplied);
  const llmFixes = asRepairFixes(repairResult.llmFixesApplied);
  const blueprintRepairs = asBlueprintRepairs(repairResult.blueprintRepairs);
  const remainingErrors = asStringList(repairResult.remainingErrors);
  const repairIterations = asNumber(repairResult.iterations);
  const qualityBefore = asString(repairResult.qualityStatusBefore);
  const qualityAfter = asString(repairResult.qualityStatusAfter);
  const hasRepair = bundle.repairResult !== null;

  return (
    <div className="flex flex-col gap-5">
      {/* Build status */}
      <div>
        <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
          <Hammer className="h-3 w-3" aria-hidden />
          Senaste bygge
        </div>
        <div
          className={cn(
            "flex items-center gap-2 rounded-md border px-2.5 py-2 text-[12px]",
            buildBadge.classes,
          )}
        >
          <BuildIcon className="h-4 w-4 shrink-0" aria-hidden />
          <span className="font-mono text-[11.5px]">{buildBadge.label}</span>
          {buildDuration !== null ? (
            <span className="text-muted-foreground ml-auto text-[10.5px]">
              {(buildDuration / 1000).toFixed(1)}s
            </span>
          ) : null}
        </div>
      </div>

      {/* Quality Gate */}
      <div>
        <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
          <ShieldCheck className="h-3 w-3" aria-hidden />
          Quality Gate
          {gateStatus ? ` · ${gateStatus}` : ""}
          {checks.length > 0
            ? ` (${failedChecks.length}/${checks.length})`
            : ""}
        </div>
        {gateSummary ? (
          <p className="text-muted-foreground mb-1.5 text-[11px] leading-snug">
            {gateSummary}
          </p>
        ) : null}
        {bundle.qualityResult === null ? (
          <p className="text-muted-foreground text-[11.5px] italic">
            quality-result.json saknas i denna run.
          </p>
        ) : checks.length === 0 ? (
          <p className="text-muted-foreground text-[11.5px] italic">
            Inga checks rapporterade i denna run.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {checks.map((check, idx) => {
              const failed = check.status === "failed";
              const fixContext =
                check.detail ||
                (check.findings.length > 0
                  ? check.findings.join("; ")
                  : "se findings");
              const fixPrompt = `Fixa Quality Gate-check "${check.name ?? "okänd"}"${
                check.severity ? ` (${check.severity})` : ""
              }: ${fixContext}`;
              return (
                <li
                  key={`${check.name ?? "check"}-${idx}`}
                  className={cn(
                    "rounded-md border p-2 text-[11.5px]",
                    checkTone(check),
                  )}
                >
                  <div className="mb-0.5 flex items-baseline justify-between gap-2">
                    <span className="font-mono text-[10.5px]">
                      {check.name ?? "—"} · {check.status ?? "okänd"}
                      {check.severity ? ` · ${check.severity}` : ""}
                      {check.durationMs != null ? ` · ${check.durationMs}ms` : ""}
                    </span>
                    {failed ? (
                      <QuickPromptButton
                        label="Be om fix"
                        prompt={fixPrompt}
                        isBuilding={isBuilding}
                        isPending={pendingPrompt === fixPrompt}
                        onSelect={onPrompt}
                      />
                    ) : null}
                  </div>
                  {check.detail ? (
                    <p className="leading-snug">{check.detail}</p>
                  ) : null}
                  {check.findings.length > 0 ? (
                    <ul className="mt-1 ml-3.5 list-disc space-y-0.5">
                      {check.findings.slice(0, 5).map((finding, fIdx) => (
                        <li
                          key={`${check.name ?? "check"}-finding-${fIdx}`}
                          className="leading-snug break-words"
                        >
                          {finding}
                        </li>
                      ))}
                      {check.findings.length > 5 ? (
                        <li className="text-muted-foreground italic">
                          … och {check.findings.length - 5} till
                        </li>
                      ) : null}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Copy-kritik (kor-4a deterministisk + kor-4b verifierModel). VARNING-
          lane: påverkar aldrig gate-status. Visas bara när blueprintet kördes
          genom critic (annars null). */}
      {critic ? (
        <div>
          <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
            <Sparkles className="h-3 w-3" aria-hidden />
            Copy-kritik
            {critic.score !== null ? ` · ${critic.score}/100` : ""}
            {critic.source ? ` · ${critic.source}` : ""}
          </div>
          {critic.issues.length === 0 ? (
            <p className="text-muted-foreground text-[11.5px] italic">
              Inga copy-fynd — blueprintet passerade critic-heuristikerna.
            </p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {critic.issues.map((issue, idx) => {
                const fixContext =
                  issue.repairHint || issue.message || "förbättra copyn";
                const fixPrompt = `Förbättra ${
                  issue.target ?? "sektionen"
                } (${issue.type ?? "copy"}): ${fixContext}`;
                return (
                  <li
                    key={`critic-${issue.target ?? "issue"}-${idx}`}
                    className={cn(
                      "rounded-md border p-2 text-[11.5px]",
                      criticTone(issue.severity),
                    )}
                  >
                    <div className="mb-0.5 flex items-baseline justify-between gap-2">
                      <span className="font-mono text-[10.5px]">
                        {issue.severity ?? "—"} · {issue.type ?? "copy"}
                        {issue.target ? ` · ${issue.target}` : ""}
                      </span>
                      <QuickPromptButton
                        label="Be om fix"
                        prompt={fixPrompt}
                        isBuilding={isBuilding}
                        isPending={pendingPrompt === fixPrompt}
                        onSelect={onPrompt}
                      />
                    </div>
                    {issue.message ? (
                      <p className="leading-snug">{issue.message}</p>
                    ) : null}
                    {issue.repairHint ? (
                      <p className="text-muted-foreground mt-1 leading-snug">
                        Förslag: {issue.repairHint}
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}

      {/* Repair Pipeline */}
      {hasRepair ? (
        <div>
          <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
            <Hammer className="h-3 w-3" aria-hidden />
            Repair Pipeline
            {repairStatus ? ` · ${repairStatus}` : ""}
          </div>
          {repairIterations !== null || qualityBefore || qualityAfter ? (
            <p className="text-muted-foreground mb-1.5 text-[10.5px]">
              {repairIterations !== null
                ? `iterationer: ${repairIterations}`
                : ""}
              {qualityBefore ? ` · gate innan: ${qualityBefore}` : ""}
              {qualityAfter ? ` → efter: ${qualityAfter}` : ""}
            </p>
          ) : null}
          {repairReason ? (
            <p className="text-muted-foreground mb-1.5 text-[11px] leading-snug">
              {repairReason}
            </p>
          ) : null}
          {repairFixes.length === 0 ? (
            <p className="text-muted-foreground text-[11.5px] italic">
              Inga mekaniska fixes körda.
            </p>
          ) : (
            <ul className="flex flex-col gap-1">
              {repairFixes.map((fix, idx) => (
                <li
                  key={`${fix.name ?? "fix"}-${idx}`}
                  className="border-border/40 bg-card/40 rounded-md border p-2 text-[11.5px]"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <code className="text-foreground bg-muted/40 rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                      {fix.name ?? "—"}
                    </code>
                    {fix.success !== undefined ? (
                      <span
                        className={cn(
                          "font-mono text-[10.5px]",
                          fix.success
                            ? "text-emerald-700 dark:text-emerald-400"
                            : "text-destructive",
                        )}
                      >
                        {fix.success ? "fixad" : "misslyckades"}
                      </span>
                    ) : null}
                  </div>
                  {fix.target ? (
                    <p className="text-muted-foreground mt-1 font-mono text-[10px] break-all">
                      {fix.target}
                    </p>
                  ) : null}
                  {fix.detail ? (
                    <p className="text-muted-foreground mt-1 leading-snug">
                      {fix.detail}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {blueprintRepairs.length > 0 ? (
            <div className="mt-1.5">
              <p className="text-muted-foreground text-[10.5px]">
                Blueprint-repair (kor-5):
              </p>
              <ul className="mt-0.5 flex flex-col gap-1">
                {blueprintRepairs.map((repair, idx) => (
                  <li
                    key={`blueprint-${repair.field ?? repair.target ?? "patch"}-${idx}`}
                    className="border-border/40 bg-card/40 rounded-md border p-2 text-[11px]"
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <code className="text-foreground bg-muted/40 rounded px-1.5 py-0.5 font-mono text-[10.5px] break-all">
                        {repair.field ?? repair.target ?? "—"}
                      </code>
                      {repair.success !== undefined ? (
                        <span
                          className={cn(
                            "shrink-0 font-mono text-[10.5px]",
                            repair.success
                              ? "text-emerald-700 dark:text-emerald-400"
                              : "text-muted-foreground",
                          )}
                        >
                          {repair.success ? "patchad" : "avvisad"}
                        </span>
                      ) : null}
                    </div>
                    {repair.issueType || repair.detail ? (
                      <p className="text-muted-foreground mt-1 leading-snug">
                        {repair.issueType ?? ""}
                        {repair.issueType && repair.detail ? " — " : ""}
                        {repair.detail ?? ""}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {llmFixes.length > 0 ? (
            <div className="mt-1.5">
              <p className="text-muted-foreground text-[10.5px]">LLM-fixes:</p>
              <ul className="mt-0.5 flex flex-col gap-1">
                {llmFixes.map((fix, idx) => (
                  <li
                    key={`llm-fix-${fix.name ?? "fix"}-${idx}`}
                    className="border-border/40 bg-card/40 rounded-md border p-2 text-[11px]"
                  >
                    <code className="text-foreground bg-muted/40 rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                      {fix.name ?? "—"}
                    </code>
                    {fix.detail ? (
                      <p className="text-muted-foreground mt-1 leading-snug">
                        {fix.detail}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {remainingErrors.length > 0 ? (
            <div className="mt-1.5">
              <p className="text-muted-foreground text-[10.5px]">
                Kvarstående fel:
              </p>
              <ul className="text-destructive mt-0.5 ml-3.5 list-disc space-y-0.5 text-[11px]">
                {remainingErrors.slice(0, 5).map((err, idx) => (
                  <li
                    key={`remaining-${idx}`}
                    className="leading-snug break-words"
                  >
                    {err}
                  </li>
                ))}
                {remainingErrors.length > 5 ? (
                  <li className="text-muted-foreground italic">
                    … och {remainingErrors.length - 5} till
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {bundle.missingArtefacts.length > 0 ? (
        <p className="text-muted-foreground border-border/40 bg-muted/30 rounded-md border p-2 text-[10.5px]">
          Saknade artefakter i denna run: {bundle.missingArtefacts.join(", ")}
        </p>
      ) : null}
    </div>
  );
}
