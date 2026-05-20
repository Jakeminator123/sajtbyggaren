/**
 * AssetStore — driver-baserad abstraktion för operatör-uppladdade bilder.
 *
 * Aktiva driver:s:
 *
 *   - `local` (default) → `LocalAssetStore`, lagrar i
 *     `data/uploads/<siteId>/<assetId>/`. Snabbast lokalt och vid CI;
 *     `copy_operator_uploads` i build_site.py läser direkt från disk.
 *
 *   - `vercel-blob` → `VercelBlobAssetStore`, lagrar i en Vercel Blob-
 *     store (public). Kräver `BLOB_READ_WRITE_TOKEN` i env. AssetRef:n
 *     får ett `sourceUrl`-fält som backend ska föredra över disk-lookup.
 *
 * Inga andra filer i kodbasen ska känna till skillnaden — interface:t
 * är kontraktet. Lägga till en S3-driver eller annan blob-tjänst sker
 * isolerat i en ny `./s3.ts` (eller liknande) och registreras i switch:en.
 */
import { LocalAssetStore } from "./local";
import { VercelBlobAssetStore } from "./vercel-blob";
import type { AssetRef, AssetRole, AssetStore } from "./types";

export type { AssetRef, AssetRole, AssetStore };
export { LocalAssetStore, VercelBlobAssetStore };

let cachedStore: AssetStore | null = null;

export function getAssetStore(): AssetStore {
  if (cachedStore) return cachedStore;
  const driver = (process.env.ASSET_STORE_DRIVER ?? "local")
    .trim()
    .toLowerCase();
  if (driver === "local") {
    cachedStore = new LocalAssetStore();
    return cachedStore;
  }
  if (driver === "vercel-blob") {
    cachedStore = new VercelBlobAssetStore();
    return cachedStore;
  }
  throw new Error(
    `ASSET_STORE_DRIVER=${driver} är inte implementerad. ` +
      `Tillåtna värden: "local" (default), "vercel-blob".`,
  );
}

/** Test-only: nollställ singleton mellan tester. */
export function resetAssetStoreForTests(): void {
  cachedStore = null;
}
