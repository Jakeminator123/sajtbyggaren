import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { STUDIO_HREF } from "@/lib/routes";

export const metadata: Metadata = {
  title: "Sidan kunde inte hittas",
  description: "Sidan du letar efter finns inte längre eller har flyttat.",
};

// Root-nivå 404. Renderas inom rot-layouten (utan marknadssajtens header/footer),
// så sidan är medvetet självbärande och centrerad. Samma tokens som
// marknadssidorna (bg-background/text-foreground, rundad pill-CTA).
export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center px-6 py-20 text-center">
      <Link
        href="/"
        aria-label="Sajtbyggaren — till startsidan"
        className="focus-visible:ring-ring/50 inline-flex items-center rounded-md focus-visible:ring-2 focus-visible:outline-none"
      >
        <Image
          src="/sajtbyggaren_logo.png"
          alt="Sajtbyggaren"
          width={120}
          height={29}
          priority
          style={{ width: "auto" }}
          className="h-7 w-auto object-contain"
        />
      </Link>

      <p className="text-muted-foreground/70 mt-12 font-mono text-[13px] tracking-wide">
        404
      </p>
      <h1 className="text-foreground mt-3 max-w-[20ch] text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        Sidan kunde inte hittas
      </h1>
      <p className="text-muted-foreground mt-4 max-w-[44ch] text-[15px] leading-relaxed sm:text-[16px]">
        Sidan du letar efter finns inte längre eller har flyttat. Den kan ha
        fått en ny adress.
      </p>

      <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
        <Link
          href="/"
          className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          Till startsidan
        </Link>
        <Link
          href={STUDIO_HREF}
          className="text-foreground border-border/60 hover:bg-foreground/[0.04] focus-visible:ring-ring/50 inline-flex h-12 items-center rounded-full border px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          Bygg din hemsida
        </Link>
      </div>
    </main>
  );
}
