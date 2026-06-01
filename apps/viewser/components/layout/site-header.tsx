"use client";

import Image from "next/image";

type SiteHeaderProps = {
  onOpenConsole: () => void;
  /**
   * Döljer brand-bubblan (Sajtbyggaren-logon längst upp till vänster)
   * men behåller konsol-knappen i höger hörn. Används av builder-läget
   * eftersom logon ligger ovanpå preview-iframens vänsterkant och
   * stör webbdesignen som operatören granskar. Default `false` så
   * pre-build-vyn (hero + DiscoveryWizard) fortfarande visar
   * brandidentiteten.
   */
  hideBrand?: boolean;
};

export function SiteHeader({ onOpenConsole, hideBrand = false }: SiteHeaderProps) {
  return (
    <div
      aria-hidden={false}
      className="pointer-events-none absolute inset-x-0 top-0 z-30 flex items-start justify-between gap-3 px-4 pt-3 pt-safe sm:px-6 sm:pt-4"
    >
      {hideBrand ? (
        // Tom spacer så `justify-between` ändå skjuter konsol-knappen
        // till höger kant utan att brand-bubblan tar upp click-target-
        // ytan över previewens vänstersida.
        <div aria-hidden className="pointer-events-none" />
      ) : (
        <div className="pointer-events-auto inline-flex items-center rounded-full border border-border/60 bg-card/80 px-3 py-1 shadow-sm backdrop-blur-xl">
          <Brandmark />
        </div>
      )}

      <button
        type="button"
        onClick={onOpenConsole}
        aria-label="Öppna konsol och run-historik (genväg ⌘K)"
        // title gör ⌘K-genvägen upptäckbar INNAN konsolen öppnats — annars
        // syns hinten bara inuti den redan öppna drawern (console-drawer.tsx).
        title="Konsol & run-historik — ⌘K (Ctrl+K på Windows)"
        className="pointer-events-auto flex min-tap sm:min-tap-0 sm:size-9 items-center justify-center rounded-full border border-border/60 bg-card/80 text-foreground/80 shadow-sm backdrop-blur-xl transition hover:bg-card hover:text-foreground active:bg-card active:scale-95"
      >
        <ConsoleIcon />
      </button>
    </div>
  );
}

function Brandmark() {
  return (
    <Image
      src="/sajtbyggaren_logo.png"
      alt="Sajtbyggaren"
      width={115}
      height={28}
      priority
      // height styrs av ``h-7``; ``style.width: auto`` bevarar aspect-ratio
      // OCH tystar Next:s "width or height modified, but not the other"-
      // varning (Next läser inline-style, inte Tailwind-klassen w-auto).
      style={{ width: "auto" }}
      className="h-7 w-auto object-contain"
    />
  );
}

function ConsoleIcon() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
    </svg>
  );
}
