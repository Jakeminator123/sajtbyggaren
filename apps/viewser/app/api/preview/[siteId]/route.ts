import { NextRequest, NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";
import {
  getPreviewServer,
  startPreviewServer,
  stopPreviewServer,
} from "@/lib/local-preview-server";

/**
 * /api/preview/[siteId] — hanterar lokal preview-server för en
 * genererad sajt så ViewerPanel kan rendera den i en iframe direkt
 * mot ``http://localhost:<port>`` utan att gå via StackBlitz.
 *
 * Endpoints:
 *
 *   - GET  → returnera nuvarande status (eller 404 om ingen server lever).
 *   - POST → starta servern (idempotent — återanvänder existerande).
 *   - DELETE → stoppa servern.
 *
 * Endast tillgänglig på localhost (assertLocalhost). Vi spawnar
 * ``next start`` som ärvtsen viewser:s env — en utomstående som når
 * routen via tunnel skulle kunna trigga spawn av processer på vår
 * maskin.
 */

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

function validateSiteId(siteId: string): string | null {
  if (!siteId) return "siteId saknas.";
  if (siteId.length > 64) return "siteId är för långt (max 64 tecken).";
  if (!SITE_ID_PATTERN.test(siteId)) {
    return "siteId får bara innehålla a-z, 0-9 och bindestreck.";
  }
  return null;
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ siteId: string }> },
) {
  const localhostError = assertLocalhost(request);
  if (localhostError) return localhostError;

  const { siteId } = await context.params;
  const validation = validateSiteId(siteId);
  if (validation) {
    return NextResponse.json({ error: validation }, { status: 400 });
  }

  const info = getPreviewServer(siteId);
  if (!info) {
    return NextResponse.json(
      { error: "Ingen preview-server körs för denna sajt." },
      { status: 404 },
    );
  }
  return NextResponse.json(info);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ siteId: string }> },
) {
  const localhostError = assertLocalhost(request);
  if (localhostError) return localhostError;

  const { siteId } = await context.params;
  const validation = validateSiteId(siteId);
  if (validation) {
    return NextResponse.json({ error: validation }, { status: 400 });
  }

  try {
    const info = await startPreviewServer(siteId);
    return NextResponse.json(info);
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Okänt fel vid start av preview-server.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ siteId: string }> },
) {
  const localhostError = assertLocalhost(request);
  if (localhostError) return localhostError;

  const { siteId } = await context.params;
  const validation = validateSiteId(siteId);
  if (validation) {
    return NextResponse.json({ error: validation }, { status: 400 });
  }

  const stopped = stopPreviewServer(siteId);
  return NextResponse.json({ stopped });
}
