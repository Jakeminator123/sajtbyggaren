"use client";

import type { WizardAnswers } from "../wizard-types";
import { FieldStack, TextareaField } from "./step-primitives";

/**
 * Steg 4 — Story. Längre fritext-fält som genererar copy för
 * Om-oss/Hero/Footer-intro.
 */
export function StoryStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  return (
    <FieldStack>
      <TextareaField
        label="Om oss"
        value={answers.aboutText}
        onChange={(value) => onChange({ aboutText: value })}
        placeholder="Berätta vem ni är, hur ni började och vad ni brinner för."
        rows={4}
      />
      <TextareaField
        label="Historia"
        optional
        value={answers.historyText}
        onChange={(value) => onChange({ historyText: value })}
        placeholder="När startades verksamheten? Viktiga milstolpar?"
        rows={3}
      />
      <TextareaField
        label="Vision och mission"
        optional
        value={answers.visionText}
        onChange={(value) => onChange({ visionText: value })}
        placeholder="Vad strävar ni mot? Vilken förändring vill ni se?"
        rows={3}
      />
      <TextareaField
        label="Kontaktsidans intro"
        optional
        value={answers.contactIntroText}
        onChange={(value) => onChange({ contactIntroText: value })}
        placeholder="Inledande text på kontakt-sidan, t.ex. 'Hör av dig — vi svarar inom 24h.'"
        rows={2}
      />
    </FieldStack>
  );
}
