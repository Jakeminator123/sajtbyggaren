import type { Metadata } from "next";
import Link from "next/link";
import { Footer } from "@/components/layout/footer";
import { Navbar } from "@/components/layout/navbar";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Priser",
  description:
    "Sajtbyggarens prismodell — rättvis credit-baserad prissättning. Beta är gratis.",
};

const tiers = [
  {
    name: "Beta",
    price: "0 kr",
    cadence: "tillsvidare",
    description:
      "Under sajtbyggarens beta är genereringen kostnadsfri. Vi vill bygga rätt produkt först, ta betalt sen.",
    cta: { label: "Skapa hemsida", href: "/" },
    highlight: true,
  },
  {
    name: "Liten",
    price: "Kommer",
    cadence: "snart",
    description:
      "Engångskredit för småföretag som vill ha en proff-hemsida på en eftermiddag.",
    cta: { label: "Anmäl intresse", href: "mailto:hej@sajtbyggaren.se" },
  },
  {
    name: "Företag",
    price: "Kommer",
    cadence: "snart",
    description:
      "Återkommande prenumeration för bolag som löpande publicerar och iterates med AI.",
    cta: { label: "Boka samtal", href: "mailto:hej@sajtbyggaren.se" },
  },
];

export default function PriserPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <Navbar />

      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-6 py-24 text-center">
          <p className="mb-4 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
            Priser
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight sm:text-5xl">
            Rättvist. Transparent. Inga överraskningar.
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
            Vi tar inte betalt under beta. När vi tar betalt blir det
            credit-baserat, inte abonnemangskrångligt.
          </p>
        </section>

        <section className="mx-auto grid max-w-5xl gap-6 px-6 pb-24 sm:grid-cols-3">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`flex flex-col rounded-2xl border p-8 ${
                tier.highlight
                  ? "border-foreground/15 bg-card shadow-sm"
                  : "border-border bg-muted/30"
              }`}
            >
              <h2 className="text-xl font-semibold text-foreground">
                {tier.name}
              </h2>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-semibold tracking-tight">
                  {tier.price}
                </span>
                <span className="text-sm text-muted-foreground">
                  / {tier.cadence}
                </span>
              </div>
              <p className="mt-4 flex-1 text-sm leading-relaxed text-muted-foreground">
                {tier.description}
              </p>
              <Button
                asChild
                variant={tier.highlight ? "default" : "outline"}
                className="mt-6"
              >
                <Link href={tier.cta.href}>{tier.cta.label}</Link>
              </Button>
            </div>
          ))}
        </section>
      </main>

      <Footer />
    </div>
  );
}
