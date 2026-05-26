"use client";

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";

import type { discoveryOption } from "../discovery-options";
import { FoundationSummary } from "../foundation-summary";
import { VibeSwatchRow } from "../visual-preview-card";
import {
  BUSINESS_FAMILIES,
  type BusinessFamily,
  type BusinessFamilyId,
  familyForCategory,
  findVibe,
  type WizardCategoryId,
} from "../wizard-constants";
import type { WizardAnswers } from "../wizard-types";
import {
  FieldLabel,
  FieldStack,
  MetadataPanel,
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
 *   1. URL-skrape — ALLTID HÖGST UPP. Snabbväg för befintliga sajter
 *      som auto-fyller företagsnamn, offer, kontaktuppgifter m.m.
 *      Detta är den vanligaste "lyxvägen" — operatören klistrar in
 *      URL → wizarden fylls automatiskt. Den får inte gömmas i en
 *      disclosure eftersom det halverar upptäckbarheten.
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
  onScrapeStateChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  options: readonly discoveryOption[];
  source: "governance" | "fallback";
  onScrapeStateChange?: (state: ScrapeState) => void;
}) {
  // Sub-specialisering togs bort 2026-05-26 efter operator-feedback
  // "Varför specialisering?". Vi behåller `options`-prop:en för API-
  // kompabilitet med discovery-wizard.tsx men referensen är void:ad
  // så TypeScript inte klagar på unused.
  void options;
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
      {/* URL-SKRAPE — alltid högst upp. Snabbväg som auto-fyller
          företagsnamn, offer, kontakt och mer från en befintlig sajt.
          Får inte gömmas i disclosure (halverar upptäckbarheten).
          Minimalism v2: en kort synlig ledtext säljer "lyxvägen" så
          operatören upptäcker den utan klick, längre förklaring
          ligger bakom info-ikonen. Status-meddelandet (scrapeMessage)
          syns kvar inline eftersom det är ett action-resultat
          operatören måste se utan klick. */}
      <div>
        <FieldLabel
          optional
          help="Vi läser publika sidor, om-oss, tjänster, kontakt och OG-bilder. Du kan granska och justera allt nedan efteråt."
        >
          Har ni redan en hemsida?
        </FieldLabel>
        <p className="text-muted-foreground/85 mt-1 text-[12px] leading-snug">
          Klistra in URL:en så fyller vi i resten automatiskt.
        </p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            type="url"
            value={answers.existingSite}
            onChange={(event) =>
              onChange({ existingSite: event.target.value })
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void handleScrape();
              }
            }}
            placeholder="www.dinhemsida.se"
            className="border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/30 flex h-9 w-full rounded-md border bg-transparent px-3 py-1 text-base md:text-[13px] shadow-xs transition-colors outline-none focus-visible:ring-2"
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
            {scrapeStatus === "loading" ? "Hämtar…" : "Hämta & fyll i"}
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

      {/* ESSENTIALS — alltid synliga: identitet + family. Hjälptexter
          ligger nu bakom info-ikon i FieldLabel (TextField/TextareaField
          dirigerar `helper`-prop:en bakom CollapsibleHelp by default
          efter minimalism-pass v2). */}
      <TextField
        label="Företagsnamn"
        optional
        value={answers.companyName}
        onChange={(value) => onChange({ companyName: value })}
        placeholder="t.ex. Ateljé Bird"
        helper={
          answers.existingSite.trim() && scrapeStatus !== "ok"
            ? "Fylls i automatiskt när du klickar Hämta ovan."
            : undefined
        }
        // Scrape-statusen är viktig att se direkt utan klick — annars
        // ren info-ikon. Vi använder inline-läge när scrape väntar,
        // annars går helpern bakom info-ikonen.
        helperInline={
          !!(answers.existingSite.trim() && scrapeStatus !== "ok")
        }
      />
      <TextareaField
        label="Vad gör ni? *"
        value={answers.offer}
        onChange={(value) => onChange({ offer: value })}
        placeholder="Beskriv kort vad ni erbjuder och vilka era kunder är."
        rows={3}
        helper="1–2 meningar räcker — vi använder den för att fylla i resten."
      />

      <div>
        <SectionHeader help="Styr scaffold + starter — vilken Next.js-mall backend bygger på. Visuell identitet (färg, typografi, känsla) bestäms i steg 2 och är fri oavsett bransch.">
          Verksamhetsfamilj *
        </SectionHeader>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {BUSINESS_FAMILIES.map((option) => (
            <FamilyCard
              key={option.id}
              family={option}
              selected={selectedFamily === option.id}
              onSelect={() => selectFamily(option.id)}
            />
          ))}
        </div>
      </div>

      {/* Live transparens — visas direkt när family + offer är ifyllda så
          operatören ser EXAKT vilka beslut backend kommer att fatta
          (scaffold, default-vibe, branch, förvalda funktioner).
          Minimalism v2: panelen ligger nu bakom en collapsible
          MetadataPanel så default-vyn för foundation är minimal och
          operatören klickar för transparens när hen vill ha det. */}
      {answers.businessFamily && answers.offer.trim() ? (
        <MetadataPanel
          id="foundation-summary"
          title="Så här tolkar vi dina val"
          subtitle="Scaffold, vibe, typografi, branch & förvalda funktioner — klicka för förhandsvisning."
        >
          <FoundationSummary
            businessFamily={answers.businessFamily}
            companyName={answers.companyName}
            offer={answers.offer}
          />
        </MetadataPanel>
      ) : null}

      {/* Specialisering-disclosure togs bort 2026-05-26 efter operator-
          feedback "Varför specialisering? Ta bort?". businessFamily ger
          backend tillräckligt scaffold-signal; sub-kategori kan alltid
          autosättas baserat på offer/scrape utan operator-input. */}
    </FieldStack>
  );
}

/**
 * FamilyCard — verksamhets­familje-kort i steg 1.
 *
 * Layouten är medvetet text-tung (label + beskrivning vänster) men
 * kompletteras av en subtil 3-prick-swatch-rad i kortets högerkant
 * som speglar default-vibens primary/accent/background. Swatchen är
 * läst-only PREVIEW — den signalerar "så här ser default-paletten ut
 * för den här branschen om du inte ändrar" snarare än att låsa
 * visuell identitet. Operatören får fri visuell ompröving i steg 2
 * (VisualStep), så en snickare kan välja "Bygg/Hantverk" och sedan
 * byta till ett mörkt tema utan inkonsekvens.
 *
 * Hero-layout-glyph är medvetet UTELÄMNAD här — vibe-id kodar inte
 * en specifik layout, så en glyph skulle behöva en godtycklig
 * default-variant och riskera att signalera "din bransch styr
 * layouten" vilket är fel mental model. Layouten väljs i steg 2.
 */
function FamilyCard({
  family,
  selected,
  onSelect,
}: {
  family: BusinessFamily;
  selected: boolean;
  onSelect: () => void;
}) {
  const defaultVibe = findVibe(family.defaultVariantId);
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={[
        "group flex w-full items-start gap-3 rounded-xl border px-3.5 py-3 text-left transition-all",
        selected
          ? "border-foreground bg-foreground/[0.04] shadow-sm"
          : "border-border/70 bg-card hover:border-foreground/40 hover:bg-foreground/[0.02] hover:shadow-sm",
      ].join(" ")}
    >
      <div className="min-w-0 flex-1">
        <div className="text-foreground text-[13px] font-semibold tracking-tight">
          {family.label}
        </div>
        <div className="text-muted-foreground line-clamp-2 text-[11.5px] leading-snug">
          {family.description}
        </div>
      </div>
      {defaultVibe ? (
        <VibeSwatchRow
          primary={defaultVibe.primarySwatch}
          accent={defaultVibe.accentSwatch}
          background={defaultVibe.background}
          size={9}
          className="mt-0.5 shrink-0 opacity-70 transition-opacity group-hover:opacity-100"
        />
      ) : null}
    </button>
  );
}
