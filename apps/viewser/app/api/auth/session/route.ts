/**
 * GET /api/auth/session — returnerar inloggad användare + saldo, eller null.
 * Används av klientkomponenter (t.ex. studio) som behöver veta auth-status.
 */

import { NextResponse } from "next/server";

import { AUTH_ENABLED } from "@/lib/auth-config";
import { getCreditBalance } from "@/lib/auth/credits";
import { getCurrentUser } from "@/lib/auth/session";

export const runtime = "nodejs";

export async function GET() {
  // Auth-ytan avstängd (NEXT_PUBLIC_AUTH_ENABLED) → svara "inte inloggad" så
  // klientkomponenter degraderar tyst i stället för att få ett fel.
  if (!AUTH_ENABLED) return NextResponse.json({ user: null });
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ user: null });
  }
  return NextResponse.json({
    user: { id: user.id, email: user.email, name: user.name },
    credits: getCreditBalance(user.id),
  });
}
