"use client";

import { Check, Info, Keyboard, Loader2, Sparkles, X } from "lucide-react";
import Image from "next/image";
import {
  useCallback,
  useEffect,
  useId,
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
import { branchForFamily } from "./wizard-constants";
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
/**
 * Source-of-truth för hjälp-overlayens lista. Håll i synk med
 * keyboard-handlern i useEffect — om du lägger till en ny shortcut
 * där, lägg till en rad här också, annars upptäcker operatören den
 * aldrig via UI.
 *
 * `keys` är display-strängar (visas i `<kbd>`-element), inte event-
 * matchningar. ⌘ visas för operatörer; handlern matchar både
 * `metaKey` och `ctrlKey` så Windows/Linux fungerar med samma listing.
 */
const KEYBOARD_SHORTCUTS: ReadonlyArray<{
  label: string;
  keys: ReadonlyArray<string>;
}> = [
  { label: "Fortsätt till nästa steg", keys: ["⌘↵", "⌘→"] },
  { label: "Gå tillbaka", keys: ["⌘←"] },
  { label: "Hoppa till steg 1–5", keys: ["⌘1", "⌘2", "⌘3", "⌘4", "⌘5"] },
  { label: "Visa/dölj denna lista", keys: ["?", "⌘/"] },
  { label: "Stäng wizarden", keys: ["esc"] },
];

/**
 * STEP_META — `eyebrow` = kort kategori-pill ovanför rubriken.
 * `description` = en (1) mening som visas under titeln.
 * `descriptionLong` = valfri längre prosa som flyttas bakom en info-
 *   ikon på rubrik-raden så default-vyn förblir luftig och minimalistisk.
 */
const STEP_META: Record<
  WizardStepId,
  { eyebrow: string; description: string; descriptionLong?: string }
> = {
  foundation: {
    eyebrow: "Sidor",
    description: "Vem ni är och vilken typ av verksamhet.",
    descriptionLong:
      "Styr scaffold + starter (vilken Next.js-mall vi använder).",
  },
  visual: {
    eyebrow: "Visuellt",
    description: "Vibe, färger och typografi.",
    descriptionLong:
      "Styr variant (CSS-tokens) — färgerna kan skriva över vibens defaults.",
  },
  functions: {
    eyebrow: "Funktioner",
    description: "Vad ska sajten kunna göra?",
    descriptionLong:
      "Funktionerna styr Dossier-val och sid-routes på en gång.",
  },
  content: {
    eyebrow: "Innehåll",
    description: "Tjänster, produkter, story och ton.",
    descriptionLong:
      "Allt som matar copy och planner. Målgrupp lägger du bakom disclosure längre ner.",
  },
  media: {
    eyebrow: "Media",
    description: "Logotyp, hero och galleri.",
    descriptionLong:
      "Favicon, social-image och bakgrundsvideo finns bakom 'mer'-pilen. Sista steget innan vi bygger.",
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
    () =>
      resolveContentBranchFromOptions(
        answers.siteType,
        discoveryOptions,
        // W2 i scout-review 2026-05-24: fallback till familj-branch när
        // operatören valt familj men inte sub-kategori. Annars landar
        // t.ex. ecommerce-familjen i "business"-branchen och content-
        // steget visar fel fält.
        answers.businessFamily ? branchForFamily(answers.businessFamily) : undefined,
      ),
    [answers.siteType, answers.businessFamily, discoveryOptions],
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

  // Hopp direkt till specifikt steg via tangentbordsgenväg eller
  // sidebar-klick. Negativa eller out-of-range index normaliseras
  // tyst — vi vill aldrig att en stale shortcut kraschar wizarden.
  const goToStep = useCallback((targetIdx: number) => {
    setStepIndex(
      Math.min(
        WIZARD_STEP_ORDER.length - 1,
        Math.max(0, Math.floor(targetIdx)),
      ),
    );
  }, []);

  // Hjälp-overlay som listar alla tillgängliga genvägar. Toggle:as
  // av "?" eller Cmd+/ — operatören kan stänga med Esc eller klick.
  const [helpOpen, setHelpOpen] = useState(false);

  // Submit-flow state. När operatören klickar "Skapa sajt" visar vi
  // en kort success-overlay (~700ms) innan vi anropar onComplete så
  // operatören ser tydligt att klicket registrerats innan wizarden
  // försvinner. Utan delay:n stänger wizarden direkt och bygget tar
  // tid att starta — operatören kan undra om något hänt.
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Ref-baserad submit-guard så två snabba ⌘↵-events i samma tick
  // inte kan passera ``if (isSubmitting)`` båda två innan React
  // hunnit rendera om (W1 i scout-review 2026-05-24).
  const submittingRef = useRef(false);

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

  // B3+B4 i scout-review 2026-05-24: reset av wizard-state mellan
  // sessioner hanteras via ``key={wizardSession}`` i prompt-builder.
  // Komponenten remountas då naturligt och useState-initiering kör om,
  // istället för att vi triggar setState i en effect (vilket React 19:s
  // ``react-hooks/set-state-in-effect`` blockerar).

  const finish = useCallback(() => {
    if (submittingRef.current || isSubmitting) return;
    // Validera ALLA steg, inte bara aktiva — sidebar/keyboard kan
    // hoppa till sista steget och därmed kringgå required fields i
    // foundation/functions (B5 i scout-review 2026-05-24).
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
    window.setTimeout(() => {
      onComplete(answers, discoveryOptions);
    }, 700);
  }, [answers, branch, discoveryOptions, isSubmitting, onComplete]);

  const isFirst = stepIndex === 0;
  const isLast = stepIndex === WIZARD_STEP_ORDER.length - 1;
  const canSkip = SKIPPABLE_STEPS.has(step);

  /**
   * Globala wizard-keyboard-shortcuts. Aktiveras bara när wizarden är
   * öppen. esc stängs automatiskt av Radix Dialog så vi hanterar bara
   * de aktiva genvägarna här:
   *
   *   - ⌘↵ / Ctrl+↵        ⇒ goNext (eller finish på sista steget)
   *   - ⌘→ / Ctrl+→        ⇒ goNext
   *   - ⌘← / Ctrl+←        ⇒ goBack
   *   - ⌘1..⌘5 / Ctrl+1..5 ⇒ hoppa direkt till steget
   *   - ⌘/ / Ctrl+/ / ?    ⇒ toggla hjälp-overlayen
   *
   * Capture-fasen undviks så textarea/input-fält som har lokala
   * handlers (t.ex. cmd+enter för newline) får företräde. Vi lyssnar
   * på bubble-fasen och kollar att event inte redan är
   * defaultPrevented av en lokal handler.
   *
   * Numeric-shortcut:s blockeras när operatören skriver i ett input
   * eller textarea — annars skulle ⌘1 i ett namn-fält oavsiktligt
   * hoppa till första steget och förstöra hens text.
   */
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

      // ⌘↵ / ⌘→ — fortsätt. Hoppa över när operatören skriver i en
      // textarea eller input så ⌘↵ kan användas för newline / lokala
      // submit-handlers (W4 i scout-review 2026-05-24).
      if (isMod && (event.key === "Enter" || event.key === "ArrowRight")) {
        if (inEditable) return;
        event.preventDefault();
        if (isLast) finish();
        else goNext();
        return;
      }
      // ⌘← — tillbaka (blockerad i editable så markörnavigering fungerar)
      if (isMod && event.key === "ArrowLeft") {
        if (inEditable) return;
        event.preventDefault();
        goBack();
        return;
      }
      // ⌘1..⌘5 — hoppa till steg (blockerad i editable fält)
      if (isMod && /^[1-9]$/.test(event.key) && !inEditable) {
        const num = parseInt(event.key, 10);
        if (num >= 1 && num <= WIZARD_STEP_ORDER.length) {
          event.preventDefault();
          goToStep(num - 1);
          return;
        }
      }
      // ? eller ⌘/ — toggla hjälp-overlay
      if ((isMod && event.key === "/") || (event.key === "?" && !inEditable)) {
        event.preventDefault();
        setHelpOpen((prev) => !prev);
        return;
      }
      // Esc inom hjälp-overlay stänger den (Radix Dialog hanterar
      // huvud-dialogen). Vi prioriterar att stänga overlay först om
      // den är öppen så Esc inte stänger hela wizarden.
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

  const meta = STEP_META[step];
  const isScraping = scrapeState?.status === "loading";

  // Auto-focus på första interaktiva element i nytt steg så operatören
  // direkt kan börja skriva utan att klicka. Sker bara på desktop —
  // mobile skulle annars få keyboard-popup vid varje stegbyte vilket
  // är distraherande. requestAnimationFrame säkerställer att DOM:en
  // för det nya steget har renderats innan vi söker.
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    if (typeof window === "undefined") return;
    // Hoppa över på små viewports — undvik keyboard-popup på mobil.
    if (window.innerWidth < 768) return;
    const raf = requestAnimationFrame(() => {
      const root = contentRef.current;
      if (!root) return;
      const candidate = root.querySelector<HTMLElement>(
        'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), [role="button"]:not([disabled]), button:not([disabled])',
      );
      // Säkerställ att vi inte stjäl fokus från ett element som
      // redan har det (t.ex. om operatören precis klickat på en
      // sidebar-länk).
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

          <DialogHeader className="space-y-2.5 px-10 pt-10 pb-6 text-left">
            {/* Header-pill — bara en (eyebrow) istället för tidigare
                dubbletten eyebrow + pipeline-badge. Pipeline-mappning
                framgår av sidebar-numreringen och dokumenteras i
                rules/handoff.md. */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="bg-foreground/[0.04] text-foreground/70 inline-flex items-center gap-2 rounded-full px-2.5 py-1 font-mono text-[9.5px] font-medium tracking-[0.2em] uppercase">
                {meta.eyebrow}
              </span>
            </div>
            <DialogTitle className="text-foreground text-[28px] leading-[1.15] font-semibold tracking-tight">
              {WIZARD_STEP_TITLES[step]}
            </DialogTitle>
            {/* DialogDescription renderas som <p>; interaktiva element
                (knappar/expansion-panel) får inte ligga inuti <p> per
                HTML-spec. Vi delar därför upp i en kort <p> + en
                syskon-region där info-knappen och panelen lever. */}
            <DialogDescription className="text-muted-foreground max-w-xl text-[13.5px] leading-relaxed">
              {meta.description}
            </DialogDescription>
            {meta.descriptionLong ? (
              // key={step} re-mountar komponenten vid steg-byte, så
              // intern useState(open) nollställs naturligt utan att
              // vi triggar setState i en effect (vilket React 19:s
              // `react-hooks/set-state-in-effect` blockerar).
              <StepDescriptionMoreButton
                key={step}
                text={meta.descriptionLong}
              />
            ) : null}
          </DialogHeader>

          <div className="bg-border/50 h-px w-full" aria-hidden />

          <div ref={contentRef} className="flex-1 overflow-y-auto px-10 py-8">
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
                  skriva igenom alla 7 stegen. Ännu mer dämpad i v2:
                  bara ikon + en bokstav i mindre opacity så den signal-
                  erar "dev tool" snarare än produkt-funktion. Hela
                  betydelsen blir tydlig via title-tooltip. */}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={fillDemo}
                aria-label="Fyll wizarden med en demo-profil"
                className="text-muted-foreground/60 hover:text-foreground hidden h-8 w-8 items-center justify-center p-0 sm:inline-flex"
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
                  disabled={!!validationError || isSubmitting}
                  className={[
                    "bg-foreground text-background hover:bg-foreground/90 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm disabled:opacity-40",
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
                    "bg-foreground text-background hover:bg-foreground/90 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm disabled:opacity-40",
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
                className="text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04] focus-visible:ring-ring/40 hidden h-7 w-7 items-center justify-center rounded-md transition-colors focus-visible:ring-2 focus-visible:outline-none sm:inline-flex"
              >
                <Keyboard className="h-3.5 w-3.5" aria-hidden />
              </button>
              <span className="text-muted-foreground hidden text-[10px] sm:inline">
                ⌘↵
              </span>
            </div>
          </div>

          {/* Keyboard shortcuts hjälp-overlay. Toggle:as via ? eller
              ⌘/. Light backdrop + centrerad kort. Behåller fokus
              inom overlayen så Tab cyklar mellan stäng-knappen och
              ev. action-element. */}
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
                <div className="border-border/60 bg-muted/20 border-t px-5 py-2.5">
                  <p className="text-muted-foreground text-[11px]">
                    Tryck <kbd className="border-border/60 bg-background mx-0.5 inline-flex h-4 items-center justify-center rounded border px-1 font-mono text-[10px]">?</kbd>{" "}
                    eller{" "}
                    <kbd className="border-border/60 bg-background mx-0.5 inline-flex h-4 items-center justify-center rounded border px-1 font-mono text-[10px]">⌘/</kbd>{" "}
                    när som helst för att öppna/stänga denna lista.
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        {/* Submit-overlay — visas ~700ms efter klick på "Skapa sajt"
            innan onComplete kallar parent. Ger operatören tydlig
            visuell bekräftelse att klicket registrerats och bygget
            är på väg innan wizarden stängs. */}
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
                <p className="text-muted-foreground font-mono text-[10px] tracking-[0.22em] uppercase">
                  Klar att bygga
                </p>
                <p className="text-foreground text-[16px] leading-tight font-semibold tracking-tight">
                  Påbörjar bygge av din sajt…
                </p>
                <p className="text-muted-foreground text-[12px]">
                  Pipelinen kör Discovery → Plan → Codegen → Quality
                  Gate i bakgrunden. Du ser progress i preview-fönstret
                  om en stund.
                </p>
              </div>
            </div>
          </div>
        ) : null}

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

/**
 * Inline "mer info"-knapp för step-description. Behåller default-vyn
 * minimalistisk (1 mening synlig) men låter en operatör som vill ha
 * mer kontext expandera utan att byta vy. Använder ``key={step}`` i
 * useState-initiering så texten automatiskt kollapsar vid steg-byte
 * — annars skulle en expanderad förklaring lämnas öppen mellan steg
 * och spilla över i nästa.
 */
function StepDescriptionMoreButton({ text }: { text: string }) {
  // useState(false) nollställs automatiskt vid steg-byte eftersom
  // föräldern monterar denna komponent med `key={step}`, vilket gör
  // att React remountar instansen vid varje stegbyte och bypassar
  // React 19:s `react-hooks/set-state-in-effect`-rule.
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Dölj förklaring" : "Visa förklaring"}
        className="text-muted-foreground/70 hover:text-foreground/85 focus-visible:ring-ring/40 inline-flex h-5 w-5 items-center justify-center self-start rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <Info className="h-3 w-3" aria-hidden />
      </button>
      <p
        id={panelId}
        role="note"
        hidden={!open}
        className="text-muted-foreground/80 max-w-xl text-[12px] leading-snug"
      >
        {text}
      </p>
    </div>
  );
}
