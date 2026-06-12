import { NextResponse } from "next/server";

import { isHostedVercelRuntime } from "@/lib/hosted-python-runtime";
import { assertLocalhost } from "@/lib/localhost-guard";
import {
  readHostedSiteComposition,
  readLocalSiteComposition,
  SITE_ID_PATTERN,
} from "@/lib/site-composition";

type RouteContext = {
  params: Promise<{ siteId: string }>;
};

/**
 * GET /api/site/[siteId]/composition — "Projektinnehåll"-bilden för en
 * sajt, DERIVERAD ur befintliga källor (senaste runens artefakter,
 * genererad package.json/component-manifest, project-input). Ingen ny
 * lagring och inga nya artefakter — se lib/site-composition.ts för
 * exakta källor och degraderingsregler.
 *
 * Lokalt läses allt från disk (data/runs/ + data/prompt-inputs/).
 * Hostat (VERCEL=1) läses samma bild ur B199-kedjan: KV-indexet →
 * run-artifacts.tar.gz → tarballens filer; saknade källor ger en
 * partiell bild med ``hostedNotice`` (hostedRuntimeNotice-mönstret),
 * aldrig påhittade data.
 *
 * Svar: SiteComposition (alla fält defensivt nullbara). 400 vid ogiltigt
 * siteId, 404 när sajten saknar både runs och project-input.
 */
export async function GET(request: Request, context: RouteContext) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  let siteId: string;
  try {
    siteId = (await context.params).siteId;
  } catch {
    return NextResponse.json({ error: "Saknar siteId i URL." }, { status: 400 });
  }

  if (!SITE_ID_PATTERN.test(siteId) || siteId.length > 100) {
    return NextResponse.json(
      {
        error:
          `Ogiltigt siteId: '${siteId}'. Tillåtet: gemener, siffror och ` +
          "bindestreck.",
      },
      { status: 400 },
    );
  }

  try {
    const composition = isHostedVercelRuntime()
      ? await readHostedSiteComposition(siteId)
      : await readLocalSiteComposition(siteId);
    if (!composition) {
      return NextResponse.json(
        {
          error:
            "Ingen byggd sajt hittades för detta siteId — bygg sajten " +
            "först, sedan kan Projektinnehåll visas.",
        },
        { status: 404 },
      );
    }
    return NextResponse.json(composition);
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Okänt fel vid läsning av projektinnehåll.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
