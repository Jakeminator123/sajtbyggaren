"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { MinimalFooter } from "@/components/layout";

const sections = [
  {
    title: "1. Personuppgiftsansvarig",
    content: "Pretty Good AB, org.nr DG97 är personuppgiftsansvarig. Kontakt: support@sajtmaskin.se",
  },
  {
    title: "2. Vilka uppgifter samlar vi in?",
    content: "Kontoinformation (e-post, namn via OAuth), betalningsuppgifter (hanteras av Stripe), användningsdata (sidvisningar, projekt) och teknisk data (IP, webbläsare).",
  },
  {
    title: "3. Hur använder vi dina uppgifter?",
    content: "Tillhandahålla och förbättra Tjänsten, hantera konto och credits, bearbeta betalningar, kommunicera om tjänsteändringar och analysera användningsmönster.",
  },
  {
    title: "4. Tredjepartstjänster",
    content: "Stripe (betalning), Vercel (hosting), Google OAuth (inloggning), GitHub OAuth (inloggning/import), AI-modeller (OpenAI/Anthropic via v0).",
  },
  {
    title: "5. Cookies",
    content: "Nödvändiga cookies för session/autentisering. Analyscookies (anonymiserad statistik) med ditt samtycke. Hantera via cookie-bannern.",
  },
  {
    title: "6. Dina rättigheter (GDPR)",
    content: "Tillgång, rättelse, radering, dataportabilitet, invändning mot behandling. Klagomål till Integritetsskyddsmyndigheten (IMY).",
  },
  {
    title: "7. Lagring och säkerhet",
    content: "Data lagras inom EU/EES med kryptering, åtkomstkontroll och regelbundna säkerhetsgranskningar.",
  },
  {
    title: "8. Ändringar",
    content: "Väsentliga ändringar meddelas via e-post eller i Tjänsten. Senaste versionen finns alltid på denna sida.",
  },
  {
    title: "9. Kontakt",
    content: "Pretty Good AB (DG97) — support@sajtmaskin.se",
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

export default function PrivacyPage() {
  return (
    <>
      <main className="bg-background text-foreground min-h-screen">
        <div className="mx-auto max-w-2xl px-6 py-16">
          <Link href="/" className="text-muted-foreground hover:text-foreground mb-8 inline-block text-sm">
            &larr; Tillbaka
          </Link>

          <h1 className="mb-2 text-2xl font-semibold tracking-tight">Integritetspolicy</h1>
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
