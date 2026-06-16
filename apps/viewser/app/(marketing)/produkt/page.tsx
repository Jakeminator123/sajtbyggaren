import type { Metadata } from "next";
import Link from "next/link";

import { STUDIO_HREF } from "@/lib/routes";

export const metadata: Metadata = {
  title: "Produkt",
  description:
    "Så fungerar Sajtbyggaren: beskriv din verksamhet, få en färdig företagshemsida, förhandsgranska och förfina med ord.",
};

// Fyra-stegs-loopen — samma kärnflöde som startsidan men med lite mer kött på
// benen. Håll texten ärlig mot vad byggaren faktiskt gör (prompt -> hemsida ->
// preview -> följdprompt -> ny version).
const STEPS: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "Beskriv",
    body: "Skriv en mening om din verksamhet — eller börja från en bransch så förfyller vi resten. Du kan lägga till logotyp, bilder och egen text om du vill.",
  },
  {
    title: "Bygg",
    body: "AI:n skapar en komplett företagshemsida med flera sidor, texter och bilder — anpassad efter din bransch och stil.",
  },
  {
    title: "Förhandsgranska",
    body: "Se din färdiga sida live direkt i webbläsaren och klicka runt — innan något publiceras.",
  },
  {
    title: "Förfina",
    body: "Be om ändringar i vanlig svenska, t.ex. ”gör tonen varmare” eller ”lägg till en prislista”. Vi bygger om och visar en ny version.",
  },
];

// Vad en genererad sida kan innehålla. Speglar de sid- och innehållstyper som
// bygg-flödet faktiskt erbjuder — inga överlöften.
const INCLUDES: ReadonlyArray<{ title: string; body: string }> = [
  {
    title: "Färdiga sidor",
    body: "Startsida, om oss, tjänster eller priser, kontakt, galleri, FAQ med mera — vi väljer det som passar din verksamhet.",
  },
  {
    title: "Texter och bilder",
    body: "AI:n skriver innehållet och föreslår bilder. Ladda upp egna när du vill — annars genererar vi passande.",
  },
  {
    title: "Egen känsla",
    body: "Färger, typografi och stil väljs efter din bransch. Du kan styra uttrycket utan att rita en enda pixel.",
  },
  {
    title: "Mobilanpassat",
    body: "Sidan ser bra ut i mobil, surfplatta och dator från start — utan extra jobb.",
  },
  {
    title: "Hittbar på Google",
    body: "Rubriker, sidtitlar och social förhandsvisning sätts automatiskt så att sidan går att hitta och dela.",
  },
  {
    title: "Kontaktväg",
    body: "Besökaren kan nå dig — kontaktuppgifter och formulär finns med där det behövs.",
  },
];

export default function ProductPage() {
  return (
    <>
      <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8">
        {/* 1. Hero. */}
        <section className="pt-20 pb-16 sm:pt-28 sm:pb-24">
          <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
            Produkt
          </p>
          <h1 className="text-foreground mt-5 max-w-[20ch] text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            Från en mening till en färdig hemsida.
          </h1>
          <p className="text-muted-foreground mt-5 max-w-[52ch] text-[16px] leading-relaxed sm:text-[18px]">
            Sajtbyggaren skapar en komplett företagshemsida åt dig med AI. Du
            beskriver din verksamhet med egna ord, ser resultatet direkt och
            förfinar tills det sitter — inga mallar, inga utvecklare.
          </p>
          <Link
            href={STUDIO_HREF}
            className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 mt-8 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
          >
            Bygg din hemsida
          </Link>
        </section>

        {/* 2. Så funkar det — fyra steg i en loop. */}
        <section className="border-border/60 border-t py-24 sm:py-32">
          <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
            Så funkar det
          </h2>
          <p className="text-muted-foreground mt-2 max-w-[48ch] text-[15px] leading-relaxed">
            Fyra steg, om och om igen — tills sidan sitter precis rätt.
          </p>
          <ol className="border-border/60 bg-border/60 mt-10 grid gap-px overflow-hidden rounded-3xl border sm:grid-cols-2 lg:grid-cols-4">
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

        {/* 3. Vad ingår — feature-rutnät. */}
        <section className="border-border/60 border-t py-24 sm:py-32">
          <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
            Vad du får
          </h2>
          <p className="text-muted-foreground mt-2 max-w-[48ch] text-[15px] leading-relaxed">
            En riktig företagshemsida — inte ett skal. Allt är med från start.
          </p>
          <div className="border-border/60 bg-border/60 mt-10 grid gap-px overflow-hidden rounded-3xl border sm:grid-cols-2 lg:grid-cols-3">
            {INCLUDES.map((item) => (
              <div
                key={item.title}
                className="bg-background flex flex-col gap-2 p-6"
              >
                <span className="text-foreground text-[16px] font-semibold tracking-tight">
                  {item.title}
                </span>
                <span className="text-muted-foreground text-[14px] leading-relaxed">
                  {item.body}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* 4. Förfina med ord — kärnan i loopen, ärligt beskriven. */}
        <section className="border-border/60 border-t py-24 sm:py-32">
          <div className="grid gap-10 lg:grid-cols-[1fr_1.1fr] lg:items-center">
            <div>
              <h2 className="text-foreground text-2xl font-semibold tracking-tight sm:text-3xl">
                Förfina med ord
              </h2>
              <p className="text-muted-foreground mt-4 max-w-[46ch] text-[16px] leading-relaxed">
                Sajten är aldrig låst. Beskriv en ändring i vanlig svenska så
                tolkar vi den och visar en ny version — du behöver aldrig öppna
                en kodredigerare.
              </p>
            </div>
            <ul className="border-border/60 bg-border/60 grid gap-px overflow-hidden rounded-3xl border">
              {[
                "”Byt rubriken på startsidan till Välkommen till verkstan.”",
                "”Lägg till en sida med våra priser.”",
                "”Gör tonen mer personlig och varm.”",
                "”Använd den blå färgen från vår logotyp.”",
              ].map((example) => (
                <li
                  key={example}
                  className="bg-background text-foreground/90 px-6 py-4 text-[15px] leading-relaxed"
                >
                  {example}
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      {/* 5. Slut-CTA — inverterad, speglar startsidan. */}
      <section className="bg-foreground text-background">
        <div className="mx-auto flex w-full max-w-[1200px] flex-col items-center gap-6 px-5 py-28 text-center sm:px-8 sm:py-36">
          <h2 className="max-w-[20ch] text-3xl font-semibold tracking-tight text-balance sm:text-5xl">
            Redo att se din hemsida ta form?
          </h2>
          <Link
            href={STUDIO_HREF}
            className="bg-background text-foreground hover:bg-background/90 focus-visible:ring-background/60 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
          >
            Bygg din hemsida
          </Link>
        </div>
      </section>
    </>
  );
}
