import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { runBuild } from "@/lib/build-runner";
import {
  hostedPythonRuntimeUnavailable,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import { stopAndWaitPreviewServer } from "@/lib/local-preview-server";
import { assertLocalhost } from "@/lib/localhost-guard";
import { runOpenClawFollowupApply } from "@/lib/openclaw-runner";
import { runPromptToProjectInput } from "@/lib/prompt-runner";
import { classifyMessage } from "@/lib/router-classify-runner";
import { readRunChangeSet } from "@/lib/run-change-set";
import { readAppliedCopyDirectives, readBuildResult, runsDir } from "@/lib/runs";

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

// B169: per-siteId mutex för prompt-flödet. Tidigare en enda global
// ``let promptInFlight: Promise | null`` som serialiserade ALLA sajter i
// processen — ett segt/hängande bygge på site A blockerade init/follow-up på
// site B. Speglar build-runner.ts:s per-site Map-mönster (rad 23-40):
//
//   - Follow-ups keyas på ``siteId`` så två följdpromptar mot SAMMA sajt
//     fortfarande serialiseras (versionsrace-skyddet: Phase 1 läser/bumpar
//     ``meta.version`` + skriver PI-snapshot — det FÅR inte race:a).
//   - Init-läget har ingen siteId vid API-gränsen (den genereras i Phase 1
//     med en unik uuid-suffix, se ``prompt_to_project_input.slugify_site_id``),
//     så två inits kan ALDRIG kollidera på siteId. De får en unik nyckel per
//     request och kör därför parallellt i stället för att blockera varandra.
//
// ``finally``-grenen rensar entry:t bara om promise:n fortfarande är den
// aktiva — så en samtidig follow-up (som hunnit skriva en ny entry för samma
// siteId) inte oavsiktligt nukas. Samma försiktiga identity-guard som
// build-runner.ts.
const promptInFlight = new Map<string, Promise<unknown>>();

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
 * B164 helper: the freshest COMPLETED run on disk for a siteId, or null.
 *
 * "Completed" = the run-dir has a ``build-result.json`` (so we only ever treat
 * a real, finished version as a recoverable one — never a half-written run-dir
 * that the targeted render abandoned). We read run-dirs in mtime order and
 * short-circuit at the first ``build-result.json`` whose ``siteId`` matches, so
 * the common case (the site's latest run is among the most recently modified
 * dirs) costs only a couple of reads. Unlike ``listRuns``' bounded global
 * window this never misses the site's run, which matters for the
 * before/after-bridge comparison in ``runPromptBuildOnce`` — a missed snapshot
 * there could either silently re-double-build OR re-surface a stale run.
 *
 * Only ever called on the FOLLOW-UP path (twice per follow-up: once for the
 * pre-bridge snapshot, once on the rare bridge-failure recovery), so the
 * worst-case full scan is bounded and off the hot init path.
 */
async function latestCompletedRunForSite(
  siteId: string,
): Promise<{ runId: string; version: number | null } | null> {
  const root = runsDir();
  let entries;
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    // ENOENT (fresh env, no data/runs yet) or any read error → no run to find.
    return null;
  }
  const dirs = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
  if (!dirs.length) return null;

  const stats = await Promise.all(
    dirs.map(async (name) => {
      try {
        const stat = await fs.stat(path.join(root, name));
        return { name, mtimeMs: stat.mtimeMs };
      } catch {
        return null;
      }
    }),
  );
  const live = stats.filter(
    (entry): entry is { name: string; mtimeMs: number } => entry !== null,
  );
  if (!live.length) return null;
  live.sort((a, b) => b.mtimeMs - a.mtimeMs);

  for (const { name } of live) {
    let buildResult: Record<string, unknown>;
    try {
      buildResult = await readBuildResult(name);
    } catch {
      // No build-result.json (partial/aborted run) → not a completed version
      // for any site; skip it and keep scanning older dirs.
      continue;
    }
    if (buildResult.siteId === siteId) {
      const rawVersion = buildResult.version;
      const version =
        typeof rawVersion === "number" && Number.isInteger(rawVersion)
          ? rawVersion
          : null;
      return { runId: name, version };
    }
  }
  return null;
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
  // Skiva 1b (action bridge): on FOLLOW-UPS, first try the OpenClaw apply
  // bridge. It runs the deterministic OpenClaw decision and — ONLY for an
  // edit_instruction (action=patch_plan_request) — the KÖR-7 chain
  // (router -> context -> patch -> apply -> targeted render). The chain stops
  // at an honest gate BEFORE any build for read-only kinds (answer/
  // clarification/plan_only) and for unmapped/no-op edits, so this NEVER
  // double-builds: when the bridge applied a visible change we re-surface its
  // run and skip the legacy build; otherwise we fall through to the unchanged
  // legacy copy/edit build path below. Init builds skip the bridge entirely so
  // init flow is byte-for-byte unchanged. Degrades to null on any failure.
  // B164: snapshot the latest COMPLETED run for this site BEFORE the bridge
  // runs. The KÖR-7 chain inside runOpenClawFollowupApply writes a new
  // immutable version (PI snapshot + targeted render) BEFORE build_site.py
  // finishes. If the bridge then fails LATE (timeout / exit!=0 / truncated
  // stdout / parse-fail) runOpenClawFollowupApply returns null — and the legacy
  // Phase 1+2 fallback below would silently build a SECOND version on top of
  // the one the chain already landed. We capture the pre-bridge runId here and
  // re-check after a null result (see the B164 recovery block below).
  const preBridgeLatestRun =
    payload.mode === "followup" && payload.siteId
      ? await latestCompletedRunForSite(payload.siteId).catch(() => null)
      : null;

  const applyResult =
    payload.mode === "followup" && payload.siteId
      ? await runOpenClawFollowupApply(payload.prompt, {
          siteId: payload.siteId,
          baseRunId: payload.baseRunId,
        }).catch(() => null)
      : null;

  if (applyResult && applyResult.bridge.applied) {
    const chain = applyResult.bridge.chain ?? {};
    const chainRunId = typeof chain.runId === "string" ? chain.runId : null;
    if (chainRunId) {
      // The OpenClaw chain materialised a new immutable version (e.g. a restyle
      // or capability add) and swapped current.json on ok/degraded. Re-surface
      // its run as the authoritative build so the EXISTING client flow (pick
      // runId -> refresh preview via onBuildDone) works unchanged — no legacy
      // build runs (the chain already built the targeted version).
      //
      // B163: the legacy path stops the local preview inside runBuild (see
      // build-runner.ts) so the NEXT preview start picks up the freshly
      // published current.json. This early-return path skipped that stop, and
      // startPreviewServer is idempotent (reuses a live `next start` whose cwd
      // is the OLD build dir) — so the iframe kept serving the previous
      // version after a successful OpenClaw apply. Stop the preview here too;
      // idempotent no-op when none is running, and never fails the response.
      // (vercel-sandbox previews restart per request and are unaffected.)
      if (payload.siteId) {
        try {
          await stopAndWaitPreviewServer(payload.siteId);
        } catch {
          // Preview-stop must never break a successful apply response.
        }
      }
      let bridgeBuildResult: Record<string, unknown> = {};
      try {
        bridgeBuildResult = await readBuildResult(chainRunId);
      } catch {
        bridgeBuildResult = {};
      }
      let bridgeCopyDirectives: Awaited<
        ReturnType<typeof readAppliedCopyDirectives>
      > = [];
      try {
        bridgeCopyDirectives = await readAppliedCopyDirectives(chainRunId);
      } catch {
        bridgeCopyDirectives = [];
      }
      let bridgeChangeSet: Awaited<ReturnType<typeof readRunChangeSet>> = null;
      try {
        bridgeChangeSet = await readRunChangeSet(
          chainRunId,
          payload.baseRunId ? { baseRunId: payload.baseRunId } : {},
        );
      } catch {
        bridgeChangeSet = null;
      }
      const chainBuildStatus =
        typeof chain.buildStatus === "string" ? chain.buildStatus : null;
      const chainVersion =
        typeof chain.version === "number" ? chain.version : null;
      return {
        runId: chainRunId,
        siteId: payload.siteId,
        projectId: null,
        version: chainVersion,
        briefSource: null,
        buildStatus: extractBuildStatus(bridgeBuildResult) ?? chainBuildStatus,
        buildResult: bridgeBuildResult,
        appliedCopyDirectives: bridgeCopyDirectives,
        changeSet: bridgeChangeSet,
        // A change DID apply, so we never show the "action bridge saknas" /
        // router no-build lines over it; the build summary + bridge line stand.
        routerDecision: null,
        openClawDecision: null,
        // Skiva 1b: the honest action-bridge outcome (applied /
        // previewShouldRefresh + chain) so FloatingChat shows a restyle /
        // capability success line and refreshes the preview.
        bridge: applyResult.bridge,
      };
    }
  }

  // B164: the bridge returned null (timeout / exit!=0 / truncated stdout /
  // parse-fail). BEFORE falling through to the legacy Phase 1+2 build — which
  // would silently build a SECOND version on top of whatever the KÖR-7 chain
  // may have already written — re-check whether a NEW completed run for this
  // site appeared since the pre-bridge snapshot. If so, the chain DID land a
  // version; re-surface THAT run with an honest degraded status instead of
  // double-building. No retry and no second model call: a pure disk re-check.
  // (A non-null applyResult with bridge.applied===false is a real no-op — the
  // chain stopped at an honest gate BEFORE any build — so it is safe and we
  // intentionally do NOT trigger recovery for it.)
  if (
    applyResult === null &&
    payload.mode === "followup" &&
    payload.siteId &&
    preBridgeLatestRun !== null
  ) {
    const postBridgeLatestRun = await latestCompletedRunForSite(
      payload.siteId,
    ).catch(() => null);
    if (
      postBridgeLatestRun &&
      postBridgeLatestRun.runId !== preBridgeLatestRun.runId
    ) {
      const recoveredRunId = postBridgeLatestRun.runId;
      // Mirror B163: stop the preview so the next start picks up the chain's
      // freshly published current.json instead of serving the old build dir.
      // Idempotent + never fails the recovered response.
      try {
        await stopAndWaitPreviewServer(payload.siteId);
      } catch {
        // Preview-stop must never break the recovered response.
      }
      let recoveredBuildResult: Record<string, unknown> = {};
      try {
        recoveredBuildResult = await readBuildResult(recoveredRunId);
      } catch {
        recoveredBuildResult = {};
      }
      let recoveredCopyDirectives: Awaited<
        ReturnType<typeof readAppliedCopyDirectives>
      > = [];
      try {
        recoveredCopyDirectives = await readAppliedCopyDirectives(recoveredRunId);
      } catch {
        recoveredCopyDirectives = [];
      }
      let recoveredChangeSet: Awaited<ReturnType<typeof readRunChangeSet>> = null;
      try {
        recoveredChangeSet = await readRunChangeSet(
          recoveredRunId,
          payload.baseRunId ? { baseRunId: payload.baseRunId } : {},
        );
      } catch {
        recoveredChangeSet = null;
      }
      const recoveredStatus = extractBuildStatus(recoveredBuildResult);
      const recoveredLanded =
        recoveredStatus === "ok" || recoveredStatus === "degraded";
      return {
        runId: recoveredRunId,
        siteId: payload.siteId,
        projectId: null,
        version: postBridgeLatestRun.version,
        briefSource: null,
        // Honest degraded status: a version DID land but the apply bridge
        // failed to report it, so we never present this as a clean success.
        // A failed chain build stays "failed"; anything else is downgraded to
        // "degraded" so the operator sees "Build klar med varning", not green.
        buildStatus: recoveredStatus === "failed" ? "failed" : "degraded",
        buildResult: recoveredBuildResult,
        appliedCopyDirectives: recoveredCopyDirectives,
        changeSet: recoveredChangeSet,
        routerDecision: null,
        openClawDecision: null,
        // Distinct marker so FloatingChat/dialogs see the recovered apply: a
        // version landed (applied) and the preview should refresh when the
        // build completed, but the bridge itself degraded.
        bridge: {
          status: "degraded-recovered",
          applied: recoveredLanded,
          previewShouldRefresh: recoveredLanded,
          chain: null,
        },
      };
    }
  }

  // KÖR-6a (skiva 1a): classify the incoming message with the DETERMINISTIC
  // router so the operator UI can honestly reframe a non-build outcome
  // (question/plan/unclear) on the legacy/fallback path. READ-ONLY metadata: it
  // runs concurrently with the build, never gates it, and never starts a
  // preview. Failures degrade to null. (The OpenClaw decision below comes from
  // the apply bridge above, which already classified the message — no second
  // spawn; on init or bridge failure it is simply null.)
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

  // Same honesty gate for the OpenClaw decision. The decision comes from the
  // apply bridge above, which classified the message even on the fallback path
  // (read-only kind / unmapped edit / bridge failure -> null). V0 returns
  // patch_plan_request for an edit instruction, but the (unchanged) deterministic
  // copyDirective path may have ALREADY applied that edit (e.g. "byt rubriken
  // till X"). Rendering "action bridge saknas" over a change that DID land would
  // be dishonest, so when the legacy path applied a visible change we drop the
  // decision and the authoritative build summary stands alone.
  const openClawDecisionRaw = applyResult?.decision ?? null;
  const openClawDecision = legacyPathAppliedVisibleChange
    ? null
    : openClawDecisionRaw;

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
    // Read-only OpenClaw Core V0 follow-up decision (skiva 1b). Null on init
    // builds and on follow-ups where the legacy path applied a visible change.
    // Richer superset of routerDecision; never controls build/preview.
    openClawDecision,
    // Skiva 1b: the action-bridge outcome (applied=false on this fallback path)
    // for transparency; null on init. FloatingChat ignores a non-applied bridge.
    bridge: applyResult?.bridge ?? null,
  };
}

async function runPromptBuildSerially(
  payload: z.infer<typeof PromptPayloadSchema>,
  options?: { onPhase1Done?: () => void },
) {
  // B169: serialise per-siteId, not globally. Follow-ups key on the concrete
  // siteId so two follow-ups for the SAME site still queue (Phase 1 version-
  // bump race protection). Init has no siteId yet and generates a collision-
  // free one in Phase 1, so each init gets a unique key and runs in parallel
  // instead of blocking — and crucially never blocks a follow-up on another
  // site. Mirrors build-runner.ts's per-site Map.
  const queueKey = payload.siteId ?? `__init__:${randomUUID()}`;

  // Vänta på pending prompt-build för EXAKT denna queueKey — andra sajter
  // (och parallella inits) kör samtidigt. Läs om Map:en efter varje await så
  // en follow-up som skrivit en ny entry medan vi väntade inte missas.
  while (promptInFlight.has(queueKey)) {
    try {
      await promptInFlight.get(queueKey);
    } catch {
      // Previous prompt for this site failed; still allow the next one to run.
    }
  }

  const promise = runPromptBuildOnce(payload, options);
  promptInFlight.set(queueKey, promise);
  try {
    return await promise;
  } finally {
    // Rensa entry:t bara om promise:n FORTFARANDE är den aktiva — så en
    // samtidig follow-up (som hunnit skriva en ny entry för samma siteId)
    // inte oavsiktligt nukas. Speglar build-runner.ts:s identity-guard.
    if (promptInFlight.get(queueKey) === promise) {
      promptInFlight.delete(queueKey);
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
