# Handoff – Sajtbyggaren

**Datum:** 2026-05-19 (post-keramik-/e-handel-pass: `bfcad8d` ovanpå `923f680`/`6e5c33c`/`d1fee90`). Riktad Builder-runda stängde **B101** (hero-CTA shop-variant → /produkter via ny `_hero_cta_target_path`-helper), **B102** (`/produkter`-bottom-CTA shop-ton via ny `_commerce_bottom_cta_label`-helper med whitelist; länken mot kontakt-routen behålls eftersom builder MVP saknar checkout) och **B128 (Hög, ny + stängd same-day)** (planner-imperativ-läcka till /om-oss — `_customer_safe_planner_note` släppte igenom svenska/engelska build-imperativ i `notesForPlanner` ("Bygg en liten e-handel på svenska för försäljning av keramik med fokus på köpkonvertering."); ny `_starts_with_planner_imperative()`-guard + utökad `_PLANNER_NOTE_BLOCKLIST` med operator-tokens). Composer-2.5 read-only review hittade en B128 bypass där ledande icke-bokstavsprefix (`-Bygg ...`, `**Bygg ...**`, `1. Bygg ...`) slipped past — hardening `bfcad8d` strippar en run av ledande non-letter-chars före token-match så markdown/list/numeral-wrappade imperativ blockeras identiskt med rena. Separat dev-tooling-commit `6e5c33c` lägger opt-in `-Https`-flag i `scripts/dev-viewser.ps1` så Viewser kan starta på `https://localhost:3000` (StackBlitz embed-konsol kräver https://-origins). Variant-spåret `feat/eight-scaffold-variants` (commit `4cd1058`, åtta gpt-5.4-genererade scaffold-varianter) finns kvar på origin som separat feature-branch och rörs inte i detta pass — coach-direktiv: ingen variant-promotion under Steward eller Scout, separat sprint/PR krävs. Föregående pass (B121 discovery-integration sealed via PR #34–#37, merge `e3fa67b`): PR #31 `feat(viewser): integrate christopher-ui discovery and asset workflow` mergades via fast-forward — merge-commit `3f4543d`, integrationscommit `0510146`. Den lyfte in hela discovery wizard, asset upload pipeline, URL-scrape, SiteHeader/ConsoleDrawer, shadcn-primitives, schema-fält för brand/gallery och naming-dictionary v15 → v16. Bugsweep i tre rundor med totalt 13 commits direkt på main: `d63fab3` (BuildProgressCard `elapsedSec`-reset), `61da065` (`--discovery` + `--followup-site-id` rejection), `d06e628` (pyright optional-narrowing cleanup), `cd03897` (B113 SSRF redirect-validation + 6 regressionstester), `fe9748e` (B114 early `Content-Length`-guard i `/api/upload-asset`), `07f9cbb` (docs-bump runda 1), `6772a14` (B117 SVG-XSS via CSP sandbox + nosniff på `/api/asset-preview`), `df24488` (B118 scrape-runner SIGKILL-fallback), `0361121` (docs-bump runda 2), `c7049b3` (operatör-direktcommit, `package-lock.json`-städning från postcss-override `^8.5.10` i `apps/viewser/package.json` som tystar npm audit GHSA-qx2v-qp2m-jg93 — Vercels eps1lon säger explicit att det är false positive eftersom postcss bara körs vid build-tid och inte på untrusted CSS, men 0 vulnerabilities är värt 3 rader JSON), `5f23d13` (B123 cross-origin isolation headers — `Cross-Origin-Embedder-Policy: credentialless` + `Cross-Origin-Opener-Policy: same-origin` i `apps/viewser/next.config.ts` + 4 source-locks i `tests/test_viewser_isolation_headers.py`; tog bort gammal felformulerad negativ lock i `tests/test_viewser_files.py:test_viewser_does_not_set_global_cross_origin_isolation_headers` från `98e8364`), `e325c67` (docs B123-registrering), `5d05e0d` (B124 iframe credentialless-attribut — `document.createElement`-patch runt `sdk.embedProject(...)` i `apps/viewser/components/viewer-panel.tsx` så iframen får `setAttribute("credentialless", "")` innan src-fetch + 3 nya source-locks; även `DevTools` + `ElementCreationOptions` tillagda i `scripts/check_term_coverage.py:COMMON_WORDS`), `60515c6` (docs B124-registrering). Ovanpå `60515c6` cherrypickades sex commits från stängda PR #32 `Backoffice kontrollplan mvp` (`cursor/backoffice-kontrollplan-mvp-62aa`, skapad från `ca59529` innan PR #31-mergen så three-way merge hade haft trädets-delta-risk trots `mergeStateStatus=CLEAN` — cherry-pick valdes som säkrare väg, christopher-UI bevarades intakt): `3338d79` `fix(backoffice): normalize compatible dossier graph edges`, `b636450` `feat(backoffice): add read-only impact preview`, `c22bc1d` `feat(backoffice): add selection profile editor`, `2065a33` `feat(backoffice): improve variant candidate review`, `855a605` `fix(backoffice): use atomic model role writes`, `00103e3` `feat(backoffice): add soft dossier candidate generator`. Tillsammans lyfter de Backoffice till en kontrollplan: ny `Kontrollplan`-vy med dynamisk graf över Starters/Scaffolds/Variants/Dossiers/Model Roles + Doctor-fynd + konsekvensvy som klassificerar `riskLevel`/`runtimeEffect` per nod, ny `Selection Profiles`-vy med signal-coverage-fynd och atomic edit-toggle, refaktorerad `Variant Candidates`-vy med field-level diff + similarity-table mot canonical variants, ny `Dossier Candidates`-vy som driver `scripts/generate_dossier_candidate.py` (mirror av `generate_variant_candidate.py`: pydantic structured output via dossierModel-rollen + mock-fallback), och gemensam `backoffice/io.py` med `atomic_write_text`/`atomic_write_json` (temp + `os.fsync` + `os.replace`) som ersätter lokala helpers i `views/governance.py` + `views/llm_engine.py`. PR #32 stängdes (inte mergades) och `cursor/backoffice-kontrollplan-mvp-62aa` raderades från origin. Samtidigt rensades `frontend/christopher-import` (PR #17 CLOSED, ersattes av PR #31 från annan branch). Denna handoff-bumpcommit kommer ovanpå `0fe353f` (B126/B127-stängning). Sex nya öppna fynd registrerade över de tre review-rundorna: B115 (binär-dubbletter `/public/` vs `apps/viewser/public/`, ~3.4 MB), B116 (`BUILD_TIMEOUT_MS` 10 min globalt serialiserad), B119 (kontaktdata via alfabetisk sortering ger fel-men-plausibel-info), B120 (adress-till-stad-regex för snäv), B121 (medel arkitekturskuld — discovery-sanning splittrad i fyra lager utan explicit konfliktlösning), B122 (UI thinking→building via `setTimeout(1500)` istället för backend-signal). PR #32-cherrypicken är feature work — inga B-IDs öppnade eller stängda. B110/B111 från föregående pass kvarstår oförändrade. **B59 (StackBlitz embed parkerad efter 2026-05-15 header-experiment) är förmodligen löst i B123/B124 för Chromium-browsers** men kvar att operatörverifiera end-to-end med en grön preview innan den stängs formellt. **B125 (Hög, produktblocker innan launch) registrerad** efter operatörsdiskussion 2026-05-18: embedded StackBlitz/WebContainer-preview funkar bara i Chromium (Chrome 110+, Edge, Brave, Vivaldi) — Safari (inkl. iPhone) och Firefox kan inte ladda embeddet. ~25-35% av svenska SMB-slutkunder behöver server-byggd fallback för preview-fliken. Slutpublicerade kund-sajter är vanlig Next.js och funkar i alla browsers. Browser-support-kravet dokumenterat i README.md "Browser-stöd för preview-läge" och `docs/product-operating-context.md` "Runtime och preview". Fyra fallback-kandidater listade i B125 — beslut ska landa i ny ADR innan implementation. Aktuellt bug-scope: **25 aktiva, 0 misplaced, 5 unknown, 91 stängda** (B101 + B102 + B128 stängda i `d1fee90` + `bfcad8d`; B121 stängd i `e3fa67b`; B126 + B127 stängda i `0fe353f`; **B129 ny** — `_DEFAULT_VARIANT_BY_SCAFFOLD` hardcoded i `plan.py` istället för governance, registrerad i PR #38 post-merge-triage). **Direkt nästa uppgift:** **Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning via det faktiska overlayflödet (4-6 case inkl. keramik som verifierar B101/B102/B128 live, tjänsteföretag med adress, scrape-case, sköldpaddssoppa-conflict, "2 sidor"-case och follow-up). Se `docs/current-focus.md` → "Next action". B123/B124-end-to-end-verifikation (Chromium-browser + `npm run dev` i `apps/viewser/`) och nya backoffice-vyerna (Kontrollplan, Selection Profiles, Variant Candidates, Dossier Candidates via `streamlit run backoffice.py --server.headless true`) kan operatören köra när det passar — det är inte längre prerequisite för nästa sprint. **Därefter:** ny ADR för B125-fallback-väg (server-byggd statisk preview vs lokal `next dev`-park vs "Öppna i StackBlitz"-fallback vs Vercel preview-deployments) + Re-Verifierings-Scout 5 med fyra demo-prompter.)
**Aktuell repo-HEAD på `main`:** `9d7c4ba` (`chore(gitignore): ignore embedding index cache`, 2026-05-19, cherry-picked från övergiven branch `cursor/embedding-index-livscykel-3065`, 1 rad till `.gitignore`) ovanpå `9176f5e` (`docs(steward): bump for PR #38 merge (48a6a22) + register B129`) ovanpå merge-commit `48a6a22` för PR #38. Samtidig branch-cleanup pushad: raderade `origin/cursor/embedding-index-livscykel-3065` (chore-fix räddad), `origin/christopher-ui` (taggen `archive/christopher-ui-2026-05-18` säkrar), `origin/feat/eight-scaffold-variants` (PR #38 mergad, inga unika commits kvar), + lokal `feat/eight-scaffold-variants`. Origin-branches efter städ: `main` + 14 backup-branches (oförändrade). Föregående **Aktuell repo-HEAD på `main`:** `48a6a22` (`Merge pull request #38 from Jakeminator123/feat/eight-scaffold-variants`, 2026-05-19) ovanpå `0511299` (`fix(tests): align variant context test with promoted variants`) + `4cd1058` (`feat(variants): add eight gpt-5.4 scaffold variants for planning`) — PR #38 mergad via operatör-OK trots coach-direktiv 2026-05-19 ("ingen variant-promotion under Steward/Scout"); 8 nya canonical Scaffold Variants (4× `local-service-business`, 4× `ecommerce-lite`) + 8 mirrors under `data/variant-candidates/<scaffold>/` + `_DEFAULT_VARIANT_BY_SCAFFOLD`-guard i `packages/generation/planning/plan.py:_pick_variant` som garanterar att `nordic-trust`/`clean-store` förblir defaults (de nya variants är dead code i prod-flödet tills variant-selection-logik kommer i dedikerad sprint). **B129 öppen** för teknisk skuld (hardcoded mapping i kod istället för governance). Merge-commit ligger ovanpå `99ec56d` (`docs(steward): mikrobump current-focus + handoff for cd720aa + park PR #38`), `cd720aa` (`chore(gitignore): ignore local scout artifacts and certificates`), `6d66c0e` (`docs(steward): bump current-focus + handoff after keramik-/e-handel-pass`) och `bfcad8d` (`fix(builder): harden B128 imperative guard against leading non-letter prefix`) ovanpå `923f680` (docs B101/B102/B128 stängningar), `6e5c33c` (dev-viewser `-Https`-flag), `d1fee90` (Builder-pass keramik/e-handel), `2ffe065` (chore-ignore övrigt/), `76f6888` (docs B121-stängning) och `e3fa67b` (merge PR #37 B121 PR D). **HEADS-UP TILL PÅGÅENDE VIEWSER-OVERLAY-E2E-SCOUT**: Scout-rapport `docs/reports/viewser-overlay-e2e-scout-2026-05-19.md` har låst `HEAD-SHA vid scout-start: 99ec56d`. Faktiskt main är nu `48a6a22` efter PR #38-merge. Scout-agenten bör notifieras för att antingen uppdatera HEAD-SHA-raden + fortsätta (de nya variants aktiveras inte i prod via `_DEFAULT_VARIANT_BY_SCAFFOLD`-guarden så Scout-observationerna är fortfarande representativa) eller stoppa och omstart vid `48a6a22`. Operatören ska ta beslutet. **Nästa spår: Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning via overlayflödet, inte mer CLI-discovery-plumbing. Kör `git log --oneline -1` eller `python scripts/focus_check.py` för faktisk HEAD-SHA. `0fe353f` stängde B126 (dossier-graf-nyckel-mismatch — `_compatible_dossier_edges` byggde `dossier:{id}` medan noder var registrerade som `{class}-dossier:{id}`; impact-vyn blev blind för scaffold→dossier-spåret) och B127 (Doctor-villkor inverterat — `run_health_checks` varnade på `status == "implemented"` med tom details-sträng och tystnade på riktiga `incomplete`/`placeholder`-scaffolds). Båda fynden kom från extern review mot PR #32-cherrypicken (`3338d79` + `b636450`) och låses av två nya regressionstester i `tests/test_backoffice_asset_graph.py`. Guards gröna efter `0fe353f`: ruff 0 findings, governance 16 policies OK, rules_sync --check OK, term-coverage strict OK, **pytest 701 passed, 3 skipped E2E** (+2 nya regressionstester). Föregående relevanta commits i kronologisk ordning: `eb1a4ec` (B125 browser-support-fallback-registrering), `00103e3` (soft dossier candidate generator), `855a605` (atomic model role writes), `2065a33` (variant candidate review), `c22bc1d` (selection profile editor), `b636450` (impact preview), `3338d79` (compatible dossier edges normalised), `60515c6` (docs B124-bump), `5d05e0d` (B124 fix), `e325c67` (docs B123-bump), `5f23d13` (B123 fix), `c7049b3` (operatör postcss-cleanup), `0361121` (docs-bump runda 2), `df24488` (B118 fix), `6772a14` (B117 fix), `07f9cbb` (docs-bump runda 1), `fe9748e` (B114 fix), `cd03897` (B113 fix), `d06e628` (pyright cleanup), `61da065` (--discovery rejection), `d63fab3` (BuildProgressCard fix), `3f4543d` (PR #31 merge), `0510146` (PR #31 integration), `ca59529` (handoff-close docs-bump), `e67cd90` (handoff-skriv), `9bf3893` (B112-fynd-logg), `adde45c` (B112-fix), `b3800ca` (Steward focus-bump efter B109), `fa277a1` (B109-fix), `7742d39` (Steward bug-scope cleanup), `1c68035` (B108-fix), `860e553` (Backoffice control-plane).
**Aktiv branch:** `main`. `backup-pre-christopher-ui-merge` är pushad till origin som extra säkerhet före PR #31-mergen (pekar på `ca59529`); kan städas separat när ångerläget inte längre behövs. Taggen `archive/christopher-ui-2026-05-18` pekar på `4a16528` (christopher-ui:s HEAD) så hela branchen kan återställas. `origin/christopher-ui` är raderad. `cursor/backoffice-kontrollplan-mvp-62aa` (PR #32 source) och `frontend/christopher-import` (PR #17 CLOSED) raderades från origin under PR #32-passet. Kvar och flaggad för operatör-OK innan radering: `feat/demo-baseline-fix-1b-bug-sweep` (alternativ-väg till PR #28 som istället mergades från `cursor/demo-baseline-buggsvep-44a5`). `backup-26-VIKTIG`, `backup-27`, `backup-28`, `backup-29` plus äldre `backup-11..backup-25-VIKTIG` finns kvar på origin från tidigare pass och rörs inte utan instruktion. Lokal kvar: `feature/backoffice-discovery-control` (PR #36 source, mergad — kan städas vid separat OK). `feature/discovery-frontend-alignment` (PR #35 source) finns kvar på origin men inte lokalt. Inget nytt backup-N skapat för denna docs-bump.
**Stash-läge:** `git stash list` är **tom**.

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet. Läs den FÖRE `docs/current-focus.md` om du är helt ny på projektet; läs `current-focus.md` FÖRE den om du bara behöver veta nästa konkreta uppgift.
Färdiga startprompter för Scout/Builder/Steward finns i [`docs/agent-prompts.md`](agent-prompts.md). För längre fleragentpass används [`docs/orchestrator-playbook.md`](orchestrator-playbook.md); den samordnar befintliga roller och skapar inte en fjärde fast roll.

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
- `backoffice/` + `backoffice.py` — Streamlit-administration (inte runtime).
- `packages/` + `apps/` — runtime + kund-UI.

## Vad funkar idag (post cleanup/prune-sprint, kod-baseline `2acdeca`)

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
- **B45 contact-route propagation (`6daee58`):** layout, home, services och products får sina kontakt-CTA:er via scaffoldens contact-route (`_pick_contact_route`/`contact_path`). En scaffold som flyttar contact-id till `/kontakta-oss` får därmed nav och CTA:er i synk.
- **B20 step 2 (PR #20, `75c980b`, ADR 0019):** `SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Ecommerce-lite-fixturen `examples/atelje-bird.project-input.json` producerar `/produkter` via `source=deterministic-v1` codegen. Real codegenModel-scope förblir `marketing-base`-only tills separat sprint utvidgar via ADR ovanpå 0017.
- **B20-followup-lucide (PR #21, `04fc2fa`, ADR 0020):** `lucide-react` ^1.14.0 tillagd i `commerce-base/package.json` så `scripts/build_site.py:write_pages`s hardcodade lucide-imports inte längre ger `Module not found` vid full `npm run build`.

### Prompt-till-sajt MVP v1 + follow-up versions + audit-fix (kod-HEAD `2701b00`, audit-fix landar 2026-05-14, PR #27 versionerade snapshots landar 2026-05-15)

- **`/api/prompt`** tar fri prompt, kör `runPromptToProjectInput` (spawnar `scripts/prompt_to_project_input.py` med `--`-separator så dash-prefixade prompts inte fastnar i argparse), och triggar `runBuild` med dossier-path-override (whitelist via `ALLOWED_DOSSIER_ROOTS` mot `examples/` + `data/prompt-inputs/`). Response-payloaden inkluderar nu `buildStatus` (B44) så klienten kan klassificera ok/degraded/failed istället för att tolka varje returnerad `runId` som lyckad build.
- **PromptBuilder** är enda promptytan på Viewser-home (legacy `ChatPanel` är raderad i B46-fixen). ProjectInputPicker är read-only-select (Build-knappen togs bort). Stage-indikatorn renderar tre distinkta paneler (success/degraded/failed) baserat på `classifyBuildStatus(buildStatus)`; `app/page.tsx` skickar `PromptBuildOutcome` vidare till `headerStatusForOutcome` så headern aldrig säger "Build klar via prompt:" för en degraderad eller failed run.
- **Dev-driver follow-up-semantik** är nu trådad: `scripts/dev_generate.py --mode followup --project-id <id>` skriver både `input.json` och `generation-package.json` som follow-up med samma `projectId`. Backoffice Playground skickar `--project-id` + `SAJTBYGGAREN_MODE=followup` till subprocessen och har regressionstest.
- **Payload-validering**: `z.string().trim().min(1).max(4000)` så whitespace-only payloads fångas vid API-gränsen. `ZodError` returneras som `400` med valideringsmeddelandet; bara genuina serverfel blir `500`.
- **Helper-skriptet** `scripts/prompt_to_project_input.py` använder briefModel + Site Brief och skriver `data/prompt-inputs/<siteId>.project-input.json` + sidecar `<siteId>.meta.json` med `projectId/version/originalPrompt/briefSource`. Brief-imports ligger på modulnivå så fallback-tester monkeypatchar lookup-namnen som `generate()` faktiskt använder.
- **Follow-up prompt versions** är landat: operatören kan fortsätta på befintlig prompt-input/run, behålla `projectId`, bumpa `version` och få ny build/run för samma sajtspår.
- **PR #27 follow-up versions v2** (mergad `e057fbd`): `scripts/prompt_to_project_input.py` skriver immutable `<siteId>.vN.project-input.json` + `<siteId>.vN.meta.json`-snapshots i `data/prompt-inputs/`, behåller current pointer-filerna, bevarar `projectId`/`originalPrompt`, skriver `followUpPrompt`, och merger follow-up-prompts konservativt på existerande Project Input. `scripts/build_site.py` läser sidecar-meta intill dossier-pathen och trådar `mode`/`projectId`/`version`/`originalPrompt`/`followUpPrompt` in i `input.json`/`generation-package.json`/`build-result.json`. `apps/viewser/lib/runs.ts` läser per-run-meta från `build-result.json` -> `input.json` -> mutable sidecar legacy-fallback (RunHistory är stabil per `projectId` + `version` även när nya follow-ups landar). `apps/viewser/lib/project-inputs.ts` filtrerar `.vN.project-input.json`-snapshots från ProjectInputPicker. `apps/viewser/lib/prompt-runner.ts` + `lib/build-runner.ts` föredrar repo-roten `.venv` Python när den finns och cleanar prompt-/build-mutex via `try/finally`. PR #27 rörde inte StackBlitz-fronten (`apps/viewser/lib/stackblitz-files.ts`, `components/viewer-panel.tsx`, `next.config.ts`, `tests/test_viewser_files.py`).
- **ViewerPanel** fallback-copy hänvisar nu till promptfältet, inte den borttagna Build-knappen.

### Backoffice trace/playground (PR #23, produkt-HEAD `e1ad5ca`)

- Engine-runs-vyn och playground-vyn använder en gemensam strukturerad trace-viewer i `backoffice/views/_trace.py` för `trace.ndjson`: halvskrivna rader hoppas över defensivt, events summeras, grupperas per fas och kan filtreras på fas/status/söktext.
- Playground-vyn kör `scripts/dev_generate.py` via kontrollerad `subprocess.Popen`-runner istället för svart-låde-`subprocess.run`, och visar status, elapsed time, exit code och loggutdrag under/efter körning.
- Backoffice trace/playground-posterna är stängda i `docs/known-issues.md`; kvar finns bara lågprioriterad cancellation-followup för riktig cancellation/background-jobb.

### Starter-katalog

- `data/starters/portfolio-base/` (PR #22) och `data/starters/docs-base/` (PR #24) finns nu som harmoniserade starters. Båda är starter-underlag, inte aktiverade i `SCAFFOLD_TO_STARTER`-mappning och inte i real-codegen-scope.
- `docs-base` (Nextra 4.6.1 + Pagefind + MDX): sidomenyn i `src/app/layout.tsx` är manuellt underhållen — scaffold-injektion av nya MDX måste också uppdatera `<aside>`-blocket. Detta är dokumenterat ärligt i `authoring.mdx`/`index.mdx`/starter-README och spårat som `B49` i `known-issues.md` (page-map-driven sidebar krävs innan runtime-aktivering).
- Befintliga aktiva starterflöden är oförändrade i routing/codegen: `marketing-base` för real codegen-scope och `commerce-base` för ecommerce-lite deterministic-v1 enligt tidigare ADR-spår. Dependency-baslinjen är däremot hårdnad i `1c68035`: båda ligger på `next@16.2.6`, `eslint-config-next@16.2.6`, `postcss@^8.5.10` och `overrides.next.postcss=8.5.10`; `copy_starter()` tvingar om-installation när dessa package-inputs ändras.

### Builder UX MVP

`apps/viewser/` har en `<RunDetailsPanel>` med fem sektioner (Build / Quality / Repair / Codegen / Models) som läser från `/api/runs/[runId]/artifacts`. Build-sektionen visar `generatedFilesDir`, `devPreviewDir`, `npmSteps` och eventuella `logExcerpt` från failed npm-steg så transient build-mismatch kan felsökas från artefakten. `<RunHistory>` har status-färgning. PreviewRuntime / StackBlitzRuntime / FlyRuntime är parkerat som Sprint 4-5.

## Vad är parkerat

- **B59 - StackBlitz `template:"node"`/WebContainer-preview** är parkerat
  efter empirisk header-utvärdering 2026-05-15: inga COOP/COEP-headers
  blockerar iframe-load, `require-corp` ger VM-handshake-timeout,
  `credentialless` får iframe att ladda men StackBlitz `sign_in`-check
  faller. Header-experimentet committades **inte**. Nästa arkitekturbeslut
  bör vara byte till lokal `next dev`-process som same-origin iframe på
  `localhost:NNNN`, eller static StackBlitz-template - inte mer
  header-toggling. Tills dess fungerar Run History + Run Details för
  diagnostik och lokal `npm run build` på den genererade siten som
  verifikation. Rör inte `apps/viewser/lib/stackblitz-files.ts`,
  `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts`
  eller `tests/test_viewser_files.py` utan separat sprintbeslut.

## Nästa konkreta uppgift

Se `docs/current-focus.md` → **"Next action"**. Kort version: keramik-/e-handel-passet är stängt (`bfcad8d`: B101 + B102 + B128 stängda, hardening efter Composer-2.5-review). Nästa är **Viewser-overlay-E2E-Scout** — verklig frontend-kvalitetsmätning via det faktiska overlayflödet (wizard → prompt → eventuell scrape/upload → build → preview). 4-6 case inkl. keramik (verifierar B101/B102/B128 live), tjänsteföretag med adress, scrape-case, sköldpaddssoppa-conflict, "2 sidor"-case och en follow-up. Vid ≥7/10 och inget case <6.5 → Project DNA-sprint. StackBlitz/HTTPS för lokal preview körs nu via `.\scripts\dev-viewser.ps1 -Https` (https://-origins är vad embed-konsolen accepterar).

Kända lågprio-rester (oförändrat): B97 (`/kontakt`-copy), B98 (bredare e-handelsserviceområde-yta; B104 stängde bara country-only-läckan). B119/B120 (kontakt/adress) prioriteras om Scout visar fel kontaktdata. B125 (browser-preview-fallback) är produktblocker före extern kundyta. Variant-spåret `feat/eight-scaffold-variants` (`4cd1058`) ligger som separat feature-branch tills variant-promotion-sprint körs.

## Handoff från detta agentpass till nästa Steward

Detta pass (2026-05-18, kvällskörning) gick i fyra ron, alla på direkt
`main` enligt branch-discipline:

1. **Steward bug-scope-cleanup** (`7742d39` + `0d3e9b8`): flyttade
   15 misplaced 1B-fixar (PR #28 / `885431b`) från "Öppna" till "Stängda"
   i `docs/known-issues.md`. Rättade också 1B closure-noten — den
   listade tidigare B71/B72/B75/B83 som stängda men de har `Fix: open`
   i sina poster och är medvetet öppna (B71 markerad som unverified av
   re-Scout). Bumpade summary-raden från `17/15/6/62` till `17/0/6/77`.
2. **B109 reviewer-hotfix** (`fa277a1` + `b3800ca`): extern reviewer
   (Cursor Bugbot-stil) mot baseline `1c68035` hittade att
   `_npm_install_inputs_changed` fångade bara `(OSError, JSONDecodeError)`
   men `load_json` läser med `encoding="utf-8"`, så ogiltig UTF-8 i
   target-`package.json` raisade `UnicodeDecodeError` och kraschade
   builden. Fix: lägg till `UnicodeDecodeError` i except-tuple.
   Två regressionstester i `tests/test_builder_hardening.py`.
3. **B112 reviewer-triage** (`adde45c` + `9bf3893`): extern reviewer
   mot post-1E-baseline. Tre fynd verifierade genom kodläsning:
   - B112 (Låg, stängd `adde45c`) — `_product_category_name`
     joinade `label.split()` utan separator, så
     `services_mentioned=["handgjord keramik"]` på e-handel-prompt gav
     H1 `"Handgjordkeramikbutik"`. Fix: använd sista ordet
     (grammatiska substantivet) → `"Keramikbutik"`,
     `"Matbutik"`, `"Smyckenbutik"`. Single-word oförändrade. Tre
     regressionstester + B106-regressionen kvarstår.
   - B110 (Låg-Medel, öppen) — `_normalize_business_type` (B107-fixen)
     körs bara i CTA-flödet; tagline/service-summary-mapparna i
     `prompt_to_project_input.py` nycklar på rå briefModel-output, med
     luckor särskilt på `webshop`/`webbshop` SV och `naprapatklinik` EN.
     Inte krash — "split sanning" som ger inkonsekvent copy. Kopplar
     mot B13a (arkitektur-flytt av `scripts/build_site.py` till
     `packages/`). Verklig fix kräver delad helper, för stor för ett
     snabbpass.
   - B111 (Låg, öppen) — `scripts/generate_variant_candidate.py`
     faller tillbaka till mock vid alla `Exception` från
     `_call_variant_model` med `source="mock-llm-error"` + stderr-print
     + `exit 0`. Medveten design men saknar
     `--fail-on-llm-error`/`--strict`-CLI-flagga för CI-strict-mode.
     Enhancement, inte bug.

### Vad du som nästa Steward bör göra först

1. `python scripts/focus_check.py` — drift-check. Förvänta dig
   `Result: OK` med eventuell "1 commit ahead - within bump tolerance".
2. `python scripts/list_open_bugs.py` — bug-scope. Förvänta dig
   `Active: 19  Misplaced: 0  Unknown: 6  Closed: 79`. Misplaced > 0
   är direkt städningssignal (öppna-poster med `Fix: <sha>` som inte
   flyttats till Stängda).
3. `git log --oneline -10` — kontrollera att HEAD är `9bf3893` eller
   nyare. Två commits per sprint (Builder + Steward bump) är normalt
   mönster sedan föregående pass.
4. Kontrollera operatörens fråga: om hen explicit ber om att fixa
   B110/B111 är det Builder-arbete (rör `scripts/`); annars lämna dem
   öppna.

### Vad du som nästa Steward INTE bör göra

- Lämna inte B110 utan att också flytta `_normalize_business_type` till
  delad helper. Halv-fix (ad-hoc-duplicering av normalisering) är värre
  än ingen fix här — det skulle hänga kvar som teknisk skuld utan
  spårning. Den hör hemma i samma sprint som B13a-arkitektur-flytten.
- Skapa inte nya B-IDs för samma fynd som B110 eller B111 om en framtida
  reviewer hittar dem igen. Hänvisa till befintliga B-IDs i stället.
  Reviewer-prompter har en tendens att åter-rapportera samma observation.
- Acceptera inte `Misplaced > 0` ohanterat. Antingen flytta dem eller
  rapportera tillbaka till operatören att en Builder/Cloud Agent är
  skyldig dem.
- Bumpa inte Last verified-SHA till en docs-only-commit om det finns
  en ny Builder-commit ovanpå. Last verified pekar på senaste
  produktcommit, inte på sin egen bump.

### Operatörsförslag som väntar på beslut (inte påbörjat)

**Mini-bot-automation för Steward-städ.** Operatören frågade om
automation i detta pass. Förslaget i tre nivåer, ingen implementerad
ännu:

- **Mini-bot (lätt):** pre-push hook eller GitHub Action som kör
  `python scripts/list_open_bugs.py --quiet` + verifierar
  summary-raden. Fångar ~80 % av Steward-städ-skulden för ~30 raders
  Python. Lägst risk och snabbast påverkan.
- **Steward-Action (medel):** GitHub Action vid push till `main` som
  kör hela steward-guardsetet (governance, rules_sync, term_coverage,
  bug_scope, docs_freshness) och öppnar draft-PR om något driftar.
- **Auto-Steward (tyngre):** schemalagd Cursor Cloud Agent med fast
  `Roll: Steward` + tydligt write-set
  (`docs/known-issues.md`, `docs/current-focus.md`, `docs/handoff.md`).
  Risken är scope-läckage; mitigeras via Scout RO-review före push.

Lägg fram förslaget igen om operatören återupptar diskussionen.

### Backup-tillstånd

`backup-26-VIKTIG` (pre-B108), `backup-27` (post-B108, pre-cleanup),
`backup-28` (post-cleanup, pre-B109) och `backup-29` (post-B109, pre-B112)
är alla pushade på origin. Inga lokala branches utöver `main` enligt
operatörens uttryckliga preferens. Inget nytt backup-N skapas för denna
handoff-commit eftersom det är ren docs-only och inte ändrar
beteende.

**Demo-baseline-fix 1C closure note (2026-05-18, `b5ee710`):**

- **B88** — `scripts/prompt_to_project_input.py:_placeholder_contact()` skriver inte längre dev-jargong i publika kontaktfält. Default-placeholdern är nu `"Adress lämnas på förfrågan"` (sv) / `"Address available on request"` (en); operatören kan fortfarande skriva över via Project Input.
- **B94** — `scripts/build_site.py:render_about` omittar hela "Teamet"-blocket (rubrik + grid) när `company.team=[]`. Samma conditional-render som B66:s trust-fix.
- **B95** — ny `_COUNTRY_NAME_LOCATION_HINTS`-set (Sweden, Sverige, Norway, Norge, Denmark, Danmark, Finland, Iceland, Island) i `prompt_to_project_input.py`. När `locationHint` matchar ett landnamn returnerar `_normalize_location_hint` `None`, och `_placeholder_location` faller tillbaka till `city == country` som country-only-markör. Ny `_location_is_country_only`-helper i `build_site.py` suppressar hero-ortstag-spanen i `render_home` när markern är satt. Bredare än B91 — täcker även `locationHint="Sverige"` (inte bara `"Sweden"`-translit).
- **B96** — ny `_hero_cta_label(dossier)`-helper i `build_site.py` routar genom `_hero_cta_variant` med prioritet shop > booking > quote. Värden från `_HERO_CTA_VARIANT_LABELS`-whitelist (`"Shoppa nu" / "Shop now"`, `"Boka tid" / "Book a time"`, `"Begär offert" / "Request a quote"`). `render_home` (hero) och `render_services` (bottom-CTA) använder samma helper. Default fallback är fortfarande "Begär offert" så painter-palma-stilen demos inte regresserar.

19 nya regression-tester låser fixerna. Guards: ruff 0 findings, full pytest grön (3 skipped E2E/slow), governance_validate, rules_sync --check, check_term_coverage --strict, `list_open_bugs` grönt (15 aktiva, 15 misplaced, 6 unknown, 54 stängda).

Off-limits-områden enligt operatorns 1C-direktiv respekterades: `apps/viewser/lib/stackblitz-files.ts`, `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts`, `tests/test_viewser_files.py` (B59 parkerat), `data/starters/`-innehåll, `examples/`, `.env*`, `packages/preview-runtime` orörda.

Bakgrund: demo-baseline-fix 1B + bug-sweep mergead i `885431b` via PR #28 stängde B64, B65, B66, B69, B70, B71, B72, B73, B74, B75, B76, B77, B78, B79 och B83. Kvar från bug-sweep: B67, B80, B81, B82, B84, B85, B86, B87. Kvar från re-Scout 2026-05-15: B97, B98 (låg-impact). Övriga öppna B-IDs: B89-B93 (extern reviewer-triage), B49, B53, B47, B13a, BO4-followup-cancel (äldre). StackBlitz B59 är fortsatt parkerad. B71 (PR #28-stängd, men markerad som unverified av re-Scout) bör verifieras i två-pass-test nästa gång någon ändå provkör follow-up-flödet.

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
b5ee710 fix(builder): close demo-baseline-fix 1C (B88 B94 B95 B96)
b09f935 docs(focus): record backup-1..backup-8 prune on origin
7fdfee2 docs: bump verified SHA + sprint state after PR #29 + #30 merge
b3a32fc Backoffice maintenance and enabled toggles (#30)
c2c6f39 feat(tooling): list_open_bugs script + bug-scope-discipline rule (#29)
38d0af9 feat(maintenance): opt-in auto-prune via .env caps
0c549ac docs: queue live pipeline-matrix backoffice idea
ac33b3f docs: log Re-Scout findings (B94-B98) and 1C plan
948d2f9 chore(rules): add read-only-shell-windows rule
d0ded58 docs: align verified SHA with post-1B bump
cc3c6f3 docs: bump verified SHA after demo-baseline-fix 1B
8282bd9 docs: triage external reviewer findings B88-B93
885431b Demo-baseline-fix 1B + bug-sweep (B64-B79) (#28)
64c30d6 docs: log B64-B67 (Scout) + B69-B87 (bug-sweep) and queue Grind sprint
c273b1a docs: bump verified SHA after 1A-hotfix
d99f8ba fix(prompt-helper): close B61 B62 B63 (demo-baseline-fix 1A-hotfix)
a12314f chore(cursorignore): pin viewser node_modules and .next explicitly
b78484f docs: record verifierings-Scout findings (B61/B62/B63)
824cd3a docs: bump verified SHA to demo-baseline-fix 1A
ab74c2a feat(builder): demo-baseline-fix 1A
f29688c docs: bump verified SHA to rules commit
d072c98 chore(rules): add powershell-glob and cli-safety-belt rules
054e3b2 docs: bump verified SHA to Finding 1 fix
2acdeca feat(scripts): add prune_generated_previews.py with dry-run default
7b90c0c docs: record B60 fix and bump verified SHA
65f052a fix(prompt-helper): harden follow-up snapshots and meta loading (B60)
dd5464f docs: sync current-focus and handoff after PR #27 merge
e057fbd feat(viewser): preserve follow-up prompt versions (#27)
86d03bf docs: record B59 StackBlitz WebContainer embed blocker
210a1d1 chore(env): document Cursor API key placeholder
9927bd2 fix(viewser): harden StackBlitz payload size handling
4b98d8b chore(repo): remove visningsexempel artifacts and keep bug notes
869b2da chore(workspace): sync docs state and editor settings
cf523ed docs(adr): add ADR 0021 for StackBlitz preview workarounds
488f8a0 feat(viewser): harden StackBlitz preview payload handling
d9c244a chore(rules): add server-lifecycle-discipline rule
1cba454 docs(product): add operating context for agents
04fb92f docs(agents): align Codex with Cursor rules
9446200 docs(focus): record B45 contact route fix
6daee58 fix(builder): thread contact route through CTAs
3178a82 chore(workspace): integrate operator + parallel-agent docs/settings touch
c073d486 docs: add cloud agent gotcha for /sajtbyggaren-output permissions (PR #25)
19c3564 docs(focus): post-PR #24 docs-base merge + B49 follow-up
c2d8632 feat(starters): add harmonized docs-base starter (PR #24)
8997596 docs(focus): bump verified SHA after workspace cleanup
97ce7a8 chore(workspace): ignore PR review worktrees and sync build-runner comment
5199d94 docs(focus): record B48 follow-up semantics landing
10eb286 fix(dev-generate): thread follow-up mode into plan phase
ec11c41 docs: sync generated output path across docs
de7fd7c docs(focus): bump verified SHA after workspace hygiene pass
134df07 chore(workspace): perf hygiene + .generated externalization + viewser prettier setup
9ff7c50 docs(focus): bump verified SHA + queue after audit-fix B44+B46
5d746e9 fix(viewser): audit-fix sprint for B44 + B46
34551b4 docs(cleanup): modernize viewser copy and starter routing notes
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
