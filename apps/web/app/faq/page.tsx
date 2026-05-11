"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, ChevronDown } from "lucide-react";
import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";

const faqs = [
  {
    q: "Behöver jag kunna programmera?",
    a: "Nej, absolut inte. Sajtbyggaren är byggt för att vem som helst ska kunna skapa en professionell hemsida. Berätta bara om ditt företag så sköter AI:n resten. Under huven används React och Next.js, men du behöver aldrig röra en rad kod.",
  },
  {
    q: "Vilken teknik byggs mina sidor med?",
    a: "Alla sajter byggs med React 19, Next.js 16, TypeScript och Tailwind CSS, vilket ger hög prestanda, bra SEO och en kodbas som går att vidareutveckla när bolaget växer.",
  },
  {
    q: "Hur snabbt kan jag få en färdig sajt?",
    a: "Första utkastet genereras på några sekunder. Därefter kan du förfina, iterera och publicera samma dag om du vill.",
  },
  {
    q: "Kan jag använda min egen domän?",
    a: "Ja. Med rätt plan och setup kan du koppla din egen domän med automatisk SSL. Vi hjälper gärna till om du vill ha stöd hela vägen.",
  },
  {
    q: "Är det GDPR-anpassat?",
    a: "Ja. Plattformen är byggd med GDPR i åtanke och vi försöker hålla både datalagring och arbetsflöden så rena och relevanta som möjligt.",
  },
  {
    q: "Kan jag byta plan när som helst?",
    a: "Ja, du kan skala upp när du behöver mer tempo eller fler iterationer. Credits som du redan köpt ligger kvar.",
  },
];

function FaqItem({ q, a, id }: { q: string; a: string; id: string }) {
  const [open, setOpen] = useState(false);
  const answerId = `faq-answer-${id}`;

  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-card transition-colors hover:border-border/70">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-4 px-5 py-5 text-left"
        aria-expanded={open}
        aria-controls={answerId}
      >
        <span className="text-sm font-medium text-foreground md:text-base">
          {q}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      <div
        id={answerId}
        role="region"
        className={`overflow-hidden transition-all duration-300 ${
          open ? "max-h-72 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <p className="px-5 pb-5 text-sm leading-relaxed text-muted-foreground">
          {a}
        </p>
      </div>
    </div>
  );
}

export default function FAQPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Navbar />

      <main className="flex-1 pt-14">
        <section className="mx-auto max-w-5xl px-6 py-20 sm:py-24">
          <p className="mb-3 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Vanliga frågor
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            Frågor och svar om Sajtbyggaren
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">
            Här samlar vi de vanligaste frågorna om hur plattformen fungerar,
            vilken teknik som används och hur snabbt du kan gå från idé till
            publicerad sajt.
          </p>

          <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,1.2fr)_320px]">
            <div className="space-y-3">
              {faqs.map((faq, i) => (
                <FaqItem key={faq.q} q={faq.q} a={faq.a} id={String(i)} />
              ))}
            </div>

            <aside className="rounded-2xl border border-border bg-muted/30 p-6">
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                Fortfarande osäker?
              </p>
              <h2 className="mt-3 text-xl font-semibold text-foreground">
                Vi hjälper gärna till personligt.
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Om du vill bolla upplägg, credits, domän eller om ni behöver
                ett team runt lanseringen går det snabbt att höra av sig.
              </p>
              <div className="mt-6 space-y-3">
                <Button asChild className="w-full">
                  <Link href="/priser">
                    Se priser
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <a href="mailto:hej@sajtbyggaren.se">Kontakta teamet</a>
                </Button>
              </div>
            </aside>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
