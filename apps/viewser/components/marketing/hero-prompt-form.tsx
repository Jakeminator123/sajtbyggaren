"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { DiscoveryWizard } from "@/components/discovery-wizard/discovery-wizard";
import type { discoveryOption } from "@/components/discovery-wizard/discovery-options";
import type { WizardAnswers } from "@/components/discovery-wizard/wizard-types";
import { emptyWizardAnswers } from "@/components/discovery-wizard/wizard-types";
import { STUDIO_HREF } from "@/lib/routes";
import { setWizardHandoff } from "@/lib/init-prompt-handoff";
import { STARTER_PRESETS, type StarterPreset } from "@/lib/starter-presets";

// Hero-prompten: besökaren beskriver sin sajt DIREKT på den nya startsidan
// och DiscoveryWizarden öppnas som popup HÄR — ovanpå den nya heron (med
// logotyp + header bakom). Besökaren ser alltså aldrig någon gammal start-
// eller tom studiosida. När wizarden är klar lämnas hela resultatet över via
// ``setWizardHandoff`` och vi navigerar till ``/studio`` som bygger direkt
// (se lib/init-prompt-handoff.ts + prompt-builder.tsx).
export function HeroPromptForm() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const [handingOff, setHandingOff] = useState(false);
  // Förvalda wizard-svar när besökaren klickat en starter-chip (familj +
  // kategori redan satta). null = vanlig fri prompt (offer fylls från texten).
  const [seedAnswers, setSeedAnswers] = useState<WizardAnswers | null>(null);
  // Bumpas vid varje öppning så DiscoveryWizarden remountas och läser om
  // initialAnswers (de läses bara i useState-initieraren).
  const [wizardKey, setWizardKey] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  function start() {
    if (handingOff) return;
    // Öppna wizarden på heron. Tom prompt → wizarden öppnas ändå (besökaren
    // fyller "Vad gör ni?" där); annars förifylls offer-fältet med texten.
    // Manuell start → ingen förvald familj (besökaren väljer i wizarden).
    setSeedAnswers(null);
    setWizardKey((key) => key + 1);
    setWizardOpen(true);
  }

  // Starter-chip: förifyll prompten OCH förvälj verksamhetsfamilj/kategori,
  // öppna sedan wizarden. Samma seam som yrkessidornas StarterCta, fast
  // wizarden körs direkt här på heron (ingen navigation förrän "Skapa sajt").
  function startWithPreset(preset: StarterPreset) {
    if (handingOff) return;
    setPrompt(preset.promptSeed);
    const base = emptyWizardAnswers();
    base.offer = preset.promptSeed;
    base.businessFamily = preset.family;
    base.siteType = [preset.category];
    setSeedAnswers(base);
    setWizardKey((key) => key + 1);
    setWizardOpen(true);
  }

  function handleWizardComplete(
    answers: WizardAnswers,
    discoveryOptions: readonly discoveryOption[],
  ) {
    setWizardOpen(false);
    setHandingOff(true);
    setWizardHandoff({ prompt: prompt.trim(), answers, discoveryOptions });
    router.push(STUDIO_HREF);
  }

  return (
    <>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          start();
        }}
        className="mt-7 w-full max-w-[640px]"
      >
        <div className="relative overflow-hidden rounded-2xl border border-white/15 bg-white/95 shadow-2xl backdrop-blur-xl">
          <label htmlFor="hero-prompt" className="sr-only">
            Beskriv din sajt
          </label>
          <textarea
            id="hero-prompt"
            ref={textareaRef}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Beskriv din sajt — företag, känsla, mål, ton…"
            rows={2}
            maxLength={4000}
            disabled={handingOff}
            onKeyDown={(event) => {
              // ⌘/Ctrl + ↵ öppnar wizarden; Enter ensamt = radbrytning.
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                start();
              }
            }}
            className="text-foreground placeholder:text-muted-foreground/80 min-h-[64px] w-full resize-none bg-transparent px-4 py-3 text-base leading-relaxed outline-none disabled:opacity-70 md:text-[15px]"
          />
          <div className="border-border/40 flex items-center justify-between gap-2 border-t px-3 py-2">
            <span className="text-muted-foreground/70 hidden font-mono text-[10px] sm:inline">
              ⌘ + ↵
            </span>
            <button
              type="submit"
              disabled={handingOff}
              aria-label="Bygg din hemsida"
              className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/60 ml-auto inline-flex size-9 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-95 disabled:opacity-70"
            >
              {handingOff ? (
                <span className="bg-background inline-block size-2 animate-pulse rounded-full" />
              ) : (
                <svg
                  aria-hidden
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 19V5" />
                  <path d="m5 12 7-7 7 7" />
                </svg>
              )}
            </button>
          </div>
        </div>
        <p className="mt-3 text-[13px] leading-relaxed text-white/70">
          Skriv en mening om ditt företag — vi tar det därifrån.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-white/50">Eller börja från:</span>
          {STARTER_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => startWithPreset(preset)}
              disabled={handingOff}
              className="focus-visible:ring-ring/60 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[13px] text-white/90 transition-colors hover:bg-white/20 focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98] disabled:opacity-70"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </form>

      {/* DiscoveryWizarden lever här på heron. Dialogen portaleras till
          <body> så den ligger ovanpå hela den nya startsidan (logotyp +
          header syns bakom backdropen) — ingen navigation till en separat
          sida förrän besökaren klickat "Skapa sajt". */}
      <DiscoveryWizard
        key={wizardKey}
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        initialPrompt={prompt}
        initialAnswers={seedAnswers ?? undefined}
        onComplete={handleWizardComplete}
      />
    </>
  );
}
