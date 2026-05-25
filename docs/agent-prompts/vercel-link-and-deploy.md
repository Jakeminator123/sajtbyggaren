# Builder-uppdrag: Vercel-länkning + minimal deploy-konfig

> Klistra in detta i en Cursor Cloud Background Agent eller annan
> isolerad builder-agent. Prompten är self-contained men har EN
> interaktiv punkt (OAuth-flöde mot Vercel) som operatören måste
> bekräfta i sin browser. Agenten ska pausa och rapportera när den
> kommer dit.

## Roll
Du är en builder-agent som ska länka detta GitHub-repo
(Jakeminator123/sajtbyggaren) till en ny Vercel-deployment som hostar
`apps/viewser/` (operatörs-UI:t). Konfigurationen ska vara MINIMAL
per operatör-direktiv: standard Vercel-produktion + preview, inga
extra Vercel-tjänster utan explicit operatör-godkännande.

## Förutsättningar (läs först, i denna ordning)
1. `AGENTS.md` — repo-konventioner
2. `governance/decisions/0030-preview-provider-portability.md` —
   Vercel måste vara adapter, INTE canonical runtime
3. `docs/reports/preview-runtime-matrix-2026-05-25.md` —
   beslutsbakgrund för varför Vercel valdes som hosting för viewser
4. `docs/known-issues.md` — sök på B146 för konfliktstatus mot main
5. `apps/viewser/package.json` — Next.js 16-app, bygg-konfig
6. `apps/viewser/next.config.ts` — production-headers + COEP/COOP
7. `apps/viewser/.env.example` — vilka env-vars apps/viewser behöver
8. `.env.example` (root) — vilka LLM-nycklar koden förväntar sig

## Mål (steg-för-steg)

### Steg 1: Vercel CLI tillgängligt
Verifiera att `vercel` CLI är installerat globalt. Om inte:
```bash
npm install -g vercel@latest
```
Verifiera version: `vercel --version` (förvänta >= 35).

### Steg 2: Skapa Vercel-projektet (OAuth-flöde, INTERAKTIVT)
Stega till `apps/viewser/` och kör:
```bash
cd apps/viewser
vercel link
```

Operatör-prompt vid första OAuth: agenten ska **pausa** och posta i
Sprintvakt-inbox via MCP-tool `post_message`:
```
from: cursor-builder-vercel-link
to: jakob-orchestrator
subject: vercel-oauth-needed
body: vercel link initierat. Operatör behöver godkänna OAuth-flödet i
      browsern och välja: (1) Vercel team/scope, (2) "Link to existing
      project" → No (skapa nytt), (3) projekt-namn: "sajtbyggaren-viewser",
      (4) directory: "./" (apps/viewser-mappen är cwd). Säg när klart.
```

Efter operatör säger ok, fortsätt. Resultatet ska vara en `.vercel/`-
mapp under apps/viewser/ med project.json + .vercelignore (auto-
genererad).

### Steg 3: Sätt production-branch till jakob-be (TILLFÄLLIGT)
Per operatör-direktiv 2026-05-25 ska production-branch initialt vara
`jakob-be`, inte `main`. Skälet: main är 1 commit framför jakob-be med
en oblockerad arkitektur-konflikt (se B146 i known-issues.md), och
jakob-be är den de facto integration-branchen tills konflikten löses.

Sätt via Vercel dashboard ELLER via CLI:
```bash
vercel project ls --scope <ditt-team>
vercel project update sajtbyggaren-viewser --production-branch jakob-be
```

Om CLI inte stödjer `--production-branch`, gör det manuellt i Vercel
dashboard: Project Settings → Git → Production Branch → jakob-be.

Lägg en TODO-rad i en ny fil `docs/operations/vercel-production-branch-todo.md`
som påminner: "när B146 löst och main = jakob-be, byt production
branch i Vercel till main".

### Steg 4: Konfigurera env-vars för Vercel
Använd `vercel env add` för dessa nycklar (operatör måste mata in
värden i prompten — agenten ska INTE läsa dem från lokala .env per
governance/rules/env-file-handling.md):

Required för apps/viewser att starta:
- OPENAI_API_KEY (Production + Preview + Development)

Optional men starkt rekommenderat:
- ANTHROPIC_API_KEY (Production + Preview + Development)
- OPENAI_MODEL (Production + Preview + Development, default gpt-5.5)

NEVER lägg på Vercel utan explicit operatör-fråga:
- GITHUB_TOKEN (security — Vercel ska inte ha repo-write)
- CURSOR_API_KEY (security — agent-tooling, inte runtime)
- STACKBLITZ_API (gäller bara WebContainer-vägen som vi parkerar)

Posta i Sprintvakt-inbox när du är vid env-steg:
```
from: cursor-builder-vercel-link
to: jakob-orchestrator
subject: vercel-env-input-needed
body: Behöver operatör mata in värden för OPENAI_API_KEY (production +
      preview + development) via vercel env add. Säg när klart, eller
      paste värdet i privat IDE-flik och säg "lokalt". Aldrig värdet
      i inbox-meddelande.
```

### Steg 5: Konfigurera build settings
Vercel auto-detektar Next.js men bekräfta:
- Framework Preset: Next.js
- Build Command: `next build` (default)
- Output Directory: `.next` (default)
- Install Command: `npm install` (default)
- Root Directory: `apps/viewser` (KRITISKT — annars bygger Vercel hela
  monorepo:t från repo-roten och misslyckas)

Sätt via dashboard eller `vercel.json` i apps/viewser/:
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "next build",
  "installCommand": "npm install"
}
```

(Root directory är project-level setting, sätts via dashboard, inte
vercel.json.)

### Steg 6: Trigger första deployment
```bash
cd apps/viewser
vercel --prod
```

Förväntat: ~3-5 min build-tid. Vercel kommer att klaga på saknade env-
vars om någon required är missing — fixa i steg 4 och kör om.

### Steg 7: Verifiera deployment
- Öppna den producerade URL:en (typiskt sajtbyggaren-viewser.vercel.app)
- Verifiera att operatörs-UI:t renderar
- Verifiera att en prompt går igenom (kommer kräva backend-server
  separat — bara UI-renderingen testas i denna deployment)

## Vad du EJ ska göra

- Installera aldrig Vercel KV, Vercel Postgres, Vercel Blob, Vercel
  AI Gateway, Vercel Edge Config eller andra Vercel-tjänster utan
  explicit operatör-godkännande. Vi vill INTE bli beroende av Vercel-
  specifika tjänster utöver det grundläggande hosting (per ADR 0030).
- Lägg aldrig in `@vercel/blob`, `@vercel/postgres`, `@vercel/kv` eller
  liknande SDK i package.json.
- Sätt aldrig upp Vercel-Cron-Jobs.
- Aktivera aldrig Vercel Analytics eller Speed Insights (separata
  abonnemang som kostar pengar utöver hosting).
- Koppla aldrig custom domän automatiskt — operatör vill själv välja
  domän.
- Läs aldrig `.env`-filer per governance/rules/env-file-handling.md.
- Merga aldrig något till main eller jakob-be utan operatör-OK.

## Konstruktion (om vercel.json eller liknande fil ska skapas)

Lägg ny `apps/viewser/vercel.json` med EXAKT detta innehåll:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "next build",
  "installCommand": "npm install"
}
```

Inget mer. Inga `headers`-array (next.config.ts hanterar COEP/COOP),
inga `redirects`, inga `rewrites`, inga `crons`, inga `functions`-blocks
med edge/runtime-overrides. Standard Vercel-Next.js setup.

## Begränsningar
- Branch-scope: denna agent får röra `apps/viewser/`, `package.json`,
  `vercel.json`, `.vercelignore`, och nya filer under `docs/operations/`.
  Allt annat är off-limits.
- Inga commits till main eller jakob-be utan operatör-OK.
- Inga PRs öppnas — denna PR landar via operator review efter agenten
  rapporterar klart.
- python-tester ska fortsatt passera lokalt (kör `python -m pytest tests/
  -q` när agenten är klar och rapportera resultat).
- ruff, governance_validate, rules_sync, check_term_coverage, sprintvakt
  ska alla vara gröna.

## Leverabel
Draft PR mot `jakob-be`. Innehåll:
- `apps/viewser/vercel.json` (4-rader, minimal)
- `apps/viewser/.vercel/` ENDAST om Vercel CLI auto-skapar (annars
  manuell skapelse är onödigt — projektet är redan länkat via OAuth)
- `docs/operations/vercel-production-branch-todo.md` (en TODO-fil för
  framtida branch-byte main ↔ jakob-be när B146 löses)
- Eventuellt `apps/viewser/.vercelignore` om det behövs explicit
  (default funkar oftast)

PR-titel: `feat(deploy): link apps/viewser to Vercel as primary hosting
(production branch: jakob-be temporary, target: main when B146 resolved)`

PR-beskrivning ska innehålla:
- Vercel project URL
- Production URL (vercel.app eller egen domän)
- Lista över env-vars du satt (men ALDRIG värden)
- Bekräftelse att första deployment lyckades med screenshot eller
  HTTP-status från curl mot prod-URL
- TODO-länk för att byta production-branch till main när B146 löses
- Hänvisning till ADR 0030 (adapter-not-dependency-låst)

## Misslyckande-mod
Om OAuth-flödet kraschar, deployment failar med build-error, eller env-
var saknas och operatör inte svarar inom rimlig tid (30 min för OAuth,
10 min för env-input), pausa och posta:

```
from: cursor-builder-vercel-link
to: jakob-orchestrator
subject: vercel-link-blocked
body: <kort beskrivning av blockerings-state, vad operatör behöver göra
       för att låsa upp, och om vi ska abort:a eller vänta>
```

Lämna inte hängande deployment-attempts. Om något ser fel ut, stoppa
hellre än improvisera.

## Efter framgång — nästa steg som DENNA agent INTE gör
Dessa hör till operatör-beslut eller framtida agent-uppdrag:
- Sätta upp custom domän (operatör-val)
- Byta production-branch från jakob-be till main (efter B146-lösning)
- Konfigurera Vercel Preview Deployments som B125-fallback (kommande
  ADR — sannolikt 0033 efter B146-port, eftersom 0031/0032 är upptagna)
- Vercel Analytics / Speed Insights / Observability Plus (separat ADR)
- Vercel AI Gateway (separat ADR eftersom det rör LLM-anrop)

## Modellval för agent
GPT-5-codex eller Composer 2.5 — det här är mest CLI-orchestration +
liten kod (vercel.json). Beräknad tid: 1-2 timmar inklusive
operatör-väntan på OAuth + env-input.
