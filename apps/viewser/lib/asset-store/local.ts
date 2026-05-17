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
  AssetRef,
  AssetStore,
  SaveAssetInput,
  SaveAssetVariant,
} from "./types";

const UPLOADS_ROOT = path.resolve(process.cwd(), "..", "..", "data", "uploads");

function mimeExtension(mime: AssetRef["mimeType"]): string {
  switch (mime) {
    case "image/png":
      return "png";
    case "image/jpeg":
      return "jpg";
    case "image/webp":
      return "webp";
    case "image/svg+xml":
      return "svg";
  }
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

    // SVG passerar orörd — vektor är redan billig och webp-konvertering
    // skulle förlora skalbarheten. Övriga format går genom sharp.
    let optimizedBytes: number;
    let width: number | null;
    let height: number | null;
    let publicMime: AssetRef["mimeType"];
    let publicExt: string;
    if (input.mimeType === "image/svg+xml") {
      optimizedBytes = input.buffer.byteLength;
      width = null;
      height = null;
      publicMime = "image/svg+xml";
      publicExt = "svg";
    } else {
      const optimized = await optimizeImage(input.buffer);
      await writeFile(path.join(dir, "optimized.webp"), optimized.buffer);
      optimizedBytes = optimized.buffer.byteLength;
      width = optimized.width;
      height = optimized.height;
      publicMime = "image/webp";
      publicExt = "webp";
    }

    const stem = slugifyFilename(input.originalName);
    const publicFilename = `${stem}-${assetId.slice(0, 8).toLowerCase()}.${publicExt}`;

    // Vision-klassificering körs på samma buffer som operatorn laddade
    // upp (inte den webp-komprimerade) för att modellen ska se högsta
    // kvalitet vid analys. SVG → deterministisk mock (vision.ts hanterar).
    const vision = await classifyAsset({
      buffer: input.buffer,
      mimeType: input.mimeType,
      role: input.role,
    });

    const ref: AssetRef = {
      assetId,
      filename: publicFilename,
      mimeType: publicMime,
      sizeBytes: optimizedBytes,
      width,
      height,
      alt: vision.suggestedAltText,
      role: input.role,
      // Logo har ingen placement (renderar i header/footer) — bara
      // hero och gallery skickar tillbaka recommendedPlacement.
      ...(input.role === "logo"
        ? {}
        : {
            placement:
              input.role === "hero" ? "home" : vision.recommendedPlacement,
          }),
      visionSubject: vision.subject,
      visionConfidence: vision.confidence,
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
    // SVG-original (eller pre-optimized fallback)
    for (const ext of ["svg", "png", "jpg", "webp"]) {
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
