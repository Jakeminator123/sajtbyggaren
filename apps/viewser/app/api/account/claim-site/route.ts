/**
 * POST /api/account/claim-site — knyter ett byggt siteId till det inloggade
 * kontot ("Mina sajter"). Medvetet löskopplad från bygg-pipelinen: anropas
 * best-effort av studion EFTER ett lyckat bygge och lagrar bara mappningen
 * siteId → userId. Ingen inloggning → tyst no-op (200), aldrig ett fel som
 * skulle kunna störa bygg-UI:t.
 */

import { NextResponse } from "next/server";

import { claimSite } from "@/lib/auth/owned-sites";
import { getCurrentUser } from "@/lib/auth/session";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ ok: false, reason: "not-authenticated" });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ ok: false, reason: "bad-request" }, { status: 400 });
  }

  const siteId = (body as { siteId?: unknown }).siteId;
  if (typeof siteId !== "string" || !siteId.trim() || siteId === "unknown") {
    return NextResponse.json({ ok: false, reason: "invalid-site" }, { status: 400 });
  }

  const result = claimSite(user.id, siteId.trim());
  if (result === "owned-by-other") {
    // Sajten ägs redan av ett annat konto — svara ärligt så studions UI
    // INTE visar "Sparad till ditt konto" för något användaren inte äger.
    return NextResponse.json({ ok: false, reason: "already-claimed" });
  }
  return NextResponse.json({ ok: true });
}
