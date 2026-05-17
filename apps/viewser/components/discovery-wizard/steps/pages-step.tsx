"use client";

import { CTA_OPTIONS, MUST_HAVE_OPTIONS } from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import {
  Chip,
  ChipRow,
  FieldLabel,
  FieldStack,
  HelperText,
  SectionHeader,
  TextField,
  TextareaField,
} from "./step-primitives";

/**
 * Steg 5 — Sidor + primär CTA + målgrupp.
 *
 * `mustHave` är obligatoriskt (minst 1) — det blir input till
 * planner-modellens routes.json.
 */
export function PagesStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const togglePage = (label: string) => {
    const set = new Set(answers.mustHave);
    if (set.has(label)) set.delete(label);
    else set.add(label);
    onChange({ mustHave: Array.from(set) });
  };

  const setCta = (label: string) => {
    onChange({ primaryCta: answers.primaryCta === label ? "" : label });
  };

  return (
    <FieldStack>
      <div>
        <SectionHeader>Vi bygger dessa sidor *</SectionHeader>
        <HelperText>Välj minst en. Du kan alltid lägga till fler senare.</HelperText>
        <div className="mt-3">
          <ChipRow>
            {MUST_HAVE_OPTIONS.map((option) => (
              <Chip
                key={option}
                label={option}
                selected={answers.mustHave.includes(option)}
                onToggle={() => togglePage(option)}
              />
            ))}
          </ChipRow>
        </div>
      </div>

      <div>
        <FieldLabel>Primär CTA</FieldLabel>
        <HelperText>Vad ska besökaren göra? Välj en eller skriv egen.</HelperText>
        <div className="mt-2">
          <ChipRow>
            {CTA_OPTIONS.map((option) => (
              <Chip
                key={option}
                label={option}
                selected={answers.primaryCta === option}
                onToggle={() => setCta(option)}
              />
            ))}
          </ChipRow>
        </div>
        <div className="mt-2">
          <TextField
            label="Egen CTA"
            optional
            value={answers.primaryCta && !CTA_OPTIONS.includes(answers.primaryCta as (typeof CTA_OPTIONS)[number]) ? answers.primaryCta : ""}
            onChange={(value) => onChange({ primaryCta: value })}
            placeholder="t.ex. Få en gratis offert"
          />
        </div>
      </div>

      <TextareaField
        label="Målgrupp"
        optional
        value={answers.targetAudience}
        onChange={(value) => onChange({ targetAudience: value })}
        placeholder="Vilka är dina kunder? Ålder, bransch, behov."
        rows={2}
      />
    </FieldStack>
  );
}
