"use client";

import { Check, Loader2, Sparkles, X } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { DEMO_PROFILES } from "./demo-answers";
import { DirectivesPreview } from "./directives-preview";
import { ContentOrchestratorStep } from "./steps/content-orchestrator";
import { FoundationStep, type ScrapeState } from "./steps/foundation-step";
import { FunctionsStep } from "./steps/functions-step";
import { MediaStep } from "./steps/media-step";
import { VisualStep } from "./steps/visual-step";
import {
  fallbackDiscoveryOptions,
  resolveContentBranchFromOptions,
} from "./discovery-options";
import type { discoveryOption } from "./discovery-options";
import type { WizardAnswers, WizardStepId } from "./wizard-types";
import {
  emptyWizardAnswers,
  validateWizardStep,
  WIZARD_STEP_ORDER,
  WIZARD_STEP_PIPELINE_BADGE,
  WIZARD_STEP_TITLES,
  wizardCompletionPercent,
} from "./wizard-types";

/**
 * Modal-driven discovery wizard. Visas över hela skärmen när
 * `open === true` och tar emot operatorns prompt-text i
 * `initialPrompt` så att första steget kan visa pitchen som default i
 * `offer`-fältet.
 *
 * När operatorn klickar "Skapa sajt" på sista steget anropar vi
 * `onComplete(answers)`. Det är där `prompt-builder.tsx` tar över och
 * POST:ar till `/api/prompt` med discovery-payload + originalprompt.
 */

export type DiscoveryWizardProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialPrompt: string;
  initialAnswers?: WizardAnswers;
  onComplete: (
    answers: WizardAnswers,
    discoveryOptions: readonly discoveryOption[],
  ) => void;
};

/**
 * Steg som operatören får hoppa över utan att fylla i något. Foundation
 * + functions har minimi-validering och är därför inte hoppbara.
 */
const SKIPPABLE_STEPS = new Set<WizardStepId>(["visual", "content", "media"]);

type discoveryOptionsState = {
  options: discoveryOption[];
  source: "governance" | "fallback";
};

/**
 * Steg-metadata för den nordiska/tech-stilade två-spalts-layouten.
 * `eyebrow` = liten label ovanför rubriken; `description` = ledtext
 * som hjälper operatorn förstå syftet utan att öppna ett tooltip.
 * Stilen efterliknar Apple / Linear / Vercel onboarding: tunn typografi,
 * generös whitespace, monokrom palett.
 */
const STEP_META: Record<
  WizardStepId,
  { eyebrow: string; description: string }
> = {
  foundation: {
    eyebrow: "Sidor",
    description:
      "Vem ni är och vilken typ av verksamhet. Styr scaffold + starter (vilken Next.js-mall vi använder).",
  },
  visual: {
    eyebrow: "Visuellt",
    description:
      "Vibe, färger och typografi. Styr variant (CSS-tokens) — färgerna kan skriva över vibens defaults.",
  },
  functions: {
    eyebrow: "Funktioner",
    description:
      "Vad ska sajten kunna göra? Funktionerna styr Dossier-val och sid-routes på en gång.",
  },
  content: {
    eyebrow: "Innehåll",
    description:
      "Tjänster, produkter, story, ton och målgrupp — allt som matar copy och planner.",
  },
  media: {
    eyebrow: "Media",
    description:
      "Logotyp, hero, galleri, favicon, OG-image och bakgrundsvideo. Sjsta steget innan vi bygger.",
  },
};

export function DiscoveryWizard({
  open,
  onOpenChange,
  initialPrompt,
  initialAnswers,
  onComplete,
}: DiscoveryWizardProps) {
  const [answers, setAnswers] = useState<WizardAnswers>(() => {
    const base = initialAnswers ?? emptyWizardAnswers();
    // Förifyll pitchen från prompt-builder så operatorn slipper
    // skriva om samma sak. Wizardens första steg har en read/write-
    // textarea där detta kan justeras innan kategori-steget.
    if (!base.offer.trim() && initialPrompt.trim()) {
      return { ...base, offer: initialPrompt.trim() };
    }
    return base;
  });
  const [stepIndex, setStepIndex] = useState(0);
  const [discoveryOptionsState, setDiscoveryOptionsState] =
    useState<discoveryOptionsState>(() => ({
      options: fallbackDiscoveryOptions(),
      source: "fallback",
    }));
  // Lyft skrape-state från CompanyStep så vi kan visa en overlay över
  // hela popupen medan /api/scrape-site körs.
  const [scrapeState, setScrapeState] = useState<ScrapeState | null>(null);

  // Roterande demo-profil-cursor. Klick på "Fyll demo" laddar
  // profil[demoCursor], visar profilnamnet kort i footern och flyttar
  // cursorn till nästa profil. Modulo över DEMO_PROFILES.length så
  // operatören kan testa varje profil utan att stänga wizarden.
  const demoCursorRef = useRef(0);
  const [demoNotice, setDemoNotice] = useState<string | null>(null);
  const demoNoticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const step = WIZARD_STEP_ORDER[stepIndex];
  const discoveryOptions = discoveryOptionsState.options;
  const branch = useMemo(
    () => resolveContentBranchFromOptions(answers.siteType, discoveryOptions),
    [answers.siteType, discoveryOptions],
  );
  const validationError = useMemo(
    () => validateWizardStep(step, answers, branch),
    [step, answers, branch],
  );
  const completion = useMemo(
    () => wizardCompletionPercent(answers, branch),
    [answers, branch],
  );

  const updateAnswers = useCallback((next: Partial<WizardAnswers>) => {
    setAnswers((prev) => ({ ...prev, ...next }));
  }, []);

  const goBack = useCallback(() => {
    setStepIndex((idx) => Math.max(0, idx - 1));
  }, []);

  const goNext = useCallback(() => {
    if (validationError) return;
    setStepIndex((idx) => Math.min(WIZARD_STEP_ORDER.length - 1, idx + 1));
  }, [validationError]);

  const skipStep = useCallback(() => {
    setStepIndex((idx) => Math.min(WIZARD_STEP_ORDER.length - 1, idx + 1));
  }, []);

  /**
   * Fyll wizarden med nästa demo-profil i rotationen. Tre profiler
   * täcker våra två fungerande scaffolds (local-service-business +
   * ecommerce-lite) och tre olika content-branches (construction,
   * restaurant, ecommerce) så operatören kan testa varje gren utan
   * att skriva igenom 7 stegen manuellt.
   *
   * Vi byter inte automatiskt steg — operatören kan klicka igenom
   * stegen för att granska data, eller hoppa direkt till sista steget
   * via sidebar-navigeringen och klicka "Skapa sajt".
   */
  const fillDemo = useCallback(() => {
    if (DEMO_PROFILES.length === 0) return;
    const profile = DEMO_PROFILES[demoCursorRef.current % DEMO_PROFILES.length];
    demoCursorRef.current = (demoCursorRef.current + 1) % DEMO_PROFILES.length;
    setAnswers(profile.build());
    setDemoNotice(`Demo inläst: ${profile.label}`);
    if (demoNoticeTimerRef.current) {
      clearTimeout(demoNoticeTimerRef.current);
    }
    demoNoticeTimerRef.current = setTimeout(() => {
      setDemoNotice(null);
      demoNoticeTimerRef.current = null;
    }, 2500);
  }, []);

  useEffect(() => {
    return () => {
      if (demoNoticeTimerRef.current) {
        clearTimeout(demoNoticeTimerRef.current);
      }
    };
  }, []);

  const finish = useCallback(() => {
    if (validationError) return;
    onComplete(answers, discoveryOptions);
  }, [answers, discoveryOptions, onComplete, validationError]);

  const isFirst = stepIndex === 0;
  const isLast = stepIndex === WIZARD_STEP_ORDER.length - 1;
  const canSkip = SKIPPABLE_STEPS.has(step);

  /**
   * Globala wizard-keyboard-shortcuts. Aktiveras bara när wizardin är
   * öppen. esc stängs automatiskt av Radix Dialog så vi hanterar bara
   * primär-actionen här:
   *   - ⌘↵ / Ctrl+↵ ⇒ goNext (eller finish när sista steget)
   *
   * Capture-fasen undviks så textarea/input-fält som har lokala
   * cmd+enter-handlers (t.ex. för newline-insert) får företräde. Vi
   * lyssnar på bubble-fasen och kollar att event inte redan är
   * defaultPrevented av en lokal handler.
   */
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key !== "Enter") return;
      if (!event.metaKey && !event.ctrlKey) return;
      event.preventDefault();
      if (isLast) {
        finish();
      } else {
        goNext();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, isLast, goNext, finish]);

  const meta = STEP_META[step];
  const isScraping = scrapeState?.status === "loading";

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    async function loadDiscoveryOptions() {
      try {
        const response = await fetch("/api/discovery-options", {
          cache: "no-store",
        });
        if (!response.ok) return;
        const payload = (await response.json()) as {
          options?: discoveryOption[];
        };
        if (!Array.isArray(payload.options) || payload.options.length === 0) {
          return;
        }
        if (!cancelled) {
          setDiscoveryOptionsState({
            options: payload.options,
            source: "governance",
          });
        }
      } catch {
        // Keep the local UI cache so the operator can continue if the
        // governance endpoint is temporarily unavailable.
      }
    }
    void loadDiscoveryOptions();
    return () => {
      cancelled = true;
    };
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="border-border/60 bg-background grid h-[min(100dvh-2rem,780px)] !w-[min(100vw-2rem,1180px)] !max-w-[min(100vw-2rem,1180px)] grid-cols-1 gap-0 overflow-hidden border p-0 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] sm:!max-w-[min(100vw-2rem,1180px)] sm:rounded-3xl md:grid-cols-[280px_1fr] md:grid-rows-1"
        showCloseButton={false}
      >
        {/* Sidebar — ljus minimalistisk panel. Tunn höger-border ger
            visuell separation utan att skapa kontrast-brus. */}
        <aside className="border-border/50 bg-muted/30 hidden flex-col border-r px-6 py-7 md:flex">
          <div className="mb-9 flex items-center gap-2.5">
            <Image
              src="/LOGO_SM2.0.png"
              alt="Sajtmaskin"
              width={28}
              height={28}
              priority
              className="size-7 rounded-md object-contain"
            />
            <div className="flex flex-col leading-tight">
              <span className="text-foreground text-[13px] font-semibold tracking-tight">
                Sajtbyggaren
              </span>
              <span className="text-muted-foreground font-mono text-[9.5px] tracking-[0.22em] uppercase">
                Discovery
              </span>
            </div>
          </div>

          <nav className="flex flex-col gap-px">
            {WIZARD_STEP_ORDER.map((id, idx) => {
              const isActive = idx === stepIndex;
              const isPast = idx < stepIndex;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setStepIndex(idx)}
                  aria-current={isActive ? "step" : undefined}
                  className={[
                    "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
                    isActive
                      ? "bg-background text-foreground shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
                      : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
                  ].join(" ")}
                >
                  <span
                    className={[
                      "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] transition-colors",
                      isActive
                        ? "bg-foreground text-background"
                        : isPast
                          ? "bg-foreground/85 text-background"
                          : "border-border/70 bg-background text-muted-foreground/70 border",
                    ].join(" ")}
                  >
                    {isPast ? (
                      <Check className="h-3 w-3" strokeWidth={2.5} />
                    ) : (
                      <span className="font-mono text-[9.5px] tracking-tight">
                        {idx + 1}
                      </span>
                    )}
                  </span>
                  <span className="text-[12.5px] font-medium tracking-tight">
                    {WIZARD_STEP_TITLES[id]}
                  </span>
                </button>
              );
            })}
          </nav>

          <div className="mt-auto pt-6">
            <div className="text-muted-foreground mb-2 flex items-center justify-between font-mono text-[9.5px] tracking-[0.22em] uppercase">
              <span>Framsteg</span>
              <span className="text-foreground">{completion}%</span>
            </div>
            <div className="bg-border/50 h-[3px] w-full overflow-hidden rounded-full">
              <div
                className="bg-foreground h-full rounded-full transition-[width] duration-300 ease-out"
                style={{ width: `${completion}%` }}
              />
            </div>
          </div>
        </aside>

        {/* Mobil-fallback för sidebar: branding + chip-rad. */}
        <div className="border-border/50 bg-muted/30 flex items-center justify-between gap-4 border-b px-5 py-3 md:hidden">
          <div className="flex items-center gap-2.5">
            <Image
              src="/LOGO_SM2.0.png"
              alt="Sajtmaskin"
              width={22}
              height={22}
              priority
              className="size-[22px] rounded-md object-contain"
            />
            <span className="text-[12px] font-semibold tracking-tight">
              Discovery
            </span>
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {WIZARD_STEP_ORDER.map((id, idx) => {
              const isActive = idx === stepIndex;
              const isPast = idx < stepIndex;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setStepIndex(idx)}
                  className={[
                    "inline-flex h-5 w-5 items-center justify-center rounded-full font-mono text-[9.5px] transition-colors",
                    isActive || isPast
                      ? "bg-foreground text-background"
                      : "text-muted-foreground ring-border/70 bg-transparent ring-1",
                  ].join(" ")}
                  aria-label={`Steg ${idx + 1}`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>
        </div>

        {/* Höger spalt — eyebrow, rubrik, beskrivning, formulär. */}
        <section className="bg-background relative flex min-h-0 flex-col">
          {/* Egen close-knapp i ljus content area så den inte krockar
              med den mörka sidebarn. */}
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Stäng"
            className="text-muted-foreground hover:bg-foreground/5 hover:text-foreground absolute top-4 right-4 z-10 inline-flex h-8 w-8 items-center justify-center rounded-full transition-colors"
          >
            <X className="h-4 w-4" />
          </button>

          <DialogHeader className="space-y-3 px-10 pt-10 pb-7 text-left">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="bg-foreground/[0.04] text-foreground/70 inline-flex items-center gap-2 rounded-full px-2.5 py-1 font-mono text-[9.5px] font-medium tracking-[0.2em] uppercase">
                {meta.eyebrow}
              </span>
              <span
                title="Pipeline-del som detta steg primärt styr"
                className="bg-foreground text-background inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[9px] font-semibold tracking-[0.18em] uppercase"
              >
                {WIZARD_STEP_PIPELINE_BADGE[step]}
              </span>
            </div>
            <DialogTitle className="text-foreground text-[28px] leading-[1.15] font-semibold tracking-tight">
              {WIZARD_STEP_TITLES[step]}
            </DialogTitle>
            <DialogDescription className="text-muted-foreground max-w-xl text-[13.5px] leading-relaxed">
              {meta.description}
            </DialogDescription>
          </DialogHeader>

          <div className="bg-border/50 h-px w-full" aria-hidden />

          <div className="flex-1 overflow-y-auto px-10 py-8">
            <div className="mx-auto max-w-2xl">
              {step === "foundation" ? (
                <FoundationStep
                  answers={answers}
                  onChange={updateAnswers}
                  options={discoveryOptions}
                  source={discoveryOptionsState.source}
                  onScrapeStateChange={setScrapeState}
                />
              ) : null}
              {step === "visual" ? (
                <VisualStep answers={answers} onChange={updateAnswers} />
              ) : null}
              {step === "functions" ? (
                <FunctionsStep answers={answers} onChange={updateAnswers} />
              ) : null}
              {step === "content" ? (
                <ContentOrchestratorStep
                  answers={answers}
                  onChange={updateAnswers}
                  branch={branch}
                />
              ) : null}
              {step === "media" ? (
                <>
                  <MediaStep answers={answers} onChange={updateAnswers} />
                  {/* Sista-steget transparens-block: visar exakt vilka
                      directives backend kommer att läsa baserat på alla
                      svar. Hjälper operatören förstå om något fält
                      "fattas" innan de klickar Skapa sajt. */}
                  <DirectivesPreview
                    answers={answers}
                    rawPrompt={initialPrompt}
                  />
                </>
              ) : null}
            </div>
          </div>

          {/* Footer — strikt, hög kontrast på primärknappen. */}
          <div className="border-border/60 bg-background/95 flex items-center justify-between gap-3 border-t px-6 py-4">
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={isFirst}
                onClick={goBack}
                className="text-muted-foreground hover:text-foreground h-9 px-3 text-[12.5px] font-medium"
              >
                ← Tillbaka
              </Button>
              {/* Demo-knapp för utveckling. Roterar genom DEMO_PROFILES
                  så operatören kan testa varje content-branch utan att
                  skriva igenom alla 7 stegen. Dämpad ghost-stil med
                  Sparkles-ikon — utan att konkurrera visuellt med
                  primärknappen "Skapa sajt". */}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={fillDemo}
                className="text-muted-foreground hover:text-foreground h-9 gap-1.5 px-2.5 text-[12px] font-medium"
                title="Fyll wizarden med en demo-profil för snabb testning"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Fyll demo
              </Button>
              {demoNotice ? (
                <span
                  role="status"
                  aria-live="polite"
                  className="hidden items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-700 sm:inline-flex dark:bg-emerald-400/10 dark:text-emerald-300"
                >
                  <Check className="h-3 w-3" strokeWidth={2.5} />
                  {demoNotice}
                </span>
              ) : null}
            </div>

            <div className="flex flex-1 items-center justify-end gap-2.5">
              {validationError ? (
                <span
                  className="hidden items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-700 sm:inline-flex dark:bg-amber-400/10 dark:text-amber-300"
                  role="status"
                >
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500"
                    aria-hidden
                  />
                  {validationError}
                </span>
              ) : null}
              {canSkip ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={skipStep}
                  className="text-muted-foreground hover:text-foreground h-9 px-3 text-[12.5px] font-medium"
                >
                  Hoppa över
                </Button>
              ) : null}
              {isLast ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={finish}
                  disabled={!!validationError}
                  className="bg-foreground text-background hover:bg-foreground/90 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm disabled:opacity-40"
                  title="⌘↵ för att skapa sajten"
                >
                  Skapa sajt →
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={goNext}
                  disabled={!!validationError}
                  className="bg-foreground text-background hover:bg-foreground/90 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm disabled:opacity-40"
                  title="⌘↵ för att fortsätta"
                >
                  Fortsätt →
                </Button>
              )}
              <span className="text-muted-foreground hidden text-[10px] sm:inline">
                ⌘↵
              </span>
            </div>
          </div>
        </section>

        {/* Scrape-overlay — täcker hela popupen så operatören tydligt
            ser att wizardens fält håller på att fyllas i automatiskt
            från den angivna URL:en. Stänger blocking-läge så fort
            POST /api/scrape-site returnerar (status === "ok" | "error").
        */}
        {isScraping ? (
          <div
            role="status"
            aria-live="polite"
            className="bg-background/80 absolute inset-0 z-50 flex items-center justify-center backdrop-blur-sm sm:rounded-3xl"
          >
            <div className="flex max-w-sm flex-col items-center gap-5 px-8 text-center">
              <div className="relative inline-flex h-14 w-14 items-center justify-center">
                <span
                  className="border-border/40 absolute inset-0 rounded-full border"
                  aria-hidden
                />
                <span
                  className="bg-foreground/5 absolute inset-0 animate-ping rounded-full"
                  aria-hidden
                />
                <Loader2 className="text-foreground relative h-6 w-6 animate-spin" />
              </div>
              <div className="space-y-1.5">
                <p className="text-muted-foreground font-mono text-[10px] tracking-[0.22em] uppercase">
                  Hämtar din hemsida
                </p>
                <p className="text-foreground text-[15px] leading-tight font-medium tracking-tight">
                  {scrapeState?.url ?? "Läser innehåll…"}
                </p>
                <p className="text-muted-foreground text-[12px]">
                  Vi läser sidan och fyller i fält automatiskt. Detta tar
                  vanligtvis 15–60 sekunder beroende på sajtens storlek.
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
