/**
 * LocalAssetStore — lagrar uppladdade assets på disk under
 * `data/uploads/<siteId>/<assetId>/`. Strukturen per asset:
 *
 *   data/uploads/<siteId>/<assetId>/
 *     ├── original.<ext>     råfilen som operatorn laddade upp
 *     ├── optimized.webp     sharp-komprimerad variant (≤200 KB)
 *     │                       SVG har ingen webp-variant; original används direkt
 *     └── manifest.json      AssetRef + vision-output
 *
 * Sökvägen `data/uploads/` är gitignored. Vid build kopierar
 * `copy_operator_uploads` i build_site.py den variant som passar
 * StackBlitz-payloaden (helst webp) till genererad sajts
 * `public/uploads/<filename>` så TSX kan referera den som `/uploads/<filename>`.
 */
import { existsSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { generateAssetId, slugifyFilename } from "./utils";
import { optimizeImage } from "./sharp-pipeline";
import { classifyAsset } from "./vision";
import type {
  AssetMimeType,
  AssetRef,
  AssetStore,
  SaveAssetInput,
  SaveAssetVariant,
} from "./types";

const UPLOADS_ROOT = path.resolve(process.cwd(), "..", "..", "data", "uploads");

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

export class LocalAssetStore implements AssetStore {
  constructor(private readonly rootDir: string = UPLOADS_ROOT) {}

  private assetDir(siteId: string, assetId: string): string {
    return path.join(this.rootDir, siteId, assetId);
  }

  async save(
    input: SaveAssetInput,
  ): Promise<{ ref: AssetRef; variant: SaveAssetVariant }> {
    const assetId = generateAssetId();
    const dir = this.assetDir(input.siteId, assetId);
    await mkdir(dir, { recursive: true });

    const originalExt = mimeExtension(input.mimeType);
    const originalPath = path.join(dir, `original.${originalExt}`);
    await writeFile(originalPath, input.buffer);

    // Tre branches på mime-typ:
    //  - SVG       : passerar orörd (vektor, ingen webp-konvertering)
    //  - Image     : sharp → optimized.webp + GPT Vision-klassificering
    //  - Video     : passerar orörd, ingen sharp/vision (Fas 1.4)
    //
    // För video sätter vi alt-text deterministiskt från role ("Bakgrundsvideo")
    // eftersom vi inte vill anropa Vision-modellen för en frame som inte
    // representerar slut-uppspelningen. Ratio (width/height) lämnas null
    // — backend kan läsa det från video-fil-headern vid render om det
    // behövs (HTML5 <video>-elementet hanterar själv aspect-ratio).
    let optimizedBytes: number;
    let width: number | null;
    let height: number | null;
    let publicMime: AssetMimeType;
    let publicExt: string;
    let altText: string;
    let visionSubject: string | undefined;
    let visionConfidence: AssetRef["visionConfidence"];
    let placement: AssetRef["placement"];

    if (isVideoMime(input.mimeType)) {
      // Video — direkt-skrivning, ingen optimering. <video>-elementet i
      // browsern hanterar codec/container. Filen ligger redan på disk
      // som original.<ext> (skrev ovan); vi sätter optimizedBytes lika
      // med originalets storlek så ref-metadatan är konsistent.
      optimizedBytes = input.buffer.byteLength;
      width = null;
      height = null;
      publicMime = input.mimeType;
      publicExt = originalExt;
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
      await writeFile(path.join(dir, "optimized.webp"), optimized.buffer);
      optimizedBytes = optimized.buffer.byteLength;
      width = optimized.width;
      height = optimized.height;
      publicMime = "image/webp";
      publicExt = "webp";
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
    };

    const manifestPath = path.join(dir, "manifest.json");
    await writeFile(manifestPath, JSON.stringify(ref, null, 2), "utf8");

    return {
      ref,
      variant: { optimizedBytes, publicFilename, width, height },
    };
  }

  async load(siteId: string, assetId: string): Promise<AssetRef | null> {
    const manifestPath = path.join(this.assetDir(siteId, assetId), "manifest.json");
    if (!existsSync(manifestPath)) return null;
    const raw = await readFile(manifestPath, "utf8");
    return JSON.parse(raw) as AssetRef;
  }

  resolveOptimizedPath(siteId: string, assetId: string): string {
    const dir = this.assetDir(siteId, assetId);
    const webp = path.join(dir, "optimized.webp");
    if (existsSync(webp)) return webp;
    // Original-format fallback. ``mp4``/``webm`` läggs sist eftersom de
    // är största/sällsynta filtyperna — den vanliga vägen hittar webp/
    // svg/png/jpg först.
    for (const ext of ["svg", "png", "jpg", "webp", "mp4", "webm"]) {
      const candidate = path.join(dir, `original.${ext}`);
      if (existsSync(candidate)) return candidate;
    }
    throw new Error(
      `Asset ${assetId} för site ${siteId} saknar varianter på disk.`,
    );
  }

  publicUrl(ref: AssetRef): string {
    return `/uploads/${ref.filename}`;
  }
}
