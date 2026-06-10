"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * BuildProgressBanner — nordiskt minimal laddningsbanner som visas över
 * previewn medan ett placerings-bygge pågår (operatörskrav 2026-06-10:
 * efter "Placera här" ska kunden INTE skickas tillbaka till dialogen,
 * utan se en lugn 0–100-banner med fraser som blurras in och ut).
 *
 * Renderas av ViewerPanel I STÄLLET för BuildProgressCard när bygget
 * kommer från ett bekräftat placerings-släpp (placementBuildActive i
 * preview-inspector-contexten) — aldrig båda samtidigt. Den absoluta
 * containern bär sin egen backdrop-blur så bytet kort↔banner är
 * symmetriskt.
 *
 * Ärlighet i procenten: bygget rapporterar ingen riktig progress, så
 * siffran är en mjuk easing-ramp mot 95 % (samma filosofi som
 * PROGRESS_RAMP_DURATION_MS i FloatingChat) — hoppet till 100 % sker
 * först när bygget faktiskt är klart (active → false), följt av en
 * kort uttoning till den nya previewn.
 *
 * Pointer-events-none: bannern blockerar aldrig canvasen eller chatten.
 */

/** Fraser som roterar med blur-övergång medan bygget pågår. */
const PHRASES = [
  "Placerar ditt element",
  "Bygger om sajten",
  "Formger detaljerna",
  "Snart klart",
] as const;

/** Tidskonstant (s) för easing-rampen — ~87 % efter 45 s. */
const RAMP_TAU_SECONDS = 22;
/** Frasväxlingens kadens inkl. blur-ut/-in. */
const PHRASE_INTERVAL_MS = 3600;
const PHRASE_BLUR_MS = 450;
/** Hur länge 100 % visas innan bannern tonas ut. */
const EXIT_HOLD_MS = 900;

export function BuildProgressBanner({ active }: { active: boolean }) {
  // visible släpar efter active så 100 %-hoppet + uttoningen hinner visas.
  const [visible, setVisible] = useState(false);
  const [progress, setProgress] = useState(0);
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [phraseShown, setPhraseShown] = useState(true);
  const [exiting, setExiting] = useState(false);
  const startedAtRef = useRef<number>(0);

  // Aktivera/avveckla. setTimeout(0) deferar setState ur effektkroppen
  // (react-hooks/set-state-in-effect, samma mönster som övriga appen).
  useEffect(() => {
    if (active) {
      startedAtRef.current = Date.now();
      const timerId = window.setTimeout(() => {
        setVisible(true);
        setExiting(false);
        setProgress(0);
        setPhraseIndex(0);
        setPhraseShown(true);
      }, 0);
      return () => window.clearTimeout(timerId);
    }
    // Bygget klart (eller avbrutet): hoppa till 100, håll kort, tona ut.
    const doneId = window.setTimeout(() => {
      setProgress(100);
      setExiting(true);
    }, 0);
    const hideId = window.setTimeout(() => {
      setVisible(false);
      setProgress(0);
    }, EXIT_HOLD_MS);
    return () => {
      window.clearTimeout(doneId);
      window.clearTimeout(hideId);
    };
  }, [active]);

  // Easing-ramp mot 95 % medan bygget pågår.
  useEffect(() => {
    if (!visible || !active) return;
    const intervalId = window.setInterval(() => {
      const t = (Date.now() - startedAtRef.current) / 1000;
      setProgress(
        Math.min(95, Math.round(95 * (1 - Math.exp(-t / RAMP_TAU_SECONDS)))),
      );
    }, 150);
    return () => window.clearInterval(intervalId);
  }, [visible, active]);

  // Frasrotation med blur-ut → byt → blur-in.
  useEffect(() => {
    if (!visible || !active) return;
    const intervalId = window.setInterval(() => {
      setPhraseShown(false);
      window.setTimeout(() => {
        setPhraseIndex((i) => (i + 1) % PHRASES.length);
        setPhraseShown(true);
      }, PHRASE_BLUR_MS);
    }, PHRASE_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [visible, active]);

  if (!visible && !active) return null;

  return (
    <div
      aria-live="polite"
      className={cn(
        "bg-background/85 pointer-events-none absolute inset-0 z-20 flex items-center justify-center px-6 backdrop-blur-sm transition-opacity duration-500",
        exiting ? "opacity-0" : "opacity-100",
      )}
    >
      <div className="border-border/50 bg-background/90 flex w-[min(380px,calc(100%-3rem))] flex-col items-center gap-5 rounded-2xl border px-10 py-9 shadow-2xl backdrop-blur-xl">
        <span className="text-foreground font-light tabular-nums tracking-tight">
          <span className="text-5xl">{progress}</span>
          <span className="text-muted-foreground ml-1 text-xl">%</span>
        </span>

        {/* Hårfin progress-linje. */}
        <div className="bg-border/60 h-px w-full overflow-hidden rounded-full">
          <div
            className="bg-foreground h-full rounded-full transition-[width] duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        <span
          className={cn(
            "text-muted-foreground text-[13px] tracking-wide transition-[opacity,filter] duration-[450ms] ease-in-out",
            phraseShown && !exiting
              ? "opacity-100 blur-0"
              : "opacity-0 blur-[6px]",
          )}
        >
          {exiting ? "Klart" : PHRASES[phraseIndex]}
        </span>
      </div>
    </div>
  );
}
