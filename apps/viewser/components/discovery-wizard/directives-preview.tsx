"use client";

import { Check, ChevronDown, Copy, FileJson } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  fallbackDiscoveryOptions,
  resolveScaffoldHintFromOptions,
} from "./discovery-options";
import { deriveWizardDirectives } from "./wizard-payload";
import { BUSINESS_FAMILIES } from "./wizard-constants";
import type { WizardAnswers } from "./wizard-types";

/**
 * Visar det härledda `WizardDirectives`-blocket som operator-läsbar JSON.
 *
 * Syftet är transparens: operatören ser **exakt** vad backend tar emot
 * baserat på wizard-svaren. Om något fält ser fel ut (t.ex. fel scaffold-
 * hint, saknad capability) vet operatören att de behöver gå tillbaka och
 * justera istället för att gissa varför genereringen blev fel.
 *
 * Komponenten är read-only och kollapsbar (default kollapsad) så den inte
 * tar fokus från huvud-UI:t. När expanderad visas JSON med syntax-
 * highlighting via `<code>` + en "Kopiera"-knapp.
 *
 * Implementationsnot: vi anropar `deriveWizardDirectives` här istället för
 * att memoa det globalt så att direkt feedback ges när operatören byter
 * något i tidigare steg och navigerar tillbaka till sista steget. Funktionen
 * är ren och deterministisk; ingen serverside-effekt.
 */
export function DirectivesPreview({
  answers,
  rawPrompt,
}: {
  answers: WizardAnswers;
  rawPrompt: string;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const directives = useMemo(() => {
    // Spegla samma scaffoldHint-resolution som `buildDiscoveryPayload` gör
    // — annars riskerar UI:t visa en annan hint än den som faktiskt skickas.
    const family = BUSINESS_FAMILIES.find(
      (f) => f.id === answers.businessFamily,
    );
    const scaffoldHint = family
      ? family.scaffoldHint
      : resolveScaffoldHintFromOptions(
          answers.siteType,
          fallbackDiscoveryOptions(),
        );
    return deriveWizardDirectives(rawPrompt, answers, scaffoldHint);
  }, [answers, rawPrompt]);

  const json = useMemo(() => JSON.stringify(directives, null, 2), [directives]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Tyst fail — clipboard kräver secure context. Ingen UI-feedback
      // krävs eftersom JSON:n är synlig nedanför och kan kopieras manuellt.
    }
  };

  // Räkna direktiv som inte är minimums (alla utöver language + scaffoldHint
  // som alltid finns). Används som badge så operator ser hur "rik" payloaden
  // är utan att behöva öppna kortet.
  const richFieldCount = Object.keys(directives).filter(
    (k) => k !== "language" && k !== "scaffoldHint",
  ).length;

  return (
    <div className="border-border/40 bg-muted/20 rounded-2xl border">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          "flex w-full items-center justify-between gap-3 px-4 py-3 text-left",
          "hover:bg-muted/40 rounded-2xl transition-colors",
        )}
        aria-expanded={open}
        aria-controls="directives-preview-content"
      >
        <div className="flex items-center gap-3">
          <FileJson className="text-muted-foreground h-4 w-4" aria-hidden />
          <div className="flex flex-col">
            <span className="text-sm font-medium">Detta ser backend</span>
            <span className="text-muted-foreground text-xs">
              {richFieldCount === 0
                ? "Bara minimal-direktiv — fyll i mer för bättre resultat"
                : `${richFieldCount} härledda direktiv från dina svar`}
            </span>
          </div>
        </div>
        <ChevronDown
          className={cn(
            "text-muted-foreground h-4 w-4 transition-transform",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {open && (
        <div
          id="directives-preview-content"
          className="border-border/40 space-y-3 border-t px-4 pt-3 pb-4"
        >
          <p className="text-muted-foreground text-xs">
            Strukturerad data som backend tar emot tillsammans med din pitch. Om
            något ser fel ut: gå tillbaka och ändra svaret. Tomma fält innebär
            att backend faller tillbaka till sin egen extraktion.
          </p>
          <div className="relative">
            <pre className="bg-muted/60 max-h-72 overflow-auto rounded-lg p-3 text-xs">
              <code className="text-foreground font-mono">{json}</code>
            </pre>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="min-tap sm:min-tap-0 absolute top-2 right-2 gap-1.5 px-2 text-xs active:scale-95 sm:h-7"
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3" aria-hidden />
                  Kopierat
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" aria-hidden />
                  Kopiera
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
