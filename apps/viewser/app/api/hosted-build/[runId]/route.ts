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

/** Samma siteId-regel som hosted-build-runner.ts / /api/preview/[siteId]. */
const SITE_ID_PATTERN = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

/**
 * B196: EN delad 404-text för både "nyckeln saknas" och "siteId matchar inte".
 * Identiskt svar i båda fallen så routen aldrig blir ett orakel som bekräftar
 * att ett gissat runId existerar (enumererings-/informationsläckage-ytan från
 * extern granskning #284, fynd C).
 */
const STATUS_NOT_FOUND_MESSAGE =
  "Ingen hostad bygg-status hittades för det runId:t och siteId:t. " +
  "Statusnycklar lever 24 h i KV — körningen kan ha förfallit, aldrig " +
  "startats, eller skrivits av en process utan KV-konfiguration.";

/**
 * GET-status för ett hostat bygge (P2). Läser ``viewser:hosted-run:<runId>``
 * ur KV-adaptern och returnerar status-JSON:en som orkestrerings-skriptet i
 * bygg-sandboxen håller uppdaterad ({ runId, siteId, phase, startedAt,
 * updatedAt, error?, buildId?, blobPrefix? }).
 *
 * B196 (site-bindning): anroparen MÅSTE skicka ``?siteId=<siteId>`` och få
 * det att matcha statusens ``siteId`` — annars 404 med samma svenska text som
 * när nyckeln saknas. Utan bindningen exponerade routen bygg-status för
 * valfritt runId i publikt läge.
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

  const siteId = new URL(request.url).searchParams.get("siteId")?.trim() ?? "";
  if (
    !siteId ||
    !SITE_ID_PATTERN.test(siteId) ||
    siteId.length > 64
  ) {
    return NextResponse.json(
      {
        error:
          "Status-läsningen kräver query-parametern ?siteId=<siteId> " +
          "(a-z, 0-9 och bindestreck, max 64 tecken) — samma siteId som " +
          "bygget startades för.",
      },
      { status: 400 },
    );
  }

  const status = await kvGetJson<HostedBuildRunStatus>(
    getKvStore(),
    hostedRunKey(runId),
  );
  // B196: saknad nyckel OCH siteId-mismatch ger exakt samma 404 — svaret får
  // aldrig avslöja om ett gissat runId existerar för en annan sajt.
  if (!status || status.siteId !== siteId) {
    return NextResponse.json(
      { error: STATUS_NOT_FOUND_MESSAGE },
      { status: 404 },
    );
  }

  return NextResponse.json(status);
}
