"use client";

import { CheckCircle2, MinusCircle, XCircle, Zap } from "lucide-react";

import { QuickPromptButton } from "@/components/builder/inspector/quick-prompt-button";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";
import { cn } from "@/lib/utils";

/**
 * Dossiers-tab: visar selectedDossiers från sitePlan (vilka
 * capability-paket som faktiskt valdes, vilka som rekommenderats
 * villkorligt, och vilka som avvisades med skäl). Rejected-listan
 * är värdefull för operatören — den visar precis vad scaffolden
 * inte kan leverera, och varför.
 *
 * Per rejected-entry får operatören en snabbprompt som ber
 * engine:n att försöka inkludera capability:n ändå.
 */

type DossierEntry = {
  id: string;
  reason?: string;
};

function asDossierList(value: unknown): DossierEntry[] {
  if (!Array.isArray(value)) return [];
  const out: DossierEntry[] = [];
  for (const entry of value) {
    // Can be either a plain string id or `{ id, reason }`.
    if (typeof entry === "string") {
      out.push({ id: entry });
      continue;
    }
    if (entry && typeof entry === "object") {
      const obj = entry as Record<string, unknown>;
      const id = typeof obj.id === "string" ? obj.id : null;
      if (!id) continue;
      const dossier: DossierEntry = { id };
      if (typeof obj.reason === "string") dossier.reason = obj.reason;
      out.push(dossier);
    }
  }
  return out;
}

function asRationale(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

type DossiersTabProps = {
  bundle: RunArtefactBundle;
  isBuilding: boolean;
  pendingPrompt: string | null;
  onPrompt: (prompt: string) => void;
};

function DossierGroup({
  icon: Icon,
  label,
  entries,
  emptyText,
  colorClass,
}: {
  icon: typeof CheckCircle2;
  label: string;
  entries: DossierEntry[];
  emptyText: string;
  colorClass: string;
}) {
  return (
    <div>
      <div
        className={cn(
          "mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase",
          colorClass,
        )}
      >
        <Icon className="h-3 w-3" aria-hidden />
        {label} ({entries.length})
      </div>
      {entries.length === 0 ? (
        <p className="text-muted-foreground text-[11.5px] italic">
          {emptyText}
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="border-border/50 bg-card/40 rounded-md border p-2"
            >
              <code className="text-foreground bg-muted/40 inline-block rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                {entry.id}
              </code>
              {entry.reason ? (
                <p className="text-muted-foreground mt-1 text-[11px] leading-snug">
                  {entry.reason}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function DossiersTab({
  bundle,
  isBuilding,
  pendingPrompt,
  onPrompt,
}: DossiersTabProps) {
  const sitePlan = bundle.sitePlan ?? {};
  const selected = (sitePlan.selectedDossiers ?? {}) as Record<string, unknown>;

  const required = asDossierList(selected.required);
  const recommended = asDossierList(selected.recommended);
  const conditional = asDossierList(selected.conditional);
  const rejected = asDossierList(selected.rejected);
  const rationale = asRationale(selected.rationale);

  // Hjälpare: bygg en retry-prompt för en rejected entry. Per-entry
  // för att vi vill mata in capability-id:t exakt så briefModel:s
  // tolkning av "försök inkludera X" blir entydig.
  const buildRetryPrompt = (entry: DossierEntry) =>
    `Försök inkludera capability "${entry.id}" på sajten. ${entry.reason ? `Tidigare avvisades den: "${entry.reason}". ` : ""}Hitta en alternativ lösning om den exakta capabilityn inte finns registrerad.`;

  return (
    <div className="flex flex-col gap-5">
      {rationale ? (
        <p className="text-muted-foreground bg-muted/30 border-border/40 rounded-md border p-2 text-[11.5px] leading-relaxed italic">
          {rationale}
        </p>
      ) : null}

      <DossierGroup
        icon={CheckCircle2}
        label="Required"
        entries={required}
        emptyText="Inga required dossiers i denna run."
        colorClass="text-emerald-700 dark:text-emerald-500"
      />

      <DossierGroup
        icon={Zap}
        label="Recommended"
        entries={recommended}
        emptyText="Inga recommended dossiers."
        colorClass="text-sky-700 dark:text-sky-500"
      />

      <DossierGroup
        icon={MinusCircle}
        label="Conditional"
        entries={conditional}
        emptyText="Inga conditional dossiers."
        colorClass="text-muted-foreground"
      />

      <div>
        <div className="text-destructive mb-1.5 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
          <XCircle className="h-3 w-3" aria-hidden />
          Rejected ({rejected.length})
        </div>
        {rejected.length === 0 ? (
          <p className="text-muted-foreground text-[11.5px] italic">
            Inga avvisade dossiers.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {rejected.map((entry) => {
              const retryPrompt = buildRetryPrompt(entry);
              return (
                <li
                  key={entry.id}
                  className="border-destructive/30 bg-destructive/5 rounded-md border p-2"
                >
                  <div className="mb-1 flex items-baseline justify-between gap-2">
                    <code className="text-foreground bg-muted/40 rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                      {entry.id}
                    </code>
                    <QuickPromptButton
                      label="Försök ändå"
                      prompt={retryPrompt}
                      isBuilding={isBuilding}
                      isPending={pendingPrompt === retryPrompt}
                      onSelect={onPrompt}
                    />
                  </div>
                  {entry.reason ? (
                    <p className="text-muted-foreground text-[11px] leading-snug">
                      {entry.reason}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
