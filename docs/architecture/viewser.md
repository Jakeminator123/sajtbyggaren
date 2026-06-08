# Viewser MVP

`apps/viewser` är en **localhost-only operator-prototype** som binder ihop
PromptBuilder, build-triggning, run history och preview av senaste run. Den är
inte en canonical runtime och kommer att ersättas av Sprint 4 LocalRuntime /
StackBlitzRuntime när de finns. Hosted Vercel-deploys får visa UI/read-only
diagnostik, men prompt/build/scrape-actions blockas med 501 eftersom de ännu
shellar repo-lokala Python-skript.

## Avgränsning

Viewser är ett dev-verktyg, inte en produkt. Den får inte:

- implementera Dossier-edit, canonical Project DNA-editor, Repair Pipeline
  eller Quality Gate (de hör till `packages/generation/`)
- skapa egna artefaktkontrakt utöver det `build_site.py` redan producerar
- exponera publika endpoints (localhost-guard avvisar non-local anrop)
- bli produktionsberoende av en deploy-plattform
- försöka köra `prompt_to_project_input.py`, `build_site.py` eller
  `scrape_site.py` från hosted Vercel Node-functions

## Mentalmodell

| Operator-yta i Viewser | Vad det är |
|---|---|
| Project Input          | Konkret kundprojekt (t.ex. `painter-palma`). Filer: `examples/<siteId>.project-input.json`. |
| PromptBuilder          | Fri init-prompt och follow-up prompt versions ovanpå Builder MVP |
| Viewer                 | StackBlitz embed av Generated Files-snapshot |
| Token Meter            | Lokal aggregering av OpenAI usage + buildResult |

`painter-palma` är ett **Project Input**, **inte** en Dossier. En Dossier är
en återanvändbar capability/legokloss (t.ex. `pacman-game`, `stripe-checkout`).
Klassen är `soft` eller `hard` (se ADR 0012).

## Dataflöde

1. Operatören skriver en fri init-prompt eller väljer en befintlig run/site för
   follow-up prompt versions.
2. `POST /api/prompt` kör helpern som skapar eller uppdaterar Project Input
   under `data/prompt-inputs/` i lokal runtime. På hosted Vercel returnerar
   routen 501 i stället för att försöka spawna Python.
3. Viewser triggar Builder MVP med den genererade dossier-pathen.
4. `POST /api/build` kör `python scripts/build_site.py --dossier <path>` i
   lokal runtime. På hosted Vercel returnerar routen 501.
5. Run-artefakter hamnar i `data/runs/<runId>/` enligt builder MVP.
6. Viewer Panel hämtar filtrerat filträd via `GET /api/runs/<runId>/files`.
7. `@stackblitz/sdk.embedProject` mountar projektfilerna i browsern.

API-mekanism: **Next.js App Router route handlers** (`app/api/.../route.ts`).
Vi använder inte Server Actions i denna runda.

## Filhämtning för preview

`lib/stackblitz-files.ts` läser källan i denna prioritetsordning:

1. `build-result.generatedFilesDir` (canonical snapshot under
   `data/runs/<runId>/generated-files/`).
2. Lokalt beräknad path till samma snapshot.
3. `build-result.devPreviewDir` (legacy fallback `.generated/<siteId>/`).

Detta håller Viewser inom det artefaktkontrakt builder MVP redan exponerar -
inget nytt kontrakt smugglas in i denna PR.

## Token cap

`lib/openai.ts` läser `VIEWSER_MAX_CHAT_TOKENS` (default 1500) och skickar det
som `max_tokens` till OpenAI. Dessutom valideras request-payload mot:

- max 40 meddelanden per request
- max 8000 tecken per meddelande

## Env-matris: root vs viewser

Viewser läser **sin egen** env, inte repo-roten. Next.js dotenv-laddningen är
scopad till `apps/viewser/` (`.env.development.local` > `.env.local` >
`.env.development` > `.env`, och `process.env` vinner alltid). Repo-rotens
`/.env` laddas **aldrig** av Viewser-processen — sätt Viewser-värden i
`apps/viewser/.env.local`. Den fullständiga, kommenterade listan bor i
`apps/viewser/.env.example`; tabellen nedan är sanningskällan för vem som läser
vad (varje rad har en verifierad läsare i koden).

| Variabel | Läses av | Default / not |
|---|---|---|
| `OPENAI_API_KEY` | `lib/openai.ts`, `lib/asset-store/vision.ts`, `app/api/generate-image/route.ts` | Krävs för riktiga anrop; annars mock/fel. |
| `OPENAI_MODEL` | `lib/openai.ts` | Fallback `gpt-4o`. |
| `OPENAI_VISION_MODEL` | `lib/asset-store/vision.ts` | Fallback `gpt-4o`. |
| `OPENAI_IMAGE_MODEL` / `OPENAI_IMAGE_QUALITY` | `app/api/generate-image/route.ts` | Fallback `gpt-image-1.5` / `medium`. |
| `OPENAI_INPUT_USD_PER_1K` / `OPENAI_OUTPUT_USD_PER_1K` | `lib/openai.ts` | Token Meter-prislapp, default `0`. |
| `VIEWSER_RUNS_DIR` | `lib/runs.ts`, `lib/build-runner.ts`, `packages/generation/orchestration/context/sources.py` | Default `../../data/runs`. |
| `VIEWSER_MAX_CHAT_TOKENS` | `lib/openai.ts` | Default `1500`. |
| `VIEWSER_PREVIEW_MODE` | `next.config.ts`, `scripts/dev.mjs` | Default `local-next`; styr driftläget. |
| `VIEWSER_ALLOW_NON_LOCALHOST` / `VIEWSER_ALLOWED_HOSTS` | `lib/localhost-guard.ts` | Localhost-guard. |
| `ASSET_STORE_DRIVER` / `BLOB_READ_WRITE_TOKEN` | `lib/asset-store/index.ts`, `app/api/upload-asset/route.ts`, `lib/asset-store/vercel-blob.ts` | `local` (default) eller `vercel-blob`. |
| `SAJTBYGGAREN_GENERATED_DIR` | `lib/local-preview-server.ts`, `lib/vercel-sandbox-runner.ts` (+ `scripts/build_site.py`) | Var den byggda sajten ligger. |
| `VERCEL_OIDC_TOKEN` / `VERCEL_TOKEN` + `VERCEL_TEAM_ID` + `VERCEL_PROJECT_ID` | `lib/vercel-sandbox-runner.ts` | Sandbox-auth; läses även från `.env.vercel.local`. |
| `VIEWSER_SANDBOX_SPIKE` / `VIEWSER_SANDBOX_SPIKE_TTL_MS` | `scripts/spike_vercel_sandbox.ts`, `lib/vercel-sandbox-runner.ts` | Flaggad PoC, default av. |

På Python-sidan (root) styrs generationens modell-routing av
`governance/policies/llm-models.v1.json` (rollerna briefModel/planningModel/
codegenModel) — **inte** av `OPENAI_MODEL`. Root-skripten läser bara
`OPENAI_API_KEY` (plus `SAJTBYGGAREN_*` prune/path-vars) ur env.

### Känd inkonsekvens: modell-fallback

`OPENAI_MODEL` (`lib/openai.ts`) och `OPENAI_VISION_MODEL`
(`lib/asset-store/vision.ts`) faller båda tillbaka till `gpt-4o` när de inte är
satta. Eftersom Viewser inte läser `/.env` når rotens `OPENAI_MODEL=gpt-5.4`
aldrig Viewser. Vill du att Viewser ska matcha root måste du sätta dem i
`apps/viewser/.env.local`; annars kör Viewser på `gpt-4o`.

### Två driftlägen

Båda lägena skapar Project Input, runs och den genererade sajten på samma sätt
lokalt — skillnaden ligger i var **preview** körs och var dess state lever.

| Steg | (a) lokal `/studio` (`local-next`) | (b) `vercel-sandbox` |
|---|---|---|
| Project Input | `data/prompt-inputs/<siteId>.project-input.json` (`POST /api/prompt` → `lib/prompt-runner.ts`) | samma lokalt |
| Runs | `data/runs/<runId>/` (`VIEWSER_RUNS_DIR`) | samma lokalt |
| Genererad sajt | `SAJTBYGGAREN_GENERATED_DIR/<siteId>/builds/<buildId>/` | samma lokalt (byggs först) |
| Preview | `lib/local-preview-server.ts` spawnar `next start` på `localhost:<4100-4199>` | `POST /api/preview/<siteId>` → `lib/vercel-sandbox-runner.ts` bygger/kör i isolerad sandbox-state och iframe:ar publik `…vercel.run`-URL (kräver Vercel-auth) |

## Säkerhetsgränser

- **Localhost-guard** (`lib/localhost-guard.ts`) avvisar allt som inte är
  `localhost` / `127.0.0.1` / `::1`. `VIEWSER_ALLOWED_HOSTS` kan sättas
  till en comma-separated lista med specifika hostar (t.ex. Vercel preview-
  och production-domäner) som får använda API:erna utan att hela ytan öppnas.
  `VIEWSER_ALLOW_NON_LOCALHOST=true` finns kvar som full bypass, men bör bara
  användas medvetet eftersom Viewser fortfarande saknar auth och rate-limit.
- `siteId` valideras mot `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` innan
  `assertProjectInputExists` rör filsystemet.
- `runId` valideras mot `^[a-zA-Z0-9._-]+$` och path-containment kollas mot
  `runsDir()`.
- Symlinks i `generated-files/` ignoreras vid file-walk för StackBlitz.
- LLM-anrop sker enbart i server route. Inga API-nycklar exponeras till
  klienten.
- Build-runner serialiserar concurrent POSTs så de inte race:ar `.generated/`.

## Kända begränsningar

- Token Meter är in-memory
- ingen streaming i promptsvar
- build timeout är 180 sekunder
- StackBlitz får filtrerad och deterministiskt sorterad filmängd (binärer och
  stora filer skippas)
- Token Meter visar **uppskattning** baserat på env-prislapp; ingen hård cap
  förutom `max_tokens`-gränsen per anrop
