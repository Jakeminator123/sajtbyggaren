/**
 * kv-store/types — leverantörsneutralt nyckel-värde-kontrakt.
 *
 * Varför detta finns (ADR: hosted-state-store): hostad Viewser behöver dela
 * tillstånd (sandbox-sessioner, bygg-pekare, run-status, rate-limit-räknare)
 * mellan serverless-instanser. Lokal Viewser ska INTE behöva någon extern
 * tjänst. Därför gäller samma adapterfilosofi som för preview-runtime
 * (local-next / vercel-sandbox / stackblitz): koden pratar bara med det här
 * kontraktet, aldrig direkt med en leverantörs-SDK. Byte av leverantör är ett
 * driver-byte, inte en omskrivning.
 */

export interface KvSetOptions {
  /** Time-to-live i sekunder. Utelämnad = ingen expiry. */
  ttlSeconds?: number;
}

export interface KvStore {
  /** Drivernamn för diagnostik/loggning (t.ex. "memory", "upstash-redis"). */
  readonly driver: string;

  /** Hämta strängvärdet för en nyckel, eller null om den saknas/expirerat. */
  get(key: string): Promise<string | null>;

  /** Sätt en nyckel till ett strängvärde, med valfri TTL. */
  set(key: string, value: string, options?: KvSetOptions): Promise<void>;

  /** Ta bort en nyckel. Idempotent — ingen effekt om nyckeln saknas. */
  delete(key: string): Promise<void>;

  /**
   * Atomisk inkrementering (skapar nyckeln som 0 först om den saknas) och
   * returnerar det nya värdet. Om ``ttlSeconds`` ges sätts expiry ENDAST när
   * nyckeln är ny (rate-limit-fönster ska inte förlängas av varje träff).
   */
  incr(key: string, options?: KvSetOptions): Promise<number>;

  /** Lista alla nycklar som börjar med ``prefix`` (diagnostik/listning). */
  listKeys(prefix: string): Promise<string[]>;
}

/** JSON-hjälpare ovanpå ``KvStore.get`` — null vid saknad eller trasig JSON. */
export async function kvGetJson<T>(
  store: KvStore,
  key: string,
): Promise<T | null> {
  const raw = await store.get(key);
  if (raw === null) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

/** JSON-hjälpare ovanpå ``KvStore.set``. */
export async function kvSetJson(
  store: KvStore,
  key: string,
  value: unknown,
  options?: KvSetOptions,
): Promise<void> {
  await store.set(key, JSON.stringify(value), options);
}
