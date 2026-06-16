import { NextRequest, NextResponse } from "next/server";

import {
  isAuthorizedBearer,
  pruneBlob,
  pruneEnabled,
  resolveEnvVar,
  resolveRetentionDays,
} from "@/lib/blob-prune.mjs";

// Behöver Node-runtimen: @vercel/blob, KV-REST-fetch och fs-baserad
// env-fallback. Listning + radering av ~tusentals objekt kan ta tid, så vi
// ger den hela Fluid-budgeten (Hobby-taket är 300 s).
export const runtime = "nodejs";
export const maxDuration = 300;

/**
 * Auto-prune-cron för den HOSTADE blob-lagringen.
 *
 * Vercel Cron triggar en GET mot ``/api/cron/prune-blob`` enligt schemat i
 * ``vercel.json`` och bifogar ``Authorization: Bearer <CRON_SECRET>`` NÄR
 * ``CRON_SECRET`` är satt i Vercel-env. Utan giltig secret svarar routen 401
 * — den får ALDRIG vara en oskyddad delete-relä (samma öppen-relä-lärdom som
 * #156). POST stöds också för manuell körning (curl med samma bearer).
 *
 * Retention styrs av ``RETENTION_DAYS`` (default 14). ``?dryRun=1`` listar vad
 * som SKULLE raderas utan att radera. ``PRUNE_ENABLED=0/false/off`` pausar
 * raderingen utan redeploy (cron loggar "skipped"). build-context/ rörs
 * aldrig (skyddat i lib/blob-prune.mjs).
 */
async function handle(request: NextRequest): Promise<NextResponse> {
  if (!isAuthorizedBearer(request, process.env.CRON_SECRET)) {
    return NextResponse.json(
      {
        error:
          "Saknar eller felaktig auktorisering. Sätt CRON_SECRET i Vercel-env " +
          "och anropa med 'Authorization: Bearer <CRON_SECRET>'.",
      },
      { status: 401 },
    );
  }

  const url = new URL(request.url);
  const dryRunParam = url.searchParams.get("dryRun");
  const dryRun = dryRunParam === "1" || dryRunParam === "true";
  const retentionDays = resolveRetentionDays(process.env.RETENTION_DAYS);

  // Paus-flagga (toggle i dashboarden utan redeploy). När den är av kör cron
  // ärligt en no-op och loggar varför — den raderar aldrig något.
  if (!pruneEnabled(process.env.PRUNE_ENABLED)) {
    const skipped = {
      event: "blob-prune",
      skipped: true,
      reason: "PRUNE_ENABLED är av",
      dryRun,
      retentionDays,
    };
    console.log(JSON.stringify(skipped));
    return NextResponse.json(skipped);
  }

  const token = resolveEnvVar("BLOB_READ_WRITE_TOKEN");
  if (!token) {
    return NextResponse.json(
      { error: "BLOB_READ_WRITE_TOKEN saknas i miljön." },
      { status: 500 },
    );
  }

  try {
    const result = await pruneBlob({ token, retentionDays, dryRun });
    // En strukturerad rad så vinsten är verifierbar i Vercel-loggarna.
    console.log(
      JSON.stringify({
        event: "blob-prune",
        dryRun,
        retentionDays,
        prunedSites: result.prunedSites,
        prunedCount: result.prunedCount,
        keptCount: result.keptCount,
        freedBytes: result.freedBytes,
      }),
    );
    return NextResponse.json(result);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel under blob-prune.";
    console.error(JSON.stringify({ event: "blob-prune", error: message }));
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  return handle(request);
}

export async function POST(request: NextRequest) {
  return handle(request);
}
