## Viewser

`apps/viewser` är en localhost-only operatörsyta för:

- chat mot OpenAI (`/api/chat`)
- build-triggning via `python scripts/build_site.py` (`/api/build`)
- preview av senaste run i StackBlitz (`/api/runs/:runId/files`)
- enkel token/cost-meter i UI

Inget i denna app deployas eller binds till extern plattform i MVP-läget.

## Setup

1. Installera beroenden:

```bash
cd apps/viewser
npm install
```

2. Skapa lokal env-fil:

```bash
cp .env.example .env.local
```

3. Lägg in `OPENAI_API_KEY` i `.env.local`.

4. Starta:

```bash
npm run dev
```

Öppna [http://localhost:3000](http://localhost:3000).

## Manuell smoke-checklista

1. Välj dossier (default: `painter-palma`)
2. Skriv ett chat-meddelande
3. Klicka `Build <dossier>`
4. Vänta tills run är klar och Viewer Panel visar StackBlitz-preview
5. Bekräfta att Token Meter ökar efter chat-call och att build visas i run history

## Begränsningar i MVP

- ingen persistens av chat/tokens mellan reload
- endast OpenAI provider
- build-cost hämtas från `build-result.json:modelUsage` (just nu 0 i builder MVP)
- inga automatiska retries vid rate limits
