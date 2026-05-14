# Viewser MVP

`apps/viewser` är en **localhost-only operator-prototype** som binder ihop
PromptBuilder, build-triggning, run history och preview av senaste run. Den är
inte en canonical runtime och kommer att ersättas av Sprint 4 LocalRuntime /
StackBlitzRuntime när de finns.

## Avgränsning

Viewser är ett dev-verktyg, inte en produkt. Den får inte:

- implementera Dossier-edit, canonical Project DNA-editor, Repair Pipeline
  eller Quality Gate (de hör till `packages/generation/`)
- skapa egna artefaktkontrakt utöver det `build_site.py` redan producerar
- exponera publika endpoints (localhost-guard avvisar non-local anrop)
- bli produktionsberoende av en deploy-plattform

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
   under `data/prompt-inputs/`.
3. Viewser triggar Builder MVP med den genererade dossier-pathen.
4. `POST /api/build` kör `python scripts/build_site.py --dossier <path>`.
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

## Säkerhetsgränser

- **Localhost-guard** (`lib/localhost-guard.ts`) avvisar allt som inte är
  `localhost` / `127.0.0.1` / `::1`. Kan stängas av med
  `VIEWSER_ALLOW_NON_LOCALHOST=true` (escape hatch).
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
