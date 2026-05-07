# Viewser MVP

`apps/viewser` är en localhost-app för operatören som binder ihop chat, build och preview.

## Syfte

- Ge en enkel yta för att prata med modellen.
- Låta operatören trigga `scripts/build_site.py` för vald dossier.
- Visa senaste run i StackBlitz preview utan deploy.
- Visa ackumulerad tokenanvändning i sessionen.

## Dataflöde

1. Operatören skriver i Chat Panel.
2. `POST /api/chat` anropar OpenAI server-side.
3. Operatören klickar build för vald dossier.
4. `POST /api/build` kör `python scripts/build_site.py --dossier <path>`.
5. Run artefakter hamnar i `data/runs/<runId>/`.
6. Viewer Panel hämtar filtrerat filträd via `GET /api/runs/<runId>/files`.
7. `@stackblitz/sdk` embed:ar projektfilerna i browsern.

## Centrala komponenter

- `components/chat-panel.tsx` - chat + build-knapp
- `components/viewer-panel.tsx` - StackBlitz embed
- `components/token-meter.tsx` - in-memory usage/cost
- `components/run-history.tsx` - välj tidigare run
- `components/dossier-picker.tsx` - välj dossier för nästa build

## Server routes

- `app/api/chat/route.ts` - OpenAI chat completions + usage
- `app/api/build/route.ts` - spawn builder + return runId/buildResult
- `app/api/runs/route.ts` - list runs och dossiers
- `app/api/runs/[runId]/files/route.ts` - return filkarta för StackBlitz

## Säkerhetsgränser i MVP

- inga API-nycklar exponeras till klienten
- runId valideras och path-traversal blockeras
- viewser läser från `data/runs/`, men skriver inte dit direkt
- LLM-anrop sker bara i server route

## Kända begränsningar

- chat-historik och tokenmeter är in-memory
- ingen streaming i chat-svaret
- build timeout är 180 sekunder
- StackBlitz får filtrerad filmängd (skip av binärer och stora filer)
