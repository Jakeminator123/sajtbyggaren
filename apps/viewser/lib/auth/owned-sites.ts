/**
 * Koppling mellan ett konto och de sajter (siteId) det äger. Detta är den
 * ENDA beröringspunkten mot bygg-världen, och den är medvetet löskopplad:
 * vi lagrar bara ``siteId`` (samma id som bygg-pipelinen redan myntar) →
 * ``userId``. Vi rör aldrig data/runs, build_site.py eller generationen.
 * Node-runtime.
 */

import { getAuthDb } from "./db";

/**
 * Försök knyta ``siteId`` till ``userId``. Resultatet är ärligt så UI:t
 * inte säger "Sparad" när sajten i själva verket redan ägs av någon annan:
 *   - "claimed"        → vi skapade kopplingen nu.
 *   - "already-own"    → anroparen ägde redan sajten (idempotent re-claim).
 *   - "owned-by-other" → en annan användare hann före; vi rör inte raden.
 */
export function claimSite(
  userId: string,
  siteId: string,
): "claimed" | "already-own" | "owned-by-other" {
  const db = getAuthDb();
  const existing = db
    .prepare("SELECT user_id FROM owned_sites WHERE site_id = ?")
    .get(siteId) as { user_id: string } | undefined;
  if (existing) {
    return existing.user_id === userId ? "already-own" : "owned-by-other";
  }
  const info = db
    .prepare(
      `INSERT INTO owned_sites (site_id, user_id, created_at) VALUES (?, ?, ?)
       ON CONFLICT(site_id) DO NOTHING`,
    )
    .run(siteId, userId, Date.now());
  // changes === 0 → en samtidig claim hann emellan SELECT och INSERT.
  // Kolla vem som faktiskt äger raden nu istället för att gissa.
  if (info.changes === 0) {
    return ownsSite(userId, siteId) ? "already-own" : "owned-by-other";
  }
  return "claimed";
}

export function listOwnedSiteIds(userId: string): string[] {
  const rows = getAuthDb()
    .prepare(
      "SELECT site_id FROM owned_sites WHERE user_id = ? ORDER BY created_at DESC",
    )
    .all(userId) as Array<{ site_id: string }>;
  return rows.map((row) => row.site_id);
}

export function ownsSite(userId: string, siteId: string): boolean {
  const row = getAuthDb()
    .prepare("SELECT 1 FROM owned_sites WHERE user_id = ? AND site_id = ?")
    .get(userId, siteId);
  return Boolean(row);
}
