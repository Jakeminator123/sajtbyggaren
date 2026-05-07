## Viewser

`apps/viewser` är en **localhost-only operator-prototype** för Sajtbyggaren. Den
binder ihop chat (OpenAI), manuell build-triggning av `scripts/build_site.py`
och en preview av senaste run via StackBlitz. Inget i denna app deployas och
inget i den är en canonical runtime; den är ett dev-verktyg före Sprint 4.

## Vad Viewser INTE är

- **Inte canonical runtime.** Sprint 4 LocalRuntime/StackBlitzRuntime ersätter
  preview-vägen.
- **Inte en plats för Dossier-edit, Project DNA, follow-up, Repair Pipeline
  eller Quality Gate.** De bor i `packages/generation/` och kommer i Sprint 2-3.
- **Inte en publik produkt.** Det finns ingen auth eller rate-limit; servern
  avvisar non-localhost-anrop.

## Stack

- Next.js 16 + Tailwind 4 + shadcn/ui (samma som `marketing-base`)
- Server-side adapters: `openai`, `zod`, `@stackblitz/sdk`
- API route handlers under `app/api/` (inga Server Actions)

## Setup

```bash
cd apps/viewser
npm install
cp .env.example .env.local
# Lägg in din OPENAI_API_KEY
npm run dev
```

Öppna [http://localhost:3000](http://localhost:3000).

## Env-variabler

| Variabel                       | Syfte                                                                |
|--------------------------------|----------------------------------------------------------------------|
| `OPENAI_API_KEY`               | Server-side OpenAI-anrop. Aldrig exponerad till klient.              |
| `OPENAI_MODEL`                 | Modell-id (default `gpt-4o-mini`).                                   |
| `OPENAI_INPUT_USD_PER_1K`      | Pris per 1k input-tokens. Token Meter använder detta.                |
| `OPENAI_OUTPUT_USD_PER_1K`     | Pris per 1k output-tokens.                                           |
| `VIEWSER_RUNS_DIR`             | Path till `data/runs` (default `../../data/runs`).                   |
| `VIEWSER_MAX_CHAT_TOKENS`      | Max output-tokens per chat-call (default 1500).                      |
| `VIEWSER_ALLOW_NON_LOCALHOST`  | Sätt `true` enbart om du vet vad du gör. Default localhost-only.     |

## Manuell smoke-checklista

1. Välj ett **Project Input** (default: `painter-palma`). Detta är site-data,
   inte en capability Dossier.
2. Skriv ett chat-meddelande - chatten kan diskutera valt input men ändrar
   ingenting i denna runda.
3. Klicka `Build <siteId>`.
4. Vänta tills run är klar och Viewer Panel visar StackBlitz-preview.
5. Bekräfta att Token Meter ökar efter chat-call och att build syns i Run
   History.

## Begränsningar i MVP

- Ingen persistens av chat eller token-state mellan reload.
- Endast OpenAI som provider.
- Build-cost hämtas från `build-result.json:modelUsage` (just nu 0 i builder MVP).
- Ingen retry vid rate-limits - fail fast och visa felet.
- Ingen autentisering - localhost-guard är enda skyddet.
