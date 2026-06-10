/**
 * kv-store — driver-val, samma mönster som ``asset-store/index.ts``.
 *
 * Val (i ordning):
 *   1. ``VIEWSER_KV_DRIVER=memory|upstash-redis`` — explicit override.
 *   2. Auto: Upstash-env närvarande -> "upstash-redis", annars "memory".
 *
 * Lokal utveckling kräver alltså ingenting: utan Redis-env blir det
 * in-memory precis som idag. Hostat injicerar Marketplace-integrationen
 * KV_REST_API_URL/KV_REST_API_TOKEN och drivern väljs automatiskt.
 */

import { MemoryKvStore } from "./memory";
import type { KvStore } from "./types";
import {
  UpstashRedisKvStore,
  upstashRestToken,
  upstashRestUrl,
} from "./upstash-redis";

export type { KvSetOptions, KvStore } from "./types";
export { kvGetJson, kvSetJson } from "./types";

let cachedStore: KvStore | null = null;

export function getKvStore(): KvStore {
  if (cachedStore) return cachedStore;

  const explicit = process.env.VIEWSER_KV_DRIVER?.trim().toLowerCase();
  const url = upstashRestUrl();
  const token = upstashRestToken();

  if (explicit === "memory") {
    cachedStore = new MemoryKvStore();
    return cachedStore;
  }
  if (explicit === "upstash-redis") {
    if (!url || !token) {
      throw new Error(
        "VIEWSER_KV_DRIVER=upstash-redis kräver KV_REST_API_URL och " +
          "KV_REST_API_TOKEN (eller UPSTASH_REDIS_REST_*-motsvarigheterna).",
      );
    }
    cachedStore = new UpstashRedisKvStore(url, token);
    return cachedStore;
  }
  if (explicit && explicit !== "") {
    throw new Error(
      `VIEWSER_KV_DRIVER=${explicit} är inte implementerad. ` +
        `Tillåtna värden: "memory", "upstash-redis".`,
    );
  }

  cachedStore =
    url && token ? new UpstashRedisKvStore(url, token) : new MemoryKvStore();
  return cachedStore;
}

/** Endast för tester — nollställ driver-cachen. */
export function resetKvStoreForTests(): void {
  cachedStore = null;
}
