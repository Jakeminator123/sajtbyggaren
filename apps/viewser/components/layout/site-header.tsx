"use client";

type SiteHeaderProps = {
  onOpenConsole: () => void;
};

export function SiteHeader({ onOpenConsole }: SiteHeaderProps) {
  return (
    <div
      aria-hidden={false}
      className="pointer-events-none absolute inset-x-0 top-0 z-30 flex items-start justify-between gap-3 px-4 pt-3 sm:px-6 sm:pt-4"
    >
      <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-border/60 bg-card/80 px-3 py-1.5 text-[12px] shadow-sm backdrop-blur-xl">
        <Brandmark />
        <span className="font-medium tracking-tight">Sajtbyggaren</span>
      </div>

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
    <span
      aria-hidden
      className="flex size-5 items-center justify-center rounded-[6px] bg-foreground text-background"
    >
      <span className="text-[9px] font-semibold leading-none">SB</span>
    </span>
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
