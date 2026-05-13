# Handoff – Sajtbyggaren

**Datum:** 2026-05-13 (kvällssession, post-PR #20 + PR #21)
**Aktuell HEAD på `main`:** `0db29e6` (efter `.cursorignore`-tweak ovanpå B20-followup-lucide-close `b0bb6c3`). Kör `git log --oneline -1` för senaste SHA.
**Aktiv branch:** `main`. Inga feature-branches öppna. Inga öppna PRs.

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet. Läs den FÖRE `docs/current-focus.md` om du är helt ny på projektet; läs `current-focus.md` FÖRE den om du bara behöver veta nästa konkreta uppgift.

## Branch-policy: var jobbar agenten egentligen?

**`main` är hemmabasen.** Du står på `main` mellan uppgifter och pullar in från `origin/main` när du startar en session. Du LÄMNAR `main` bara när du faktiskt ska ändra kod under granskning.

Två lägen, båda definierade i [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md):

### Mainline-steward – direkt på `main`

För **tiny + safe** ändringar:

- Dokumentation (`docs/*.md`).
- Governance-regler (`governance/rules/*.md`) + rules_sync.
- `.gitignore`, `.cursorignore`, `.vscode/settings.json`, redaktionella editor-config.
- Standard loop steg 7 (bumpa `current-focus.md` Last verified-SHA efter merge).
- Andra agents städ-arbete som inte rör en pågående feature.

Flöde: `git pull --ff-only origin main` → ändra → `git commit` → `git push origin main`. Inga PR:er, ingen Bugbot.

### Feature-PR – via `feat/<spår>`-branch + PR

För allt som **kan introducera buggar**:

- `scripts/*.py` (builder, dev_generate, governance-validatorer, lint-tooling).
- `packages/generation/**` (codegen, quality_gate, repair, planning, brief, artifacts).
- `apps/viewser/**` (UI som operatörer ser).
- `governance/policies/*.json` + `governance/schemas/*.json` (kontrakt).
- `examples/*.project-input.json` när de driver tester eller fixtures.
- Tester som låser nytt beteende (även om bara test-filen ändras).
- `data/starters/<starter>/` (kräver dessutom ADR-referens i PR per `.cursor/BUGBOT.md`).
- `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER` (kräver ADR i SAMMA PR — Bugbot blockar annars; lärdom från PR #20).

Flöde: `git checkout -b feat/<spår>` → arbeta → `git push -u origin feat/<spår>` → öppna PR → invänta Bugbot + governance-CI → ev. fix-runda enligt `governance/rules/bugbot-pr-loop.md` → squash-merge → städa branchen lokalt + remote.

### Varför inte alltid `main`?

Cursor Bugbot triggar bara på **pull requests** i denna repo-konfig. PR #19 körde tre Bugbot-rundor (3 buggar fångade) och PR #20 körde en runda (2 fynd). Mönstret "mainline-steward för tiny, PR för kod" är inte byråkrati — det är det som faktiskt har räddat fem buggar från att landa.

Vill du ha Bugbot på direkt-pushar till `main` också? Det måste konfigureras i Cursor-dashboarden (repo settings → Bugbot → triggers). Idag är "every push to a PR" + "draft-PR-review" aktivt; "every push to main" är inte påslaget.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:

- `governance/` — JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- `backoffice/` + `backend.py` — Streamlit-administration (inte runtime).
- `packages/` + `apps/` — runtime + kund-UI.

## Vad funkar idag (post-PR #21 merge, `04fc2fa` + post-fixes till `0db29e6`)

### Governance + guards

- ADR 0001–0020 + 15 policies + matchande schemas under `governance/schemas/`.
- Fem automatiska checks: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. GitHub Actions kör dem på push + PR. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift.
- **381 tester passerar**, 3 skipped (env-gated: `SAJTBYGGAREN_VERIFY_BUILD`, `SAJTBYGGAREN_E2E briefModel`, `SAJTBYGGAREN_E2E codegenModel`). 0 ruff findings.

### Phase 1 + 2 (Sprint 2A + 2B)

- `briefModel` via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- `planningModel` via shared `packages.generation.planning.produce_site_plan`. Både `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper.

### Phase 3 (Sprint 3A → 3C-lite + B13b + B20)

- Real Quality Gate-checks (typecheck, route-scan, build-status, policy-compliance) i `packages/generation/quality_gate/`.
- Repair Pipeline med ensure-default-export-fix och sandwich-loop i `packages/generation/repair/`.
- Real `codegenModel` (scope: `marketing-base`) i `packages/generation/codegen/`. `_REAL_CODEGEN_STARTERS = {"marketing-base"}` (ADR 0017). Truth-fields: `real` / `mock-llm-error` / `mock-no-key` / `deterministic-v1`.
- **B13b route-emission (PR #19, `fda1464`):** `scripts/build_site.py:write_pages` är scaffold-drivet. `ecommerce-lite` genererar `/produkter` (inte `/tjanster`), nav följer scaffolden, contact-CTA på `render_products` följer scaffold (`_pick_contact_route`).
- **B20 step 2 (PR #20, `75c980b`, ADR 0019):** `SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Ecommerce-lite-fixturen `examples/atelje-bird.project-input.json` producerar `/produkter` via `source=deterministic-v1` codegen. Real codegenModel-scope förblir `marketing-base`-only tills separat sprint utvidgar via ADR ovanpå 0017.
- **B20-followup-lucide (PR #21, `04fc2fa`, ADR 0020):** `lucide-react` ^1.14.0 tillagd i `commerce-base/package.json` så `scripts/build_site.py:write_pages`s hardcodade lucide-imports inte längre ger `Module not found` vid full `npm run build`. Verifierat: `cd .generated/atelje-bird && npm install && npm run build` grön (11 statiska sidor inkl `/produkter` plus commerce-base:s egna dynamiska routes).

### Builder UX MVP

`apps/viewser/` har en `<RunDetailsPanel>` med fem sektioner (Build / Quality / Repair / Codegen / Models) som läser från `/api/runs/[runId]/artifacts`. `<RunHistory>` har status-färgning. PreviewRuntime / StackBlitzRuntime / FlyRuntime är parkerat som Sprint 4-5.

## Nästa konkreta uppgift

Se `docs/current-focus.md` → **"Next action"**. Kort version: ingen aktiv blocker. Operatör väljer från Queue:

1. **B13a arkitektur-flytt** — `scripts/build_site.py` produktlogik till `packages/generation/build/`. Egen sprint, kräver troligen egen ADR (rör mappgränser i `repo-boundaries.v1.json`). Destinationen pre-allokerad i `.gitignore` + `.cursorignore` (kommit `b4fe4a8`).
2. **`write_pages` icon-bibliotek-agnostisk refactor** — lyfter den arkitekturskuld som ADR 0020 explicit lämnade öppen. Förebygger att samma lucide-typen av starter-vs-codegen-konflikt uppstår igen för en framtida starter utan lucide.
3. **Prompt-till-sajt-loopen** — nästa fas i produktarbetet, inte direkt blockerad av något konkret B-ID.
4. **BO2/BO4 backoffice-skuld** — dataframes → grupperad + färgad trace-viewer + async/cancellation i `backoffice/views/playground.py`.

## Operatörspreferenser (2026-05-13)

- **Språk:** alltid svenska. Riktiga svenska tecken (`å`, `ä`, `ö`). Se [`governance/rules/always-swedish.md`](../governance/rules/always-swedish.md).
- **Reply-style:** kort + koncist. Förklara dev-uttryck med korta parenteser första gången per konversation (operatören är inte utvecklare i grunden). Se [`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
- **Branch-städning:** ta bort feature-branches direkt efter merge, både lokalt och på origin. Behåll `backup-{1..4}` och `frontend/christopher-import` (PR #17, stängd men branchen lever).
- **Create-PR-knappen i Cursor:** användaren kan av misstag trycka den. Om branchen redan har en öppen PR: säg till och gör ingenting. GitHub tillåter inte två öppna PR:er från samma branch mot samma bas.
- **PowerShell + git commit -m flerrads:** PowerShell saknar bash heredoc. Skriv message till `$env:TEMP\sb-commit-msg.txt` och `git commit -F`. Aldrig `.commit-msg.tmp` i repo-roten (race med `git add -A`). Detaljerat i `governance/rules/branch-discipline.md` "Multi-line commit-meddelanden på Windows/PowerShell".
- **Cursor IDE git-editor pipe error på Windows** är vanligt (`ENOENT \\\\.\\pipe\\vscode-git-...sock`). Fall tillbaka till `git commit -m` eller `-F` från shell direkt.

## Bugbot-loop på PR (kritisk lärdom från PR #20)

Hela rutinen står i [`governance/rules/bugbot-pr-loop.md`](../governance/rules/bugbot-pr-loop.md). Sammanfattning:

1. Efter `gh pr create`: verifiera att Bugbot är aktiverad (en check med `name == "Cursor Bugbot"` ELLER en review från `author.login == "cursor"`). Om aktiverad: skriv exakt strängen `kommer nu vänta i upp till högst 8 min på att bugbotten blir klar` till operatören.
2. Polla 60–90s × max 8 min. Stoppa så fort `Cursor Bugbot`-checken är `COMPLETED`.
3. **Tolka resultatet via 3 signaler — inte via Bugbots summary-body.** Bodyn säger "found N issues" från första körningen och uppdateras inte mellan commits. Använd istället: (a) check-conclusion, (b) GraphQL `reviewThreads.isResolved` för att räkna aktiva trådar, (c) övriga checks.
4. Grönt = check `SUCCESS` ELLER (`NEUTRAL` OCH 0 aktiva trådar) OCH alla övriga checks `SUCCESS` OCH `mergeStateStatus == "CLEAN"`. Grönt → `gh pr merge --squash --delete-branch` automatiskt + Standard loop steg 7.
5. Rött → fix-loop iteration N (max 10). Per iteration: läs aktiva trådar, minimal-fix, push, **markera trådar som resolved via GraphQL** så loopens nästa poll blir korrekt.
6. > 10 iterationer → posta `[NÖDLÄGE PR]`-kommentar och lämna åt operatör.

## Pre-push self-review checklist (lärt från PR #19 + PR #20)

Innan `git push` på en feature-branch:

1. `git diff origin/main..HEAD --stat` — jämför listan rad för rad mot PR-beskrivningens "What changed". Bugbot blockerar PR:er där en ändrad fil saknas i listan.
2. Sök efter samma sorts hardcoded-pattern som PR:n säger sig fixa. Klassiskt blindspot på nya filer (PR #19: vi fixade hardcoded `/tjanster` i existerande renderers men introducerade hardcoded `/kontakt` i den nya `render_products`).
3. Print-/logg-meddelanden i present tense ("Writing X") måste komma FÖRE handlingen, inte efter, så operatören ser vad som är i flygt vid crash.
4. För varje ny renderer/komponent som tar `dossier`: kontrollera om den länkar någonstans och om pathen ska komma från scaffolden (`_pick_*_route`) eller dossiern.
5. Uppdatera PR-beskrivningens "What changed" + "What did not change" varje gång du commitar — inte bara vid PR-öppnandet.
6. Om PR ändrar `SCAFFOLD_TO_STARTER` eller `data/starters/<starter>/`: skapa motsvarande ADR i SAMMA PR (lärdom från PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019; för starter-deps se PR #21:s ADR 0020).
7. Om PR har en informativ post-merge-followup som inte blockerar merge: lägg den under "Post-merge sanity needed" i PR-mallen, INTE under "Known risks / blockers" — Bugbot tolkar varje rad i blocker-sektionen som hård gate (lärdom från PR #20:s Bugbot-iteration 1).

## Standard loop (för referens)

Hela rutinen står i [`docs/agent-handbook.md`](agent-handbook.md) under "Standard loop". Åtta steg, varav steg 7 (uppdatera `current-focus.md`) är obligatoriskt agentens ansvar — inte operatörens.

```text
0. Drift-check (python scripts/focus_check.py).
1. Implementation-agent på egen branch (eller main om mainline-steward).
2. Ro-review: Bugbot på PR (följ governance/rules/bugbot-pr-loop.md), eller egen explore-subagent i RO-läge för main-push.
3. Operatör + extern reviewer beslutar.
4. Fix-agent (om Bugbot/reviewer hittade fynd).
5. Final sanity (python scripts/review_check.py).
6. Merge (squash) eller direkt push till main.
7. Bumpa SHA i current-focus.md + uppdatera Queue/Blocked + flytta stängda B-IDs i known-issues.md.
8. Nästa etapp.
```

## Sista commit-historiken (för snabb orientering)

```text
0db29e6 chore(cursorignore): ignore referens/ from Cursor indexing
b0bb6c3 docs: close B20-followup-lucide post-merge + bump focus to 04fc2fa (Standard loop step 7)
04fc2fa feat(commerce-base): add lucide-react dep to fix ecommerce-lite full build (#21)
e574cfa refactor(rules): bugbot-pr-loop reads resolved-state via GraphQL (lärdom från PR #20)
9486d73 docs: close B20 post-merge + bump focus to 75c980b (Standard loop step 7)
75c980b feat(planning): activate ecommerce-lite -> commerce-base mapping (B20 step 2) (#20)
bba8e36 feat(rules): add bugbot-pr-loop rule (8-min poll + 10-iter fix-loop + nödläge escalation)
af8b337 docs: refresh handoff for main-as-default policy + post-B13b state
872ae68 docs: close B13b post-merge + bump focus to fda1464 (Standard loop step 7)
fda1464 feat(builder): drive write_pages from scaffold routes.json (B13) (#19)
```
