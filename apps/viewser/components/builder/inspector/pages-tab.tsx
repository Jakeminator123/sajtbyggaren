"use client";

import { AlertTriangle, ChevronDown, FileText, FileWarning, Layers } from "lucide-react";
import { useState } from "react";

import { QuickPromptButton } from "@/components/builder/inspector/quick-prompt-button";
import type { RunArtefactBundle } from "@/components/builder/inspector/use-run-artefacts";
import { cn } from "@/lib/utils";

/**
 * Sidor-tab: visar routePlan från sitePlan och pageIntentWarnings
 * (sidor wizarden bad om men scaffolden inte emittade). Varje sida
 * får tre snabbprompts: skriv om innehållet, lägg till sektion, ta
 * bort sidan. Varje pageIntentWarning får en knapp som ber engine:n
 * att försöka inkludera sidan ändå.
 *
 * Spår D — per-sektion-edit för home-routen:
 * Home-routen får en expanderbar "Sektioner"-grupp där operatören kan
 * rikta in sig på en specifik sektion (hero, story, gallery, FAQ etc)
 * istället för att skriva om hela sidan. Sektionerna matchar vad
 * ``render_home`` i build_site.py producerar: hero, services-grid,
 * story, gallery, testimonials, FAQ, contact-CTA. Listan är statisk —
 * vi har ingen runtime-introspektion av exakt vilka sektioner som
 * faktiskt renderades, men eftersom render_home alltid emitterar
 * hero + services + CTA och de andra är opt-in baserat på dossier-
 * innehåll, är det rimligt att alltid visa hela menyn (operatören
 * får bara ett build-fel om de ber om att redigera en sektion som
 * inte finns, vilket pipelinen hanterar med "sektion saknas, ska den
 * läggas till?"-flöde).
 */

/**
 * Per-sektion-prompts för home-routens "Sektioner"-grupp. Varje
 * sektion får två snabbval: "Anpassa innehåll" (textuell ändring som
 * brief-modellen kan hantera) och "Ändra design" (visuell ändring
 * som triggar variant/typography/layout-direktiv).
 *
 * Sektionsnamnen matchar vad render_home producerar (line 1615+ i
 * scripts/build_site.py). När backend i framtiden exponerar en
 * faktisk sektion-introspektion via sitePlan kan denna lista bytas
 * mot data, men för v1 räcker statisk lista eftersom alla home-
 * sektioner är deterministiska.
 */
const HOME_SECTIONS: ReadonlyArray<{
  id: string;
  label: string;
  contentPrompt: string;
  designPrompt: string;
}> = [
  {
    id: "hero",
    label: "Hero",
    contentPrompt:
      'Skriv om hero-sektionen på startsidan. Behåll företagets namn men gör rubriken mer säljande och tagline:n mer specifik.',
    designPrompt:
      'Ändra hero-sektionens design: prova en annan layout (centered/split/gradient) eller en mer dramatisk färg.',
  },
  {
    id: "services",
    label: "Tjänster / Sortiment",
    contentPrompt:
      'Skriv om tjänsteblocken på startsidan så texterna blir mer specifika och konkreta — varje tjänst ska säga exakt vad kunden får.',
    designPrompt:
      'Ändra designen på tjänsteblocken: lägg in ikoner som passar branschen bättre, eller byt grid-uppställning.',
  },
  {
    id: "story",
    label: "Historia",
    contentPrompt:
      'Skriv om "Vår historia"-sektionen på startsidan så berättelsen känns mer personlig och förankrad i företagets verklighet.',
    designPrompt:
      'Ändra hur "Vår historia"-sektionen presenteras visuellt — mer luftig typografi eller en mer dramatisk bakgrund.',
  },
  {
    id: "gallery",
    label: "Galleri",
    contentPrompt:
      'Lägg till galleri-sektionen på startsidan med kuraterade exempel — om inga bilder finns uppladdade, använd branschmatchande Unsplash-bilder.',
    designPrompt:
      'Ändra galleri-sektionens layout: prova ett större format, en karusell, eller fler kolumner.',
  },
  {
    id: "testimonials",
    label: "Recensioner",
    contentPrompt:
      'Skriv om recensions-sektionen på startsidan så citaten känns mer specifika och trovärdiga.',
    designPrompt:
      'Ändra recensions-sektionens design — prova en mer minimalistisk stil, eller större typografi.',
  },
  {
    id: "faq",
    label: "Vanliga frågor",
    contentPrompt:
      'Skriv om FAQ-sektionen på startsidan med frågor som faktiskt är relevanta för vår bransch och våra kunder.',
    designPrompt:
      'Ändra FAQ-sektionens layout — prova en accordeon-stil, eller en mer kompakt grid.',
  },
  {
    id: "cta",
    label: "Slutlig CTA",
    contentPrompt:
      'Skriv om CTA-sektionen längst ner på startsidan så texten är mer specifik för vår bransch och kund.',
    designPrompt:
      'Ändra CTA-sektionens design — prova en mer dramatisk bakgrund, eller en mindre central knapp.',
  },
];

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
  // Vilka route-id:n som har sin "Sektioner"-grupp expanderad.
  // Default-set:en är tom så listan är kompakt vid första öppning;
  // operatören kan klicka home-routen för att se per-sektion-knapparna.
  // För närvarande stödjer vi bara sektion-edit för home-routen
  // eftersom övriga routes (services, about, contact, faq) är enklare
  // och rewrite-prompten räcker. Lägg till fler i HOME_SECTIONS för
  // framtida utbyggnad.
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const toggleSections = (routeId: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(routeId)) next.delete(routeId);
      else next.add(routeId);
      return next;
    });
  };

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
                    {/* Spår D — sektion-toggle endast för home-routen.
                        Andra routes har en enklare sektionsstruktur så
                        de allmänna prompt-knapparna räcker. Toggle:n
                        ligger sist så de tre vanliga knapparna ovan
                        behåller sin position; det är en utveckling, inte
                        en omdesign. */}
                    {route.id === "home" ? (
                      <button
                        type="button"
                        onClick={() => toggleSections(route.id)}
                        aria-expanded={expandedSections.has(route.id)}
                        aria-controls={`pages-tab-sections-${route.id}`}
                        className={cn(
                          "text-muted-foreground hover:text-foreground hover:bg-muted/40",
                          "focus-visible:ring-ring/50 focus-visible:ring-2 focus-visible:outline-none",
                          "inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11.5px] font-medium tracking-tight transition-colors",
                        )}
                        title="Visa per-sektion-edits"
                      >
                        <Layers className="h-3 w-3" aria-hidden />
                        Sektioner
                        <ChevronDown
                          className={cn(
                            "h-3 w-3 transition-transform duration-150",
                            expandedSections.has(route.id) && "rotate-180",
                          )}
                          aria-hidden
                        />
                      </button>
                    ) : null}
                  </div>
                  {/* Per-sektion-edit-panel. Visas bara när home-routen
                      är expanderad. Varje sektion får två kompakta knappar
                      (innehåll + design) som båda går genom samma
                      `onPrompt`-pipeline som de större knapparna ovan. */}
                  {route.id === "home" && expandedSections.has(route.id) ? (
                    <div
                      id={`pages-tab-sections-${route.id}`}
                      className="border-border/40 mt-3 flex flex-col gap-2 border-t pt-3"
                    >
                      <p className="text-muted-foreground mb-0.5 text-[10.5px] font-medium tracking-[0.16em] uppercase">
                        Redigera en sektion
                      </p>
                      {HOME_SECTIONS.map((section) => (
                        <div
                          key={section.id}
                          className="flex flex-col gap-1.5"
                        >
                          <div className="text-foreground/80 text-[11.5px] font-medium">
                            {section.label}
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            <QuickPromptButton
                              label="Anpassa innehåll"
                              prompt={section.contentPrompt}
                              isBuilding={isBuilding}
                              isPending={pendingPrompt === section.contentPrompt}
                              onSelect={onPrompt}
                            />
                            <QuickPromptButton
                              label="Ändra design"
                              prompt={section.designPrompt}
                              isBuilding={isBuilding}
                              isPending={pendingPrompt === section.designPrompt}
                              onSelect={onPrompt}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
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
