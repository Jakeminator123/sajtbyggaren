/**
 * POST /api/auth/logout — förstör sessionen (raderar DB-raden + cookien).
 */

import { NextResponse } from "next/server";

import { authSurfaceDisabled } from "@/lib/auth/guard";
import { destroySession } from "@/lib/auth/session";

export const runtime = "nodejs";

export async function POST() {
  const off = authSurfaceDisabled();
  if (off) return off;
  await destroySession();
  return NextResponse.json({ ok: true });
}
