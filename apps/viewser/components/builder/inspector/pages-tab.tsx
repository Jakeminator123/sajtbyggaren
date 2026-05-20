"use client";

import { AlertTriangle, FileText, FileWarning } from "lucide-react";

import { QuickPromptButton } from "@/components/builder/inspector/quick-prompt-button";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";
import { cn } from "@/lib/utils";

/**
 * Sidor-tab: visar routePlan från sitePlan och pageIntentWarnings
 * (sidor wizarden bad om men scaffolden inte emittade). Varje sida
 * får tre snabbprompts: skriv om innehållet, lägg till sektion, ta
 * bort sidan. Varje pageIntentWarning får en knapp som ber engine:n
 * att försöka inkludera sidan ändå.
 */

type RoutePlanItem = {
  id: string;
  path: string;
  purpose?: string;
};

type PageIntentWarning = {
  page?: string;
  expectedPath?: string;
  reason?: string;
};

function asRoutePlan(
  sitePlan: Record<string, unknown> | null,
): RoutePlanItem[] {
  if (!sitePlan) return [];
  const raw = sitePlan.routePlan;
  if (!Array.isArray(raw)) return [];
  const out: RoutePlanItem[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const id = typeof obj.id === "string" ? obj.id : null;
    const path = typeof obj.path === "string" ? obj.path : null;
    if (!id || !path) continue;
    const item: RoutePlanItem = { id, path };
    if (typeof obj.purpose === "string") item.purpose = obj.purpose;
    out.push(item);
  }
  return out;
}

function asPageWarnings(
  sitePlan: Record<string, unknown> | null,
): PageIntentWarning[] {
  if (!sitePlan) return [];
  const raw = sitePlan.pageIntentWarnings;
  if (!Array.isArray(raw)) return [];
  const out: PageIntentWarning[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    const warning: PageIntentWarning = {};
    if (typeof obj.page === "string") warning.page = obj.page;
    if (typeof obj.expectedPath === "string")
      warning.expectedPath = obj.expectedPath;
    if (typeof obj.reason === "string") warning.reason = obj.reason;
    out.push(warning);
  }
  return out;
}

type PagesTabProps = {
  bundle: RunArtefactBundle;
  isBuilding: boolean;
  pendingPrompt: string | null;
  onPrompt: (prompt: string) => void;
};

export function PagesTab({
  bundle,
  isBuilding,
  pendingPrompt,
  onPrompt,
}: PagesTabProps) {
  const routes = asRoutePlan(bundle.sitePlan);
  const warnings = asPageWarnings(bundle.sitePlan);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="text-muted-foreground mb-2 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase">
          <FileText className="h-3 w-3" aria-hidden />
          Sidor i sajten ({routes.length})
        </div>
        {routes.length === 0 ? (
          <p className="text-muted-foreground text-[12px] italic">
            Ingen routePlan registrerad i denna run.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {routes.map((route) => {
              const removePrompt = `Ta bort sidan "${route.id}" (${route.path}) från sajten.`;
              const rewritePrompt = `Skriv om allt innehåll på sidan "${route.id}" (${route.path}). Behåll syftet "${route.purpose ?? ""}" men gör texten mer specifik och engagerande.`;
              const addSectionPrompt = `Lägg till en ny sektion på sidan "${route.id}" (${route.path}). Föreslå själv vad sektionen ska vara baserat på sidans syfte.`;
              return (
                <li
                  key={route.id}
                  className="border-border/50 bg-card/40 rounded-lg border p-3"
                >
                  <div className="mb-1.5 flex items-baseline justify-between gap-2">
                    <span className="text-foreground text-[13px] font-medium tracking-tight">
                      {route.id}
                    </span>
                    <code className="text-muted-foreground bg-muted/50 rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                      {route.path}
                    </code>
                  </div>
                  {route.purpose ? (
                    <p className="text-muted-foreground mb-2 text-[11.5px] leading-snug">
                      {route.purpose}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-1.5">
                    <QuickPromptButton
                      label="Skriv om"
                      prompt={rewritePrompt}
                      isBuilding={isBuilding}
                      isPending={pendingPrompt === rewritePrompt}
                      onSelect={onPrompt}
                    />
                    <QuickPromptButton
                      label="+ Sektion"
                      prompt={addSectionPrompt}
                      isBuilding={isBuilding}
                      isPending={pendingPrompt === addSectionPrompt}
                      onSelect={onPrompt}
                    />
                    <QuickPromptButton
                      label="Ta bort"
                      prompt={removePrompt}
                      isBuilding={isBuilding}
                      isPending={pendingPrompt === removePrompt}
                      onSelect={onPrompt}
                      className="text-destructive hover:text-destructive"
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {warnings.length > 0 ? (
        <div>
          <div
            className={cn(
              "mb-2 flex items-center gap-1.5 text-[10.5px] tracking-[0.16em] uppercase",
              "text-amber-700 dark:text-amber-500",
            )}
          >
            <AlertTriangle className="h-3 w-3" aria-hidden />
            Önskade sidor som saknas ({warnings.length})
          </div>
          <ul className="flex flex-col gap-2">
            {warnings.map((warning, idx) => {
              const includePrompt = warning.page
                ? `Försök inkludera sidan "${warning.page}" (önskad path: ${warning.expectedPath ?? "—"}). Anpassa innehållet till scaffolden om det behövs.`
                : "Försök inkludera den saknade sidan.";
              return (
                <li
                  key={`${warning.page ?? "page"}-${idx}`}
                  className="rounded-lg border border-amber-300/50 bg-amber-50/50 p-3 dark:border-amber-700/40 dark:bg-amber-950/20"
                >
                  <div className="mb-1 flex items-start gap-1.5">
                    <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-500" />
                    <div className="flex-1">
                      <div className="text-foreground text-[12.5px] font-medium tracking-tight">
                        {warning.page ?? "Saknad sida"}
                      </div>
                      {warning.expectedPath ? (
                        <code className="text-muted-foreground bg-muted/50 mt-0.5 inline-block rounded px-1.5 py-0.5 font-mono text-[10.5px]">
                          {warning.expectedPath}
                        </code>
                      ) : null}
                    </div>
                  </div>
                  {warning.reason ? (
                    <p className="text-muted-foreground mb-2 ml-5 text-[11px] leading-snug">
                      {warning.reason}
                    </p>
                  ) : null}
                  <div className="ml-5">
                    <QuickPromptButton
                      label="Försök ändå"
                      prompt={includePrompt}
                      isBuilding={isBuilding}
                      isPending={pendingPrompt === includePrompt}
                      onSelect={onPrompt}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <div className="border-border/50 rounded-lg border border-dashed p-3">
        <QuickPromptButton
          label="Lägg till ny sida"
          prompt="Lägg till en ny sida i sajten. Du bestämmer själv namn, path och innehåll baserat på företagets bransch."
          isBuilding={isBuilding}
          isPending={
            pendingPrompt ===
            "Lägg till en ny sida i sajten. Du bestämmer själv namn, path och innehåll baserat på företagets bransch."
          }
          onSelect={onPrompt}
        />
      </div>
    </div>
  );
}
