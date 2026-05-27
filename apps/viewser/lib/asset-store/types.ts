/**
 * Typer för AssetStore-driver:s. Matchar `$defs/assetRef` i
 * `governance/schemas/project-input.schema.json` så Project Input
 * kan acceptera samma form rakt av.
 */

export type AssetRole =
  | "logo"
  | "hero"
  | "gallery"
  // Fas 1.2 — extra-roles för wizardens steg 5. Backend renderar:
  //   favicon         → <link rel="icon"> + <link rel="apple-touch-icon">
  //   ogImage         → <meta property="og:image"> + Twitter Card
  //   backgroundVideo → <video autoPlay loop muted playsInline> i hero
  // Roles persisteras till `dossier.media[<role>]` (efter Jakob M2).
  // Tills dess används de av wizard-payload som strukturerad referens
  // i `answers.media` så framtida persistering bara behöver mappa fält.
  | "favicon"
  | "ogImage"
  | "backgroundVideo";

export type AssetPlacement =
  | "home"
  | "about"
  | "services"
  | "projects"
  | "products"
  | "gallery";

export type VisionConfidence = "low" | "medium" | "high";

/**
 * Image MIMEs som sharp-pipelinen kan optimera till webp. Video och andra
 * binary-typer ligger utanför detta union eftersom de bypass:ar
 * sharp + vision-klassificeringen.
 */
export type ImageMimeType =
  | "image/png"
  | "image/jpeg"
  | "image/webp"
  | "image/svg+xml";

/**
 * Video MIMEs som backgroundVideo-rollen stödjer. Sharp opererar inte
 * på video; uploads passerar orörda till disk/Blob. <video>-elementet
 * i browser hanterar containerformat & codec själv så vi behöver inte
 * transkoda.
 */
export type VideoMimeType = "video/mp4" | "video/webm";

export type AssetMimeType = ImageMimeType | VideoMimeType;

export interface AssetRef {
  assetId: string;
  filename: string;
  mimeType: AssetMimeType;
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
   * `scripts/build_site.py copy_operator_uploads` är disk-first; när
   * disk-lookup misslyckas och `sourceUrl` finns + pekar på en
   * allowlist:ad HTTPS-host (`public.blob.vercel-storage.com`) HTTP-
   * fetchas bytes och skrivs till `public/uploads/<filename>` med en
   * 8 MB cap och 15 s timeout. Se `docs/backend-handoff.md` gap #11
   * för historik (gap stängd, PR #66 + senare refinements).
   */
  sourceUrl?: string;
}

export interface SaveAssetInput {
  siteId: string;
  buffer: Buffer;
  originalName: string;
  mimeType: AssetMimeType;
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

  /** Absolut sökväg på disk för optimerad/orginalfil — endast LocalAssetStore. */
  resolveOptimizedPath?(siteId: string, assetId: string): string;

  /** Public URL som genererad sajt kommer rendera (/uploads/<filename>). */
  publicUrl(ref: AssetRef): string;
}
