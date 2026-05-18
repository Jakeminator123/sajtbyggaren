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

/**
 * Discovery-wizardens payload. Schemat speglar `DiscoveryPayload` i
 * `apps/viewser/components/discovery-wizard/wizard-payload.ts`. Vi
 * validerar bara den yttersta strukturen — `answers`-objektet är
 * intentionellt löst (operator-prototyp) och kontrolleras djupare av
 * `_apply_discovery_overrides` på Python-sidan där fält som inte
 * känns igen helt enkelt ignoreras.
 */
const DiscoveryPayloadSchema = z.object({
  // Heter `schemaVersion` (inte version) avsiktligt: test_viewser_files
  // förbjuder en sidecar-meta-shape med "version:z" eller "projectId:z"
  // som client-payload — de tillhör Project Input-meta, inte API-
  // kontraktet. Discovery har sin egen schema-version som lever
  // oberoende av PI-schemat.
  schemaVersion: z.literal(1),
  rawPrompt: z.string().trim().max(8000),
  contentBranch: z.string().trim().max(40).optional(),
  scaffoldHint: z.string().trim().max(60).optional(),
  answers: z.record(z.string(), z.unknown()),
});

const PromptPayloadSchema = z.object({
  // Master-prompten från discovery-wizarden kan bli flera kilobyte
  // (operatörens originaltext + 8 sektioner med kategori, kontakt,
  // tjänster, story, sidor, ton). 16k är vältilltaget för worst-case
  // (alla wizard-fält maxade) utan att riskera att brytas vid en
  // ovanligt lång story-text.
  prompt: z
    .string()
    .trim()
    .min(1, "Prompt får inte vara tom.")
    .max(16000, "Prompt får vara max 16 000 tecken."),
  mode: z.enum(["init", "followup"]).default("init"),
  siteId: z
    .string()
    .trim()
    .regex(SITE_ID_PATTERN, "Ogiltigt siteId för följdprompt.")
    .optional(),
  discovery: DiscoveryPayloadSchema.optional(),
}).superRefine((payload, context) => {
  if (payload.mode === "followup" && !payload.siteId) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["siteId"],
      message: "Följdprompt kräver valt siteId.",
    });
  }
  if (payload.mode === "followup" && payload.discovery) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["discovery"],
      message: "Discovery-wizarden används bara i init-läge.",
    });
  }
});

let promptInFlight: Promise<unknown> | null = null;

// Read the raw `status` field from build-result.json without trusting
// its type. build_site.py writes "ok" / "degraded" / "failed" / "skipped";
// dev_generate.py writes "mock-complete". Anything else collapses to
// null so the client surface explicitly handles the unknown case
// instead of silently rendering a green "build klar" banner over a
// failed run (B44).
function extractBuildStatus(buildResult: Record<string, unknown>): string | null {
  const value = buildResult.status;
  return typeof value === "string" ? value : null;
}

async function runPromptBuildOnce(
  payload: z.infer<typeof PromptPayloadSchema>,
) {
  // Phase 1: prompt -> Project Input on disk (data/prompt-inputs/<siteId>.*).
  const helper = await runPromptToProjectInput(payload.prompt, {
    mode: payload.mode,
    siteId: payload.siteId,
    discovery: payload.discovery,
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
    // B44: surface the canonical build status so the operator UI can
    // distinguish ok / degraded / failed instead of treating any
    // returned runId as a successful build. build-runner.ts intentionally
    // returns the structured failure path with a runId so failed runs
    // still appear in Run History (B40 contract); without buildStatus
    // on the wire PromptBuilder used to flag those as "Build klar".
    buildStatus: extractBuildStatus(build.buildResult),
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
  promptInFlight = promise;
  try {
    return await promise;
  } finally {
    if (promptInFlight === promise) {
      promptInFlight = null;
    }
  }
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
