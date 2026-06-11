/**
 * kv-store/upstash-redis — Redis-driver via Upstash REST-API.
 *
 * Medvetet ingen SDK-dependency (`@upstash/redis`): REST-ytan är trivial och
 * att hålla sig till rena Redis-kommandon över fetch gör drivern lätt att
 * porta till valfri annan Redis (eller helt annan KV) — leverantören är en
 * adapter, inte ett ägarskap (jfr ADR 0030 för preview-runtime).
 *
 * Env (Upstash-integrationen i Vercel Marketplace injicerar KV_*-namnen):
 *   VIEWSER_KV_REST_URL  || KV_REST_API_URL  || UPSTASH_REDIS_REST_URL
 *   VIEWSER_KV_REST_TOKEN|| KV_REST_API_TOKEN|| UPSTASH_REDIS_REST_TOKEN
 */

import type { KvSetOptions, KvStore } from "./types";

function firstEnv(...names: string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name]?.trim();
    if (value) return value;
  }
  return undefined;
}

export function upstashRestUrl(): string | undefined {
  return firstEnv(
    "VIEWSER_KV_REST_URL",
    "KV_REST_API_URL",
    "UPSTASH_REDIS_REST_URL",
  );
}

export function upstashRestToken(): string | undefined {
  return firstEnv(
    "VIEWSER_KV_REST_TOKEN",
    "KV_REST_API_TOKEN",
    "UPSTASH_REDIS_REST_TOKEN",
  );
}

interface KvRestResponse {
  result?: unknown;
  error?: string;
}

export class UpstashRedisKvStore implements KvStore {
  readonly driver = "upstash-redis";

  constructor(
    private readonly url: string,
    private readonly token: string,
  ) {}

  /** Kör ett rått Redis-kommandon, t.ex. ["SET", "k", "v", "EX", "60"]. */
  private async command(parts: (string | number)[]): Promise<unknown> {
    const response = await fetch(this.url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(parts.map(String)),
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(
        `kv-store(upstash-redis): HTTP ${response.status} för ${parts[0]}`,
      );
    }
    const payload = (await response.json()) as KvRestResponse;
    if (payload.error) {
      throw new Error(`kv-store(upstash-redis): ${payload.error}`);
    }
    return payload.result;
  }

  async get(key: string): Promise<string | null> {
    const result = await this.command(["GET", key]);
    return result === null || result === undefined ? null : String(result);
  }

  async set(key: string, value: string, options?: KvSetOptions): Promise<void> {
    const parts: (string | number)[] = ["SET", key, value];
    if (options?.ttlSeconds !== undefined) {
      parts.push("EX", options.ttlSeconds);
    }
    await this.command(parts);
  }

  async delete(key: string): Promise<void> {
    await this.command(["DEL", key]);
  }

  async incr(key: string, options?: KvSetOptions): Promise<number> {
    const next = Number(await this.command(["INCR", key]));
    if (options?.ttlSeconds !== undefined) {
      // ``EXPIRE ... NX`` sätter TTL endast när nyckeln saknar en — så
      // fönstret rullar aldrig framåt (sätts en gång på första träffen),
      // men en TTL som tappats (t.ex. INCR lyckades men en tidigare EXPIRE
      // föll på nätfel) läks vid nästa anrop i stället för att nyckeln blir
      // TTL-lös och rate-limitar IP:n permanent. Idempotent och billigt.
      await this.command(["EXPIRE", key, options.ttlSeconds, "NX"]);
    }
    return next;
  }

  async listKeys(prefix: string): Promise<string[]> {
    const keys: string[] = [];
    let cursor = "0";
    // SCAN i stället för KEYS — blockerar inte storen vid många nycklar.
    do {
      const result = (await this.command([
        "SCAN",
        cursor,
        "MATCH",
        `${prefix}*`,
        "COUNT",
        200,
      ])) as [string, string[]];
      cursor = result[0];
      keys.push(...result[1]);
    } while (cursor !== "0");
    return keys;
  }
}
