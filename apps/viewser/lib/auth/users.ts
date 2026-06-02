/**
 * Användar-CRUD mot SQLite-storen. Node-runtime only (importerar password.ts
 * som använder node:crypto). Aldrig från edge/klient.
 */

import { randomUUID } from "node:crypto";

import { getAuthDb } from "./db";
import { hashPassword, verifyPassword } from "./password";
import type { AuthUser } from "./types";

type UserRow = {
  id: string;
  email: string;
  name: string | null;
  password_hash: string;
  stripe_customer_id: string | null;
  created_at: number;
};

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

function mapRow(row: UserRow): AuthUser {
  return {
    id: row.id,
    email: row.email,
    name: row.name,
    stripeCustomerId: row.stripe_customer_id,
    createdAt: row.created_at,
  };
}

export function emailExists(email: string): boolean {
  const row = getAuthDb()
    .prepare("SELECT 1 FROM users WHERE email = ?")
    .get(normalizeEmail(email));
  return Boolean(row);
}

export function findUserById(id: string): AuthUser | null {
  const row = getAuthDb()
    .prepare(
      "SELECT id, email, name, password_hash, stripe_customer_id, created_at FROM users WHERE id = ?",
    )
    .get(id) as UserRow | undefined;
  return row ? mapRow(row) : null;
}

export function createUser(
  email: string,
  password: string,
  name?: string | null,
): AuthUser {
  const id = randomUUID();
  const now = Date.now();
  getAuthDb()
    .prepare(
      "INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
    )
    .run(id, normalizeEmail(email), name?.trim() || null, hashPassword(password), now);
  return { id, email: normalizeEmail(email), name: name?.trim() || null, stripeCustomerId: null, createdAt: now };
}

/** Returnerar användaren om e-post + lösenord stämmer, annars null. */
export function verifyCredentials(email: string, password: string): AuthUser | null {
  const row = getAuthDb()
    .prepare(
      "SELECT id, email, name, password_hash, stripe_customer_id, created_at FROM users WHERE email = ?",
    )
    .get(normalizeEmail(email)) as UserRow | undefined;
  if (!row) return null;
  if (!verifyPassword(password, row.password_hash)) return null;
  return mapRow(row);
}

export function setStripeCustomerId(userId: string, customerId: string): void {
  getAuthDb()
    .prepare("UPDATE users SET stripe_customer_id = ? WHERE id = ?")
    .run(customerId, userId);
}

export function findUserByStripeCustomerId(customerId: string): AuthUser | null {
  const row = getAuthDb()
    .prepare(
      "SELECT id, email, name, password_hash, stripe_customer_id, created_at FROM users WHERE stripe_customer_id = ?",
    )
    .get(customerId) as UserRow | undefined;
  return row ? mapRow(row) : null;
}
