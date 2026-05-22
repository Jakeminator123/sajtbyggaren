"use client";

import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

import type { discoveryOption } from "../discovery-options";
import {
  BUSINESS_FAMILIES,
  type BusinessFamilyId,
  familyForCategory,
  type WizardCategoryId,
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
 * FoundationStep — wizardens nya steg 1.
 *
 * Kombinerar tidigare CompanyStep + SiteTypeStep, plus den nya
 * BusinessFamily-väljaren som driver scaffold/starter-valet.
 *
 * Innehållsordning (UI-mening "av-stort-till-litet"):
 *   1. URL-skrape (snabbväg för befintliga sajter)
 *   2. Företagsnamn + offer (identitet)
 *   3. Verksamhetsfamilj (8 kort → primärt scaffold-val)
 *   4. Sub-specialisering (chips filtrerade efter vald family)
 *   5. Kontakt (telefon/email/adress/öppettider)
 */

export type ScrapeStatus = "idle" | "loading" | "ok" | "error";

export type ScrapeState = {
  status: ScrapeStatus;
  message: string;
  url?: string;
};

type ScrapeResponse = {
  ok: boolean;
  data?: Partial<WizardAnswers>;
  error?: string;
};

export function FoundationStep({
  answers,
  onChange,
  options,
  source,
  onScrapeStateChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  options: readonly discoveryOption[];
  source: "governance" | "fallback";
  onScrapeStateChange?: (state: ScrapeState) => void;
}) {
  const [scrapeStatus, setScrapeStatus] = useState<ScrapeStatus>("idle");
  const [scrapeMessage, setScrapeMessage] = useState<string>("");

  const handleScrape = useCallback(async () => {
    const url = answers.existingSite.trim();
    if (!url) return;
    const loadingMessage = `Hämtar innehåll från ${url}…`;
    setScrapeStatus("loading");
    setScrapeMessage(loadingMessage);
    onScrapeStateChange?.({ status: "loading", message: loadingMessage, url });
    try {
      const response = await fetch("/api/scrape-site", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          companyName: answers.companyName || undefined,
        }),
      });
      const payload = (await response.json()) as ScrapeResponse;
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error ?? "Kunde inte läsa sajten.");
      }
      const data = payload.data ?? {};
      const patch: Partial<WizardAnswers> = {};
      for (const [key, value] of Object.entries(data)) {
        if (value === undefined || value === null) continue;
        if (typeof value === "string" && value.trim().length === 0) continue;
        if (Array.isArray(value) && value.length === 0) continue;
        (patch as Record<string, unknown>)[key] = value;
      }
      // Auto-härleda business family från första matchande sub-kategori
      // om operatören ännu inte valt en family själv.
      if (
        !answers.businessFamily &&
        Array.isArray(patch.siteType) &&
        patch.siteType.length > 0
      ) {
        const inferred = familyForCategory(
          patch.siteType[0] as WizardCategoryId,
        );
        if (inferred) {
          patch.businessFamily = inferred.id;
        }
      }
      onChange(patch);
      setScrapeStatus("ok");
      const filledCount = Object.keys(patch).length;
      const okMessage =
        filledCount > 0
          ? `Hämtade ${filledCount} fält. Granska och justera nedan.`
          : "Sajten kunde läsas men inga fält kunde fyllas i automatiskt.";
      setScrapeMessage(okMessage);
      onScrapeStateChange?.({ status: "ok", message: okMessage, url });
    } catch (error) {
      setScrapeStatus("error");
      const errorMessage =
        error instanceof Error ? error.message : "Okänt fel vid skrape.";
      setScrapeMessage(errorMessage);
      onScrapeStateChange?.({ status: "error", message: errorMessage, url });
    }
  }, [
    answers.businessFamily,
    answers.companyName,
    answers.existingSite,
    onChange,
    onScrapeStateChange,
  ]);

  const selectedFamily = answers.businessFamily;
  const family = BUSINESS_FAMILIES.find((f) => f.id === selectedFamily);

  // Sub-kategori-chips visar bara de som tillhör vald family.
  // Om ingen family är vald visas inga chips (operatören väljer family först).
  const subCategoryOptions = useMemo(() => {
    if (!family) return [];
    return options.filter((opt) =>
      (family.subCategories as readonly WizardCategoryId[]).includes(opt.id),
    );
  }, [family, options]);

  const toggleSubCategory = useCallback(
    (id: WizardCategoryId) => {
      const set = new Set(answers.siteType);
      if (set.has(id)) {
        set.delete(id);
      } else {
        set.add(id);
      }
      onChange({ siteType: Array.from(set) });
    },
    [answers.siteType, onChange],
  );

  const selectFamily = useCallback(
    (familyId: BusinessFamilyId) => {
      // Byt family → rensa sub-kategorier som inte tillhör nya familyn.
      const newFamily = BUSINESS_FAMILIES.find((f) => f.id === familyId);
      if (!newFamily) return;
      const validSubs = new Set<WizardCategoryId>(newFamily.subCategories);
      const filteredSubs = answers.siteType.filter((id) => validSubs.has(id));
      onChange({
        businessFamily: familyId,
        siteType: filteredSubs,
      });
    },
    [answers.siteType, onChange],
  );

  return (
    <FieldStack>
      {/* 1. URL-skrape — snabbväg när det finns en befintlig sajt. */}
      <div>
        <FieldLabel optional>Befintlig hemsida</FieldLabel>
        <HelperText>
          Klistra in din nuvarande hemsida så fyller vi i fält automatiskt.
        </HelperText>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            type="url"
            value={answers.existingSite}
            onChange={(event) => onChange({ existingSite: event.target.value })}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void handleScrape();
              }
            }}
            placeholder="www.dinhemsida.se"
            className="border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/30 flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-[13px] shadow-xs transition-colors outline-none focus-visible:ring-2"
          />
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={handleScrape}
            disabled={
              scrapeStatus === "loading" || !answers.existingSite.trim()
            }
            className="h-9 shrink-0"
          >
            {scrapeStatus === "loading" ? "Hämtar…" : "Hämta"}
          </Button>
        </div>
        {scrapeMessage ? (
          <p
            className={`mt-1.5 text-[11px] ${
              scrapeStatus === "error"
                ? "text-destructive"
                : scrapeStatus === "ok"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-muted-foreground"
            }`}
          >
            {scrapeMessage}
          </p>
        ) : null}
      </div>

      {/* 2. Identitet — namn + offer. */}
      <TextField
        label="Företagsnamn *"
        value={answers.companyName}
        onChange={(value) => onChange({ companyName: value })}
        placeholder="t.ex. Ateljé Bird"
      />
      <TextareaField
        label="Vad gör ni? *"
        value={answers.offer}
        onChange={(value) => onChange({ offer: value })}
        placeholder="Beskriv kort vad ni erbjuder och vilka era kunder är."
        rows={3}
        helper="1–2 meningar räcker — vi använder den för att fylla i resten."
      />

      {/* 3. Verksamhetsfamilj — primärt scaffold-val (8 kort). */}
      <div>
        <SectionHeader>Verksamhetsfamilj *</SectionHeader>
        <HelperText>
          Styr scaffold + starter — vilken Next.js-mall backend bygger på. Välj
          den som passar bäst; sub-kategorin nedanför finjusterar copy och SEO.
        </HelperText>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {BUSINESS_FAMILIES.map((option) => {
            const isSelected = selectedFamily === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => selectFamily(option.id)}
                aria-pressed={isSelected}
                className={[
                  "rounded-xl border p-3 text-left transition-colors",
                  isSelected
                    ? "border-foreground bg-foreground/[0.04] shadow-sm"
                    : "border-border/70 bg-card hover:border-foreground/40 hover:bg-foreground/[0.02]",
                ].join(" ")}
              >
                <div className="text-foreground text-[13px] font-semibold tracking-tight">
                  {option.label}
                </div>
                <div className="text-muted-foreground mt-1 text-[11.5px] leading-snug">
                  {option.description}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. Sub-specialisering — filtrerade chips för vald family. */}
      {selectedFamily && subCategoryOptions.length > 0 ? (
        <div>
          <SectionHeader>Specialisering (valfri)</SectionHeader>
          <HelperText>
            En eller flera sub-kategorier för bättre copy och SEO.
            {source === "fallback"
              ? " (Visar lokal UI-cache tills governance-listan laddats.)"
              : ""}
          </HelperText>
          <div className="mt-2">
            <ChipRow>
              {subCategoryOptions.map((category) => (
                <Chip
                  key={category.id}
                  label={category.label}
                  selected={answers.siteType.includes(category.id)}
                  onToggle={() => toggleSubCategory(category.id)}
                />
              ))}
            </ChipRow>
          </div>
        </div>
      ) : null}

      {/* 5. Kontakt. */}
      <div>
        <SectionHeader>Kontakt</SectionHeader>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Telefon"
            type="tel"
            optional
            value={answers.contact.phone}
            onChange={(value) =>
              onChange({ contact: { ...answers.contact, phone: value } })
            }
            placeholder="08-123 45 67"
          />
          <TextField
            label="E-post"
            type="email"
            optional
            value={answers.contact.email}
            onChange={(value) =>
              onChange({ contact: { ...answers.contact, email: value } })
            }
            placeholder="hej@dittforetag.se"
          />
          <TextField
            label="Adress"
            optional
            value={answers.contact.address}
            onChange={(value) =>
              onChange({ contact: { ...answers.contact, address: value } })
            }
            placeholder="Storgatan 1, 111 22 Stockholm"
          />
          <TextField
            label="Öppettider"
            optional
            value={answers.contact.openingHours}
            onChange={(value) =>
              onChange({ contact: { ...answers.contact, openingHours: value } })
            }
            placeholder="Mån–Fre 09–17"
          />
        </div>
      </div>
    </FieldStack>
  );
}
