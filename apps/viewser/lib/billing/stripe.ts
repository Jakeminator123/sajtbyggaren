/**
 * Stripe-klient + hjälpare. Server-only (importerar stripe-SDK:n med
 * hemlig nyckel). All betalning sker via Stripe; vi lagrar aldrig kortdata.
 *
 * Stripe är medvetet "lazy": om STRIPE_SECRET_KEY saknas kastar getStripe(),
 * och anropande route returnerar ett ärligt 503 istället för att krascha vid
 * import. Så pris-sidan + auth fungerar även utan Stripe-konfig (dev).
 */

import Stripe from "stripe";

import { PLANS, type Plan } from "./plans";

let client: Stripe | null = null;

export function isStripeConfigured(): boolean {
  return Boolean(process.env.STRIPE_SECRET_KEY);
}

export function getStripe(): Stripe {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) {
    throw new Error("STRIPE_SECRET_KEY saknas — Stripe är inte konfigurerat.");
  }
  if (!client) {
    client = new Stripe(key);
  }
  return client;
}

/** Stripe price-id för ett paket, från env (eller null om ej satt). */
export function stripePriceIdForPlan(plan: Plan): string | null {
  return process.env[plan.stripePriceEnv]?.trim() || null;
}

/** Hitta paketet som hör till ett givet Stripe price-id (via env-mappningen). */
export function planForStripePriceId(priceId: string | null | undefined): Plan | undefined {
  if (!priceId) return undefined;
  return PLANS.find((plan) => stripePriceIdForPlan(plan) === priceId);
}

/** Bas-URL för success/cancel/return — env-override eller request-origin. */
export function appBaseUrl(request: Request): string {
  const configured = process.env.NEXT_PUBLIC_APP_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  return new URL(request.url).origin;
}
