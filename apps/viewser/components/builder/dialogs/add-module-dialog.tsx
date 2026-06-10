"use client";

import {
  Blocks,
  Clock,
  HelpCircle,
  Images,
  Loader2,
  Mail,
  MapPin,
  MousePointerClick,
  ShieldCheck,
  Star,
  Tag,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  useFollowupBuild,
  type FollowupToolIntent,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
import { usePreviewInspector } from "@/components/preview-inspector-context";
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
  /**
   * Substantivfrasen som skickas i följdprompten ("Lägg till <promptNoun>
   * <överst|längst ner>."). EMPIRISKT verifierad mot routern (classify.py):
   * varje fras klassas som section_add med rätt componentIntent + position
   * för ALLA nio moduler i båda positionerna. VIKTIGT: nämn INTE sidan i
   * prompten ("på startsidan"/"på sidan") — det tippar vissa typer (pris/
   * team/garantier) till route_add. Backend defaultar ändå till home-routen.
   */
  promptNoun: string;
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
  {
    id: "gallery",
    label: "Galleri",
    description: "Bildrutnät",
    Icon: Images,
    effect: "registered",
    promptNoun: "en galleri-sektion",
  },
  {
    id: "contact-form",
    label: "Kontaktformulär",
    description: "Namn, e-post, meddelande",
    Icon: Mail,
    effect: "registered",
    promptNoun: "en kontaktformulär-sektion",
  },
  {
    id: "faq",
    label: "Vanliga frågor",
    description: "Hopfällbara frågor och svar",
    Icon: HelpCircle,
    effect: "route",
    promptNoun: "en FAQ-sektion",
  },
  {
    id: "testimonials",
    label: "Omdömen",
    description: "Kundcitat",
    Icon: Star,
    effect: "registered",
    promptNoun: "en sektion med omdömen",
  },
  {
    id: "pricing",
    label: "Priser",
    description: "Pris-/paketlista",
    Icon: Tag,
    effect: "registered",
    promptNoun: "en sektion med priser",
  },
  {
    id: "map",
    label: "Karta",
    description: "Plats med adress",
    Icon: MapPin,
    effect: "registered",
    promptNoun: "en sektion med en karta",
  },
  {
    id: "opening-hours",
    label: "Öppettider",
    description: "Veckoschema",
    Icon: Clock,
    effect: "inline",
    promptNoun: "en öppettider-sektion",
  },
  {
    id: "team",
    label: "Team",
    description: "Personalkort",
    Icon: Users,
    effect: "route",
    promptNoun: "en team-sektion",
  },
  {
    id: "trust-badges",
    label: "Förtroende",
    description: "Certifikat och logotyper",
    Icon: ShieldCheck,
    effect: "registered",
    promptNoun: "en sektion om garantier",
  },
];

/** Operatörsvänlig, ärlig etikett per synlighets-utfall ("kan" — gated). */
const EFFECT_BADGES: Record<ModuleEffect, { label: string; title: string }> = {
  inline: {
    label: "kan synas på startsidan",
    // Scaffold-nyansen per msg-0057: inline-rendern gäller i skiva 1 bara
    // local-service-business-sajter; på andra sajttyper blir den ärligt
    // mount-only (toasten säger då "registrerad men syns inte").
    title:
      "Kan renderas som ett block på startsidan — förutsatt att sajten har riktigt innehåll för sektionen (inga påhittade uppgifter). Gäller i nuläget sajter byggda på företags-/tjänstemallen; på andra sajttyper registreras den utan att synas än.",
  },
  route: {
    label: "kan bli egen sida",
    title:
      "Kan läggas till som en egen sida med länk i menyn (t.ex. /faq) — gäller företags-/tjänstemallen, och team-sidan kräver att sajten har team-uppgifter. Annars registreras den utan att synas än.",
  },
  registered: {
    label: "syns inte än",
    title:
      "Monteras och registreras i sajtens data men renderas inte i previewen än. Bygget rapporterar ärligt vad som landade.",
  },
};

// Sid-mål. I skiva 1 styr backend bara startsidan (inline-rendern är
// home-only och routern sid-targetar inte) — övriga sidor visas som
// medvetet inaktiva zoner ("stöds inte än") i stället för att lova en
// placering bygget inte kan hålla (granskningsfynd 2026-06-09).
const PAGE_TARGETS: ReadonlyArray<{
  id: string;
  label: string;
  enabled: boolean;
}> = [
  { id: "home", label: "Startsida", enabled: true },
  { id: "about", label: "Om oss", enabled: false },
  { id: "services", label: "Tjänster", enabled: false },
  { id: "contact", label: "Kontakt", enabled: false },
];

// Positions-slot. `clause` blir en del av följdprompten och MÅSTE vara ett
// nyckelord routern parsar (_POSITION_PHRASES i packages/generation/
// orchestration/router/classify.py): "överst" → top (= direkt efter hero),
// "längst ner" → bottom (= före kontakt-CTA:n). Minimala fraser med flit —
// EMPIRISKT verifierat att längre fraser med "på sidan" tippar vissa
// sektionstyper till route_add i klassificeringen.
const POSITIONS: ReadonlyArray<{ id: string; label: string; clause: string }> =
  [
    { id: "top", label: "Överst (efter hero)", clause: "överst" },
    { id: "bottom", label: "Längst ner", clause: "längst ner" },
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

function modulePromptNoun(moduleId: string): string {
  return MODULE_CATALOG.find((m) => m.id === moduleId)?.promptNoun ?? moduleId;
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
  // Etikett från senaste peka-i-previewn-valet ("Efter Omdömen → längst
  // ner") — visas vid placeringsraden som kvitto på var klicket landade.
  const [pickedLabel, setPickedLabel] = useState<string | null>(null);
  const { runFollowup, isBusy, error } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  // Peka-i-previewn: knappen visas bara när en server-nåbar preview-URL
  // finns (local-next/vercel-sandbox — StackBlitz publicerar ingen).
  // Flödet: requestPlacementPick() + stäng dialogen → ViewerPanel ritar
  // overlayn → klick/Esc → BuilderShell öppnar dialogen igen → effekten
  // nedan läser ut lastPlacementPick och sätter positionen.
  const {
    previewUrl,
    requestPlacementPick,
    lastPlacementPick,
    clearPlacementPick,
  } = usePreviewInspector();

  useEffect(() => {
    if (!open || !lastPlacementPick) return;
    const timerId = window.setTimeout(() => {
      const { point, coarsePosition } = lastPlacementPick;
      setPlacements((current) =>
        current.length > 0
          ? current.map((p, idx) =>
              idx === 0 ? { ...p, positionId: coarsePosition } : p,
            )
          : current,
      );
      setPickedLabel(
        `${point.label} → ${coarsePosition === "top" ? "överst" : "längst ner"}`,
      );
      clearPlacementPick();
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [open, lastPlacementPick, clearPlacementPick]);

  const handlePlacementPick = useCallback(() => {
    requestPlacementPick();
    onOpenChange(false);
  }, [requestPlacementPick, onOpenChange]);

  const addPlacement = useCallback((moduleId: string, pageId: string) => {
    // En modul per bygge (skiva 1): routern klassar EN section_add-klausul
    // tillförlitligt, men flera moduler i samma prompt kollapsar till fel
    // editKind (empiriskt verifierat mot classify.py). Ett nytt val ersätter
    // därför det föregående i stället för att köa.
    setPlacements([
      {
        key: `${moduleId}-${pageId}-${Date.now()}`,
        moduleId,
        pageId,
        // Default: längst ner (backendens default-slot, före kontakt-CTA:n)
        // så vi inte överlovar topp-placering operatören inte bett om.
        positionId: "bottom",
      },
    ]);
    setPickedLabel(null);
  }, []);

  const removePlacement = useCallback((key: string) => {
    setPlacements((current) => current.filter((p) => p.key !== key));
    setPickedLabel(null);
  }, []);

  const setPlacementPosition = useCallback(
    (key: string, positionId: string) => {
      setPlacements((current) =>
        current.map((p) => (p.key === key ? { ...p, positionId } : p)),
      );
      // Manuellt positionsval ersätter peka-kvittot (annars skulle kvittot
      // kunna motsäga dropdownen).
      setPickedLabel(null);
    },
    [],
  );

  const handleDrop = useCallback(
    (pageId: string) => (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setDragOverPageId(null);
      // Inaktiva sid-zoner tar inte emot släpp (skiva 1: bara Startsida).
      if (!PAGE_TARGETS.find((p) => p.id === pageId)?.enabled) return;
      const moduleId = event.dataTransfer.getData(DRAG_MIME);
      if (!moduleId) return;
      addPlacement(moduleId, pageId);
    },
    [addPlacement],
  );

  const handleSubmit = useCallback(async () => {
    const placement = placements[0];
    if (!placement) return;
    // EMPIRISKT verifierat promptformat (alla 9 moduler x båda positionerna
    // klassas som section_add med rätt componentIntent + position): EN
    // självständig klausul med verb + sektionstyps-substantiv + minimal
    // positionsfras. Nämn INTE sidan ("på startsidan"/"på sidan") — det
    // tippar pris/team/garantier till route_add. Backend defaultar till
    // home-routen, vilket är exakt vad sid-zonen (Startsida) lovar.
    const prompt =
      `Lägg till ${modulePromptNoun(placement.moduleId)} ` +
      `${positionClause(placement.positionId)}. ` +
      "Behåll övrig design, copy och struktur intakt.";
    // Strukturerad intent (specialist-dispatch steg 2): modul-id +
    // position är redan exakta — promptformatet ovan är empiriskt
    // router-säkert men med toolIntent slipper backend klassificera
    // alls och kan gå rakt till section_add-pipelinen.
    const toolIntent: FollowupToolIntent = {
      tool: "section_add",
      params: {
        sectionType: placement.moduleId,
        position: placement.positionId === "top" ? "top" : "bottom",
      },
    };
    const result = await runFollowup(prompt, { toolIntent });
    if (result.ok) {
      setPlacements([]);
      setPickedLabel(null);
      onOpenChange(false);
    }
  }, [placements, runFollowup, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Lägg till modul</DialogTitle>
          <DialogDescription>
            Dra (eller klicka) en modul till startsidan — en modul per bygge. Vi
            skickar en strukturerad instruktion och bygger om sajten. Märkningen
            på varje kort visar ärligt vad som kan synas efter bygget. Exakt
            position är något vi bara styr på startsidan (överst / längst ner) —
            finare placering och fler sidor kommer senare.
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
                    <Icon
                      className="text-muted-foreground h-4 w-4 shrink-0"
                      aria-hidden
                    />
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
                  aria-disabled={!page.enabled}
                  onDragOver={(event) => {
                    if (!page.enabled) return;
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "copy";
                    setDragOverPageId(page.id);
                  }}
                  onDragLeave={() =>
                    setDragOverPageId((cur) => (cur === page.id ? null : cur))
                  }
                  onDrop={handleDrop(page.id)}
                  className={cn(
                    "flex min-h-[52px] flex-col items-center justify-center rounded-lg border border-dashed px-2 py-3 text-center text-[12px] transition",
                    !page.enabled
                      ? "border-border/40 text-muted-foreground/50 opacity-60"
                      : dragOverPageId === page.id
                        ? "border-foreground bg-foreground/5 text-foreground"
                        : "border-border/60 text-muted-foreground",
                  )}
                >
                  <span className="font-medium">{page.label}</span>
                  <span className="text-[10px] opacity-70">
                    {page.enabled ? "släpp här" : "stöds inte än"}
                  </span>
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
                      <span className="font-medium">
                        {moduleLabel(p.moduleId)}
                      </span>
                      <span className="text-muted-foreground">
                        {" "}
                        → {pageLabel(p.pageId)}
                      </span>
                    </span>
                    <select
                      value={p.positionId}
                      onChange={(event) =>
                        setPlacementPosition(p.key, event.target.value)
                      }
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
              {/* Peka-i-previewn: välj position genom att klicka i den
                  rendrade förhandsvisningen i stället för dropdownen.
                  Dialogen stängs under valet och öppnas igen efteråt.
                  Visas bara när en server-nåbar preview-URL finns. */}
              {previewUrl ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handlePlacementPick}
                    disabled={isBusy}
                    className="border-border/60 hover:border-border text-foreground inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] transition disabled:opacity-50"
                  >
                    <MousePointerClick className="h-3.5 w-3.5" aria-hidden />
                    Peka i förhandsvisningen
                  </button>
                  {pickedLabel ? (
                    <span className="text-muted-foreground text-[11px]">
                      Vald plats:{" "}
                      <span className="text-foreground">{pickedLabel}</span>
                    </span>
                  ) : (
                    <span className="text-muted-foreground/70 text-[10.5px]">
                      Dialogen stängs medan du väljer — klicket snäpper till
                      överst/längst ner.
                    </span>
                  )}
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-muted-foreground border-border/60 rounded-md border border-dashed px-3 py-2 text-[11px] leading-snug">
              Modulerna ovan kan backend montera (section_add). Märkningen per
              kort visar vad som kan synas: &quot;kan synas på startsidan&quot;
              renderas som block (om sajten har riktigt innehåll för sektionen
              och bygger på företags-/tjänstemallen), &quot;kan bli egen
              sida&quot; får en route i menyn när villkoren stöds, &quot;syns
              inte än&quot; registreras utan synlig ändring. Bygget rapporterar
              ärligt i chatten och toasten vad som faktiskt landade.
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
                Lägg till{" "}
                {placements.length > 0 ? `(${placements.length})` : ""}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
