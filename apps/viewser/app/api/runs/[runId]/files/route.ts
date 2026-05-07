import { NextResponse } from "next/server";

import { readRunFilesForStackblitz } from "@/lib/stackblitz-files";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  try {
    const { runId } = await context.params;
    const files = await readRunFilesForStackblitz(runId);
    return NextResponse.json({ runId, files });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid filhämtning.";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
