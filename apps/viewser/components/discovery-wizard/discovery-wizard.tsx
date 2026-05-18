"use client";

import { Check, Loader2, X } from "lucide-react";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { AssetsStep } from "./steps/assets-step";
import { BrandStep } from "./steps/brand-step";
import { CompanyStep, type ScrapeState } from "./steps/company-step";
import { ContentStep } from "./steps/content-step";
import { PagesStep } from "./steps/pages-step";
import { SiteTypeStep } from "./steps/site-type-step";
import { StoryStep } from "./steps/story-step";
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

const SKIPPABLE_STEPS = new Set<WizardStepId>([
  "content",
  "story",
  "assets",
  "brand",
]);

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
  company: {
    eyebrow: "Identitet",
    description:
      "Vem ni är och hur vi når er. Klistra in en befintlig URL så hämtar vi resten automatiskt.",
  },
  siteType: {
    eyebrow: "Kategori",
    description:
      "Välj vilken typ av sajt vi bygger. Det styr scaffold, sidor och vilka frågor du får härnäst.",
  },
  content: {
    eyebrow: "Innehåll",
    description:
      "Tjänster, produkter, menyer eller projekt — det konkreta innehållet som ska synas på sajten.",
  },
  story: {
    eyebrow: "Berättelse",
    description:
      "Bakgrund, vision och tonen i texten. Det vi inte hittar här hittar vi inte alls.",
  },
  pages: {
    eyebrow: "Sidor",
    description:
      "Vilka sidor sajten ska ha, vilken målgrupp ni vänder er till och vad ni vill att besökarna gör.",
  },
  assets: {
    eyebrow: "Visuellt",
    description:
      "Logotyp, hero-bild och galleri. AI:n föreslår placering — du har sista ordet.",
  },
  brand: {
    eyebrow: "Stil",
    description:
      "Tonarter, färger och ord vi ska undvika. Här finjusterar du sajtens röst.",
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

  const finish = useCallback(() => {
    if (validationError) return;
    onComplete(answers, discoveryOptions);
  }, [answers, discoveryOptions, onComplete, validationError]);

  const isFirst = stepIndex === 0;
  const isLast = stepIndex === WIZARD_STEP_ORDER.length - 1;
  const canSkip = SKIPPABLE_STEPS.has(step);

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
        const payload = (await response.json()) as { options?: discoveryOption[] };
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
        className="!w-[min(100vw-2rem,1180px)] !max-w-[min(100vw-2rem,1180px)] grid h-[min(100dvh-2rem,780px)] grid-cols-1 gap-0 overflow-hidden border border-border/60 bg-background p-0 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] sm:!max-w-[min(100vw-2rem,1180px)] sm:rounded-3xl md:grid-cols-[280px_1fr] md:grid-rows-1"
        showCloseButton={false}
      >
        {/* Sidebar — ljus minimalistisk panel. Tunn höger-border ger
            visuell separation utan att skapa kontrast-brus. */}
        <aside className="hidden flex-col border-r border-border/50 bg-muted/30 px-6 py-7 md:flex">
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
              <span className="text-[13px] font-semibold tracking-tight text-foreground">
                Sajtbyggaren
              </span>
              <span className="font-mono text-[9.5px] uppercase tracking-[0.22em] text-muted-foreground">
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
                          : "border border-border/70 bg-background text-muted-foreground/70",
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
            <div className="mb-2 flex items-center justify-between font-mono text-[9.5px] uppercase tracking-[0.22em] text-muted-foreground">
              <span>Framsteg</span>
              <span className="text-foreground">{completion}%</span>
            </div>
            <div className="h-[3px] w-full overflow-hidden rounded-full bg-border/50">
              <div
                className="h-full rounded-full bg-foreground transition-[width] duration-300 ease-out"
                style={{ width: `${completion}%` }}
              />
            </div>
          </div>
        </aside>

        {/* Mobil-fallback för sidebar: branding + chip-rad. */}
        <div className="flex items-center justify-between gap-4 border-b border-border/50 bg-muted/30 px-5 py-3 md:hidden">
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
                      : "bg-transparent text-muted-foreground ring-1 ring-border/70",
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
        <section className="relative flex min-h-0 flex-col bg-background">
          {/* Egen close-knapp i ljus content area så den inte krockar
              med den mörka sidebarn. */}
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            aria-label="Stäng"
            className="absolute top-4 right-4 z-10 inline-flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>

          <DialogHeader className="space-y-3 px-10 pt-10 pb-7 text-left">
            <span className="inline-flex w-fit items-center gap-2 rounded-full bg-foreground/[0.04] px-2.5 py-1 font-mono text-[9.5px] font-medium uppercase tracking-[0.2em] text-foreground/70">
              {meta.eyebrow}
            </span>
            <DialogTitle className="text-[28px] font-semibold leading-[1.15] tracking-tight text-foreground">
              {WIZARD_STEP_TITLES[step]}
            </DialogTitle>
            <DialogDescription className="max-w-xl text-[13.5px] leading-relaxed text-muted-foreground">
              {meta.description}
            </DialogDescription>
          </DialogHeader>

          <div className="h-px w-full bg-border/50" aria-hidden />

          <div className="flex-1 overflow-y-auto px-10 py-8">
            <div className="mx-auto max-w-2xl">
              {step === "company" ? (
                <CompanyStep
                  answers={answers}
                  onChange={updateAnswers}
                  onScrapeStateChange={setScrapeState}
                />
              ) : null}
              {step === "siteType" ? (
                <SiteTypeStep
                  answers={answers}
                  onChange={updateAnswers}
                  options={discoveryOptions}
                  source={discoveryOptionsState.source}
                />
              ) : null}
              {step === "content" ? (
                <ContentStep
                  answers={answers}
                  onChange={updateAnswers}
                  branch={branch}
                />
              ) : null}
              {step === "story" ? (
                <StoryStep answers={answers} onChange={updateAnswers} />
              ) : null}
              {step === "pages" ? (
                <PagesStep answers={answers} onChange={updateAnswers} />
              ) : null}
              {step === "assets" ? (
                <AssetsStep answers={answers} onChange={updateAnswers} />
              ) : null}
              {step === "brand" ? (
                <BrandStep answers={answers} onChange={updateAnswers} />
              ) : null}
            </div>
          </div>

          {/* Footer — strikt, hög kontrast på primärknappen. */}
          <div className="flex items-center justify-between gap-3 border-t border-border/60 bg-background/95 px-6 py-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isFirst}
              onClick={goBack}
              className="h-9 px-3 text-[12.5px] font-medium text-muted-foreground hover:text-foreground"
            >
              ← Tillbaka
            </Button>

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
                  className="h-9 px-3 text-[12.5px] font-medium text-muted-foreground hover:text-foreground"
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
                  className="h-9 rounded-full bg-foreground px-5 text-[12.5px] font-medium text-background shadow-sm hover:bg-foreground/90 disabled:opacity-40"
                >
                  Skapa sajt →
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={goNext}
                  disabled={!!validationError}
                  className="h-9 rounded-full bg-foreground px-5 text-[12.5px] font-medium text-background shadow-sm hover:bg-foreground/90 disabled:opacity-40"
                >
                  Fortsätt →
                </Button>
              )}
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
            className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm sm:rounded-3xl"
          >
            <div className="flex max-w-sm flex-col items-center gap-5 px-8 text-center">
              <div className="relative inline-flex h-14 w-14 items-center justify-center">
                <span
                  className="absolute inset-0 rounded-full border border-border/40"
                  aria-hidden
                />
                <span
                  className="absolute inset-0 animate-ping rounded-full bg-foreground/5"
                  aria-hidden
                />
                <Loader2 className="relative h-6 w-6 animate-spin text-foreground" />
              </div>
              <div className="space-y-1.5">
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                  Hämtar din hemsida
                </p>
                <p className="text-[15px] font-medium leading-tight tracking-tight text-foreground">
                  {scrapeState?.url ?? "Läser innehåll…"}
                </p>
                <p className="text-[12px] text-muted-foreground">
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
