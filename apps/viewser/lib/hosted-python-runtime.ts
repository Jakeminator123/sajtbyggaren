import { NextResponse } from "next/server";

/**
 * Vercel-hosted Viewser can render the UI, but the prompt/build/scrape
 * actions still shell out to repo-local Python scripts. Those actions are
 * local-operator tooling until they move to a real backend runtime.
 */
export function isHostedVercelRuntime(): boolean {
  return process.env.VERCEL === "1";
}

export function hostedPythonRuntimeUnavailable(feature: string): NextResponse {
  return NextResponse.json(
    {
      ok: false,
      code: "hosted-python-runtime-unavailable",
      feature,
      error:
        "Den här åtgärden kör Python-skript lokalt och stöds bara i lokal Viewser just nu. Den hostade Vercel-vyn kan visa UI och befintliga artefakter, men kan inte skapa eller bygga sajter förrän Python-kedjan flyttas till en riktig backend-runtime.",
    },
    { status: 501 },
  );
}
