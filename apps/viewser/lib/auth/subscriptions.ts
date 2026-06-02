/**
 * Prenumerationsstatus speglad från Stripe. Den auktoritativa källan är
 * Stripe; vi cachar status/period/plan lokalt så UI:t kan visa "aktiv plan"
 * utan ett Stripe-anrop per sidladdning. Uppdateras av webhooken. Node-runtime.
 */

import { getAuthDb } from "./db";
import type { SubscriptionRecord } from "./types";

export function getSubscription(userId: string): SubscriptionRecord | null {
  const row = getAuthDb()
    .prepare(
      "SELECT plan_id, status, current_period_end, stripe_subscription_id FROM subscriptions WHERE user_id = ?",
    )
    .get(userId) as
    | {
        plan_id: string | null;
        status: string | null;
        current_period_end: number | null;
        stripe_subscription_id: string | null;
      }
    | undefined;
  if (!row) return null;
  return {
    planId: row.plan_id,
    status: row.status,
    currentPeriodEnd: row.current_period_end,
    stripeSubscriptionId: row.stripe_subscription_id,
  };
}

export function upsertSubscription(
  userId: string,
  record: SubscriptionRecord,
): void {
  getAuthDb()
    .prepare(
      `INSERT INTO subscriptions (user_id, stripe_subscription_id, plan_id, status, current_period_end, updated_at)
       VALUES (@userId, @stripeSubscriptionId, @planId, @status, @currentPeriodEnd, @updatedAt)
       ON CONFLICT(user_id) DO UPDATE SET
         stripe_subscription_id = excluded.stripe_subscription_id,
         plan_id = excluded.plan_id,
         status = excluded.status,
         current_period_end = excluded.current_period_end,
         updated_at = excluded.updated_at`,
    )
    .run({
      userId,
      stripeSubscriptionId: record.stripeSubscriptionId,
      planId: record.planId,
      status: record.status,
      currentPeriodEnd: record.currentPeriodEnd,
      updatedAt: Date.now(),
    });
}

export function isSubscriptionActive(record: SubscriptionRecord | null): boolean {
  if (!record?.status) return false;
  return record.status === "active" || record.status === "trialing";
}
