import { NextResponse } from "next/server";

import {
  hostedRuntimeNotice,
  isHostedVercelRuntime,
} from "@/lib/hosted-python-runtime";
import { assertLocalhost } from "@/lib/localhost-guard";
import { readRunTrace } from "@/lib/runs";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

/**
 * Return the tail of `data/runs/<runId>/trace.ndjson` as JSON, plus the
 * resolved `runStatus` (`pending` while `build-result.json` is missing,
 * otherwise the build-result `status` field).
 *
 * Query params:
 *   - `?since=<iso-timestamp>` — only return events strictly after this
 *     timestamp (incremental polling for Live Build Sync).
 *   - `?limit=<n>` — cap the returned events (default 50, max 500).
 *
 * This endpoint is read-only and is the source of truth for the
 * "Live Build Sync" UI in apps/viewser. It never invents events and
 * never normalises shapes — `scripts/build_site.py` writes the
 * canonical NDJSON format and we just tail it.
 */
export async function GET(request: Request, context: RouteContext) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  // No persistent repo disk hosted → trace lives under `data/runs/<runId>/`.
  if (isHostedVercelRuntime()) {
    return NextResponse.json(
      { error: hostedRuntimeNotice(), hostedNotice: hostedRuntimeNotice() },
      { status: 404 },
    );
  }

  let runId: string;
  try {
    runId = (await context.params).runId;
  } catch {
    return NextResponse.json({ error: "Saknar runId i URL." }, { status: 400 });
  }

  const url = new URL(request.url);
  const since = url.searchParams.get("since") ?? undefined;
  const limitRaw = url.searchParams.get("limit");
  let limit: number | undefined;
  if (limitRaw !== null) {
    const parsed = Number.parseInt(limitRaw, 10);
    if (!Number.isFinite(parsed)) {
      return NextResponse.json(
        { error: "limit måste vara ett heltal." },
        { status: 400 },
      );
    }
    limit = parsed;
  }

  try {
    const trace = await readRunTrace(runId, { since, limit });
    return NextResponse.json(trace);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid läsning av trace.";
    // 400 för felaktig input (path-escape eller ogiltigt format), 404 endast
    // när run-katalogen saknas på disk. Pollers ska inte tolka en input-bug
    // som "kommer snart" och fortsätta poolla i evighet.
    if (/Ogiltigt runId|Ogiltigt since|pekar utanför/.test(message)) {
      return NextResponse.json({ error: message }, { status: 400 });
    }
    if (/saknar katalog/.test(message)) {
      return NextResponse.json({ error: message }, { status: 404 });
    }
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
