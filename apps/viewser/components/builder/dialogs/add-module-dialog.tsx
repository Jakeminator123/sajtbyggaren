"use client";

import {
  Blocks,
  Briefcase,
  Clock,
  HelpCircle,
  Images,
  LayoutTemplate,
  Loader2,
  Mail,
  MapPin,
  Megaphone,
  ShieldCheck,
  Star,
  Tag,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useState } from "react";

import { useFollowupBuild } from "@/components/builder/use-followup-build";
import type { PromptBuildOutcome } from "@/components/prompt-builder";
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
 * Lägg till modul — yta för att be backend lägga in en ny sektion på sajten.
 * Operatören drar (eller klickar) ett modulkort till släpp-zonen och vi
 * komponerar en följdprompt som skickas via samma `useFollowupBuild`-seam
 * som färg/variant/bild-dialogerna.
 *
 * KONTRAKTET (verifierat mot backend `section_add`, section_directives.py):
 * backend stödjer i MVP fyra sanktionerade sektionstyper — `team`, `faq`,
 * `trust` (garantier) och `reviews` (recensioner/omdömen) — som monteras
 * genom samma kontrollerade OpenClaw-apply-kedja som en restyle. Routern
 * (KÖR-6a classify.py) känner igen ett add-verb ("lägg till") + ett
 * sektions-ord ("sektion"/"FAQ-sektion") + ett typ-ord, så modulernas
 * `prompt` är formulerade exakt så. En typ utan implementerande dossier blir
 * en ÄRLIG no-op (`stage=section_unsupported`) — vi låtsas aldrig.
 *
 * MEDVETET INGEN frontend-magi: vi muterar inte previewen direkt (den är en
 * cross-origin iframe vi inte når DOM:en i). Sid-/positions-targeting visas
 * INTE än eftersom backend inte resolvar sida/position — den kommer tillbaka
 * när Jakob wirar det (docs/agent-inbox.jsonl, topic module-dragdrop-prep).
 */

// Sanktionerad sektionstyp i backend (section_directives.SECTION_TYPE_CAPABILITY).
// null = ingen monterbar dossier än → modulen är "kommer", inte valbar.
type SectionType = "team" | "faq" | "trust" | "reviews";

type ModuleDef = {
  id: string;
  label: string;
  description: string;
  Icon: LucideIcon;
  // null = inte inkopplad i backend än (ärligt "kommer", ej valbar).
  sectionType: SectionType | null;
  // Router-matchande svensk följdprompt (add-verb + sektions-ord + typ-ord).
  // Bara satt för sektionstyper backend faktiskt kan montera.
  prompt?: string;
};

// Modul-paletten. De fyra med `sectionType` är live mot backend `section_add`;
// resten är synliga men markerade "kommer" tills fler dossiers finns.
const MODULE_CATALOG: ReadonlyArray<ModuleDef> = [
  {
    id: "faq",
    label: "Vanliga frågor",
    description: "Hopfällbara frågor och svar",
    Icon: HelpCircle,
    sectionType: "faq",
    prompt: "Lägg till en FAQ-sektion",
  },
  {
    id: "testimonials",
    label: "Omdömen",
    description: "Kundcitat och recensioner",
    Icon: Star,
    sectionType: "reviews",
    prompt: "Lägg till en sektion med recensioner",
  },
  {
    id: "team",
    label: "Team",
    description: "Personalkort",
    Icon: Users,
    sectionType: "team",
    prompt: "Lägg till en sektion om teamet",
  },
  {
    id: "trust-badges",
    label: "Garantier",
    description: "Trygghet och förtroende",
    Icon: ShieldCheck,
    sectionType: "trust",
    prompt: "Lägg till en sektion om garantier",
  },
  // Nedan: inte inkopplade i backend än (ärligt "kommer").
  { id: "hero", label: "Hero", description: "Stor toppbanner", Icon: LayoutTemplate, sectionType: null },
  { id: "gallery", label: "Galleri", description: "Bildrutnät", Icon: Images, sectionType: null },
  { id: "services", label: "Tjänster", description: "Tjänste-/produktkort", Icon: Briefcase, sectionType: null },
  { id: "contact-form", label: "Kontaktformulär", description: "Namn, e-post, meddelande", Icon: Mail, sectionType: null },
  { id: "pricing", label: "Priser", description: "Pris-/paketlista", Icon: Tag, sectionType: null },
  { id: "cta-banner", label: "CTA-banner", description: "Uppmaning med knapp", Icon: Megaphone, sectionType: null },
  { id: "map", label: "Karta", description: "Plats med adress", Icon: MapPin, sectionType: null },
  { id: "opening-hours", label: "Öppettider", description: "Veckoschema", Icon: Clock, sectionType: null },
];

const DRAG_MIME = "application/x-sajtbyggaren-module";

function moduleById(moduleId: string): ModuleDef | undefined {
  return MODULE_CATALOG.find((m) => m.id === moduleId);
}

type AddModuleDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: (runId: string, outcome: PromptBuildOutcome) => void;
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
  // En sektion per följdprompt (routern hanterar en section_add per meddelande).
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const { runFollowup, isBusy, error } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const selectModule = useCallback((moduleId: string) => {
    const mod = moduleById(moduleId);
    if (!mod || !mod.sectionType) return; // bara live-typer kan väljas
    setPendingId(moduleId);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragOver(false);
      const moduleId = event.dataTransfer.getData(DRAG_MIME);
      if (moduleId) selectModule(moduleId);
    },
    [selectModule],
  );

  const handleSubmit = useCallback(async () => {
    const mod = pendingId ? moduleById(pendingId) : undefined;
    if (!mod?.prompt) return;
    const prompt = `${mod.prompt}. Behåll övrig design, copy och struktur intakt.`;
    const result = await runFollowup(prompt);
    if (result.ok) {
      setPendingId(null);
      onOpenChange(false);
    }
  }, [pendingId, runFollowup, onOpenChange]);

  const pending = pendingId ? moduleById(pendingId) : undefined;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Lägg till sektion</DialogTitle>
          <DialogDescription>
            Dra (eller klicka) en sektion till släpp-zonen. Vi skickar en
            instruktion och bygger om sajten med den nya sektionen.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {/* Sektions-palett — live-typer är draggable/klickbara, "kommer" är inaktiva. */}
          <div>
            <p className="text-muted-foreground mb-2 text-[11px] tracking-tight uppercase">
              Sektioner
            </p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {MODULE_CATALOG.map((mod) => {
                const Icon = mod.Icon;
                const live = Boolean(mod.sectionType);
                const isPending = mod.id === pendingId;
                return (
                  <button
                    key={mod.id}
                    type="button"
                    draggable={live}
                    disabled={!live}
                    onDragStart={
                      live
                        ? (event) => {
                            event.dataTransfer.setData(DRAG_MIME, mod.id);
                            event.dataTransfer.effectAllowed = "copy";
                          }
                        : undefined
                    }
                    onClick={() => selectModule(mod.id)}
                    title={
                      live
                        ? `${mod.label} — ${mod.description}`
                        : `${mod.label} — kommer (inte inkopplad i backend än)`
                    }
                    aria-label={
                      live
                        ? `Lägg till ${mod.label} (dra till släpp-zonen eller klicka)`
                        : `${mod.label} — kommer, inte valbar än`
                    }
                    className={cn(
                      "relative flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition",
                      live
                        ? "border-border/60 hover:border-border bg-card/60 cursor-grab active:scale-[0.98] active:cursor-grabbing"
                        : "border-border/40 bg-muted/30 cursor-not-allowed opacity-55",
                      isPending && "border-foreground bg-foreground/5",
                    )}
                  >
                    <Icon className="text-muted-foreground h-4 w-4 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="text-foreground block truncate text-[12px] font-medium">
                        {mod.label}
                      </span>
                      <span className="text-muted-foreground block truncate text-[10px]">
                        {live ? mod.description : "Kommer"}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Släpp-zon + vald sektion. */}
          <div
            onDragOver={(event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "copy";
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-[56px] items-center justify-between gap-2 rounded-lg border border-dashed px-3 py-3 text-[12px] transition",
              isDragOver
                ? "border-foreground bg-foreground/5 text-foreground"
                : "border-border/60 text-muted-foreground",
            )}
          >
            {pending ? (
              <>
                <span className="text-foreground min-w-0 flex-1 truncate">
                  Lägger till: <span className="font-medium">{pending.label}</span>
                </span>
                <button
                  type="button"
                  onClick={() => setPendingId(null)}
                  aria-label={`Ta bort vald sektion ${pending.label}`}
                  className="text-muted-foreground hover:text-foreground rounded p-1 transition"
                >
                  <X className="h-3.5 w-3.5" aria-hidden />
                </button>
              </>
            ) : (
              <span className="w-full text-center">Släpp en sektion här</span>
            )}
          </div>

          <p className="text-muted-foreground border-border/60 rounded-md border border-dashed px-3 py-2 text-[11px] leading-snug">
            Backend stödjer i nuläget sektionerna ovan som är aktiva. Stöds inte
            en typ rapporterar bygget det ärligt i chatten. Vilken sida och
            position sektionen hamnar på styrs av backend tills sid-targeting är
            inkopplad.
          </p>
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
          <Button type="button" onClick={handleSubmit} disabled={isBusy || !pending}>
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <Blocks className="h-4 w-4" />
                Lägg till
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
