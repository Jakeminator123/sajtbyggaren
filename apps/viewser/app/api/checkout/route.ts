/**
 * POST /api/checkout — startar en Stripe Checkout (subscription) för det
 * valda paketet. Kräver inloggning. Skapar/återanvänder en Stripe-kund knuten
 * till kontot. Rör inte bygg-pipelinen.
 */

import { NextResponse } from "next/server";

import { authSurfaceDisabled } from "@/lib/auth/guard";
import { getCurrentUser } from "@/lib/auth/session";
import { setStripeCustomerId } from "@/lib/auth/users";
import { getPlan } from "@/lib/billing/plans";
import {
  appBaseUrl,
  getStripe,
  isStripeConfigured,
  stripePriceIdForPlan,
} from "@/lib/billing/stripe";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const off = authSurfaceDisabled();
  if (off) return off;
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Inte inloggad." }, { status: 401 });
  }

  if (!isStripeConfigured()) {
    return NextResponse.json(
      { error: "Betalning är inte aktiverad ännu. Hör av dig så löser vi det." },
      { status: 503 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Ogiltig förfrågan." }, { status: 400 });
  }

  const planId = (body as { planId?: string }).planId;
  const plan = getPlan(planId);
  if (!plan) {
    return NextResponse.json({ error: "Okänt paket." }, { status: 400 });
  }

  const priceId = stripePriceIdForPlan(plan);
  if (!priceId) {
    return NextResponse.json(
      { error: "Paketet är inte kopplat till ett pris ännu." },
      { status: 503 },
    );
  }

  const stripe = getStripe();

  let customerId = user.stripeCustomerId;
  if (!customerId) {
    const customer = await stripe.customers.create({
      email: user.email,
      name: user.name ?? undefined,
      metadata: { userId: user.id },
    });
    customerId = customer.id;
    setStripeCustomerId(user.id, customerId);
  }

  const baseUrl = appBaseUrl(request);
  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    customer: customerId,
    line_items: [{ price: priceId, quantity: 1 }],
    success_url: `${baseUrl}/konto?checkout=success`,
    cancel_url: `${baseUrl}/priser?checkout=cancel`,
    metadata: { userId: user.id, planId: plan.id },
    subscription_data: { metadata: { userId: user.id, planId: plan.id } },
    allow_promotion_codes: true,
  });

  return NextResponse.json({ url: session.url });
}
