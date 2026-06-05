import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { runBuild } from "@/lib/build-runner";
import {
  hostedPythonRuntimeUnavailable,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import { assertLocalhost } from "@/lib/localhost-guard";
import { runPromptToProjectInput } from "@/lib/prompt-runner";
import { classifyMessage } from "@/lib/router-classify-runner";
import { readRunChangeSet } from "@/lib/run-change-set";
import { readAppliedCopyDirectives } from "@/lib/runs";

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
const DiscoveryPayloadSchema = z
  .object({
    // Heter `schemaVersion` (inte version) avsiktligt: test_viewser_files
    // förbjuder en sidecar-meta-shape med "version:z" eller "projectId:z"
    // som client-payload — de tillhör Project Input-meta, inte API-
    // kontraktet. Discovery har sin egen schema-version som lever
    // oberoende av PI-schemat.
    //
    // Accepterar v1 (legacy, utan ``directives``-block) OCH v2
    // (2026-05-22, med strukturerade directives för att hoppa över
    // briefModel-extraktion när data finns). Frontend bumpar till v2
    // i ``buildDiscoveryPayload`` — backend (Python) tolererar båda
    // versioner via ``_apply_discovery_overrides``-stratifieringen.
    // Före detta union avvisade route:n v2-payloads med kryptiska
    // "Invalid input: expected 1" som operatören inte kunde tolka.
    schemaVersion: z.union([z.literal(1), z.literal(2)]),
    rawPrompt: z.string().trim().max(8000),
    contentBranch: z.string().trim().max(40).optional(),
    scaffoldHint: z.string().trim().max(60).optional(),
    answers: z.record(z.string(), z.unknown()),
    // Strukturerade wizard-directives introducerade i v2
    // (2026-05-22, se docs/contracts/wizard-discovery.v2.md). Vi
    // validerar bara att det är ett objekt — djupare schema-koll
    // ligger på Python-sidan (``_apply_discovery_overrides`` /
    // ``_normalise_wizard_directives``) eftersom directives är ett
    // växande kontrakt mellan rollout-passar (pass 1: backend
    // accepterar, pass 2: frontend skickar — där vi är nu, pass 3:
    // backend konsumerar fler fält). Att låsa schemat hårt här
    // skulle tvinga koordinerade deploys per pass — onödigt strikt
    // för ett internt API på localhost.
    directives: z.record(z.string(), z.unknown()).optional(),
  })
  .strict()
  .superRefine((payload, context) => {
    if (Object.prototype.hasOwnProperty.call(payload.answers, "starterId")) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["answers", "starterId"],
        message: "Discovery-payload får inte sätta starterId.",
      });
    }
  });

// Run-id-mönstret matchar `RUN_ID_PATTERN` i `lib/runs.ts` så vi avvisar
// path-traversal och whitespace-injektion redan vid 400-validering.
const RUN_ID_PATTERN = /^[a-zA-Z0-9._-]+$/;

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
  // Iterera från en specifik historisk run istället för senaste. UI
  // sätter denna när operatören klickar "Iterera från denna" på en
  // versions-rad (se GAP-backend-build-trace-endpoint.md). Bakåt-
  // kompatibel: utan baseRunId fungerar follow-up exakt som idag
  // (prompt_to_project_input.py läser senaste PI-snapshotet för siteId).
  baseRunId: z
    .string()
    .trim()
    .regex(RUN_ID_PATTERN, "Ogiltigt baseRunId.")
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
  if (payload.baseRunId && payload.mode !== "followup") {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["baseRunId"],
      message: "baseRunId kan bara anges i follow-up-läge.",
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

// Read build-result.json's `appliedVisibleEffect` without trusting its type.
// build_site.py writes this boolean on follow-up builds (B155). It is the
// signal we use to decide whether the legacy copy/edit path already landed a
// visible change for this follow-up — see the routerDecision honesty gate in
// runPromptBuildOnce. Returns null on init builds / field-drift.
function extractAppliedVisibleEffect(
  buildResult: Record<string, unknown>,
): boolean | null {
  const value = buildResult.appliedVisibleEffect;
  return typeof value === "boolean" ? value : null;
}

/**
 * runPromptBuildOnce — kör Phase 1 (prompt → Project Input) och Phase 2
 * (build_site.py via runBuild) sekventiellt. Den frivilliga
 * `onPhase1Done`-callbacken bjuds in mellan faserna så stream-läget
 * kan emittera en riktig "building"-signal till klienten exakt när
 * Phase 1 är klar — istället för att klienten gissar via setTimeout
 * (B122). Synkrona callers (utan callback) får samma slutresultat
 * som tidigare utan beteendeskillnad.
 */
async function runPromptBuildOnce(
  payload: z.infer<typeof PromptPayloadSchema>,
  options?: { onPhase1Done?: () => void },
) {
  // KÖR-6a (Fas 1, skiva 1a): classify the incoming message with the
  // DETERMINISTIC router so the operator UI can honestly show what the router
  // thought ("fråga", "plan", "ändring"). This is READ-ONLY metadata: it runs
  // concurrently with the build, never gates it, and never starts a preview.
  // shouldStartPreview / the build path stay EXACTLY as before. Failures
  // degrade to null (no routerDecision on the wire) so the build flow can never
  // break. Wiring the full follow-up chain (router -> context -> patch -> apply)
  // is a separate slice (1b); here we only expose the decision.
  const routerDecisionPromise = classifyMessage(payload.prompt, {
    siteId: payload.siteId,
  }).catch(() => null);

  // Phase 1: prompt -> Project Input on disk (data/prompt-inputs/<siteId>.*).
  const helper = await runPromptToProjectInput(payload.prompt, {
    mode: payload.mode,
    siteId: payload.siteId,
    baseRunId: payload.baseRunId,
    discovery: payload.discovery,
  });
  options?.onPhase1Done?.();

  // Phase 2: build_site.py with the absolute dossier path produced
  // above. runBuild's mutex serialises this against any concurrent
  // /api/build call so two builds do not race over .generated/.
  const build = await runBuild(helper.siteId, helper.dossierPath);

  // ADR 0034 path B (B155 UI): expose the validated copy-directives
  // that this version actually applied, härledda ur project-input-
  // snapshotet på dossierPath. Init-builds + builds utan directives
  // returnerar [] så UI:t kan särskilja "no-op" (appliedVisibleEffect
  // === false) från "applied without structured copy" (true men tom
  // lista). Aldrig en throw — felaktig artefakt landar som [] och
  // FloatingChat faller tillbaka på den generiska success-raden.
  let appliedCopyDirectives: Awaited<
    ReturnType<typeof readAppliedCopyDirectives>
  > = [];
  try {
    appliedCopyDirectives = await readAppliedCopyDirectives(build.runId);
  } catch {
    appliedCopyDirectives = [];
  }

  // UI-gap-fix (2026-06-02, Jakobs flagga): exponera en EXAKT change-set
  // för follow-ups så FloatingChat kan visa bekräftade deltas (routes
  // tillagda/borttagna, variant-byten) under "Ändrat" istället för
  // prompt-heuristiken under "Troligen ändrat". Härleds genom att diffa
  // den nya runen mot föregående run (eller baseRunId). Init-builds har
  // ingen föregående run → null. Aldrig en throw: artefakt-läsfel landar
  // som null och UI:t faller tillbaka på heuristiken.
  let changeSet: Awaited<ReturnType<typeof readRunChangeSet>> = null;
  if (payload.mode === "followup") {
    try {
      changeSet = await readRunChangeSet(
        build.runId,
        payload.baseRunId ? { baseRunId: payload.baseRunId } : {},
      );
    } catch {
      changeSet = null;
    }
  }

  // KÖR-6a honesty gate (skiva 1a): expose the router's read-only opinion
  // alongside runId/siteId/buildStatus, BUT never let it preempt a visible
  // change the (unchanged) legacy copy/edit path actually landed for this
  // follow-up. FloatingChat's summarizeRouterDecision (#177) honestly reframes
  // non-build outcomes (question/plan/unclear) but would, for the
  // artifact_patch_only / unclear classifications, wrongly say "not built yet"
  // over a copy change that DID apply. So when this follow-up applied copy
  // directives or reported a visible effect, we send routerDecision=null and
  // the existing authoritative build summary stands alone ("Ingen påhittad
  // effekt"). Init builds and genuine no-op follow-ups carry the full decision.
  const routerDecisionRaw = await routerDecisionPromise;
  const legacyPathAppliedVisibleChange =
    payload.mode === "followup" &&
    (appliedCopyDirectives.length > 0 ||
      extractAppliedVisibleEffect(build.buildResult) === true);
  const routerDecision = legacyPathAppliedVisibleChange
    ? null
    : routerDecisionRaw;

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
    appliedCopyDirectives,
    changeSet,
    // Read-only KÖR-6a router decision (deterministic classify_message).
    // Sibling of runId/siteId/buildStatus; never controls build/preview.
    routerDecision,
  };
}

async function runPromptBuildSerially(
  payload: z.infer<typeof PromptPayloadSchema>,
  options?: { onPhase1Done?: () => void },
) {
  while (promptInFlight) {
    try {
      await promptInFlight;
    } catch {
      // Previous prompt failed; still allow the next operator request to run.
    }
  }

  const promise = runPromptBuildOnce(payload, options);
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
  if (isHostedVercelRuntime()) {
    return hostedPythonRuntimeUnavailable("prompt-build");
  }

  let payload: z.infer<typeof PromptPayloadSchema>;
  try {
    const json = await request.json().catch(() => ({}));
    payload = PromptPayloadSchema.parse(json);
  } catch (error) {
    if (error instanceof z.ZodError) {
      // Client-side validation errors must surface as 400, not 500.
      // Returning 500 for "missing field" / "too long" muddies the
      // API contract and makes operator-side debugging harder.
      //
      // Inkludera ``path`` i meddelandet så operatören ser vilket
      // fält som failade. Zod 4:s default-message-rendering ger
      // texter som ``"Invalid input: expected 1"`` utan att nämna
      // fältet — vilket är obegripligt när felet kommer från en
      // nästad payload (t.ex. ``discovery.schemaVersion``). Med
      // path-prefix blir det ``"discovery.schemaVersion: Invalid
      // input: expected 1"`` vilket är åtgärdsbart.
      const issue = error.issues[0];
      const message = issue
        ? `${issue.path.length > 0 ? `${issue.path.join(".")}: ` : ""}${issue.message}`
        : "Ogiltig prompt-payload.";
      return NextResponse.json({ error: message }, { status: 400 });
    }
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }

  // B122-fix: när klienten signalerar `Accept: application/x-ndjson`
  // emitterar vi två NDJSON-rader istället för en synkron JSON:
  //   1. `{stage:"building"}` exakt när Phase 1 (prompt → Project Input)
  //      är klar, så PromptBuilder kan flippa stage på en RIKTIG signal
  //      istället för en gissad `setTimeout(1500)`.
  //   2. `{stage:"done", runId, siteId, ...}` när Phase 2 är klar.
  // Vid fel skickas `{stage:"error", error:"..."}` och streamen stängs.
  // Klienter som inte sätter Accept-headern får oförändrad synkron JSON
  // (zero impact på floating-chat.tsx + use-followup-build.ts).
  const acceptHeader = request.headers.get("accept") ?? "";
  const wantsStream = acceptHeader.includes("application/x-ndjson");

  if (wantsStream) {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        const enqueueLine = (line: Record<string, unknown>) => {
          controller.enqueue(encoder.encode(`${JSON.stringify(line)}\n`));
        };
        try {
          const result = await runPromptBuildSerially(payload, {
            onPhase1Done: () => {
              enqueueLine({ stage: "building" });
            },
          });
          enqueueLine({ stage: "done", ...result });
        } catch (error) {
          const message =
            error instanceof Error
              ? error.message
              : "Okänt fel vid prompt-anropet.";
          enqueueLine({ stage: "error", error: message });
        } finally {
          controller.close();
        }
      },
    });
    return new Response(stream, {
      status: 200,
      headers: {
        "Content-Type": "application/x-ndjson; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        // X-Accel-Buffering=no hindrar reverse proxies (om någon
        // tillkommer framför Next.js) från att buffra streamen och
        // kollapsa den till en synkron response — vi vill att klienten
        // ska se {stage:"building"} omedelbart efter Phase 1.
        "X-Accel-Buffering": "no",
      },
    });
  }

  try {
    return NextResponse.json(await runPromptBuildSerially(payload));
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid prompt-anropet.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
