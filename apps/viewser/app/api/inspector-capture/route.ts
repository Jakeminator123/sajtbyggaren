import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { assertLocalhost } from "@/lib/localhost-guard";
import {
  clamp,
  describePoint,
  drawCaptureOverlay,
  tryInspectorWorker,
  withInspectorPage,
} from "@/lib/inspector/playwright-engine";
import {
  checkInspectorTarget,
  isLoopbackTarget,
} from "@/lib/inspector/target-guard";

/**
 * POST /api/inspector-capture — punkt-inspektion av den rendrade previewn.
 *
 * Porterad från sajtmaskins inspector-flöde (Jakob-OK 2026-06-10). Tar en
 * preview-URL + en klickpunkt i procent och returnerar (1) en beskrivning
 * av elementet närmast punkten (tag, text, selector, närmaste rubrik) och
 * (2) en PNG-crop runt punkten med kryssmarkör — användbar som ärligt
 * underlag i en följdprompt ("den här knappen", inte bara fritext).
 *
 * Samma motorval som /api/inspector-element-map: extern worker för publika
 * mål när INSPECTOR_CAPTURE_WORKER_URL är satt, annars lokal Playwright.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_CROP_WIDTH = 420;
const DEFAULT_CROP_HEIGHT = 280;

const CaptureRequestSchema = z.object({
  url: z.string().min(1),
  xPercent: z.number(),
  yPercent: z.number(),
  viewportWidth: z.number(),
  viewportHeight: z.number(),
  cropWidth: z.number().optional(),
  cropHeight: z.number().optional(),
});

export async function POST(request: NextRequest) {
  const guardResponse = assertLocalhost(request);
  if (guardResponse) return guardResponse;

  const body = await request.json().catch(() => null);
  const parsed = CaptureRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      {
        success: false,
        error:
          "Ogiltig payload. Kräver url, xPercent, yPercent, viewportWidth, viewportHeight.",
      },
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

  const viewportWidth = clamp(Math.round(parsed.data.viewportWidth), 320, 2400);
  const viewportHeight = clamp(
    Math.round(parsed.data.viewportHeight),
    240,
    2400,
  );
  const xPercent = clamp(parsed.data.xPercent, 0, 100);
  const yPercent = clamp(parsed.data.yPercent, 0, 100);
  const centerX = clamp((xPercent / 100) * viewportWidth, 0, viewportWidth);
  const centerY = clamp((yPercent / 100) * viewportHeight, 0, viewportHeight);
  const cropWidth = clamp(
    Math.round(parsed.data.cropWidth ?? DEFAULT_CROP_WIDTH),
    120,
    viewportWidth,
  );
  const cropHeight = clamp(
    Math.round(parsed.data.cropHeight ?? DEFAULT_CROP_HEIGHT),
    90,
    viewportHeight,
  );

  if (!isLoopbackTarget(target)) {
    const workerResult = await tryInspectorWorker("/capture", {
      url: target.toString(),
      xPercent,
      yPercent,
      viewportWidth,
      viewportHeight,
      cropWidth,
      cropHeight,
    });
    if (workerResult) {
      return NextResponse.json(workerResult, { status: 200 });
    }
  }

  try {
    const result = await withInspectorPage(
      target.toString(),
      { width: viewportWidth, height: viewportHeight },
      async (page) => {
        const pointDetails = await describePoint(page, centerX, centerY);
        const resolvedCenterX = clamp(
          Math.round(pointDetails.resolvedX),
          0,
          viewportWidth,
        );
        const resolvedCenterY = clamp(
          Math.round(pointDetails.resolvedY),
          0,
          viewportHeight,
        );
        const clipX = clamp(
          Math.round(resolvedCenterX - cropWidth / 2),
          0,
          Math.max(0, viewportWidth - cropWidth),
        );
        const clipY = clamp(
          Math.round(resolvedCenterY - cropHeight / 2),
          0,
          Math.max(0, viewportHeight - cropHeight),
        );
        await drawCaptureOverlay(
          page,
          resolvedCenterX,
          resolvedCenterY,
          xPercent,
          yPercent,
        );

        const previewBuffer = await page.screenshot({
          type: "png",
          omitBackground: false,
          clip: { x: clipX, y: clipY, width: cropWidth, height: cropHeight },
        });

        return {
          capturedUrl: page.url(),
          previewDataUrl: `data:image/png;base64,${previewBuffer.toString("base64")}`,
          pointSummary: pointDetails.pointSummary,
          element: pointDetails.element,
          clip: { x: clipX, y: clipY, width: cropWidth, height: cropHeight },
        };
      },
    );

    if ("unavailable" in result) {
      return NextResponse.json(
        { success: false, error: result.reason },
        { status: 503 },
      );
    }

    return NextResponse.json({
      success: true,
      source: "local" as const,
      capturedUrl: result.capturedUrl,
      previewDataUrl: result.previewDataUrl,
      previewMimeType: "image/png",
      xPercent,
      yPercent,
      viewportWidth,
      viewportHeight,
      pointSummary: result.pointSummary,
      element: result.element,
      clip: result.clip,
    });
  } catch (error) {
    const details =
      error instanceof Error ? error.message : "Okänt capture-fel";
    return NextResponse.json(
      {
        success: false,
        error:
          "Kunde inte skapa punktbild. Kontrollera att preview-servern är igång.",
        details,
      },
      { status: 502 },
    );
  }
}
