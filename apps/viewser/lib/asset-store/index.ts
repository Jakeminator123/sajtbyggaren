/**
 * AssetStore — driver-baserad abstraktion för operatör-uppladdade bilder.
 *
 * Idag används endast `LocalAssetStore` som lagrar i
 * `data/uploads/<siteId>/<assetId>/`. När vi flyttar till S3 (eller annan
 * blob-tjänst) implementeras `S3AssetStore` mot samma interface och
 * `getAssetStore()` returnerar den nya driver:n baserat på
 * `ASSET_STORE_DRIVER`-env. Inga andra filer i kodbasen ska känna till
 * skillnaden — interface är kontraktet.
 */
import { LocalAssetStore } from "./local";
import type { AssetRef, AssetRole, AssetStore } from "./types";

export type { AssetRef, AssetRole, AssetStore };
export { LocalAssetStore };

let cachedStore: AssetStore | null = null;

export function getAssetStore(): AssetStore {
  if (cachedStore) return cachedStore;
  const driver = (process.env.ASSET_STORE_DRIVER ?? "local").toLowerCase();
  if (driver === "local") {
    cachedStore = new LocalAssetStore();
    return cachedStore;
  }
  throw new Error(
    `ASSET_STORE_DRIVER=${driver} är inte implementerad ännu. ` +
      `Endast 'local' är stödd i MVP; S3AssetStore tillkommer.`,
  );
}

/** Test-only: nollställ singleton mellan tester. */
export function resetAssetStoreForTests(): void {
  cachedStore = null;
}
