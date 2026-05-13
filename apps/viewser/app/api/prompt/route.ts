import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { runBuild } from "@/lib/build-runner";
import { assertLocalhost } from "@/lib/localhost-guard";
import { runPromptToProjectInput } from "@/lib/prompt-runner";

// Operator-prototype: keep the prompt small enough that an accidental
// 50 MB paste cannot wedge the build pipeline. The cap is generous for
// real prompts but blocks obvious abuse.
const PromptPayloadSchema = z.object({
  prompt: z
    .string()
    .min(1, "Prompt får inte vara tom.")
    .max(4000, "Prompt får vara max 4000 tecken."),
});

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  try {
    const json = await request.json().catch(() => ({}));
    const payload = PromptPayloadSchema.parse(json);

    // Phase 1: prompt -> Project Input on disk (data/prompt-inputs/<siteId>.*).
    const helper = await runPromptToProjectInput(payload.prompt);

    // Phase 2: build_site.py with the absolute dossier path produced
    // above. runBuild's mutex serialises this against any concurrent
    // /api/build call so two prompts do not race over .generated/.
    const build = await runBuild(helper.siteId, helper.dossierPath);

    return NextResponse.json({
      runId: build.runId,
      siteId: helper.siteId,
      projectId: helper.projectId,
      briefSource: helper.briefSource,
      buildResult: build.buildResult,
    });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
