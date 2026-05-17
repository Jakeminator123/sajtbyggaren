import { existsSync, statSync } from "node:fs";
import { extname } from "node:path";

import { NextRequest, NextResponse } from "next/server";

import { getAssetStore } from "@/lib/asset-store";
import { assertLocalhost } from "@/lib/localhost-guard";
import { readFile } from "node:fs/promises";

/**
 * GET /api/asset-preview?assetId=...&siteId=...
 *
 * Strömmar tillbaka den optimerade webp-varianten (eller SVG-originalet)
 * för en uppladdad asset så att wizardens AssetCard kan rendera en
 * thumbnail. Localhost-only.
 *
 * Den här endpointen läser bara från `data/uploads/` — inga skrivningar.
 */

const SITE_ID_PATTERN = /^[a-z0-9_-]{1,64}$/i;
const ASSET_ID_PATTERN = /^[A-Z0-9]{20,40}$/i;

const MIME_BY_EXT: Record<string, string> = {
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
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

  let resolvedPath: string;
  try {
    resolvedPath = getAssetStore().resolveOptimizedPath(siteId, assetId);
  } catch (caught) {
    const message = caught instanceof Error ? caught.message : "Hittade inte asset.";
    return NextResponse.json({ error: message }, { status: 404 });
  }

  if (!existsSync(resolvedPath)) {
    return NextResponse.json({ error: "Asset saknas på disk." }, { status: 404 });
  }

  const stats = statSync(resolvedPath);
  const mime = MIME_BY_EXT[extname(resolvedPath).toLowerCase()] ?? "application/octet-stream";
  const bytes = await readFile(resolvedPath);

  return new NextResponse(new Uint8Array(bytes), {
    status: 200,
    headers: {
      "content-type": mime,
      "content-length": String(stats.size),
      "cache-control": "private, max-age=60",
    },
  });
}
