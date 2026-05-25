"use client";

import { BookText, Info, Layers } from "lucide-react";
import { useId, useState } from "react";

import type { ContentBranch } from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import { ContentStep } from "./content-step";
import {
  AdvancedDisclosure,
  FieldStack,
  HelperText,
  TextareaField,
} from "./step-primitives";
import { StoryEssentialsFields, StoryExtrasFields } from "./story-step";

/**
 * ContentOrchestratorStep — wizardens steg 4.
 *
 * Tre rader, från viktigast till valfri:
 *   1. Erbjudande/innehåll (branch-specifik ContentStep).
 *   2. Företagets identitet — bara "Om oss" är synlig; historia,
 *      vision, kontaktintro och målgrupp ligger i en disclosure.
 *      Om-oss är det enda fält som verkligen driver hero/intro-copy;
 *      resten är "fluff" som operatörer ofta hoppar.
 */
export function ContentOrchestratorStep({
  answers,
  onChange,
  branch,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  branch: ContentBranch;
}) {
  const storyAdvancedFilled =
    (answers.historyText.trim() ? 1 : 0) +
    (answers.visionText.trim() ? 1 : 0) +
    (answers.contactIntroText.trim() ? 1 : 0) +
    (answers.targetAudience.trim() ? 1 : 0);

  return (
    <FieldStack>
      <SectionCard
        icon={<Layers className="h-3.5 w-3.5" />}
        title="Erbjudande och innehåll"
        description={branchDescriptionShort(branch)}
        descriptionLong={branchDescription(branch)}
      >
        <ContentStep answers={answers} onChange={onChange} branch={branch} />
      </SectionCard>

      <SectionCard
        icon={<BookText className="h-3.5 w-3.5" />}
        title="Företagets identitet"
        description="Om-oss matar hero + intro-texter."
        descriptionLong="Mer detaljer (historia, vision, målgrupp) ligger i disclosure nedan. AI:n fyller i det som saknas från tone of voice."
      >
        <FieldStack>
          <StoryEssentialsFields answers={answers} onChange={onChange} />
          <AdvancedDisclosure
            id="content-identity-advanced"
            label="Historia, vision, kontaktintro & målgrupp"
            hint="Helt valfritt. Om du lämnar tomt skriver AI:n det från Om-oss + tone of voice."
            count={4}
            activeCount={storyAdvancedFilled}
          >
            <StoryExtrasFields answers={answers} onChange={onChange} />
            <TextareaField
              label="Beskriv målgruppen"
              optional
              value={answers.targetAudience}
              onChange={(value) => onChange({ targetAudience: value })}
              placeholder="Ålder, bransch, behov, plats, vad är typiskt för dem?"
              rows={2}
              helper="Driver tone of voice och copy-personalisering."
            />
          </AdvancedDisclosure>
        </FieldStack>
      </SectionCard>
    </FieldStack>
  );
}

/**
 * SectionCard — gemensam "kort"-wrapper för stora sektioner i steg 4.
 * Visar en ikon-pill + titel + kort beskrivning, sedan barnens innehåll.
 *
 * Minimalism v2: `description` är max en mening. `descriptionLong`
 * (valfritt) ligger bakom en info-ikon i `SectionHeader`-mönstret
 * så längre prosa inte tar default-yta.
 */
function SectionCard({
  icon,
  title,
  description,
  descriptionLong,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  descriptionLong?: string;
  children: React.ReactNode;
}) {
  const [helpOpen, setHelpOpen] = useState(false);
  const helpPanelId = useId();
  return (
    <div className="border-border/70 bg-card/40 rounded-xl border p-4">
      <div className="mb-3 flex items-start gap-3">
        <span className="bg-foreground/[0.05] inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-foreground text-[13.5px] font-semibold tracking-tight">
              {title}
            </span>
            {descriptionLong ? (
              <button
                type="button"
                onClick={() => setHelpOpen((prev) => !prev)}
                aria-expanded={helpOpen}
                aria-controls={helpPanelId}
                aria-label={helpOpen ? "Dölj förklaring" : "Visa förklaring"}
                className="text-muted-foreground/60 hover:text-foreground/80 focus-visible:ring-ring/40 inline-flex h-4 w-4 items-center justify-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none"
              >
                <Info className="h-3 w-3" aria-hidden />
              </button>
            ) : null}
          </div>
          <HelperText>{description}</HelperText>
          {descriptionLong ? (
            // Panelen mountas alltid (hidden när stängd) så aria-controls
            // alltid pekar på ett element i DOM — bättre AT-stöd än
            // conditional rendering.
            <p
              id={helpPanelId}
              role="note"
              hidden={!helpOpen}
              className="text-muted-foreground/80 mt-1 text-[11px] leading-snug"
            >
              {descriptionLong}
            </p>
          ) : null}
        </div>
      </div>
      {children}
    </div>
  );
}

/** En-mening default för SectionCard (minimalism v2). */
function branchDescriptionShort(branch: ContentBranch): string {
  switch (branch) {
    case "ecommerce":
      return "Produkter, prisnivå och USP:er.";
    case "restaurant":
      return "Meny, kök och kostalternativ.";
    case "salon":
      return "Behandlingar, team och bokning.";
    case "portfolio":
      return "Projekt, case och kunder.";
    case "construction":
      return "Tjänsteområden och referenser.";
    case "consulting":
      return "Tjänsteområden och kompetenser.";
    default:
      return "Konkret innehåll som ska finnas på sajten.";
  }
}

/** Längre prosa bakom info-ikon i SectionCard. */
function branchDescription(branch: ContentBranch): string {
  switch (branch) {
    case "ecommerce":
      return "Produkter, prisnivå och USP:er — för en sajt med köp-flöde.";
    case "restaurant":
      return "Meny, kök, kostalternativ och bokningslänk — för restaurang/café.";
    case "salon":
      return "Behandlingar, team och bokningslänk — för salong, klinik eller gym.";
    case "portfolio":
      return "Projekt, case och kunder — för kreativa eller konsulter.";
    case "construction":
      return "Tjänsteområden och referenser — för bygg, hantverk eller bil.";
    case "consulting":
      return "Tjänsteområden och kompetenser — för konsult eller byrå.";
    default:
      return "Konkret innehåll som ska finnas på sajten. Allt är valfritt; tomma fält fyller AI:n från er story.";
  }
}
