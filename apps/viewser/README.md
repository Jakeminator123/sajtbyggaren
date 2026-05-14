## Viewser

`apps/viewser` är en **localhost-only operator-prototype** för Sajtbyggaren. Den
binder ihop PromptBuilder, `scripts/build_site.py`, run history och preview av
senaste run via StackBlitz. Inget i denna app deployas och inget i den är en
canonical runtime; den är ett dev-verktyg före Sprint 4.

## Vad Viewser INTE är

- **Inte canonical runtime.** Sprint 4 LocalRuntime/StackBlitzRuntime ersätter
  preview-vägen.
- **Inte canonical Project DNA-editor eller Repair Pipeline/Quality Gate-yta.**
  Follow-up prompt versions finns i Viewser som operatörsflöde, men kontrakt och
  generation bor fortsatt i `packages/generation/` och scripts.
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
| `VIEWSER_MAX_CHAT_TOKENS`      | Max output-tokens per server-side OpenAI-call (default 1500).        |
| `VIEWSER_ALLOW_NON_LOCALHOST`  | Sätt `true` enbart om du vet vad du gör. Default localhost-only.     |

## Manuell smoke-checklista

1. Skriv en fri init-prompt i PromptBuilder och kör flödet.
2. Vänta tills run är klar och Viewer Panel visar StackBlitz-preview.
3. Välj en befintlig run/site när du vill testa follow-up prompt versions.
4. Skriv en följdprompt och bekräfta att samma `projectId` får bumpad version.
5. Bekräfta att build syns i Run History och att Token Meter uppdateras när
   server-side modellen används.

## Begränsningar i MVP

- Ingen persistens av token-state mellan reload.
- Endast OpenAI som provider.
- Build-cost hämtas från `build-result.json:modelUsage` (just nu 0 i builder MVP).
- Ingen retry vid rate-limits - fail fast och visa felet.
- Ingen autentisering - localhost-guard är enda skyddet.
