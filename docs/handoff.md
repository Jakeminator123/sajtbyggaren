# Handoff – Sajtbyggaren

**Datum:** 2026-05-25 natt-till-morgon (**post-merge sync efter PR #75
Sprintvakt V1.1+V1.2+V1.2.1 + CI hardening + Backoffice industry coverage
+ docs sync, mergad ovanpå Christophers PR #71 Front 1-4 + wizard
minimalism**). Verifierad `main` är `84bf9dde512ce171abc27ff982b13e43ff8511a1`
(`feat: Sprintvakt V1.1+V1.2 + CI hardening + industry coverage + docs sync (post-PR70 batch) (#75)`).
Main health är grön: governance (18 policies), rules-sync, strict term
coverage, sprintvakt-check `--strict`, ruff 0 findings, hela pytest-suiten
(25 sprintvakt-tester + 14 industry-coverage + 2 workflow-regression + 30+
övriga svit-tester) körd på `53f027e` innan auto-squash-merge.
`jakob-be` är resetad mot nya main och pushad. `christopher-ui` väntar på
Christophers sync (Filosofi B `git reset --hard origin/main`).

**MCP-server-status:** Sprintvakt-servern exponerar 9 deterministiska tools
(`get_workboard`, `list_gaps`, `create_gap`, `reserve_paths`, `detect_collisions`,
`suggest_next_gaps`, `generate_agent_prompt`, `validate_workboard`,
`post_merge_sync_instructions`, `activate_gap`, `complete_gap` — totalt 11
efter V1.2). Operatörens `.cursor/mcp.json` är konfigurerad med
`PYTHONPATH` så `python -m tooling.sprintvakt_mcp.server` startar utan
ModuleNotFoundError. Editable install (`pip install -e .`) krävs en gång
per venv enligt ADR 0029.

**Direkt nästa spår — vänta tills operatör väljer:**

1. **`GAP-backend-build-trace-endpoint`** (queued, jakob) — Christophers
   backend-spec för Live Build Sync. Tre endpoints: `GET /api/runs/[runId]/trace`,
   `GET /api/runs` med `pending`-status, `POST /api/prompt` med valfri
   `baseRunId`. Full spec i `docs/gaps/GAP-backend-build-trace-endpoint.md`.
   ~3-5h Builder-arbete. **Nästa naturliga backend-spår.**
2. **Path B / section-driven renderer i `scripts/build_site.py:write_pages`**
   — dokumenterad i `docs/scaffold-runtime-extension-needed.md` (Christophers
   plan) + `docs/path-b-backend-scout.md` (Jakobs backend-Scout med 9-commit
   revision, ~22-28h över 3 sessioner). Låser upp restaurant-hospitality
   fullt + ger nollkostnad för 4 framtida scaffolds. Kräver explicit
   operator-OK innan start.
3. **Backend-Gap 4 + 5** från `docs/backend-handoff-2026-05-22.md` är
   öppna men ej akuta.
4. **Sprintvakt V1.3 (potential)** — tvåvägs-sync mellan workboard.json och
   gap-filer så `activate_gap`/`complete_gap` även uppdaterar `docs/gaps/<id>.md`.
   Flaggat som follow-up i `docs/sprintvakt-mcp.md` "Källa till sanning"-sektionen.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project DNA
V2 tills sprinten är formellt vald. Rör inte B125 om det inte uttryckligen
väljs.

**Andra cloud-agenters obesegrade arbete (operatörens uppmärksamhet):**

- `origin/cursor/jakob-be-contact-route-regression` — 2 commits med nya
  kontaktrout-regression-tester. Ej PR:ad.
- `origin/cursor/jakob-be-followup-versioning-regression-5fb4` — 3 commits
  med nya follow-up-versionerings-regression-tester. Ej PR:ad.
- Operatören bestämmer om/när de ska PR:as eller raderas. Nästa Jakob-agent
  ska inte röra dem utan instruktion.

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
