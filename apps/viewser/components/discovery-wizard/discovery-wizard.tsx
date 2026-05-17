"use client";

import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";

import { AssetsStep } from "./steps/assets-step";
import { BrandStep } from "./steps/brand-step";
import { CompanyStep } from "./steps/company-step";
import { ContentStep } from "./steps/content-step";
import { PagesStep } from "./steps/pages-step";
import { SiteTypeStep } from "./steps/site-type-step";
import { StoryStep } from "./steps/story-step";
import { resolveContentBranch } from "./wizard-constants";
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
  onComplete: (answers: WizardAnswers) => void;
};

const SKIPPABLE_STEPS = new Set<WizardStepId>([
  "content",
  "story",
  "assets",
  "brand",
]);

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

  const step = WIZARD_STEP_ORDER[stepIndex];
  const branch = useMemo(() => resolveContentBranch(answers.siteType), [answers.siteType]);
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
    onComplete(answers);
  }, [answers, onComplete, validationError]);

  const isFirst = stepIndex === 0;
  const isLast = stepIndex === WIZARD_STEP_ORDER.length - 1;
  const canSkip = SKIPPABLE_STEPS.has(step);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[90vh] w-[min(100vw-2rem,720px)] flex-col gap-0 overflow-hidden p-0 sm:rounded-3xl"
        showCloseButton
      >
        <DialogHeader className="space-y-3 border-b border-border/60 px-6 py-5 text-left">
          <div className="flex items-center justify-between gap-3">
            <div>
              <DialogTitle className="text-base font-semibold tracking-tight">
                {WIZARD_STEP_TITLES[step]}
              </DialogTitle>
              <DialogDescription className="text-[12px] text-muted-foreground">
                Steg {stepIndex + 1} av {WIZARD_STEP_ORDER.length} · {completion}% klart
              </DialogDescription>
            </div>
            <StepDots activeIndex={stepIndex} />
          </div>
          <Progress value={((stepIndex + 1) / WIZARD_STEP_ORDER.length) * 100} className="h-1" />
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {step === "company" ? (
            <CompanyStep answers={answers} onChange={updateAnswers} />
          ) : null}
          {step === "siteType" ? (
            <SiteTypeStep answers={answers} onChange={updateAnswers} />
          ) : null}
          {step === "content" ? (
            <ContentStep answers={answers} onChange={updateAnswers} branch={branch} />
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

        <div className="flex items-center justify-between gap-3 border-t border-border/60 bg-card/60 px-6 py-4 backdrop-blur">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={isFirst}
            onClick={goBack}
            className="text-[12px]"
          >
            Tillbaka
          </Button>

          <div className="flex flex-1 flex-col items-end gap-1">
            {validationError ? (
              <span className="text-[11px] text-amber-600 dark:text-amber-300">
                {validationError}
              </span>
            ) : null}
            <div className="flex items-center gap-2">
              {canSkip ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={skipStep}
                  className="text-[12px]"
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
                  className="rounded-full"
                >
                  Skapa sajt
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  onClick={goNext}
                  disabled={!!validationError}
                  className="rounded-full"
                >
                  Fortsätt
                </Button>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function StepDots({ activeIndex }: { activeIndex: number }) {
  return (
    <div className="flex items-center gap-1.5" aria-hidden>
      {WIZARD_STEP_ORDER.map((_, idx) => (
        <span
          key={idx}
          className={`size-1.5 rounded-full transition-colors ${
            idx <= activeIndex ? "bg-foreground" : "bg-border"
          }`}
        />
      ))}
    </div>
  );
}
