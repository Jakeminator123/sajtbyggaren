"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import {
  CTA_OPTIONS,
  MUST_HAVE_OPTIONS,
  suggestPagesFromAnswers,
} from "../wizard-constants";
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
 * Sidor föreslås automatiskt baserat på (a) valda kategorier i steg 2
 * och (b) keyword-träffar i fri-text från skrape/wizard-svar (offer,
 * uniqueValue, products, menu, etc). Resterande sidor visas under
 * "Övriga sidor" så operatorn kan välja till manuellt.
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
  // Bygg rekommendationer från kategori + skrape-text. useMemo så vi
  // inte räknar om vid varje render, bara när någon underliggande
  // text/typ-fält ändras. Vi plattar ut produkter/menu-items till
  // strängar så keyword-detektorn ser deras namn + beskrivningar.
  const productsText = useMemo(
    () =>
      answers.products
        .map((p) => `${p.name} ${p.description ?? ""} ${p.category ?? ""}`)
        .join(" "),
    [answers.products],
  );
  const menuText = useMemo(
    () =>
      answers.menuItems
        .map((m) => `${m.name} ${m.description ?? ""} ${m.category ?? ""}`)
        .join(" "),
    [answers.menuItems],
  );
  const sellingPointsText = useMemo(
    () => answers.uniqueSellingPoints.join(" "),
    [answers.uniqueSellingPoints],
  );

  const suggested = useMemo(
    () =>
      suggestPagesFromAnswers(answers.siteType, [
        answers.offer,
        sellingPointsText,
        answers.companyName,
        productsText,
        menuText,
        answers.targetAudience,
        answers.aboutText,
      ]),
    [
      answers.siteType,
      answers.offer,
      sellingPointsText,
      answers.companyName,
      productsText,
      menuText,
      answers.targetAudience,
      answers.aboutText,
    ],
  );

  const suggestedSet = useMemo(() => new Set(suggested), [suggested]);
  const otherPages = useMemo(
    () => MUST_HAVE_OPTIONS.filter((opt) => !suggestedSet.has(opt)),
    [suggestedSet],
  );

  // Auto-välj rekommenderade sidor vid första besöket på steget.
  // Vi vill INTE auto-välja igen om operatören explicit avmarkerat
  // dem — därför körs effekten bara en gång per komponent-mount, och
  // bara om `mustHave` är helt tomt.
  const autoAppliedRef = useRef(false);
  useEffect(() => {
    if (autoAppliedRef.current) return;
    if (answers.mustHave.length > 0) {
      autoAppliedRef.current = true;
      return;
    }
    if (suggested.length === 0) return;
    autoAppliedRef.current = true;
    onChange({ mustHave: suggested });
    // suggested ändras bara om underliggande svar ändras — och då vill
    // vi inte längre auto-applicera eftersom operatören redan sett
    // wizardens första render av sidan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const togglePage = (label: string) => {
    const set = new Set(answers.mustHave);
    if (set.has(label)) set.delete(label);
    else set.add(label);
    onChange({ mustHave: Array.from(set) });
  };

  const applyAllSuggested = () => {
    const set = new Set(answers.mustHave);
    for (const page of suggested) set.add(page);
    onChange({ mustHave: Array.from(set) });
  };

  const clearSuggested = () => {
    const set = new Set(answers.mustHave);
    for (const page of suggested) set.delete(page);
    onChange({ mustHave: Array.from(set) });
  };

  const setCta = (label: string) => {
    onChange({ primaryCta: answers.primaryCta === label ? "" : label });
  };

  const allSuggestedSelected =
    suggested.length > 0 && suggested.every((p) => answers.mustHave.includes(p));

  return (
    <FieldStack>
      <div>
        <div className="flex items-end justify-between gap-3">
          <div>
            <SectionHeader>Vi bygger dessa sidor *</SectionHeader>
            <HelperText>
              Föreslagna sidor är baserade på din kategori
              {answers.existingSite?.trim() ? " och din befintliga sajt" : ""}.
              Du kan ändra eller välja till fler nedan.
            </HelperText>
          </div>
          {suggested.length > 0 ? (
            <button
              type="button"
              onClick={allSuggestedSelected ? clearSuggested : applyAllSuggested}
              className="shrink-0 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {allSuggestedSelected ? "Avmarkera alla" : "Välj alla"}
            </button>
          ) : null}
        </div>

        {suggested.length > 0 ? (
          <div className="mt-4 rounded-2xl border border-foreground/10 bg-foreground/[0.02] p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-foreground/10">
                <Sparkles
                  className="h-3 w-3 text-foreground"
                  strokeWidth={2.2}
                />
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                Rekommenderade · {suggested.length}
              </span>
            </div>
            <ChipRow>
              {suggested.map((option) => (
                <Chip
                  key={option}
                  label={option}
                  selected={answers.mustHave.includes(option)}
                  onToggle={() => togglePage(option)}
                />
              ))}
            </ChipRow>
          </div>
        ) : null}

        {otherPages.length > 0 ? (
          <div className="mt-5">
            <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Övriga sidor
            </div>
            <ChipRow>
              {otherPages.map((option) => (
                <Chip
                  key={option}
                  label={option}
                  selected={answers.mustHave.includes(option)}
                  onToggle={() => togglePage(option)}
                />
              ))}
            </ChipRow>
          </div>
        ) : null}
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
