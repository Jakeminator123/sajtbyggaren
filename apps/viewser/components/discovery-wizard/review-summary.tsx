"use client";

import { Check, ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

import type { MoreInfoTabId } from "./more-info-dialog";
import type { WizardAnswers } from "./wizard-types";

/**
 * Lätt review-summary (2026-06-09) — hopfällbar "granska dina svar"-rad som
 * renderas sist på Bilder-steget, precis innan "Skapa sajt". Den sammanfattar
 * INPUTEN operatören matat in (inte vad backend kommer bygga — planen finns
 * inte förrän bygget kört) och lyfter ärligt de luckor som gör sajten generisk:
 * ingen kontakt, ingen om-text, inga bilder. Varje rad har en "Ändra"-länk som
 * hoppar till rätt tab eller öppnar Mer information-popupen.
 *
 * Medveten minimalism: kollapsad som default (en rad), ingen ny tab. Payloaden
 * är oförändrad — ren UI/UX i apps/viewser-lane.
 */
export function ReviewSummary({
  answers,
  onJumpToStep,
  onOpenMoreInfo,
}: {
  answers: WizardAnswers;
  /** Hoppar till ett wizard-steg (0=Företaget, 1=Stil, 2=Funktioner). */
  onJumpToStep: (stepIndex: number) => void;
  /** Öppnar Mer information-popupen på en specifik flik (kontakt/about). */
  onOpenMoreInfo: (tab: MoreInfoTabId) => void;
}) {
  const [open, setOpen] = useState(false);

  const items = useMemo(() => {
    const company = answers.companyName.trim();
    const offerSnippet = answers.offer.trim().slice(0, 40);
    const contactValue = [
      answers.contact.phone.trim() ? "telefon" : null,
      answers.contact.email.trim() ? "e-post" : null,
      answers.contact.address.trim() ? "adress" : null,
      answers.contact.openingHours.trim() ? "öppettider" : null,
    ]
      .filter(Boolean)
      .join(" + ");
    const hasContact = contactValue.length > 0;
    const hasAbout = !!answers.aboutText.trim();
    const imageCount =
      (answers.assets.logo ? 1 : 0) +
      (answers.assets.heroImage ? 1 : 0) +
      answers.assets.gallery.length;
    const functionCount = answers.selectedFunctions.length;

    return [
      {
        id: "company",
        label: "Företag",
        value: company || (offerSnippet ? `”${offerSnippet}”` : "Namnges automatiskt"),
        gap: false,
        gapLabel: null as string | null,
        onEdit: () => onJumpToStep(0),
      },
      {
        id: "style",
        label: "Stil",
        value: answers.vibe.vibeId ? "Egen stil vald" : "Automatisk (från bransch)",
        gap: false,
        gapLabel: null,
        onEdit: () => onJumpToStep(1),
      },
      {
        id: "functions",
        label: "Funktioner",
        value:
          functionCount > 0
            ? `${functionCount} valda`
            : "Inga extra (standardsidor)",
        gap: false,
        gapLabel: null,
        onEdit: () => onJumpToStep(2),
      },
      {
        id: "contact",
        label: "Kontakt",
        value: hasContact ? contactValue : "Saknas",
        gap: !hasContact,
        gapLabel: "kontakt",
        onEdit: () => onOpenMoreInfo("contact"),
      },
      {
        id: "about",
        label: "Om-text",
        value: hasAbout ? "Ifylld" : "Genereras automatiskt",
        gap: !hasAbout,
        gapLabel: "om-text",
        onEdit: () => onOpenMoreInfo("about"),
      },
      {
        id: "images",
        label: "Bilder",
        value:
          imageCount > 0
            ? `${imageCount} uppladdade`
            : "Inga (AI-hero + monogram)",
        gap: imageCount === 0,
        gapLabel: "bild",
        // Bilder-steget ÄR den aktiva tabben — ingen "Ändra"-länk behövs.
        onEdit: null as (() => void) | null,
      },
    ];
  }, [answers, onJumpToStep, onOpenMoreInfo]);

  const gapLabels = items
    .filter((item) => item.gap)
    .map((item) => item.gapLabel)
    .filter((label): label is string => !!label);
  const allFilled = gapLabels.length === 0;

  return (
    <div className="border-border/40 mt-8 border-t pt-6">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-controls="wizard-review-summary"
        className="hover:bg-foreground/[0.03] focus-visible:ring-ring/40 flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="flex items-center gap-2.5">
          <span
            className={[
              "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
              allFilled
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "bg-amber-500/15 text-amber-600 dark:text-amber-400",
            ].join(" ")}
            aria-hidden
          >
            {allFilled ? (
              <Check className="h-3 w-3" strokeWidth={2.5} />
            ) : (
              <span className="text-[11px] font-semibold">
                {gapLabels.length}
              </span>
            )}
          </span>
          <span className="flex flex-col">
            <span className="text-foreground text-[12.5px] font-medium leading-tight">
              Granska dina svar
            </span>
            <span className="text-muted-foreground text-[11.5px] leading-tight">
              {allFilled
                ? "Allt viktigt ifyllt — redo att bygga"
                : `Att kolla: ${gapLabels.join(", ")}`}
            </span>
          </span>
        </span>
        <ChevronDown
          className={[
            "text-muted-foreground h-4 w-4 shrink-0 transition-transform",
            open ? "rotate-180" : "",
          ].join(" ")}
          aria-hidden
        />
      </button>

      {open ? (
        <dl
          id="wizard-review-summary"
          className="divide-border/40 border-border/40 mt-2 flex flex-col divide-y rounded-xl border"
        >
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3 px-3.5 py-2.5"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                {item.gap ? (
                  <span
                    className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"
                    aria-hidden
                  />
                ) : (
                  <span
                    className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500/70"
                    aria-hidden
                  />
                )}
                <dt className="text-muted-foreground w-20 shrink-0 text-[11.5px]">
                  {item.label}
                </dt>
                <dd className="text-foreground/90 truncate text-[12px]">
                  {item.value}
                </dd>
              </div>
              {item.onEdit ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={item.onEdit}
                  className="text-muted-foreground hover:text-foreground hover:bg-foreground/[0.04] min-tap sm:min-tap-0 h-7 shrink-0 rounded-full px-3 text-[11.5px] font-medium"
                >
                  Ändra
                </Button>
              ) : (
                <span className="text-muted-foreground/50 shrink-0 px-3 text-[11px]">
                  denna flik
                </span>
              )}
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
