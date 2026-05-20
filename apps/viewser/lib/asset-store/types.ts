/**
 * Typer för AssetStore-driver:s. Matchar `$defs/assetRef` i
 * `governance/schemas/project-input.schema.json` så Project Input
 * kan acceptera samma form rakt av.
 */

export type AssetRole = "logo" | "hero" | "gallery";

export type AssetPlacement =
  | "home"
  | "about"
  | "services"
  | "projects"
  | "products"
  | "gallery";

export type VisionConfidence = "low" | "medium" | "high";

export interface AssetRef {
  assetId: string;
  filename: string;
  mimeType: "image/png" | "image/jpeg" | "image/webp" | "image/svg+xml";
  sizeBytes: number;
  width: number | null;
  height: number | null;
  alt: string;
  role: AssetRole;
  placement?: AssetPlacement;
  visionSubject?: string;
  visionConfidence?: VisionConfidence;
  /**
   * Publik URL där den optimerade bytes:n kan hämtas (HTTPS, ingen auth).
   *
   * Satt av `VercelBlobAssetStore` när ASSET_STORE_DRIVER=vercel-blob, då
   * raderna ovan inte räcker — filen ligger inte på disk utan i en remote
   * blob-store. `LocalAssetStore` lämnar fältet `undefined` (filen finns
   * under `data/uploads/<siteId>/<assetId>/optimized.webp`).
   *
   * `scripts/build_site.py copy_operator_uploads` ska föredra `sourceUrl`
   * framför disk-lookup när fältet finns (HTTP-fetch → skriv till
   * `public/uploads/<filename>`). Se `docs/backend-handoff.md` gap #11.
   */
  sourceUrl?: string;
}

export interface SaveAssetInput {
  siteId: string;
  buffer: Buffer;
  originalName: string;
  mimeType: AssetRef["mimeType"];
  role: AssetRole;
}

export interface SaveAssetVariant {
  /** Bytes faktiskt lagrade på disk (efter sharp-komprimering). */
  optimizedBytes: number;
  /** Filens slutgiltiga filename i /public/uploads/. */
  publicFilename: string;
  /** Pixel-bredd, null om SVG utan dims. */
  width: number | null;
  height: number | null;
}

export interface AssetStore {
  /**
   * Spara råfil + komprimerad variant + manifest. Returnerar den
   * AssetRef som ska skickas vidare i wizardens state och senare
   * patchas in i Project Input.
   */
  save(input: SaveAssetInput): Promise<{
    ref: AssetRef;
    variant: SaveAssetVariant;
  }>;

  /** Läs manifest.json för en tidigare sparad asset. Returnerar null om saknas. */
  load(siteId: string, assetId: string): Promise<AssetRef | null>;

  /** Absolut sökväg på disk för optimerad/orginalfil — används av Python copy-step. */
  resolveOptimizedPath(siteId: string, assetId: string): string;

  /** Public URL som genererad sajt kommer rendera (/uploads/<filename>). */
  publicUrl(ref: AssetRef): string;
}
