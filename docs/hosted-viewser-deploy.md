# Hostad Viewser på Vercel — vad fungerar, vad är ärligt gatat

Den här guiden beskriver hur operatörsappen `apps/viewser` deployas på
Vercel-hosting, och — viktigast — vad som faktiskt fungerar hostat kontra vad
som är medvetet gatat. Inget här ljuger om vad som inte går hostat ännu.

Bakgrund och full roadmap finns i repo-dokumentationens migrationsplan (mappen
för migrationsplanen, G1–G8 och prompterna P0–P5). Drift-fusklappen (env-kedja,
redis-nycklar, felsökning) finns i `docs/operations/hosted-viewser-manual.md` —
läs den vid drift, den här guiden vid arkitektur-/deployfrågor.

## Läget (uppdaterat 2026-06-12)

Den hostade deployen är en **publik v1** efter operatörens spärr-hävning
2026-06-11: hostat bygge är PÅ (`VIEWSER_ENABLE_HOSTED_BUILD=1` +
`VIEWSER_ALLOW_NON_LOCALHOST=true` i alla Vercel-miljöer, konsoliderat via
env-städningen + PR #286). Skyddet i drift är per-ip-rate-limit (ADR 0050) +
sandbox-TTL — ingen app-auth (parkerad, ADR 0035). Den tidigare beskrivningen
av en "auth-gatad P1-skiva" där bygge bara kördes lokalt gäller inte längre.

## Vad som fungerar hostat

- **Hostat bygge av användarsajter** (P2, ADR 0048): `/api/prompt` kör
  Python-pipen i en Vercel Sandbox, publicerar builden fil-för-fil till blob
  under `generated/<siteId>/` och sätter pekaren i kv-store (ADR 0049).
  - Status pollas via `GET /api/hosted-build/<runId>?siteId=<siteId>` —
    routen är site-bunden (B196-härdningen): utan rätt `siteId` svarar den
    404 med samma text som när nyckeln saknas, så den aldrig läcker status
    för gissade runId:n.
  - Båda svarslägena på `/api/prompt` väntar in resultatet: NDJSON-streamen
    (`Accept: application/x-ndjson`) emitterar accepted/building/done|error,
    och den synkrona JSON-vägen pollar samma KV-status server-side tills
    done/failed (review-fynd #284: det tidigare omedelbara 202-svaret
    tolkades av icke-streamande klienter som ett färdigt bygge).
  - Serveringen är manifest-baserad (B195, PR #287): bygget publicerar sist
    `generated/<siteId>/.manifest.json` och previewen visar bara
    manifest-listade filer, så stale blobbar från ett tidigare bygge mot
    samma `siteId` aldrig syns.
  - Hårda krav hostat: blob-token, kv-store-env och en uppladdad
    build-kontext (se env-tabellen). Kv-store-kravet preflightas numera i
    `startHostedBuild` FÖRE `Sandbox.create` — saknas Upstash-env failar
    bygget direkt med tydlig svensk text i stället för att hänga i
    status-pollningen till timeout.
- UI:t laddar (marknadssida och studio-skal).
- `/api/discovery-options` — policy- och variantfilerna bundlas in via
  `outputFileTracingIncludes` i `next.config.ts`, så wizardens alternativ finns
  hostat. Om en fil mot förmodan saknas degraderar routen ärligt (tom lista plus
  en svensk notis) i stället för att 500:a.
- `/api/chat` och `/api/generate-image` — fungerar om `OPENAI_API_KEY` är satt.
- Sandbox-preview av en redan byggd sajt (blob-källan ovan) bakom
  `VIEWSER_ENABLE_HOSTED_SANDBOX=1`.

## Kvarvarande begränsningar hostat (ärliga, trackade)

Hostade följdpromptar FUNGERAR sedan 2026-06-11/12 (B194 stängd via #307 +
B199 v2): run-artefakterna tarballas till blob efter varje lyckat bygge,
hydreras i sandboxen före apply, och run-historiken/inspektorn läses ur
KV-index + blob via `/api/runs?siteId=`. Det som återstår:

| Begränsning | Tracking | Innebörd |
| --- | --- | --- |
| Discovery-paritet | B197 (P3) | den hostade vägen skickar bara prompt-texten in i sandboxen — wizardens strukturerade `discovery`-block når inte `prompt_to_project_input.py` hostat (lokalt gör det det) |
| `changeSet` hostat | — | hostade followup-svar bär `changeSet: null` (lokalt beräknas diffen); filträdet per run (StackBlitz-fallbacken) serveras inte heller hostat |
| App-auth och tenant-isolering | ADR 0035 (parkerad) | publik v1 skyddas av rate-limit per IP, inte auth |

## Vad som är ärligt gatat hostat (och varför)

| Yta | Hostat beteende | Varför |
| --- | --- | --- |
| `/api/prompt` | Hostat bygge i sandbox när `VIEWSER_ENABLE_HOSTED_BUILD=1` (PÅ i drift); utan flaggan 501 | P2/ADR 0048 — utan flaggan (eller utan blob/kv-env) degraderar routen ärligt |
| `/api/build`, `/api/scrape-site` | 501 med svensk text | Ingen Python eller `.venv` hostat — dessa är fortsatt lokala |
| `/api/preview/[siteId]` POST | sandbox-preview när `VIEWSER_ENABLE_HOSTED_SANDBOX=1` (PÅ i drift); annars 501 | Kostsam sandbox-spawn — opt-in, kvoterad av rate-limit (ADR 0050) |
| `/api/runs` plus run-detaljer | listas/serveras ur KV-index + blob-tarball (B199 v2) — kräver `siteId` som capability-nyckel, utan den listas inget | Ingen beständig repo-disk hostat; artefakterna persisteras i stället till blob per lyckat bygge |
| App-auth och tenant-isolering | byggs inte | Auth/billing är parkerat (ADR 0035) — publik v1 skyddas av rate-limit i stället |

## Env-variabler (sätts i Vercel-projektet — committa ALDRIG värden)

Alla värden sätts i Vercel-projektets inställningar. `.env*`-filer är gitignorerade
och får aldrig committas (utom `apps/viewser/.env.example`, som bara är en mall).
Den konsoliderade faktiska listan per 2026-06-11 finns i
`docs/operations/hosted-viewser-manual.md` avsnitt 2.

| Variabel | Syfte |
| --- | --- |
| `VERCEL=1` | Sätts automatiskt hostat — detekteras av `isHostedVercelRuntime()` och gate:ar bl.a. kv-preflighten |
| `VERCEL_OIDC_TOKEN` | Sätts ALDRIG som statisk env-var hostat (en statisk token dör efter ~12 h och skuggar den färska). Plattformen levererar tokenen per request via request-kontexten; `resolveCredentials` adopterar den automatiskt |
| `VIEWSER_PREVIEW_MODE` | Sätt till sandbox-läget för hostad förhandsvisning (exakt token finns dokumenterad i `apps/viewser/.env.example`) |
| `NEXT_PUBLIC_VIEWSER_PREVIEW_MODE` | Klient-spegel av samma läge (samma värde) |
| `VIEWSER_ALLOW_NON_LOCALHOST` | `true` i drift — kortsluter `assertLocalhost`-hostlistan (då behövs inte `VIEWSER_ALLOWED_HOSTS`) |
| `VIEWSER_ENABLE_HOSTED_SANDBOX` | `1` i drift — aktiverar den hostade sandbox-previewen |
| `VIEWSER_ENABLE_HOSTED_BUILD` | `1` i drift — aktiverar hostat bygge i sandbox (P2, ADR 0048) |
| `VIEWSER_BUILD_CONTEXT_URL` | Fallback för build-kontext-URL:en om KV-nyckeln `viewser:build-context:url` saknas |
| `OPENAI_API_KEY` | Server-side OpenAI-anrop (utan den kör pipen ärlig mock-fallback) |
| `BLOB_READ_WRITE_TOKEN` / `BLOB_STORE_ID` | Artefaktkälla för hostad preview och hostad bygg-output (injiceras av blob-integrationen) |
| `KV_REST_API_URL` / `KV_REST_API_TOKEN` | Injiceras av Upstash-marketplace-integrationen; kv-store-adaptern (ADR 0049) auto-detekterar. HÅRT krav hostat — `startHostedBuild` preflight-failar utan dem |
| `VIEWSER_RATE_LIMIT_<SCOPE>` | Override av per-ip-kvoterna (ADR 0050); 0 stänger av ett scope |

Build-kontexten (Python-pipen som sandboxen kör) laddas upp av operatören
lokalt. Efter merge av Python/generation/OpenClaw-ändringar i `scripts/`,
`packages/`, `governance/`, `data/starters/`, `requirements.txt` eller
`pyproject.toml`:

```bash
cd apps/viewser
npm run build-context:check
npm run build-context:upload
```

Check-kommandot jämför `viewser:build-context:sha` i KV med aktuell
git-commit för samma ytor som tarballen innehåller. Upload-kommandot sparar
både URL, SHA och dirty-flagga i KV. Det finns ingen auto-publish.

## Skyddsmodellen i publik drift (ADR 0050)

Publik åtkomst utan auth skyddas av per-ip-rate-limit på de dyra endpointsen
(prompt-bygget är striktast: 3 anrop per 300 s) plus sandbox-TTL (15 min för
byggen) så ett hängt bygge aldrig läcker kostnad. Klient-IP läses spoofsäkert
(fixat före #284-mergen). Status-routen är site-bunden (B196) så den inte är
en enumererings-yta. Deployment-protection är INTE längre en förutsättning —
operatörsbeslutet 2026-06-11 är publik drift med dessa skydd (se
`docs/known-issues.md`, sektionen om publik-deploy-uppföljningar).

## Kallstart och kostnad (ärlig caveat)

- Kallstart för preview: sedan pre-built-passet (2026-06-12) laddar hostade
  byggen upp byggets `.next/` (minus cache/trace) till blob, så
  preview-sandboxen kör bara `npm install --omit=dev` plus `next start` —
  inget eget `next build`. Saknas en komplett `.next` i blob (bygge före
  passet) tar previewen ärligt fulla vägen (`npm install` + `next build` +
  `next start`, ~28 s eller mer, ofta minuter).
- Ett hostat BYGGE tar typiskt flera minuter (pip + npm install + next build).
  `/api/prompt` har `maxDuration = 300` (kräver Pro-plan); tar bygget längre
  än svarsbudgeten (~280 s) avslutas svaret ärligt med en hänvisning till
  status-routen — bygget i sandboxen fortsätter och pekaren sätts när det
  blir klart.
- Varje sandbox kostar per körning (CPU plus nätverk). En TTL plus
  `stop()`/`delete()` städar; sessionsregistret är i minnet och överlever inte en
  serverless-kallstart (TTL städar ändå) — ett durabelt register är ett senare
  steg.

## Artefaktkälla hostat

Hostade byggen publicerar sin output direkt till blob (`generated/<siteId>/`
plus `.manifest.json`, se ovan) — ingen manuell snapshot behövs för sajter som
byggts hostat. En LOKALT byggd sajt görs förhandsvisbar hostat genom att
snapshotta dess generated-files till blob med en icke-publik operatör-CLI:

```bash
# Körs LOKALT av operatören (ingen publik upload-endpoint — #156):
node apps/viewser/scripts/snapshot-site-to-blob.mjs <siteId>
```

Den hostade sandbox-runnern läser sedan filerna från blob i stället för disk.

## Nästa arkitektursteg (separat beslut)

- Discovery-payloaden når sandboxen (B197, Christophers spår).
- `changeSet` beräknat hostat + filträd per run.
- App-auth och tenant-isolering (P4 / ADR 0035).
