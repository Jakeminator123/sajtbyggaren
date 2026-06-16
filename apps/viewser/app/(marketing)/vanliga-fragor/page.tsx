import type { Metadata } from "next";
import Link from "next/link";

import { STUDIO_HREF } from "@/lib/routes";

export const metadata: Metadata = {
  title: "Vanliga frågor",
  description:
    "Svar på de vanligaste frågorna om Sajtbyggaren — hur det fungerar, vad som ingår och hur du förfinar din hemsida.",
};

// FAQ-sida. Native <details>/<summary> ger tillgänglig öppna/stäng utan
// klientkod (tangentbord + skärmläsare fungerar direkt). Svaren hålls ärliga
// mot vad bygg-flödet faktiskt gör — inga löften om pris/domän vi inte kan
// hålla; sånt hänvisas till kontakt.
const FAQS: ReadonlyArray<{ q: string; a: string }> = [
  {
    q: "Hur fungerar Sajtbyggaren?",
    a: "Du beskriver din verksamhet med egna ord. AI:n skapar en komplett företagshemsida med flera sidor, texter och bilder. Du förhandsgranskar den live och förfinar med ord tills den sitter.",
  },
  {
    q: "Behöver jag kunna något tekniskt?",
    a: "Nej. Du behöver varken koda, välja mallar eller rita. Beskriv vad ditt företag gör i vanlig svenska, så sköter vi resten.",
  },
  {
    q: "Vad ingår i en sida?",
    a: "En riktig företagshemsida med flera sidor — startsida, om oss, tjänster eller priser, kontakt, galleri och FAQ där det passar. Texter och bilder ingår, och sidan är mobilanpassad från start.",
  },
  {
    q: "Kan jag ändra sidan efteråt?",
    a: "Ja. Sidan är aldrig låst. Beskriv en ändring i text — till exempel ”gör tonen varmare” eller ”lägg till en prislista” — så bygger vi om och visar en ny version.",
  },
  {
    q: "Kan jag använda min egen logotyp och egna bilder?",
    a: "Ja, ladda upp logotyp och bilder när du vill. Gör du inte det genererar vi passande automatiskt — till exempel ett bokstavsmonogram som logotyp och en toppbild som matchar din bransch.",
  },
  {
    q: "Hur lång tid tar det?",
    a: "Det första bygget tar oftast någon eller några minuter. Varje gång du ber om en ändring bygger vi om och visar den nya versionen.",
  },
  {
    q: "Syns sidan på Google?",
    a: "Rubriker, sidtitlar och social förhandsvisning sätts automatiskt så att sidan går att hitta i sökmotorer och ser bra ut när den delas.",
  },
  {
    q: "Vad kostar det?",
    a: "Vi är i en tidig fas och finjusterar fortfarande erbjudandet. Hör av dig så berättar vi vad som gäller just nu.",
  },
];

export default function FaqPage() {
  return (
    <div className="mx-auto w-full max-w-[760px] px-5 sm:px-8">
      {/* Hero. */}
      <section className="pt-20 pb-12 sm:pt-28 sm:pb-16">
        <p className="text-muted-foreground text-[13px] font-medium tracking-wide uppercase">
          Vanliga frågor
        </p>
        <h1 className="text-foreground mt-5 max-w-[20ch] text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Det du undrar, kort och ärligt.
        </h1>
        <p className="text-muted-foreground mt-5 max-w-[52ch] text-[16px] leading-relaxed sm:text-[18px]">
          Hittar du inte svaret här?{" "}
          <Link
            href="/kontakt"
            className="text-foreground underline-offset-4 hover:underline"
          >
            Hör av dig
          </Link>{" "}
          så hjälper vi dig.
        </p>
      </section>

      {/* Frågor. */}
      <section className="border-border/60 border-t py-10 sm:py-14">
        <ul className="border-border/60 bg-border/60 grid gap-px overflow-hidden rounded-3xl border">
          {FAQS.map((item) => (
            <li key={item.q} className="bg-background">
              <details className="group">
                <summary className="text-foreground focus-visible:ring-ring/50 flex cursor-pointer items-center justify-between gap-4 px-6 py-5 text-[16px] font-medium tracking-tight focus-visible:ring-2 focus-visible:outline-none [&::-webkit-details-marker]:hidden">
                  {item.q}
                  <span
                    aria-hidden
                    className="text-muted-foreground/70 shrink-0 text-[20px] leading-none transition-transform group-open:rotate-45"
                  >
                    +
                  </span>
                </summary>
                <p className="text-muted-foreground px-6 pb-5 text-[15px] leading-relaxed">
                  {item.a}
                </p>
              </details>
            </li>
          ))}
        </ul>
      </section>

      {/* CTA. */}
      <section className="border-border/60 border-t py-16 sm:py-24">
        <Link
          href={STUDIO_HREF}
          className="bg-foreground text-background hover:bg-foreground/90 focus-visible:ring-ring/50 inline-flex h-12 items-center rounded-full px-7 text-[15px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none active:scale-[0.98]"
        >
          Bygg din hemsida
        </Link>
      </section>
    </div>
  );
}
