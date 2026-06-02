import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { liveDisabled } from "@/lib/live-gate";
import { startLiveBuild } from "@/lib/sandbox-build-runner";

/**
 * POST /api/live/start — starta en HOSTAD prompt→bygg→preview-loop.
 *
 * Till skillnad från /api/prompt + /api/preview (localhost-låsta, lokal
 * Python) kör denna hela pipen i en Vercel Sandbox och funkar därför hostat.
 * Den gate:as av ``VIEWSER_ENABLE_LIVE`` så funktionen är lätt att stänga av.
 *
 * Returnerar direkt med ``{ siteId, url, status: "building" }`` — klienten
 * pollar sedan GET /api/live/status tills ``phase === "ready"``.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const BodySchema = z.object({
  prompt: z
    .string()
    .trim()
    .min(1, "Prompt får inte vara tom.")
    .max(16000, "Prompt får vara max 16 000 tecken."),
});

export async function POST(request: NextRequest) {
  const disabled = liveDisabled();
  if (disabled) return disabled;

  let prompt: string;
  try {
    const json = await request.json().catch(() => ({}));
    prompt = BodySchema.parse(json).prompt;
  } catch (error) {
    const message =
      error instanceof z.ZodError
        ? (error.issues[0]?.message ?? "Ogiltig payload.")
        : "Ogiltig payload.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const result = await startLiveBuild(prompt);
  if (result.status === "failed") {
    return NextResponse.json(
      { error: result.error ?? "Kunde inte starta bygget.", code: "start_failed" },
      { status: 502 },
    );
  }

  return NextResponse.json({
    siteId: result.siteId,
    url: result.url,
    status: "building",
  });
}
