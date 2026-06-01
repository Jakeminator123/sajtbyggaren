# Builder-uppdrag: PreviewRuntime Bite B — wire local + stackblitz adaptrar

> Klistra in detta i en Cursor-agent (lokal eller cloud-grind). Prompten är
> self-contained. Det här är **wiring inom redan beslutad arkitektur** —
> inga ADR-ändringar, inga nya canonical-namn, ingen ny vendor-adapter.
> Bite A landade som commit `bb6ab2e` på `jakob-be` och skapade adapter-
> skelettet i `packages/preview-runtime/src/`. Bite B kopplar adaptrarna
> till befintliga helpers i `apps/viewser/lib/`.

## Roll

Du är en Builder-agent som ska göra `localRuntime` och `stackblitzRuntime`
i `packages/preview-runtime/` faktiskt funktionella genom att delegera till
existerande logik i `apps/viewser/lib/local-preview-server.ts` resp.
`apps/viewser/lib/stackblitz-files.ts`. Inga nya feature-ytor, ingen
ny-arkitektur, inga UI-ändringar.

## Branch-regel (HÅRD)

- Arbeta på `jakob-be`. Verifiera vid start:
  - `git rev-parse --abbrev-ref HEAD` → `jakob-be`
  - `git fetch origin && git status` → `Your branch is up to date with 'origin/jakob-be'`
- Ändra inte `main`. Använd `main` bara som referens.
- **OFF-LIMITS för denna agent:** `apps/viewser/components/**`,
  `apps/viewser/app/**/*.tsx`, `apps/viewser/app/**/*.css`,
  `apps/viewser/public/**`. Det är Christophers lane per
  `governance/rules/branch-scope-ui-ux.md`. Om uppdraget kräver att röra
  någon av dessa: STOPPA och rapportera till operatören.

## Förutsättningar (läs först, i denna ordning)

1. `AGENTS.md`
2. `governance/rules/branch-scope-ui-ux.md` (off-limits-listan, scope-leak-procedur)
3. `governance/decisions/0028-runtime-ladder.md` (PreviewRuntime-abstraktion + runtime ladder)
4. `governance/decisions/0030-preview-provider-portability.md` (Vercel som adapter, inte beroende; Regel 1-3 är hårda gränser)
5. `packages/preview-runtime/README.md` (Bite-roadmap som denna prompt fortsätter)
6. `packages/preview-runtime/src/types.ts` (kontraktet)
7. `packages/preview-runtime/src/registry.ts` (env-mappning, `currentRuntime()`)
8. `packages/preview-runtime/src/adapters/{local,stackblitz,fly}.ts` (skelett som ska bli funktionella)
9. `apps/viewser/lib/local-preview-server.ts` (existerande LocalRuntime-implementation)
10. `apps/viewser/lib/stackblitz-files.ts` (existerande StackBlitzRuntime file-payload-byggare)
11. `apps/viewser/tsconfig.json` (för path-alias-beslut)
12. `governance/policies/naming-dictionary.v1.json` (sök efter `previewRuntime` — `PreviewRuntimeKind = stackblitz | local | fly` är låst)

## Mål

Adaptrarna ska delegera, inte duplicera. Konkret:

### 1. Etablera importväg från `apps/viewser/` → `packages/preview-runtime/src/`

Två val. Föredra **(a)**:

- **(a) tsconfig path-alias** i `apps/viewser/tsconfig.json`:
  - Lägg till `"@preview-runtime/*": ["../../packages/preview-runtime/src/*"]` i `paths`.
  - Utöka `include` med `"../../packages/preview-runtime/src/**/*.ts"`.
  - Verifiera med `npx tsc --noEmit` att Next.js bundler hittar filerna.
- **(b) npm-workspace** — endast om (a) inte fungerar med Next.js
  Turbopack. Kräver root `package.json` med `"workspaces": ["apps/*", "packages/*"]`
  + `packages/preview-runtime/package.json`. Större lyft, mer verifiering.
  STOPPA före du går vidare med (b) och be operatören bekräfta — det är ett
  arkitekturbeslut.

Inga andra alternativ utan operatör-OK.

### 2. Implementera `localRuntime`

I `packages/preview-runtime/src/adapters/local.ts`: ersätt
`unsupported`-stubsen med en wrapper som delegerar till
`apps/viewser/lib/local-preview-server.ts`. Mappa adapterns
`PreviewRuntimeConfig`-input till de signaturer som `local-preview-server.ts`
redan exponerar. Om en behövd export saknas — utöka exporterna i
`local-preview-server.ts` minimalt **utan att bryta existerande callsites**.
Konvertera resultatet till `PreviewResult`-shape (`status`,
`previewSession.{id,url,kind,createdAt}`, `logs`, `error`).

**Viktigt:** kopiera inte logik. Delegera. Om `local-preview-server.ts`
äger en mutex eller process-lifecycle ska adaptern *anropa* den, inte
återimplementera den.

### 3. Implementera `stackblitzRuntime`

Samma princip för `packages/preview-runtime/src/adapters/stackblitz.ts`:
delegera till `apps/viewser/lib/stackblitz-files.ts`. Returnera
`PreviewResult` där `previewSession` (eller motsvarande fält) bär
file-payload som `PreviewFile[]`. Adaptern stannar vid file-bygget —
själva `@stackblitz/sdk`-embedet sker i UI-lagret
(`apps/viewser/components/viewer-panel.tsx`, off-limits för dig). Om
`stackblitz-files.ts` exporterar shape som inte matchar `PreviewResult`,
gör konverteringen i adaptern, inte i UI-fileln.

### 4. `flyRuntime` förblir orörd

Den ska fortsätta returnera `unsupported` med befintlig text. ADR 0028 §3
+ ADR 0030 §"Vad ADR 0030 INTE beslutar" säger att Fly-implementation
kräver framtida ADR.

### 5. Smoke-test

Lägg till TS-test (eller Python-pytest om TS-runner saknas) som
verifierar:

- `currentRuntime()` returnerar `localRuntime` när `VIEWSER_PREVIEW_MODE=local-next`.
- `currentRuntime()` returnerar `stackblitzRuntime` när `VIEWSER_PREVIEW_MODE=stackblitz`.
- `localRuntime.isAvailable()` returnerar `true`.
- `localRuntime.start({...})` med fake/missing siteId ger `PreviewResult`
  med `status: "failed"` (inte `unsupported` — det är beviset på att
  delegering sker).

`apps/viewser/lib/localhost-guard.test.ts` använder `node:assert/strict`
+ `declare describe/it`-pattern. Matcha det om viewser inte har en aktiv
TS-runner. Alternativt: skriv en Python-test i `tests/test_preview_runtime_*.py`
som kör adapter-resolution genom subprocess till `node -e` eller liknande
— bara om TS-pattern inte räcker.

## Out of scope (rör inte)

- INTE `apps/viewser/components/viewer-panel.tsx` (Christophers lane → Bite C)
- INTE bygga `vercel-preview`-adapter (kräver v18 naming-dict-bump + egen ADR)
- INTE bygga `static-export`-adapter (samma)
- INTE byta env-namn (`VIEWSER_PREVIEW_MODE` står)
- INTE röra `scripts/build_site.py` eller `packages/generation/`
- INTE röra `apps/viewser/components/**`, `app/**/*.tsx`, `app/**/*.css`, `public/**`
- INTE lägga till nya ADR
- INTE lägga till nya canonical-namn till naming-dictionary
- INTE byta `PreviewRuntimeKind`-typunion
- INTE öppna PR mot `main` — pusha till `jakob-be` direkt (solo arbets-branch)

## Implementation-guidning

- `apps/viewser/lib/local-preview-server.ts:resolveGeneratedDir()` är
  redan canonical path-resolver. Använd den, skapa inte en ny.
- Om du behöver utöka `local-preview-server.ts` eller `stackblitz-files.ts`
  med nya exporter, behåll bakåtkompatibilitet — existerande callsites i
  `viewer-panel.tsx`, `next.config.ts`, `dev.mjs` ska fortsätta fungera
  utan ändring.
- Om en konvertering kräver `process.cwd()`, `'use client'`, eller annan
  Next.js-specifik directive — STOPPA. Det betyder att gränsen är fel
  och adaptern är på fel sida av Node/browser-skiljelinjen.
- Det här är ett bra ställe att lära av PR #85 (stängd unmerged) som
  tidigare gjorde liknande wiring i större scope. PR #85:s innehåll är
  delvis mergat via PR #88/#92/#97/#100/#101 — `dev.mjs` + `next.config.ts`
  + `local-preview-server.ts` har redan den `VIEWSER_PREVIEW_MODE`-grund
  som du behöver. Du behöver bara delegera, inte återskapa.

## Validering (alla MÅSTE vara gröna före push)

```powershell
cd apps/viewser
npx tsc --noEmit
cd ../..
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python -m ruff check .
python -m pytest tests/test_llm_golden_path_smoke.py tests/test_followup_versioning_regression.py tests/test_quality_gate.py -q
python scripts/focus_check.py
```

Plus din nya smoke-test om den är Python-baserad. Förvänta dig 0 TS-fel,
ruff säger "all checks passed", term-coverage OK, pytest minst 30+
passed, focus_check `Result: OK` eller "1 commit ahead within tolerance".

## Stop-villkor (stanna och rapportera till operatören)

- Path-alias (a) fungerar inte med Turbopack och du måste till (b) workspace.
- `local-preview-server.ts` eller `stackblitz-files.ts` har en signatur
  som kräver bredare ändring än rena export-tillägg.
- Cirkulär dependency mellan `packages/preview-runtime/` och `apps/viewser/lib/`.
- En adapter behöver `'use client'`-directive eller annan Next.js-direktiv
  i `packages/preview-runtime/`.
- Du upptäcker att Bite A:s typmodell (`PreviewRuntimeConfig`,
  `PreviewResult`) inte täcker faktiska behoven — Bite A skulle behöva
  reviewas innan Bite B kan slutföras.
- Du upptäcker att existerande viewer-panel.tsx-grenarna måste röras för
  att Bite B ska fungera (det är Bite C, kräver Christopher-koordinering).
- Test för `currentRuntime()` med `local-next`-env ger inte `localRuntime`.
  Det betyder env-mappningen i `registry.ts:normalizePreviewMode()` är fel.

## Acceptanskriterier

- `apps/viewser/` har fungerande `import { currentRuntime } from "@preview-runtime"`
  (eller motsvarande väg som path-alias-beslutet pekar mot).
- `localRuntime.start({siteId: ...})` delegerar till befintlig
  `startLocalPreview()` (eller motsvarande), inte en duplicate.
- `stackblitzRuntime.start({...})` returnerar `PreviewResult` med fungerande
  `files`/`previewSession`-shape.
- `flyRuntime` returnerar fortfarande `unsupported`.
- Existerande callsites i `local-preview-server.ts`, `stackblitz-files.ts`,
  `dev.mjs`, `viewer-panel.tsx`, `next.config.ts` fortsätter fungera utan
  signatur-ändring.
- Inga nya canonical-namn introduceras.
- Smoke-test som verifierar `resolveRuntime()` + `currentRuntime()` finns
  och passerar.
- Alla guards gröna.
- Bumpa raden för senast verifierad SHA i `docs/current-focus.md` +
  `docs/handoff.md` till nya HEAD i en sista steward-commit per Standard
  loop steg 8.

## Commit-stil

Föredra två commits:

1. `feat(preview-runtime): bite B — wire localRuntime + stackblitzRuntime adaptrar`
2. `test(preview-runtime): smoke for resolveRuntime + currentRuntime + adapter delegation`

Plus eventuell tredje:

3. `docs(steward): bump verified state to <SHA> post Bite B push`

Eller en enda om diff:en är liten. Body följer repo-konventionen
(engelska titel, svensk body, backtick-quoted identifiers, ADR-referens
till 0028 + 0030, lista validering-resultat). Push till `origin/jakob-be`
direkt — solo arbets-branch, ingen PR krävs.

## Branch-state efter du är klar

Rapportera till operatören (eller orchestrator-agent) med:

- Top-3 commits oneline.
- Vald importväg (path-alias eller workspace) + motivering.
- Eventuella signature-utvidgningar i `apps/viewser/lib/local-preview-server.ts`
  eller `stackblitz-files.ts` (lista exporterna som lades till).
- Pytest-summary (X passed).
- TS-typecheck-resultat (errors / clean).
- Eventuella stop-villkor som triggades och hur du löste dem.
- Bumpad SHA i `docs/current-focus.md`.

## Kontext för reviewer

Mitt arbete (Bite A) är i commit `bb6ab2e` på `jakob-be`. Reviewer-paketet
för det arbetet finns i samtalshistoriken där denna prompt skapades.
Reviewern (orchestrator-agent eller annan) ska verifiera att Bite B
endast wirear, inte expanderar scope, och att `bb6ab2e`:s typmodell
fortfarande är giltig efter Bite B.
