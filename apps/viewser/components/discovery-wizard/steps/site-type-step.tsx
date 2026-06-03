"use client";

import type { discoveryOption } from "../discovery-options";
import type { WizardCategoryId } from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import { Chip, ChipRow, HelperText } from "./step-primitives";

/**
 * Step 2: category chips. The list comes from Discovery Taxonomy via
 * /api/discovery-options when available; wizard-constants is only a UI cache.
 */
export function SiteTypeStep({
  answers,
  onChange,
  options,
  source,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  options: readonly discoveryOption[];
  source: "governance" | "fallback";
}) {
  const toggle = (id: WizardCategoryId) => {
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
      <HelperText>
        Välj en eller flera kategorier som beskriver verksamheten bäst.
      </HelperText>
      <ChipRow>
        {options.map((category) => {
          const helper =
            source === "governance" ? supportHelper(category) : undefined;
          return (
            <Chip
              key={category.id}
              label={category.label}
              selected={answers.siteType.includes(category.id)}
              onToggle={() => toggle(category.id)}
              title={helper}
            />
          );
        })}
      </ChipRow>
      {renderSupportNotice({
        selected: answers.siteType,
        options,
        source,
      })}
    </div>
  );
}

function supportHelper(option: discoveryOption): string | undefined {
  if (option.supportStatus === "active") return undefined;
  if (option.supportStatus === "planned" && option.fallbackLabel) {
    return `${option.label} byggs som ${option.fallbackLabel} tills ${option.targetScaffoldLabel} är tillgänglig.`;
  }
  if (option.supportStatus === "fallback" && option.fallbackLabel) {
    return `${option.label} körs via ${option.fallbackLabel}.`;
  }
  return option.operatorNotes;
}

function renderSupportNotice({
  selected,
  options,
  source,
}: {
  selected: readonly WizardCategoryId[];
  options: readonly discoveryOption[];
  source: "governance" | "fallback";
}) {
  if (source !== "governance") return null;
  const selectedOptions = selected
    .map((id) => options.find((option) => option.id === id))
    .filter((option): option is discoveryOption => Boolean(option));
  const plannedOrFallback = selectedOptions.find(
    (option) =>
      option.supportStatus === "planned" || option.supportStatus === "fallback",
  );
  if (!plannedOrFallback) return null;

  const fallbackText = plannedOrFallback.fallbackLabel
    ? ` körs som ${plannedOrFallback.fallbackLabel}`
    : " körs via fallback";
  const targetText =
    plannedOrFallback.supportStatus === "planned"
      ? ` tills ${plannedOrFallback.targetScaffoldLabel} är tillgänglig`
      : "";

  return (
    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] px-3 py-2 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
      {plannedOrFallback.label}
      {fallbackText}
      {targetText}. Vi väljer en närliggande mall som grund så länge.
    </div>
  );
}
