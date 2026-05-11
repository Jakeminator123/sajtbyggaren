"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { MinimalFooter } from "@/components/layout";

const sections = [
  {
    title: "1. Om tjänsten",
    content: 'Sajtmaskin ("Tjänsten") är en AI-driven plattform för webbplatsgenerering som drivs av Pretty Good AB, org.nr DG97. Genom att använda Tjänsten godkänner du dessa villkor.',
  },
  {
    title: "2. Användarkonto",
    content: "Du ansvarar för att hålla dina inloggningsuppgifter säkra. Vi förbehåller oss rätten att stänga konton som missbrukas.",
  },
  {
    title: "3. Credits och betalning",
    content: "Tjänsten använder ett credit-baserat system. Credits köps via Stripe och kan användas för att generera webbplatser och AI-funktioner. Köpta credits återbetalas inte om inget annat avtalas.",
  },
  {
    title: "4. Genererat innehåll",
    content: "Innehåll som genereras via Tjänsten baseras på AI-modeller. Du erhåller rätten att använda genererat innehåll fritt, inklusive kommersiellt. Vi garanterar inte att innehållet är felfritt. Du ansvarar för att granska materialet innan publicering.",
  },
  {
    title: "5. Acceptabel användning",
    content: "Du förbinder dig att inte använda Tjänsten för att generera olagligt, skadligt eller vilseledande innehåll, kränka tredje parts rättigheter, eller överbelasta infrastrukturen.",
  },
  {
    title: "6. Ansvarsbegränsning",
    content: 'Tjänsten tillhandahålls "i befintligt skick". Vi ansvarar inte för indirekta skador. Vår maximala ansvarsskyldighet är begränsad till det belopp du betalat under de senaste 12 månaderna.',
  },
  {
    title: "7. Ändringar",
    content: "Vi kan uppdatera dessa villkor med 30 dagars förvarning. Fortsatt användning innebär godkännande.",
  },
  {
    title: "8. Tvistlösning",
    content: "Dessa villkor regleras av svensk lag. Tvister avgörs av Stockholms tingsrätt som första instans.",
  },
  {
    title: "9. Kontakt",
    content: "Pretty Good AB (DG97) — support@sajtmaskin.se — sajtstudio.se",
  },
];

function Accordion({ title, content }: { title: string; content: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-border/30 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-4 py-4 text-left"
      >
        <span className="text-sm font-medium text-foreground">{title}</span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      <div className={`overflow-hidden transition-all duration-200 ${open ? "max-h-60 pb-4 opacity-100" : "max-h-0 opacity-0"}`}>
        <p className="text-sm leading-relaxed text-muted-foreground">{content}</p>
      </div>
    </div>
  );
}

export default function TermsPage() {
  return (
    <>
      <main className="bg-background text-foreground min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <Link href="/" className="text-muted-foreground hover:text-foreground mb-8 inline-block text-sm">
            &larr; Tillbaka
          </Link>

          <h1 className="mb-2 text-2xl font-semibold tracking-tight">Användarvillkor</h1>
          <p className="text-muted-foreground mb-8 text-xs">
            Senast uppdaterad: {new Date().toISOString().split("T")[0]}
          </p>

          <div>
            {sections.map((s) => (
              <Accordion key={s.title} title={s.title} content={s.content} />
            ))}
          </div>
        </div>
      </main>
      <MinimalFooter />
    </>
  );
}
