"use client";

import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import type { PromptStage } from "@/components/prompt-builder";

// BuildProgressCard — dominant central laddningsmodul som
// ``ViewerPanel`` mountar när bygget pågår. Extraherad ur
// ``viewer-panel.tsx`` (1182 rader → ~1020) som ren textextraktion,
// inga beteendeändringar. Allt som följer med (BUILD_STEPS,
// stageToStepIndex, PREVIEW_PREP_HINT) används bara här.
//
// Komponenten är fortfarande client-side eftersom den har sin egen
// elapsed-sek-timer (useState + useEffect).
//
// PREVIEW_PREP_HINT läser samma `NEXT_PUBLIC_VIEWSER_PREVIEW_MODE`
// som viewer-panel.tsx — Next.js inlinear `process.env.NEXT_PUBLIC_*`
// vid build-tid så båda får samma värde utan delad konstant.
//
// Normaliseringen MÅSTE matcha viewer-panel.tsx exakt
// (``.trim().toLowerCase()``) annars kan en operatör som råkar sätta
// ``LOCAL-NEXT`` eller `` local-next `` få olika hint vs preview-mode
// i ViewerPanel — splitten introducerade tidigare bara ``.trim()`` här.
const VIEWSER_PREVIEW_MODE = (
  process.env.NEXT_PUBLIC_VIEWSER_PREVIEW_MODE ?? "local-next"
)
  .trim()
  .toLowerCase();
const IS_LOCAL_NEXT_MODE = VIEWSER_PREVIEW_MODE === "local-next";

// Mode-aware UI-copy för preview-steget. local-next-mode startar en
// lokal ``next start``-server, stackblitz-mode laddar upp till
// StackBlitz-iframen — operatören förtjänar rätt mental modell.
// Texten är kundvänlig — inga tekniska termer (preview-server,
// next start, StackBlitz, iframe) eftersom slutkunden inte ska
// behöva förstå pipelinen för att vänta i lugn och ro.
const PREVIEW_PREP_HINT = IS_LOCAL_NEXT_MODE
  ? "Snart kan du klicka runt på er sajt."
  : "Laddar förhandsvisningen i webbläsaren.";

const BUILD_STEPS: ReadonlyArray<{
  id: "prepare" | "generate" | "build" | "preview";
  title: string;
  hint: string;
}> = [
  {
    id: "prepare",
    title: "Läser dina svar",
    hint: "Vi går igenom det du har fyllt i i wizarden.",
  },
  {
    id: "generate",
    title: "Planerar sajten",
    hint: "Vi väljer rätt struktur, ton och funktioner för er verksamhet.",
  },
  {
    id: "build",
    title: "Bygger sajten",
    hint: "Vi monterar alla sidor och bilder. Första bygget tar 1–3 minuter, sedan går det snabbare.",
  },
  {
    id: "preview",
    title: "Öppnar förhandsvisning",
    hint: PREVIEW_PREP_HINT,
  },
];

function stageToStepIndex(stage: PromptStage): number {
  switch (stage) {
    case "idle":
      return 0;
    case "thinking":
      return 1;
    case "building":
      return 2;
    case "success":
    case "degraded":
    case "failed":
      return 3;
    default:
      return 0;
  }
}

export function BuildProgressCard({ stage }: { stage: PromptStage }) {
  const activeIdx = stageToStepIndex(stage);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const minutes = Math.floor(elapsedSec / 60);
  const seconds = (elapsedSec % 60).toString().padStart(2, "0");

  return (
    <div className="border-border/60 bg-background/95 w-full max-w-[560px] rounded-3xl border p-9 shadow-[0_32px_80px_-16px_rgba(0,0,0,0.25)] backdrop-blur-xl">
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-foreground text-[17px] font-semibold tracking-tight">
          Bygger din sajt
        </h2>
        <span className="bg-muted/50 text-foreground rounded-full px-2.5 py-1 font-mono text-[11px] tracking-tight tabular-nums">
          {minutes}:{seconds}
        </span>
      </div>

      <ol className="flex flex-col gap-0.5">
        {BUILD_STEPS.map((step, idx) => {
          const isActive = idx === activeIdx;
          const isPast = idx < activeIdx;
          const isFuture = idx > activeIdx;
          return (
            <li
              key={step.id}
              className={[
                "flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors",
                isActive ? "bg-foreground/[0.04]" : "",
              ].join(" ")}
            >
              <span
                className={[
                  "mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] transition-colors",
                  isPast
                    ? "bg-foreground text-background"
                    : isActive
                      ? "bg-foreground text-background"
                      : "border-border/70 bg-background text-muted-foreground/70 border",
                ].join(" ")}
              >
                {isPast ? (
                  <Check aria-hidden className="h-3 w-3" strokeWidth={2.5} />
                ) : isActive ? (
                  <Loader2 aria-hidden className="h-3 w-3 animate-spin" />
                ) : (
                  <span className="font-mono text-[9.5px] tracking-tight">
                    {idx + 1}
                  </span>
                )}
              </span>
              <div className="flex flex-1 flex-col leading-snug">
                <span
                  className={[
                    "text-[13px] font-medium tracking-tight",
                    isFuture ? "text-muted-foreground" : "text-foreground",
                  ].join(" ")}
                >
                  {step.title}
                </span>
                <span
                  className={[
                    "text-[11.5px] leading-relaxed",
                    isActive
                      ? "text-muted-foreground"
                      : "text-muted-foreground/70",
                  ].join(" ")}
                >
                  {step.hint}
                </span>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="bg-border/50 mt-6 h-[2px] w-full overflow-hidden rounded-full">
        <div
          className="bg-foreground/80 h-full animate-pulse rounded-full transition-[width] duration-500 ease-out"
          style={{
            width: `${((activeIdx + 1) / BUILD_STEPS.length) * 100}%`,
          }}
        />
      </div>
    </div>
  );
}
