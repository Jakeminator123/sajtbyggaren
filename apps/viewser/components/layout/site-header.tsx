"use client";

import Image from "next/image";

type SiteHeaderProps = {
  onOpenConsole: () => void;
  /**
   * Döljer brand-bubblan ("Sajtbyggaren"-logon längst upp till vänster)
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
      className="pointer-events-none absolute inset-x-0 top-0 z-30 flex items-start justify-between gap-3 px-4 pt-3 sm:px-6 sm:pt-4"
    >
      {hideBrand ? (
        // Tom spacer så `justify-between` ändå skjuter konsol-knappen
        // till höger kant utan att brand-bubblan tar upp click-target-
        // ytan över previewens vänstersida.
        <div aria-hidden className="pointer-events-none" />
      ) : (
        <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-border/60 bg-card/80 px-2.5 py-1 text-[12px] shadow-sm backdrop-blur-xl">
          <Brandmark />
          <span className="font-medium tracking-tight">Sajtbyggaren</span>
        </div>
      )}

      <button
        type="button"
        onClick={onOpenConsole}
        aria-label="Öppna konsol och run-historik"
        className="pointer-events-auto flex size-9 items-center justify-center rounded-full border border-border/60 bg-card/80 text-foreground/80 shadow-sm backdrop-blur-xl transition hover:bg-card hover:text-foreground"
      >
        <ConsoleIcon />
      </button>
    </div>
  );
}

function Brandmark() {
  return (
    <Image
      src="/LOGO_SM2.0.png"
      alt="Sajtmaskin 2.0"
      width={24}
      height={24}
      priority
      className="size-6 rounded-md object-contain"
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
