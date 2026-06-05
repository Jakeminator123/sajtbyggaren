"use client";

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";

import type { WizardAnswers } from "../wizard-types";
import {
  FieldLabel,
  FieldStack,
  HelperText,
  SectionHeader,
  TextField,
  TextareaField,
} from "./step-primitives";

/**
 * Steg 1 — Företag.
 *
 * Innehåller URL-input + "Hämta"-knapp som anropar
 * `POST /api/scrape-site`. Resultatet returneras till parent via
 * `onChange()` så att kommande steg ser auto-ifyllda fält.
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

export function CompanyStep({
  answers,
  onChange,
  onScrapeStateChange,
}: {
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  /**
   * Lyfter skrape-state upp till DiscoveryWizard så den kan rendera en
   * overlay över hela popupen medan POST /api/scrape-site pågår.
   * Lokalt visar vi fortfarande en inline-status under URL-fältet.
   */
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
        body: JSON.stringify({ url, companyName: answers.companyName || undefined }),
      });
      const payload = (await response.json()) as ScrapeResponse;
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error ?? "Kunde inte läsa sajten.");
      }
      const data = payload.data ?? {};
      // Patcha bara fält som faktiskt har innehåll — låt resten vara
      // så operatorn inte tappar ev. tidigare manuellt skrivna värden.
      const patch: Partial<WizardAnswers> = {};
      for (const [key, value] of Object.entries(data)) {
        if (value === undefined || value === null) continue;
        if (typeof value === "string" && value.trim().length === 0) continue;
        if (Array.isArray(value) && value.length === 0) continue;
        (patch as Record<string, unknown>)[key] = value;
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
    answers.companyName,
    answers.existingSite,
    onChange,
    onScrapeStateChange,
  ]);

  return (
    <FieldStack>
      <TextField
        label="Företagsnamn"
        optional
        value={answers.companyName}
        onChange={(value) => onChange({ companyName: value })}
        placeholder="t.ex. Ateljé Bird"
      />

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
            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-base md:text-[13px] shadow-xs transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          />
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={handleScrape}
            disabled={scrapeStatus === "loading" || !answers.existingSite.trim()}
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

      <TextareaField
        label="Beskriv din verksamhet *"
        value={answers.offer}
        onChange={(value) => onChange({ offer: value })}
        placeholder="Vad gör ni? Vilka är era kunder? Vad gör er unika?"
        rows={4}
      />

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
