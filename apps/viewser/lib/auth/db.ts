/**
 * Auth/credits-store — egen inbäddad SQLite-databas (ingen tredjepart).
 *
 * Eget kontosystem enligt beslut 2026-06-02: scrypt-hash + cookie-sessioner
 * + SQLite-store + Stripe (subscription/credits). E-post uppskjuten.
 *
 * Databasen är HELT separat från bygg-pipelinen (data/runs, build_site.py
 * m.m.) — auth rör aldrig den logiken. Filen ligger under
 * ``data/auth/auth.db`` (gitignored; innehåller lösenordshashar + PII).
 *
 * Native-modul: ``better-sqlite3`` är externaliserad i next.config.ts
 * (serverExternalPackages) och importeras BARA från Node-runtime-ytor
 * (route handlers + server components) — aldrig från middleware (edge)
 * eller klientbundlar.
 */

import { mkdirSync } from "node:fs";
import path from "node:path";

import Database from "better-sqlite3";

let db: Database.Database | null = null;

function databasePath(): string {
  const configured = process.env.VIEWSER_AUTH_DB;
  if (configured && configured.trim()) {
    return path.resolve(process.cwd(), configured);
  }
  // Repo-rot (två nivåer upp från apps/viewser) + data/auth/auth.db, samma
  // konvention som lib/runs.ts använder för data/runs.
  const root = path.resolve(process.cwd(), "..", "..");
  return path.join(root, "data", "auth", "auth.db");
}

function migrate(database: Database.Database): void {
  database.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      name TEXT,
      password_hash TEXT NOT NULL,
      stripe_customer_id TEXT,
      created_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      created_at INTEGER NOT NULL,
      expires_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

    CREATE TABLE IF NOT EXISTS subscriptions (
      user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      stripe_subscription_id TEXT,
      plan_id TEXT,
      status TEXT,
      current_period_end INTEGER,
      updated_at INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS credit_ledger (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      delta INTEGER NOT NULL,
      reason TEXT NOT NULL,
      ref TEXT,
      created_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_credit_user ON credit_ledger(user_id);

    CREATE TABLE IF NOT EXISTS owned_sites (
      site_id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      created_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_owned_user ON owned_sites(user_id);

    -- Idempotensskydd: varje Stripe-event hanteras exakt en gång så
    -- webhook-retries inte dubbel-krediterar ett konto.
    CREATE TABLE IF NOT EXISTS processed_stripe_events (
      id TEXT PRIMARY KEY,
      created_at INTEGER NOT NULL
    );
  `);
}

/**
 * Singleton-handle till auth-databasen. Skapar katalog + schema vid första
 * anropet. Synkron (better-sqlite3) — säkert i route handlers/server
 * components som ändå är async-yttre.
 */
export function getAuthDb(): Database.Database {
  if (db) return db;
  const file = databasePath();
  mkdirSync(path.dirname(file), { recursive: true });
  const database = new Database(file);
  database.pragma("journal_mode = WAL");
  database.pragma("foreign_keys = ON");
  migrate(database);
  db = database;
  return db;
}
