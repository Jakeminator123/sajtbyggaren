import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { followupLiveBuild } from "@/lib/sandbox-build-runner";
import { liveDisabled } from "@/lib/live-gate";

/**
 * POST /api/live/followup — fortsättningsprompt mot en levande session.
 * Bygger en ny version i SAMMA sandbox och startar om previewen på samma URL.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

const BodySchema = z.object({
  siteId: z.string().trim().regex(SITE_ID_PATTERN, "Ogiltigt siteId."),
  prompt: z
    .string()
    .trim()
    .min(1, "Prompt får inte vara tom.")
    .max(16000, "Prompt får vara max 16 000 tecken."),
});

export async function POST(request: NextRequest) {
  const disabled = liveDisabled();
  if (disabled) return disabled;

  let body: z.infer<typeof BodySchema>;
  try {
    const json = await request.json().catch(() => ({}));
    body = BodySchema.parse(json);
  } catch (error) {
    const message =
      error instanceof z.ZodError
        ? (error.issues[0]?.message ?? "Ogiltig payload.")
        : "Ogiltig payload.";
    return NextResponse.json({ error: message }, { status: 400 });
  }

  const result = await followupLiveBuild(body.siteId, body.prompt);
  if (result.status === "failed") {
    return NextResponse.json(
      { error: result.error ?? "Kunde inte starta följdbygget.", code: "followup_failed" },
      { status: 502 },
    );
  }

  return NextResponse.json({
    siteId: result.siteId,
    url: result.url,
    status: "building",
  });
}
