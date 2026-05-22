"use client";

import {
  Heart,
  Info,
  Search,
  ShoppingBag,
  Sparkles,
  Target,
  Utensils,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Input } from "@/components/ui/input";

import {
  CTA_OPTIONS,
  findFunctionChoice,
  type FunctionChoice,
  type FunctionGroup,
  type FunctionGroupIconKey,
  functionGroupsForFamily,
  MUST_HAVE_OPTIONS,
  RECOMMENDED_FUNCTIONS_BY_FAMILY,
} from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import {
  AdvancedDisclosure,
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
 * FunctionsStep — wizardens steg 3 (Pass 3: rik gruppering + sök +
 * smart-defaults per family).
 *
 * Layout:
 *   1. Sökruta (filtrerar live mellan funktioner).
 *   2. "Använd rekommenderade"-knapp som per family applicerar
 *      `RECOMMENDED_FUNCTIONS_BY_FAMILY` (auto-väljer 4–8 funktioner).
 *   3. Per-grupp-kort med:
 *      - Lucide-ikon + label + beskrivning i header.
 *      - Chip-rad med funktioner; en-klick-toggle.
 *   4. Extra sidor (utöver de som triggas av funktioner).
 *   5. Primär CTA (chip eller fritext).
 *   6. Specialönskemål (fritext för det vi missat).
 *   7. Bottom sammanfattning av valda funktioner.
 */
export function FunctionsStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const family = answers.businessFamily;
  const groups = useMemo(() => functionGroupsForFamily(family), [family]);

  const [query, setQuery] = useState("");

  const toggleFunction = useCallback(
    (choice: FunctionChoice) => {
      const selectedSet = new Set(answers.selectedFunctions);
      const pagesSet = new Set(answers.mustHave);
      const wasSelected = selectedSet.has(choice.id);
      if (wasSelected) {
        selectedSet.delete(choice.id);
        if (choice.pageMustHave) pagesSet.delete(choice.pageMustHave);
      } else {
        selectedSet.add(choice.id);
        if (choice.pageMustHave) pagesSet.add(choice.pageMustHave);
      }
      onChange({
        selectedFunctions: Array.from(selectedSet),
        mustHave: Array.from(pagesSet),
      });
    },
    [answers.mustHave, answers.selectedFunctions, onChange],
  );

  /**
   * Auto-applicera familjens rekommenderade funktioner. Användaren får
   * ändå justera; vi append:ar (inte overskriver) befintliga val.
   * "Återställ till rekommenderade" rensar först.
   */
  const applyRecommendations = useCallback(
    (mode: "merge" | "reset") => {
      if (!family) return;
      const ids = RECOMMENDED_FUNCTIONS_BY_FAMILY[family] ?? [];
      const baseFns =
        mode === "reset"
          ? new Set<string>()
          : new Set(answers.selectedFunctions);
      const basePages =
        mode === "reset" ? new Set<string>() : new Set(answers.mustHave);
      for (const id of ids) {
        const choice = findFunctionChoice(id);
        if (!choice) continue;
        baseFns.add(choice.id);
        if (choice.pageMustHave) basePages.add(choice.pageMustHave);
      }
      onChange({
        selectedFunctions: Array.from(baseFns),
        mustHave: Array.from(basePages),
      });
    },
    [answers.mustHave, answers.selectedFunctions, family, onChange],
  );

  // Sökfilter. Tomt query = inga ändringar.
  const filteredGroups = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return groups;
    return groups
      .map((group) => ({
        ...group,
        choices: group.choices.filter((choice) => {
          const haystack = [choice.label, choice.description, choice.capability]
            .filter((s): s is string => Boolean(s))
            .join(" ")
            .toLowerCase();
          return haystack.includes(q);
        }),
      }))
      .filter((group) => group.choices.length > 0);
  }, [groups, query]);

  // Auto-apply rekommendationer första gången operatören öppnar steget,
  // om family är vald men inga funktioner ännu satta. Effekten körs
  // bara en gång per komponent-mount via `autoAppliedRef` så vi inte
  // skriver över operatorns aktiva avval.
  const autoAppliedRef = useRef(false);
  useEffect(() => {
    if (autoAppliedRef.current) return;
    if (!family) return;
    if (answers.selectedFunctions.length > 0) {
      autoAppliedRef.current = true;
      return;
    }
    autoAppliedRef.current = true;
    applyRecommendations("merge");
    // applyRecommendations är stabil mellan renders så länge family
    // och svaren inte ändras. Vi vill bara köra denna effekt en gång,
    // därför undertryck deps-varningen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setCta = (label: string) => {
    onChange({ primaryCta: answers.primaryCta === label ? "" : label });
  };

  const functionPageSet = useMemo(() => {
    const set = new Set<string>();
    for (const group of groups) {
      for (const choice of group.choices) {
        if (choice.pageMustHave) set.add(choice.pageMustHave);
      }
    }
    return set;
  }, [groups]);

  const extraPages = useMemo(
    () => MUST_HAVE_OPTIONS.filter((page) => !functionPageSet.has(page)),
    [functionPageSet],
  );

  const togglePage = useCallback(
    (label: string) => {
      const set = new Set(answers.mustHave);
      if (set.has(label)) set.delete(label);
      else set.add(label);
      onChange({ mustHave: Array.from(set) });
    },
    [answers.mustHave, onChange],
  );

  return (
    <FieldStack>
      {!family ? (
        <div className="border-border/70 bg-card/50 rounded-xl border p-4">
          <p className="text-muted-foreground text-[12px]">
            Välj verksamhetsfamilj i steg 1 för att se relevanta funktioner. Vi
            visar bara de funktionsgrupper som passar din typ av sajt.
          </p>
        </div>
      ) : null}

      {/* 1. Sökruta + 2. Smart-defaults-knapp. */}
      {family ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="text-muted-foreground absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2" />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Sök funktioner — t.ex. boka, gallery, chat…"
              className="h-9 pl-8 text-[12.5px]"
            />
          </div>
          <button
            type="button"
            onClick={() => applyRecommendations("reset")}
            title="Ersätter alla val med familjens rekommenderade funktioner"
            className="border-border/70 bg-card text-foreground/80 hover:border-foreground/40 hover:text-foreground inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md border px-3 text-[12px] font-medium transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Använd rekommenderade
          </button>
        </div>
      ) : null}

      {/* 3. Per-grupp-kort. */}
      {filteredGroups.map((group) => (
        <FunctionGroupCard
          key={group.id}
          group={group}
          selected={answers.selectedFunctions}
          onToggle={toggleFunction}
        />
      ))}

      {/* 5. CTA. */}
      <div>
        <FieldLabel>Primär CTA</FieldLabel>
        <HelperText>
          Vad ska besökaren göra? Backend keyword-mappar texten till conversion
          goals (boka, ring, offert, köp, kontakt). Välj en av chipsen.
        </HelperText>
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
      </div>

      {/* ADVANCED — extra sidor + egen CTA-fritext + specialönskemål. */}
      {family ? (
        <AdvancedDisclosure
          id="functions-advanced"
          label="Mer finjustering"
          hint="Egen CTA-text, extra sidor som inte triggas av funktioner ovan, och specialönskemål till backend."
          count={3}
          activeCount={
            (answers.primaryCta &&
            !CTA_OPTIONS.includes(
              answers.primaryCta as (typeof CTA_OPTIONS)[number],
            )
              ? 1
              : 0) +
            (extraPages.some((page) => answers.mustHave.includes(page)) ? 1 : 0) +
            (answers.specialRequests.trim() ? 1 : 0)
          }
        >
          <TextField
            label="Egen CTA"
            optional
            value={
              answers.primaryCta &&
              !CTA_OPTIONS.includes(
                answers.primaryCta as (typeof CTA_OPTIONS)[number],
              )
                ? answers.primaryCta
                : ""
            }
            onChange={(value) => onChange({ primaryCta: value })}
            placeholder="t.ex. Få en gratis offert"
            helper="Skriver över valt CTA-chip ovan. Tom = använd chip-valet."
          />

          {extraPages.length > 0 ? (
            <div>
              <SectionHeader>Extra sidor</SectionHeader>
              <HelperText>
                Lägg till sidor som inte triggas av en funktion ovan.
              </HelperText>
              <div className="mt-2">
                <ChipRow>
                  {extraPages.map((page) => (
                    <Chip
                      key={page}
                      label={page}
                      selected={answers.mustHave.includes(page)}
                      onToggle={() => togglePage(page)}
                    />
                  ))}
                </ChipRow>
              </div>
            </div>
          ) : null}

          <TextareaField
            label="Specialönskemål"
            optional
            value={answers.specialRequests}
            onChange={(value) => onChange({ specialRequests: value })}
            placeholder="Skriv om det är någon specifik funktion vi inte täckt ovan."
            rows={2}
            helper="Hamnar i planner-prompten som notesForPlanner — bra för specifika UI-önskemål."
          />
        </AdvancedDisclosure>
      ) : null}

      {/* 7. Sammanfattning. */}
      {answers.selectedFunctions.length > 0 ? (
        <div className="border-border/60 bg-foreground/[0.02] rounded-lg border p-3">
          <div className="text-muted-foreground font-mono text-[10px] tracking-[0.2em] uppercase">
            Valda funktioner · {answers.selectedFunctions.length}
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {answers.selectedFunctions.map((id) => {
              const choice = findFunctionChoice(id);
              if (!choice) return null;
              return (
                <span
                  key={id}
                  className="border-border/60 bg-card text-foreground/80 rounded-full border px-2 py-0.5 text-[10.5px]"
                >
                  {choice.label}
                </span>
              );
            })}
          </div>
        </div>
      ) : null}
    </FieldStack>
  );
}

function FunctionGroupCard({
  group,
  selected,
  onToggle,
}: {
  group: FunctionGroup;
  selected: string[];
  onToggle: (choice: FunctionChoice) => void;
}) {
  const Icon = ICON_MAP[group.iconKey];
  const selectedCount = group.choices.filter((c) =>
    selected.includes(c.id),
  ).length;
  return (
    <div className="border-border/70 bg-card/40 rounded-xl border p-4">
      <div className="mb-3 flex items-start gap-3">
        <span className="bg-foreground/[0.05] inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
          <Icon className="text-foreground h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-foreground text-[13.5px] font-semibold tracking-tight">
              {group.label}
            </span>
            {selectedCount > 0 ? (
              <span className="bg-foreground text-background inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 font-mono text-[9.5px]">
                {selectedCount}
              </span>
            ) : null}
          </div>
          <p className="text-muted-foreground mt-0.5 text-[11.5px] leading-snug">
            {group.description}
          </p>
        </div>
      </div>
      <ChipRow>
        {group.choices.map((choice) => (
          <Chip
            key={choice.id}
            label={choice.label}
            selected={selected.includes(choice.id)}
            onToggle={() => onToggle(choice)}
            title={choice.description}
          />
        ))}
      </ChipRow>
    </div>
  );
}

const ICON_MAP: Record<FunctionGroupIconKey, typeof Info> = {
  info: Info,
  conversion: Target,
  ecommerce: ShoppingBag,
  food: Utensils,
  interaction: Heart,
};
