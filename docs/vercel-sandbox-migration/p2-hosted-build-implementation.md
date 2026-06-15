# P2 — Hostat bygge i Vercel Sandbox (implementation)

Status: implementerad (statisk verifiering); ej end-to-end-körd ännu.
Beslutsgrund: G1 alternativ A + G2 i `01-arkitekturval.md` — Python-pipen körs
oförändrad i en sandbox, blob är artefaktlager, KV håller pekare/status.

## Arkitektur

```
operatör (lokalt, en gång per pipe-ändring)
  └─ apps/viewser/scripts/upload-build-context-to-blob.mjs
       └─ blob: build-context/current.tar.gz  (+ KV: viewser:build-context:url)

hostad Viewser (serverless)
  └─ startHostedBuild()  (apps/viewser/lib/hosted-build-runner.ts)
       ├─ KV: viewser:hosted-run:<runId> = { phase: "queued", ... }  (TTL 24 h)
       └─ Sandbox.create(source: tarball) -> writeFiles(hosted-build.sh)
            -> runCommand(detached) -> svarar direkt med { runId }

bygg-sandbox (node24, TTL 15 min, kör hosted-build.sh detached)
  ├─ pip install -r requirements.txt
  ├─ scripts/prompt_to_project_input.py  (prompt -> dossier)
  ├─ scripts/build_site.py --dossier ... --generated-dir /vercel/sandbox/.generated-output
  ├─ blob: generated/<siteId>/<relPath>   (fil för fil, samma layout som
  │        lib/generated-blob-source.ts listar/läser — hostad preview funkar direkt)
  ├─ KV: viewser:site:<siteId>:current = { buildId, blobPrefix, updatedAt }
  └─ KV: viewser:hosted-run:<runId> uppdateras efter varje fas

UI/klient
  └─ GET /api/hosted-build/<runId>?siteId=<siteId>  (läser status via
       kv-store-adaptern; siteId-bindningen är B196-härdningen)
```

Ingen tarball för sajt-outputen: läsaren (`lib/generated-blob-source.ts`)
listar per-fil-blobbar under prefixet `generated/<siteId>/`, så uploaden sker
fil för fil med samma skip-kataloger (`node_modules`, `.next`, `.git`,
`.turbo`, `.vercel`, `.cache`, `out`) och samma `.env*`-skydd som
`apps/viewser/scripts/snapshot-site-to-blob.mjs`.

## Hur build-kontexten uppdateras (operatörs-CLI)

Kör lokalt (Windows-kompatibelt — använder systemets `tar`, bsdtar ingår i
Windows 10+; ingen ny npm-dependency):

```
node apps/viewser/scripts/upload-build-context-to-blob.mjs
```

- Paketerar `scripts/`, `packages/`, `governance/`, `data/starters/`,
  `requirements.txt`, `pyproject.toml` som tar.gz. Repo-roten har ingen
  `config/`-katalog — pipens konfiguration ligger i `governance/policies/`
  och `governance/schemas/`, som följer med. Övriga `data/`-undermappar
  (runs, prompt-inputs, uploads, evals) är lokal historik och ingår inte.
- Exkluderar `node_modules`, `.venv`, `.git`, `.next`, `__pycache__`,
  `*.pyc` (och `.env*` täcks aldrig av inkluderingslistan).
- Laddar upp till blob-pathname `build-context/current.tar.gz`
  (`access: public`, `allowOverwrite: true`, `addRandomSuffix: false`),
  skriver den publika URL:en till stdout och sparar URL, git-SHA och
  dirty-flagga i KV under `viewser:build-context:url`,
  `viewser:build-context:sha` och `viewser:build-context:dirty` när KV-env
  finns (annars notis på stderr).
- Token-upplösning: `process.env.BLOB_READ_WRITE_TOKEN`, annars repo-rotens
  `.env`, sist `apps/viewser/.env.vercel.local`.

Kör checken och sedan uploaden varje gång Python-pipen eller OpenClaw-kedjan
ändras — bygg-sandboxen ser bara det som ligger i tarballen:

```bash
cd apps/viewser
npm run build-context:check
npm run build-context:upload
```

Checken jämför sparad `viewser:build-context:sha` mot aktuell git-commit för
`scripts/`, `packages/`, `governance/`, `data/starters/`, `requirements.txt`
och `pyproject.toml`. Om senaste upload gjordes från ett dirty arbetsträd
varnar checken också via `viewser:build-context:dirty`. Ingen auto-publish
sker.

## Env-krav

I den hostade Viewser-processen (eller lokalt vid test av runnern):

| Env | Krävs | Används till |
| --- | --- | --- |
| `VERCEL_OIDC_TOKEN` eller `VERCEL_TOKEN`+`VERCEL_TEAM_ID`+`VERCEL_PROJECT_ID` | ja | `Sandbox.create` (samma auth-trio som preview-runnern) |
| `BLOB_READ_WRITE_TOKEN` | ja | skickas in i sandboxen för output-uploaden |
| `KV_REST_API_URL`/`KV_REST_API_TOKEN` (eller `VIEWSER_KV_REST_*`/`UPSTASH_REDIS_REST_*`) | ja hostat (`VERCEL=1`) | run-status + pekare. Preflight i `startHostedBuild` failar hårt FÖRE `Sandbox.create` utan dem hostat (annars hänger status-pollningen till timeout). Lokalt utan `VERCEL=1`: memory-driver, sandboxens status-POST:ar hoppas över ärligt |
| `VIEWSER_BUILD_CONTEXT_URL` | fallback | används om KV-nyckeln `viewser:build-context:url` saknas |
| `OPENAI_API_KEY` (+ valfri `OPENAI_MODEL`) | nej | utan nyckel kör pipen ärlig mock-fallback (`briefSource=mock-no-key`) |

In i sandboxen skickas (via `runCommand env`): `RUN_ID`, `SITE_ID`,
`PROMPT_TEXT`, `FOLLOWUP_MODE`, `BLOB_READ_WRITE_TOKEN`, `KV_REST_URL`,
`KV_REST_TOKEN`, `OPENAI_API_KEY` samt `OPENAI_MODEL` när den är satt.

## Statusnycklar i KV

- `viewser:hosted-run:<runId>` (TTL 24 h): JSON
  `{ runId, siteId, phase, startedAt, updatedAt, error?, buildId?, blobPrefix? }`.
  Faser: `queued` (sätts av runnern) -> `installing` -> `project-input` ->
  `building` -> `uploading` -> `done`, eller `failed` med `error`-text.
- `viewser:site:<siteId>:current` (ingen TTL): JSON
  `{ buildId, blobPrefix, updatedAt }` — hostad motsvarighet till
  `current.json`-pekaren på disk. Sätts först efter lyckad blob-upload.
- `viewser:build-context:url` (ingen TTL): rå URL-sträng till senaste
  build-kontext-tarballen (skrivs av operatörs-CLI:t).
- `viewser:build-context:sha` (ingen TTL): git-SHA som senaste
  build-kontext-tarballen laddades upp från.
- `viewser:build-context:dirty` (ingen TTL): `true` när senaste upload
  gjordes med ocommittade ändringar i build-kontext-ytorna.

Pollning: `GET /api/hosted-build/<runId>?siteId=<siteId>` returnerar
status-JSON:en när siteId matchar statusens. 404 med samma svenska notis vid
saknad/förfallen nyckel OCH vid siteId-mismatch (B196: identiskt svar i båda
fallen så routen aldrig bekräftar att ett gissat runId existerar). Utan
`?siteId=` svarar routen 400.

## Ingår INTE i P2 (hanteras separat)

- Auth/tenant-isolering (G4): routen kör `assertLocalhost` som idag; hostat
  bypassas den via env tills riktig auth landar. Ingen publik POST-endpoint
  som startar byggen skapades i detta steg (#156-risken).
- Kvoter, kostnadsstyrning, idle-stop utöver sandbox-TTL (G7).
- Persistens av run-historik (`data/runs/`, `data/prompt-inputs/`) hostat —
  följdprompter (`followup: true`) kräver den och failar ärligt i sandboxen
  tills den biten landar.
- ~~Städning av föråldrade blobbar under `generated/<siteId>/`~~ — löst via
  manifest-baserad servering (B195, PR #287): bygget publicerar sist
  `generated/<siteId>/.manifest.json` med byggets exakta fil-set och
  `lib/generated-blob-source.ts` serverar bara manifest-listade filer, så
  stale blobbar ignoreras utan radering.
- Strukturerad discovery-payload hostat (B197): den hostade vägen skickar
  bara `PROMPT_TEXT` in i sandboxen — wizardens `discovery`-block når aldrig
  `prompt_to_project_input.py` där (lokalt gör det det). P3-spår.
