/**
 * POST /api/stripe/webhook — tar emot Stripe-events och håller vårt konto-
 * tillstånd i synk: tilldelar kreditpotten vid köp + förnyelse och speglar
 * prenumerationsstatus. Idempotent (varje event-id hanteras en gång) så
 * webhook-retries inte dubbel-krediterar.
 *
 * Den auktoritativa betalningssanningen är Stripe; den här routen översätter
 * bara events → krediter/abonnemangsstatus i auth-storen. Rör inte bygget.
 */

import { NextResponse } from "next/server";
import type Stripe from "stripe";

import { addCredits } from "@/lib/auth/credits";
import { getAuthDb } from "@/lib/auth/db";
import { upsertSubscription } from "@/lib/auth/subscriptions";
import { findUserByStripeCustomerId } from "@/lib/auth/users";
import { getPlan } from "@/lib/billing/plans";
import { getStripe, isStripeConfigured } from "@/lib/billing/stripe";

export const runtime = "nodejs";

function asRecord(value: unknown): Record<string, unknown> {
  return (value ?? {}) as Record<string, unknown>;
}

function subscriptionPeriodEndMs(sub: Stripe.Subscription): number | null {
  const top = asRecord(sub)["current_period_end"];
  if (typeof top === "number") return top * 1000;
  const itemEnd = asRecord(asRecord(sub.items?.data?.[0]))["current_period_end"];
  if (typeof itemEnd === "number") return itemEnd * 1000;
  return null;
}

function planIdFromSubscription(sub: Stripe.Subscription): string | null {
  const meta = asRecord(sub.metadata)["planId"];
  return typeof meta === "string" ? meta : null;
}

function invoiceSubscriptionId(invoice: Stripe.Invoice): string | null {
  const direct = asRecord(invoice)["subscription"];
  if (typeof direct === "string") return direct;
  const details = asRecord(asRecord(invoice)["parent"])["subscription_details"];
  const subId = asRecord(details)["subscription"];
  return typeof subId === "string" ? subId : null;
}

function eventAlreadyProcessed(eventId: string): boolean {
  return Boolean(
    getAuthDb()
      .prepare("SELECT 1 FROM processed_stripe_events WHERE id = ?")
      .get(eventId),
  );
}

function recordProcessedEvent(eventId: string): void {
  // ``OR IGNORE`` så två samtidiga leveranser av samma event inte kraschar
  // på UNIQUE-konflikt (en av dem vinner, den andra blir en no-op).
  getAuthDb()
    .prepare(
      "INSERT OR IGNORE INTO processed_stripe_events (id, created_at) VALUES (?, ?)",
    )
    .run(eventId, Date.now());
}

function syncSubscriptionRecord(sub: Stripe.Subscription): void {
  const user = findUserByStripeCustomerId(String(sub.customer));
  if (!user) return;
  upsertSubscription(user.id, {
    planId: planIdFromSubscription(sub),
    status: sub.status,
    currentPeriodEnd: subscriptionPeriodEndMs(sub),
    stripeSubscriptionId: sub.id,
  });
}

export async function POST(request: Request) {
  if (!isStripeConfigured()) {
    return NextResponse.json({ error: "Stripe ej konfigurerat." }, { status: 503 });
  }
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) {
    return NextResponse.json(
      { error: "STRIPE_WEBHOOK_SECRET saknas." },
      { status: 503 },
    );
  }

  const signature = request.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "Saknar signatur." }, { status: 400 });
  }

  const payload = await request.text();
  const stripe = getStripe();
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(payload, signature, secret);
  } catch {
    return NextResponse.json({ error: "Ogiltig signatur." }, { status: 400 });
  }

  // Idempotensskydd: hoppa över redan hanterade events (snabb dedup).
  if (eventAlreadyProcessed(event.id)) {
    return NextResponse.json({ received: true, duplicate: true });
  }

  // Sidoeffekterna körs FÖRE vi markerar eventet som hanterat. Kastar
  // någon kredit-/Stripe-operation svarar vi 500 så Stripe gör en retry —
  // annars hade ett halvkört event markerats klart och krediter tappats.
  try {
    await handleEvent(event, stripe);
  } catch {
    return NextResponse.json(
      { error: "Kunde inte hantera eventet — försök igen." },
      { status: 500 },
    );
  }
  recordProcessedEvent(event.id);
  return NextResponse.json({ received: true });
}

async function handleEvent(
  event: Stripe.Event,
  stripe: Stripe,
): Promise<void> {
  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId =
        typeof asRecord(session.metadata)["userId"] === "string"
          ? (session.metadata!.userId as string)
          : null;
      const planId =
        typeof asRecord(session.metadata)["planId"] === "string"
          ? (session.metadata!.planId as string)
          : null;
      const plan = getPlan(planId);
      if (userId && plan) {
        // Första cykelns krediter (renewals hanteras av invoice.paid nedan).
        addCredits(userId, plan.creditsPerMonth, "subscription-start", plan.id);
      }
      if (session.subscription) {
        const sub = await stripe.subscriptions.retrieve(
          String(session.subscription),
        );
        syncSubscriptionRecord(sub);
      }
      break;
    }

    case "invoice.paid": {
      const invoice = event.data.object as Stripe.Invoice;
      // Bara förnyelser här — första betalningen hanteras av checkout-eventet.
      if (asRecord(invoice)["billing_reason"] !== "subscription_cycle") break;
      const subId = invoiceSubscriptionId(invoice);
      if (!subId) break;
      const sub = await stripe.subscriptions.retrieve(subId);
      const user = findUserByStripeCustomerId(String(sub.customer));
      const plan = getPlan(planIdFromSubscription(sub));
      if (user && plan) {
        addCredits(user.id, plan.creditsPerMonth, "subscription-renewal", plan.id);
      }
      syncSubscriptionRecord(sub);
      break;
    }

    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      syncSubscriptionRecord(event.data.object as Stripe.Subscription);
      break;
    }

    default:
      break;
  }
}
