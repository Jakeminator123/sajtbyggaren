/**
 * Krediter som append-only ledger. Saldo = SUM(delta) per användare, så vi
 * får både ett aktuellt saldo och en fullständig historik (tilldelning från
 * prenumeration, förbrukning per bygge, manuella justeringar).
 *
 * Krediter är produktens "valuta": prenumerationspaket ger en månatlig
 * kreditpott (Stripe), och krediter dras per bygge/följdprompt. Node-runtime.
 */

import { getAuthDb } from "./db";

export type CreditEntry = {
  id: number;
  delta: number;
  reason: string;
  ref: string | null;
  createdAt: number;
};

export function getCreditBalance(userId: string): number {
  const row = getAuthDb()
    .prepare("SELECT COALESCE(SUM(delta), 0) AS balance FROM credit_ledger WHERE user_id = ?")
    .get(userId) as { balance: number } | undefined;
  return row?.balance ?? 0;
}

export function addCredits(
  userId: string,
  amount: number,
  reason: string,
  ref?: string | null,
): void {
  getAuthDb()
    .prepare(
      "INSERT INTO credit_ledger (user_id, delta, reason, ref, created_at) VALUES (?, ?, ?, ?, ?)",
    )
    .run(userId, amount, reason, ref ?? null, Date.now());
}

/**
 * Dra krediter atomärt. Returnerar true om saldot räckte och draget gjordes,
 * annars false (utan att ändra något). Körs i en transaktion så två samtidiga
 * bygg-anrop inte kan dra samma sista kredit två gånger.
 */
export function consumeCredits(
  userId: string,
  amount: number,
  reason: string,
  ref?: string | null,
): boolean {
  const database = getAuthDb();
  const run = database.transaction(() => {
    const balance = getCreditBalance(userId);
    if (balance < amount) return false;
    database
      .prepare(
        "INSERT INTO credit_ledger (user_id, delta, reason, ref, created_at) VALUES (?, ?, ?, ?, ?)",
      )
      .run(userId, -amount, reason, ref ?? null, Date.now());
    return true;
  });
  return run();
}

export function listCreditEntries(userId: string, limit = 20): CreditEntry[] {
  const rows = getAuthDb()
    .prepare(
      "SELECT id, delta, reason, ref, created_at FROM credit_ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?",
    )
    .all(userId, limit) as Array<{
    id: number;
    delta: number;
    reason: string;
    ref: string | null;
    created_at: number;
  }>;
  return rows.map((row) => ({
    id: row.id,
    delta: row.delta,
    reason: row.reason,
    ref: row.ref,
    createdAt: row.created_at,
  }));
}
