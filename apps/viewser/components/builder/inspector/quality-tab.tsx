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
 * Kvalitet & Bygg-tab: visar status från build-result.json (status,
 * duration, exit code), quality-result.json (findings per gate), och
 * repair-result.json (om/hur Repair Pipeline försökte fixa något).
 * Vi narrowar shapes lokalt med små helpers istället för att hård-
 * typa hela artefakten — formatet är fortfarande pre-1.0 i builder
 * MVP:n och vi vill inte bryta inspectorn varje gång engine byter
 * fält-namn.
 */

type QualityFinding = {
  gate?: string;
  severity?: string;
  message?: string;
  file?: string;
};

type RepairAction = {
  id?: string;
  status?: string;
  description?: string;
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

function asFindings(value: unknown): QualityFinding[] {
  if (!Array.isArray(value)) return [];
  const out: QualityFinding[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const finding: QualityFinding = {};
    if (typeof obj.gate === "string") finding.gate = obj.gate;
    if (typeof obj.severity === "string") finding.severity = obj.severity;
    if (typeof obj.message === "string") finding.message = obj.message;
    if (typeof obj.file === "string") finding.file = obj.file;
    out.push(finding);
  }
  return out;
}

function asRepairActions(value: unknown): RepairAction[] {
  if (!Array.isArray(value)) return [];
  const out: RepairAction[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const action: RepairAction = {};
    if (typeof obj.id === "string") action.id = obj.id;
    if (typeof obj.status === "string") action.status = obj.status;
    if (typeof obj.description === "string")
      action.description = obj.description;
    out.push(action);
  }
  return out;
}

function statusBadge(status: string | null): {
  label: string;
  classes: string;
  Icon: typeof CheckCircle2;
} {
  if (status === "ok" || status === "mock-complete" || status === "skipped") {
    return {
      label: status,
      classes:
        "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-400/40",
      Icon: CheckCircle2,
    };
  }
  if (status === "degraded") {
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

function severityClasses(severity: string | undefined): string {
  if (severity === "error" || severity === "blocking") {
    return "text-destructive border-destructive/40 bg-destructive/5";
  }
  if (severity === "warning" || severity === "warn") {
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
  const buildDuration = asNumber(buildResult.durationMs);
  const exitCode = asNumber(buildResult.exitCode);
  const buildBadge = statusBadge(buildStatus);
  const BuildIcon = buildBadge.Icon;

  // Quality artefakten har inget perfekt schema än. Acceptera både
  // `findings` (flat) och `gates: [{ findings: [] }]` (grouped).
  const flatFindings = asFindings(qualityResult.findings);
  const groupedFindings: QualityFinding[] = [];
  if (Array.isArray(qualityResult.gates)) {
    for (const gate of qualityResult.gates as unknown[]) {
      if (!gate || typeof gate !== "object") continue;
      const obj = gate as Record<string, unknown>;
      const sub = asFindings(obj.findings);
      const gateLabel = typeof obj.id === "string" ? obj.id : undefined;
      for (const f of sub) {
        groupedFindings.push({ ...f, gate: f.gate ?? gateLabel });
      }
    }
  }
  const findings = [...flatFindings, ...groupedFindings];

  const repairActions = asRepairActions(repairResult.actions);
  const repairStatus = asString(repairResult.status);

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
          {exitCode !== null ? (
            <span className="text-muted-foreground text-[10.5px]">
              exit {exitCode}
            </span>
          ) : null}
        </div>
      </div>

      {/* Quality findings */}
      <div>
        <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
          <ShieldCheck className="h-3 w-3" aria-hidden />
          Quality Gate ({findings.length})
        </div>
        {findings.length === 0 ? (
          <p className="text-muted-foreground text-[11.5px] italic">
            Inga findings — Quality Gate gick rent.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {findings.map((finding, idx) => {
              const fixPrompt = `Fixa Quality Gate-finding i ${finding.file ?? "okänd fil"} (gate: ${finding.gate ?? "—"}): ${finding.message ?? "—"}`;
              return (
                <li
                  key={`${finding.gate ?? "gate"}-${idx}`}
                  className={cn(
                    "rounded-md border p-2 text-[11.5px]",
                    severityClasses(finding.severity),
                  )}
                >
                  <div className="mb-0.5 flex items-baseline justify-between gap-2">
                    <span className="font-mono text-[10.5px]">
                      {finding.gate ?? "—"} · {finding.severity ?? "info"}
                    </span>
                    <QuickPromptButton
                      label="Be om fix"
                      prompt={fixPrompt}
                      isBuilding={isBuilding}
                      isPending={pendingPrompt === fixPrompt}
                      onSelect={onPrompt}
                    />
                  </div>
                  {finding.message ? (
                    <p className="leading-snug">{finding.message}</p>
                  ) : null}
                  {finding.file ? (
                    <code className="text-muted-foreground mt-0.5 inline-block font-mono text-[10px]">
                      {finding.file}
                    </code>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Repair actions */}
      {repairActions.length > 0 || repairStatus ? (
        <div>
          <div className="text-muted-foreground mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
            <Hammer className="h-3 w-3" aria-hidden />
            Repair Pipeline
            {repairStatus ? ` · ${repairStatus}` : ""}
          </div>
          {repairActions.length === 0 ? (
            <p className="text-muted-foreground text-[11.5px] italic">
              Repair Pipeline har inga actions att rapportera.
            </p>
          ) : (
            <ul className="flex flex-col gap-1">
              {repairActions.map((action, idx) => (
                <li
                  key={`${action.id ?? "action"}-${idx}`}
                  className="border-border/40 bg-card/40 rounded-md border p-2 text-[11.5px]"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <code className="text-foreground bg-muted/40 rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                      {action.id ?? "—"}
                    </code>
                    {action.status ? (
                      <span className="text-muted-foreground font-mono text-[10.5px]">
                        {action.status}
                      </span>
                    ) : null}
                  </div>
                  {action.description ? (
                    <p className="text-muted-foreground mt-1 leading-snug">
                      {action.description}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
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
