/**
 * optimize-images.mjs — bygg servbara, lättviktiga yrkesbilder.
 *
 * Källa: REPO-ROOT public/Bilder/*.png (~7–8 MB råa PNG:er, gitignorade,
 * lokal-bara). Next.js serverar INTE repo-root public/, så detta script
 * konverterar dem till WebP och skriver dem till apps/viewser/public/Bilder/
 * (som faktiskt serveras). De optimerade derivaten committas (~några MB
 * totalt) per operatörsbeslut D4.
 *
 * P0: en bredd (1280w) WebP per bild räcker för startsidan + räcker som
 * källa för next/image-nedskalning i bildväggen (P3). Roll-specifika
 * varianter (grid/hero/OG) + blurDataURL-manifest läggs till i asset-fasen.
 *
 * Körs: npm run assets:images  (från apps/viewser/)
 */
import { existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = resolve(HERE, "../../../public/Bilder");
const OUT_DIR = resolve(HERE, "../public/Bilder");

const TARGET_WIDTH = 1280;
const WEBP_QUALITY = 72;

async function main() {
  if (!existsSync(SRC_DIR)) {
    console.error(`[optimize-images] Källmapp saknas: ${SRC_DIR}`);
    process.exit(1);
  }
  mkdirSync(OUT_DIR, { recursive: true });

  const pngs = readdirSync(SRC_DIR).filter((f) => f.toLowerCase().endsWith(".png"));
  if (pngs.length === 0) {
    console.error(`[optimize-images] Inga PNG:er i ${SRC_DIR}`);
    process.exit(1);
  }

  let totalOut = 0;
  for (const file of pngs) {
    const stem = file.replace(/\.png$/i, "");
    const inPath = join(SRC_DIR, file);
    const outPath = join(OUT_DIR, `${stem}.webp`);
    await sharp(inPath)
      .resize({ width: TARGET_WIDTH, withoutEnlargement: true })
      .webp({ quality: WEBP_QUALITY })
      .toFile(outPath);
    const kb = Math.round(statSync(outPath).size / 1024);
    totalOut += kb;
    console.log(`  ${file}  ->  Bilder/${stem}.webp  (${kb} KB)`);
  }
  console.log(
    `[optimize-images] Klart: ${pngs.length} bilder, ~${Math.round(totalOut / 1024)} MB totalt -> ${OUT_DIR}`,
  );
}

main().catch((err) => {
  console.error("[optimize-images] Fel:", err);
  process.exit(1);
});
