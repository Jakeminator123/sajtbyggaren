# Hostad Viewser på Vercel — vad fungerar, vad är ärligt gatat

Den här guiden beskriver hur operatörsappen `apps/viewser` deployas på
Vercel-hosting, och — viktigast — vad som faktiskt fungerar hostat kontra vad
som är medvetet gatat. Inget här ljuger om vad som inte går hostat ännu.

Bakgrund och full roadmap finns i repo-dokumentationens migrationsplan (mappen
för migrationsplanen, G1–G8 och prompterna P0–P5). Den här deployen motsvarar en
auth-gatad skiva av P1.

## Kort sammanfattning

Den hostade vyn visar UI:t och kan — bakom plattforms-skydd och ett uttryckligt
opt-in — förhandsvisa en redan byggd sajt i en isolerad sandbox. Bygge,
följdprompt och run-historik körs fortfarande lokalt i den här versionen
(Python-kedjan och lokal disk finns inte i en hostad serverless-funktion).

## Vad som fungerar hostat

- UI:t laddar (marknadssida och studio-skal).
- `/api/discovery-options` — policy- och variantfilerna bundlas in via
  `outputFileTracingIncludes` i `next.config.ts`, så wizardens alternativ finns
  hostat. Om en fil mot förmodan saknas degraderar routen ärligt (tom lista plus
  en svensk notis) i stället för att 500:a.
- `/api/chat` och `/api/generate-image` — fungerar om `OPENAI_API_KEY` är satt.
- Gatad sandbox-preview av en redan byggd, blob-snapshottad sajt (se nedan) när
  opt-in är på och deployen är skyddad.

## Vad som är ärligt gatat hostat (och varför)

| Yta | Hostat beteende | Varför |
| --- | --- | --- |
| `/api/prompt`, `/api/build`, `/api/scrape-site` | 501 med svensk text | Ingen Python eller `.venv` hostat — bygg-orkestreringen är lokal |
| `/api/preview/[siteId]` POST | 501 om inte opt-in | En publik, oautentiserad endpoint som kan starta sandboxar är just den öppna relä-risken som parkerade PR #156 |
| `/api/runs` plus run-detaljer | tom lista / 404 plus notis | Ingen beständig repo-disk hostat (`data/runs/` finns inte) |
| App-auth och tenant-isolering | byggs inte | Auth/billing är parkerat (ADR 0035) — gatas hostat i stället |

## Env-variabler (sätts i Vercel-projektet — committa ALDRIG värden)

Alla värden sätts i Vercel-projektets inställningar. `.env*`-filer är gitignorerade
och får aldrig committas (utom `apps/viewser/.env.example`, som bara är en mall).

| Variabel | Syfte |
| --- | --- |
| `VERCEL=1` | Sätts automatiskt hostat — detekteras av `isHostedVercelRuntime()` |
| `VERCEL_OIDC_TOKEN` | Injiceras nativt i Vercel-funktioner; sandbox-runnern autentiserar med den (ingen lokal `vercel env pull`-dans hostat) |
| `VIEWSER_PREVIEW_MODE` | Sätt till sandbox-läget för hostad förhandsvisning (exakt token finns dokumenterad i `apps/viewser/.env.example`) |
| `NEXT_PUBLIC_VIEWSER_PREVIEW_MODE` | Klient-spegel av samma läge (samma värde) |
| `VIEWSER_ALLOWED_HOSTS` | Den hostade domänen, så `assertLocalhost` släpper in operatören på rätt host |
| `VIEWSER_ENABLE_HOSTED_SANDBOX` | Sätt `1` för att aktivera den gatade hostade sandbox-previewen (default av) |
| `OPENAI_API_KEY` | Server-side OpenAI-anrop |
| `BLOB_READ_WRITE_TOKEN` / `BLOB_STORE_ID` | Artefaktkälla för hostad sandbox-preview (snapshot av generated-files) |

## Hård förutsättning innan sandbox-endpointen aktiveras

Innan `VIEWSER_ENABLE_HOSTED_SANDBOX=1` sätts MÅSTE deployen skyddas på
plattformsnivå med Vercel-deployment-protection (standard-skydd eller lösenord).
Då är preview-start-POST:en aldrig publikt nåbar utan plattforms-auth, och vi
bygger ingen egen auth-kod (ADR 0035). Utan det skyddet ska opt-in-flaggan vara
av — annars vore det en öppen relä för kostsam sandbox-körning (#156).

## Kallstart och kostnad (ärlig caveat)

- Kallstart är ~28 s eller mer: sandboxen kör `npm install` plus `next build`
  plus `next start` innan den publika URL:en svarar.
- Preview-routen sätter `maxDuration = 300` (kräver Pro-plan). Hobby-planen är
  hårt kapad till 60 s, vilket inte räcker för en kall sandbox-build.
- Varje sandbox kostar per körning (CPU plus nätverk). En TTL plus
  `stop()`/`delete()` städar; sessionsregistret är i minnet och överlever inte en
  serverless-kallstart (TTL städar ändå) — ett durabelt register är ett senare
  steg.

## Artefaktkälla hostat (FAS 2B)

Det finns ingen lokal disk hostat, så sandbox-runnern kan inte läsa
generated-files från `../sajtbyggaren-output/.generated/`. En redan byggd sajt
görs förhandsvisbar hostat genom att snapshotta dess generated-files till
blob-lagring lokalt med en icke-publik operatör-CLI:

```bash
# Körs LOKALT av operatören (ingen publik upload-endpoint — #156):
node apps/viewser/scripts/snapshot-site-to-blob.mjs <siteId>
```

Den hostade sandbox-runnern läser sedan filerna från blob i stället för disk.

## Nästa arkitektursteg (separat beslut)

- Automatisk bygg-output till blob och en extern build-backend (migrationsplanens
  P2) så bygge kan ske utan lokal Python.
- Durabelt sessionsregister plus sandbox-snapshots för snabb uppstart (P3).
- App-auth och tenant-isolering (P4 / ADR 0035).
