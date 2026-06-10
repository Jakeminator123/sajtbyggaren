/**
 * rate-limit — fixed-window rate limiting per IP via kv-store.
 *
 * Varför detta finns: hostad Viewser är publik utan auth, så de dyra
 * endpointsen (OpenAI-anrop, sandbox-start) måste ha kostnadsskydd — en
 * oskyddad endpoint som kan trigga LLM-anrop eller sandbox-körningar är
 * exakt öppen-relä-risken som parkerade PR #156. Lokalt (memory-driver) är
 * limiten per process; hostat (Redis-driver) delas räknarna mellan
 * serverless-instanser så limiten gäller globalt.
 *
 * Strategi: fixed window via ``KvStore.incr`` — nyckeln
 * ``viewser:rate:<scope>:<ip>`` får TTL = fönsterlängden vid första träffen
 * och räknas sedan upp utan att TTL:en förlängs.
 *
 * Env-override per scope: ``VIEWSER_RATE_LIMIT_<SCOPE>`` (scope uppercase,
 * bindestreck → underscore, t.ex. ``VIEWSER_RATE_LIMIT_GENERATE_IMAGE``).
 * Ett heltal ersätter default-limiten; ``0`` stänger av limiten för det
 * scopet. Det låter operatören strama åt eller lätta på skyddet per miljö
 * utan kodändring (t.ex. högre tak bakom Deployment Protection, lägre på en
 * helt öppen preview-deploy).
 *
 * Fail-open: vid KV-fel loggas en varning och requesten släpps igenom —
 * rate limiting är ett kostnadsskydd och får inte fälla tjänsten.
 */

import { NextResponse } from "next/server";

import { getKvStore } from "./kv-store";

const RATE_KEY_PREFIX = "viewser:rate:";

/** IP ur proxy-headers: första x-forwarded-for, annars x-real-ip, annars "unknown". */
function clientIp(request: Request): string {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) {
    const first = forwardedFor.split(",")[0]?.trim();
    if (first) return first;
  }
  const realIp = request.headers.get("x-real-ip")?.trim();
  if (realIp) return realIp;
  return "unknown";
}

/** Läs env-override för ett scope, eller null om ingen giltig är satt. */
function envLimitOverride(scope: string): number | null {
  const envName = `VIEWSER_RATE_LIMIT_${scope.toUpperCase().replace(/-/g, "_")}`;
  const raw = process.env[envName]?.trim();
  if (!raw) return null;
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || String(parsed) !== raw || parsed < 0) {
    console.warn(
      `[rate-limit] ${envName}="${raw}" är inte ett giltigt heltal — ignoreras.`,
    );
    return null;
  }
  return parsed;
}

/**
 * Kontrollera (och räkna upp) rate-limiten för ``scope`` + anroparens IP.
 * Returnerar ett färdigt 429-svar när limiten är överskriden, annars ``null``
 * (= släpp igenom). Anropas direkt efter localhost-guarden i en route-handler:
 *
 *   const rateLimited = await enforceRateLimit(request, "chat", { limit: 20, windowSeconds: 60 });
 *   if (rateLimited) return rateLimited;
 */
export async function enforceRateLimit(
  request: Request,
  scope: string,
  options: { limit: number; windowSeconds: number },
): Promise<NextResponse | null> {
  const override = envLimitOverride(scope);
  const limit = override ?? options.limit;
  // 0 = avstängd limit för scopet (operatörens explicita val).
  if (limit === 0) return null;

  try {
    const ip = clientIp(request);
    const count = await getKvStore().incr(`${RATE_KEY_PREFIX}${scope}:${ip}`, {
      ttlSeconds: options.windowSeconds,
    });
    if (count > limit) {
      return NextResponse.json(
        {
          error:
            `För många anrop till ${scope} just nu — ` +
            "vänta en liten stund och försök igen.",
          code: "rate_limited",
        },
        { status: 429 },
      );
    }
    return null;
  } catch (error) {
    // Fail-open: rate limiting får inte fälla tjänsten.
    console.warn(
      `[rate-limit] KV-fel för scope ${scope} — släpper igenom requesten:`,
      error instanceof Error ? error.message : error,
    );
    return null;
  }
}
