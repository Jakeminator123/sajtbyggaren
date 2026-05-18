# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent ska läsa denna fil
**först**, innan något annat i `docs/` eller `governance/`.
Startpromptar och rollgränser finns i
[`docs/agent-prompts.md`](agent-prompts.md).

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Standard loop steg 8 i
[`docs/agent-handbook.md`](agent-handbook.md) är obligatoriskt: efter
varje merge eller direktpush till `main` ska agenten i samma eller direkt
efterföljande commit:

1. Uppdatera "Current stage" och "Current active sprint" till nya läget.
2. Stryka från "Queue" / "Blocked" det som blev klart.
3. Lägga till nya blockers eller queue-items om något upptäcktes.
4. Bumpa "Last verified state"-SHA:n till nya HEAD.

Steward ska dessutom post-push-verifiera origin/main-SHA, `git status`,
`python scripts/focus_check.py` och om `origin/main` matchar lokal `main`.
Uppdatera `current-focus.md` och/eller `handoff.md` när ny faktisk HEAD
avslutar en sprint, active sprint ändras, next action/queue/blocked ändras,
ett beslut påverkar agentflöde, branchflöde, grindmode eller rollansvar, ny
risk/blocker/nice-to-have blir viktig för nästa agent, eller extern PR/
Grind-agent ändrar vad `main` betyder. Uppdatera inte för ren mikrostatus
som inte ändrar nästa agents arbete.

Operatören (Jakob) **verifierar** att det är gjort. Om operatören
upptäcker att filen är inaktuell är det första instruktionen till nästa
agent: "uppdatera current-focus innan något annat".

Last verified state: `b5ee710` (2026-05-18, lokal mainline-commit `fix(builder): close demo-baseline-fix 1C (B88 B94 B95 B96)`. Konvention för denna rad: SHA pekar på senaste produkt-/governance-commit; efterföljande Steward-bump-commit räknas som "within bump tolerance" av `focus_check.py`. 1C-commiten stänger fyra top synliga demo-blockers efter re-Verifierings-Scout 2026-05-15:s 5.54/10-mätning: B88 (`_placeholder_contact` dev-jargong byts mot branschneutral fras), B94 (`render_about` omittar tom team-sektion), B95 (ny `_COUNTRY_NAME_LOCATION_HINTS`-set + country-only-markör + `_location_is_country_only`-helper som suppressar hero-ortstag), B96 (`_hero_cta_label`-helper trådar `scaffoldId` + `conversionGoals` så `ecommerce-lite` får "Shoppa nu", `booking_request` får "Boka tid", övriga behåller "Begär offert"). Påverkar `scripts/prompt_to_project_input.py` + `scripts/build_site.py`; 19 nya regression-tester i `tests/test_prompt_to_project_input.py` + `tests/test_builder_route_emission.py`. Föregående mainline-push: `b09f935` (`docs(focus): record backup-1..backup-8 prune on origin`). Föregående baseline: `b3a32fc` (PR #30 squash-merge `Backoffice maintenance and enabled toggles` ovanpå PR #29 `c2c6f39` `list_open_bugs script + bug-scope-discipline rule`). PR #30 döper om Streamlit-entrypoint (`backend.py → backoffice.py`), lägger till `Underhåll`-sektion, och lägger `enabled: bool`-toggles på Scaffolds/Variants/Dossiers/Starters med fail-loud i `packages/generation/planning/plan.py` + `scripts/build_site.py`. ADR 0023 + ny policy `governance/policies/starter-registry.v1.json` + ny schema `governance/schemas/starter-registry.schema.json`. PR #29 lägger till `scripts/list_open_bugs.py` + `governance/rules/bug-scope-discipline.md` (alwaysApply) + sammanfattningsrad i `docs/known-issues.md` (låst av `tests/test_bug_scope_discipline.py::test_known_issues_summary_line_matches_script`). Aktuell räkning efter Re-Verifierings-Scout 3 2026-05-18: 21 aktiva (15 + B99/B100/B101/B102/B103/B104), 15 misplaced, 6 unknown, 54 stängda. `backup-22` skapad från synkad `main` innan 1C-sprinten (lokalt + push).)

Föregående produktcommit: `ab74c2a` (2026-05-15, demo-baseline-fix 1A landade direkt på `main`. Konvention för denna rad: SHA pekar på senaste produkt-/kodcommit; den efterföljande Steward-bump-commiten själv (denna rad-ändring) räknas som "within bump tolerance" av `focus_check.py` och får inte ge en till bump-rundgång. `feat(builder): demo-baseline-fix 1A` (`ab74c2a`) stängde Scout-auditens topp 3 demo-blockers i ett pass: (1) `/_global-error` prerender-fel (regression/variant av B41) löst genom att lägga explicit `app/global-error.tsx` i `data/starters/marketing-base/app/` och `data/starters/commerce-base/app/` med `"use client"` och inga third-party-imports - verifierat end-to-end via `painter-palma` (marketing-base) + `atelje-bird` (commerce-base) som båda nu landar `status: ok`, `quality: ok`, `npm install + npm run build` gröna; (2) rå prompt läckte ut som `company.name`/`company.story` på rendererade sajter - `scripts/prompt_to_project_input.py` skriver om `_company_name_from_prompt` till `_derive_company_name` (läser bara `brief.businessTypeGuess` + `brief.locationHint` via en liten svensk business-type label-map: electrician -> elektriker, hairdresser -> frisör, ceramics-studio -> keramikstudio, ...) och `_derive_story` (föredrar `brief.notesForPlanner`, fallback till strukturerad svensk platshållartext, aldrig raw prompt); (3) svenska tecken förstördes i service-labels (`F Rska Gg Direkt Fr N G Rden`) - `_slugify_label` NFKD-foldar för id-fältet (`färska ägg -> farska-agg`) men `_service_label_from_text` behåller å/ä/ö i labeln, och brief `services_mentioned` Field-description + system-prompt frågar nu efter natural-language fraser på originalspråk istället för kebab-case English slugs. `slugify_site_id` NFKD-foldar också före substitution så `elektriker i Malmö` ger `elektriker-i-malmo-<tail>` (förut `elektriker-i-malm-<tail>` med `ö` kollapsad till dash). Regression-tester: `test_company_name_and_story_never_contain_raw_prompt` (låser exakta tokens från den failande real-runen `enehmsida-som-s-ljer-b-t-661e23`: `Enehmsida`, `båtari`, `2 sidor`), `test_swedish_service_labels_preserve_case` (`färska ägg direkt från gården -> Färska ägg direkt från gården` som label, ASCII-only slug), `test_slugify_label_ascii_folds_swedish_chars`, `test_company_name_uses_swedish_business_type_mapping`, `test_story_prefers_notes_for_planner` plus fyra fallback-tester. Out-of-scope per Scout/coach: ingen Project DNA / semantic follow-up merge, ingen StackBlitz/COOP/COEP, inga nya starters, ingen docs/rules-sprint utöver denna bump. `backup-19` skapad från synkad `main` innan sprintarbetet (lokalt + push). Föregående mainline-pushar samma dag: `f29688c` (Steward-bump efter rules-commit), `d072c98` (powershell-glob + cli-safety-belt rules), `8d45140` (Steward-sync efter prune-sprinten), `2acdeca` (prune-script + tester), `7b90c0c` (Steward-sync efter B60), `65f052a` (B60 fix), `dd5464f` (post-PR-#27 sanity-bump), `e057fbd` (PR #27 follow-up versions squash-merge). `backup-15` t.o.m. `backup-19` finns lokalt och på origin. Inga öppna PRs.)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid lokal mainline-commit `b5ee710` (`fix(builder): close demo-baseline-fix 1C (B88 B94 B95 B96)`). 1C stängde top synliga demo-blockers efter re-Verifierings-Scout 2026-05-15:s 5.54/10-mätning: B88 (kontakt-placeholder dev-jargong byts mot branschneutral fras i `_placeholder_contact`), B94 (`render_about` omittar tom team-sektion likt B66:s trust-fix), B95 (Nordic country names i `locationHint` mappas till country-only-markör så hero-ortstag suppressas via ny `_location_is_country_only`-helper), B96 (hero-CTA + render_services-CTA går via ny `_hero_cta_label`-helper med shop/booking/quote-variants beroende på `scaffoldId` + `conversionGoals`). 19 nya regression-tester låser fixen i `tests/test_prompt_to_project_input.py` + `tests/test_builder_route_emission.py`. Bug-scope-räkningen i `docs/known-issues.md` sammanfattningsrad: 15 aktiva, 15 misplaced (Steward-städ-uppgift för PR #28-stängningar), 6 unknown (B47, B49, B53, B59 + två till), 54 stängda. Off-limits-områden enligt operatorns 1C-direktiv respekterades: `apps/viewser/lib/stackblitz-files.ts`, `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts`, `tests/test_viewser_files.py`, `data/starters/`-innehåll, `examples/`, `.env*`, `packages/preview-runtime` orörda. Föregående mainline-pushar: `b09f935` (`docs(focus): record backup-1..backup-8 prune on origin`) och PR #30 squash-merge (`b3a32fc`) för Backoffice maintenance + enabled toggles + ADR 0023, ovanpå PR #29 (`c2c6f39`) för list_open_bugs + bug-scope-discipline rule.

Föregående baseline: PR #28 squash-merge (`885431b`) för demo-baseline-fix 1B + bug-sweep. 1B stängde must-/should-land-spåret och alla nice-to-have som hanns med: B64/B65 (Site Brief company/contact-fält + ADR 0022), B66 (tom trustSignals renderar inte "Varför oss"), B69 (Quality Gate route-scan får alla emitterade default-routes inkl. `/om-oss`; aggregate-status ändrades medvetet inte), B70 (IPv6 localhost Host-header), B71 (follow-up merge-docstring + byte-stabil story/tagline/tone), B72 (`listRuns` slicar innan JSON-läsning), B73 (tagline-fallback utan Project Input-jargong), B74 (dev_generate codegen routes), B75 (`additionalProperties: false` i Project Input-schema), B76 (Run Details visar site-plan), B77 (dossier-komponenter får inte skugga starter-komponenter), B78 (realpath-baserad dossier-whitelist), B79 (svensk selectedDossiers-rationale) och B83 (service slug-kollisioner får suffix). PR #28 verifierades med ruff, full pytest, governance/rules/term checks, Viewser `npm run build` och två isolerade smoke-builds (`elektriker Malmö`, `frisör Göteborg`) som båda landade `status=ok`, `quality=ok`. Bugbot var inte aktiv på PR:n; GitHub governance, builder-smoke och secret-scan var gröna före merge.

**Verifierings-Scout 2026-05-15 (pre-hotfix)** körde fyra skarpa prompter (`elektriker Malmö`, `frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som säljer keramik`) via `prompt_to_project_input.py` + `build_site.py` mot 1A-koden. Alla fyra byggde grönt med `status: ok`. **Totalsnitt 6.2 / 10** — precis över 6/10-tröskeln, men tre regressioner/buggar identifierades och loggades som **B61** (notes_for_planner-läckage som customer copy — 1A-regression), **B62** (`detect_language` slår fel på korta svenska prompts → engelska sajter på 2 av 4 case) och **B63** (`_BUSINESS_TYPE_LABEL_SV` slug-glipor mot briefModels faktiska slugs). Alla tre stängda i 1A-hotfix `d99f8ba`; nästa steg är re-verifierings-Scout med samma fyra prompter för att jämföra mot 6.2-baselinen — se "Next action".

Föregående produktcommit före hotfix: `ab74c2a` (demo-baseline-fix 1A): Scout-auditens topp 3 demo-blockers stängda i ett pass — `/_global-error` build-fel borta (verifierat på `painter-palma` + `atelje-bird` med båda `status: ok`), rå prompt landar inte längre i `company.name`/`company.story` (brief-driven `_derive_company_name` + `_derive_story` ersätter prompt-as-H1/story-mönstret med Swedish business-type label-map), svenska tecken bevarade i service-labels (NFKD-fold för slugs, original-string för labels). 10 regression-tester i `tests/test_prompt_to_project_input.py` från 1A-passet kvarstår.

Föregående cleanup/prune-sprint är fortfarande klar: nytt `scripts/prune_generated_previews.py` med dry-run default + `--apply`-gate (env-flaggan `SAJTBYGGAREN_PREVIEW_RETENTION_DRY_RUN` defaultar till OFF så `--apply` ensamt räcker; sätts den explicit till `true` blockas radering även med `--apply` som operatörs-safety-belt) + current-pointer-skydd + port-3000-refusal landade tillsammans med tolv regression-tester i `tests/test_prune_generated_previews.py` (tio från första passet plus två som låser env-/CLI-interaktionen efter Finding 1-fixen) och utvidgad allowlist i `scripts/check_term_coverage.py`. B60 är stängd: follow-up-versioneringen från PR #27 hade fyra kontraktsbrott som upptäcktes i post-merge audit (versionerade snapshots inte immutabla, follow-up-prompt läckte i `company.story`, icke-atomisk pointer-update, tyst init-fallback vid saknad sidecar) och alla fyra är nu fixade i `scripts/prompt_to_project_input.py` + `scripts/build_site.py:load_prompt_input_meta` med 5 nya/uppdaterade regression-tester. PR #27 (`feat(viewser): preserve follow-up prompt versions`, `e057fbd`) är fortfarande merge-baseline: follow-up promptar skriver immutable `<siteId>.vN.project-input.json`/`<siteId>.vN.meta.json`-snapshots i `data/prompt-inputs/`, behåller `projectId`/`originalPrompt` och lägger `followUpPrompt` på snapshot-meta. `scripts/build_site.py` läser sidecar-meta intill dossier-pathen och trådar `mode`/`projectId`/`version`/`originalPrompt`/`followUpPrompt` in i `input.json`, `generation-package.json` och `build-result.json`. `apps/viewser/lib/runs.ts` läser per-run-meta från `build-result.json` -> `input.json` -> mutable sidecar legacy-fallback, så RunHistory visar stabil `projectId` + `version` även när nya follow-ups landar. `apps/viewser/lib/project-inputs.ts` filtrerar `.vN.project-input.json`-snapshots från ProjectInputPicker (bara current pointer är valbar). `apps/viewser/lib/prompt-runner.ts` + `lib/build-runner.ts` föredrar repo-roten `.venv` Python när den finns (cloud/lokal dev-konsistens) och cleanar prompt-/build-mutex via `try/finally`.

StackBlitz-preview-spåret är fortsatt avgränsat till preview-payload-only: `apps/viewser/lib/stackblitz-files.ts` patchar in-memory (`next dev/build --webpack`, `npm run build && npm run start`, lockfile med i payload, `app/global-error.tsx`-override, patched payload-bytes mot size cap, `next start`-fallback), medan `apps/viewser/next.config.ts` fortsatt är tom och testet låser att global COEP/COOP inte sätts i Viewser. Ingen ändring är gjord i starters, builder eller preview-runtime-paketet; ADR 0021 är källan för beslut/avgränsning.

`B59` (StackBlitz `template:"node"`/WebContainer-embed blockerad/instabil i moderna Chrome-runtimes; tre header-lägen empiriskt verifierade utan grön preview, header-experimentet committades inte) är **parkerat**: ingen mer COOP/COEP-toggling i nuvarande sprintkö. Nästa arkitekturbeslut bör vara byte till lokal `next dev`-process som same-origin iframe på `localhost:NNNN` eller static StackBlitz-template, inte mer header-toggling. Run History + Run Details ger fortfarande diagnostik utan preview, och lokal `npm run build` på den genererade siten fungerar som verifikation.

Läget bygger på orkestrator-playbooken i `e026642`, `27f7fe9` (focus efter PR #26), PR #26:s produktkompass (`docs/product-operating-context.md`) i `1cba454`, `6daee58` (B45 `_pick_contact_route`-propagation till layout/home/services/products), `c2d8632` (PR #24 docs-base starter, squash-merge), `10eb286` (B48 follow-up-semantik i dev-driver/backoffice), `5d746e9` (Builder audit-fix för B44 + B46) och `9944abb` efter Prompt-till-sajt MVP v1 (Builder-
sprint 2026-05-13/14, Scout-RO-godkänd), review-hotfix för
prompt-helperns brief-fallback, Viewser mini-sprint som tog bort
gamla ChatPanel från home och en audit-hotfix-sprint som städade
fyra Scout-fynd i prompt-flödet. Operatören kan nu skriva
en fri prompt i Viewser, helpern (`scripts/prompt_to_project_input.py`)
kör briefModel, mappar Site Brief deterministiskt mot en schema-valid
Project Input, skriver den till `data/prompt-inputs/SITE_ID.project-input.json`
plus sidecar `SITE_ID.meta.json` (projectId/version/originalPrompt/
briefSource), och `apps/viewser/app/api/prompt/route.ts` triggar
`runBuild` med dossier-path-override. PromptBuilder är nu den enda
primära promptytan på Viewser-home; legacy ChatPanel är raderad. Follow-up
prompt versions är nu landat: operatören kan fortsätta på befintlig
prompt-input/run, behålla `projectId`, bumpa version och få ny build/run
för samma sajtspår. RunHistory uppdateras via samma `fetchRuns`-loop som
`/api/build`. PR #23 har dessutom landat backoffice trace/playground-
förbättringar: engine-runs-vyn och playground-vyn använder en gemensam strukturerad
trace-viewer och playground visar subprocess-status/loggutdrag medan körningen
pågår. `backup-9` finns lokalt från pre-PR-#23-läget; backup-8 finns lokalt
efter follow-up-sprinten; backup-7 från `fb11925` ligger på origin som fallback
efter audit-hotfix-sprinten. PR #22 har också landat `portfolio-base` som ny
harmoniserad starter under `data/starters/portfolio-base/`. Commit `e9093c0`
ändrar bara `.cursor/settings.json` och aktiverar `linear` + `sanity`; commit
`d43bce2` synkar handoff/focus efter settings-commiten.

Föregående: PR #21 (lucide-react i commerce-base + ADR 0020,
mergad `04fc2fa` 2026-05-13 19:55 UTC) gjorde full `npm run build`
mot `.generated/atelje-bird/` grön (11 statiska sidor + commerce-
base:s dynamiska routes utan `Module not found`). PR #20 (B20 step 2
mapping-flip + ADR 0019, samma dag 19:33 UTC) aktiverade
`SCAFFOLD_TO_STARTER["ecommerce-lite"] = "commerce-base"`. Real
codegenModel-scope är fortsatt låst till `marketing-base` per
ADR 0017 (ingen utvidgning beslutad).

Prompt-till-sajt MVP v1-pushen (2026-05-14):

- `afaa8a8` — `docs(workflow): formalize progress estimate + scout
  model level`. Operatörs-supplied: Builder slutrapport ska ge en
  grov progress-procent + bedömning av nästa etapp; Scout föreslår
  modell-/insatsnivå 1-10; Steward verifierar att current-focus +
  handoff fortfarande pekar rätt.
- `4d5b4de` — `feat(viewser): prompt-till-sajt MVP v1`. Ny
  `scripts/prompt_to_project_input.py` (briefModel + Site Brief →
  schema-valid Project Input + sidecar meta i `data/prompt-inputs/`),
  ny `/api/prompt` route med localhost-guard + Zod-payload (1-4000
  tecken), ny PromptBuilder-UI-panel, `runBuild` får
  dossier-path-override bakom ALLOWED_DOSSIER_ROOTS-whitelist
  (examples/ + data/prompt-inputs/), 11 nya helper-tester + 2 nya
  viewser-guards. Ingen ADR/policy-bump (sidecar-meta undviker
  project-input.schema.json-migration).
- `c6e2f1d` — `fix(viewser): fall back when prompt brief extraction
  raises`. Review-hotfix: `extract_site_brief` och
  `site_brief_to_artifact` ligger nu i fallback-try/catch så
  promptflödet skriver schema-valid mock Project Input även vid
  oväntade LLM-/serialiseringsfel. Regressions täcker båda grenarna.
- `ea4b165` — `fix(viewser): isolate StackBlitz preview mount`.
  StackBlitz SDK embed mountas nu i en unmanaged child-node istället
  för att ersätta React-ägda preview-shellen. Cleanup använder
  `replaceChildren()`. Source-lock uppdaterad i `test_viewser_files.py`.
- `fd67fbd` — `refactor(viewser): remove legacy chat panel from home`.
  `app/page.tsx` importerar/renderar inte längre `ChatPanel`; nya
  `test_viewser_prompt_primary.py` låser att PromptBuilder är canonical
  promptyta på Viewser-home.

Audit-hotfix-sprint (2026-05-14, post-Scout-bug-audit):

- `fe56344` — `fix(prompt-helper): hoist brief imports to module level
  for monkeypatching`. Lyfter `detect_language`,
  `extract_site_brief`, `site_brief_to_artifact` och
  `resolve_brief_model` från function-scope till modulnivå så
  fallback-tester faktiskt patchar lookup-namnen som
  `prompt_to_project_input.generate` använder. Tidigare patch mot
  `packages.generation.brief.*` no-opp:ade tyst.
- `cb54ca9` — `docs(agent-prompts): expand role catalog with parallel-
  agent rules`. Utökar Scout/Builder/Steward-startprompter och låser
  parallell-agent-disciplinen.
- `1033bf6` — `fix(prompt-route): return 400 on Zod errors and trim
  whitespace at API edge`. Splitt:ar try/catch så `ZodError` -> 400
  med valideringsmeddelandet, lägger `.trim()` före `.min(1)` i
  payload-schemat så whitespace-only prompts fångas vid API-gränsen
  istället för att slinka ned till helperns 500-gren. Två nya
  source-lock-tester i `tests/test_viewser_files.py`.
- `e067006` — `fix(prompt-runner): pass -- to argparse so dashed
  prompts spawn cleanly`. `spawn(...,[scriptPath, "--", trimmed])` så
  en prompt som börjar med `-` eller `--` (vanlig punktlista) inte
  tolkas som CLI-option av argparse i `prompt_to_project_input.py`.
- `c039ebd` — `fix(viewer-panel): refresh stale fallback copy after
  legacy chat panel removal`. 404-fallback och tip-block hänvisar nu
  till promptfältet istället för den borttagna Build-knappen i
  ChatPanel.
- `e421a00` — `chore(check_term_coverage): allowlist ZodError TS
  symbol`. Speglar Pydantic `ValidationError`-behandlingen så
  `ZodError` (extern lib-symbol från `zod`) inte räknas som
  okänt domänbegrepp i strict-läget.
- `2f0af68` — `docs: bump focus + handoff to e421a00 post-audit-
  hotfix-sprint`. Standard loop steg 7 efter audit-hotfix-sprinten:
  bumpar SHA + uppdaterar Queue/Blocked.
- `c3dcc14` — `docs: correct verified HEAD to 2f0af68 in focus +
  handoff`. Följdfix ovanpå `2f0af68`; lokal `main` och `origin/main`
  är post-push-verifierade på denna SHA.
- `006be38` — `docs(workflow): formalize steward post-push
  verification`. Låser Builder→Steward-post-push-flödet i docs,
  governance-spegeln och `focus_check.py`-remindern.
- `2701b00` — `feat(viewser): add follow-up prompt versions`.
  Follow-up prompt versions landat direkt på `main`: promptflödet kan
  fortsätta på befintligt `projectId`, bumpa version och skriva nya
  prompt-inputs/runs för samma sajtspår.
- `e1ad5ca` — `feat(backoffice): improve trace viewer and playground
  logs`. PR #23 squash-mergead: backoffice trace/playground-städning med
  gemensam trace-viewer, synlig subprocess-status/loggar och stängda
  backoffice-poster i `docs/known-issues.md`.
- `9944abb` — `feat(starters): add harmonized portfolio-base starter`.
  PR #22 squash-mergead efter update-branch mot post-PR-#23 main och gröna
  governance-, Bugbot- och secret-scan-checkar.
- `e9093c0` — `Liten settings.json bara som committades`.
  Aktiverar `linear` och `sanity` i `.cursor/settings.json`; ingen
  produktkod ändrad.
- `d43bce2` — `docs: sync handoff after settings commit`.
  Synkar current-focus/handoff efter settings-commiten.
- `34551b4` — `docs(cleanup): modernize viewser copy and starter
  routing notes`. Steward-cleanup efter Scout-fynd: README, Viewser,
  starter-routing och migration-plan moderniserade till PromptBuilder
  samt follow-up versions; `.cursor/settings.json`-status och stale
  PromptBuilder-timeout-nice-to-have rensade.
- `5d746e9` — `fix(viewser): audit-fix sprint for B44 + B46`. B44 stängd:
  `/api/prompt` exponerar `buildStatus`, PromptBuilder klassificerar
  utfall via `classifyBuildStatus`, `app/page.tsx` använder
  `PromptBuildOutcome` + `headerStatusForOutcome`. B46 stängd:
  `apps/viewser/components/chat-panel.tsx` raderad, tester +
  vocabulary-discipline + check_term_coverage rensade. Två nya öppna
  poster: B45 (hardcoded `/kontakt`) och B47 (commerce-base Shopify
  handles).
- `9ff7c50` — `docs(focus): bump verified SHA + queue after audit-fix
  B44+B46`. Standard loop steg 8 efter audit-fix-sprinten.
- `134df07` — `chore(workspace): perf hygiene + .generated externalization + viewser prettier setup`. Workspace-hygien-pass: utökad `.cursorignore`,
  ny `.cursorindexingignore` + `.editorconfig`, `.vscode/settings.json`
  får watcher-exclude + tsserver memory-bump + prettier-format-on-save,
  `scripts/build_site.py` skriver dev-preview-output till
  `../sajtbyggaren-output/.generated/SITE_ID` som default (override via
  `--generated-dir`/`SAJTBYGGAREN_GENERATED_DIR`), ny `builder-smoke`
  CI-job, `apps/viewser` får prettier 3.8.3 + plugin, `konversation.txt`
  untrackas. Inte en buggfix - se note i `docs/known-issues.md`
  "Notera (inte en bugg)" om den nya output-pathen.
- `de7fd7c` — `docs(focus): bump verified SHA after workspace hygiene pass`.
  Standard loop steg 8 efter workspace-hygien-passet.
- `ec11c41` — `docs: sync generated output path across docs`.
  Synkar `AGENTS.md`, `README.md` och `docs/architecture/builder-mvp.md`
  till nya defaulten `../sajtbyggaren-output/.generated/<siteId>/`.
- `10eb286` — `fix(dev-generate): thread follow-up mode into plan phase`.
  B48 stängd: `run_phase_plan()` tar `mode`/`project_id` och skickar dem
  till `produce_site_plan()`, så `generation-package.json` matchar
  `input.json` vid follow-up. Tester låser både CLI/dev-driver och
  Backoffice Playground-subprocessen.
- `5199d94` — `docs(focus): record B48 follow-up semantics landing`.
  Standard loop steg 8 efter B48-sprinten; dokumenterar PR #24 draft.
- `97ce7a8` — `chore(workspace): ignore PR review worktrees and sync
  build-runner comment`. `.review-*/` ignoreras i git/Cursor/VS Code
  watcher och `build-runner.ts`-kommentaren pekar på external
  generated preview directory.
- `8997596` — `docs(focus): bump verified SHA after workspace cleanup`.
  Standard loop steg 8 efter parallell-agentens workspace-cleanup.
- `c2d8632` — `feat(starters): add harmonized docs-base starter (PR #24)`.
  Squash-merge: ny `data/starters/docs-base/`-starter (Nextra 4.6.1 +
  Pagefind + MDX) + Steward-fixup för coachens fynd: ärlig sidebar-
  copy i `authoring.mdx`/`index.mdx`/starter-README + harden:ad
  ThemeToggle (useState lazy-init istället för DOM-mutation, plus
  aria-pressed + suppressHydrationWarning, lint-clean mot React 19/
  Next 16's `react-hooks/set-state-in-effect`-regel). `docs-base` är
  starter-underlag, inte aktiverad i `SCAFFOLD_TO_STARTER`. B49 öppen
  som följdsteg innan runtime-aktivering: page-map-driven sidebar
  istället för manuell `<aside>` i `layout.tsx`.
- `19c3564` — `docs(focus): post-PR #24 docs-base merge + B49 follow-up`.
  Standard loop steg 8 efter PR #24, plus B49 öppnad i
  `known-issues.md` och term-coverage allowlist för
  `ThemeToggle`/`Layout`/`B49`.
- `c073d486` — `docs: add cloud agent gotcha for /sajtbyggaren-output
  permissions (PR #25)`. Cloud-agent docs-PR: AGENTS.md får en
  gotcha för Cloud Agent VMs som visar att
  `/sajtbyggaren-output/` måste finnas med write-permissions för
  builder-tester (annars failar de tysta).
- `04fb92f` — `docs(agents): align Codex with Cursor rules`.
  `AGENTS.md` låser att Codex-IDE-agenten agerar Cursor-kompatibel
  repo-agent och följer `.cursor/BUGBOT.md` + `.cursor/rules/`, men
  fortsätter ändra governance-källorna i stället för genererade speglar.
- `9446200` — `docs(focus): record B45 contact route fix`.
  Standard loop steg 8 efter B45: current-focus/handoff synkar nästa
  konkreta uppgift till B49.
- `3178a82` — `chore(workspace): integrate operator + parallel-agent
  docs/settings touch`. Sopar upp tre filer som drev i working tree
  efter parallell-agent-aktivitet: `.cursor/settings.json` vercel-
  blocket borttaget (operator-toggle), `README.md` ADR-lista 0016-0020
  samt Sprint 3B+3B-next-status, `docs/agent-prompts.md` ny "Baseline för
  Codex-IDE"-sektion som kodifierar Scout-/Builder-/Steward-disciplin
  vid parallella agentpass.

Mainline-steward-pushar efter PR #21 (pure docs/governance):

- `0db29e6` — `.cursorignore` ignorerar nu hela `referens/`.
- `06a6047` — `docs/handoff.md` refreshad till post-PR-#20/#21-state.
- `09c53b0` — `check_term_coverage.py` allowlistar Bugbot/GitHub-
  statussträngar.
- `ebc9c09` — `current-focus.md` Queue/Next action efter RO-audit.
- `2aafa41` — agentflödet formaliseras (3 fasta roller +
  backup-N-disciplin + Scout som RO-bugggranskare).
- `504befc` — `agent-prompts.md` flyttad in i `docs/`.

Mainline-steward-pushar som också ligger på main:

- `bba8e36` - ny `bugbot-pr-loop`-regel (8-min poll + 10-iter
  fix-loop + nödläge-eskalering) under `governance/rules/`.
- `af8b337` - refresh av `docs/handoff.md` för main-as-default-
  policy + post-B13b-state.
- `61f9f69` - `reply-style`-regel (kort+koncis svenska med
  parens-förklaringar för dev-uttryck) under `governance/rules/`.
- `b4fe4a8` + `1c2227b` - `.gitignore`/`.cursorignore` pre-allokerar
  `packages/generation/build/` (B13a-destinationen) och blockar
  `.cursor/mcp.json`.

Branches städade 2026-05-13/14: feat/b20-step-2-mapping-flip raderad
lokalt + remote efter merge. 2026-05-14 skapades remote `backup-12`
från `9446200` som aktuell fallback, och de verifierat mergeade
PR-head-brancherna `cursor/env-setup-9fef`,
`cursor/docs-base-starter-harmonisering-98ec`,
`cursor/portfolio-base-starter-upps-ttning-bf2e` och
`cursor/backoffice-sp-r-lekplats-st-dning-d1d5` raderades från GitHub
eller bekräftades redan raderade. Backup-prune 2026-05-17 (efter
PR #29 + PR #30-merge): `backup-1` t.o.m. `backup-8` raderade från
origin på explicit operatörsdirektiv (~4 sprintar gamla, fallback-
behovet täckt av yngre backup-N). `backup-9` och `backup-10` har
aldrig existerat. Kvarvarande origin-fallbacks: `backup-11` t.o.m.
`backup-22` (12 st, äldsta från 2026-05-14). Inga lokala backup-N
finns kvar — alla raderades 2026-05-17 efter SHA-jämförelse mot
origin. Kvarvarande remote arbetsbrancher som inte ska raderas utan
separat beslut: `christopher-ui` och `frontend/christopher-import`
(PR #17 stängd utan merge, reference only). Stale PR-head-branch
`feat/demo-baseline-fix-1b-bug-sweep` (PR #28 mergad ovanpå) finns
också kvar på origin men är fri att radera i nästa Steward-städ.

## Current active sprint

Ingen pågående produktimplementation på `main`. Demo-baseline-fix 1C (B88 + B94 + B95 + B96) landade lokalt i `b5ee710` 2026-05-18. Re-Verifierings-Scout 3 (post-1C, samma dag) körd: totalsnitt **5.13/10 (rå) / ~5.9/10 (kalibrerat mot Scout-2-skalan)**, case-spann 4.88-5.75, alla fyra builds `status=ok`/`quality=ok`/`briefSource=real`. Verdict: 1C lyfte snittet (mest case 4 där B95+B96 aktiveras) men under 7/10-tröskeln och minst ett case under 6.5 → bug-sweep round 2 rekommenderas, Project DNA / semantic follow-up merge skjuts upp. B88/B94/B95/B96 mekaniskt verifierade som stängda; B96 stängd men levereras inte i case 2 + 3 eftersom briefModel returnerar `conversionGoals=[]` för korta prompter (booking-bransch faller tillbaka till quote-default). Sex nya öppna B-IDs loggade: B99 (Hög, `_derive_story` publik platshållartext på alla 4 case), B100 (Medel, `_hero_cta_label` saknar `businessType`-fallback), B101 (Låg, hero shop-CTA länkar fel route), B102 (Låg, `render_products` egen CTA-text matchar inte hero), B103 (Medel, `_derive_tagline` upprepar H1), B104 (Låg, `render_about` "Områden vi arbetar i" inte country-only-medveten). Inga öppna PRs. Nästa konkreta uppgift är **demo-baseline-fix 1D / bug-sweep round 2** — se "Next action".

Tidigare klara sprintar: demo-baseline-fix 1C (B88 B94 B95 B96), A-mini cleanup
(B51/B52/B54/B55 + B53 registrerad), Prompt-till-sajt MVP v1,
mini-sprinten som gjorde PromptBuilder till enda primära promptyta, follow-up
prompt versions, PR #23 backoffice trace/playground, PR #22 `portfolio-base`
starter, B48 follow-up-semantik, PR #24 `docs-base` starter, B45
kontakt-route-propagation, B50 route-hardening, Codex-IDE agent-parity-regeln,
mergead branch-cleanup, PR #26 produktkompass/agentläsordning,
orkestrator-playbooken för längre fleragentpass, StackBlitz preview
payload-hardening (ADR 0021 + B59 dokumentation), PR #27 follow-up
prompt versions (versionerade Project Input-snapshots, stabil
`projectId`/`version` i RunHistory, repo-`.venv` Python preferred),
PR #28 demo-baseline-fix 1B + bug-sweep, demo-baseline-fix 1A-hotfix.

## Next action - direktiv till nästa agent

**Demo-baseline-fix 1D / bug-sweep round 2** ovanpå 1C (`b5ee710` +
Steward-bump `6eaf222`). Re-Verifierings-Scout 3 2026-05-18 mätte
snittet till **5.13/10 (rå) / ~5.9/10 (kalibrerat)** och pekar på
att 1C levererade exakt vad den lovade — men störst hävstång ligger
nu i (a) story-platshållartext (B99) eftersom den är publik på alla
4 case och (b) booking-bransch-CTA (B100) eftersom det är samma
problem 1C trodde sig lösa. Decision rule: snitt ≥7/10 OCH inget
case <6.5 → Project DNA / semantic follow-up merge är nästa.

**Sprintscope i prioritetsordning (B-IDs):**

1. **B99 Hög** — `_derive_story` i
   `scripts/prompt_to_project_input.py` skriver platshållartexten
   "Vi är en {label} i {city}. Byt ut den här texten mot er egen
   berättelse så besökarna lär känna er." även när
   `brief.notesForPlanner` är icke-tom. Verifierat publikt på
   `/om-oss` på alla fyra demo-case. Fixa så `notesForPlanner`
   faktiskt föredras när det finns; behåll strukturerad
   platshållare bara när briefen är genuint tom. Lås med ny test
   som monkey-patchar briefModel-utfall till `notesForPlanner="…"`
   och asserterar att story inte innehåller "Byt ut den här texten".
2. **B100 Medel** — `_hero_cta_label` i `scripts/build_site.py`
   triggar inte "Boka tid" för korta prompter på booking-branscher
   eftersom briefen returnerar `conversionGoals=[]` för
   3-ords-prompter. Lägg `businessType`-fallback i prioritetskedjan:
   hair-salon, barber, naprapat-clinic, chiropractor, massage,
   physiotherapist, dentist, personal-training → booking;
   e-commerce, webshop → shop. Fortsatt prioritet: explicit
   `conversionGoals` > `businessType`-fallback > scaffold-default.
   Lås med tester per branschmappning.
3. **B103 Medel** — `_derive_tagline` ska inte upprepa H1. Föredra
   `brief.tagline` → använd `notesForPlanner` som källa för
   1-rads-USP → fall *inte* tillbaka till "Lokal {label} i {city}"
   om H1 redan innehåller `{label}` + `{city}`.
4. **B104 Låg** — `render_about` ska inte rendera "Områden vi
   arbetar i" när `_location_is_country_only(dossier)` är true
   (samma helper som B95 använder i hero). Rena trådningsfix.
   Närbesläktad med B98 — kan slås ihop.

**Off-limits (rör inte):**

- `apps/viewser/lib/stackblitz-files.ts`,
  `apps/viewser/components/viewer-panel.tsx`,
  `apps/viewser/next.config.ts`, `tests/test_viewser_files.py`
  (B59 parkerat).
- `data/starters/`, `examples/`, `.env*`,
  `packages/preview-runtime/`.

**Inte i scope denna sprint:** B101, B102 (commerce-CTA-mismatch,
låg prioritet — väntar tills någon tar `render_products` separat).
B97, B98 (re-Scout låg-impact, väntar — B104 löser delvis B98).
B89-B93 (extern reviewer-triage, separat sprint).

**Acceptanskriterier:**

- B99/B100/B103/B104 stängda med regression-tester.
- Smoke-build körd manuellt på `"frisör Göteborg"` och
  `"liten e-handel som säljer keramik"`. Hero CTA på frisör =
  "Boka tid". Story på båda innehåller inte
  "Byt ut den här texten".
- `docs/known-issues.md` får stängningsposter för B99/B100/B103/
  B104 och bug-scope-räkningen i sammanfattningsraden uppdateras
  (21 → 17 aktiva).
- `docs/current-focus.md` + `docs/handoff.md` bumpade till ny SHA
  efter push.

**Guards före push (alla MÅSTE vara gröna):**

- `python -m ruff check .` (baseline 0 findings)
- `python -m pytest tests/ -v` (inkl. nya tester)
- `python scripts/governance_validate.py`
- `python scripts/rules_sync.py --check`
- `python scripts/check_term_coverage.py --strict`
- `python scripts/list_open_bugs.py` (sanity-räkning)

**Beslutsregel för Re-Verifierings-Scout 4 (efter denna sprint):**
snitt ≥7/10 och inget case <6.5 → Project DNA / semantic follow-up
merge (inkl. två-pass-verifiering av B71). Annars riktad fix på det
case som dröjer.

Skapa `backup-23` från synkad `main` innan sprintstart.

B59 är fortfarande parkerad - rör inte StackBlitz-fronten. PR #27,
B60 och cleanup/prune-sprinten är klara; ingen ny header-toggling.

Föregående cleanup-status:

- A-mini cleanup landad i `2ad01a2`. B51 (nav-label JSX-escape),
  B52 (`/spel`-dedupe), B54 (`.env*`-filter i StackBlitz upload),
  B55 (test_viewser_env_file gitignore-semantik) stängda med
  regression-tester. B53 (routes.schema.json) registrerad som queue.
- B50 stängd i `4940cbb` + Scout-follow-up `f787eb7`: route-hrefs
  går via `_route_href()`, saknad contact-route ger tydligt builder-fel,
  `render_home()` hittar inte längre på `/tjanster` när listing-route
  saknas och route paths avvisar protocol-relative URLs/dot-segments innan
  href/page-path skrivs.
- B45 klar i `6daee58`: `write_pages()` trådar scaffoldens contact-path
  till layout, home, services och products, och tester låser frånvaro av
  hardcoded `href="/kontakt"` i renderer-helpers.
- `AGENTS.md` innehåller Codex-IDE-regeln från `04fb92f`: Codex agerar
  Cursor-kompatibel repo-agent och följer `.cursor`-reglerna, men ändrar
  governance-källorna om en regel behöver uppdateras.
- PR #26 mergead i `1cba454`: produktkompassen i
  `docs/product-operating-context.md`. Den förtydligar att tekniskt
  intressanta sidospår parkeras om de inte hjälper kärnflödet.

Öppna B-IDs: B13a (arkitektur-flytt, kräver ADR), B47 (commerce-base
Shopify handles), B49 (docs-base page-map sidebar), B53 (routes.schema),
BO4-followup-cancel (Playground-cancellation). Ingen är blocker idag.

`portfolio-base` och `docs-base` är båda starter-underlag; ingen
`SCAFFOLD_TO_STARTER`-mappning eller real-codegen-scope är aktiverad
av #22 eller #24. Real codegen-scope är fortfarande `marketing-base`-only
per ADR 0017.

### Pre-push self-review checklist (lärt från B13b + B20)

Innan `git push origin main`:

- Jämför `git diff origin/main..HEAD --stat` rad-för-rad mot sprintens
  deklarerade scope. PR #19-lärdomen kvarstår: ändrade filer som inte
  nämns i scope är ofta scope-läckage.
- Sök efter samma sorts hardcoded-pattern som PR:n säger sig fixa.
  PR #19 fixade hardcoded `/tjanster`/`/om-oss`/`/kontakt`, men en
  ny `render_products` introducerade hardcoded `/kontakt` igen.
  Klassiskt blindspot på nya filer.
- Om printar/loggar har present tense ("Writing X"): placera dem
  FÖRE handlingen, inte efter. Operatör ska se vad som är i flygt
  vid crash.
- För varje ny renderer som tar `dossier`: kontrollera om den
  länkar någonstans och om den pathen ska komma från scaffolden
  (`_pick_*_route`) eller bara från dossiern.
- Om sprinten ändrar `SCAFFOLD_TO_STARTER` eller liknande policy-
  förankrad dict: skapa motsvarande ADR i samma ändringsrunda (lärdom från
  PR #20:s Bugbot-iteration 1, åtgärdad via ADR 0019).
- Om sprinten har en informativ post-merge-followup som inte blockerar
  push: lägg den i `docs/current-focus.md`, men håll blocker-listan ren från
  nice-to-have.

## Blocked items

Inga öppna PR-blockers just nu. PR #25 `cursor/env-setup-9fef` är mergad
i `c073d486` och PR-branchen är inte längre kvar på GitHub.

## Do not start yet

- StackBlitz-preview, Fly-deploy, PreviewRuntime - inte påbörjat.
- Nya starters utöver `marketing-base`, `commerce-base`, `portfolio-base`
  och `docs-base` (vendor).
- Större Builder UX-utbyggnad.
- B13a arkitektur-flytt (`scripts/build_site.py` produktlogik ->
  `packages/generation/build/`) - kvarstår som öppen post men kräver
  egen sprint + sannolikt egen ADR. Destinationen är pre-allokerad i
  `.gitignore` + `.cursorignore` (kommit `b4fe4a8`).
- PR #17 / `frontend/christopher-import` - behåll som design-/copy-
  referens only. Återöppna inte PR #17 och starta inte `apps/web` förrän
  Prompt-till-sajt MVP fungerar.

## Queue

1. **Demo-baseline-fix 1D / bug-sweep round 2** - se "Next action".
   Stänger B99 (Hög, `_derive_story` platshållartext på alla 4 case),
   B100 (Medel, `_hero_cta_label` saknar `businessType`-fallback för
   booking-branscher med tomma `conversionGoals`), B103 (Medel,
   `_derive_tagline` upprepar H1), B104 (Låg, `render_about`
   country-only-medveten — kan slå ihop med B98). Förväntad effekt:
   snitt 6.5-7.5/10 i Re-Verifierings-Scout 4.
2. **Re-verifierings-Scout 4** - tredje scorecard-pass efter 1D,
   samma fyra prompter (`elektriker Malmö`, `frisör Göteborg`,
   `naprapatklinik Stockholm`, `liten e-handel som säljer keramik`),
   jämför med Scout-3-snittet 5.13/10 (rå) / ~5.9/10 (kalibrerat).
   Beslutsregel ≥7/10 OCH inget case <6.5 → Project DNA.
3. **Project DNA / follow-up semantic merge** - om Scout 4 bekräftar
   ≥7/10 och inget case <6.5: gör `merge_followup_project_input`
   semantic så följdprompt mot tone/story/tagline ger synlig
   förändring i v2. Kan behöva egen ADR. B71 (PR #28-stängd, men
   markerad som unverified av re-Scout) bör verifieras i två-pass-
   test inom samma sprint.
4. **Bug-sweep round 3 (om Scout 4 fortsatt under tröskel)** -
   prioritera B67, B80, B81, B82, B84, B85, B86, B87 + B89-B93
   (extern reviewer-triage) + B97, B101, B102 (låg-impact-rester)
   eller riktad fix på det case som dröjer.
5. **Live pipeline-matris i backoffice (operatörsförslag 2026-05-15
   sent på kvällen)** - visualisera `prompt → brief → plan → codegen
   → build → preview` som en live-uppdaterad matris i backoffice
   playground-vyn. Varje cell visar status (pending/running/ok/fail),
   senaste log-utdrag och artefakt-länk. Kombinerar befintlig
   playground-`subprocess.Popen`-runner (B04-stängning) med en
   pipeline-event-bus som `scripts/build_site.py` + `scripts/
   dev_generate.py` emitterar `phase.<name>.started/finished`-events
   till. Streamlit-realtidsuppdatering kräver `st.empty()`-pattern
   eller WebSocket-shim. Bästa demo-/granskningsverktyg vi kan bygga
   för dig (operatören). Egen sprint, ej blocker för re-Scout.
6. B49 (medel): page-map-driven sidebar för `docs-base`-startern; måste vara klar innan `course-education -> docs-base` aktiveras i `SCAFFOLD_TO_STARTER`.
7. **B59 follow-up** (parkerad - väntar på arkitekturbeslut): byte till lokal `next dev`-process som same-origin iframe på `localhost:NNNN` eller static StackBlitz-template. Ingen mer COOP/COEP-toggling. Bredare extern research om SDK-/Codeflow-/Teams-/MCP-ytan, kommersiell licens och browser-baseline ligger i [`docs/integrations/stackblitz-research.md`](integrations/stackblitz-research.md) som underlag inför arkitekturbeslutet.
8. B53 (låg): `governance/schemas/routes.schema.json` för scaffold-routes-kontraktet.
9. B47 (låg): commerce-base Shopify-handles dokumenteras eller får fallback.
10. B13a arkitektur-flytt (egen sprint, kräver ADR).
11. `write_pages` icon-bibliotek-agnostisk refactor.
12. Cancellation-followup (låg): riktig cancellation/background-jobb i playground-vyn om operatören behöver avbryta redan startade körningar.

**Vänta med ny/sista starter** tills minst följande är sant: marketing-base real codegen stabil, 4 demo-sajter kan byggas (minst 3/4), follow-up versions funkar, build-fail från fri prompt är förstådda, enkelt scorecard finns. Annars blir ny starter mer yta att felsöka utan att stärka kärnflödet.

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → skapa `backup-N` → Builder/Steward jobbar på
`main` → Scout RO-review före push → vid push-OK och clean tree får Builder
pusha direkt → Steward post-push-verifierar → uppdatera denna fil vid faktisk
fokus-/handoff-förändring → nästa etapp.

Operatörspreferens (2026-05-13): svara kort och koncist på svenska,
förklara dev-uttryck med korta parenteser första gången per
konversation. Mönstret är formaliserat i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
