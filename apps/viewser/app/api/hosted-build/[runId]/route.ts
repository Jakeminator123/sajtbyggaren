import { NextResponse } from "next/server";

import {
  hostedRunKey,
  type HostedBuildRunStatus,
} from "@/lib/hosted-build-runner";
import { getKvStore, kvGetJson } from "@/lib/kv-store";
import { assertLocalhost } from "@/lib/localhost-guard";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

/** runId är ett crypto.randomUUID från startHostedBuild — tillåt en
 * konservativ delmängd så en kreativ URL aldrig blir en udda KV-nyckel. */
const RUN_ID_PATTERN = /^[a-zA-Z0-9-]{1,64}$/;

/**
 * GET-status för ett hostat bygge (P2). Läser ``viewser:hosted-run:<runId>``
 * ur KV-adaptern och returnerar status-JSON:en som orkestrerings-skriptet i
 * bygg-sandboxen håller uppdaterad ({ runId, siteId, phase, startedAt,
 * updatedAt, error?, buildId?, blobPrefix? }).
 *
 * Att läsa status är ofarligt, men assertLocalhost körs ändå för konsekvens
 * med övriga routes — hostat bypassas guarden via env
 * (VIEWSER_ALLOWED_HOSTS/VIEWSER_ALLOW_NON_LOCALHOST), precis som annars.
 */
export async function GET(request: Request, context: RouteContext) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let runId: string;
  try {
    runId = (await context.params).runId;
  } catch {
    return NextResponse.json({ error: "Saknar runId i URL." }, { status: 400 });
  }

  if (!RUN_ID_PATTERN.test(runId)) {
    return NextResponse.json(
      { error: "Ogiltigt runId-format (a-z, A-Z, 0-9 och bindestreck, max 64 tecken)." },
      { status: 400 },
    );
  }

  const status = await kvGetJson<HostedBuildRunStatus>(
    getKvStore(),
    hostedRunKey(runId),
  );
  if (!status) {
    return NextResponse.json(
      {
        error:
          "Ingen hostad bygg-status hittades för det runId:t. Statusnycklar " +
          "lever 24 h i KV — körningen kan ha förfallit, aldrig startats, " +
          "eller skrivits av en process utan KV-konfiguration.",
      },
      { status: 404 },
    );
  }

  return NextResponse.json(status);
}
