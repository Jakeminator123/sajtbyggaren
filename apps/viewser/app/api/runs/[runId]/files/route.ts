import { NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";
import { RunNotFoundError, readRunFilesForStackblitz } from "@/lib/stackblitz-files";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

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
