import { NextResponse } from "next/server";

/**
 * Vercel-hosted Viewser can render the UI, but a number of operator actions are
 * still local-operator tooling that cannot run on a hosted serverless function:
 *
 *   1. Python-backed actions (prompt/build/scrape) shell out to repo-local
 *      `scripts/*.py` — there is no Python or `.venv` on hosted Vercel.
 *   2. Disk-backed views (run history, run artefakter, the local-disk source for
 *      the sandbox preview) read `data/runs/` and the generated-output dir — a
 *      hosted serverless function has no persistent repo disk.
 *   3. The preview-start endpoint spawns a build-like Vercel Sandbox
 *      (`npm install` + `next build`). A public, unauthenticated POST that can
 *      start sandboxes is exactly the open-relay risk that parked PR #156, so it
 *      stays gated hosted unless the operator explicitly opts in AND the
 *      deployment is protected (see `isHostedSandboxPreviewEnabled`).
 *
 * Rather than crash, hang, or silently return an empty list, the hosted routes
 * degrade honestly: a structured 501 with a Swedish operator message, or a
 * `hostedNotice` field on an otherwise-empty 200, so the UI can say plainly that
 * the action runs locally in this version.
 */
export function isHostedVercelRuntime(): boolean {
  return process.env.VERCEL === "1";
}

/**
 * True only when the operator has explicitly opted the hosted deployment in to
 * the build-like sandbox preview-start endpoint. Default OFF so the endpoint is
 * never a public, unauthenticated sandbox-spawn by accident (#156). Enabling it
 * is a deliberate operator decision and assumes the deployment is gated behind
 * platform-level protection (Vercel Deployment Protection) — see the hosted
 * deploy guide in `docs/hosted-viewser-deploy.md`.
 */
export function isHostedSandboxPreviewEnabled(): boolean {
  return process.env.VIEWSER_ENABLE_HOSTED_SANDBOX === "1";
}

/**
 * True when the operator has opted the hosted deployment in to the full
 * hosted build chain (init build + follow-up prompts via Vercel Sandbox,
 * ADR 0048/B194). Same env contract as the gate in `/api/prompt`.
 */
export function isHostedBuildEnabled(): boolean {
  return process.env.VIEWSER_ENABLE_HOSTED_BUILD === "1";
}

/** Shared Swedish notice surfaced to the UI for hosted-only-degraded views. */
export const HOSTED_LOCAL_ONLY_NOTICE =
  "Den här hostade vyn visar gränssnittet och kan förhandsvisa redan byggda " +
  "sajter. Att skapa nya sajter — bygge, följdprompt och run-historik — sker i " +
  "operatörens lokala miljö i den här versionen, inte i den hostade vyn, tills " +
  "bygg-kedjan flyttas till en riktig backend-runtime.";

/**
 * Honest notice for hosted deployments where the build chain IS enabled:
 * building works, but disk-backed views (run-historik, artefakter, inspector)
 * still read local repo disk and stay empty hosted.
 */
export const HOSTED_BUILD_ENABLED_NOTICE =
  "Hostade byggen är PÅ: init-bygge och följdprompt körs i Vercel Sandbox " +
  "direkt från den här vyn. Run-historik, artefakter och inspector läser dock " +
  "fortfarande lokal disk och är tomma hostat — byggläget i fliken försvinner " +
  "vid omladdning av sidan.";

/** Pick the notice that matches the hosted deployment's actual capability. */
export function hostedRuntimeNotice(): string {
  return isHostedBuildEnabled() ? HOSTED_BUILD_ENABLED_NOTICE : HOSTED_LOCAL_ONLY_NOTICE;
}

export function hostedPythonRuntimeUnavailable(feature: string): NextResponse {
  return NextResponse.json(
    {
      ok: false,
      code: "hosted-python-runtime-unavailable",
      feature,
      error:
        "Den här åtgärden kör Python-skript lokalt och stöds bara i lokal Viewser just nu. Den hostade Vercel-vyn kan visa UI och befintliga artefakter, men kan inte skapa eller bygga sajter förrän Python-kedjan flyttas till en riktig backend-runtime.",
    },
    { status: 501 },
  );
}

/**
 * Generic honest 501 for a hosted-only-unavailable feature that is NOT a
 * Python spawn (e.g. the build-like sandbox preview-start, or a disk-backed
 * action). Mirrors `hostedPythonRuntimeUnavailable`'s shape with a distinct
 * `code` and a caller-provided Swedish message so the UI can explain exactly
 * why the action is unavailable hosted.
 */
export function hostedFeatureUnavailable(
  feature: string,
  message: string,
): NextResponse {
  return NextResponse.json(
    {
      ok: false,
      code: "hosted-runtime-unavailable",
      feature,
      error: message,
    },
    { status: 501 },
  );
}
