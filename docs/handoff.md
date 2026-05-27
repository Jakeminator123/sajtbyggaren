# Handoff – Sajtbyggaren

**Datum:** 2026-05-27 UTC, post cloud-grind-batch (7 PRs mergade på
~2h fm: #125, #127, #128, #129, #130, #131, #132) + PR #131-follow-up
(`c9a730b`, smoke-test drain-thread refaktor) + PreviewRuntime Bite A
skeleton (`bb6ab2e`) + tre runda reviewer-fynd-fixar (`3e660ea`,
`e9e3f32`, `44ea54b`, `e60f493` på smoke-test cleanup;
`8358326` `test_no_legacy_terms`-fix; `19480dc` fail-loud i
`currentKind()`; `e2f857c` narrow placeholder-copy-scan) + sync-merge
mot `origin/main` (`cbe1ba9`) + steward-bumps + extern-reviewer-
cleanup-batch 2026-05-27 efm (`d60bb58` bot-report-verification-regel,
`abff654` placeholder-scan case-insensitive, `58cfe20` fly-slot-
reconciliation till ADR 0028 nivå 3 i README) + extern-reviewer-
analys 2 (`8fb24e4` B157 + GAP-windows-safe-rebuild-pipeline registrerad
— WinError 5 rmtree på live `node_modules`, arkitektur-anti-pattern att
rebuilda ovanpå aktiv preview-katalog; ingen kodfix i denna batch) +
Cursor BugBot suggestions 1-3 (`82b9f99` defensive cleanup i b154-test,
`23b473e` smala placeholder-scan till `.tsx`/`.jsx` only, `f446be1` AND
→ OR i `_has_contact_cta`, pushade direkt av BugBot) + GPT P2 Badge
fix (`0b40b8d` accept scaffold-specific contact-routes inkl.
`/kontakta-oss` + `/hitta-hit`). Verifierad `jakob-be` är `0b40b8d`.
`origin/main` ligger kvar på `4d879177` (25 commits efter `jakob-be`).
Draft-PR #133 (`jakob-be → main`) är öppen — alla reviewer-trådar
adresserade, redo för ready-flip + merge. Bug-count: 16 aktiva (B157 ny).

**PreviewRuntime Bite A (`bb6ab2e`):** typkontrakt + registry + 3
adapter-stubs i `packages/preview-runtime/`. Skelett bara — alla
adaptrar returnerar `unsupported` med tydlig "Bite B-wiring saknas"-
text. Inga existerande filer ändrade. ADR 0028 + ADR 0030 är de
canonical-källor som Bite A följer; `PreviewRuntimeKind` är låst till
naming-dictionary v17 (`stackblitz | local | fly`). Bite B wirear
local + stackblitz mot `apps/viewser/lib/local-preview-server.ts` resp.
`apps/viewser/lib/stackblitz-files.ts` när tsconfig path-alias eller
npm-workspace etableras. Bite C (`viewer-panel.tsx` UI-refaktor) kräver
Christopher-koordinering eftersom `apps/viewser/components/**` är hans
lane per `governance/rules/branch-scope-ui-ux.md`.

**Nya PRs sedan föregående checkpoint (i mergeordning):**

- PR #125 — fix(discovery): honor wizard clears across versioned fields.
- PR #127 — fix(viewser): block Python-backed actions on hosted Vercel
  (501 på `/api/prompt`, `/api/build`, `/api/scrape-site` när VERCEL=1).
- PR #128 — docs(gaps): file followup-prompt-content-passthrough + ADR
  0034 draft (nya B155, operatör-beslut väg (b) ärlig först).
- PR #129 — feat(quality-gate): add contact-CTA + placeholder-copy
  checks som non-blocking warnings. Follow-up `8269800` separerade
  blocking/warning i summary efter reviewer-fynd.
- PR #130 — test(api): add HTTP smoke-test för `/api/prompt`-bron
  (Bite 2 från LLM Golden Path handoff).
- PR #131 — fix(builder): close B154 — TDZ at dev hydration on
  deterministic codegen. Lockfile-alignment + chunk-heuristik-smoke
  + `_npm_install_inputs_changed` diffar nu lockfile-bytes. B156
  registrerad för browser-hydration follow-up. Follow-up `c9a730b`
  (direct push till `jakob-be` efter merge): drain-tråden i
  `tests/test_b154_next_dev_tdz.py` skriver nu direkt in i en delad
  `output`-lista istället för att queue:a, så assertionen ser TDZ-fel
  som dyker upp *efter* Next.js ready-raden (precis B154-fönstret).
- PR #132 — docs(steward): cleanup pass — 8 filer arkiverade till
  `docs/archive/` (5 dated handoffs + 3 completed reports, ~78 KB).

**MCP-server-status:** Sprintvakt-servern exponerar 14 tools efter
PR #77 (`get_workboard`, `list_gaps`, `create_gap`, `activate_gap`,
`complete_gap`, `reserve_paths`, `detect_collisions`, `suggest_next_gaps`,
`generate_agent_prompt`, `validate_workboard`, `post_merge_sync_instructions`,
`post_message`, `list_messages`, `ack_message`). Agent-inbox-tools är
bakade av append-only `docs/agent-inbox.jsonl` med deterministisk
message-id + idempotent ack. Operatörens `.cursor/mcp.json` är
konfigurerad med `PYTHONPATH` så `python -m tooling.sprintvakt_mcp.server`
startar utan ModuleNotFoundError. Editable install (`pip install -e .`)
krävs en gång per venv enligt ADR 0029.

**Direkt nästa spår — operatörsbeslut + Gap-fixar:**

1. **Backend-Gap fixar (post-C4-audit)** — Gap 1-11 är nu stängda efter Gap 10-merge i PR #122. Detaljer i `docs/current-focus.md`.
2. **Sync-PR `jakob-be → main`** — `jakob-be` är nu 38 commits framför `origin/main`. Bra läge för en sync-PR (operatörens beslut).

**Parkerade lanes (väntar trigger):**

- **Path B / section-driven renderer** — dokumenterad i `docs/scaffold-runtime-extension-needed.md` + `docs/path-b-backend-scout.md` (~22-28h). Lane 2 är klar (B137-B141 stängda 2026-05-22) så Path B är inte längre tekniskt blockad — väntar bara på operatörsbeslut om sprint.
- **Christophers `GAP-backend-build-trace-endpoint`-PR** — Christopher har implementerat hela gapet på `christopher-ui` under operator-OK scope-leak. Han har inte PR:at än. Jakob är reviewer. När PR öppnas: granska scope-leaken (medvetet brutet jakob-lane), kontrollera att workboard.json `owner` är kvar på `jakob` (precedent från PR #68), merge mot `main` när nöjd.
- **Sprintvakt V1.3 (potential)** — tvåvägs-sync workboard.json ↔ gap-filer. Flaggat som follow-up i `docs/sprintvakt-mcp.md`.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project DNA
V2 tills sprinten är formellt vald. Rör inte B125 om det inte uttryckligen
väljs.

**Andra cloud-agenters obesegrade arbete (operatörens uppmärksamhet):**

- `origin/cursor/jakob-be-contact-route-regression` — 2 commits. Innehåll inne via recovery #76.
- `origin/cursor/jakob-be-followup-versioning-regression-5fb4` — 3 commits. Innehåll inne via recovery #76.
- `origin/cursor/candidate-generation-safety-provenance` — 1 commit `07aca96`. Sibling-PR-branch till #78 som inte städades vid merge. Innehåll inne via #78.
- Alla tre kan raderas på operatörens OK (`git push origin --delete <branch>`). Nästa Jakob-agent ska inte röra dem utan instruktion.

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

**Inga öppna PRs.** PR #69 är stängd. Senaste merge till main: PR #120 (2026-05-26 PM). Senare commits sedan dess ligger på `jakob-be` och väntar nästa sync-PR (se "Direkt nästa spår" ovan).

**Öppna gaps på workboarden:** 1 queued gap:
`GAP-backend-build-trace-endpoint` — Christopher-implementerat under
operator-OK scope-leak, väntar PR från `christopher-ui` mot `main`. Inga
aktiva gaps.

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

- `2a5d2e5` PR #83 / `docs(grind): close B72 + B75 status-sync to Stängda`. Båda buggarna var fixade i `885431b` (PR #28) men entries glömdes kvar i Öppna under Steward-städning 2026-05-18. Cloud-grind round 4 verifierade båda regression-tester passar mot HEAD (`tests/test_viewser_security_1b.py` + `tests/test_project_input_schema.py`), uppdaterade summary-rad till 19/112 aktiva.
- `2821e5f` docs(steward) / Sprintvåg 1 stängd, bumpade verified state till `7654573` med fyra PRs dokumenterade.
- `7654573` PR #79 / `fix(grind): close B87 model fallback warning`. `resolve_brief_model`-fallback loggar nu högt på stderr per B87 fix-direktivet (`known-issues.md:138-139`). Cloud-grind round 3, rebasad och pushad efter #80-merge med uppdaterad bugräkning 22→21 aktiva.
- `4d4a27b` PR #80 / `fix(grind): close B85 stdout contract drift`. Source-lock-test `test_prompt_helper_docstring_matches_stdout_contract` låser `scripts/prompt_to_project_input.py`-docstringen mot stdout-nycklar. Cloud-grind round 2.
- `0ea3f3d` PR #82 / `docs(scout): embedding readiness audit 2026-05-25`. Lane 3 Scout-rapport (No-Go-dom, modellval, Go-villkor, B-IDer för schema-bumpar, 386 rader docs).
- `86c01fa` PR #81 / `fix(grind): close B83 service slug collision`. Status-only-stängning från Cloud-grind round 1.
- `74e74f2` docs(steward) / parallell-sprint-plan committad, last verified state bumpad till `b12c164`, mcp tools 11→14, lane-strukturen dokumenterad.
- `b12c164` post-merge grind / `_load_gap_from_file` unescapes markdown backslash-escapes så `sanitize_repo_path` inte producerar korrupta paths. 80 rader, ny regression-test, ren cloud-grind-fix mot `jakob-be`.
- `a0b06b5` docs-fix / escape `[runId]` i gap-frontmatter så markdown-linter inte klagar (matchar `_MARKDOWN_ESCAPE_RE`-konvention i `core.py`).
- `e2574af` PR #78 / candidate generation provenance + helpers (`scripts/candidate_generation_metadata.py`) + sidecar `.meta.json` per kandidat + Backoffice-default `use_llm=False`. 9 filer, ~562 additions.
- `d3f51ee` PR #77 / Sprintvakt agent inbox (post/list/ack) + 5 reviewfynd-fixar i samma squash (symlink-resistens, deterministic id, idempotent ack, ordinal > 9999, UTC-aware since-filter). 5 filer, ~1399 additions (varav 752 är tester).
- `dc1d53f` docs(steward) / closing-round sync 2026-05-25 04:30 efter recovery #76 — post-merge docs-bump utan kod.
- `92df12c` PR #76 / recovery av tappade #73/#74-regressionstester + Industry Coverage catch-all-fix. Mergad till `jakob-be` (inte `main` än). 4 filer, 531 additions / 3 deletions.
- `6649b51` docs(steward) / closing-round sync på `jakob-be` efter PR #75 (post-merge docs-bump utan kod-ändringar).
- `84bf9dd` PR #75 / Sprintvakt V1.1+V1.2+V1.2.1 + CI hardening + Backoffice industry coverage + Path B scout + ADR 0029 + docs sync (16 commits squashade till en). Tackled fyra legitima external review-fynd före merge (status-enum-validering, collision-recheck i `activate_gap`, gap-md vs workboard "workboard wins"-dokumentation, stale "next"-claim-cleanup).
- `7e21b49` PR #71 / Christophers Front 1-4 + wizard minimalism. Levererar 5 nya UI-gaps (4 in-review/completed + 1 aktivt: `GAP-viewser-live-build-sync` + 1 queued backend-spec åt Jakob: `GAP-backend-build-trace-endpoint`).
- `cb5c837` PR #70 / Sprintvakt V1 koordineringsserver + MCP (path-overlap-fix i `419d3f1`). 14 sprintvakt-tester gröna.
- `839d0c8` PR #68 / restaurant-hospitality Week 1 declarative expansion (11 soft dossiers + 14 variants). Inkluderade två `[scope-leak]`-commits från Christopher i `plan.py` + `resolve.py`.
- `7e900d2` PR #67 / AI bug review-workflow-steg i CI (`gpt-5.4` + repo-specifik prompt).
- `d709864` PR #66 / sourceUrl-asset-uploads med stream-safe fetch (PR #65 stängd och supersededad).
- `89f14a1` PR #64 / branch-naming-konventioner för parallellt teamarbete. Permanenta arbets-branches `jakob-be` + `christopher-ui` formaliserade i `docs/ownership-map.md`.
- `f9312ec` PR #63 / wizard-directives `useCustomColors` + `scaffoldHint` (backend-Gap 1 + 3 stängda).
- `7240fcd` PR #62 / viewser-christopher-ui builder-workflow-integration.
- `a32152d` PR #61 / team parallel workflow + ownership map.
- `c0b59fb` PR #60 / Starter Candidate Auditor v1, read-only — utgångspunkten för denna spårserie.

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
Kort: backend-Gap 1-11 är stängda och nästa naturliga steg är sync-PR
`jakob-be → main`. Därefter är Christophers
`GAP-backend-build-trace-endpoint`-PR nästa review-spår när den öppnas.

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

## Föregående checkpoint

### 2026-05-25 UTC — handoff.md före `2057241`

**Datum:** 2026-05-25 kväll. Verifierad feature-branch
`b146-port-section-dispatcher` (B146 stängd: Christophers PR #105 + #108
section-arkitektur portad ovanpå PR #107-splitten). `jakob-be` HEAD är
`ee2a91e`; `main` HEAD är `84bf842`. **Öppen PR:** feature →
`jakob-be` följt av sync-PR `jakob-be → main`. Bug-räkning på
feature-branchen: **19 aktiva / 5 unknown / 114 stängda** (B146 +
B116 båda stängda).

**Kvällens fönster (B146 + Phase 3 port):**

- Ny fil `packages/generation/build/dispatcher.py` (~370 rader) med
  section-id registry, treatment-resolution-helpers, `render_route_generic`.
- `packages/generation/build/renderers.py` växte från 2357 → ~4710 rader
  med ~30 nya `render_section_*` + uppdaterade page renderers från
  Christophers main-versioner. Initial sektion-registrering vid filslut.
- `scripts/build_site.py` ~3162 → ~3650 rader: utökade re-exports +
  `__getattr__`-shim som proxar okända namn till
  renderers/dispatcher/static_assets. `from scripts.build_site import
  render_section_X` fortsätter fungera.
- ADR 0031 (section-treatments från main:PR #108) renumrerad till **0032**
  eftersom jakob-be:s 0031 (Steward auto-bump, PR #106) var äldre.
  Renumber-not överst i ADR + uppdaterade referenser i alla
  source-/test-/doc-filer.
- Phase 3 backend: `_apply_directives_fields` additivt-mergar
  `directives.sectionTreatments` i resolve.py; `_SECTION_TREATMENTS_CATALOGUE`
  + planning-prompt-update i plan.py; schema-bump i project-input.schema.json.
- Wizard-UI: `treatment-options.ts` (ny), `wizard-types.ts`/
  `wizard-payload.ts`/`steps/visual-step.tsx`/`demo-answers.ts` uppdaterade,
  `wizard-constants.ts` fick 113 nya rader (deriveEffectiveScaffoldHint +
  4 restaurant-vibes).
- Tester: 5 nya/uppdaterade testfiler portade,
  `tests/test_section_treatments_{prompts,propagation,resolve}.py` +
  `test_section_renderer_registry.py` + `test_project_input_schema.py` (utökat).
  126 nya cases passerar. `test_builder_audit_post_3b_next.py` fick utökad
  JSX-escaping-lista (sätter `render_section_hero`, treatment-helpers etc.).

**Eftermiddags-fönstret (4 produkt-PRs + sync-PR till main):**

- PR #97 — pedagogiskt preview-fel i local-next mode (404/missing_artifacts mapping)
- PR #100 — per-siteId build mutex (Map ersätter global inFlight) → stänger B116
- PR #101 — StackBlitz embed unblocker (cross-origin-isolated permissions policy)
- PR #104 — honor preview mode end-to-end + mode-aware progress copy
- PR #103 — sync-merge `jakob-be → main` (16 commits totalt: 6 produkt + 6 härdning + 2 docs + 2 sync)

**Christopher-koord:** `origin/christopher-ui` är `399cf39` (idag) och
ligger **21 commits framför `origin/main`** — har inte pullat sync-PR
#103. Senaste commit `[scope-leak]`-taggad av honom själv (gick in i
`scripts/build_site.py:render_home`-territoriet, utanför hans branch-scope).
Meddelande postat till hans Sprintvakt-inbox 2026-05-25
(`msg-0007-ae0ac0`) om rebase-behov. PR mot main blockerad tills han
har merge:at + löst konflikter i `apps/viewser/components/viewer-panel.tsx`.

**Föregående checkpoint samma dag (morgon):** Sprintvåg 1+2 stängd — fem
PRs landade på `jakob-be` på 2 timmar (#81 + #82 + #80 + #79 + #83).
Verifierad `jakob-be` var då `2a5d2e5`, `main` på `6649b51`,
bug-räkning 19/112.

**ÄRLIG BEDÖMNING (extern reviewer + orchestrator-self-audit):** Av
dagens fem PRs är endast **#79 en substantiell produktkodsförändring**
(stderr-warning vid `briefModel`-fallback). #80 = docstring-source-lock-
test (intern kvalitet, ingen runtime-effekt). #81 + #83 = docs-
flyttar av redan-fixed B-IDer i `known-issues.md`. #82 = read-only
scout-rapport för embeddings-readiness. Dagens energi gick åt
**koordinationslager** (Sprintvakt-inbox, lane-disciplin, worktree-
isolering, multitask-räddningsoperation) snarare än till kärnflödet
`prompt → brief → plan/build → preview → följdprompt`. Verklig
produktlyft denna session: minimal. `main` rör sig inte alls. Detta
är acceptabelt OM nästa session prioriterar Lane 2 LLM contract
propagation (B137-B141) och `jakob-be → main`-sync.

`origin/christopher-ui` är på `9f63f15` med Christophers
scope-leak-implementation av `GAP-backend-build-trace-endpoint` plus en
versions-tab-fix, ej PR:ad än. Hon är hård blocker för `jakob-be → main`-
sync eftersom hennes branch behöver hanteras innan main rör sig.

Health på `jakob-be` är grön: governance (18 policies), rules-sync,
strict term coverage, sprintvakt-check `--strict`, ruff 0 findings,
hela pytest-suiten (25 sprintvakt-tester + 14 industry-coverage + 2
workflow-regression + 30+ övriga + nya #76-recovery-tester körda lokalt
i ren worktree från `origin/jakob-be` innan PR).

### 2026-05-25 UTC — handoff.md före `ee31eb1`

**Datum:** 2026-05-25 UTC, steward-auto efter PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime smoke-lock + golden-path eval (#112, #109, #110). Verifierad `main` är `ee31eb1`.

Nya PRs sedan föregående checkpoint: PR #55 — fix(viewser): stale run-following och
artefakt-panel; PR #59 — feat(backoffice): add read-only asset graph lens; PR #60 —
tooling: Starter Candidate Auditor v1 (read-only); PR #61 — docs: add team parallel
workflow and ownership map; PR #62 — feat(viewser): integrate christopher-ui builder
workflow; PR #63 — feat(discovery): respect wizard directives — useCustomColors +
scaffoldHint (Gap 1 + 3); PR #64 — docs(ownership): add branch-naming conventions for
parallel team work; PR #66 — fix(assets): sourceUrl uploads with stream-safe fetch
(supersedes #65); PR #67 — ci: add AI bug review workflow step; PR #68 — feat(week1):
restaurant-hospitality scaffold + 11 soft dossiers + 14 variants (fantastic sites W1);
PR #70 — feat(tooling): add Sprintvakt V1 coordination guard; PR #71 — feat(viewser):
Front 1-3 + wizard minimalism — preview, iteration & polish; PR #75 — feat: Sprintvakt
V1.1+V1.2 + CI hardening + industry coverage + docs sync (post-PR70 batch); PR #76 —
fix(backoffice): recover regression tests and catch-all coverage status; PR #77 —
feat(tooling): add Sprintvakt agent inbox (post/list/ack); PR #78 — fix(backoffice):
harden candidate generation provenance and defaults; PR #81 — fix(grind): close B83
service slug collision; PR #82 — docs(scout): embedding readiness audit 2026-05-25; PR
#80 — fix(grind): close B85 stdout contract drift; PR #79 — fix(grind): close B87 model
fallback warning; PR #83 — docs(grind): close B72 + B75 status-sync to Stängda; PR #84 —
test(generation): contract regression net for B137-B141 + extend B139 tone fallback; PR
#87 — feat(backoffice): add one-click eval smoke runs; PR #89 — feat(eval-probe): add
scaffold-selection probe + docs; PR #88 — fix(viewser): make preview mode drive local
iframe headers; PR #92 — fix(viewser): handle quoted-with-comment + $VAR expansion in
dev-dispatcher .env-parser; PR #93 — feat(builder): wire menu+booking renderers so
restaurant-hospitality builds; PR #94 — docs(dossiers): import-readiness scope-doc for
Sajtmaskin material; PR #95 — feat(evals): add cafe-bistro to FULL_CASES so full suite
covers all 3 on-disk scaffolds; PR #97 — fix(viewser): pedagogical preview-error in
local-next mode + soft transport-mismatch warning; PR #99 — docs(adr): 0030
preview/deploy-providers are adapters, not canonical runtime; PR #98 — chore(tooling):
lucide-react cross-policy lock + ADR 0021 upstream-issue recheck + B145 entry; PR #100 —
fix(viewser): per-siteId build mutex so unrelated sites can build in parallel; PR #101 —
fix(viewser): cross-origin-isolated permissions policy + dispatcher https signal; PR
#102 — fix(evals): cherry-pick timeout-hardening + helper API from #96; PR #104 —
fix(viewser): honor preview mode end-to-end + mode-aware progress copy; PR #103 —
sync(jakob-be -> main): 5 produkt + 6 härdning + 2 docs (13 commits); PR #105 — Live
Build Sync + Restaurant Path A + Wizard polish + Side-by-side preview; PR #106 —
feat(steward): auto-bump current-focus + handoff on PR merge to main (ADR 0031); PR #107
— refactor(builder): extract page renderers from build_site.py to
packages/generation/build (B13a step C); PR #108 — Phase 3 — section-treatments
operator-pin + scout-driven polish; PR #112 — feat(b146): port Christopher's
section-arkitektur ovanpå PR #107-splitten; PR #109 — test(builder): lock runtime
scaffold smoke coverage on jakob-be; PR #110 — feat(evals): add deterministic golden
path scorecard and embeddings gate; PR #111 — fix(agents): correct python3-venv package
name for Ubuntu Noble; PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime
smoke-lock + golden-path eval (#112, #109, #110).

### 2026-05-26 UTC — handoff.md före `858f8e8`

**Datum:** 2026-05-26 ~14:05 UTC, post-merge bump efter PR #117 + B151-B153 + sync-PR #118 öppnad. Verifierad `jakob-be` HEAD är `05a84bb`. `origin/main` är fortsatt `50217e3` (12 commits efter `jakob-be`); **sync-PR #118 är ÖPPEN** (`jakob-be → main`, OPEN/MERGEABLE/UNSTABLE-CI) och väntar på operatörens granskning + merge.

Nya PRs / direkta commits till `jakob-be` sedan föregående checkpoint (`50217e3`):

- `a337f01` audit-rapport `docs/archive/pr113-ours-conflict-audit-2026-05-26.md` (PR #113 `--ours`-resolution är clean).
- `f2e84b0` + `e6a23a3` — B148 (nav `/kontakt`-hardcode), B149 (Intent Guard substring), B150 (`_normalize_business_type` multi-word) stängda + 14 regression-tester.
- `c85ae70` + `3b5a798` — B97 (kontakt-page hero body per CTA-variant), B98 (`Områden vi arbetar i` suppress för ecommerce-lite) stängda + 9 regression-tester.
- `6d4a096` + `49f5513` — B90 (ENGLISH_HINTS "a"/"an" false positives), B91 (English-exonym → svensk endonym), B92 (`naprapat` ≠ `naprapatklinik`), B93 (22 nya multi-word slugs) stängda + ~20 regression-tester.
- `8c057b1` **PR #116 mergad** — `feat(backoffice): add dossier candidate intake from local files` (1453 inser / 21 del, 8 filer, ny `scripts/dossier_candidate_intake.py` + tester).
- `2319ef9` **PR #117 mergad** — `feat(viewser): mobile responsive — foundation + polish + final (fas 1+2+3 + scout passes)`. 31 commits från `christopher-ui`, 100 % UI-only mot merge-base `3bedddd`. Konflikter på `docs/agent-inbox.jsonl` + `docs/current-focus.md` lösta med kombinerade versioner.
- `4a6243a` + `1471d16` — **B151+B152+B153 stängda** direkt efter PR #117-merge (per operatörs-momentum-beslut, inte väntat på Christopher-följ-PR). Floating-chat iOS Safari <14 compat, compare-modal w-full overflow, viewer-panel `'full'`-preset hydration. 3 source-lock regression-tester i `tests/test_viewser_files.py`.
- `05a84bb` inbox msg-0017-c3f924 till christopher-ui (rapport om merge + att vi tog AI-fynden).

Ny aktiv då: **B147 Medel-Hög** (Vercel preview wizard 403 via `assertLocalhost`). Stängd senare i `b3834b3`. Bug-räkning då: **14 aktiva / 0 misplaced / 5 unknown / 126 stängda** (från 19/0/5/114 vid sessionsstart — netto 5 färre aktiva, 12 stängda, 1 ny tracked).

**Öppen PR just nu:**

- **#118 sync(jakob-be → main)** — OPEN, MERGEABLE, mergeStateStatus UNSTABLE (CI pågår). 45 commits / 56 filer / +5158/-328. Innehåller hela sessionens leverans. Operatörsbeslut då: granska body + checks, sedan merge. Vercel production branch-flippen är åtgärdad 2026-05-26; B146-blockaren är borta.

### 2026-05-27 UTC — handoff.md före `91230b4`

**Datum:** 2026-05-27 tidig morgon UTC, steward-pass efter `91230b4` — completed gap-spec cleanup + B147 closure sync. Verifierad `jakob-be` är `91230b4be799067ec05beb22ce34046ba6e89e0c`.

Nya PRs sedan föregående checkpoint: PR #118 — sync(jakob-be -> main): PR #117 mobile
responsive + PR #116 dossier-intake + 12 closed bugs + B147 new + audit-report; PR #120
— sync(jakob-be -> main): repo hygiene 2026-05-26 (4 commits, docs-only).

### 2026-05-27 UTC — handoff.md före `3415e7d`

**Datum:** 2026-05-27 UTC, steward-auto efter PR #123 — sync(jakob-be -> main): backend gap batch and docs cleanup. Verifierad `main` är `3415e7d`.

Nya PRs sedan föregående checkpoint: PR #123 — sync(jakob-be -> main): backend gap batch
and docs cleanup.

### 2026-05-27 UTC — handoff.md före `44bdbdd`

**Datum:** 2026-05-27 UTC, steward-auto efter PR #125 — fix(discovery): honor wizard clears across versioned fields. Verifierad `main` är `44bdbdd`.

Nya PRs sedan föregående checkpoint: PR #125 — fix(discovery): honor wizard clears
across versioned fields.

### 2026-05-27 UTC — handoff.md före `82ce287`

**Datum:** 2026-05-27 UTC, steward-auto efter PR #124 — feat(llm-golden-path): lock v1 + extend with multi-intent chain, real-build smoke, runbook and handoff. Verifierad `main` är `82ce287`.

Nya PRs sedan föregående checkpoint: PR #124 — feat(llm-golden-path): lock v1 + extend
with multi-intent chain, real-build smoke, runbook and handoff.
