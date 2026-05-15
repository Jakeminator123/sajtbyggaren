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

Last verified state: `ab74c2a` (2026-05-15, demo-baseline-fix 1A landade direkt på `main`. Konvention för denna rad: SHA pekar på senaste produkt-/kodcommit; den efterföljande Steward-bump-commiten själv (denna rad-ändring) räknas som "within bump tolerance" av `focus_check.py` och får inte ge en till bump-rundgång. `feat(builder): demo-baseline-fix 1A` (`ab74c2a`) stängde Scout-auditens topp 3 demo-blockers i ett pass: (1) `/_global-error` prerender-fel (regression/variant av B41) löst genom att lägga explicit `app/global-error.tsx` i `data/starters/marketing-base/app/` och `data/starters/commerce-base/app/` med `"use client"` och inga third-party-imports - verifierat end-to-end via `painter-palma` (marketing-base) + `atelje-bird` (commerce-base) som båda nu landar `status: ok`, `quality: ok`, `npm install + npm run build` gröna; (2) rå prompt läckte ut som `company.name`/`company.story` på rendererade sajter - `scripts/prompt_to_project_input.py` skriver om `_company_name_from_prompt` till `_derive_company_name` (läser bara `brief.businessTypeGuess` + `brief.locationHint` via en liten svensk business-type label-map: electrician -> elektriker, hairdresser -> frisör, ceramics-studio -> keramikstudio, ...) och `_derive_story` (föredrar `brief.notesForPlanner`, fallback till strukturerad svensk platshållartext, aldrig raw prompt); (3) svenska tecken förstördes i service-labels (`F Rska Gg Direkt Fr N G Rden`) - `_slugify_label` NFKD-foldar för id-fältet (`färska ägg -> farska-agg`) men `_service_label_from_text` behåller å/ä/ö i labeln, och brief `services_mentioned` Field-description + system-prompt frågar nu efter natural-language fraser på originalspråk istället för kebab-case English slugs. `slugify_site_id` NFKD-foldar också före substitution så `elektriker i Malmö` ger `elektriker-i-malmo-<tail>` (förut `elektriker-i-malm-<tail>` med `ö` kollapsad till dash). Regression-tester: `test_company_name_and_story_never_contain_raw_prompt` (låser exakta tokens från den failande real-runen `enehmsida-som-s-ljer-b-t-661e23`: `Enehmsida`, `båtari`, `2 sidor`), `test_swedish_service_labels_preserve_case` (`färska ägg direkt från gården -> Färska ägg direkt från gården` som label, ASCII-only slug), `test_slugify_label_ascii_folds_swedish_chars`, `test_company_name_uses_swedish_business_type_mapping`, `test_story_prefers_notes_for_planner` plus fyra fallback-tester. Out-of-scope per Scout/coach: ingen Project DNA / semantic follow-up merge, ingen StackBlitz/COOP/COEP, inga nya starters, ingen docs/rules-sprint utöver denna bump. `backup-19` skapad från synkad `main` innan sprintarbetet (lokalt + push). Föregående mainline-pushar samma dag: `f29688c` (Steward-bump efter rules-commit), `d072c98` (powershell-glob + cli-safety-belt rules), `8d45140` (Steward-sync efter prune-sprinten), `2acdeca` (prune-script + tester), `7b90c0c` (Steward-sync efter B60), `65f052a` (B60 fix), `dd5464f` (post-PR-#27 sanity-bump), `e057fbd` (PR #27 follow-up versions squash-merge). `backup-15` t.o.m. `backup-19` finns lokalt och på origin. Inga öppna PRs.)

Kör `python scripts/focus_check.py` som första steg i varje session.
Scriptet jämför HEAD mot SHA:n ovan + kollar git/gh-tillstånd och
varnar om något har drivit (glömd push, glömd pull, öppna oväntade
PRs, etcetera).

## Current stage

`main` är vid demo-baseline-fix 1A-commiten (`ab74c2a`) plus en Steward-bump-commit ovanpå för denna fil och `handoff.md`; faktisk HEAD-SHA syns via `git log --oneline -1` eller `python scripts/focus_check.py`. Demo-baseline-fix 1A är klar: Scout-auditens topp 3 demo-blockers stängda i ett pass — `/_global-error` build-fel borta (verifierat på `painter-palma` + `atelje-bird` med båda `status: ok`), rå prompt landar inte längre i `company.name`/`company.story` (brief-driven `_derive_company_name` + `_derive_story` ersätter prompt-as-H1/story-mönstret med Swedish business-type label-map), svenska tecken bevarade i service-labels (NFKD-fold för slugs, original-string för labels). 10 nya regression-tester i `tests/test_prompt_to_project_input.py`, 0 ruff findings, governance/rules-sync/term-coverage gröna, full pytest-suite grön (3 skipped E2E som kräver `SAJTBYGGAREN_E2E=1`).

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
Project Input, skriver den till `data/prompt-inputs/<siteId>.project-input.json`
+ sidecar `<siteId>.meta.json` (projectId/version/originalPrompt/
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
  + follow-up versions; `.cursor/settings.json`-status och stale
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
- `134df07` — `chore(workspace): perf hygiene + .generated externalization
  + viewser prettier setup`. Workspace-hygien-pass: utökad `.cursorignore`,
  ny `.cursorindexingignore` + `.editorconfig`, `.vscode/settings.json`
  får watcher-exclude + tsserver memory-bump + prettier-format-on-save,
  `scripts/build_site.py` skriver dev-preview-output till
  `../sajtbyggaren-output/.generated/<siteId>` som default (override via
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
  + Sprint 3B+3B-next-status, `docs/agent-prompts.md` ny "Baseline för
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
eller bekräftades redan raderade. `backup-6`, `backup-7`, `backup-8`,
`backup-11` och `backup-12` finns på origin som fallbacks; äldre
`backup-1`-`backup-5` finns också kvar. Kvarvarande remote
arbetsbrancher som inte ska raderas utan separat beslut:
`feat/backoffice-trace-playground-cleanup` (ingen egen PR, inte ancestry-
mergead efter squash) och `frontend/christopher-import` (PR #17 stängd
utan merge, reference only).

## Current active sprint

Ingen pågående produktimplementation på `main`. A-mini cleanup
(B51/B52/B54/B55 + B53 registrerad), Prompt-till-sajt MVP v1,
mini-sprinten som gjorde PromptBuilder till enda primära promptyta, follow-up
prompt versions, PR #23 backoffice trace/playground, PR #22 `portfolio-base`
starter, B48 follow-up-semantik, PR #24 `docs-base` starter, B45
kontakt-route-propagation, B50 route-hardening, Codex-IDE agent-parity-regeln,
mergead branch-cleanup, PR #26 produktkompass/agentläsordning,
orkestrator-playbooken för längre fleragentpass, StackBlitz preview
payload-hardening (ADR 0021 + B59 dokumentation) och PR #27 follow-up
prompt versions (versionerade Project Input-snapshots, stabil
`projectId`/`version` i RunHistory, repo-`.venv` Python preferred) är
klara. Inga öppna PRs efter PR #27-merge.

## Next action - direktiv till nästa agent

**Verifiera demo-baseline-fix 1A mot 4 testfall + besluta nästa fokus.**
Demo-baseline-audit har levererats (totalt-snitt 4.1-4.6 / 10 över de
fyra testfallen elektriker Malmö, frisör Göteborg, naprapatklinik
Stockholm, keramik-e-handel) och topp 3 demo-blockers är åtgärdade i
`ab74c2a`. Nästa naturliga steg är en kort verifierings-Scout/Grind
som kör de fyra prompterna skarpt mot fixad kod (`OPENAI_API_KEY` satt,
`python scripts/dev_generate.py` per case) och scorar om sajterna nu
ligger närmare 6/10 på första generationens kvalitet. Tre kvarstående
gap från Scout-auditen som inte är lösta i 1A:

1. `contact.*` är fortfarande 100% placeholder (`+46 8 000 00 00`,
   `kontakt@example.se`, "Adress saknas") — brief-schemat saknar
   kontaktfält. Egen sprint, kräver schema-justering eller
   prompt-helper-tillägg.
2. `trustSignals` är alltid tom efter prompt → "Varför oss"-sektion
   blir tunn. Kan fyllas med generic-by-business-type-mall, eller
   låta briefModel returnera 2-3 trust-fraser.
3. `merge_followup_project_input` bevarar fortfarande `tone`, `story`,
   `tagline`, `trustSignals` byte-för-byte — operatör som ber om
   "byt ton" eller "ändra story" får v2 utan synlig förändring.
   Detta är Project DNA / semantic patching-sprinten som väntar.

Också: `detect_language()` i `packages/generation/brief/extract.py` har
hård SWEDISH_HINTS-lista som missar korta svenska prompts utan stop-ord
(t.ex. "frisör Göteborg" → returnerar "en"). Real briefModel kompenserar
oftast men den latenta buggen kvarstår.

Verifierings-Scout-rapporten bör styra om nästa Builder-sprint blir:
(a) demo-baseline-fix 1B (kontakt + trustSignals + språk-detection),
(b) Project DNA / follow-up semantic merge, eller
(c) annan blocker som dyker upp på de skarpa körningarna.

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

1. **Verifierings-Scout för demo-baseline-fix 1A** - kör fyra
   testfall skarpt mot fixad kod, scora om första generationens
   kvalitet ligger ≥6/10. Levererar mini-scorecard + go/no-go på
   nästa sprint.
2. **Demo-baseline-fix 1B (om verifierings-Scout indikerar)** -
   åtgärdar de tre kvarstående gap som 1A inte täckte: kontakt-
   placeholder, tom trustSignals, hård SWEDISH_HINTS-lista i
   `detect_language()`. Kan kräva brief-schema-tillägg och i så
   fall en ny ADR.
3. **Project DNA / follow-up semantic merge (vänta)** - så fort
   verifierings-Scout bekräftar att första generationen ligger
   nära 7/10 är detta nästa naturliga steg: göra
   `merge_followup_project_input` semantic så följdprompt mot
   tone/story/tagline ger synlig förändring i v2.
4. B49 (medel): page-map-driven sidebar för `docs-base`-startern; måste
   vara klar innan `course-education -> docs-base` aktiveras i
   `SCAFFOLD_TO_STARTER`. Antingen återinför Nextra-theme-docs `Layout`
   eller bygg lokal `_meta.ts`-/filsystem-driven nav. Coach-beslut:
   tas EFTER demo-baseline-audit, inte före.
4. **B59 follow-up** (parkerad - väntar på arkitekturbeslut): byte till
   lokal `next dev`-process som same-origin iframe på `localhost:NNNN`
   eller static StackBlitz-template. Ingen mer COOP/COEP-toggling.
5. B53 (låg): `governance/schemas/routes.schema.json` för scaffold-
   routes-kontraktet (egen schema-sprint, mönster från B22).
6. B47 (låg): commerce-base Shopify-handles dokumenteras eller får
   fallback. Egen e-commerce-sprint, ej blocker idag.
7. B13a arkitektur-flytt (egen sprint, kräver ADR).
8. `write_pages` icon-bibliotek-agnostisk refactor (förebygger
   lucide-typen av starter-vs-codegen-konflikt; ADR 0020:s
   "INTE beslutar"-sektion).
9. Cancellation-followup (låg): riktig cancellation/background-jobb i
   playground-vyn om operatören behöver avbryta redan startade körningar.

**Vänta med ny/sista starter** tills minst följande är sant: marketing-
base real codegen stabil, 4 demo-sajter kan byggas (minst 3/4), follow-up
versions funkar, build-fail från fri prompt är förstådda, enkelt
scorecard finns. Annars blir ny starter mer yta att felsöka utan att
stärka kärnflödet.

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
