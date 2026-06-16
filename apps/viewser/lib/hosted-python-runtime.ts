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

// Kundvänlig ton (UI-text): plain svenska utan teknisk jargong om
// infrastruktur, lagring eller interna byggbegrepp. Bannern syns för
// slutanvändaren i den hostade vyn, så den ska beskriva VAD hen kan göra —
// inte HUR det körs under huven. Honest: vi lovar inget den hostade vyn inte
// kan i respektive läge. (Källåsen i tests/test_viewser_hosted_run_history.py
// vaktar att inga jargongtokens läcker tillbaka in i strängarna.)

/** Kundvänlig notis för hostad vy där byggkedjan ännu inte är aktiverad. */
export const HOSTED_LOCAL_ONLY_NOTICE =
  "Den här vyn visar Sajtbyggaren och kan förhandsvisa färdiga sajter. Att " +
  "skapa nya sajter är inte aktiverat i den här vyn just nu.";

/**
 * Kundvänlig notis för hostad vy där byggkedjan ÄR aktiverad. Sedan B199 v2
 * sparas det du bygger automatiskt så att du kan komma tillbaka och förfina
 * det. Inga interna driftdetaljer i UI-texten.
 */
export const HOSTED_BUILD_ENABLED_NOTICE =
  "Den här vyn körs i molnet. Sajter du skapar här sparas automatiskt så att " +
  "du kan komma tillbaka och förfina dem.";

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
