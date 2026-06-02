/**
 * Delade auth-typer. Hålls medvetet client-säkra (inga Node-imports) så de
 * kan importeras både i server- och klientkod.
 */

export type AuthUser = {
  id: string;
  email: string;
  name: string | null;
  stripeCustomerId: string | null;
  createdAt: number;
};

/** Prenumerationsstatus speglad från Stripe (subset vi bryr oss om). */
export type SubscriptionRecord = {
  planId: string | null;
  status: string | null;
  currentPeriodEnd: number | null;
  stripeSubscriptionId: string | null;
};
