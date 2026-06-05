"use client";

import {
  Check,
  Keyboard,
  Loader2,
  MoreHorizontal,
  Phone,
  Sparkles,
  X,
} from "lucide-react";
import Image from "next/image";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { PRIMARY_INTERACTIONS } from "@/lib/ui-tokens";

import { DEMO_PROFILES } from "./demo-answers";
import { MoreInfoDialog, type MoreInfoTabId } from "./more-info-dialog";
import { AssetsStep } from "./steps/assets-step";
import { FoundationStep, type ScrapeState } from "./steps/foundation-step";
import { FunctionsStep } from "./steps/functions-step";
import { VisualStep } from "./steps/visual-step";
import {
  fallbackDiscoveryOptions,
  resolveContentBranchFromOptions,
} from "./discovery-options";
import type { discoveryOption } from "./discovery-options";
import { branchForFamily } from "./wizard-constants";
import type { WizardAnswers } from "./wizard-types";
import {
  emptyWizardAnswers,
  validateWizardStep,
  WIZARD_STEP_ORDER,
  WIZARD_STEP_TITLES,
} from "./wizard-types";

/**
 * Discovery wizard — total-minimalism-passet (2026-05-26,
 * GAP-viewser-wizard-minimal-tabs).
 *
 * Tre tabs högst upp: Företaget / Stil / Funktioner. Innehåll och
 * Media-fält finns kvar men ligger bakom "Mer information"-popup på
 * tab 3 så default-vyn hålls superminimalistisk.
 *
 * URL-skrap på tab 1 fyller alla fält (inkl. content + media-stubbar)
 * automatiskt i bakgrunden — operatorn behöver inte se eller godkänna
 * texterna. Om hen vill granska/redigera finns det i popupen.
 *
 * Tre lager av text/feedback:
 *   1. Synlig som default: tab-labels + minimum-required-fields på varje tab.
 *   2. Visas bara vid fel: validation-pill i footern.
 *   3. Öppnas på begäran: tangentbordsgenvags-overlay (?) + Mer information-popup.
 *
 * Backend-payload är INTE ändrad — vi skickar samma `WizardAnswers`-struct
 * till `/api/prompt` via `buildDiscoveryPayload`.
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

type discoveryOptionsState = {
  options: discoveryOption[];
  source: "governance" | "fallback";
};

const KEYBOARD_SHORTCUTS: ReadonlyArray<{
  label: string;
  keys: ReadonlyArray<string>;
}> = [
  { label: "Fortsätt till nästa steg", keys: ["⌘↵", "⌘→"] },
  { label: "Gå tillbaka", keys: ["⌘←"] },
  { label: "Hoppa till ett steg", keys: ["⌥1", "⌥2", "⌥3", "⌥4"] },
  { label: "Visa/dölj denna lista", keys: ["?", "⌘/"] },
  { label: "Stäng wizarden", keys: ["esc"] },
];

export function DiscoveryWizard({
  open,
  onOpenChange,
  initialPrompt,
  initialAnswers,
  onComplete,
}: DiscoveryWizardProps) {
  const [answers, setAnswers] = useState<WizardAnswers>(() => {
    const base = initialAnswers ?? emptyWizardAnswers();
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
  const [scrapeState, setScrapeState] = useState<ScrapeState | null>(null);
  const [moreInfoOpen, setMoreInfoOpen] = useState(false);
  const [moreInfoTab, setMoreInfoTab] = useState<MoreInfoTabId>("about");

  // Öppnar "Mer information"-popupen på en specifik flik. Telefon-nudgen
  // på sista steget djuplänkar till "contact" så operatören slipper leta
  // upp Kontakt-fliken själv; den vanliga knappen öppnar på "about".
  const openMoreInfo = useCallback((tab: MoreInfoTabId = "about") => {
    setMoreInfoTab(tab);
    setMoreInfoOpen(true);
  }, []);

  const demoCursorRef = useRef(0);
  const [demoNotice, setDemoNotice] = useState<string | null>(null);
  const demoNoticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const step = WIZARD_STEP_ORDER[stepIndex];
  const discoveryOptions = discoveryOptionsState.options;
  const branch = useMemo(
    () =>
      resolveContentBranchFromOptions(
        answers.siteType,
        discoveryOptions,
        answers.businessFamily ? branchForFamily(answers.businessFamily) : undefined,
      ),
    [answers.siteType, answers.businessFamily, discoveryOptions],
  );
  const validationError = useMemo(
    () => validateWizardStep(step, answers, branch),
    [step, answers, branch],
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

  const goToStep = useCallback((targetIdx: number) => {
    setStepIndex(
      Math.min(
        WIZARD_STEP_ORDER.length - 1,
        Math.max(0, Math.floor(targetIdx)),
      ),
    );
  }, []);

  const [helpOpen, setHelpOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submittingRef = useRef(false);
  // Submit-overlayn väntar 700 ms innan onComplete (bygg-start) körs. Spara
  // timern så vi kan avbryta den om operatören stänger wizarden (Esc) under
  // väntan — annars startade ett bygge efter att hen backat ut.
  const submitTimerRef = useRef<number | null>(null);

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
      if (submitTimerRef.current !== null) {
        clearTimeout(submitTimerRef.current);
        submitTimerRef.current = null;
      }
    };
  }, []);

  // När wizarden stängs (Esc/klick på X) nollställer vi submitting-state.
  // Render-time-justering (i st.f. effect) undviker React 19:s
  // ``set-state-in-effect``-varning, precis som i more-info-dialog.tsx.
  // Inga refs rörs här — ``react-hooks/refs`` förbjuder ref-access i render;
  // timer-avbrott + ref-nollställning sker i effekten nedan.
  const [wizardWasOpen, setWizardWasOpen] = useState(open);
  if (open !== wizardWasOpen) {
    setWizardWasOpen(open);
    if (!open) setIsSubmitting(false);
  }

  // Avbryt en pågående submit-timer när wizarden stängs så 700 ms-timern
  // inte fyrar av onComplete (bygg-start) efter att operatören backat ut.
  // Refs får läsas/skrivas i effekter (men inte i render).
  useEffect(() => {
    if (open) return;
    if (submitTimerRef.current !== null) {
      clearTimeout(submitTimerRef.current);
      submitTimerRef.current = null;
    }
    submittingRef.current = false;
  }, [open]);

  const finish = useCallback(() => {
    if (submittingRef.current || isSubmitting) return;
    for (const stepId of WIZARD_STEP_ORDER) {
      const err = validateWizardStep(stepId, answers, branch);
      if (err) {
        const idx = WIZARD_STEP_ORDER.indexOf(stepId);
        if (idx !== -1) setStepIndex(idx);
        return;
      }
    }
    submittingRef.current = true;
    setIsSubmitting(true);
    submitTimerRef.current = window.setTimeout(() => {
      submitTimerRef.current = null;
      onComplete(answers, discoveryOptions);
    }, 700);
  }, [answers, branch, discoveryOptions, isSubmitting, onComplete]);

  const isFirst = stepIndex === 0;
  const isLast = stepIndex === WIZARD_STEP_ORDER.length - 1;

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const isMod = event.metaKey || event.ctrlKey;
      const target = event.target as HTMLElement | null;
      const inEditable =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);

      if (isMod && (event.key === "Enter" || event.key === "ArrowRight")) {
        if (inEditable) return;
        event.preventDefault();
        if (isLast) finish();
        else goNext();
        return;
      }
      if (isMod && event.key === "ArrowLeft") {
        if (inEditable) return;
        event.preventDefault();
        goBack();
        return;
      }
      // Steg-hopp via ⌥ (Alt) + siffra, INTE ⌘/Ctrl: Cmd+siffra (Mac) och
      // Ctrl+siffra (Win/Linux) är webbläsarens egna flik-genvägar och
      // preventDefault hinner sällan före — operatören trodde sig hoppa
      // steg men bytte webbläsarflik. Option+siffra ger specialtecken på
      // Mac så vi matchar på event.code (Digit1–Digit9), inte event.key.
      if (
        event.altKey &&
        !event.metaKey &&
        !event.ctrlKey &&
        !inEditable &&
        /^Digit[1-9]$/.test(event.code)
      ) {
        const num = parseInt(event.code.slice(5), 10);
        if (num >= 1 && num <= WIZARD_STEP_ORDER.length) {
          event.preventDefault();
          goToStep(num - 1);
          return;
        }
      }
      if (
        ((isMod && event.key === "/") || event.key === "?") &&
        !inEditable
      ) {
        event.preventDefault();
        setHelpOpen((prev) => !prev);
        return;
      }
      if (event.key === "Escape" && helpOpen) {
        event.preventDefault();
        event.stopPropagation();
        setHelpOpen(false);
        return;
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, isLast, goNext, goBack, finish, goToStep, helpOpen]);

  const isScraping = scrapeState?.status === "loading";

  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    if (typeof window === "undefined") return;
    if (window.innerWidth < 768) return;
    const raf = requestAnimationFrame(() => {
      const root = contentRef.current;
      if (!root) return;
      const candidate = root.querySelector<HTMLElement>(
        'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), [role="button"]:not([disabled]), button:not([disabled])',
      );
      if (candidate && document.activeElement === document.body) {
        candidate.focus({ preventScroll: true });
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [open, stepIndex]);

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
        className="border-border/60 bg-background grid h-[min(100dvh-2rem,780px)] !w-[min(100vw-2rem,1080px)] !max-w-[min(100vw-2rem,1080px)] grid-rows-[auto_auto_1fr_auto] gap-0 overflow-hidden border p-0 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] sm:!max-w-[min(100vw-2rem,1080px)] sm:rounded-3xl"
        showCloseButton={false}
      >
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Stäng"
          className="text-muted-foreground hover:bg-foreground/5 hover:text-foreground min-tap sm:min-tap-0 absolute top-3 right-3 z-10 inline-flex items-center justify-center rounded-full transition-colors active:scale-95 sm:top-4 sm:right-4 sm:h-8 sm:w-8"
        >
          <X className="h-4 w-4" />
        </button>

        <DialogHeader className="space-y-0 px-5 pt-5 pb-3 text-left sm:px-8 sm:pt-6 sm:pb-3">
          <div className="flex items-center gap-3">
            <Image
              src="/sajtbyggaren_logo.png"
              alt="Sajtbyggaren"
              width={115}
              height={28}
              priority
              // Se site-header.tsx: style.width auto bevarar aspect-ratio
              // och tystar Next:s aspect-ratio-varning (B160).
              style={{ width: "auto" }}
              className="h-7 w-auto object-contain"
            />
            <DialogTitle className="sr-only">Sajtbyggaren</DialogTitle>
            <DialogDescription className="text-muted-foreground/70 hidden text-[11.5px] leading-relaxed sm:inline">
              Bygger en personlig hemsida åt dig på några frågor.
            </DialogDescription>
          </div>
        </DialogHeader>

        <div
          role="tablist"
          aria-label="Steg i guiden"
          className="border-border/60 flex w-full items-stretch gap-0 border-b px-5 sm:justify-center sm:gap-1 sm:px-8"
        >
          {WIZARD_STEP_ORDER.map((id, idx) => {
            const isActive = idx === stepIndex;
            const isPast = idx < stepIndex;
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-current={isActive ? "step" : undefined}
                aria-selected={isActive}
                onClick={() => setStepIndex(idx)}
                className={[
                  "min-tap sm:min-tap-0 relative -mb-px inline-flex flex-1 items-center justify-center gap-1.5 border-b-2 px-3 py-2.5 text-[12.5px] font-medium tracking-tight transition-colors sm:flex-none sm:px-5",
                  isActive
                    ? "text-foreground border-foreground"
                    : "text-muted-foreground hover:text-foreground border-transparent",
                ].join(" ")}
              >
                <span
                  className={[
                    "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9.5px] font-mono transition-colors",
                    isActive
                      ? "bg-foreground text-background"
                      : isPast
                        ? "bg-foreground/85 text-background"
                        : "border-border/70 bg-background text-muted-foreground/70 border",
                  ].join(" ")}
                >
                  {isPast ? (
                    <Check className="h-2.5 w-2.5" strokeWidth={2.5} />
                  ) : (
                    idx + 1
                  )}
                </span>
                <span className="truncate">{WIZARD_STEP_TITLES[id]}</span>
              </button>
            );
          })}
        </div>

        <section className="bg-background relative flex min-h-0 flex-col overflow-hidden">
          <div
            ref={contentRef}
            className="flex-1 overflow-y-auto px-5 py-6 sm:px-10 sm:py-8"
          >
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
              {step === "assets" ? (
                <>
                  {/* Logo + mediamaterial — egen tab så det blir tydligt
                      att uppladdning är ett separat steg. Vision-modellen
                      pickar bästa hero/galleribild från det operatorn
                      laddar upp här (favicon / OG / bakgrundsvideo ligger
                      kvar i Mer information-popupen). */}
                  <AssetsStep answers={answers} onChange={updateAnswers} />

                  {/* Telefon-nudge: utan ett riktigt nummer döljer backend
                      (B158/B159) kontaktfältet publikt och visar en allmän
                      "Hör av dig"-knapp i stället — sajten får alltså ingen
                      telefon/Ring-knapp. Vi nudgar bara när fältet är tomt
                      (skrapning fyller det automatiskt annars) och
                      djuplänkar direkt till Kontakt-fliken så operatören
                      inte behöver leta. Ren UI/UX — payloaden är oförändrad. */}
                  {!answers.contact.phone.trim() ? (
                    <div className="mt-8 flex flex-col gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] p-4 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-2.5">
                        <Phone
                          className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400"
                          aria-hidden
                        />
                        <div className="space-y-0.5">
                          <p className="text-foreground text-[12.5px] leading-tight font-medium">
                            Inget telefonnummer angivet
                          </p>
                          <p className="text-muted-foreground text-[11.5px] leading-relaxed">
                            Utan nummer får sajten ingen Ring-knapp — besökarna ser bara en allmän kontaktknapp. Lägg till ditt riktiga nummer så når kunderna er direkt.
                          </p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => openMoreInfo("contact")}
                        className="min-tap sm:min-tap-0 h-9 shrink-0 rounded-full border border-amber-500/40 px-4 text-[12px] font-medium text-amber-700 hover:bg-amber-500/10 dark:text-amber-300"
                      >
                        Lägg till nummer
                      </Button>
                    </div>
                  ) : null}

                  {/* "Mer information"-knappen flyttades hit från tab 3
                      eftersom Bilder nu är sista tabben — knappen syns
                      precis innan "Skapa sajt", vilket var operatorens
                      ursprungliga önskemål. */}
                  <div className="border-border/40 mt-8 border-t pt-6">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => openMoreInfo("about")}
                      className="text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04] min-tap sm:min-tap-0 inline-flex h-9 items-center gap-2 rounded-full border border-dashed border-current/40 px-4 text-[12.5px] font-medium"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" aria-hidden />
                      Ange information till hemsidan
                    </Button>
                    <p className="text-muted-foreground/70 mt-2 text-[11.5px] leading-relaxed">
                      Innehåll, kontaktuppgifter, favicon och fler detaljer — fylls i automatiskt vid skrapning, men du kan granska eller komplettera här.
                    </p>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </section>

        <div className="border-border/60 bg-background/95 flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 pb-safe-or-4 sm:px-6 sm:py-4">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isFirst}
              onClick={goBack}
              className="text-muted-foreground hover:text-foreground min-tap sm:min-tap-0 h-9 px-3 text-[12.5px] font-medium"
            >
              ← Tillbaka
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={fillDemo}
              aria-label="Fyll wizarden med en demo-profil"
              className="text-muted-foreground/50 hover:text-foreground hidden h-8 w-8 items-center justify-center p-0 sm:inline-flex"
              title="Fyll wizarden med en demo-profil för snabb testning"
            >
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
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
                className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-700 dark:bg-amber-400/10 dark:text-amber-300"
                role="status"
              >
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500"
                  aria-hidden
                />
                {validationError}
              </span>
            ) : null}
            {isLast ? (
              <Button
                type="button"
                size="sm"
                onClick={finish}
                disabled={!!validationError || isSubmitting}
                className={[
                  "bg-foreground text-background hover:bg-foreground/90 min-tap sm:min-tap-0 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm disabled:opacity-40",
                  PRIMARY_INTERACTIONS,
                ].join(" ")}
                title="⌘↵ för att skapa sajten"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Påbörjar bygge…
                  </>
                ) : (
                  "Skapa sajt →"
                )}
              </Button>
            ) : (
              <Button
                type="button"
                size="sm"
                onClick={goNext}
                disabled={!!validationError}
                className={[
                  "bg-foreground text-background hover:bg-foreground/90 min-tap sm:min-tap-0 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm disabled:opacity-40",
                  PRIMARY_INTERACTIONS,
                ].join(" ")}
                title="⌘↵ för att fortsätta"
              >
                Fortsätt →
              </Button>
            )}
            <button
              type="button"
              onClick={() => setHelpOpen((prev) => !prev)}
              aria-label="Visa tangentbordsgenvägar"
              title="Tangentbordsgenvägar (?)"
              // Tidigare ``hidden sm:inline-flex`` dolde hjälpen helt på
              // smal viewport (t.ex. iPad i porträtt med tangentbord). Nu
              // alltid synlig; ``min-tap`` ger ett 44px tap-target på mobil
              // medan ikonen behåller sin diskreta 28px-yta på desktop.
              className="text-muted-foreground/50 hover:text-foreground hover:bg-foreground/[0.04] focus-visible:ring-ring/40 min-tap sm:min-tap-0 inline-flex h-7 w-7 items-center justify-center rounded-md transition-colors focus-visible:ring-2 focus-visible:outline-none"
            >
              <Keyboard className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        </div>

        {helpOpen ? (
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Tangentbordsgenvägar"
            className="bg-background/85 absolute inset-0 z-40 flex items-center justify-center p-6 backdrop-blur-sm sm:rounded-3xl"
            onClick={(event) => {
              if (event.target === event.currentTarget) {
                setHelpOpen(false);
              }
            }}
          >
            <div className="bg-card border-border/70 w-full max-w-md overflow-hidden rounded-2xl border shadow-2xl">
              <div className="border-border/60 flex items-center justify-between border-b px-5 py-3">
                <div className="flex items-center gap-2">
                  <Keyboard className="text-foreground/70 h-4 w-4" />
                  <h3 className="text-foreground text-[14px] font-semibold tracking-tight">
                    Tangentbordsgenvägar
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setHelpOpen(false)}
                  aria-label="Stäng"
                  className="text-muted-foreground hover:text-foreground rounded-md p-1 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <dl className="divide-border/40 flex flex-col divide-y">
                {KEYBOARD_SHORTCUTS.map((shortcut) => (
                  <div
                    key={shortcut.label}
                    className="flex items-center justify-between gap-4 px-5 py-2.5"
                  >
                    <dt className="text-foreground/85 text-[12.5px]">
                      {shortcut.label}
                    </dt>
                    <dd className="flex shrink-0 items-center gap-1">
                      {shortcut.keys.map((key, idx) => (
                        <span key={`${shortcut.label}-${idx}`} className="contents">
                          {idx > 0 ? (
                            <span className="text-muted-foreground text-[10px]">
                              eller
                            </span>
                          ) : null}
                          <kbd className="border-border/60 bg-background text-foreground/80 inline-flex h-5 min-w-5 items-center justify-center rounded border px-1.5 font-mono text-[10.5px]">
                            {key}
                          </kbd>
                        </span>
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        ) : null}

        {isSubmitting ? (
          <div
            role="status"
            aria-live="polite"
            className="bg-background/85 absolute inset-0 z-50 flex items-center justify-center backdrop-blur-sm sm:rounded-3xl"
          >
            <div className="flex max-w-sm flex-col items-center gap-5 px-8 text-center">
              <div className="relative inline-flex h-14 w-14 items-center justify-center">
                <span
                  className="border-emerald-500/40 absolute inset-0 rounded-full border-2 motion-safe:animate-ping"
                  aria-hidden
                />
                <span className="bg-emerald-500/15 absolute inset-2 rounded-full" aria-hidden />
                <Check
                  className="relative h-6 w-6 text-emerald-600 dark:text-emerald-400"
                  strokeWidth={3}
                />
              </div>
              <div className="space-y-1.5">
                <p className="text-foreground text-[16px] leading-tight font-semibold tracking-tight">
                  Påbörjar bygge av din sajt…
                </p>
                <p className="text-muted-foreground text-[12px]">
                  Vi läser dina svar, planerar sidorna och bygger sajten.
                </p>
              </div>
            </div>
          </div>
        ) : null}

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
                <p className="text-foreground text-[15px] leading-tight font-medium tracking-tight">
                  Hämtar innehåll från {scrapeState?.url ?? "din hemsida"}…
                </p>
                <p className="text-muted-foreground text-[12px]">
                  Vi läser sidan och fyller i fält automatiskt.
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>

      <MoreInfoDialog
        open={moreInfoOpen}
        onOpenChange={setMoreInfoOpen}
        answers={answers}
        onChange={updateAnswers}
        branch={branch}
        initialTab={moreInfoTab}
      />
    </Dialog>
  );
}
