import { NextRequest, NextResponse } from "next/server";

import { getLiveStatus, isValidSiteId } from "@/lib/sandbox-build-runner";
import { liveDisabled } from "@/lib/live-gate";

/**
 * GET /api/live/status?siteId=<id> — fas-status för en live-session.
 * Klienten pollar denna under bygget och iframe:ar ``url`` när
 * ``phase === "ready"``.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET(request: NextRequest) {
  const disabled = liveDisabled();
  if (disabled) return disabled;

  const siteId = request.nextUrl.searchParams.get("siteId")?.trim() ?? "";
  if (!isValidSiteId(siteId)) {
    return NextResponse.json({ error: "Ogiltigt siteId." }, { status: 400 });
  }

  const status = await getLiveStatus(siteId);
  return NextResponse.json(status);
}
