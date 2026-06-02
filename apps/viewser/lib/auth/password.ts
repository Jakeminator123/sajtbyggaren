/**
 * Lösenordshashning med Node:s inbyggda ``scrypt`` — ingen tredjeparts-
 * dependency (inget bcrypt/argon2). scrypt är minnes-hård och rekommenderad
 * av OWASP för lösenordslagring.
 *
 * Lagringsformat: ``scrypt$<salt-hex>$<derived-hex>``. Salt är 16 random
 * bytes per användare; jämförelsen är konstant-tid (timingSafeEqual) för att
 * inte läcka via timing.
 *
 * Endast Node-runtime (route handlers) — aldrig edge/klient.
 */

import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

const KEY_LENGTH = 64;

export function hashPassword(password: string): string {
  const salt = randomBytes(16);
  const derived = scryptSync(password, salt, KEY_LENGTH);
  return `scrypt$${salt.toString("hex")}$${derived.toString("hex")}`;
}

export function verifyPassword(password: string, stored: string): boolean {
  const parts = stored.split("$");
  if (parts.length !== 3 || parts[0] !== "scrypt") return false;
  const salt = Buffer.from(parts[1], "hex");
  const expected = Buffer.from(parts[2], "hex");
  if (salt.length === 0 || expected.length === 0) return false;
  const derived = scryptSync(password, salt, expected.length);
  return derived.length === expected.length && timingSafeEqual(derived, expected);
}
