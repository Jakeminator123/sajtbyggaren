# Handoff – Sajtbyggaren

**Datum:** 2026-05-13
**Aktuell HEAD på `main`:** `872ae68` (efter B13b-merge `fda1464` + docs-bump). Kör `git log --oneline -1` för senaste SHA.
**Aktiv branch:** `main`. Inga feature-branches öppna.

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

Flöde: `git checkout -b feat/<spår>` → arbeta → `git push -u origin feat/<spår>` → öppna PR → invänta Bugbot + governance-CI → ev. fix-runda → squash-merge → städa branchen lokalt + remote.

### Varför inte alltid `main`?

Cursor Bugbot triggar bara på **pull requests** i denna repo-konfig. PR #19 (B13b route-emission) körde tre Bugbot-rundor och fångade tre riktiga buggar (print-order, hardcoded `/kontakt`, PR-description scope) som hade skeppats direkt på `main`. Mönstret "mainline-steward för tiny, PR för kod" är inte byråkrati – det är det som faktiskt har räddat tre buggar från att landa.

Vill du ha Bugbot på direkt-pushar till `main` också? Det måste konfigureras i Cursor-dashboarden (repo settings → Bugbot → triggers). Idag är "every push to a PR" + "draft-PR-review" aktivt; "every push to main" är inte påslaget. Säg till om du vill att jag dokumenterar den config-ändringen som en operatörsuppgift.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:

- `governance/` – JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- `backoffice/` + `backend.py` – Streamlit-administration (inte runtime).
- `packages/` + `apps/` – framtida runtime + kund-UI.

## Vad funkar idag (post-B13b merge, `fda1464`)

### Governance + guards

- ADR 0001–0018 + 15 policies + matchande schemas under `governance/schemas/`.
- Fem automatiska checks: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. GitHub Actions kör dem på push + PR. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift.
- **381 tester passerar**, 3 skipped (env-gated: `SAJTBYGGAREN_VERIFY_BUILD`, `SAJTBYGGAREN_E2E briefModel`, `SAJTBYGGAREN_E2E codegenModel`). 0 ruff findings.

### Phase 1 + 2 (Sprint 2A + 2B)

- `briefModel` via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- `planningModel` via shared `packages.generation.planning.produce_site_plan`. Både `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper.

### Phase 3 (Sprint 3A → 3C-lite + post-merge B13b)

- Real Quality Gate-checks (typecheck, route-scan, build-status, policy-compliance) i `packages/generation/quality_gate/`.
- Repair Pipeline med ensure-default-export-fix och sandwich-loop i `packages/generation/repair/`.
- Real `codegenModel` (scope: `marketing-base`) i `packages/generation/codegen/`. Truth-fields: `real` / `mock-llm-error` / `mock-no-key` / `deterministic-v1`.
- **B13b route-emission (PR #19, `fda1464`):** `scripts/build_site.py:write_pages` är scaffold-drivet. `ecommerce-lite` genererar `/produkter` (inte `/tjanster`), nav följer scaffolden, contact-CTA på `render_products` följer scaffold (`_pick_contact_route`).
- Vendor-only `commerce-base`-starter (PR #16, `ff3d512`) — inte aktiverad i mappningen än.

### Builder UX MVP

`apps/viewser/` har en `<RunDetailsPanel>` med fem sektioner (Build / Quality / Repair / Codegen / Models) som läser från `/api/runs/[runId]/artifacts`. `<RunHistory>` har status-färgning. PreviewRuntime / StackBlitzRuntime / FlyRuntime är parkerat som Sprint 4-5.

## Nästa konkreta uppgift

Se `docs/current-focus.md` → **"Next action"** för full 9-punkts-checklista. Kort version: B20 step 2 – flippa `SCAFFOLD_TO_STARTER["ecommerce-lite"]` från `"marketing-base"` till `"commerce-base"`. Förutsättningar är på plats. Egen feature-branch + PR.

## Operatörspreferenser (2026-05-13)

- **Språk:** alltid svenska. Riktiga svenska tecken (`å`, `ä`, `ö`). Se [`governance/rules/always-swedish.md`](../governance/rules/always-swedish.md).
- **Reply-style:** kort + koncist. Förklara dev-uttryck med korta parenteser första gången per konversation (operatören är inte utvecklare i grunden). Se [`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
- **Branch-städning:** ta bort feature-branches direkt efter merge, både lokalt och på origin. Behåll `backup-{1..4}` och `frontend/christopher-import` (PR #17, stängd men branchen lever).
- **Create-PR-knappen i Cursor:** användaren kan av misstag trycka den. Om branchen redan har en öppen PR: säg till och gör ingenting. GitHub tillåter inte två öppna PR:er från samma branch mot samma bas.

## Pre-push self-review checklist (lärt från PR #19)

Innan `git push` på en feature-branch:

1. `git diff origin/main..HEAD --stat` – jämför listan rad för rad mot PR-beskrivningens "What changed". Bugbot blockerar PR:er där en ändrad fil saknas i listan.
2. Sök efter samma sorts hardcoded-pattern som PR:n säger sig fixa. Klassiskt blindspot på nya filer (PR #19: vi fixade hardcoded `/tjanster` i existerande renderers men introducerade hardcoded `/kontakt` i den nya `render_products`).
3. Print-/logg-meddelanden i present tense ("Writing X") måste komma FÖRE handlingen, inte efter, så operatören ser vad som är i flygt vid crash.
4. För varje ny renderer/komponent som tar `dossier`: kontrollera om den länkar någonstans och om pathen ska komma från scaffolden (`_pick_*_route`) eller dossiern.
5. Uppdatera PR-beskrivningens "What changed" + "What did not change" varje gång du commitar — inte bara vid PR-öppnandet.

## Standard loop (för referens)

Hela rutinen står i [`docs/agent-handbook.md`](agent-handbook.md) under "Standard loop". Åtta steg, varav steg 7 (uppdatera `current-focus.md`) är obligatoriskt agentens ansvar – inte operatörens.

```text
0. Drift-check (python scripts/focus_check.py).
1. Implementation-agent på egen branch (eller main om mainline-steward).
2. Ro-review: Bugbot på PR, eller egen explore-subagent i RO-läge för main-push.
3. Operatör + extern reviewer beslutar.
4. Fix-agent (om Bugbot/reviewer hittade fynd).
5. Final sanity (python scripts/review_check.py).
6. Merge (squash) eller direkt push till main.
7. Bumpa SHA i current-focus.md + uppdatera Queue/Blocked.
8. Nästa etapp.
```
