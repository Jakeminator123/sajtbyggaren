# Handoff – Sajtbyggaren

**Datum:** 2026-05-14 (post-PR #23 + #22 + settings-sync + docs-sync)
**Aktuell repo-HEAD på `main`:** `d43bce2` (docs-sync efter settings-commit `e9093c0`, som aktiverade `linear` + `sanity` i `.cursor/settings.json`). Aktuell produkt-HEAD är `9944abb` (squash-merge PR #22 `feat(starters): add harmonized portfolio-base starter` ovanpå PR #23 `e1ad5ca` och follow-up prompt versions `2701b00`). Kör `git log --oneline -1` för senaste lokala SHA.
**Aktiv branch:** `main`. Standardflödet är `main` + numrerad `backup-N`, inte feature-PR-branch. `backup-9` finns lokalt från pre-PR-#23-läget; `backup-8` finns lokalt efter follow-up-sprinten; `backup-7` (från `fb11925`) ligger på origin som tidigare fallback.

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet. Läs den FÖRE `docs/current-focus.md` om du är helt ny på projektet; läs `current-focus.md` FÖRE den om du bara behöver veta nästa konkreta uppgift.
Färdiga startprompter för Scout/Builder/Steward finns i [`docs/agent-prompts.md`](agent-prompts.md).

## Branch-policy: var jobbar agenten egentligen?

**`main` är arbetsytan.** Du står på `main` före, under och efter sprinten om operatören inte uttryckligen säger något annat. Inför varje ny sprintrunda skapar agenten en numrerad backup-branch från ren/synkad `main`, men fortsätter jobba på `main`.

Detta är definierat i [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md):

### Sprintstart – backup först

1. Kör `python scripts/focus_check.py`.
2. Verifiera att branch är `main` och att den är synkad med `origin/main`.
3. Lista `backup-*` och välj högsta nummer + 1.
4. Skapa `git branch backup-N` från aktuell `main`.
5. Pusha backupen om operatören vill ha fjärrbackup: `git push origin backup-N`.
6. Stanna kvar på `main` och gör arbetet där.

Backup-branchen är bara fallback. Den är inte arbetsbranch och ska inte få PR.

### Tre agentroller

- **Scout-agent** är read-only: audit, plan, risker, RO-bugggranskning före push, nästa Builder-prompt.
- **Builder-agent** implementerar: skapar sprintens backup, jobbar på `main`, testar, rapporterar och pushar först efter gröna guards. Om Scout säger att push är OK och working tree är clean får Builder pusha utan ny manuell operatörs-OK.
- **Steward-agent** håller ordning: docs/current-focus, handoff, sanity och låg-risk governance på `main`. Efter Builder-push verifierar Steward origin/main-SHA, `git status`, `python scripts/focus_check.py`, om `origin/main` matchar lokal `main`, samt om docs behövde uppdateras.

### PR är undantag

PR skapas bara om operatören uttryckligen ber om PR/separat arbetsbranch. Annars används Scout-agentens RO-review + lokala guards före `git push origin main`.

Cursor Bugbot triggar i nuvarande repo-konfig främst på PR. Eftersom operatörspreferensen nu är `main` + backup används Bugbot inte som standardgate. För direkt-main-flödet är Scout-agenten pre-push-granskare. För större risker ska agenten stoppa, rapportera och låta operatör + extern reviewer besluta innan push.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:

- `governance/` — JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- `backoffice/` + `backend.py` — Streamlit-administration (inte runtime).
- `packages/` + `apps/` — runtime + kund-UI.

## Vad funkar idag (post-PR #22, repo-HEAD `d43bce2`)

### Governance + guards

- ADR 0001–0020 + 15 policies + matchande schemas under `governance/schemas/`.
- Fem automatiska checks: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. GitHub Actions kör dem på push + PR. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift.
- **3 nya source-lock-tester** lades till i audit-hotfixen (Zod 400, trim, `--`-separator). 0 ruff findings.

### Phase 1 + 2 (Sprint 2A + 2B)

- `briefModel` via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- `planningModel` via shared `packages.generation.planning.produce_site_plan`. Både `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper.

### Phase 3 (Sprint 3A → 3C-lite + B13b + B20)

- Real Quality Gate-checks (typecheck, route-scan, build-status, policy-compliance) i `packages/generation/quality_gate/`.
- Repair Pipeline med ensure-default-export-fix och sandwich-loop i `packages/generation/repair/`.
- Real `codegenModel` (scope: `marketing-base`) i `packages/generation/codegen/`. `_REAL_CODEGEN_STARTERS = {"marketing-base"}` (ADR 0017). Truth-fields: `real` / `mock-llm-error` / `mock-no-key` / `deterministic-v1`.
- **B13b route-emission (PR #19, `fda1464`):** `scripts/build_site.py:write_pages` är scaffold-drivet. `ecommerce-lite` genererar `/produkter` (inte `/tjanster`), nav följer scaffolden, contact-CTA på `render_products` följer scaffold (`_pick_contact_route`).
- **B20 step 2 (PR #20, `75c980b`, ADR 0019):** `SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Ecommerce-lite-fixturen `examples/atelje-bird.project-input.json` producerar `/produkter` via `source=deterministic-v1` codegen. Real codegenModel-scope förblir `marketing-base`-only tills separat sprint utvidgar via ADR ovanpå 0017.
- **B20-followup-lucide (PR #21, `04fc2fa`, ADR 0020):** `lucide-react` ^1.14.0 tillagd i `commerce-base/package.json` så `scripts/build_site.py:write_pages`s hardcodade lucide-imports inte längre ger `Module not found` vid full `npm run build`.

### Prompt-till-sajt MVP v1 + follow-up versions (kod-HEAD `2701b00`)

- **`/api/prompt`** tar fri prompt, kör `runPromptToProjectInput` (spawnar `scripts/prompt_to_project_input.py` med `--`-separator så dash-prefixade prompts inte fastnar i argparse), och triggar `runBuild` med dossier-path-override (whitelist via `ALLOWED_DOSSIER_ROOTS` mot `examples/` + `data/prompt-inputs/`).
- **PromptBuilder** är canonical promptyta på Viewser-home; legacy ChatPanel finns kvar som komponent men importeras inte. ProjectInputPicker är read-only-select (Build-knappen togs bort).
- **Payload-validering**: `z.string().trim().min(1).max(4000)` så whitespace-only payloads fångas vid API-gränsen. `ZodError` returneras som `400` med valideringsmeddelandet; bara genuina serverfel blir `500`.
- **Helper-skriptet** `scripts/prompt_to_project_input.py` använder briefModel + Site Brief och skriver `data/prompt-inputs/<siteId>.project-input.json` + sidecar `<siteId>.meta.json` med `projectId/version/originalPrompt/briefSource`. Brief-imports ligger på modulnivå så fallback-tester monkeypatchar lookup-namnen som `generate()` faktiskt använder.
- **Follow-up prompt versions** är landat: operatören kan fortsätta på befintlig prompt-input/run, behålla `projectId`, bumpa `version` och få ny build/run för samma sajtspår.
- **ViewerPanel** fallback-copy hänvisar nu till promptfältet, inte den borttagna Build-knappen.

### Backoffice trace/playground (PR #23, produkt-HEAD `e1ad5ca`)

- Engine-runs-vyn och playground-vyn använder en gemensam strukturerad trace-viewer i `backoffice/views/_trace.py` för `trace.ndjson`: halvskrivna rader hoppas över defensivt, events summeras, grupperas per fas och kan filtreras på fas/status/söktext.
- Playground-vyn kör `scripts/dev_generate.py` via kontrollerad `subprocess.Popen`-runner istället för svart-låde-`subprocess.run`, och visar status, elapsed time, exit code och loggutdrag under/efter körning.
- Backoffice trace/playground-posterna är stängda i `docs/known-issues.md`; kvar finns bara lågprioriterad cancellation-followup för riktig cancellation/background-jobb.

### Starter-katalog

- `data/starters/portfolio-base/` finns nu som harmoniserad starter via PR #22. Den är starter-underlag, inte aktiverad `SCAFFOLD_TO_STARTER`-mappning och inte real-codegen-scope.
- Befintliga aktiva starterflöden är oförändrade: `marketing-base` för real codegen-scope och `commerce-base` för ecommerce-lite deterministic-v1 enligt tidigare ADR-spår.

### Builder UX MVP

`apps/viewser/` har en `<RunDetailsPanel>` med fem sektioner (Build / Quality / Repair / Codegen / Models) som läser från `/api/runs/[runId]/artifacts`. `<RunHistory>` har status-färgning. PreviewRuntime / StackBlitzRuntime / FlyRuntime är parkerat som Sprint 4-5.

## Nästa konkreta uppgift

Se `docs/current-focus.md` → **"Next action"**. Kort version: ingen aktiv PR-blocker och inga öppna PRs. Nästa Builder-beslut är follow-up-semantiken i dev-driver/backoffice:

1. **Follow-up-semantik i `scripts/dev_generate.py` + Backoffice Playground** — `--mode followup` och Project ID exponeras, men planfasen skickar fortfarande `engine_mode="init"` och `project_id=None`. Antingen dölj/disable:a follow-up där tills kontraktet är riktigt, eller för `mode`/`project_id` hela vägen genom planfasen och lås med test.
2. **B13a arkitektur-flytt** — `scripts/build_site.py` produktlogik till `packages/generation/build/`. Egen sprint, kräver troligen egen ADR (rör mappgränser i `repo-boundaries.v1.json`). Destinationen pre-allokerad i `.gitignore` + `.cursorignore` (kommit `b4fe4a8`).
3. **`write_pages` icon-bibliotek-agnostisk refactor** — lyfter den arkitekturskuld som ADR 0020 explicit lämnade öppen. Förebygger att samma lucide-typen av starter-vs-codegen-konflikt uppstår igen för en framtida starter utan lucide.
4. **Cancellation-followup** — lågprioriterad separat sprint om operatören behöver avbryta redan startade playground-körningar.

PromptBuilder stage-timeout är inte längre listad som aktiv nice-to-have; Scout verifierade att cleanup redan finns.

PR #17 / `frontend/christopher-import` är reference only: återöppna inte PR #17,
starta inte `apps/web`, men behåll branchen som framtida design-/copy-referens.

## Operatörspreferenser (2026-05-13)

- **Språk:** alltid svenska. Riktiga svenska tecken (`å`, `ä`, `ö`). Se [`governance/rules/always-swedish.md`](../governance/rules/always-swedish.md).
- **Reply-style:** kort + koncist. Förklara dev-uttryck med korta parenteser första gången per konversation (operatören är inte utvecklare i grunden). Se [`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
- **Backup-branches:** inför varje sprintrunda skapas nästa `backup-N` från synkad `main`. Backupen är fallback och ska inte raderas utan uttryckligt beslut.
- **Create-PR-knappen i Cursor:** användaren kan av misstag trycka den. Standard är att inte öppna PR; fråga operatören om PR verkligen är avsikten.
- **PowerShell + git commit -m flerrads:** PowerShell saknar bash heredoc. Skriv message till `$env:TEMP\sb-commit-msg.txt` och `git commit -F`. Aldrig `.commit-msg.tmp` i repo-roten (race med `git add -A`). Detaljerat i `governance/rules/branch-discipline.md` "Multi-line commit-meddelanden på Windows/PowerShell".
- **Cursor IDE git-editor pipe error på Windows** är vanligt (`ENOENT \\\\.\\pipe\\vscode-git-...sock`). Fall tillbaka till `git commit -m` eller `-F` från shell direkt.

## Bugbot-loop vid PR-undantag

Standardflödet är inte PR, men om operatören uttryckligen väljer PR-flöde står hela rutinen i [`governance/rules/bugbot-pr-loop.md`](../governance/rules/bugbot-pr-loop.md). Sammanfattning:

1. Efter `gh pr create`: verifiera att Bugbot är aktiverad (en check med `name == "Cursor Bugbot"` ELLER en review från `author.login == "cursor"`). Om aktiverad: skriv exakt strängen `kommer nu vänta i upp till högst 8 min på att bugbotten blir klar` till operatören.
2. Polla 60–90s × max 8 min. Stoppa så fort `Cursor Bugbot`-checken är `COMPLETED`.
3. **Tolka resultatet via 3 signaler — inte via Bugbots summary-body.** Bodyn säger "found N issues" från första körningen och uppdateras inte mellan commits. Använd istället: (a) check-conclusion, (b) GraphQL `reviewThreads.isResolved` för att räkna aktiva trådar, (c) övriga checks.
4. Grönt = check `SUCCESS` ELLER (`NEUTRAL` OCH 0 aktiva trådar) OCH alla övriga checks `SUCCESS` OCH `mergeStateStatus == "CLEAN"`. Grönt → `gh pr merge --squash --delete-branch` automatiskt + Standard loop steg 8.
5. Rött → fix-loop iteration N (max 10). Per iteration: läs aktiva trådar, minimal-fix, push, **markera trådar som resolved via GraphQL** så loopens nästa poll blir korrekt.
6. > 10 iterationer → posta `[NÖDLÄGE PR]`-kommentar och lämna åt operatör.

## Pre-push self-review checklist

Innan `git push origin main`:

1. `git diff origin/main..HEAD --stat` — jämför listan rad för rad mot sprintens deklarerade scope.
2. Sök efter samma sorts hardcoded-pattern som sprinten säger sig fixa. Klassiskt blindspot på nya filer (PR #19: vi fixade hardcoded `/tjanster` i existerande renderers men introducerade hardcoded `/kontakt` i den nya `render_products`).
3. Print-/logg-meddelanden i present tense ("Writing X") måste komma FÖRE handlingen, inte efter, så operatören ser vad som är i flygt vid crash.
4. För varje ny renderer/komponent som tar `dossier`: kontrollera om den länkar någonstans och om pathen ska komma från scaffolden (`_pick_*_route`) eller dossiern.
5. Om sprinten ändrar `SCAFFOLD_TO_STARTER` eller `data/starters/<starter>/`: skapa motsvarande ADR i samma ändringsrunda (lärdom från PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019; för starter-deps se PR #21:s ADR 0020).
6. Om sprinten har en informativ followup som inte blockerar push: lägg den i `docs/current-focus.md`, inte som blocker.

## Standard loop (för referens)

Hela rutinen står i [`docs/agent-handbook.md`](agent-handbook.md) under "Standard loop". Tio steg, varav steg 8 (Steward post-push-verifierar och uppdaterar `current-focus.md`/`handoff.md` vid faktisk fokusförändring) är obligatoriskt agentens ansvar — inte operatörens.

```text
0. Drift-check (python scripts/focus_check.py).
1. Scout-agent vid behov.
2. Skapa nästa backup-N från synkad main.
3. Builder/Steward jobbar på main.
4. Scout-agent gör RO-review före push.
5. Operatör + extern reviewer beslutar om Scout inte redan gett push-OK.
6. Final sanity (python scripts/review_check.py).
7. Commit + push till main.
8. Steward verifierar pushed SHA, git status, focus_check, origin/main == local main, och docs-beslut. Uppdatera current-focus/handoff när HEAD, active sprint, next action/queue/blocked, agentflöde, branchflöde, grindmode, rollansvar, risk/blocker/nice-to-have eller extern PR/Grind-agent ändrar nästa agents arbete.
9. Nästa etapp.
```

## Sista commit-historiken (för snabb orientering)

```text
d43bce2 docs: sync handoff after settings commit
e9093c0 Liten settings.json bara som committades
9944abb feat(starters): add harmonized portfolio-base starter
e1ad5ca feat(backoffice): improve trace viewer and playground logs
2701b00 feat(viewser): add follow-up prompt versions
006be38 docs(workflow): formalize steward post-push verification
c3dcc14 docs: correct verified HEAD to 2f0af68 in focus + handoff
2f0af68 docs: bump focus + handoff to e421a00 post-audit-hotfix-sprint
e421a00 chore(check_term_coverage): allowlist ZodError TS symbol
c039ebd fix(viewer-panel): refresh stale fallback copy after legacy chat panel removal
e067006 fix(prompt-runner): pass -- to argparse so dashed prompts spawn cleanly
1033bf6 fix(prompt-route): return 400 on Zod errors and trim whitespace at API edge
cb54ca9 docs(agent-prompts): expand role catalog with parallel-agent rules
fe56344 fix(prompt-helper): hoist brief imports to module level for monkeypatching
fb11925 docs(focus): record Viewser prompt surface cleanup
fd67fbd refactor(viewser): remove legacy chat panel from home
ea4b165 fix(viewser): isolate StackBlitz preview mount
0a060e1 docs(focus): bump Last verified after prompt fallback hotfix
c6e2f1d fix(viewser): fall back when prompt brief extraction raises
7eea2f0 docs(focus): bump Last verified to 4d5b4de + queue post-prompt-till-sajt-mvp-v1
4d5b4de feat(viewser): prompt-till-sajt MVP v1
afaa8a8 docs(workflow): formalize progress estimate + scout model level
504befc docs(workflow): move agent prompts into docs
2aafa41 docs(workflow): formalize main backup agent flow
```
