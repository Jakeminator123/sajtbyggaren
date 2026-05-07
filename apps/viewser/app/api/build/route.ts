import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { runBuild } from "@/lib/build-runner";

const BuildPayloadSchema = z.object({
  dossierId: z.string().min(1).default("painter-palma"),
});

export async function POST(request: NextRequest) {
  try {
    const json = await request.json().catch(() => ({}));
    const payload = BuildPayloadSchema.parse(json);
    const result = await runBuild(payload.dossierId);

    return NextResponse.json({
      runId: result.runId,
      buildResult: result.buildResult,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid build-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
