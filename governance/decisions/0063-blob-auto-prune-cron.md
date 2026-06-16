# ADR 0063 — Auto-prune av hostad blob via daglig Vercel Cron

**Status:** Accepted
**Datum:** 2026-06-16
**Beroenden:** ADR 0049 (kv-store), ADR 0050 (publik hostad viewser, rate-limit
i stället för auth — samma öppen-relä-lärdom som #156), ADR 0048 (hostad
byggväg som fyller blob-storen).
Referens:
[`apps/viewser/lib/blob-prune.mjs`](../../apps/viewser/lib/blob-prune.mjs),
[`apps/viewser/app/api/cron/prune-blob/route.ts`](../../apps/viewser/app/api/cron/prune-blob/route.ts),
[`apps/viewser/scripts/blob-admin.mjs`](../../apps/viewser/scripts/blob-admin.mjs).

## Kontext

Den hostade blob-storen (`sajtbyggaren-viewser-blob`) växer obegränsat. Varje
hostat bygge skriver fil-för-fil till de sajt-scopade prefixen
`generated/<siteId>/`, `run-artifacts/<siteId>/`, `run-state/<siteId>/` och
`preview-bundles/<siteId>/`, men ingenting städar upp gamla sajter. Sandboxar
auto-termineras via TTL; blob gör det inte. `generated/` har redan ~5900
objekt. Det femte topp-prefixet, `build-context/`, är Python-motorns tarball
(EN fil, inte en sajt) och får aldrig röras.

Det fanns redan ett operatör-CLI (`apps/viewser/scripts/blob-admin.mjs`) med
`audit` / `list-sites` / `delete-site <siteId>`, men ingen automatisk
rensning (`vercel.json` saknade `crons`). Manuell radering skalar inte.

## Beslut

En daglig Vercel Cron prunar gammal sajt-data:

- **Delad kärna:** all listnings-/raderings-/staleness-logik bor i
  `apps/viewser/lib/blob-prune.mjs`. Både CLI:t och cron-routen importerar den
  — ingen duplicering av raderingslogiken.
- **Cron:** `vercel.json` registrerar
  `{ path: "/api/cron/prune-blob", schedule: "0 4 * * *" }` (04:00 UTC, en
  gång/dygn — Hobby-planens gräns, endast production).
- **Auktorisering:** routen kräver `Authorization: Bearer <CRON_SECRET>`.
  Vercel skickar headern automatiskt på cron-anrop när env är satt. Saknad
  eller felaktig secret ger 401 (deny-by-default) — routen får aldrig vara en
  oskyddad delete-relä. Cronen är inaktiv tills `CRON_SECRET` sätts.
- **Retention:** sajt-data äldre än `RETENTION_DAYS` (default 14) prunas.
  Färskheten per sajt = max(senaste blob-`uploadedAt`,
  `viewser:site:<siteId>:current`.updatedAt). Den senaste versionen behålls
  alltid om den inte själv är äldre än retention; sajter med okänd ålder
  behålls.
- **Skydd:** `build-context/` kan aldrig raderas — en explicit grind
  (`assertSafeSiteId` + mål-kontroll i `deleteSite`) plus ett test låser det.
- **Torrkörning:** `?dryRun=1` (route) och dry-run-default (CLI `prune`)
  listar vad som skulle raderas utan att radera.
- **Av/på utan redeploy:** `PRUNE_ENABLED=0` (eller `false`/`off`) pausar
  raderingen; cronen loggar då en no-op. Default är på.
- **Observability:** varje körning loggar en strukturerad rad
  (`event: "blob-prune"`, prunedSites, freedBytes, kept).

Backoffice får en vy under Underhåll (`Vercel - blob auto-prune`) som kör
samma logik manuellt mot samma delade store.

## Nya env-variabler (runtime-kontrakt)

| Variabel | Default | Roll |
| --- | --- | --- |
| `CRON_SECRET` | (osatt) | Bearer-secret som gatear routen; obligatorisk för att aktivera cronen. |
| `RETENTION_DAYS` | 14 | Ålder (dygn) då sajt-data prunas. |
| `PRUNE_ENABLED` | på | `0`/`false`/`off` pausar raderingen utan redeploy. |

Dokumenterade i `apps/viewser/.env.example` och
`docs/operations/hosted-viewser-manual.md` (avsnitt 10). Inga riktiga värden
committas.

## Konsekvenser

- Plus: lagringen slutar växa obegränsat; samma raderingskod i CLI och cron
  (en sanning); ingen ny auth-infrastruktur (bara en delad secret); paus och
  retention styrs via env utan kodändring.
- Minus: rensningen är per sajt (allt-eller-inget per `siteId`), inte
  per version — det speglar `delete-site`-granulariteten och är medvetet;
  per-versions-prune är en senare fråga om det behövs. Cron-tidpunkten ligger
  i `vercel.json` och kräver redeploy för att ändras.
