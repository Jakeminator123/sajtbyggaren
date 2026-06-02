/**
 * Prenumerationspaket och kreditmodell. Client-säker (inga server-imports) så
 * både pris-sidan och server-yta kan importera den.
 *
 * Modell (beslut 2026-06-02): Stripe-prenumeration som ger en månatlig
 * kreditpott. Krediter är produktens valuta — de dras per bygge/följdprompt.
 * Stripe price-id:n bor i env (per paket) så inga hemligheter ligger i koden;
 * priserna nedan är display-värden för pris-sidan.
 */

export type PlanId = "bas" | "plus" | "pro";

export type Plan = {
  id: PlanId;
  name: string;
  /** Månadspris i kr (display). Den faktiska debiteringen styrs av Stripe-priset. */
  priceSek: number;
  /** Krediter som tilldelas varje månad prenumerationen förnyas. */
  creditsPerMonth: number;
  /** Namnet på env-variabeln som håller Stripe price-id för paketet. */
  stripePriceEnv: string;
  tagline: string;
  features: string[];
  highlighted?: boolean;
};

export const PLANS: readonly Plan[] = [
  {
    id: "bas",
    name: "Bas",
    priceSek: 99,
    creditsPerMonth: 3,
    stripePriceEnv: "STRIPE_PRICE_BAS",
    tagline: "För dig som vill komma igång med en sida.",
    features: [
      "3 bygg-krediter per månad",
      "Obegränsade förhandsvisningar",
      "Förfina med ord",
    ],
  },
  {
    id: "plus",
    name: "Plus",
    priceSek: 199,
    creditsPerMonth: 8,
    stripePriceEnv: "STRIPE_PRICE_PLUS",
    tagline: "För företaget som vill iterera ofta.",
    features: [
      "8 bygg-krediter per månad",
      "Allt i Bas",
      "Prioriterad bygg-kö",
    ],
    highlighted: true,
  },
  {
    id: "pro",
    name: "Pro",
    priceSek: 399,
    creditsPerMonth: 20,
    stripePriceEnv: "STRIPE_PRICE_PRO",
    tagline: "För dig som bygger flera sajter.",
    features: [
      "20 bygg-krediter per månad",
      "Allt i Plus",
      "Flera sajter på ett konto",
    ],
  },
] as const;

/** Krediter en ny användare får direkt vid registrering (gratis att prova). */
export const FREE_SIGNUP_CREDITS = 1;

/** Krediter som dras per genomfört bygge/följdprompt. */
export const CREDITS_PER_BUILD = 1;

export function getPlan(id: string | null | undefined): Plan | undefined {
  return PLANS.find((plan) => plan.id === id);
}

export function formatSek(amount: number): string {
  return `${amount} kr`;
}
