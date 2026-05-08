import { NextResponse } from "next/server";
import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY ?? "", {
  apiVersion: "2024-10-28.acacia",
});

interface Body {
  priceId: string;
  successUrl?: string;
  cancelUrl?: string;
}

export async function POST(request: Request) {
  if (!process.env.STRIPE_SECRET_KEY) {
    return NextResponse.json(
      { error: "STRIPE_SECRET_KEY is not configured" },
      { status: 503 },
    );
  }
  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  if (!body.priceId || typeof body.priceId !== "string") {
    return NextResponse.json({ error: "priceId is required" }, { status: 400 });
  }

  const origin = request.headers.get("origin") ?? "http://localhost:3000";
  const successUrl = body.successUrl ?? `${origin}/payment-success`;
  const cancelUrl = body.cancelUrl ?? `${origin}/`;

  try {
    const session = await stripe.checkout.sessions.create({
      mode: body.priceId.startsWith("price_") ? "subscription" : "payment",
      line_items: [{ price: body.priceId, quantity: 1 }],
      success_url: successUrl,
      cancel_url: cancelUrl,
    });
    return NextResponse.json({ url: session.url });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown Stripe error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
