"use client";

import {
  Blocks,
  Clock,
  HelpCircle,
  Images,
  Loader2,
  Mail,
  MapPin,
  ShieldCheck,
  Star,
  Tag,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useState } from "react";

import {
  useFollowupBuild,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Lägg till modul — drag-and-drop-yta för att be backend lägga in en
 * ny sektion på en specifik sida. Operatören drar (eller klickar) ett
 * modulkort till en sid-zon och väljer position; vi komponerar en
 * strukturerad svensk följdprompt och skickar den via samma
 * `useFollowupBuild`-seam som färg/variant/bild-dialogerna.
 *
 * MEDVETET INGEN frontend-magi: vi muterar inte previewen direkt
 * (previewen är en cross-origin iframe vi inte kan nå DOM:en i).
 * Vi skickar en strukturerad instruktion genom /api/prompt och låter
 * OpenClaw-apply-bryggan utföra den.
 *
 * Synlighets-ärlighet (ADR 0038, synlig section_add skiva 1): tre
 * utfall beroende på modultyp, märkta per kort via `effect`:
 *   - "inline"     → kan renderas som block på startsidan (öppettider;
 *                    gated på grundat innehåll i backend).
 *   - "route"      → blir en egen sida (/faq, /team) på LSB-scaffolden.
 *   - "registered" → monteras men syns inte i previewen än.
 * Positionsvalen är begränsade till de två routern faktiskt parsar
 * ("överst" → top = direkt efter hero, "längst ner" → bottom = före
 * kontakt-CTA:n). Det gamla "Efter hero"-valet saknade parsbart
 * nyckelord och föll tyst till default — borttaget som falsk
 * affordance. Kontraktshistorik i docs/agent-inbox.jsonl
 * (topics: module-dragdrop-prep, wizard-page-suggestions).
 */

type ModuleEffect = "inline" | "route" | "registered";

type ModuleDef = {
  id: string;
  label: string;
  description: string;
  Icon: LucideIcon;
  /** Vad operatören ärligt kan förvänta sig att se efter bygget. */
  effect: ModuleEffect;
};

// Modul-paletten. Etiketterna är operatörsvänlig svenska; id:t är den
// stabila nyckel UI:t och backend-kontraktet delar. Endast moduler som
// backend faktiskt kan montera via section_add listas här: varje rad har en
// sektionstyp i routerns _SECTION_TYPES + en implementerande dossier i
// SECTION_TYPE_CAPABILITY (packages/generation/followup/section_directives.py).
// Tidigare fanns även hero/services/cta-banner i listan, men de är INTE
// section_add-mål (hero/services är sidsektioner, cta-banner saknar dossier),
// så de gav en falsk affordance (Vercel-agent-fynd 2026-06-08) och är borttagna.
const MODULE_CATALOG: ReadonlyArray<ModuleDef> = [
  { id: "gallery", label: "Galleri", description: "Bildrutnät", Icon: Images, effect: "registered" },
  { id: "contact-form", label: "Kontaktformulär", description: "Namn, e-post, meddelande", Icon: Mail, effect: "registered" },
  { id: "faq", label: "Vanliga frågor", description: "Hopfällbara frågor och svar", Icon: HelpCircle, effect: "route" },
  { id: "testimonials", label: "Omdömen", description: "Kundcitat", Icon: Star, effect: "registered" },
  { id: "pricing", label: "Priser", description: "Pris-/paketlista", Icon: Tag, effect: "registered" },
  { id: "map", label: "Karta", description: "Plats med adress", Icon: MapPin, effect: "registered" },
  { id: "opening-hours", label: "Öppettider", description: "Veckoschema", Icon: Clock, effect: "inline" },
  { id: "team", label: "Team", description: "Personalkort", Icon: Users, effect: "route" },
  { id: "trust-badges", label: "Förtroende", description: "Certifikat och logotyper", Icon: ShieldCheck, effect: "registered" },
];

/** Operatörsvänlig, ärlig etikett per synlighets-utfall. */
const EFFECT_BADGES: Record<ModuleEffect, { label: string; title: string }> = {
  inline: {
    label: "syns på startsidan",
    title:
      "Renderas som ett block på startsidan — förutsatt att sajten har riktigt innehåll för sektionen (inga påhittade uppgifter).",
  },
  route: {
    label: "egen sida",
    title: "Läggs till som en egen sida med länk i menyn (t.ex. /faq).",
  },
  registered: {
    label: "syns inte än",
    title:
      "Monteras och registreras i sajtens data men renderas inte i previewen än. Bygget rapporterar ärligt vad som landade.",
  },
};

// Sid-mål. Speglar de vanligaste rutterna i en genererad företagssajt.
const PAGE_TARGETS: ReadonlyArray<{ id: string; label: string }> = [
  { id: "home", label: "Startsida" },
  { id: "about", label: "Om oss" },
  { id: "services", label: "Tjänster" },
  { id: "contact", label: "Kontakt" },
];

// Positions-slot inom en sida. `clause` blir en del av följdprompten och
// MÅSTE innehålla ett nyckelord routern parsar (_POSITION_PHRASES i
// packages/generation/orchestration/router/classify.py): "överst" → top
// (= direkt efter hero), "längst ner" → bottom (= före kontakt-CTA:n).
// Endast dessa två honoreras av render-seamen (ADR 0038 skiva 1) — fler
// val här vore falsk affordance.
const POSITIONS: ReadonlyArray<{ id: string; label: string; clause: string }> = [
  { id: "top", label: "Överst (efter hero)", clause: "överst på sidan" },
  { id: "bottom", label: "Längst ner", clause: "längst ner på sidan" },
];

type Placement = {
  // Lokalt unikt id så samma modul kan placeras flera gånger.
  key: string;
  moduleId: string;
  pageId: string;
  positionId: string;
};

const DRAG_MIME = "application/x-sajtbyggaren-module";

function moduleLabel(moduleId: string): string {
  return MODULE_CATALOG.find((m) => m.id === moduleId)?.label ?? moduleId;
}

function pageLabel(pageId: string): string {
  return PAGE_TARGETS.find((p) => p.id === pageId)?.label ?? pageId;
}

function positionClause(positionId: string): string {
  return POSITIONS.find((p) => p.id === positionId)?.clause ?? positionId;
}

type AddModuleDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: OnFollowupBuildDone;
  isBuilding?: boolean;
  baseRunId?: string | null;
};

export function AddModuleDialog({
  open,
  onOpenChange,
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
}: AddModuleDialogProps) {
  const [placements, setPlacements] = useState<Placement[]>([]);
  const [dragOverPageId, setDragOverPageId] = useState<string | null>(null);
  const { runFollowup, isBusy, error } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const addPlacement = useCallback((moduleId: string, pageId: string) => {
    setPlacements((current) => [
      ...current,
      {
        key: `${moduleId}-${pageId}-${Date.now()}-${current.length}`,
        moduleId,
        pageId,
        // Default: längst ner (backendens default-slot, före kontakt-CTA:n)
        // så vi inte överlovar topp-placering operatören inte bett om.
        positionId: "bottom",
      },
    ]);
  }, []);

  const removePlacement = useCallback((key: string) => {
    setPlacements((current) => current.filter((p) => p.key !== key));
  }, []);

  const setPlacementPosition = useCallback((key: string, positionId: string) => {
    setPlacements((current) =>
      current.map((p) => (p.key === key ? { ...p, positionId } : p)),
    );
  }, []);

  const handleDrop = useCallback(
    (pageId: string) => (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOverPageId(null);
      const moduleId = event.dataTransfer.getData(DRAG_MIME);
      if (!moduleId) return;
      addPlacement(moduleId, pageId);
    },
    [addPlacement],
  );

  const handleSubmit = useCallback(async () => {
    if (placements.length === 0) return;
    const lines = placements.map(
      (p) =>
        `- sektionen "${moduleLabel(p.moduleId)}" på ${pageLabel(p.pageId)} (${positionClause(p.positionId)})`,
    );
    const prompt = `Lägg till följande sektioner på sajten:\n${lines.join("\n")}\n\nBehåll övrig design, copy och struktur intakt.`;
    const result = await runFollowup(prompt);
    if (result.ok) {
      setPlacements([]);
      onOpenChange(false);
    }
  }, [placements, runFollowup, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Lägg till modul</DialogTitle>
          <DialogDescription>
            Dra (eller klicka) en modul till en sida. Vi skickar en strukturerad
            instruktion och bygger om sajten. Märkningen på varje kort visar
            ärligt vad som syns efter bygget: vissa moduler renderas på
            startsidan eller blir egna sidor, andra registreras utan att synas
            än. Exakt position är något vi bara styr på startsidan (överst /
            längst ner) — finare placering och fler sidor kommer senare.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Modul-palett — draggable + klickbara kort (klick = a11y-fallback). */}
          <div>
            <p className="text-muted-foreground mb-2 text-[11px] tracking-tight uppercase">
              Moduler
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {MODULE_CATALOG.map((mod) => {
                const Icon = mod.Icon;
                const badge = EFFECT_BADGES[mod.effect];
                return (
                  <button
                    key={mod.id}
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData(DRAG_MIME, mod.id);
                      event.dataTransfer.effectAllowed = "copy";
                    }}
                    onClick={() => addPlacement(mod.id, "home")}
                    title={`${mod.label} — ${mod.description}. ${badge.title}`}
                    aria-label={`Lägg till ${mod.label} (dra till en sida eller klicka för startsidan) — ${badge.label}`}
                    className={cn(
                      "border-border/60 hover:border-border bg-card/60 flex cursor-grab items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition active:scale-[0.98] active:cursor-grabbing",
                    )}
                  >
                    <Icon className="text-muted-foreground h-4 w-4 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="text-foreground block truncate text-[12px] font-medium">
                        {mod.label}
                      </span>
                      <span className="text-muted-foreground block truncate text-[10px]">
                        {mod.description}
                      </span>
                      <span
                        className={cn(
                          "mt-0.5 block truncate text-[9.5px] font-medium",
                          mod.effect === "registered"
                            ? "text-muted-foreground/70"
                            : "text-emerald-600 dark:text-emerald-400",
                        )}
                      >
                        {badge.label}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Sid-zoner — drop-targets. */}
          <div>
            <p className="text-muted-foreground mb-2 text-[11px] tracking-tight uppercase">
              Sidor
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {PAGE_TARGETS.map((page) => (
                <div
                  key={page.id}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "copy";
                    setDragOverPageId(page.id);
                  }}
                  onDragLeave={() => setDragOverPageId((cur) => (cur === page.id ? null : cur))}
                  onDrop={handleDrop(page.id)}
                  className={cn(
                    "flex min-h-[52px] flex-col items-center justify-center rounded-lg border border-dashed px-2 py-3 text-center text-[12px] transition",
                    dragOverPageId === page.id
                      ? "border-foreground bg-foreground/5 text-foreground"
                      : "border-border/60 text-muted-foreground",
                  )}
                >
                  <span className="font-medium">{page.label}</span>
                  <span className="text-[10px] opacity-70">släpp här</span>
                </div>
              ))}
            </div>
          </div>

          {/* Kö av planerade placeringar. */}
          {placements.length > 0 ? (
            <div>
              <p className="text-muted-foreground mb-2 text-[11px] tracking-tight uppercase">
                Att lägga till ({placements.length})
              </p>
              <ul className="flex flex-col gap-1.5">
                {placements.map((p) => (
                  <li
                    key={p.key}
                    className="border-border/60 bg-card/60 flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-[12px]"
                  >
                    <span className="text-foreground min-w-0 flex-1 truncate">
                      <span className="font-medium">{moduleLabel(p.moduleId)}</span>
                      <span className="text-muted-foreground"> → {pageLabel(p.pageId)}</span>
                    </span>
                    <select
                      value={p.positionId}
                      onChange={(event) => setPlacementPosition(p.key, event.target.value)}
                      aria-label={`Position för ${moduleLabel(p.moduleId)} på ${pageLabel(p.pageId)}`}
                      className="border-border/60 bg-background text-muted-foreground rounded border px-1.5 py-1 text-[11px]"
                    >
                      {POSITIONS.map((pos) => (
                        <option key={pos.id} value={pos.id}>
                          {pos.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => removePlacement(p.key)}
                      aria-label={`Ta bort ${moduleLabel(p.moduleId)}`}
                      className="text-muted-foreground hover:text-foreground rounded p-1 transition"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-muted-foreground border-border/60 rounded-md border border-dashed px-3 py-2 text-[11px] leading-snug">
              Modulerna ovan kan backend montera (section_add). Märkningen per
              kort visar vad som syns: &quot;syns på startsidan&quot; renderas
              som block (om sajten har riktigt innehåll för sektionen),
              &quot;egen sida&quot; får en route i menyn, &quot;syns inte än&quot;
              registreras utan synlig ändring. Bygget rapporterar ärligt i
              chatten och toasten vad som faktiskt landade.
            </p>
          )}
        </div>

        {error ? (
          <p
            role="alert"
            className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
          >
            {error}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isBusy}
          >
            Avbryt
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={isBusy || placements.length === 0}
          >
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <Blocks className="h-4 w-4" />
                Lägg till {placements.length > 0 ? `(${placements.length})` : ""}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
