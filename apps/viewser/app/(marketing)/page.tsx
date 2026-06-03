import type { Metadata } from "next";
import Link from "next/link";

import { HeroPromptForm } from "@/components/marketing/hero-prompt-form";
import { HeroVideo } from "@/components/marketing/hero-video";
import { ProfessionGrid } from "@/components/marketing/profession-grid";

export const metadata: Metadata = {
  description:
    "Beskriv din verksamhet — Sajtbyggaren bygger en färdig företagshemsida åt dig med AI. Förhandsgranska och förfina med ord.",
};

const STEPS: ReadonlyArray<{ title: string; body: string }> = [
  { title: "Beskriv", body: "Berätta kort vad ditt företag gör och vem ni är." },
  { title: "Bygg", body: "AI:n skapar en komplett företagshemsida på minuter." },
  { title: "Förhandsgranska", body: "Se din sida live direkt — inget krångel." },
  { title: "Förfina", body: "Be om ändringar med ord. Vi bygger om åt dig." },
];

export default function MarketingHome() {
  return (
    <>
      {/* 1. Hero — full-bleed video, få ord, prompt-CTA. id="start" = mål för
          slut-CTA:n så all bygg-start sker här på heron. */}
      <section
        id="start"
        className="relative flex h-[100svh] min-h-[560px] items-end overflow-hidden scroll-mt-16"
      >
        <HeroVideo />
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-t from-black/65 via-black/25 to-black/35"
        />
        <div className="relative mx-auto w-full max-w-[1200px] px-5 pb-16 sm:px-8 sm:pb-24">
          <h1 className="max-w-[18ch] text-4xl font-semibold tracking-tight text-balance text-white sm:text-6xl">
            Din hemsida, byggd medan du beskriver den.
          </h1>
          <p className="mt-4 max-w-[48ch] text-[16px] leading-relaxed text-white/80 sm:text-[18px]">
            Sajtbyggaren skapar en färdig företagshemsida åt dig med AI. Du
            förfinar med ord — vi bygger om.
          </p>
          {/* Bygg-CTA:n bor numera HÄR — besökaren beskriver sin sajt direkt
              på heron och landar i bygg-flödet (DiscoveryWizard förifylld)
              utan att passera studions tomma prompt-landning. */}
          <HeroPromptForm />
        </div>
      </section>

      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        {/* 2. Värdelöfte — stor whitespace, minimal copy. */}
        <section className="py-28 text-center sm:py-40">
          <p className="text-muted-foreground mx-auto max-w-[26ch] text-[13px] font-medium tracking-wide uppercase">
            För dem som bygger Sverige
          </p>
          <p className="text-foreground mx-auto mt-6 max-w-[20ch] text-3xl font-semibold tracking-tight text-balance sm:max-w-[24ch] sm:text-5xl">
            Inga mallar att slåss med. Inga utvecklare att jaga.
          </p>
          <p className="text-muted-foreground mx-auto mt-5 max-w-[52ch] text-[16px] leading-relaxed sm:text-[18px]">
            Bara din verksamhet, beskriven med dina egna ord — och en hemsida
            som känns som er.
          </p>
        </section>

        {/* 3. Så funkar det — fyra steg i en loop. */}
        <section className="border-border/60 border-t py-24 sm:py-32">
          <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
            Så funkar det
          </h2>
          <p className="text-muted-foreground mt-2 max-w-[48ch] text-[15px] leading-relaxed">
            Fyra steg, om och om igen — tills sidan sitter precis rätt.
          </p>
          <ol className="mt-10 grid gap-px overflow-hidden rounded-3xl border border-border/60 bg-border/60 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <li
                key={step.title}
                className="bg-background flex flex-col gap-2 p-6"
              >
                <span className="text-muted-foreground/70 font-mono text-[12px]">
                  0{i + 1}
                </span>
                <span className="text-foreground text-[17px] font-semibold tracking-tight">
                  {step.title}
                </span>
                <span className="text-muted-foreground text-[14px] leading-relaxed">
                  {step.body}
                </span>
              </li>
            ))}
          </ol>
        </section>

        {/* 4. Bildvägg — varje bransch får en sida som känns som deras. */}
        <section className="border-border/60 border-t py-24 sm:py-32">
          <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
            En sida för varje bransch
          </h2>
          <p className="text-muted-foreground mt-2 mb-10 max-w-[48ch] text-[15px] leading-relaxed">
            Från bilverkstad till bageri — bilderna skapar känslan, orden gör
            den till er.
          </p>
          <ProfessionGrid />
        </section>
      </div>

      {/* 5. Känsla/citat — full-bleed, lugn. */}
      <section className="border-border/60 bg-muted/40 border-y py-28 sm:py-40">
        <div className="mx-auto w-full max-w-[1000px] px-5 text-center sm:px-8">
          <p className="text-foreground text-2xl font-medium tracking-tight text-balance sm:text-4xl">
            “Lämna huvudvärken att bygga och underhålla en hemsida med oss.”
          </p>
        </div>
      </section>

      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        {/* 6. Grundar-teaser → /om-oss. */}
        <section className="py-24 text-center sm:py-32">
          <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
            Byggt av två som bryr sig
          </p>
          <p className="text-foreground mx-auto mt-5 max-w-[44ch] text-xl leading-relaxed text-balance sm:text-2xl">
            Jakob och Christopher — två killar som älskar (och fruktar) AI, och
            vill använda den för att hjälpa små företag.
          </p>
          <Link
            href="/om-oss"
            className="text-foreground hover:text-foreground/70 focus-visible:ring-ring/50 mt-6 inline-flex items-center gap-1 rounded text-[15px] font-medium underline-offset-4 transition-colors hover:underline focus-visible:ring-2 focus-visible:outline-none"
          >
            Läs mer om oss →
          </Link>
        </section>
      </div>

      {/* 7. Slut-CTA — inverterad. */}
      <section className="bg-foreground text-background">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col items-center gap-6 px-5 py-28 text-center sm:px-8 sm:py-36">
          <h2 className="max-w-[20ch] text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
            Redo att se din hemsida ta form?
          </h2>
          {/* Scrollar upp till hero-prompten (#start) i stället för studions
              tomma landning — all bygg-start sker via heron. */}
          <a
            href="#start"
            className="bg-background text-foreground hover:bg-background/90 focus-visible:ring-background/60 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
          >
            Bygg din hemsida
          </a>
        </div>
      </section>
    </>
  );
}
