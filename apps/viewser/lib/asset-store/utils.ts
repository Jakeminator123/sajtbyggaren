/**
 * Hjälpfunktioner för asset-store. AssetId genereras med ULID-style
 * (kollisionssäker, tidssorterbar) men utan extern lib — vi kör
 * crypto.randomUUID prefixat med tid så vi slipper en deplib.
 */
import { randomUUID } from "node:crypto";

const BASE32_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // Crockford

function toBase32(value: number, length: number): string {
  let n = Math.max(0, Math.floor(value));
  const out: string[] = [];
  for (let i = 0; i < length; i += 1) {
    out.unshift(BASE32_ALPHABET[n % 32] ?? "0");
    n = Math.floor(n / 32);
  }
  return out.join("");
}

/**
 * Tidssorterbar identifierare (10 char timestamp i Crockford-base32 +
 * 16 hex-tecken från randomUUID). Inte exakt ULID men tjänar samma
 * syfte: assetId:n från samma session sorteras kronologiskt och
 * kollision är effektivt omöjlig.
 */
export function generateAssetId(): string {
  const ts = toBase32(Date.now(), 10);
  const rand = randomUUID().replace(/-/g, "").slice(0, 16).toUpperCase();
  return `${ts}${rand}`;
}

/**
 * Gör om ett operatör-uppladdat filnamn till ett URL-säkert stem
 * (lower-case, ASCII-folded, kort). Behåller inte extension — den
 * sätts från MIME efter sharp-pipelinen.
 */
export function slugifyFilename(originalName: string): string {
  const withoutExt = originalName.replace(/\.[^./\\]+$/, "");
  const ascii = withoutExt
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const trimmed = ascii.slice(0, 48);
  return trimmed.length > 0 ? trimmed : "asset";
}
