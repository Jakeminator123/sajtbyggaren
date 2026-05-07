import { NextResponse } from "next/server";

import { listSiteDossiers } from "@/lib/dossiers";
import { listRuns } from "@/lib/runs";

export async function GET() {
  try {
    const [runs, dossiers] = await Promise.all([listRuns(20), listSiteDossiers()]);
    return NextResponse.json({ runs, dossiers });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid hämtning av runs.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
