import { NextResponse } from "next/server";

import { isHostedVercelRuntime } from "@/lib/hosted-python-runtime";
import {
  fetchHostedRunArtefactsTar,
  hostedRunArtefactBundle,
  resolveHostedRunEntry,
} from "@/lib/hosted-run-history";
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
 *
 * Hostat (VERCEL=1, B199 v2): bundeln läses ur versionens
 * run-artifacts.tar.gz i blob via KV-indexet. En run som inte kan lösas
 * (byggd lokalt, eller före artefakt-persistensen) svarar en VANLIG 404
 * utan `hostedNotice` — latch-kontraktet i lib/hosted-run-artefacts.ts är
 * reserverat för "hela förmågan saknas hostat", vilket inte längre stämmer.
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

  if (isHostedVercelRuntime()) {
    try {
      const entry = await resolveHostedRunEntry(runId);
      const files = entry ? await fetchHostedRunArtefactsTar(entry) : null;
      if (!entry || !files) {
        return NextResponse.json(
          {
            error:
              "Run-artefakter saknas i den hostade vyn för denna run — den " +
              "byggdes lokalt eller före hostad artefakt-persistens (B199).",
          },
          { status: 404 },
        );
      }
      return NextResponse.json(hostedRunArtefactBundle(entry, files));
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Okänt fel vid hostad artefakt-läsning.";
      return NextResponse.json({ error: message }, { status: 500 });
    }
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
