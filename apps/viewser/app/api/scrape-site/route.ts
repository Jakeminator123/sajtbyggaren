import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";

import { assertLocalhost } from "@/lib/localhost-guard";
import { runScrapeSite } from "@/lib/scrape-runner";

/**
 * POST /api/scrape-site — discovery-wizard URL-scrape.
 *
 * Frontend (`apps/viewser/components/discovery-wizard/steps/company-step.tsx`)
 * skickar in en URL från operatorn. Vi spawnar
 * `scripts/scrape_site.py --url <url>` som hämtar HTML, parsar med
 * BeautifulSoup och (om OPENAI_API_KEY finns) berikar med en LLM-
 * syntes. Resultatet är wizard-fält som operatorn kan granska och
 * justera innan sajten byggs.
 *
 * Localhost-only — speglar samma guard som /api/prompt och /api/build.
 */

const ScrapePayloadSchema = z.object({
  url: z
    .string()
    .trim()
    .min(3, "URL saknas.")
    .max(500, "URL får vara max 500 tecken."),
  companyName: z
    .string()
    .trim()
    .max(200, "companyName får vara max 200 tecken.")
    .optional(),
});

export async function POST(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let payload: z.infer<typeof ScrapePayloadSchema>;
  try {
    const json = await request.json().catch(() => ({}));
    payload = ScrapePayloadSchema.parse(json);
  } catch (error) {
    if (error instanceof z.ZodError) {
      const message = error.issues[0]?.message ?? "Ogiltig scrape-payload.";
      return NextResponse.json({ ok: false, error: message }, { status: 400 });
    }
    const message =
      error instanceof Error ? error.message : "Okänt fel vid scrape-anropet.";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }

  try {
    const result = await runScrapeSite(payload.url, {
      companyName: payload.companyName,
    });
    return NextResponse.json(result, { status: result.ok ? 200 : 422 });
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Okänt fel vid scrape-anropet.";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
