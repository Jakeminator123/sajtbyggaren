"use client";

import { Info, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { ContentOrchestratorStep } from "./steps/content-orchestrator";
import { MediaStep } from "./steps/media-step";
import type { ContentBranch } from "./wizard-constants";
import type { WizardAnswers } from "./wizard-types";

/**
 * MoreInfoDialog \u2014 popup som \u00f6ppnas fr\u00e5n "Mer information"-knappen
 * p\u00e5 tab 3 (Funktioner). \u00c5teranv\u00e4nder ContentOrchestratorStep och
 * MediaStep men presenterar deras f\u00e4lt som flikar h\u00f6gst upp, s\u00e5
 * huvud-wizarden kan f\u00f6rbli minimalistisk medan operat\u00f6ren \u00e4nd\u00e5 har
 * full kontroll \u00f6ver inneh\u00e5ll/media om hen vill.
 *
 * Backend-payload p\u00e5verkas inte \u2014 alla f\u00e4lt skrivs till samma
 * `WizardAnswers`-objekt som `buildDiscoveryPayload` redan l\u00e4ser.
 *
 * Pass 1 (Commit 2 i GAP-viewser-wizard-minimal-tabs):
 *   - Flikar: Inneh\u00e5ll (ContentOrchestratorStep) + Media (MediaStep).
 *   - Scaffold-aware utvidgning sker i ContentOrchestratorStep redan
 *     (den filtrerar produkter/meny/tj\u00e4nster/team/projekt utifr\u00e5n
 *     `branch`), s\u00e5 vi beh\u00f6ver inte duplicera den logiken h\u00e4r.
 *
 * Pass 2-3 (uppf\u00f6ljande commits, om operatorn vill):
 *   - Bryta upp ContentOrchestratorStep i finare flikar
 *     (Tj\u00e4nster, Produkter, Meny, Projekt, Team) baserat p\u00e5 `branch`.
 *   - Egen Kontakt-flik, egen Avancerat-flik (favicon/og/video).
 */

type MoreInfoTabId = "content" | "media";

const TABS: ReadonlyArray<{
  id: MoreInfoTabId;
  label: string;
  description: string;
}> = [
  {
    id: "content",
    label: "Inneh\u00e5ll",
    description:
      "Tj\u00e4nster, produkter, meny, team, projekt, om-text och kontakt. Fyll i s\u00e5 mycket du vill \u2014 fr\u00e5gor utan svar fylls senare av Vision/skrap.",
  },
  {
    id: "media",
    label: "Bilder & media",
    description:
      "Logotyp, hero, galleri, favicon, OG-bild och bakgrundsvideo. Allt valfritt \u2014 vi pickar default-bilder fr\u00e5n stilen om inget laddas upp.",
  },
];

export type MoreInfoDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  answers: WizardAnswers;
  onChange: (next: Partial<WizardAnswers>) => void;
  branch: ContentBranch;
};

export function MoreInfoDialog({
  open,
  onOpenChange,
  answers,
  onChange,
  branch,
}: MoreInfoDialogProps) {
  const [activeTab, setActiveTab] = useState<MoreInfoTabId>("content");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="border-border/60 bg-background grid h-[min(100dvh-3rem,720px)] !w-[min(100vw-2rem,960px)] !max-w-[min(100vw-2rem,960px)] grid-cols-1 gap-0 overflow-hidden border p-0 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.25)] sm:!max-w-[min(100vw-2rem,960px)] sm:rounded-3xl"
        showCloseButton={false}
      >
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="St\u00e4ng"
          className="text-muted-foreground hover:bg-foreground/5 hover:text-foreground min-tap sm:min-tap-0 absolute top-3 right-3 z-10 inline-flex items-center justify-center rounded-full transition-colors active:scale-95 sm:top-4 sm:right-4 sm:h-8 sm:w-8"
        >
          <X className="h-4 w-4" />
        </button>

        <DialogHeader className="space-y-0 px-5 pt-5 pb-3 text-left sm:px-8 sm:pt-6 sm:pb-4">
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <DialogTitle className="text-foreground text-[16px] leading-tight font-semibold tracking-tight sm:text-[17px]">
              Mer information
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-[12.5px] leading-relaxed">
              Detaljer fr\u00e5n din nuvarande hemsida fylls i automatiskt.
            </DialogDescription>
          </div>
        </DialogHeader>

        <div className="border-border/60 border-b px-5 sm:px-8">
          <div role="tablist" aria-label="Mer information" className="flex gap-1">
            {TABS.map((tab) => {
              const isActive = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setActiveTab(tab.id)}
                  className={[
                    "relative -mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-[12.5px] font-medium tracking-tight transition-colors",
                    isActive
                      ? "text-foreground border-foreground"
                      : "text-muted-foreground hover:text-foreground border-transparent",
                  ].join(" ")}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-8 sm:py-6">
          <div className="mx-auto max-w-2xl">
            <p className="text-muted-foreground/85 mb-5 flex items-start gap-2 text-[12px] leading-relaxed">
              <Info className="text-muted-foreground/60 mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>
                {TABS.find((tab) => tab.id === activeTab)?.description}
              </span>
            </p>

            {activeTab === "content" ? (
              <ContentOrchestratorStep
                answers={answers}
                onChange={onChange}
                branch={branch}
              />
            ) : null}
            {activeTab === "media" ? (
              <MediaStep answers={answers} onChange={onChange} />
            ) : null}
          </div>
        </div>

        <div className="border-border/60 bg-background/95 flex items-center justify-end gap-2 border-t px-4 py-3 pb-safe-or-4 sm:px-6 sm:py-4">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="text-muted-foreground hover:text-foreground min-tap sm:min-tap-0 h-9 px-3 text-[12.5px] font-medium"
          >
            St\u00e4ng
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={() => onOpenChange(false)}
            className="bg-foreground text-background hover:bg-foreground/90 min-tap sm:min-tap-0 h-9 rounded-full px-5 text-[12.5px] font-medium shadow-sm"
          >
            Klar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
