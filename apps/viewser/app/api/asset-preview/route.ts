import { existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { extname } from "node:path";

import { NextRequest, NextResponse } from "next/server";

import { getAssetStore } from "@/lib/asset-store";
import { LocalAssetStore } from "@/lib/asset-store/local";
import { assertLocalhost } from "@/lib/localhost-guard";

/**
 * GET /api/asset-preview?assetId=...&siteId=...
 *
 * Returnerar en thumbnail av den uppladdade asset:n så wizardens
 * AssetCard kan rendera en preview. Beteende beror på vilken
 * `AssetStore`-driver som är aktiv:
 *
 *   - LocalAssetStore: strömmar bytes direkt från
 *     `data/uploads/<siteId>/<assetId>/optimized.webp` (eller SVG-
 *     originalet). no-store cache så thumbnailen syns omedelbart.
 *
 *   - VercelBlobAssetStore: HTTP 307-redirect till blob-URL:n så
 *     browsern hämtar bytes direkt från CDN:en (snabbare än att proxa
 *     genom Next.js dev-servern, och vi slipper buffra bytes onödigt).
 *     Vi slår upp `AssetRef.sourceUrl` via `store.load()`.
 *
 * Localhost-only.
 */

const SITE_ID_PATTERN = /^[a-z0-9_-]{1,64}$/i;
const ASSET_ID_PATTERN = /^[A-Z0-9]{20,40}$/i;

const MIME_BY_EXT: Record<string, string> = {
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".mp4": "video/mp4",
  ".webm": "video/webm",
};

export async function GET(request: NextRequest) {
  const guard = assertLocalhost(request);
  if (guard) return guard;

  const params = request.nextUrl.searchParams;
  const assetId = params.get("assetId") ?? "";
  const siteId = params.get("siteId") ?? "__draft";

  if (!ASSET_ID_PATTERN.test(assetId)) {
    return NextResponse.json({ error: "Ogiltigt assetId." }, { status: 400 });
  }
  if (!SITE_ID_PATTERN.test(siteId)) {
    return NextResponse.json({ error: "Ogiltigt siteId." }, { status: 400 });
  }

  const store = getAssetStore();

  // Non-local-driver:s (idag bara VercelBlobAssetStore) har ingen
  // disk-sökväg. Vi slår upp manifestet och redirectar till blob-URL:n.
  if (!(store instanceof LocalAssetStore)) {
    let ref;
    try {
      ref = await store.load(siteId, assetId);
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Misslyckades läsa manifest.";
      return NextResponse.json({ error: message }, { status: 502 });
    }
    if (!ref || !ref.sourceUrl) {
      return NextResponse.json(
        { error: "Asset saknas i remote store (sourceUrl saknas)." },
        { status: 404 },
      );
    }
    // 307 Temporary Redirect bevarar metoden (GET) och säger åt browsern
    // att inte cacha redirecten själv — då slipper vi att en flyttad
    // asset visar gammal cache. CDN:en bakom blob-URL:n cache:ar
    // bytes:en själv så preview-hastigheten blir likvärdig disk.
    return NextResponse.redirect(ref.sourceUrl, {
      status: 307,
      headers: { "cache-control": "no-store" },
    });
  }

  let resolvedPath: string;
  try {
    resolvedPath = store.resolveOptimizedPath(siteId, assetId);
  } catch (caught) {
    const message =
      caught instanceof Error ? caught.message : "Hittade inte asset.";
    return NextResponse.json({ error: message }, { status: 404 });
  }

  if (!existsSync(resolvedPath)) {
    return NextResponse.json({ error: "Asset saknas på disk." }, { status: 404 });
  }

  const stats = statSync(resolvedPath);
  const mime =
    MIME_BY_EXT[extname(resolvedPath).toLowerCase()] ??
    "application/octet-stream";
  const bytes = await readFile(resolvedPath);

  // VIKTIGT: ingen browser-cache här. När operatören byter wizard-steg
  // re-mountar AssetCard:n och webbläsaren kan annars välja att försöka
  // re-validera mot servern (If-Modified-Since/ETag) mot ett 60s-fönster
  // som råkar landa precis när dev-servern just startat om — vilket
  // tidigare gjorde att thumbnails "försvann en stund efter". Filerna
  // ligger statiskt på disk så vi serverar dem alltid färska och låter
  // Next.js dev-servern bestämma response-storleken.
  const headers: Record<string, string> = {
    "content-type": mime,
    "content-length": String(stats.size),
    "cache-control": "no-store",
    // Förhindra MIME-sniffing oavsett innehåll. Stoppar t.ex. en
    // operatör-uppladdad "fake JPEG" som faktiskt är HTML från att
    // renderas som dokument i en flik.
    "x-content-type-options": "nosniff",
  };
  // SVG kan innehålla <script> + onload-attribut som kör i operatörens
  // dev-server-domän om någon öppnar /api/asset-preview-URL:n direkt
  // i en ny flik (inte via <img>, där JS är inaktivt). CSP `sandbox`
  // utan `allow-scripts` skapar en sandbox-kontext för det renderade
  // dokumentet där inline-script och event-handlers blockeras. Vi
  // tillåter `allow-same-origin` så att SVG:n fortfarande kan refera
  // till externa resurser via samma origin, men script + forms är av.
  // Bilder som laddas via <img src> ignorerar CSP-headern eftersom de
  // aldrig parsas som dokument, så denna fix påverkar inte AssetCard.
  if (mime === "image/svg+xml") {
    headers["content-security-policy"] = "sandbox allow-same-origin";
  }
  return new NextResponse(new Uint8Array(bytes), {
    status: 200,
    headers,
  });
}
