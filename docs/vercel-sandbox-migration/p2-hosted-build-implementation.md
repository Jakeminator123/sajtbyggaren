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
  └─ GET /api/hosted-build/<runId>  (läser status via kv-store-adaptern)
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
  skriver den publika URL:en till stdout och sparar den i KV under
  `viewser:build-context:url` när KV-env finns (annars notis på stderr).
- Token-upplösning: `process.env.BLOB_READ_WRITE_TOKEN`, annars repo-rotens
  `.env`, sist `apps/viewser/.env.vercel.local`.

Kör om CLI:t varje gång Python-pipen (scripts/packages/governance/starters)
ändras — bygg-sandboxen ser bara det som ligger i tarballen.

## Env-krav

I den hostade Viewser-processen (eller lokalt vid test av runnern):

| Env | Krävs | Används till |
| --- | --- | --- |
| `VERCEL_OIDC_TOKEN` eller `VERCEL_TOKEN`+`VERCEL_TEAM_ID`+`VERCEL_PROJECT_ID` | ja | `Sandbox.create` (samma auth-trio som preview-runnern) |
| `BLOB_READ_WRITE_TOKEN` | ja | skickas in i sandboxen för output-uploaden |
| `KV_REST_API_URL`/`KV_REST_API_TOKEN` (eller `VIEWSER_KV_REST_*`/`UPSTASH_REDIS_REST_*`) | rekommenderas | run-status + pekare; utan dem blir status memory-driver lokalt och sandboxens status-POST:ar hoppas över |
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

Pollning: `GET /api/hosted-build/<runId>` returnerar status-JSON:en, 404 med
svensk notis när nyckeln saknas/förfallit.

## Ingår INTE i P2 (hanteras separat)

- Auth/tenant-isolering (G4): routen kör `assertLocalhost` som idag; hostat
  bypassas den via env tills riktig auth landar. Ingen publik POST-endpoint
  som startar byggen skapades i detta steg (#156-risken).
- Kvoter, kostnadsstyrning, idle-stop utöver sandbox-TTL (G7).
- Persistens av run-historik (`data/runs/`, `data/prompt-inputs/`) hostat —
  följdprompter (`followup: true`) kräver den och failar ärligt i sandboxen
  tills den biten landar.
- Städning av föråldrade blobbar under `generated/<siteId>/` — samma
  semantik som snapshot-CLI:t (overwrite, ingen delete), så en borttagen
  route kan lämna en kvarliggande fil i blob tills en städrutin landar.
