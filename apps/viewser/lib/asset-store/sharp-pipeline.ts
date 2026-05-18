/**
 * Sharp-pipelinen producerar en webp-variant som passar StackBlitz-payloaden
 * (`MAX_FILE_BYTES = 250_000` i `apps/viewser/lib/stackblitz-files.ts`).
 * Strategi:
 *   1. Resize ned till max-bredd 1920px (behåller aspekt, ingen upscale)
 *   2. Encoda som webp, kvalitet 82
 *   3. Om resulterande bytes > BUDGET, sänk kvalitet i 5-steg ner till 60
 *   4. Om vi fortfarande är över BUDGET vid kvalitet 60, returnera ändå —
 *      uppladdnings-API:t klassar då varningen och visar för operatorn,
 *      men byggena fortsätter. StackBlitz hoppar ev. över filen om den
 *      är för stor, men 99 % av JPG/PNG hamnar under 200 KB efter 1920px webp 82.
 */
import sharp from "sharp";

const TARGET_BUDGET_BYTES = 200_000;
const MAX_WIDTH_PX = 1920;

export interface OptimizedImage {
  buffer: Buffer;
  width: number | null;
  height: number | null;
  quality: number;
}

export async function optimizeImage(input: Buffer): Promise<OptimizedImage> {
  const base = sharp(input, { failOn: "error" }).rotate(); // honor EXIF
  const meta = await base.metadata();
  const resized =
    meta.width && meta.width > MAX_WIDTH_PX
      ? base.resize({ width: MAX_WIDTH_PX, withoutEnlargement: true })
      : base;

  let quality = 82;
  let buffer = await resized.webp({ quality, effort: 5 }).toBuffer();
  while (buffer.byteLength > TARGET_BUDGET_BYTES && quality > 60) {
    quality -= 5;
    buffer = await sharp(input, { failOn: "error" })
      .rotate()
      .resize({ width: MAX_WIDTH_PX, withoutEnlargement: true })
      .webp({ quality, effort: 5 })
      .toBuffer();
  }

  const outMeta = await sharp(buffer).metadata();
  return {
    buffer,
    width: outMeta.width ?? null,
    height: outMeta.height ?? null,
    quality,
  };
}
