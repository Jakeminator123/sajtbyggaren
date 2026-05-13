import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { runBuild } from "@/lib/build-runner";
import { assertLocalhost } from "@/lib/localhost-guard";
import { runPromptToProjectInput } from "@/lib/prompt-runner";

// Operator-prototype: keep the prompt small enough that an accidental
// 50 MB paste cannot wedge the build pipeline. The cap is generous for
// real prompts but blocks obvious abuse. Trim before length-checks so a
// whitespace-only payload fails at the API boundary with 400 instead of
// slipping through `.min(1)` and surfacing later as a 500 from the
// Python helper's own emptiness-check.
const PromptPayloadSchema = z.object({
  prompt: z
    .string()
    .trim()
    .min(1, "Prompt får inte vara tom.")
    .max(4000, "Prompt får vara max 4000 tecken."),
});

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let prompt: string;
  try {
    const json = await request.json().catch(() => ({}));
    prompt = PromptPayloadSchema.parse(json).prompt;
  } catch (error) {
    if (error instanceof z.ZodError) {
      // Client-side validation errors must surface as 400, not 500.
      // Returning 500 for "missing field" / "too long" muddies the
      // API contract and makes operator-side debugging harder.
      const message = error.issues[0]?.message ?? "Ogiltig prompt-payload.";
      return NextResponse.json({ error: message }, { status: 400 });
    }
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  try {
    // Phase 1: prompt -> Project Input on disk (data/prompt-inputs/<siteId>.*).
    const helper = await runPromptToProjectInput(prompt);

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
