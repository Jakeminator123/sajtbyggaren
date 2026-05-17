# Handoff – Sajtbyggaren

**Datum:** 2026-05-17 (post-PR #29 `list_open_bugs + bug-scope-discipline rule` och post-PR #30 `Backoffice maintenance and enabled toggles`. Två operatör-supplied review-fynd stängdes på PR #30:s branch innan merge: pinned-disabled-scaffold fail-loud-test + sessionsförklaring i `view_safe_cleanup`. Aktuellt bug-scope: 19 aktiva, 15 misplaced, 6 unknown, 50 stängda — låst av sammanfattningsraden i `docs/known-issues.md`. Nästa konkreta uppgift är fortsatt demo-baseline-fix 1C (B88 + B94 + B95 + B96) eftersom re-Scout-mätningen från 2026-05-15 visade snitt 5.54/10.)
**Aktuell repo-HEAD på `main`:** Steward-bump-commit ovanpå `b3a32fc` (PR #30 squash-merge), som ligger ovanpå `c2c6f39` (PR #29 squash-merge) och `38d0af9` (`feat(maintenance): opt-in auto-prune via .env caps`). Kör `git log --oneline -1` eller `python scripts/focus_check.py` för faktisk HEAD-SHA. Föregående produktbaseline: `948d2f9` (`chore(rules): add read-only-shell-windows rule`) och `885431b` (PR #28 demo-baseline-fix 1B + bug-sweep).
**Aktiv branch:** `main`. PR #29 och PR #30 är mergade; PR-brancherna `cursor/bug-scope-disciplin` och `cursor/backoffice-rensning-styrning-7c51` är raderade både lokalt och remote. `backup-21` finns på origin från PR #28-sprintstart; nästa backup blir `backup-22` när 1C startar. Inga kända öppna PR-blockers.
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
- Befintliga aktiva starterflöden är oförändrade: `marketing-base` för real codegen-scope och `commerce-base` för ecommerce-lite deterministic-v1 enligt tidigare ADR-spår.

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

Se `docs/current-focus.md` → **"Next action"**. Kort version: PR #29 + PR #30 är mergade. Nästa är **demo-baseline-fix 1C (B88 + B94 + B95 + B96)** — riktad fix mot top synliga demo-blockers efter re-Scout-mätningen 5.54/10. Förväntad effekt: snitt 6.5-7.0/10. Lokal sprint på `main` (skapa `backup-22` först), ingen PR. Efter 1C: re-Scout med samma fyra prompter, sedan Project DNA om snitt ≥7/10 och inget case <6.5, annars bug-sweep round 2.

Bakgrunden är att demo-baseline-fix 1B + bug-sweep är mergead i `885431b` via PR #28. Den stängde:

- **B64/B65** — Site Brief har nu `companyName`, `contactPhone`, `contactEmail`, `contactAddress`; prompt-helpern använder explicita bolags-/kontaktvärden före fallback. ADR 0022 dokumenterar schema-utökningen.
- **B66** — `render_home()` renderar inte "Varför oss" när `trustSignals=[]`.
- **B69** — Quality Gate route-scan får alla emitterade default-routes + dossier-routes, så `/om-oss` granskas även när scaffolden markerar den `required:false`. Aggregate-status ändrades inte; route-scan-only failure är fortsatt degraded enligt befintligt kontrakt.
- **B70/B78** — Viewser localhost-/dossier-guards är härdade för IPv6 Host-header och symlink traversal.
- **B71/B72/B73** — follow-up merge-docstring matchar konservativ byte-stabil semantik, `listRuns()` läser JSON bara för limit-survivors, tagline fallback saknar Project Input-jargong.
- **B74/B75/B76/B77/B79/B83** — nice-to-have-spåret landade: dev_generate route-manifest, Project Input fail-closed schema, site-plan i Run Details, dossier-vs-starter component collision, svensk rationale och slug-suffix för service-kollisioner.

Verifiering i PR #28: ruff 0 findings, full pytest grön (3 skipped E2E/slow), governance/rules/term checks gröna, Viewser `npm run build` grön, smoke-builds `elektriker Malmö` + `frisör Göteborg` båda `status=ok`, `quality=ok`. Bugbot var inte aktiv; GitHub governance, builder-smoke och secret-scan var gröna.

**Nästa uppgift: Demo-baseline-fix 1C (B88 + B94 + B95 + B96).** Re-
Verifierings-Scout rapporterade snitt 5.54/10 (case-spann 3.9-6.25),
audit-konfidence 7/10. Alla fyra builds var `status=ok`/`quality=ok`.
Beslutsregeln triggar (snitt <7/10 OCH e-handel-case 3.9 <6.5) →
riktad fix på top synliga demo-blockers:

- **B88** (kontakt-placeholder dev-jargong syns på alla fyra case som
  `"Adress saknas - uppdatera Project Input"` i publik `<address>`).
- **B94** (tom team-grid renderas alltid på `/om-oss`; conditional
  section render likt B66).
- **B95** (`locationHint="Sverige"` utan stad blir ortstag i hero
  på e-handel-case; bredare variant av B91).
- **B96** (hero-CTA "Begär offert" hardcoded i `render_home` oavsett
  `scaffoldId`/`conversionGoals`; e-handel borde få "Shoppa nu").

Förväntad effekt: snitt 6.5-7.0/10. Project DNA / semantic follow-up
merge (inkl. två-pass-verifiering av B71) får vänta tills vi är över
7/10. B97, B98 är låg-impact och kan vänta. Övriga öppna B-IDs:
B67, B80, B81, B82, B84, B85, B86, B87 (deferred från Grind),
B89-B93 (extern reviewer-triage), B49, B53, B47, B13a, BO4-followup-
cancel (äldre). StackBlitz B59 är fortsatt parkerad.

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
