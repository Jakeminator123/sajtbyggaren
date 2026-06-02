/**
 * POST /api/checkout/portal — öppnar Stripe Customer Portal så kunden kan
 * hantera/avsluta sitt abonnemang och byta betalkort. Kräver inloggning + en
 * befintlig Stripe-kund.
 */

import { NextResponse } from "next/server";

import { authSurfaceDisabled } from "@/lib/auth/guard";
import { getCurrentUser } from "@/lib/auth/session";
import { appBaseUrl, getStripe, isStripeConfigured } from "@/lib/billing/stripe";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const off = authSurfaceDisabled();
  if (off) return off;
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Inte inloggad." }, { status: 401 });
  }
  if (!isStripeConfigured() || !user.stripeCustomerId) {
    return NextResponse.json(
      { error: "Inget abonnemang att hantera." },
      { status: 400 },
    );
  }

  const stripe = getStripe();
  const session = await stripe.billingPortal.sessions.create({
    customer: user.stripeCustomerId,
    return_url: `${appBaseUrl(request)}/konto`,
  });
  return NextResponse.json({ url: session.url });
}
