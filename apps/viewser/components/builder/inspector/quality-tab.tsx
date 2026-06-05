"use client";

import {
  AlertCircle,
  CheckCircle2,
  Hammer,
  ShieldCheck,
  ShieldX,
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
  findings: string[];
};

type RepairFix = {
  name?: string;
  detail?: string;
  success?: boolean;
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
    if (typeof obj.detail === "string") fix.detail = obj.detail;
    if (typeof obj.success === "boolean") fix.success = obj.success;
    out.push(fix);
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

  // repair-result.json: { status, iterations, mechanicalFixesApplied[],
  // remainingErrors[], qualityStatusBefore } (packages/generation/repair).
  const repairStatus = asString(repairResult.status);
  const repairFixes = asRepairFixes(repairResult.mechanicalFixesApplied);
  const remainingErrors = asStringList(repairResult.remainingErrors);
  const repairIterations = asNumber(repairResult.iterations);
  const qualityBefore = asString(repairResult.qualityStatusBefore);
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

      {/* Repair Pipeline */}
      {hasRepair ? (
        <div>
          <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
            <Hammer className="h-3 w-3" aria-hidden />
            Repair Pipeline
            {repairStatus ? ` · ${repairStatus}` : ""}
          </div>
          {repairIterations !== null || qualityBefore ? (
            <p className="text-muted-foreground mb-1.5 text-[10.5px]">
              {repairIterations !== null
                ? `iterationer: ${repairIterations}`
                : ""}
              {qualityBefore ? ` · gate innan: ${qualityBefore}` : ""}
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
                  {fix.detail ? (
                    <p className="text-muted-foreground mt-1 leading-snug">
                      {fix.detail}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
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
