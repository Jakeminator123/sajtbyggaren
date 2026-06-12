import { NextResponse } from "next/server";

import {
  hostedRuntimeNotice,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import {
  hostedProjectInputForSite,
  listHostedRunsForSite,
} from "@/lib/hosted-run-history";
import { assertLocalhost } from "@/lib/localhost-guard";
import { listProjectInputs } from "@/lib/project-inputs";
import { listRuns } from "@/lib/runs";

const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/**
 * List recent engine runs and the available Project Inputs.
 *
 * Query params:
 *   - `?siteId=<id>` — return only runs belonging to that site (server-side
 *     filter so UI doesn't have to dedupe a 20-row mixed list).
 *
 * Pending runs (where `build-result.json` has not landed yet) are now
 * included with `status: "pending"`, `currentPhase` and `currentEvent`
 * derived from the last `trace.ndjson` event so Live Build Sync can show
 * an in-flight version on every browser tab — see
 * `GAP-backend-build-trace-endpoint.md`.
 *
 * Hostat (VERCEL=1, B199 v2): run-historiken läses ur KV-indexet i stället
 * för disk — men BARA per sajt. siteId är capability-nyckeln (samma
 * åtkomstmodell som B196): utan ?siteId= svaras en tom lista, eftersom en
 * global listning av alla sajters runs på en publik oautentiserad route
 * vore en integritetsläcka. Svaret bär alltid `hostedBanner` (ren
 * info-banner — ALDRIG `hostedNotice`, som är 404-latchens kontrakt).
 */
export async function GET(request: Request) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  const url = new URL(request.url);
  const siteIdRaw = url.searchParams.get("siteId");
  if (siteIdRaw && !SITE_ID_PATTERN.test(siteIdRaw)) {
    return NextResponse.json(
      { error: "Ogiltigt siteId-filter." },
      { status: 400 },
    );
  }
  const siteIdOption = siteIdRaw ? { siteId: siteIdRaw } : {};

  if (isHostedVercelRuntime()) {
    if (!siteIdRaw) {
      return NextResponse.json({
        runs: [],
        projectInputs: [],
        hostedBanner: hostedRuntimeNotice(),
      });
    }
    try {
      const { runs } = await listHostedRunsForSite(siteIdRaw, 20);
      const projectInput = await hostedProjectInputForSite(siteIdRaw);
      return NextResponse.json({
        runs,
        projectInputs: projectInput ? [projectInput] : [],
        hostedBanner: hostedRuntimeNotice(),
      });
    } catch {
      // KV otillgänglig → ärligt tomt svar med banner, aldrig 500-brus.
      return NextResponse.json({
        runs: [],
        projectInputs: [],
        hostedBanner: hostedRuntimeNotice(),
      });
    }
  }

  try {
    const [runs, projectInputs] = await Promise.all([
      listRuns(20, siteIdOption),
      listProjectInputs(),
    ]);
    return NextResponse.json({ runs, projectInputs });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid hämtning av runs.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
