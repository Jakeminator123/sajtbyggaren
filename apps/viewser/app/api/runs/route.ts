import { NextResponse } from "next/server";

import {
  HOSTED_LOCAL_ONLY_NOTICE,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
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
 */
export async function GET(request: Request) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  // Hosted Vercel has no persistent repo disk, so `data/runs/` does not exist.
  // Return an empty-but-honest payload with a Swedish notice instead of a
  // misleading empty list (or a 500 if the dir is missing), so the UI can tell
  // the operator that run history + build run locally in this version.
  if (isHostedVercelRuntime()) {
    return NextResponse.json({
      runs: [],
      projectInputs: [],
      hostedNotice: HOSTED_LOCAL_ONLY_NOTICE,
    });
  }

  const url = new URL(request.url);
  const siteIdRaw = url.searchParams.get("siteId");
  if (siteIdRaw && !SITE_ID_PATTERN.test(siteIdRaw)) {
    return NextResponse.json(
      { error: "Ogiltigt siteId-filter." },
      { status: 400 },
    );
  }
  const siteIdOption = siteIdRaw ? { siteId: siteIdRaw } : {};

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
