import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PlanCheckoutButton } from "@/components/billing/plan-checkout-button";
import { AUTH_ENABLED } from "@/lib/auth-config";
import { formatSek, PLANS } from "@/lib/billing/plans";

export const metadata: Metadata = {
  title: "Priser",
  description:
    "Välj ett paket och få bygg-krediter varje månad. Förfina din hemsida med ord — vi bygger om.",
};

export default function PricingPage() {
  // Billing-ytan är opt-in (NEXT_PUBLIC_AUTH_ENABLED). Avstängd → 404.
  if (!AUTH_ENABLED) notFound();
  return (
    <div className="mx-auto w-full max-w-[1100px] px-5 py-20 sm:px-8 sm:py-28">
      <div className="flex max-w-[640px] flex-col gap-4">
        <h1 className="text-foreground text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Enkel prissättning. Inga överraskningar.
        </h1>
        <p className="text-muted-foreground text-[17px] leading-relaxed">
          Varje paket ger dig bygg-krediter varje månad. En kredit räcker till
          ett bygge eller en förfining. Avsluta när du vill.
        </p>
      </div>

      <div className="mt-14 grid gap-5 md:grid-cols-3">
        {PLANS.map((plan) => (
          <div
            key={plan.id}
            className={`relative flex flex-col gap-6 rounded-3xl border p-7 ${
              plan.highlighted
                ? "border-foreground/80 shadow-sm"
                : "border-border/60"
            }`}
          >
            {plan.highlighted && (
              <span className="bg-foreground text-background absolute -top-3 left-7 rounded-full px-3 py-1 text-[12px] font-medium">
                Populärast
              </span>
            )}
            <div className="flex flex-col gap-1.5">
              <h2 className="text-foreground text-xl font-semibold tracking-tight">
                {plan.name}
              </h2>
              <p className="text-muted-foreground text-[14px]">{plan.tagline}</p>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="text-foreground text-4xl font-semibold tracking-tight">
                {formatSek(plan.priceSek)}
              </span>
              <span className="text-muted-foreground text-[14px]">/mån</span>
            </div>
            <ul className="flex flex-col gap-2.5">
              {plan.features.map((feature) => (
                <li
                  key={feature}
                  className="text-foreground/90 flex items-start gap-2 text-[14px]"
                >
                  <span aria-hidden className="text-foreground/40 mt-0.5">
                    —
                  </span>
                  {feature}
                </li>
              ))}
            </ul>
            <div className="mt-auto">
              <PlanCheckoutButton
                planId={plan.id}
                highlighted={plan.highlighted}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="text-muted-foreground mt-10 text-[13px]">
        Priserna anges inkl. moms. Betalning sker säkert via Stripe. Genom att
        köpa godkänner du våra{" "}
        <a
          href="/anvandarvillkor"
          className="text-foreground underline-offset-4 hover:underline"
        >
          användarvillkor
        </a>
        .
      </p>
    </div>
  );
}
