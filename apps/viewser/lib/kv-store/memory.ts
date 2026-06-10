/**
 * kv-store/memory — in-memory-driver (default lokalt).
 *
 * Samma semantik som Redis-drivern men per process: värden överlever inte en
 * omstart och delas inte mellan instanser. Det är medvetet OK lokalt (dagens
 * beteende för sandbox-sessioner) och i tester. Hostat ska
 * ``upstash-redis``-drivern användas — index.ts auto-detekterar.
 */

import type { KvSetOptions, KvStore } from "./types";

interface MemoryEntry {
  value: string;
  /** Epoch-ms när entryt expirerar, eller null för ingen expiry. */
  expiresAtMs: number | null;
}

export class MemoryKvStore implements KvStore {
  readonly driver = "memory";

  private readonly entries = new Map<string, MemoryEntry>();

  private liveEntry(key: string): MemoryEntry | null {
    const entry = this.entries.get(key);
    if (!entry) return null;
    if (entry.expiresAtMs !== null && Date.now() >= entry.expiresAtMs) {
      this.entries.delete(key);
      return null;
    }
    return entry;
  }

  async get(key: string): Promise<string | null> {
    return this.liveEntry(key)?.value ?? null;
  }

  async set(key: string, value: string, options?: KvSetOptions): Promise<void> {
    this.entries.set(key, {
      value,
      expiresAtMs:
        options?.ttlSeconds !== undefined
          ? Date.now() + options.ttlSeconds * 1000
          : null,
    });
  }

  async delete(key: string): Promise<void> {
    this.entries.delete(key);
  }

  async incr(key: string, options?: KvSetOptions): Promise<number> {
    const entry = this.liveEntry(key);
    if (!entry) {
      await this.set(key, "1", options);
      return 1;
    }
    const next = (Number.parseInt(entry.value, 10) || 0) + 1;
    // Befintlig expiry behålls — TTL ska inte förlängas av varje träff.
    entry.value = String(next);
    return next;
  }

  async listKeys(prefix: string): Promise<string[]> {
    const keys: string[] = [];
    for (const key of this.entries.keys()) {
      if (key.startsWith(prefix) && this.liveEntry(key)) keys.push(key);
    }
    return keys;
  }
}
