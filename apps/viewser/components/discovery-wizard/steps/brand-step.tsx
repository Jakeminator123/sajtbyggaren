"use client";

import { DESIGN_STYLE_OPTIONS, TONE_OPTIONS } from "../wizard-constants";
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
 * Steg 6 — Ton, design-stil och brand-färger.
 *
 * Allt är valfritt — backend faller tillbaka till variantens
 * defaultfärger om inget anges.
 */
export function BrandStep({
  answers,
  onChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
}) {
  const toggleTone = (label: string) => {
    const set = new Set(answers.brand.toneTags);
    if (set.has(label)) set.delete(label);
    else set.add(label);
    onChange({ brand: { ...answers.brand, toneTags: Array.from(set) } });
  };

  const setDesignStyle = (label: string) => {
    onChange({
      brand: {
        ...answers.brand,
        designStyle: answers.brand.designStyle === label ? "" : label,
      },
    });
  };

  return (
    <FieldStack>
      <div>
        <SectionHeader>Ton i texterna</SectionHeader>
        <HelperText>Välj en eller flera tonalitets-tags.</HelperText>
        <div className="mt-2">
          <ChipRow>
            {TONE_OPTIONS.map((tone) => (
              <Chip
                key={tone}
                label={tone}
                selected={answers.brand.toneTags.includes(tone)}
                onToggle={() => toggleTone(tone)}
              />
            ))}
          </ChipRow>
        </div>
      </div>

      <div>
        <SectionHeader>Visuell stil</SectionHeader>
        <ChipRow>
          {DESIGN_STYLE_OPTIONS.map((style) => (
            <Chip
              key={style}
              label={style}
              selected={answers.brand.designStyle === style}
              onToggle={() => setDesignStyle(style)}
            />
          ))}
        </ChipRow>
      </div>

      <div>
        <SectionHeader>Färger</SectionHeader>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <FieldLabel optional>Primärfärg (hex)</FieldLabel>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={answers.brand.primaryColorHex || "#0f172a"}
                onChange={(event) =>
                  onChange({
                    brand: { ...answers.brand, primaryColorHex: event.target.value },
                  })
                }
                className="h-9 w-12 cursor-pointer rounded-md border border-border bg-transparent"
              />
              <TextField
                label=""
                value={answers.brand.primaryColorHex}
                onChange={(value) =>
                  onChange({ brand: { ...answers.brand, primaryColorHex: value } })
                }
                placeholder="#0f172a"
              />
            </div>
          </div>
          <div>
            <FieldLabel optional>Accentfärg (hex)</FieldLabel>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={answers.brand.accentColorHex || "#f59e0b"}
                onChange={(event) =>
                  onChange({
                    brand: { ...answers.brand, accentColorHex: event.target.value },
                  })
                }
                className="h-9 w-12 cursor-pointer rounded-md border border-border bg-transparent"
              />
              <TextField
                label=""
                value={answers.brand.accentColorHex}
                onChange={(value) =>
                  onChange({ brand: { ...answers.brand, accentColorHex: value } })
                }
                placeholder="#f59e0b"
              />
            </div>
          </div>
        </div>
      </div>

      <TextareaField
        label="Ord och uttryck att undvika"
        optional
        value={answers.brand.wordsToAvoid}
        onChange={(value) =>
          onChange({ brand: { ...answers.brand, wordsToAvoid: value } })
        }
        placeholder="t.ex. 'världsbäst', 'revolutionerande', branschjargong vi tycker är slitet"
        rows={2}
      />
    </FieldStack>
  );
}
