"use client";

import { Info, X } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";

import {
  BUSINESS_FAMILIES,
  deriveEffectiveScaffoldHint,
  resolveContentBranch,
} from "./wizard-constants";
import { deriveWizardDirectives } from "./wizard-payload";
import type { WizardAnswers } from "./wizard-types";

/**
 * PayloadAlignmentPopover — operatör-transparens-fönster som visar
 * EXAKT vilket directives-block backend kommer att få när hen klickar
 * "Skapa sajt". Anropar `deriveWizardDirectives()` read-only och
 * stringifierar resultatet.
 *
 * Detta är vår ALIGNMENT-GARANTI i UI-form: operatören kan ALLTID se
 * exakt vad som skickas, och vad som ändras när hen ändrar ett val.
 * Inga gissningar, inga "vi tror"-meddelanden. Bara den faktiska
 * payload-byggaren live-renderad.
 *
 * Sidoeffekt: om någon framtida bug skulle göra att UI-state inte
 * påverkar payload, blir det omedelbart synligt här (operatören
 * ändrar något, popoverns JSON ändras inte → felet upptäcks).
 */
export function PayloadAlignmentPopover({
  answers,
  rawPrompt,
  align = "right",
}: {
  answers: WizardAnswers;
  rawPrompt: string;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);

  // Härled scaffoldHint via SAMMA helper som buildDiscoveryPayload använder
  // vid submit (`deriveEffectiveScaffoldHint`). Tidigare läste popover:n bara
  // `family.scaffoldHint`, vilket missade sub-kategori-uppgraderingar (t.ex.
  // service-family + legal-sub-cat → professional-services) → popover:n
  // visade en annan scaffoldHint än den backend faktiskt fick. Nu är de 1:1.
  const directives = useMemo(() => {
    const family = BUSINESS_FAMILIES.find(
      (f) => f.id === answers.businessFamily,
    );
    const scaffoldHint = deriveEffectiveScaffoldHint(family, answers.siteType);
    return deriveWizardDirectives(rawPrompt, answers, scaffoldHint);
  }, [answers, rawPrompt]);

  const branch = useMemo(
    () => resolveContentBranch(answers.siteType),
    [answers.siteType],
  );

  // Pretty-printed JSON av directives — operatören ser den exakta
  // strukturen som backend tar emot. Vi sorterar inte nycklarna så
  // ordningen speglar deriveWizardDirectives ekonstruktion (visuellt
  // mer förutsägbart vid jämförelse).
  const json = useMemo(() => JSON.stringify(directives, null, 2), [directives]);

  return (
    <div
      className={cn("relative inline-flex", align === "right" ? "ml-auto" : "")}
    >
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04] focus-visible:ring-ring/40 inline-flex items-center gap-1.5 rounded-full border border-dashed border-current/40 px-2.5 py-1 text-[10.5px] font-medium tracking-tight transition-colors focus-visible:ring-2 focus-visible:outline-none"
        aria-expanded={open}
        title="Visa exakt vad backend får baserat på dina svar"
      >
        <Info className="h-3 w-3" />
        Vad backend får
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="Backend-payload baserat på dina svar"
          className={cn(
            // Tidigare fast w-[340px] orsakade horisontell overflow på 375px-
            // viewports inuti wizardens steg-padding. Nu: 340px på desktop,
            // krympt till "så bred som popoverns container tillåter" på
            // smala skärmar via max-w-[calc(100vw-2rem)].
            "border-border/70 bg-popover text-popover-foreground absolute top-full z-30 mt-2 w-[min(340px,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border shadow-xl",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          <div className="border-border/60 flex items-center justify-between border-b px-3 py-2">
            <div className="flex flex-col leading-tight">
              <span className="text-foreground text-[12px] font-semibold tracking-tight">
                Vad backend får
              </span>
              <span className="text-muted-foreground font-mono text-[9.5px] tracking-[0.18em] uppercase">
                directives + branch
              </span>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Stäng"
              className="text-muted-foreground hover:text-foreground min-tap sm:min-tap-0 flex items-center justify-center rounded-md transition-colors active:scale-95 sm:p-1"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="border-border/40 bg-muted/30 flex items-center justify-between gap-3 border-b px-3 py-2">
            <span className="text-muted-foreground text-[11px]">
              Content branch
            </span>
            <span className="text-foreground font-mono text-[11px]">
              {branch}
            </span>
          </div>

          <pre className="max-h-[280px] overflow-y-auto px-3 py-2 font-mono text-[10.5px] leading-relaxed">
            {json}
          </pre>

          <p className="border-border/40 text-muted-foreground border-t px-3 py-2 text-[10px] leading-snug">
            Detta block läses av <code>briefModel</code> som strukturerad
            sanning — backend hoppar över LLM-extraktion för fält som finns här.
          </p>
        </div>
      ) : null}
    </div>
  );
}
