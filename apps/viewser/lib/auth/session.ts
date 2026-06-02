/**
 * Serverside-sessionshantering: skapar/läser/förstör httpOnly-cookie-
 * sessioner backade av sessions-tabellen i SQLite (revocerbara, till skillnad
 * från rena stateless-JWT). Node-runtime only — använder next/headers + DB.
 *
 * Middleware (edge) gör en billigare kontroll via verifySessionToken (bara
 * signatur + utgång). Den auktoritativa kontrollen — att sessionen finns och
 * inte förstörts vid utloggning — sker här i getCurrentUser().
 */

import { randomUUID } from "node:crypto";

import { cookies } from "next/headers";

import { getAuthDb } from "./db";
import {
  SESSION_COOKIE_NAME,
  signSessionToken,
  verifySessionToken,
} from "./tokens";
import { findUserById } from "./users";
import type { AuthUser } from "./types";

const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30; // 30 dagar

type SessionRow = { id: string; user_id: string; expires_at: number };

export async function createSession(userId: string): Promise<void> {
  const sid = randomUUID();
  const now = Date.now();
  const expiresAt = now + SESSION_MAX_AGE_SECONDS * 1000;
  getAuthDb()
    .prepare(
      "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
    )
    .run(sid, userId, now, expiresAt);
  const token = await signSessionToken({ sid, exp: expiresAt });
  const store = await cookies();
  store.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
}

export async function destroySession(): Promise<void> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE_NAME)?.value;
  if (token) {
    const parsed = await verifySessionToken(token);
    if (parsed) {
      getAuthDb().prepare("DELETE FROM sessions WHERE id = ?").run(parsed.sid);
    }
  }
  store.delete(SESSION_COOKIE_NAME);
}

/**
 * Den auktoritativa "vem är inloggad?"-frågan. Verifierar cookie-signatur,
 * slår upp sessionen i DB, kontrollerar utgång och returnerar användaren —
 * eller null om något inte stämmer. Tål rensning av utgångna sessioner.
 */
export async function getCurrentUser(): Promise<AuthUser | null> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE_NAME)?.value;
  const parsed = await verifySessionToken(token);
  if (!parsed) return null;
  const row = getAuthDb()
    .prepare("SELECT id, user_id, expires_at FROM sessions WHERE id = ?")
    .get(parsed.sid) as SessionRow | undefined;
  if (!row || row.expires_at < Date.now()) return null;
  return findUserById(row.user_id);
}

/** Bekvämlighet för server-komponenter som bara behöver en boolean. */
export async function hasActiveSession(): Promise<boolean> {
  return (await getCurrentUser()) !== null;
}
