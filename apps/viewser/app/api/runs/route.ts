import { NextResponse } from "next/server";

import { assertLocalhost } from "@/lib/localhost-guard";
import { listProjectInputs } from "@/lib/project-inputs";
import { listRuns } from "@/lib/runs";

export async function GET(request: Request) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  try {
    const [runs, projectInputs] = await Promise.all([
      listRuns(20),
      listProjectInputs(),
    ]);
    return NextResponse.json({ runs, projectInputs });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid hämtning av runs.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
