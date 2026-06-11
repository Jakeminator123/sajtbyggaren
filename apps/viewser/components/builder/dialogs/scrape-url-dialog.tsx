"use client";

import { Globe, Loader2 } from "lucide-react";
import { useCallback, useState } from "react";

import {
  useFollowupBuild,
  type FollowupToolIntent,
  type OnFollowupBuildDone,
} from "@/components/builder/use-followup-build";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Skrapa en URL och använd resultatet som strukturerad context i
 * nästa follow-up-prompt. Vi återanvänder `/api/scrape-site` som
 * DiscoveryWizards CompanyStep redan ringer — backenden kör
 * `scripts/scrape_site.py` som crawlar upp till 5 sidor och
 * (om OPENAI_API_KEY finns) syntetiserar fälten via LLM.
 *
 * I builder-läget bryr vi oss inte om att patcha wizardens fält —
 * vi tar resultatet, serialiserar relevanta nycklar till en
 * läsbar text, och paketerar det som en följdprompt:
 *
 *   Använd följande info från {URL} för att uppdatera sajten:
 *     - Företagsnamn: ...
 *     - Erbjudande: ...
 *     - ...
 *
 * briefModel + planningModel-paret hanterar det som vilken som
 * helst följdprompt — Project Input uppdateras och sajten byggs om.
 */

type ScrapeResponse = {
  ok?: boolean;
  data?: Record<string, unknown>;
  error?: string;
};

type ScrapePreviewField = {
  key: string;
  label: string;
  preview: string;
};

// Mappa kända scrape-nycklar till svenska etiketter för preview-listan.
// Okända nycklar visas också (med rå key som label) så vi inte tappar info.
const FIELD_LABELS: Record<string, string> = {
  companyName: "Företagsnamn",
  offer: "Erbjudande",
  aboutText: "Om oss",
  historyText: "Historik",
  visionText: "Vision",
  contactIntroText: "Kontakt-intro",
  services: "Tjänster",
  products: "Produkter",
  team: "Team",
  projects: "Projekt",
  menuItems: "Menyalternativ",
  uniqueSellingPoints: "USP",
  targetAudience: "Målgrupp",
  primaryCta: "Primär CTA",
  contact: "Kontaktuppgifter",
};

function previewValue(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return null;
    return trimmed.length > 80 ? `${trimmed.slice(0, 77)}…` : trimmed;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return null;
    return `${value.length} st`;
  }
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    if (keys.length === 0) return null;
    return `${keys.length} fält`;
  }
  return String(value);
}

function buildPromptFromData(
  url: string,
  data: Record<string, unknown>,
): string {
  const lines: string[] = [];
  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) continue;
      lines.push(`- ${FIELD_LABELS[key] ?? key}: ${trimmed}`);
      continue;
    }
    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      const serialized = value
        .map((entry) => {
          if (typeof entry === "string") return entry;
          if (entry && typeof entry === "object") {
            try {
              return JSON.stringify(entry);
            } catch {
              return String(entry);
            }
          }
          return String(entry);
        })
        .join("; ");
      lines.push(`- ${FIELD_LABELS[key] ?? key}: ${serialized}`);
      continue;
    }
    if (typeof value === "object") {
      try {
        lines.push(`- ${FIELD_LABELS[key] ?? key}: ${JSON.stringify(value)}`);
      } catch {
        // Hoppa över non-serialiserbara objekt.
      }
    }
  }
  return [
    `Använd följande info från ${url} för att uppdatera sajten. Du bestämmer själv vad som ska in i vilket avsnitt — behåll struktur och design, men ersätt platshållartext med riktig info där det är relevant:`,
    "",
    ...lines,
  ].join("\n");
}

type ScrapeUrlDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  siteId: string;
  onBuildStart: () => void;
  onBuildEnd: () => void;
  onBuildDone: OnFollowupBuildDone;
  /** C2 globalt bygg-lås + C1 "Iterera från denna"-pin (från BuilderShell). */
  isBuilding?: boolean;
  baseRunId?: string | null;
};

export function ScrapeUrlDialog({
  open,
  onOpenChange,
  siteId,
  onBuildStart,
  onBuildEnd,
  onBuildDone,
  isBuilding = false,
  baseRunId = null,
}: ScrapeUrlDialogProps) {
  const [url, setUrl] = useState("");
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeError, setScrapeError] = useState<string | null>(null);
  const [scrapedData, setScrapedData] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [scrapedUrl, setScrapedUrl] = useState<string | null>(null);
  const {
    runFollowup,
    isBusy,
    error: buildError,
  } = useFollowupBuild({
    siteId,
    onBuildStart,
    onBuildEnd,
    onBuildDone,
    isBuilding,
    baseRunId,
  });

  const reset = useCallback(() => {
    setUrl("");
    setScrapedData(null);
    setScrapedUrl(null);
    setScrapeError(null);
  }, []);

  const handleClose = useCallback(
    (next: boolean) => {
      if (!next) reset();
      onOpenChange(next);
    },
    [onOpenChange, reset],
  );

  const handleScrape = useCallback(async () => {
    const trimmed = url.trim();
    if (!trimmed || isScraping) return;
    setIsScraping(true);
    setScrapeError(null);
    setScrapedData(null);
    try {
      const response = await fetch("/api/scrape-site", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });
      const payload = (await response.json()) as ScrapeResponse;
      if (!response.ok || !payload.ok || !payload.data) {
        throw new Error(payload.error ?? "Kunde inte läsa sajten.");
      }
      setScrapedData(payload.data);
      setScrapedUrl(trimmed);
    } catch (caught) {
      setScrapeError(caught instanceof Error ? caught.message : "Okänt fel.");
    } finally {
      setIsScraping(false);
    }
  }, [url, isScraping]);

  const handleApply = useCallback(async () => {
    if (!scrapedData || !scrapedUrl) return;
    const prompt = buildPromptFromData(scrapedUrl, scrapedData);
    // Strukturerad intent (specialist-dispatch steg 2): de råa scrape-
    // fälten skickas som data så copy-specialisten (copyDirectiveModel
    // i extraktionsläge) slipper re-parsa den serialiserade prompttexten.
    const toolIntent: FollowupToolIntent = {
      tool: "content_import",
      params: { sourceUrl: scrapedUrl, fields: scrapedData },
    };
    const result = await runFollowup(prompt, { toolIntent });
    if (result.ok) handleClose(false);
  }, [scrapedData, scrapedUrl, runFollowup, handleClose]);

  const previewFields: ScrapePreviewField[] = scrapedData
    ? Object.entries(scrapedData)
        .map(([key, value]) => {
          const preview = previewValue(value);
          if (!preview) return null;
          return {
            key,
            label: FIELD_LABELS[key] ?? key,
            preview,
          };
        })
        .filter((entry): entry is ScrapePreviewField => entry !== null)
    : [];

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Hämta info från en URL</DialogTitle>
          <DialogDescription>
            Skrapa en webbsida och använd resultatet för att uppdatera sajtens
            innehåll i nästa bygge.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div>
            <Label
              htmlFor="builder-scrape-url"
              className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase"
            >
              URL
            </Label>
            <div className="flex gap-2">
              <Input
                id="builder-scrape-url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void handleScrape();
                  }
                }}
                placeholder="https://exempel.se"
                disabled={isScraping || isBusy}
                spellCheck={false}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={handleScrape}
                disabled={isScraping || isBusy || !url.trim()}
              >
                {isScraping ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Skrapar…
                  </>
                ) : (
                  <>
                    <Globe className="h-4 w-4" />
                    Hämta
                  </>
                )}
              </Button>
            </div>
            <p className="text-muted-foreground mt-1 text-[10.5px]">
              Vi crawlar upp till 5 sidor och syntetiserar fälten. Tar ofta
              30-90 sekunder för riktiga sajter.
            </p>
          </div>

          {scrapeError ? (
            <p
              role="alert"
              className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
            >
              {scrapeError}
            </p>
          ) : null}

          {scrapedData ? (
            previewFields.length > 0 ? (
              <div>
                <Label className="text-muted-foreground mb-1.5 block text-[11px] tracking-tight uppercase">
                  Hämtade fält ({previewFields.length})
                </Label>
                <ul className="border-border/60 bg-muted/30 max-h-[220px] overflow-y-auto rounded-md border p-2 text-[12px]">
                  {previewFields.map((field) => (
                    <li
                      key={field.key}
                      className="flex items-start gap-2 py-0.5 leading-snug"
                    >
                      <span className="text-muted-foreground min-w-[110px] shrink-0">
                        {field.label}
                      </span>
                      <span className="text-foreground/85 break-words">
                        {field.preview}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-muted-foreground text-[12px]">
                Sajten kunde läsas men inga användbara fält hittades.
              </p>
            )
          ) : null}
        </div>

        {buildError ? (
          <p
            role="alert"
            className="text-destructive bg-destructive/10 border-destructive/40 rounded-md border px-3 py-2 text-[12px]"
          >
            {buildError}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => handleClose(false)}
            disabled={isScraping || isBusy}
          >
            Stäng
          </Button>
          <Button
            type="button"
            onClick={handleApply}
            disabled={!scrapedData || previewFields.length === 0 || isBusy}
          >
            {isBusy ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Bygger…
              </>
            ) : (
              <>
                <Globe className="h-4 w-4" />
                Använd som följdprompt
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
