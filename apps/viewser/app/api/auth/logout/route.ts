/**
 * POST /api/auth/logout — förstör sessionen (raderar DB-raden + cookien).
 */

import { NextResponse } from "next/server";

import { destroySession } from "@/lib/auth/session";

export const runtime = "nodejs";

export async function POST() {
  await destroySession();
  return NextResponse.json({ ok: true });
}
