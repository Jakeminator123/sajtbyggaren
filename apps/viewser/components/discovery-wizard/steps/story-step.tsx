"use client";

import type { WizardAnswers } from "../wizard-types";
import { FieldStack, TextareaField } from "./step-primitives";

/**
 * Story-fält splittade i ``essentials`` (bara Om oss — driver hero/
 * intro-copy) och ``extras`` (historia, vision, kontaktintro — fluff
 * som de flesta operatörer hoppar). Tidigare hade vi en monolit
 * ``StoryStep`` som visade allt; det gjorde steg 4 oöverskådligt.
 *
 * Den exporterade ``StoryStep`` är kvar för bakåtkompatibilitet men
 * är inte längre monterad i nya orchestrator-flödet — den renderar
 * essentials + extras i samma stack ifall någon konsument fortfarande
 * importerar den.
 */
export function StoryEssentialsFields({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  return (
    <TextareaField
      label="Om oss"
      value={answers.aboutText}
      onChange={(value) => onChange({ aboutText: value })}
      placeholder="Berätta vem ni är, hur ni började och vad ni brinner för."
      rows={4}
    />
  );
}

export function StoryExtrasFields({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  return (
    <>
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
    </>
  );
}

/**
 * Bakåt-kompatibel monolit-export — använder inte längre orchestratorn
 * men kvarstår ifall en konsument utanför wizarden importerar den.
 */
export function StoryStep(props: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  return (
    <FieldStack>
      <StoryEssentialsFields {...props} />
      <StoryExtrasFields {...props} />
    </FieldStack>
  );
}
