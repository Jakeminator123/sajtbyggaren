# ADR 0049 — Leverantörsneutral kv-store-adapter (memory lokalt, upstash-redis hostat)

**Status:** Accepted
**Datum:** 2026-06-10 (operatörsbeslut, Jakob)
**Beroenden:** ADR 0030 (preview-provider-portability — samma adapterfilosofi),
ADR 0048 (hostad byggväg). Stänger G3 och pekardelen av G2 i
[`docs/vercel-sandbox-migration/01-arkitekturval.md`](../../docs/vercel-sandbox-migration/01-arkitekturval.md).
Referens: [`apps/viewser/lib/kv-store/`](../../apps/viewser/lib/kv-store/).

## Kontext

Hostad viewser behöver delat, durabelt tillstånd mellan serverless-instanser:
sandbox-sessioner (idag in-memory, tappas per instans), bygg-pekare
("hostad current.json"), run-status för pollning och rate-limit-räknare.
Operatörskravet är uttryckligt: ingen leverantörslåsning — det ska gå att byta
lagring lika smidigt som preview-runtime byts (local-next / vercel-sandbox /
stackblitz).

## Alternativ

- Direkt SDK-beroende på en leverantör (`@upstash/redis`, `@vercel/kv`).
- Marketplace-postgres (neon) eller supabase som första store.
- Egen adapter med utbytbara drivers, rena redis-kommandon över rest.

## Beslut

Egen adapter: `apps/viewser/lib/kv-store/` med kontraktet `KvStore`
(`get/set/delete/incr/listKeys`, ttl-stöd) och två drivers:

- `memory` — default lokalt och i tester; exakt dagens beteende, ingen extern
  tjänst krävs för lokal utveckling.
- `upstash-redis` — rest-anrop via fetch (ingen sdk-dependency); env-kedjan
  `VIEWSER_KV_REST_URL/TOKEN` -> `KV_REST_API_URL/TOKEN` ->
  `UPSTASH_REDIS_REST_URL/TOKEN` (marketplace-integrationens namn).

Driver väljs via `VIEWSER_KV_DRIVER` eller auto-detekteras (redis-env
närvarande -> redis, annars memory). All kod pratar bara med kontraktet;
upstash provisioneras via vercel-marketplace men är ett driver-byte bort.
Postgres/supabase avvisas inte — de är fel verktyg för pekare/sessioner/
räknare idag och kan läggas till som driver eller separat databas när
relationsdata (användare, delning) faktiskt behövs.

## Konsekvenser

- Plus: noll nya npm-dependencies; lokal utveckling kravlös; byte av
  kv-leverantör = en ny driverfil; sessioner överlever instansbyten hostat.
- Minus: fixed-window-räknare och scan-listning är medvetet enkla; en
  fullfjädrad databas för run-historik (P3) är ett separat beslut.
