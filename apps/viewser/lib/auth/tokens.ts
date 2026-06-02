/**
 * Signerade session-tokens med HMAC-SHA256 via Web Crypto
 * (``globalThis.crypto.subtle``) — fungerar i BÅDE Node-runtime (route
 * handlers) och edge-runtime (middleware), så samma kod kan signera och
 * verifiera oavsett yta. Ingen tredjeparts-dependency.
 *
 * Token-form: ``<base64url(payload)>.<base64url(hmac)>`` där payload är
 * ``{ sid, exp }`` (session-id + utgångstid i ms). Cookien bär bara detta;
 * den fulla session-/användarslagningen sker mot SQLite i server-yta. I
 * middleware verifieras enbart signatur + utgång (billig gate, ingen DB).
 */

const encoder = new TextEncoder();
const decoder = new TextDecoder();

const DEV_FALLBACK_SECRET = "dev-insecure-auth-secret-change-me";

function getSecret(): string {
  const secret = process.env.AUTH_SECRET;
  if (secret && secret.trim().length > 0) return secret;
  // I produktion ska AUTH_SECRET ALLTID finnas — annars är sessions-cookies
  // signerade med en publik fallback-nyckel och därmed förfalskningsbara.
  // Vägra hellre starta än att tyst köra osäkert.
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "AUTH_SECRET måste sättas i produktion — vägrar använda dev-fallback-nyckeln.",
    );
  }
  // Dev faller tillbaka på en fast nyckel så lokal utveckling funkar utan
  // setup (sessioner blir då inte hemliga men det är OK på en dev-maskin).
  return DEV_FALLBACK_SECRET;
}

export type SessionTokenPayload = {
  /** Session-id (UUID) som slås upp mot sessions-tabellen. */
  sid: string;
  /** Utgångstid i epoch-ms. */
  exp: number;
};

function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function stringToBase64Url(value: string): string {
  return bytesToBase64Url(encoder.encode(value));
}

function base64UrlToString(value: string): string {
  const padded =
    value.length % 4 === 0 ? value : value + "=".repeat(4 - (value.length % 4));
  const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return decoder.decode(bytes);
}

async function hmacBase64Url(data: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(getSecret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(data));
  return bytesToBase64Url(new Uint8Array(signature));
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export async function signSessionToken(
  payload: SessionTokenPayload,
): Promise<string> {
  const encoded = stringToBase64Url(JSON.stringify(payload));
  const signature = await hmacBase64Url(encoded);
  return `${encoded}.${signature}`;
}

/**
 * Verifiera signatur + utgång. Returnerar payloaden om giltig, annars null.
 * Gör INGEN DB-slagning — det är upp till anroparen (server-yta) att
 * bekräfta att sessionen fortfarande finns.
 */
export async function verifySessionToken(
  token: string | undefined | null,
): Promise<SessionTokenPayload | null> {
  if (!token) return null;
  const dot = token.indexOf(".");
  if (dot <= 0) return null;
  const encoded = token.slice(0, dot);
  const signature = token.slice(dot + 1);
  const expected = await hmacBase64Url(encoded);
  if (!constantTimeEqual(signature, expected)) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(base64UrlToString(encoded));
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object") return null;
  const candidate = parsed as Record<string, unknown>;
  if (typeof candidate.sid !== "string" || typeof candidate.exp !== "number") {
    return null;
  }
  if (Date.now() > candidate.exp) return null;
  return { sid: candidate.sid, exp: candidate.exp };
}

export const SESSION_COOKIE_NAME = "sb_session";
