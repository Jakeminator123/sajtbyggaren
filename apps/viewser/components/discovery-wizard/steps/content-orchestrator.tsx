"use client";

import { BookText, Layers, Target as TargetIcon } from "lucide-react";

import type { ContentBranch } from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import { ContentStep } from "./content-step";
import {
  FieldStack,
  HelperText,
  TextareaField,
} from "./step-primitives";
import { StoryStep } from "./story-step";

/**
 * ContentOrchestratorStep — wizardens steg 4 (Pass 4: rik sektion-layout).
 *
 * Wrapper som samlar alla copy/innehåll-fält i en tydlig ordning:
 *   1. Branch-specifika listor (tjänster/produkter/meny/projekt/team)
 *      — återanvänder `ContentStep`-grenar.
 *   2. Företagets identitet (om-oss, historia, vision, intro)
 *      — återanvänder `StoryStep`.
 *   3. Målgrupp (separat sektion så det inte tappas bort).
 *
 * Varje sektion har en kort header med ikon för visuell rytm och så
 * operatören enkelt kan scanna sig till rätt block.
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
  return (
    <FieldStack>
      <SectionCard
        icon={<Layers className="h-3.5 w-3.5" />}
        title="Erbjudande och innehåll"
        description={branchDescription(branch)}
      >
        <ContentStep answers={answers} onChange={onChange} branch={branch} />
      </SectionCard>

      <SectionCard
        icon={<BookText className="h-3.5 w-3.5" />}
        title="Företagets identitet"
        description="Bakgrund, vision och hur vi skriver om er. AI:n använder det för Om-oss, hero och intro-texter."
      >
        <StoryStep answers={answers} onChange={onChange} />
      </SectionCard>

      <SectionCard
        icon={<TargetIcon className="h-3.5 w-3.5" />}
        title="Målgrupp"
        description="Vilka är dina kunder? Driver tone of voice + copy-personalisering."
      >
        <TextareaField
          label="Beskriv målgruppen"
          optional
          value={answers.targetAudience}
          onChange={(value) => onChange({ targetAudience: value })}
          placeholder="Ålder, bransch, behov, plats, vad är typiskt för dem?"
          rows={2}
        />
      </SectionCard>
    </FieldStack>
  );
}

/**
 * SectionCard — gemensam "kort"-wrapper för stora sektioner i steg 4.
 * Visar en ikon-pill + titel + kort beskrivning, sedan barnens innehåll.
 */
function SectionCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-border/70 bg-card/40 rounded-xl border p-4">
      <div className="mb-3 flex items-start gap-3">
        <span className="bg-foreground/[0.05] inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-foreground text-[13.5px] font-semibold tracking-tight">
            {title}
          </div>
          <HelperText>{description}</HelperText>
        </div>
      </div>
      {children}
    </div>
  );
}

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
