import { NextResponse } from "next/server";

import { isHostedVercelRuntime } from "@/lib/hosted-python-runtime";
import { assertLocalhost } from "@/lib/localhost-guard";
import { RunNotFoundError, readRunFilesForStackblitz } from "@/lib/stackblitz-files";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  // Hostat serveras previewen från blob-manifestet och artefakter/trace ur
  // run-artifacts-tarballen (B199 v2) — men det FULLA filträdet per run
  // snapshotas inte till blob, så StackBlitz-fallbacken saknar källa.
  // Vanlig 404 utan `hostedNotice`: latch-kontraktet i
  // lib/hosted-run-artefacts.ts skulle annars stänga av de numera
  // fungerande artefakt-/trace-ytorna för resten av sessionen.
  if (isHostedVercelRuntime()) {
    return NextResponse.json(
      {
        error:
          "Körfilerna för enskilda runs serveras inte i den hostade vyn — " +
          "previewen läser blob-manifestet och artefakter/trace läses ur " +
          "run-artefakt-tarballen.",
      },
      { status: 404 },
    );
  }

  let runId: string;
  try {
    runId = (await context.params).runId;
  } catch {
    return NextResponse.json({ error: "Saknar runId i URL." }, { status: 400 });
  }

  try {
    const files = await readRunFilesForStackblitz(runId);
    return NextResponse.json({ runId, files });
  } catch (error) {
    if (error instanceof RunNotFoundError) {
      return NextResponse.json({ error: error.message }, { status: 404 });
    }
    const message =
      error instanceof Error ? error.message : "Okänt fel vid filhämtning.";
    const isClient = /Ogiltigt runId|pekar utanför/.test(message);
    return NextResponse.json({ error: message }, { status: isClient ? 400 : 500 });
  }
}
