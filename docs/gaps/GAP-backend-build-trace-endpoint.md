---
id: GAP-backend-build-trace-endpoint
type: Gap/Runtime
owner: jakob
title: Build-trace endpoint + baseRunId i /api/prompt — unlocks Live Build Sync A+D
whyNow: |
  UI-laget (christopher-ui) har levererat:
  - Front 1: live-preview variants (PR #71)
  - Front 2: wizard första intryck (PR #71)
  - Front 3: versions-tab + diff (PR #71)
  - Wizard minimalism (PR #71)
  - Live Build Sync UI (B+C, GAP-viewser-live-build-sync) — kommande

  Två "fantastisk hemsida"-features blockeras av att backend inte
  exponerar pipeline-status under en pågående build:

  A) Real pipeline-status i FloatingChat
     - Idag visar FloatingChat fyra hårdkodade `setTimeout`-steg
       ("Förstår din instruktion" → 5s → "Planerar ändringarna" → 7s
        → "Bygger om sajten" → 14s → "Kvalitetskollar" → 60s).
     - Det matchar inte verkligheten — brief kan vara klar på 1s,
       codegen kan ta 90s, och quality gate kan misslyckas tidigt.
     - Resultat: operatören får "är det stuck?"-känsla precis när
       systemet borde inge mest förtroende.
     - Riktig pipeline-status finns redan på disk i
       `data/runs/<runId>/trace.ndjson` (`phase`, `event`, `status`,
       `payloadPath`) men ingen Viewser-route läser den.

  D) "Iterera från version N"
     - UI har en knapp som öppnar FloatingChat med prompt-prefix
       "Utgå från version N: …", men backend följer fortfarande
       senaste Project Input för siteId (se
       `scripts/prompt_to_project_input.py:2782-2822`).
     - För riktig semantisk iteration från en historisk version
       behöver `/api/prompt` ta emot `baseRunId` och
       `prompt_to_project_input.py` läsa PI-snapshotet från den runen.

  Två relaterade gaps slår också in på samma område:
  - `/api/runs` filtrerar bort pågående runs (kräver
    `build-result.json`). UI kan inte visa "version 7 är på gång"
    med en riktig runId förrän bygget är 100% klart.
  - `/api/prompt` är blockerande och returnerar runId först när allt
    är klart. UI får ingen handle på bygget medan det pågår.

  Detta gap-dokument är en backend-specifikation skriven av UI-laget.
  Jakob får frihet att implementera på sätt han föredrar. Vi listar
  bara minimum-kontrakt UI behöver.

paths:
  # Förslag — Jakob bestämmer slutgiltig placering:
  - apps/viewser/app/api/runs/[runId]/trace/route.ts  # NY
  - apps/viewser/app/api/prompt/route.ts              # baseRunId-stöd
  - apps/viewser/lib/runs.ts                          # listRuns inkluderar in-progress
  - scripts/prompt_to_project_input.py                # baseRunId
  - scripts/build_site.py                             # ev. tidigare runId-emit
  - packages/generation/build/**                      # om phase-events behöver berikas
  - tests/test_runs_api.py                            # NY eller utökad
  - tests/test_prompt_route.py                        # baseRunId-fall

doNotTouch:
  # UI är klart för dessa features och rör inte sin del:
  - apps/viewser/components/builder/floating-chat.tsx
  - apps/viewser/components/builder/inspector/versions-tab.tsx
  - apps/viewser/components/discovery-wizard/**

acceptanceCriteria:
  # A) Trace-endpoint:
  - "GET /api/runs/[runId]/trace returnerar de senaste N (default 50)
    trace-events från data/runs/<runId>/trace.ndjson som JSON-array.
    Stöd för ?since=<timestamp> så UI kan polla incrementally."
  - "Responsen inkluderar `runId`, `events` (array av trace-event), och
    `runStatus: 'pending' | 'ok' | 'degraded' | 'failed' | 'skipped'`.
    pending = run pågår (build-result.json saknas än)."
  - "Varje trace-event har minst: `phase`, `event`, `status`,
    `timestamp`, `message`, optional `payloadPath`."
  - "Endpoint är read-only och stänger gracefully om runId inte finns
    (404) eller om trace.ndjson är skadad (200 med tom events-array
    + warning-header)."
  - "Respekterar localhost-guard på samma sätt som /api/runs."

  # Pågående runs synliga:
  - "GET /api/runs returnerar både färdiga och pågående runs. Pågående
    runs (utan build-result.json) inkluderas med status='pending' och
    läser metadata från input.json + sista trace-eventet."
  - "Stöd för ?siteId=<id>-filter direkt i query (idag filtrerar UI
    client-side på 20 senaste)."

  # D) baseRunId:
  - "POST /api/prompt accepterar valfri `baseRunId: string` när
    mode='followup'. Om angiven, laddas Project Input-snapshotet från
    den runen istället för senaste."
  - "Versionsräkning blir baserunVersion + 1 (med skydd mot duplicat
    om operatören iterar samma version flera gånger — kanske
    `Math.max(latestVersion, baserunVersion) + 1`)."
  - "Om baseRunId inte tillhör samma siteId returneras 400 med ett
    tydligt felmeddelande."
  - "Backward compatible: utan baseRunId fungerar follow-up som idag
    (senaste PI för siteId)."

  # Tidigt runId (nice-to-have, inte blocker):
  - "Önskvärt: /api/prompt returnerar `runId` så fort backend har
    allokerat det (efter input.json är skrivet) via response-header
    `X-Run-Id` eller liknande, så UI kan börja polla trace-endpoint
    innan hela bygget är klart. Om det kräver SSE/streaming är det
    OK att hoppa över i v1 — UI har en workaround via pending-row
    + post-build runId-match."

checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/rules_sync.py --check
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint
  - "Manuell: en pågående follow-up syns i /api/runs med
    status='pending' och kan följas via /api/runs/[runId]/trace."

collisionRisk: yellow
reviewer: christopher
status: queued
createdAt: 2026-05-25T02:35:00Z
updatedAt: 2026-05-25T02:35:00Z
notes:
  - Detta är en UI-skriven backend-spec. Jakob har final say på
    implementation, response-shape och teststrategi.
  - Trace-endpoint är låg risk — pure read av en NDJSON-fil som
    redan skrivs.
  - baseRunId-ändringen är högre risk eftersom den rör
    Project-Input-snapshot-flödet i prompt_to_project_input.py.
    Rekommendation: gör den som ett separat sub-gap om scope
    blir för stort.
  - UI-koden för "Iterera från version N" är skriven så den
    fungerar med prompt-prefix-workaround idag. Den uppgraderar
    automatiskt till baseRunId så fort backend stödjer det
    (vi byter bara från prefix → query-param i fetch).
---

## Föreslagen response-shape för trace-endpoint

Ett trace-event har minst följande fält (Jakob bestämmer exakt
TypeScript-shape):

- `runId: string`
- `phase: "understand" | "plan" | "build"`
- `event: string` (t.ex. `brief.generated`, `codegen.started`)
- `status: "ok" | "warn" | "error" | "in-progress"`
- `timestamp: string` (ISO 8601)
- `message?: string` (frivilligt klartext-meddelande)
- `payloadPath?: string` (relative path mot `data/runs/<runId>/`)

Trace-endpointen returnerar:

- `runId: string`
- `runStatus: "pending" | "ok" | "degraded" | "failed" | "skipped"`
- `events: <event-array>` (senaste N, default 50)
- `artefactsPresent: string[]` (lista av filer som finns i run-mappen)

## Föreslagen `/api/runs` förändring

`run-meta`-objektet utökas med:

- `status: "pending" | "ok" | "degraded" | "failed" | "skipped"`
  (NYTT värde: `pending`)
- `currentPhase?: "understand" | "plan" | "build"` (bara för pending)
- `currentEvent?: string` (bara för pending)

Listans response-shape är bakåtkompatibel: lägg bara till nya fält,
ändra inga existerande.

## Föreslagen `/api/prompt` förändring

```ts
const PromptPayloadSchema = z.object({
  prompt: z.string().min(1),
  mode: z.enum(["init", "followup"]).default("init"),
  siteId: z.string().optional(),
  baseRunId: z.string().optional(),   // NYTT — endast giltig med mode='followup'
  discovery: DiscoveryPayloadSchema.optional(),
});
```

## Why this matters for the product compass

Detta gap stänger pilen "följdprompt → ny version" i kärnflödet
(`prompt → preview → följdprompt → ny version`). Med real pipeline-
status och iteration från valfri version blir Sajtbyggaren från
"AI-generator" till "AI-medbyggare" — exakt produkt-löftet i
`docs/product-operating-context.md`.
