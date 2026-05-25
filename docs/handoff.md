# Handoff – Sajtbyggaren

**Datum:** 2026-05-25 natt (**post-merge sync efter PR #70 Sprintvakt V1
koordineringsserver, ovanpå parallell-team-uppsättningen (PR #61, #64),
Viewser/christopher-ui-integration (PR #62), wizard-directives + Gap 1+3
(PR #63), sourceUrl-assets (PR #66), AI bug review-CI (PR #67) och
restaurant-hospitality Week 1 (PR #68)**). Verifierad `main` är
`cb5c837548125bd94740f19e3b4a7acfa89b44cf`
(`feat(tooling): add Sprintvakt V1 coordination guard (#70)`). Main health
är grön: governance, rules-sync, strict term coverage, builder-smoke och
sprintvakt-suiten (14 passerar) körda på fix-commit `419d3f1` innan merge.
`python scripts/sprintvakt_check.py` ger `Sprintvakt check: OK` på en synkad
`jakob-be`. PR #70 tillförde lokal filbaserad workboard
(`docs/workboard.json`), gap-modell (`docs/gaps/`), collision-checker
(`scripts/sprintvakt_check.py`), dependency-free MCP-kompatibel stdio-server
(`tooling/sprintvakt_mcp/`), tester och agent-prompt — inga ändringar i
`scripts/build_site.py`, `packages/generation/**`, `apps/viewser/**` eller
`governance/policies/**`. Path-overlap-buggen i `paths_overlap` som Bugbot
flaggade som HIGH är fixad och täckt av en explicit regression-test
(`test_paths_overlap_distinguishes_literals_and_globs` —
`paths_overlap("docs/workboard.json", "docs/sprintvakt-mcp.md") is False`).

**Direkt nästa spår — vänta tills operatör väljer:**

1. **Path B / section-driven renderer i `scripts/build_site.py:write_pages`**
   är dokumenterad i `docs/scaffold-runtime-extension-needed.md`. Den är
   nästa stora backend-jobb (~20-26h, dedikerad session). Den låser upp
   `restaurant-hospitality` fullt + ger nollkostnad för 4 framtida scaffolds
   (clinic-healthcare, portfolio-creator, real-estate, professional-services).
   Kräver explicit operator-OK innan start eftersom estimatet är stort.
2. **Backend-Gap 4 + 5** från `docs/backend-handoff-2026-05-22.md` är öppna
   men inte akuta — kan tas som mindre sessioner.
3. **Sprintvakt V1.1 follow-up**: tre AI-bug-review-fynd från PR #70:
   - HIGH (92%, 8/10): `generate_agent_prompt` hanterar inte file-only
     queued gaps i `docs/gaps/*.md` — bara `workboard.json.activeGaps`.
   - MEDIUM (84%, 7/10): `reserve_paths` appendar utan att ersätta
     tidigare reservationer för samma `gapId` — risk för falska röda
     collisions vid upprepade anrop.
   - LOW (74%, 6/10): `scripts/sprintvakt_check.py` muterar `sys.path` för
     att importera `tooling.sprintvakt_mcp` — funkar från repo-rot men
     skört i andra import-kontexter.
   Inte blockerande för V1-koordinationen; bör landa innan en V2-utbyggnad.
4. **Annat smalt produktspår** om operatör vill växla — bug-sweep mot
   låg-prio B-IDs, eller någon yta kring Project Input/builder som
   mini-evalen pekade på.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project DNA
V2 tills sprinten är formellt vald. Rör inte B125 om det inte uttryckligen
väljs.

**Filosofi B (parallellt arbete) är nu fullt operativ:**

- `jakob-be` är **permanent arbets-branch** för backend/generation/
  governance/scripts/runtime/merge-review. Solo-ägd, `--force-with-lease`
  efter varje main-merge är OK enligt `governance/rules/branch-scope-ui-ux.md`.
- `christopher-ui` är **permanent arbets-branch** för UI/frontend/viewser/
  visual-polish. Reserverade paths: `apps/viewser/components/**`,
  `apps/viewser/app/**/*.tsx`, `apps/viewser/app/**/*.css`,
  `apps/viewser/public/**`.
- PR går alltid mot `main`, aldrig mot motpartens arbets-branch. Efter
  squash-merge synkar respektive ägare med `git reset --hard origin/main`
  + `git push --force-with-lease`. Pulla aldrig en redan squash-mergad
  branch — gör `reset --hard origin/main` i stället.
- Workboard (`docs/workboard.json`) säger vem som äger vad.
  `python scripts/sprintvakt_check.py` ska vara grönt innan nytt arbete
  startar.

**Pågående parallellt:**

- PR #69 (`docs: add product north star runtime ladder`) — docs-only,
  öppen draft, grön CI, väntar operator-OK.

**Öppna gaps på workboarden:** inga aktiva eller queuade gaps just nu.
Workboarden är ren och redo att ta första riktiga gapen via
`create_gap` med `dryRun:true` → `confirm:true`-flödet.

**Christopher-scope-leak-precedent från PR #68:** två backend-commits
(`acc6265` planner-fix i `plan.py`, `a44740a` resolver-fix i `resolve.py`)
togs på `christopher-ui` med `[scope-leak] Approved by operator`-tag
eftersom de var rena dispatch-tabell-tillägg utan runtime-beroende. Detta
är **operator-approved engångsundantag, inte permanent norm**. Framtida
backend-kontrakt-ändringar ska gå via separat backend-PR på `jakob-be`,
om inte operatören explicit godkänner ett scope-leak i förväg.

**Startprompt för ny agent:**

[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md)
har en färdig första prompt med läs-ordning, sanity-kommandon, och
gränser för vad agenten får göra utan att fråga. För Sprintvakt-agent
finns separat prompt i [`docs/agent-prompts/sprintvakt.md`](agent-prompts/sprintvakt.md).

**Senaste landade spår sedan c0b59fbe (PR #60), nyast först:**

- `246569a` docs: bump verified state to cb5c837 after PR #70 Sprintvakt V1 (denna docs-bump på `jakob-be`, ej PR:ad än).
- `cb5c837` PR #70 / Sprintvakt V1 koordineringsserver + MCP
  (`feat(tooling): add Sprintvakt V1 coordination guard`). Path-overlap-fix
  i `419d3f1` ovanpå initial `b72fb6f`. 14 sprintvakt-tester gröna.
- `839d0c8` PR #68 / restaurant-hospitality Week 1 declarative expansion
  (`feat(week1): restaurant-hospitality scaffold + 11 soft dossiers + 14 variants`).
  Inkluderar Christophers två `[scope-leak]`-commits i `plan.py` + `resolve.py`.
- `7e900d2` PR #67 / AI bug review-workflow-steg i CI
  (`ci: add AI bug review workflow step`). gpt-5.4 + repo-specifik prompt.
- `d709864` PR #66 / sourceUrl-asset-uploads med stream-safe fetch
  (`fix(assets): sourceUrl uploads with stream-safe fetch`). Supersededar
  stängd PR #65.
- `89f14a1` PR #64 / branch-naming-konventioner för parallellt teamarbete
  (`docs(ownership): add branch-naming conventions for parallel team work`).
  Permanenta arbets-branches `jakob-be` + `christopher-ui` formaliserade.
- `f9312ec` PR #63 / wizard-directives `useCustomColors` + `scaffoldHint`
  (`feat(discovery): respect wizard directives`). Backend-Gap 1 + 3 stängda.
- `7240fcd` PR #62 / viewser-christopher-ui builder-workflow-integration
  (`feat(viewser): integrate christopher-ui builder workflow`).
- `a32152d` PR #61 / team parallel workflow + ownership map
  (`docs: add team parallel workflow and ownership map`).
- `0252820` Steward-sync efter PR #60
  (`docs(steward): sync after starter auditor merge`).
- `c0b59fb` PR #60 / Starter Candidate Auditor v1, read-only
  (`tooling: Starter Candidate Auditor v1 (read-only) (#60)`) — den verified
  state som c0b59fbe-blocket i [`docs/current-focus.md`](current-focus.md)
  avser.

För djupare commit-historik före c0b59fbe (PR #60), se
`git log --oneline origin/main` eller
[`docs/current-focus.md`](current-focus.md):s "Föregående produkt-läge"-block.

## Hur agenten jobbar — Filosofi B + branch-policy

Standardflödet definieras i tre källor:

- [`docs/ownership-map.md`](ownership-map.md) — vem äger vad, branch-konventioner, livscykel för arbets-branch.
- [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md) — Steward/Scout/Builder-roller, fyra guards, push-disciplin, multi-line commits på Windows.
- [`governance/rules/branch-scope-ui-ux.md`](../governance/rules/branch-scope-ui-ux.md) — off-limits-paths på `christopher-*`/`frontend/*`/`ui/*`/`ux/*`-branches.

**Tre nivåer:**

1. **`main`** är sanningen. Pushas aldrig med `--force`. Inga direkta pushes utan operator-OK när det är produktkod — bara docs-/governance-/steward-pushes är OK direkt enligt `branch-discipline.md` "Mainline-steward"-sektion.
2. **Permanenta arbets-branches** (`jakob-be`, `christopher-ui`) är solo-ägda. PR till `main` när det är dags att släppa. Efter merge: `reset --hard origin/main` + `--force-with-lease`-push.
3. **Tillfälliga feature-branches** (`jakob/<x>`, `frontend/<x>`, `cursor/<x>`, `tooling/<x>`) startas från `main`, PR:as till `main`, raderas efter merge.

**Sprintvakt V1 som koordinationslager:**

- `docs/workboard.json` håller `people`, `reservedPaths`, `queuedGaps`, `activeGaps`, `completedGaps`.
- `scripts/sprintvakt_check.py` (CLI + `--json`/`--strict`) körs som lokal collision-guard.
- `tooling/sprintvakt_mcp/server.py` är en dependency-free MCP-kompatibel stdio JSON-RPC-server med nio tools (`get_workboard`, `list_gaps`, `create_gap`, `reserve_paths`, `detect_collisions`, `suggest_next_gaps`, `generate_agent_prompt`, `validate_workboard`, `post_merge_sync_instructions`).
- Mutationer kräver `dryRun:false` + `confirm:true`. Skrivning är begränsad till `docs/workboard.json`, `docs/gaps/**`, `docs/sprintvakt-log.md`.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator för småföretagare. Mål: stabilt kärnflöde
`prompt → företagshemsida → preview → följdprompt → ny version`.
Sanningskällan är `governance/` (JSON-policies + JSON-Schemas + ADR).
Runtime + kund-UI ligger i `packages/` + `apps/`. Streamlit-backoffice
i `backoffice/`. Se
[`docs/product-operating-context.md`](product-operating-context.md) för
produktkompass.

## Vad funkar idag (post `cb5c837` / Sprintvakt V1)

### Governance + guards

- 18 policies + matchande schemas under `governance/schemas/`. Validering via `python scripts/governance_validate.py`.
- Fem automatiska checks körs på push + PR via GitHub Actions: `governance_validate.py`, `rules_sync.py --check`, `check_term_coverage.py --strict`, `pytest`, `ruff check .`. `tests/test_docs_freshness.py` är en sjätte mjuk guard mot doc-drift (AGENTS.md ruff-baseline + dossier README-status).
- Ruff baseline = **0 findings**. Inga `noqa`-tillägg utan ADR.
- Cursor Bugbot (`.cursor/BUGBOT.md`) granskar PRs och postar trådar; autofix är **av**. PR #67 lade till en separat `@sajtbyggaren-ai-bug-review`-workflow (gpt-5.4 + repo-specifik prompt) som postar topp-3-fynd som vanlig PR-kommentar.

### Brief, plan, build

- **briefModel** via OpenAI structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `briefSource`: `real` / `mock-no-key` / `mock-llm-error`.
- **planningModel** via shared `packages.generation.planning.produce_site_plan`. Både `scripts/build_site.py` och `scripts/dev_generate.py` använder samma helper.
- **codegenModel** (scope: `marketing-base` + `commerce-base` via deterministic-v1) i `packages/generation/codegen/` med Quality Gate (typecheck / route-scan / build-status / policy-compliance) och Repair Pipeline. Real codegen för andra starters är V2-scope (ADR 0017).

### Scaffolds, dossiers, variants

- **3 scaffolds:** `local-service-business` + `ecommerce-lite` (fullt runtime-aktiva via `_RUNTIME_SCAFFOLD_HINTS`), `restaurant-hospitality` (planner-aktiv via PR #68; runtime aktiveras när Path B / section-renderer landar — se [`docs/scaffold-runtime-extension-needed.md`](scaffold-runtime-extension-needed.md)).
- **11 soft dossiers** efter PR #68 Week 1-expansion. Wizard-page-label → capability-map är fullt wired efter PR #68 + PR #63 (Gap 1 + 3 stängda).
- **18 variants** över LSB + ecommerce-lite + restaurant-hospitality. Wizard step-2 exponerar alla via `vibesForScaffold()`.
- **5 starters på disk**, 2 mappade i `SCAFFOLD_TO_STARTER` (`marketing-base`, `commerce-base`). `restaurant-hospitality` återanvänder `marketing-base` (PR #68).

### Prompt-till-sajt + follow-up versions

- `/api/prompt` i Viewser tar fri prompt → spawnar `scripts/prompt_to_project_input.py` → `runBuild` med whitelisted dossier-path-override → svar med `buildStatus` (ok/degraded/failed).
- Follow-up versions: immutable `<siteId>.vN.project-input.json` + `<siteId>.vN.meta.json`-snapshots i `data/prompt-inputs/`. `projectId` + `version` bevaras. PromptBuilder är enda promptytan i Viewser-home.
- StackBlitz preview fungerar för Chromium-baserade browsers; Safari/Firefox behöver server-byggd fallback (B125, ADR 0025 — parkerad, se nedan).

### Sprintvakt V1 (PR #70)

- Lokal workboard + collision-checker + MCP-server (se "Hur agenten jobbar" ovan).
- 14 tester gröna. Path-overlap fixad (`paths_overlap("docs/workboard.json", "docs/sprintvakt-mcp.md") is False`).

## Vad är parkerat

- **B59 / B125 — embedded StackBlitz-preview för Safari/Firefox.** WebContainer-runtime kräver iframe-attributet `credentialless` som bara finns i Chromium. ~25-35 % av svenska SMB-kunder behöver server-byggd fallback. ADR 0025 + B125-rapport finns; väntar på operatörens implementations-OK (Vercel preview-deployments, lokal `next dev` same-origin iframe eller static export embed är kandidater). Rör inte `apps/viewser/lib/stackblitz-files.ts`, `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/next.config.ts` eller `tests/test_viewser_files.py` utan separat sprintbeslut.
- **Embeddings, SNI-runtime-konsumtion, variant-promotion, nya starters/starter-importer, Project DNA V2** — alla parkerade tills explicit sprint vald. SNI 2025-taxonomin finns under `data/taxonomies/sni/` och konsumeras read-only av Backoffice-diagnostik (ingen runtime-koppling än).

## Nästa konkreta uppgift

Se [`docs/current-focus.md`](current-focus.md) → **"Direkt nästa fokus"**.
Kort: Path B / section-renderer är största spåret men kräver operator-OK;
Sprintvakt V1.1 follow-up-fynd är queueade som ej akuta; backend-Gap 4 + 5
är öppna.

## Operatörspreferenser

- **Språk:** alltid svenska. Riktiga svenska tecken (`å`, `ä`, `ö`). Se [`governance/rules/always-swedish.md`](../governance/rules/always-swedish.md).
- **Reply-style:** kort + koncist. Förklara dev-uttryck med korta parenteser första gången per konversation (operatören är inte utvecklare i grunden). Se [`governance/rules/reply-style.md`](../governance/rules/reply-style.md).
- **Backup-branches:** kvar i historisk practice för sprint-flöde på `main`. För `jakob-be`/`christopher-ui`-passen är det inte längre standard — Filosofi B är operatörens explicit-valda alternativ.
- **Create-PR-knappen i Cursor:** användaren kan av misstag trycka den. Standard är att inte öppna PR; fråga operatören om PR verkligen är avsikten.
- **PowerShell + git commit multi-line:** Här-string piped till `git commit -F -` är primär lösning (skapar ingen disk-fil). Fallback är temp-fil under `$env:LOCALAPPDATA\Temp` — aldrig `$env:TEMP` (resolveras till `C:\WINDOWS\TEMP` i elevated agent-shell). Aldrig `.commit-msg.tmp` i repo-roten (race med `git add -A`). Detaljerat i `governance/rules/branch-discipline.md`.
- **Cursor IDE git-editor pipe error på Windows** är vanligt (`ENOENT \\\\.\\pipe\\vscode-git-...sock`). Fall tillbaka till `git commit -F` från shell direkt.

## Bugbot + AI bug review

Två oberoende automatiska reviewers körs på alla PRs:

- **Cursor Bugbot** (`.cursor/BUGBOT.md`). Trigger: varje push till PR + draft-PRs. Autofix är **av** — Bugbot postar PR-kommentarer som review-trådar. Manuell granskning + fix krävs. Vanligt fall: nya commits flyttar inte tidigare trådar till "outdated" — verifiera mot senaste commit-SHA innan slutsats om fynd kvarstår.
- **`@sajtbyggaren-ai-bug-review`** (PR #67, gpt-5.4 + repo-specifik prompt). Postar topp-3-fynd som vanlig PR-kommentar med probability + impact-score.

Vid PR-merge: kontrollera (a) check `SUCCESS`/`NEUTRAL` med 0 aktiva trådar,
(b) `mergeStateStatus == "CLEAN"`, (c) ingen oadresserad HIGH-severity. För
direkt-`main`-flöde (steward-pushes på docs/governance): inga
Bugbot-iterationer, men Scout-agent kan göra RO-review före push.

Full PR-loop-rutin: [`governance/rules/bugbot-pr-loop.md`](../governance/rules/bugbot-pr-loop.md).

## Pre-push self-review checklist

Innan `git push origin <branch>` (alla branches):

1. `git diff origin/<branch>..HEAD --stat` — jämför mot deklarerat scope.
2. Sök efter samma hardcoded-pattern som sprinten säger sig fixa (klassiskt blindspot på nya filer).
3. Log-/print-meddelanden i present tense ska komma FÖRE handlingen, inte efter, så operatören ser vad som är i flygt vid crash.
4. Nya renderers/komponenter som tar `dossier` — kontrollera om de länkar via scaffolden (`_pick_*_route`) eller dossiern.
5. Ändringar i `SCAFFOLD_TO_STARTER` eller `data/starters/<starter>/` kräver ADR i samma PR.
6. Sprintvakt: `python scripts/sprintvakt_check.py` ska vara grönt; `detect_collisions` på sprintens paths ska vara `green` (eller dokumenterad `yellow` med operator-OK).

## Standard loop (referens)

Full rutin i [`docs/agent-handbook.md`](agent-handbook.md). Tio steg; steg 8
(Steward post-push-verifierar och uppdaterar `current-focus.md` +
`handoff.md` vid faktisk fokusförändring) är agentens ansvar, inte
operatörens.

```text
0. Drift-check (python scripts/focus_check.py).
1. Sprintvakt-check (python scripts/sprintvakt_check.py) — collision-guard.
2. Skapa nästa backup-N från synkad main vid main-arbete;
   för jakob-be/christopher-ui hoppas detta steg.
3. Builder/Steward jobbar på arbets-branchen.
4. Scout-agent RO-review före push vid produktkod.
5. Operatör + extern reviewer beslutar vid stora ändringar.
6. Final sanity: governance + rules_sync + term-coverage + sprintvakt-check.
7. Commit + push.
8. Steward verifierar pushed SHA, git status, focus_check,
   origin == local, och docs-beslut. Uppdatera current-focus/handoff när
   HEAD, active sprint, risk/blocker eller arbetsflöde ändras.
9. Nästa etapp.
```

## Tidigare djup-historik

Detaljerade session-narrativ från perioden före 2026-05-25 har städats ur
denna fil för att hålla den hanterbar (tidigare 1086 rader, nu ~270).
Källor för bakgrund:

- `git log --oneline origin/main` för full commit-historik.
- [`docs/current-focus.md`](current-focus.md) "Föregående produkt-läge"-block för verified-state-progression.
- [`docs/known-issues.md`](known-issues.md) för B-ID-historik (aktiva, misplaced, unknown, stängda).
- [`governance/decisions/`](../governance/decisions/) för ADR-spår.
