import type { Metadata } from "next";
import Link from "next/link";

import { FounderCard } from "@/components/marketing/founder-card";
import { LOGIN_HREF } from "@/lib/auth-config";

export const metadata: Metadata = {
  title: "Om oss",
  description:
    "Två killar som älskar och är rädda för AI — och vill använda den för att hjälpa små och medelstora företag i Sverige.",
};

const FOUNDERS: ReadonlyArray<{
  name: string;
  role: string;
  initials: string;
}> = [
  { name: "Jakob Eberg", role: "AI-fantast och smått galen", initials: "JE" },
  {
    name: "Christopher Genberg",
    role: "Fullstack-utvecklare & bipolär",
    initials: "CG",
  },
];

export default function AboutPage() {
  return (
    <div className="mx-auto w-full max-w-[800px] px-5 sm:px-8">
      {/* Hero. */}
      <section className="pt-20 pb-16 sm:pt-28 sm:pb-20">
        <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
          Om oss
        </p>
        <h1 className="text-foreground mt-5 max-w-[20ch] text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Vi vill underlätta vardagen för dem som bygger Sverige.
        </h1>
      </section>

      {/* Grundarna. */}
      <section className="border-border/60 border-t py-14 sm:py-20">
        <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
          Grundarna
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {FOUNDERS.map((f) => (
            <FounderCard
              key={f.initials}
              name={f.name}
              role={f.role}
              initials={f.initials}
            />
          ))}
        </div>
      </section>

      {/* Delad filosofi. */}
      <section className="border-border/60 border-t py-14 sm:py-20">
        <div className="space-y-5 text-[16px] leading-relaxed sm:text-[18px]">
          <p className="text-foreground">
            Vi är två killar som på riktigt älskar — och samtidigt är rädda för
            — utvecklingen av AI. Vi kan ta långa, filosofiska samtal om risken
            att AI tar över världen.
          </p>
          <p className="text-muted-foreground">
            Men vårt mål med Sajtbyggaren är enkelt: att använda AI för att
            hjälpa dem som bygger Sverige — de små och medelstora företagen —
            att få en enklare vardag.
          </p>
          <p className="text-foreground font-medium">
            Lämna huvudvärken att bygga och underhålla en hemsida med oss.
          </p>
        </div>
      </section>

      {/* CTA. */}
      <section className="border-border/60 border-t py-16 sm:py-24">
        <Link
          href={LOGIN_HREF}
          className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          Bygg din hemsida
        </Link>
      </section>
    </div>
  );
}
