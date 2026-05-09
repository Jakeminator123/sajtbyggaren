import { NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";
import { readRunArtefacts } from "@/lib/runs";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

/**
 * Return the four canonical Engine Run artefakter for a given runId in
 * a single response. Missing files are returned as `null` and listed
 * under `missingArtefacts` so the Builder UX MVP can render "saknas i
 * äldre run" labels instead of failing with 500. This route never
 * invents artefakter or normalises shapes - the underlying
 * scripts/build_site.py and scripts/dev_generate.py contracts apply.
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

  try {
    const bundle = await readRunArtefacts(runId);
    return NextResponse.json(bundle);
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid läsning av artefakter.";
    const isClient = /Ogiltigt runId|pekar utanför|saknar katalog/.test(message);
    return NextResponse.json({ error: message }, { status: isClient ? 400 : 500 });
  }
}
