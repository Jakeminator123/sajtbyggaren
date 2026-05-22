/**
 * VercelBlobAssetStore — lagrar uppladdade assets i en Vercel Blob-store
 * (public access). Aktiveras när `ASSET_STORE_DRIVER=vercel-blob` och
 * `BLOB_READ_WRITE_TOKEN` är satt i env.
 *
 * Layout per asset i blob-store:n (samma struktur som LocalAssetStore på
 * disk, så mentalmodellen är identisk):
 *
 *   <siteId>/<assetId>/original.<ext>
 *   <siteId>/<assetId>/optimized.webp   (SVG hoppas över — original används)
 *   <siteId>/<assetId>/manifest.json
 *
 * `addRandomSuffix: false` används för att path:en ska vara deterministisk
 * — annars genererar Blob:en ett random suffix per put som hade brutit
 * `load()`-lookup via list-prefix.
 *
 * Skillnaden mot LocalAssetStore som backend måste känna till:
 *
 *   - `AssetRef.sourceUrl` är satt till blob-URL:en för `optimized.webp`
 *     (eller `original.svg`/`original.<ext>` om webp hoppades över).
 *     `scripts/build_site.py copy_operator_uploads` ska föredra detta
 *     fält framför disk-lookup — se `docs/backend-handoff.md` gap #11.
 *
 *   - `resolveOptimizedPath()` kastar — det finns ingen disk-sökväg.
 *     Använd `ref.sourceUrl` istället i den lilla mängd kallare som
 *     idag förlitar sig på disk (bara `/api/asset-preview` lokalt).
 *
 *   - `publicUrl(ref)` returnerar fortsatt `/uploads/<filename>` eftersom
 *     den genererade sajten — efter att backend kopierat in bytes via
 *     copy_operator_uploads — refererar bilden lokalt under public/uploads/.
 *     Blob-URL:n är bara en transport mellan operatörens upload och
 *     build-tillfället; slutsajten är fortsatt fristående.
 */
import { head, list, put } from "@vercel/blob";

import { optimizeImage } from "./sharp-pipeline";
import type {
  AssetMimeType,
  AssetRef,
  AssetStore,
  SaveAssetInput,
  SaveAssetVariant,
} from "./types";
import { generateAssetId, slugifyFilename } from "./utils";
import { classifyAsset } from "./vision";

function mimeExtension(mime: AssetMimeType): string {
  switch (mime) {
    case "image/png":
      return "png";
    case "image/jpeg":
      return "jpg";
    case "image/webp":
      return "webp";
    case "image/svg+xml":
      return "svg";
    case "video/mp4":
      return "mp4";
    case "video/webm":
      return "webm";
  }
}

function isVideoMime(mime: AssetMimeType): boolean {
  return mime === "video/mp4" || mime === "video/webm";
}

function requireToken(): string {
  const token = process.env.BLOB_READ_WRITE_TOKEN;
  if (!token || token.trim().length === 0) {
    throw new Error(
      "VercelBlobAssetStore: BLOB_READ_WRITE_TOKEN saknas i env. " +
        "Sätt den i apps/viewser/.env.local (hämtas från Vercel → " +
        "Storage → <ditt blob-store> → .env.local-fliken).",
    );
  }
  return token;
}

export class VercelBlobAssetStore implements AssetStore {
  constructor(private readonly tokenOverride?: string) {}

  private token(): string {
    return this.tokenOverride ?? requireToken();
  }

  private pathFor(siteId: string, assetId: string, leaf: string): string {
    return `${siteId}/${assetId}/${leaf}`;
  }

  async save(
    input: SaveAssetInput,
  ): Promise<{ ref: AssetRef; variant: SaveAssetVariant }> {
    const token = this.token();
    const assetId = generateAssetId();

    const originalExt = mimeExtension(input.mimeType);
    const originalPut = await put(
      this.pathFor(input.siteId, assetId, `original.${originalExt}`),
      input.buffer,
      {
        access: "public",
        token,
        contentType: input.mimeType,
        addRandomSuffix: false,
        allowOverwrite: false,
      },
    );

    // Tre branches (samma som LocalAssetStore.save):
    //  - SVG     : ingen optimering, sourceUrl pekar mot original.svg
    //  - Image   : sharp → optimized.webp, sourceUrl mot optimized
    //  - Video   : ingen optimering, sourceUrl mot original.<mp4|webm>
    let optimizedBytes: number;
    let width: number | null;
    let height: number | null;
    let publicMime: AssetMimeType;
    let publicExt: string;
    let optimizedUrl: string;
    let altText: string;
    let visionSubject: string | undefined;
    let visionConfidence: AssetRef["visionConfidence"];
    let placement: AssetRef["placement"];

    if (isVideoMime(input.mimeType)) {
      optimizedBytes = input.buffer.byteLength;
      width = null;
      height = null;
      publicMime = input.mimeType;
      publicExt = originalExt;
      // ``head()`` skulle räcka, men ``put()`` returnerar redan URL:n
      // för originalets blob, så vi använder den för att slippa en
      // extra round-trip till Vercel API.
      optimizedUrl = originalPut.url;
      altText = "Bakgrundsvideo";
      visionSubject = undefined;
      visionConfidence = undefined;
      placement = "home";
    } else if (input.mimeType === "image/svg+xml") {
      optimizedBytes = input.buffer.byteLength;
      width = null;
      height = null;
      publicMime = "image/svg+xml";
      publicExt = "svg";
      // SVG har ingen separat optimized-fil. ``head()`` ger oss den
      // canoniska URL:n inklusive Vercel:s store-prefix.
      const originalBlob = await head(
        this.pathFor(input.siteId, assetId, `original.${originalExt}`),
        { token },
      );
      optimizedUrl = originalBlob.url;
      const vision = await classifyAsset({
        buffer: input.buffer,
        mimeType: input.mimeType,
        role: input.role,
      });
      altText = vision.suggestedAltText;
      visionSubject = vision.subject;
      visionConfidence = vision.confidence;
      placement =
        input.role === "logo"
          ? undefined
          : input.role === "hero"
            ? "home"
            : vision.recommendedPlacement;
    } else {
      const optimized = await optimizeImage(input.buffer);
      const optimizedPut = await put(
        this.pathFor(input.siteId, assetId, "optimized.webp"),
        optimized.buffer,
        {
          access: "public",
          token,
          contentType: "image/webp",
          addRandomSuffix: false,
          allowOverwrite: false,
        },
      );
      optimizedBytes = optimized.buffer.byteLength;
      width = optimized.width;
      height = optimized.height;
      publicMime = "image/webp";
      publicExt = "webp";
      optimizedUrl = optimizedPut.url;
      const vision = await classifyAsset({
        buffer: input.buffer,
        mimeType: input.mimeType,
        role: input.role,
      });
      altText = vision.suggestedAltText;
      visionSubject = vision.subject;
      visionConfidence = vision.confidence;
      placement =
        input.role === "logo"
          ? undefined
          : input.role === "hero"
            ? "home"
            : vision.recommendedPlacement;
    }

    const stem = slugifyFilename(input.originalName);
    const publicFilename = `${stem}-${assetId.slice(0, 8).toLowerCase()}.${publicExt}`;

    const ref: AssetRef = {
      assetId,
      filename: publicFilename,
      mimeType: publicMime,
      sizeBytes: optimizedBytes,
      width,
      height,
      alt: altText,
      role: input.role,
      ...(placement ? { placement } : {}),
      ...(visionSubject ? { visionSubject } : {}),
      ...(visionConfidence ? { visionConfidence } : {}),
      sourceUrl: optimizedUrl,
    };

    // Manifest:en lagras i blob:en så `load()` (och en framtida server-
    // side admin-vy) kan slå upp AssetRef:n på (siteId, assetId) utan
    // att vandra hela list-katalogen. Filen är public men innehåller
    // bara metadata om assetn — inget hemligt.
    await put(
      this.pathFor(input.siteId, assetId, "manifest.json"),
      JSON.stringify(ref, null, 2),
      {
        access: "public",
        token,
        contentType: "application/json",
        addRandomSuffix: false,
        allowOverwrite: true,
      },
    );

    return {
      ref,
      variant: { optimizedBytes, publicFilename, width, height },
    };
  }

  async load(siteId: string, assetId: string): Promise<AssetRef | null> {
    const token = this.token();
    const prefix = `${siteId}/${assetId}/manifest.json`;
    // Vi listar med prefix för att verifiera att manifest:en finns innan
    // vi gör HTTP-fetch — annars riskerar vi en 404-roundtrip mot CDN:en.
    const listing = await list({ token, prefix, limit: 1 });
    const blob = listing.blobs[0];
    if (!blob) return null;
    const response = await fetch(blob.url, { cache: "no-store" });
    if (!response.ok) return null;
    const raw = await response.text();
    try {
      return JSON.parse(raw) as AssetRef;
    } catch {
      return null;
    }
  }

  resolveOptimizedPath(_siteId: string, assetId: string): string {
    throw new Error(
      `VercelBlobAssetStore.resolveOptimizedPath() är inte stödd — bytes ligger ` +
        `i Vercel Blob, inte på disk. Använd ref.sourceUrl istället ` +
        `(asset ${assetId}). /api/asset-preview redirectar dit automatiskt.`,
    );
  }

  publicUrl(ref: AssetRef): string {
    // Den GENERERADE sajten serverar bilden lokalt från public/uploads/
    // — copy_operator_uploads i backend fetchar ref.sourceUrl vid build
    // och skriver bytes till `public/uploads/<filename>`. Blob är bara
    // transport mellan upload och build; slutsajten är fortsatt fristående.
    return `/uploads/${ref.filename}`;
  }
}
