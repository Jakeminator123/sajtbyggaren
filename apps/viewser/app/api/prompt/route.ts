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
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

const PromptPayloadSchema = z.object({
  prompt: z
    .string()
    .trim()
    .min(1, "Prompt får inte vara tom.")
    .max(4000, "Prompt får vara max 4000 tecken."),
  mode: z.enum(["init", "followup"]).default("init"),
  siteId: z
    .string()
    .trim()
    .regex(SITE_ID_PATTERN, "Ogiltigt siteId för följdprompt.")
    .optional(),
}).superRefine((payload, context) => {
  if (payload.mode === "followup" && !payload.siteId) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["siteId"],
      message: "Följdprompt kräver valt siteId.",
    });
  }
});

let promptInFlight: Promise<unknown> | null = null;

async function runPromptBuildOnce(
  payload: z.infer<typeof PromptPayloadSchema>,
) {
  // Phase 1: prompt -> Project Input on disk (data/prompt-inputs/<siteId>.*).
  const helper = await runPromptToProjectInput(payload.prompt, {
    mode: payload.mode,
    siteId: payload.siteId,
  });

  // Phase 2: build_site.py with the absolute dossier path produced
  // above. runBuild's mutex serialises this against any concurrent
  // /api/build call so two builds do not race over .generated/.
  const build = await runBuild(helper.siteId, helper.dossierPath);

  return {
    runId: build.runId,
    siteId: helper.siteId,
    projectId: helper.projectId,
    version: helper.version,
    briefSource: helper.briefSource,
    buildResult: build.buildResult,
  };
}

async function runPromptBuildSerially(
  payload: z.infer<typeof PromptPayloadSchema>,
) {
  while (promptInFlight) {
    try {
      await promptInFlight;
    } catch {
      // Previous prompt failed; still allow the next operator request to run.
    }
  }

  const promise = runPromptBuildOnce(payload);
  promptInFlight = promise.finally(() => {
    if (promptInFlight === promise) {
      promptInFlight = null;
    }
  });
  return promise;
}

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let payload: z.infer<typeof PromptPayloadSchema>;
  try {
    const json = await request.json().catch(() => ({}));
    payload = PromptPayloadSchema.parse(json);
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
    return NextResponse.json(await runPromptBuildSerially(payload));
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
