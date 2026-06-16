"use client";

import Link from "next/link";
import { useEffect } from "react";

// Root-nivå error boundary (måste vara en klientkomponent). Fångar oväntade
// runtime-fel i hela trädet och visar en lugn, on-brand fallback istället för
// Next:s tekniska standardsida. ``reset`` försöker rendera om segmentet.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Logga till konsolen så felet syns i Vercel-loggar/analys utan att
    // exponera detaljer för besökaren.
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center">
      <p className="text-muted-foreground/70 font-mono text-[13px] tracking-wide">
        Något gick fel
      </p>
      <h1 className="text-foreground mt-3 max-w-[22ch] text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        Oj, här blev det ett fel
      </h1>
      <p className="text-muted-foreground mt-4 max-w-[44ch] text-[15px] leading-relaxed sm:text-[16px]">
        Något oväntat hände när sidan skulle laddas. Försök igen — om det
        återkommer, ladda om sidan eller gå tillbaka till startsidan.
      </p>

      <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
        <button
          type="button"
          onClick={reset}
          className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          Försök igen
        </button>
        <Link
          href="/"
          className="text-foreground border-border/60 hover:bg-foreground/[0.04] focus-visible:ring-ring/50 inline-flex h-12 items-center rounded-full border px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          Till startsidan
        </Link>
      </div>

      {error.digest ? (
        <p className="text-muted-foreground/50 mt-8 font-mono text-[11px]">
          Felreferens: {error.digest}
        </p>
      ) : null}
    </main>
  );
}
