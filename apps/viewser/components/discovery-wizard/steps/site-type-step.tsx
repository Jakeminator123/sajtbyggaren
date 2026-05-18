"use client";

import { WIZARD_CATEGORIES } from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import { Chip, ChipRow, HelperText } from "./step-primitives";

/**
 * Steg 2 — Kategori. Multi-select chip-lista över 25 verksamhetstyper.
 * Första vald kategori styr `scaffoldHint` i discovery-payload:en.
 */
export function SiteTypeStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const toggle = (id: (typeof WIZARD_CATEGORIES)[number]["id"]) => {
    const set = new Set(answers.siteType);
    if (set.has(id)) {
      set.delete(id);
    } else {
      set.add(id);
    }
    onChange({ siteType: Array.from(set) });
  };

  return (
    <div className="flex flex-col gap-3">
      <HelperText>Välj en eller flera kategorier som beskriver verksamheten bäst.</HelperText>
      <ChipRow>
        {WIZARD_CATEGORIES.map((category) => (
          <Chip
            key={category.id}
            label={category.label}
            selected={answers.siteType.includes(category.id)}
            onToggle={() => toggle(category.id)}
          />
        ))}
      </ChipRow>
    </div>
  );
}
