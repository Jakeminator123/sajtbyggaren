import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { assertLocalhost } from "@/lib/localhost-guard";
import {
  clamp,
  collectElementMap,
  tryInspectorWorker,
  withInspectorPage,
} from "@/lib/inspector/playwright-engine";
import {
  checkInspectorTarget,
  isLoopbackTarget,
} from "@/lib/inspector/target-guard";

/**
 * POST /api/inspector-element-map — DOM-karta över den rendrade previewn.
 *
 * Porterad från sajtmaskins inspector-flöde (Jakob-OK 2026-06-10). Tar en
 * preview-URL (local-next `http://localhost:<port>` eller vercel-sandbox
 * `https://…vercel.run`) och returnerar upp till `maxElements` synliga
 * element med selector + bounding box i viewport-procent. UI:t
 * (preview-inspektorn i ViewerPanel) använder kartan för hover-highlight
 * och sektionszoner så operatören kan peka i förhandsvisningen.
 *
 * Motorval: extern inspector-worker när INSPECTOR_CAPTURE_WORKER_URL är
 * satt OCH målet inte är loopback (workern blockerar loopback i sin egen
 * SSRF-guard); annars lokal Playwright. StackBlitz-previews kan inte
 * inspekteras alls — de rendrar i operatörens browser (WebContainer) och
 * har ingen URL som en server-Chromium kan navigera till.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ElementMapRequestSchema = z.object({
  url: z.string().min(1),
  viewportWidth: z.number().optional(),
  viewportHeight: z.number().optional(),
  maxElements: z.number().optional(),
});

export async function POST(request: NextRequest) {
  const guardResponse = assertLocalhost(request);
  if (guardResponse) return guardResponse;

  const body = await request.json().catch(() => null);
  const parsed = ElementMapRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { success: false, error: "Ogiltig payload. Kräver url (sträng)." },
      { status: 400 },
    );
  }

  const targetCheck = checkInspectorTarget(parsed.data.url);
  if (!targetCheck.ok) {
    return NextResponse.json(
      { success: false, error: targetCheck.error },
      { status: targetCheck.status },
    );
  }
  const target = targetCheck.url;

  const viewportWidth = clamp(
    Math.round(parsed.data.viewportWidth ?? 1280),
    320,
    2400,
  );
  const viewportHeight = clamp(
    Math.round(parsed.data.viewportHeight ?? 800),
    240,
    2400,
  );
  const maxElements = clamp(
    Math.round(parsed.data.maxElements ?? 300),
    50,
    600,
  );

  if (!isLoopbackTarget(target)) {
    const workerResult = await tryInspectorWorker("/element-map", {
      url: target.toString(),
      viewportWidth,
      viewportHeight,
      maxElements,
    });
    if (workerResult) {
      return NextResponse.json(workerResult, { status: 200 });
    }
  }

  try {
    const result = await withInspectorPage(
      target.toString(),
      { width: viewportWidth, height: viewportHeight },
      async (page) => collectElementMap(page, maxElements),
    );

    if (!Array.isArray(result) && "unavailable" in result) {
      return NextResponse.json(
        { success: false, error: result.reason },
        { status: 503 },
      );
    }

    return NextResponse.json({
      success: true,
      elements: result,
      viewport: { width: viewportWidth, height: viewportHeight },
      elementCount: result.length,
      collectedAt: new Date().toISOString(),
    });
  } catch (error) {
    const details =
      error instanceof Error ? error.message : "Okänt element-map-fel";
    return NextResponse.json(
      {
        success: false,
        error:
          "Kunde inte kartlägga previewn. Kontrollera att preview-servern är igång.",
        details,
      },
      { status: 502 },
    );
  }
}
