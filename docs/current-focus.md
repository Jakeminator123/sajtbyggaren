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

Last verified state: `fb3b1f8` (2026-06-01 UTC, steward-auto efter PR #142 — sync(jakob-be -> main): ADR 0034 path A copyDirectives + contact eval-fix + placeholder suppression).
Nya PRs sedan föregående checkpoint: PR #142 — sync(jakob-be -> main): ADR 0034 path A
copyDirectives + contact eval-fix + placeholder suppression.

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`. Christopher jobbar default på `christopher-ui`.
- `main` är canonical/sanningsbranch. Operatören eller agenten öppnar PR
  från arbets-branchen mot `main` när "en ny officiell version ska in" —
  ingen schemalagd cadence, det är ett beslut per leveransfönster.
- Efter merge: arbets-branchen synkas till `origin/main` (`git reset --hard
  origin/main` + `--force-with-lease`-push), inte via separat PR.
- Detaljerade regler: [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md).

## Pågående/öppna PR:s just nu

**Fyra öppna PRs (2026-06-01 PM):**

- **#139** `christopher-ui → main` — ready/clean, alla checks gröna. UI/UX-batch
  som bär både B155 FloatingChat-no-op-signal och copyDirectives väg B-UI
  (success/no-op-feedback). Scout-dom: merge-redo, men bekräfta Bugbot-trådar
  (ingen godkänd review än) + notera additiv scope-läcka i `route.ts`/`runs.ts`/
  `check_term_coverage.py` utan `[scope-leak]`-tagg (operatörsbeslut).
- **#140** `cursor/preview-runtime-bite-b-di → jakob-be` — draft. Bite B
  PreviewRuntime via dependency-injection. Inom scope; rör ej copyDirectives-
  filer eller Christopher-UI. Mergas in i `jakob-be`, ej `main`.
- **#138** `cursor/cloud-dev-env-setup-a928 → main` — draft, docs (AGENTS.md
  Cloud-gotchas). Clean.
- **#141** `cursor/cloud-agents-md-env-notes-7a3f → main` — draft, docs.
  Governance failar (term-coverage flaggar ett versalt backtick-ord i AGENTS.md);
  enradsfix kvar. Nästan-dubblett av #138 → konsolidera till en PR.

Rekommenderad main-merge-ordning: **#139 först**, sedan sync-PR
`jakob-be → main` (löser bara docs-konflikter i `current-focus.md` +
`known-issues.md`). `jakob-be` får EJ `reset --hard origin/main` i mellanläget
— `merge`/`rebase` in `main`, lös docs, öppna sync-PR.

**Christophers `origin/christopher-ui`** — efter PR #117 är hans branch
synkad mot post-#117-main. Han har under operator-OK scope-leak
implementerat hela `GAP-backend-build-trace-endpoint` (3 endpoints + UI +
5 bug-hunt-fixes). Mergad via PR #105 / commit `fe7a9e4`; flyttad till
`completedGaps` i `docs/workboard.json`. Workboardens `owner` är
medvetet kvar på `jakob` så Sprintvakt-lane-policyn passerar.

## Direkt nästa fokus

### Prioordning post-B157-stängning

1. **Manuell B157-end-to-end-verifiering** (operatörsuppgift, ~5 min) —
   kör follow-up på commerce-base-site med lockfile-drift, förvänta
   ingen `PermissionError: [WinError 5]`. Strukturella regression-
   tester finns redan (`tests/test_local_preview_server_b157_followup.py`),
   men en faktisk end-to-end-körning bevisar reap-fixet i naturlig miljö.
2. **Bite B (PreviewRuntime wiring)** — builder-prompt finns redan i
   `docs/agent-prompts/preview-runtime-bite-b.md`. Wirear `localRuntime`
   + `stackblitzRuntime` adaptrar mot existerande `apps/viewser/lib/`-
   helpers. Self-contained prompt; klistras in i ny agent-session.
   ~2-4h. Inga UI-ändringar (Bite C kräver Christopher). Vercel-
   preview/Fly/static-export-adaptrar lämnas för senare sprint.
3. **B157 nivå-4 (Windows-safe rebuild, immutable build-dir + pointer-
   swap)** — arkitektur-rätta lösningen, 12-16h. Akut nivå-1 +
   followup-fix räddar 99% av case idag, men anti-patternet "rebuilda
   ovanpå live output-katalog" kvarstår tills nivå-4 landar. Spec i
   `docs/gaps/GAP-windows-safe-rebuild-pipeline.md`.
4. **ADR 0034 — väg (b) "ärlig först"** (B155). FloatingChat markerar
   när följdprompt inte gav synlig effekt. Liten kodändring, kräver
   Christopher-koordinering (UI-yta).
5. **Quality-gate scaffold-routes-discovery** (tech-debt från `0b40b8d`).
   Läs scaffoldens `routes.json` direkt istället för pattern-matching
   `kontakt`/`contact`/`hitta-hit`-fragmenten. Egen sprint, ej akut.
6. **B156 follow-up: browser-hydration-smoke** — headless
   playwright/puppeteer ersätter chunk-heuristik. Egen sprint, ej akut.
7. **Worktree- och städ-cleanup** (operatörsbeslut):
   - Adapter-WIP på `cursor/preview-runtime-adapters` (worktreen
     `C:/Users/jakem/Desktop/sajtbyggaren-worktrees/preview-runtime-adapters`)
     — innehåller vercel-sandbox-adapter-skiss, naming-dict v18-bump,
     fly-stub. Bör snapshot:as till `origin` innan worktreen rensas.
   - `origin/cursor/dossier-intake-v11-review-895d` (3 commits, ingen PR).
   - `origin/cursor/jakob-be-viewser-local-next-preview` (PR #85 stängd,
     innehåll inne via #88/#92/#97/#100/#101).
   - Worktree-mappen `C:/Users/jakem/Desktop/sajtbyggaren-worktrees/
     llm-golden-path-v1` — git har glömt den; stäng Cursor + radera mappen.

## Redan landat (tidigare session-status korrigerad 2026-05-26 PM)

- Lane 2 LLM contract propagation — klar. B137 + B138 stängda
  2026-05-21, B141 stängd 2026-05-21 (PR #52), B139 + B140 stängda
  2026-05-22. Regression-net via PR #84 (`0205212`).
- Lane 4 Golden Path eval — klar. Levererad via PR #110 (`1f8966a`).
  `scripts/run_golden_path_eval.py` är aktiv och användes 2026-05-26 PM
  för att verifiera naprapat-fixen (5.83 → 6.81, gate `no-go` → `go`).
- Naprapat scaffold-routing — klar. Lane 3 embeddings-gate gick från
  `no-go` → `go`. Total Golden Path 7.10 → 7.34.

## Parkerade lanes (väntar trigger)

- Path B / section-driven renderer — kräver Lane 2 mergad först (delar
  `scripts/build_site.py`). Lane 2 är klar; Path B är fortfarande
  operatörsbeslut.
- Christophers `GAP-backend-build-trace-endpoint`-PR — Jakob är reviewer
  när Christopher öppnar PR från `christopher-ui` mot `main`.
- Sajtmaskin inspiration Scout — lokalt-only (kräver `sajtmaskin.rar` på
  operatörens maskin).
- Sprintvakt V1.3, B125 preview-fallback — öppna men ej akuta.

Vänta fortsatt med embeddings, SNI-runtime, variant-promotion, många nya
starters, starter-importer, ny scaffold-runtime-aktivering och Project
DNA V2 tills en sprint är formellt vald.

Startprompt för nya agenter:
[`docs/agent-prompts/morning-fresh-start.md`](agent-prompts/morning-fresh-start.md).

## Aktiv kö (kort lista)

Detaljerade Queue-/Blocked-block ligger i arkivet
[`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md).
Aktiva spår i prioritetsordning:

1. Manuell B157-end-to-end-verifiering (operatörsuppgift, ~5 min).
2. Bite B (PreviewRuntime wiring local + stackblitz).
3. B157 nivå-4 (immutable build-dir + pointer-swap, GAP-windows-
   safe-rebuild-pipeline) — eliminerar orphan-process-klassen.
4. ADR 0034 / GAP-followup-prompt-content-passthrough — fri
   follow-up-text når codegen via ``copyDirectives[]``. **Väg A first
   slice landad på `jakob-be` 2026-06-01 (ej i `main`, ingen PR än):**
   ``directives.copyDirectives`` (target company-name|tagline, operation
   replace-text|include-token), deterministisk extraktor + ny
   ``copyDirectiveModel``-roll (llm-models v5), guards gröna, 25 nya
   tester. Nästa: operatör-review + ev. sync-PR `jakob-be → main`; sen
   väg B FloatingChat-UI (Christopher) + bredare targets.
5. B49 (docs-base page-map sidebar) — låg prio, behövs innan
   `course-education → docs-base` aktiveras.
6. B13a arkitektur-flytt — kvarstår som öppen post, kräver egen sprint
   + sannolikt egen ADR.
7. B53, B47, BO4-followup-cancel — låga, ingen blocker.

(Sync-PR `jakob-be → main` är operatörsbeslut, inte aktivt
agentarbete. `GAP-backend-build-trace-endpoint` är completed via
PR #105 / commit `fe7a9e4`.)

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) under rubriken "Standard
loop". Kort: Scout vid behov → arbete på arbets-branch (`jakob-be` eller
`christopher-ui`) → guards gröna → push → vid behov PR mot `main` →
post-merge-sync.

Operatörspreferens: svenska, kort och koncist. Förklara dev-uttryck med
korta parenteser första gången per konversation. Mönstret i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).

## Arkiv

Historiska checkpoints och "Föregående produkt-läge"-kedjan från
2026-05-13 till 2026-05-26 PM ligger i
[`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md).
Den filen växer när vi gör nästa slim-down-pass. För djupare commit-
historik: `git log --oneline origin/main` eller `git log --oneline
origin/jakob-be`.

## Föregående checkpoint

### 2026-05-25 UTC — current-focus.md före `2057241`

Last verified state: feature-branch `b146-port-section-dispatcher`
(2026-05-25 **kväll**, B146-port: Christophers PR #105 + #108
section-arkitektur portad ovanpå jakob-be:s PR #107 split). `main`
HEAD är `84bf842`; `jakob-be` HEAD är `ee2a91e`. PR mot `jakob-be`
öppnas härnäst, följt av en sync-PR `jakob-be → main` när feature
PR:n mergat. Bug-räkning: **19 aktiva / 5 unknown / 114 stängda**
(B146 stängd via denna port).

**Kvällens fönster — B146 + Phase 3 port:**

- `packages/generation/build/dispatcher.py` (ny, ~370 rader):
  section-id registry, `_SECTION_TREATMENTS_BY_VARIANT`,
  `_treatment_for_section`, `_operator_pin_for_section`,
  `_load_scaffold_sections`, `_section_renderer_kwargs`,
  `_call_section_renderer`, `render_route_generic`.
- `packages/generation/build/renderers.py`: utvidgat från 2357 → ~4700
  rader. Alla ~30 nya `render_section_*` + uppdaterade page renderers.
- `scripts/build_site.py`: utökade re-exports + `__getattr__`-shim så
  `from scripts.build_site import render_section_X` fortsätter fungera.
- Phase 3 backend: `_apply_directives_fields` i resolve.py mergar
  `directives.sectionTreatments`; `plan.py` får
  `_SECTION_TREATMENTS_CATALOGUE` och prompt-update; schema-bump.
- ADR 0031 → 0032 renumrerad (jakob-be:s 0031 Steward auto-bump äldre).
- Wizard-UI: `treatment-options.ts`, `wizard-types.ts`,
  `wizard-payload.ts`, `steps/visual-step.tsx`, `demo-answers.ts`,
  `wizard-constants.ts` uppdaterade.
- Tester: 126 nya cases passerar.

**Eftermiddags-fönstret — 4 PRs landade i `jakob-be` + sync-PR #103
till main:** PR #97 (preview-fel mapping), PR #100 (per-siteId build
mutex → B116), PR #101 (StackBlitz embed unblocker), PR #104 (preview
mode end-to-end), PR #103 (sync-merge `jakob-be → main`, 16 commits).

### 2026-05-25 UTC — current-focus.md före `ee31eb1`

Last verified state: `ee31eb1` (2026-05-25 UTC, steward-auto efter
PR #113 — sync(jakob-be -> main): B146 reconciliation + runtime
smoke-lock + golden-path eval (#112, #109, #110)).

Sammanfattning: detta var checkpointen där hela serien PR #55, #59-#68,
#70-#71, #75-#84, #87-#113 mergades till main över loppet av några
dagar. Innehåller bl.a. starter-candidate-auditor (#60), team-parallel-
workflow (#61), wizard-directives Gap 1 + 3 (#63), restaurant-
hospitality Week 1 (#68), Sprintvakt V1+V1.1 (#70 + #75), agent-inbox
(#77), candidate-provenance (#78), B83+B85+B87+B72+B75 grind-PRs
(#79-#83), section-treatments + Path B-refaktor (#107 + #108), B146-
port (#112), golden-path-eval (#110), och sync-PR #113 till main.

### 2026-05-26 UTC — current-focus.md före `858f8e8`

Last verified state: `858f8e8` (post-merge `jakob-be` HEAD, 2026-05-26
~13:15 UTC, merge av PR #117 — `feat(viewser): mobile responsive` + PR
#119 dossier intake model review + docs-hygien T0+T1 ovanpå).

**Sessionens leverans:** 12 buggar stängda (B97, B98, B148, B149,
B150, B90, B91, B92, B93, B151, B152, B153) + PR #116 dossier-intake
mergad + PR #117 mobile responsive mergad (31 commits från
christopher-ui, 100 % UI-only mot merge-base `3bedddd`).

**B147 (Medel-Hög) ny aktiv bugg då** — Vercel preview wizard 403 via
`assertLocalhost` på `*.vercel.app`. Stängd senare i `b3834b3`.

`origin/jakob-be` var då 8+ commits före `origin/main`. Sync-PR
`jakob-be → main` var queued men ej öppnad — Christophers
`christopher-ui` är nu mergad genom #117, så den blockaren var löst.
Kvarvarande blockare då: B147-vägval + Vercel-production-branch-flip.
Båda är åtgärdade 2026-05-26; B147 stängdes i `b3834b3`.

### 2026-05-27 UTC — current-focus.md före `91230b4`

Last verified state: `91230b4be799067ec05beb22ce34046ba6e89e0c` (2026-05-27 early morning UTC, post completed gap-spec cleanup).

Nya commits sedan föregående checkpoint (`0f3bd67`):

- `91230b4` docs(steward): prune completed gap specs before sync.
- `6222627` docs(steward): archive completed gap prompts after Gap 10.
- `3b61c73` feat(build): close Gap 10 product image pipeline (#122).
- `365c1d7` feat(build): close Gap 9 — isolate moodImages to private uploads.
- `0043839` docs(current-focus): update verified SHA and commit count after recent changes.
- `e9c8afa` docs(handoff): update verified SHA and commit count after eval-layout refactor.
- `63656fb` refactor(evals): split data/evals into summaries/ + artifacts/ layout.
- `91990de` docs(steward): bump focus and handoff counts after B147 sync.
- `2a77c07` docs(steward): close B147 after host whitelist merge.
- `d483b7d` docs(steward): bump focus and handoff counts after docs sync commits.
- `b4473ee` docs(known-issues): move B147 to Stängda after b3834b3.
- `b3834b3` feat(viewser): close B147 — add VIEWSER_ALLOWED_HOSTS host-whitelist.
- `88dedf0` docs(steward): sync backend handoff after gap 6 and 7 merge.
- `cb07dbb` docs(steward): sync handoff/focus/workboard with actual code state 2026-05-26.
- `ea6e141` feat(build): close Gap 6 + 7 — multi-size favicon.ico + 1200x630 og-image.png.
- `c002aec` chore(deps): add pillow>=10.0 for build-pipeline image conversion.
- `dbc97d8` docs(agents): add cloud-grind prompt-pack for gaps + B147 + doc-cleanup.
- `1332efd` settingscommit (befintlig branch-commit, ej rörd i detta steward-pass).
- `9d052b9` docs(steward): bump current-focus + handoff + write late-evening handoff.
- `cc1a5aa` chore(viewser): commit vercel.json deploy config.
- `0ed5348` docs(backend-handoff): mark gap 1 + 11 as closed (audit 2026-05-26).
- `3fc187e`, `4cd367c`, `b414c6b`, `ee1751f` — naprapat scaffold-fix + Lane 2/4 stale-correction.
- `d3a2ad6`, `9dbd10a` — reviewer-flagged drift correction.
- `0f3bd67` — C4 audit landed via local merge (PR #121).
- `1721494`, `46d819f` — focus bump + Gap-headings cleanup.
- `6aeec35`, `fdb1fef`, `ff6154e` — evening handoff till nästa orchestrator + term-coverage cleanup.
- `b89a3d2` feat(discovery): persist directives.notesForPlanner into Site Brief (**Gap 5 stängd**).
- `1b91ca6` feat(discovery): merge directives.requestedCapabilities into resolver (**Gap 4 stängd**).
- `1c6d033` docs(focus,handoff): close Gap 4 + Gap 5 in audit table.
- `f7c437e` docs: slim current-focus från 1414→205 rader + skriv om branch-discipline.md för enkel modell (jakob-be/christopher-ui default, PR mot main vid officiell version). Auto-regen .cursor/rules-speglar.

### 2026-05-27 UTC — current-focus.md före `3415e7d`

Last verified state: `3415e7d` (2026-05-27 UTC, steward-auto efter PR #123 — sync(jakob-be -> main): backend gap batch and docs cleanup).
Nya PRs sedan föregående checkpoint: PR #123 — sync(jakob-be -> main): backend gap batch
and docs cleanup.

### 2026-05-27 UTC — current-focus.md före `44bdbdd`

Last verified state: `44bdbdd` (2026-05-27 UTC, steward-auto efter PR #125 — fix(discovery): honor wizard clears across versioned fields).
Nya PRs sedan föregående checkpoint: PR #125 — fix(discovery): honor wizard clears
across versioned fields.

### 2026-05-27 UTC — current-focus.md före `82ce287`

Last verified state: `82ce287` (2026-05-27 UTC, steward-auto efter PR #124 — feat(llm-golden-path): lock v1 + extend with multi-intent chain, real-build smoke, runbook and handoff).
Nya PRs sedan föregående checkpoint: PR #124 — feat(llm-golden-path): lock v1 + extend
with multi-intent chain, real-build smoke, runbook and handoff.

### 2026-05-27 UTC — current-focus.md före `67bd89a`

Last verified state: `67bd89a` (2026-05-27 UTC, post coach-godkänd
sanning-städning av PR #133. Dynamisk count med
`git rev-list --count origin/main..origin/jakob-be` visade **40**
commits framför `origin/main` — inte 29 som tidigare antagits.
PR #133 (öppen, inte draft) är redo för ready-merge).

Nya commits sedan `c9a730b` (i historisk ordning):
- `c67b53f` docs(steward): bump verified state to c9a730b post PR #131
  follow-up.
- `3e660ea` fix(docs): unbacktick Next.js ready output to clear
  term-coverage strict (false positive från föregående steward-bump).
- `bb6ab2e` feat(preview-runtime): Bite A skeleton — types + registry
  + 3 adapter stubs i `packages/preview-runtime/`. Inga callsites bytta;
  Bite B wirear local + stackblitz mot befintliga `apps/viewser/lib/`-
  helpers när tsconfig path-alias eller npm-workspace etableras. Bite C
  (UI-refaktor av `viewer-panel.tsx`) kräver Christopher-koordinering.
  Se ADR 0028 (Runtime Ladder) + ADR 0030 (Preview-Provider Portability).
- `e9e3f32` fix(test): close race condition in /api/prompt smoke
  teardown — `ProcessLookupError` mellan `poll()` och `os.killpg()`.
- `e6f5376` docs(steward): bump verified state to e9e3f32 post Bite A push.
- `6375a60` docs(quality-gate): annotate severity-status mapping per ADR 0015
  (false-positive bot-rapport om `_CHECKS_REGISTRY`).
- `331aaa0` docs(agent-prompts): add PreviewRuntime Bite B builder prompt.
- `cbe1ba9` merge: sync `origin/main` steward-auto-bump (`-X ours`).
- `44ea54b` fix(test): wrap second `wait()` in `/api/prompt` smoke teardown —
  `TimeoutExpired` om SIGKILL inte reapar D-state-process.
- `8358326` fix(preview-runtime): refer to forbidden-aliases list, do not
  copy them — fixade `test_no_legacy_terms` CI-failure på `cbe1ba9`.
- `e60f493` fix(test): catch `PermissionError` on Windows in `/api/prompt`
  smoke teardown — Win32-race där `Popen.terminate()` kastar errno 5.
- `19480dc` feat(preview-runtime): fail loud on unknown VIEWSER_PREVIEW_MODE
  — `currentKind()` kastar Error på explicit men okänt env-värde,
  fortsätter tyst fallback till `local` bara på tomt/osatt env.
- `e2f857c` fix(quality-gate): smala `placeholder-copy-scan` så
  dev-markers (todo/fixme-stil) inte räknas som customer-copy-placeholder
  — de gav brus när check:en skannar både code-comments och
  customer-rendering-strängar.
- `5d5106c` docs(steward): bump verified state to e2f857c post PR #133
  reviewer batch.
- `5d4111f` fix(docs): unbacktick dev-marker words in steward-bump body
  — term-coverage strict false positive på fixme-ordet i förra bumpens body.
- `d60bb58` docs(rules): add bot-report-verification — alwaysApply: true
  rule som säger kolla mot `origin/<branch>` innan fix på cachad
  bot-rapport. Skrevs efter att två stale bot-rundor ledde till
  onödiga rundor.
- `abff654` fix(quality-gate): make TBD + REPLACE_ME case-insensitive in
  placeholder scan — extern reviewer-fynd post #133. `\b`-word-boundaries
  håller kvar mot infix-false-positives.
- `58cfe20` docs(preview-runtime): reconcile fly slot to ADR 0028 level 3
  in README — extern reviewer-fynd post #133. Operatörsbeslut väg (a):
  behåll typunionen, dokumentera att `fly` är slot för production-/deploy-
  check (ej implementerad). Naming-dict v17 oförändrad.
- `f8d0d0b` docs(steward): bump verified state to 58cfe20 + fix open-PR
  contradiction.
- `8fb24e4` docs: file B157 + GAP-windows-safe-rebuild-pipeline (extern
  reviewer-analys 2) — WinError 5 rmtree på live `node_modules` när
  builder rebuildar samma `.generated/<siteId>/` som aktiv preview-
  process. Root cause: arkitektur-anti-pattern (rebuild ovanpå live
  output-katalog), trigger: B154-fixens lockfile-diff-check + commerce-
  base Next-bump. Fix-laddare i gap-spec; ingen kodfix i denna commit.
- `924a1df` docs(steward): bump verified state to 8fb24e4 + B157 in
  next-focus queue.
- `82b9f99` Cursor BugBot suggestion 1: defensive cleanup i
  `tests/test_b154_next_dev_tdz.py:_stop_process` (samma pattern som
  redan finns i `test_api_prompt_smoke.py`). Pushad direkt av BugBot.
- `23b473e` Cursor BugBot suggestion 2: smala `_TEXT_EXTENSIONS` i
  `placeholder-copy-scan` till bara `{".tsx", ".jsx"}` (var: 9 ext
  inkl. `.md`/`.json` som gav false positives på docs/config). Pushad
  direkt av BugBot.
- `f446be1` Cursor BugBot suggestion 3: byt AND till OR i
  `_has_contact_cta` så `tel:`/`mailto:`-länkar accepteras utan att
  body måste matcha CTA-mönster. Pushad direkt av BugBot.
- `0b40b8d` fix(quality-gate): accept scaffold-specific contact-routes
  (kontakta-oss + hitta-hit) — GPT P2 Badge + BugBot suggestion 4.
  Hybrid: pattern-fragments + iterera `app/`-dirs istället för att
  hardcoda `app/kontakt/page.tsx`. Stänger sista reviewer-fyndet på
  PR #133. Egen sprint som tech-debt: läs scaffoldens routes.json
  direkt istället för pattern-matching.
- `a67bc01` docs(steward): bump verified state to 0b40b8d + post-merge-
  133 priolista (Bite B + B157-val + ADR 0034 + städning).
- `f2de33f` chore(term-coverage): allowlist BugBot CamelCase-stavning.
- `86b5782` docs(integrations): fix dead markdown link i
  `webcontainers-notes.md` (pekade på `struktur/PreviewRuntime.ts` som
  aldrig fanns; nu pekar på `packages/preview-runtime/src/types.ts`).
- `ea1e435` fix(quality-gate): contact-CTA href-only check (body-text
  ensamt räcker inte) — GPT-reviewer-fynd post `f446be1` OR-fix där
  `<a href="/products">Ring oss</a>` falskt godkändes som contact-CTA.

PR #133 (`jakob-be → main`) är öppen (inte draft) och uppdateras
automatiskt med varje push. Alla guards gröna lokalt mot HEAD.
Sync-merge till main är operatörsbeslut när reviewer-trådarna är stängda.

Nya PRs sedan föregående checkpoint (i mergeordning):
PR #125 — fix(discovery): honor wizard clears across versioned fields.
PR #127 — fix(viewser): block Python-backed actions on hosted Vercel.
PR #128 — docs(gaps): file followup-prompt-content-passthrough + ADR 0034 draft.
PR #129 — feat(quality-gate): add contact-CTA + placeholder-copy checks (+ follow-up
  summary-severity-fix i `8269800`).
PR #130 — test(api): add HTTP smoke-test for /api/prompt Node->Python bridge.
PR #131 — fix(builder): close B154 — TDZ at dev hydration on deterministic codegen.
  Follow-up `c9a730b` (direct push till `jakob-be` efter merge) refaktorerade
  drain-tråden i `tests/test_b154_next_dev_tdz.py` — tidigare returnerade
  `_wait_for_dev_ready` en fresh list som slutade växa vid Next.js
  ready-raden, så TDZ-fel som trillade ut *efter* ready (precis
  B154-fönstret) syntes inte. Nu äger `_spawn_next_dev` listan och
  drain-tråden skriver direkt in i den.
PR #132 — docs(steward): cleanup pass — archive stale handoffs + completed reports.

### 2026-05-31 UTC — current-focus.md före `8709aae`

Last verified state: `8709aae` (2026-05-31 UTC, B155-backend (#135)
+ quality-gate routes-discovery (#134) + post-merge quality-gate-
härdning mergade/pushade till `jakob-be`). B155: buildern skriver
`appliedVisibleEffect` + `appliedVisibleEffectReason` till
build-result.json och emitterar trace-event `followup.no_op_detected`
för fri-text-följdpromptar utan synlig effekt (hybrid: intent-regel +
cross-run byte-diff av `app/page.tsx`). UI-delen (FloatingChat-signal)
väntar Christopher. Quality-gate: contact-route resolveras via
scaffoldens `routes.json` (`id="contact"`) istället för
fragment-matchning; post-merge-review-härdning (`8709aae`) gör en
oresolverbar contact-route till en synlig warning-finding (ej längre
tyst ok) + robustare fallback mot kända scaffold-contact-paths. Alla
guards gröna (ruff, pytest, governance, rules-sync, term-coverage,
sprintvakt). BO6 (föregående) stängd. **Kärnflödet verifierat
end-to-end via Viewser-browser** 2026-05-28 ~01:40
(måleri-bygg-genberg-07d364 init + tone-shift follow-up, båda byggde
utan WinError 5).

`jakob-be` är synkad med `origin/jakob-be`. `origin/main` ligger på
`4196c17`. Inga öppna PRs. Bug-count: 15 aktiva / 0 misplaced /
5 unknown / 130 stängda. Golden-path-eval baseline: **7.34/10,
embeddings=go** (2026-05-28 00:57, 0 regressioner från natt-batchen).

Natt-batchen 2026-05-27 → 2026-05-28 (alla pushade):

- `4196c17` docs(steward-auto): bump HEAD to acdfad2 via PR #133 sync.
- `adba139` fix(viewser): close B157 acute — stop local preview before
  ``build_site.py`` (Windows file-lock).
- `9c3bad7` chore(docs): archive 4 sprint-handoffs + drop product-
  north-star duplicate.
- `697cf4f` fix(viewser): close B157 followup — wait for actual exit
  after SIGKILL (reap-fix, ``sigkillSent`` + ``REAP_TIMEOUT_MS``).
- `c821b8e` chore(governance): post-B157 cleanup-fixes (alwaysApply,
  GAP-status, workboard.json sync).
- `f46c01a` docs(steward): remove stale post-PR-133 focus drift.
- `9196fa1` docs(steward): complete post-PR-133 drift-fix round 2.
- `ef8745d` **fix(viewser): close B157 round 3 — Windows process-
  tree-kill (taskkill /T /F)**. Diagnostiserad rotorsak: Node.js
  ``ChildProcess.kill()`` på Windows mappar till
  ``TerminateProcess(handle)`` som **bara dödar direct PID, inte
  descendants**. ``npx next start`` → child ``next start`` blev
  orphan med exklusivt fil-lås. Fix: ny ``killProcessTree``-helper
  + Windows-fast-path. 4:e regression-test låser tree-kill-mönstret.
  Full diagnostik i `B157-WINDOWS-PROCESS-TREE-FYND.md` (repo-rot).
- `7ab5060` docs(agent-prompts): add 2 scout-grind prompts för
  cloud-agent-fixes (backoffice-runtime-scaffolds-stale +
  followup-honest-no-op-detection backend).

**B157-status efter round 3:** verifierat end-to-end. Kvarvarande
edge case: orphan-processer från en TIDIGARE Viewser-session (pre-
698f745d-dev-server). För dessa: kör `python kill-dev-trees.py`
(Windows-only helper i repo-roten) eller dubbelklicka
`kill-dev-trees.bat`. Whitelist:ar bara Sajtbyggaren-relaterade
node-processer (skyddar VS Code language-servers etc.).

**Nivå-4-sprinten** (immutable build-dir + pointer-swap, GAP-windows-
safe-rebuild-pipeline) eliminerar hela klassen anti-pattern
"rebuilda ovanpå live preview-katalog". Egen sprint per gap-spec.

### 2026-05-31 UTC — current-focus.md före `5746419`

Last verified state: `5746419` (2026-05-31 UTC, extern-review-fixar ovanpå Stage A+B: `kill-dev-trees.py` scope:ad så den bara tree-killar Sajtbyggaren-processer (path-token eller `next start`/`next dev` på preview-port 4100-4199, inte vilket Next-projekt som helst) + latent `.generated`-token-bugg fixad, och `read_active_build_dir` (Python + TS-spegel) kryssvaliderar `current.json:buildPath` mot `activeBuildId`. Nya `tests/test_kill_dev_trees.py`. Guards gröna. Föregående: `df640c0`. — B157 level 4 Stage A+B landad på `jakob-be`. Stage A (`34db1c2`): immutable build-dir + atomär pointer-swap. Builder bygger nu till `<generated>/<siteId>/builds/<buildId>/` via ny modul `packages/generation/build/immutable_builds.py` (`new_build_id`/`build_dir_for`/`write_active_pointer`/`read_active_build_dir`) och publicerar aktiv build via atomär tmp+`os.replace` på `current.json`. Swap sker endast på slutstatus ok|degraded; failed/skipped lämnar pekaren orörd. Preview-resolvern i `local-preview-server.ts` läser pekaren med legacy-`.next`-fallback, `verify_run.py` är pointer-medveten, `build-runner.ts` dokumenterar stopAndWait som restart/consistency. WinError-5-klassen (B157) är därmed eliminerad arkitektoniskt — round 1-3-plåstren + build-runner-tree-kill är nu redundanta säkerhetsnät. Alla guards gröna inkl. slow real-builds (golden-path, b154 next dev, api-prompt bridge) + dedikerat B157-repro-test. Föregående verified: `5047ac0`.

Stage B landad ovanpå Stage A i `df640c0`: ny CLI `scripts/gc_old_builds.py` för delayed GC av gamla immutable builds under `<generated>/<siteId>/builds/`. Retention: behåll aktiv build (`current.json`), builds yngre än 24h, samt de 5 senaste per siteId; allt annat är GC-kandidat. Dry-run default, `--apply` krävs för radering. Konservativ vid saknad/korrupt `current.json` (raderar inget för den siteId:n), rör aldrig legacy flat-layout-sajter, robusta deletes (locked build → delete-failed, GC kraschar aldrig, idempotent). Återanvänder Stage A:s helpers (`read_active_build_dir`/`BUILDS_DIRNAME`/`_BUILD_ID_RE`). Alla Stage B-guards gröna (ruff, governance, rules_sync, term_coverage, pytest test_gc_old_builds+test_immutable_builds 31 pass, sprintvakt, focus). GC är operatör-/schemalagt-anropad CLI; inte inwirad i build-flödet. Kvar (framtida): flat-layout-städning + POSIX-tree-kill.)
Nya PRs sedan föregående checkpoint: PR #136 — sync(jakob-be -> main): B157 round 3 +
BO6 + B155 backend + quality-gate routes-discovery.

### 2026-06-01 UTC — current-focus.md före `ee31eb1`

Last verified state: pending (2026-06-01 fm, christopher-ui local — Tier
1 robusthet implementerad: ErrorBoundary + lättviktigt toast-system +
network-failure UX för /api/runs. Tre komplement utan backend-beroende,
alla inom apps/viewser-lanen, för att hindra tysta launch-buggar medan
Jakob sätter upp Vercel-preview-fallback för B125. (A) Ny
``components/error-boundary.tsx`` (klass — React 19 har inget hook-API)
wrappar ViewerPanel + PromptBuilder + BuilderShell i page.tsx så
crash i någon subtree avgränsas; reset-knapp ökar resetKey → React
remountar barnträdet. (B) Nytt ``components/ui/toast.tsx``
(ToastProvider + useToast + viewport, ~250 rader, ingen extern dep,
aria-live polite/assertive per variant). Mountas i providers.tsx. Hookas
in på fyra ställen i page.tsx: /api/runs initial-failure
(error-toast med retry-action), /api/runs follow-up-failure efter build
(warning-toast), handleBuildDone success (success-toast), degraded
(warning), failed (error). Stable retry-callback via loadRunsRef så
toast-actionen inte stänger över sig själv (React 19:s
react-hooks/immutability-regel). (C) Initial /api/runs-loader
extraherad till useCallback ``loadRuns`` så retry kan trigga om utan
duplicerad kod; ny ``RunsLoadErrorCard``-komponent med WifiOff-ikon +
felmeddelande + Försök-igen-knapp visas centrerat över hero när
runsLoadError är satt och builder-mode inte är aktivt. Fyra nya
source-lock-tester (``test_tier1_*``). Pre-existing
test_page_useeffect_guards_success_path uppdaterat så det accepterar
både ``cancelled`` (bool) och ``cancelledRef.current`` (ref-objekt).
ErrorBoundary-/Toast-helpers + TriangleAlert (lucide-ikon) allowlistade
i scripts/check_term_coverage.py. Slutkontroll grön: tsc 0, lint 0,
ruff 0, pytest 1198 passed + 3 skipped, governance 18/18, rules-sync
OK, term-coverage --strict 0 unknowns. Commit: f8f2213. Tidigare
verified state: pending (2026-06-01 fm, christopher-ui local — ADR
0034 väg B (B155 path B) implementerad i FloatingChat. Backend för
path A landade på `jakob-be` (commit 641abc9) men är inte mergad till
`main` än, så UI:t är redo för end-to-end så fort jakob-be → main
mergas. Kontraktet är låst per Jakobs handoff och vi rör inte
backend/generation. apps/viewser/lib/runs.ts: ny export
``readAppliedCopyDirectives(runId)`` som läser ``input.json``
→ ``dossierPath`` → versionens project-input-snapshot och returnerar
schema-strikt validerad ``AppliedCopyDirective[]`` (path-traversal-
skydd vitlistar bara ``data/prompt-inputs/`` + ``examples/`` under
repo-root). apps/viewser/app/api/prompt/route.ts: anropar helpern
efter runBuild och inkluderar ``appliedCopyDirectives`` på top-level
i prompt-svaret. apps/viewser/components/builder/floating-chat.tsx:
ny ``summarizeCopyDirectives`` helper härleder svenska success-rader
("Jag ändrade företagsnamnet till '...'.", "Jag uppdaterade rubriken
till '...'.", "Jag la in '...' i hero-texten.") per direktiv.
``summarizeBuildResult`` success-grenen prioriterar
``applied === false`` (info-variant) före applied===true med
directives före generisk "Klart!"-rad. Säkerhet: payload renderas
som textnod via React auto-escape; regression-test bevakar att
``dangerouslySetInnerHTML`` aldrig används i floating-chat.tsx.
Fyra nya source-lock-tester
(``test_b155_path_b_*``). ``AppliedCopyDirective`` allowlistad i
``scripts/check_term_coverage.py`` — lokal UI/server-helper-typ
(canonical term registreras av jakob-be när path A → main).
Slutkontroll grön: tsc 1306, ruff 0, pytest pass + 3 skipped,
governance 18/18, rules-sync OK, term-coverage --strict 0 unknowns.
PR #139 uppdaterad. Tidigare verified state: pending (2026-06-01 fm,
christopher-ui local — merge
av `origin/main` (PR #136 backend-batch: B157, BO6, B155-backend, quality-
gate) klar. 11 merge-konflikter lösta: 7 i kod (FloatingChat,
BuilderActions, ComparePreviewModal, DiscoveryWizard, wizard-types,
PromptBuilder, ViewerPanel) + 4 i docs (agent-inbox, current-focus,
known-issues, workboard). Code-conflicts prioriterade `christopher-ui`s
minimalist-UI/UX där backend-fixar från `main` ändå behölls (B151
matchMedia-listener, B152 snap-x-bredd, B153-providern). B155 UI
implementerad i `floating-chat.tsx`: `summarizeBuildResult` läser nu
`payload.buildResult.appliedVisibleEffect` (auktoritativ källa per
Jakobs PR #136) och flippar success-bubblan till en ärlig info-rad
("Ingen synlig ändring fångades — prova en mer specifik följdprompt")
när motorn rapporterar `applied=false`. Två nya regressionstester
låser kontraktet (`test_b155_floating_chat_reads_applied_visible_effect`
+ `test_b155_floating_chat_no_op_does_not_claim_success`) plus uppdaterat
`test_b153_device_preset_*`-testet pekar nu på providern istället för
viewer-panel.tsx. Slutkontroll grön: tsc 1306 filer, ruff 0 findings,
pytest 1300+ pass / 3 skipped, 18 governance-policies, rule-mirrors i
synk, term-coverage --strict 0 unknowns. Sync-PR `christopher-ui` →
`main` öppnas härnäst. Tidigare verified state: `7b6fb6c` (2026-05-27
natt, christopher-ui local — B122
stängd. `/api/prompt` exponerar nu NDJSON-stream på `Accept: application/
x-ndjson` med två events: `{stage:"building"}` exakt mellan Phase 1 och
Phase 2, samt `{stage:"done", ...result}` som slutevent. PromptBuilder
läser body-strömmen via `response.body.getReader()` och flippar stage på
riktig signal istället för den gamla `setTimeout(1500)`-gissningen som
gav falsk "Bygger sajt" vid snabba svar och falskt "thinking" vid hängda
prompter. `floating-chat.tsx`/`use-followup-build.ts` skickar inte
Accept-headern → fortfarande synkron JSON, ingen regression. Två nya
regressionstester. Term-coverage utökad med TextEncoder/TextDecoder.
Tidigare verified state: `15efae0` (2026-05-26 sen kväll, christopher-ui
local — scout-pass över hela toolbar/wizard-batchen sedan PR #117 mergades.
Tre P1-regressioner åtgärdade i ett sammanhängande pass:
A) DevicePresetProvider hydration race — persist-effekten skrev "full"
till sessionStorage före hydration läste, så valet nollställdes vid
reload. Fix: hasHydratedRef gate:ar persist tills hydration är klar.
B) Toolbar-pillen utanför viewport vid default-position — clampToViewport
räknade bara PANEL_HEIGHT (460) och inte toolbar-radens ~36-40px nedanför.
Fix: ny PANEL_FOOTPRINT_HEIGHT-konstant används i alla 4 clamp-anrop.
C) Functions-step bevarade restaurang-sidor vid byte till e-handel.
Fix: family-switch räknar nu diff mellan föregående och nya familjs
defaults, byter ut defaults men behåller operatorns custom-tillägg.
Plus 4 P2-cleanups parkade som non-blocking i scout-batchen. Lint +
typecheck + term-coverage --strict passerar.).

Aktuell christopher-ui-lane (lokala commits sedan `3bedddd`/main):

- `15efae0` fix(viewser): scout-pass P1 — device-preset persist,
  toolbar clamp, family-switch resync. DevicePresetProvider: hasHydratedRef
  gating för persist-effekten. FloatingChat: PANEL_FOOTPRINT_HEIGHT
  inkluderar TOOLBAR_ROW_HEIGHT (40px) i alla clampToViewport-anrop.
  functions-step: useEffect hanterar previousFamily ≠ null separat —
  byter ut föregående familjs defaults, behåller operatorns tillägg.
  lastAppliedFamilyRef typad om till BusinessFamilyId|null.
- `23a5c16` style(viewser/builder): unified toolbar pill — format +
  Verktyg ihopkopplade i EN container med samma `bg-card/95` som chat-
  panelen + subtil vertikal divider mellan device-knapparna och
  Verktyg-knappen. BuilderActions inline-knappen rensad från egen
  border/shadow så den smälter in.
- `481593d` fix(viewser/builder): flat Verktyg-grid + Versioner-text.
  Dialog-modalen rendar nu alla actions i en enda `grid-cols-2 sm:grid-
  cols-3` istället för per grupp. Versioner-description statisk
  "Bläddra tidigare bygg" (var dynamisk runId).
- `46a54cd` style(viewser/builder): Verktyg-grid 3-per-rad på desktop
  (`sm:grid-cols-3`, var `sm:grid-cols-4`).
- `3829260` feat(viewser/builder): Verktyg-menyn som modal grid med
  backdrop. BuilderActions inline-variant: dropdown-listan ersatt av
  Dialog-modal (Base UI). Backdrop dimmer sajt + chat; klick utanför
  stänger via Dialog default.
- `aa934cc` refactor(viewser/builder): Verktyg-pill in i FloatingChat-
  toolbar-raden. BuilderActions: ny `variant: "fixed" | "inline"` (default
  "fixed"). FloatingChat: ny `tools?: ReactNode`-slot — toolbar-raden
  under chatten blir nu en flex-row med device-toggle + tools, fortsatt
  centrerad mot panel-mittpunkten via translateX(-50%). builder-shell
  passerar BuilderActions via tools={...} med variant="inline".
- `0296fad` style(viewser): centrera device-toggle under chatt utan gap.
  DevicePresetToggleBar i FloatingChat: `left: position.x + PANEL_WIDTH/2`
  + `transform: translateX(-50%)` centrerar; `top: position.y + PANEL_HEIGHT`
  (utan +8) gör att toggle-baren hänger ihop kant-i-kant med chat-rutan.
- `362a24c` refactor(viewser): ta bort "Foundation-beslut"-panelen från
  Stil-tabben (visual-step). MetadataPanel + selectedVibe useMemo + ContextChips
  helpers raderade — operatorn behöver inte se "Family → scaffold → default-
  vibe"-meta.
- `57a56c6` refactor(viewser): wizard popup-revision — 5 smala flikar, ta bort
  Specialisering. Foundation-step: Specialiserings-disclosure med sub-kategori-
  chips raderad helt. MoreInfoDialog: max-w 720px (var 960), 4 flikar → 5 flikar
  (Innehåll splittad i Om oss + Innehåll), header pt-4 pb-2 sm:pt-5 sm:pb-3 så
  content börjar högre upp, DialogDescription hidden sm:inline, tab-bar med
  overflow-x-auto + snap-x snap-mandatory för 5 flikar på 375px. Backend oändrad
  (validateDiscoveryCategoryIds([]) godkänner tom siteType, branchForFamily()
  fallback finns redan).
- `3843a80` fix(viewser): wizard texter visade rå \uXXXX-kod — decoda till
  svenska bokstäver. JSX text-content tolkar inte JS unicode-escape-syntax —
  operatören såg "Forts\u00e4tt", "\u00e5t dig", "fr\u00e5gor" osv i klartext.
  239 escapes decodade i discovery-wizard.tsx (80), more-info-dialog.tsx (85),
  wizard-types.ts (45), assets-step.tsx (20), foundation-step.tsx (9).
- `1ab516c` feat(viewser): GPT Vision auto-hero-pick från mediamaterial-galleri.
  AssetsStep gallery-dropzone promoteras till hero automatiskt om operatorn
  inte explicit valt en — picks bästa kandidaten via `pickHeroFromGallery`
  (placement+visionConfidence). Klassificering finns redan i upload-asset/api.
- `b1e92ca` feat(viewser): wizard popup utvidgning + logo/mediamaterial på tab 3.
  MoreInfoDialog: 4 flikar (Innehåll/Kontakt/Media/Avancerat) som återanvänder
  ContentOrchestratorStep + nya ContactBlock/MediaExtrasBlock/AdvancedBlock.
  Tab 3 (functions) får AssetsStep direkt. Kontakt-disclosure flyttad från
  foundation-step.
- `1c1a9fb` feat(viewser): wizard total-minimalism — 3 tabs överst + Mer
  information-popup. WIZARD_STEP_ORDER 5→3 (foundation/visual/functions).
  Sidebar borttagen, tabs på desktop+mobile. Inga proaktiva tips/varningar.
  Foundation: bara offer + businessFamily är hard-required; alla andra fält
  och steg är skip-bara.
- `4442aea` feat(viewser): device-preset-context + iframe-mounted-during-build.
  DevicePresetProvider för delad state mellan FloatingChat (toggle-bar under
  panelen) + ViewerPanel. Iframen behålls mountad under build (BuildProgressCard
  med backdrop-blur) så ingen vit canvas mellan iterationer.

- `a1d1a1f` docs(inbox): ack msg-0008 (scope-process-PR-105) + msg-0009 (b146-port).
- `ea62e45` docs(gap): open GAP-viewser-mobile-responsive-foundation. Pausar tillfälligt
  `GAP-viewser-pipeline-status-polling` + `GAP-viewser-side-by-side-preview` (samma owner,
  samma kärnfiler) till queuedGaps. Återöppnas efter denna mobil-PR landar.
- `31a888a` feat(viewser/ui): mobile foundation — `pb-safe`/`pt-safe`/`px-safe`,
  `min-tap` (44px Apple HIG), `touch-visible` (motsatsen till hover-only),
  `bottom-sheet-handle` + `sheet.tsx` bottom-sheet-stöd (`max-h-[90dvh]`,
  `rounded-t-3xl`, `pb-safe` automatiskt under `data-[side=bottom]`).
- `3b2420d` feat(viewser/wizard): mobile pass — `validationError` alltid synlig
  (tidigare `hidden sm:inline-flex` dolde förklaringen till disabled primärknapp),
  close-knapp + konsol-knapp + popover-close får min-tap mobile, wizard-padding
  `px-5 sm:px-10`, footer `pb-safe-or-4`, `PayloadAlignmentPopover`
  `w-[min(340px,calc(100vw-2rem))]` (tidigare fast 340px overflowade),
  moodboard/produktbild-delete använder `touch-visible` (tidigare osynlig på touch),
  `site-header` `pt-safe`.
- `9593769` feat(viewser/builder): mobile pass — `FloatingChat` bottom-sheet på
  mobil med drag-handle + pb-safe (tidigare fast 360×460 blockerade hela viewporten);
  minimerat tillstånd = 56×56 FAB nederst höger på mobil (sidotab-mönstret hamnar
  mitt på 375px); composer-textarea `text-base sm:text-[13px]` (förhindrar iOS
  Safari auto-zoom); `BuilderActions` `hidden md:flex` (verktygsmenyn skulle
  hamna under bottom-sheet:n); `SiteInspectorSheet` bottom-sheet på mobil
  (`max-md:!inset-x-0 max-md:!bottom-0 max-md:!h-[90dvh] max-md:!rounded-t-3xl`)
  + tabs `overflow-x-auto scrollbar-hidden` så 7 triggers kan scrolla horisontellt.
- `fb87699` docs(focus): bump current-focus till 9593769 + governance fixes
  (fidelity-term ut, FloatingChat-syntax i kommentar).
- `b0140b1` docs(inbox): notify jakob-be om PR #117 + pausade gaps (msg-0010).
- `62437de` docs(gap): open GAP-viewser-mobile-responsive-polish (fas 2).
- `d7ca301` fix(viewser/prompt): mobile-friendly composer tap-targets + iOS-zoom-fix
  (PromptBuilder textarea text-base sm:text-[15px], submit min-tap, ModePill px-3).
- `6b2d68c` fix(viewser/wizard,builder): systematic tap-target upgrade — utility
  buttons (InlineHelpButton, AssetDropzone "Välj fil", DirectivesPreview Copy,
  QuickPromptButton — alla min-tap sm:min-tap-0).
- `64445bb` fix(viewser/canvas): hero typography scale + console-drawer safe-area
  (ViewerPanel text-3xl sm:text-4xl md:text-5xl + px-5 sm:px-12, ConsoleDrawer
  pt-safe + pb-safe-or-4).
- `712a3c2` fix(viewser/dialogs): mobile-friendly grids + iOS-zoom-fix på inputs
  (ai-image-generator grid-cols-1 sm:grid-cols-2 + max-h-[90dvh], asset-uploader
  grid-cols-2 sm:grid-cols-3, color-picker grid-cols-4 sm:grid-cols-6 + min-tap
  per swatch, alla inputs text-base sm:text-[X]).

Inga off-limits-paths rörda i fas 1 (`scripts/`, `packages/generation/`,
`apps/viewser/app/api/`, `apps/viewser/lib/`, `middleware.ts`, `next.config.ts`,
`package.json` — alla intakta).

Fas 2 (polish/P1) — completed (in-review). `GAP-viewser-mobile-responsive-polish`
adresserade: PromptBuilder textarea iOS-zoom-fix + min-tap-submit, `InlineHelpButton`
min-tap, `ViewerPanel` hero typografi `text-3xl sm:text-4xl` + padding `px-5
sm:px-12`, `ai-image-generator-dialog` mobile bottom-sheet-stack + grid-cols-1,
asset/color-dialog-grids responsiva, `ConsoleDrawer` flexibel höjd,
`AssetDropzone` + `DirectivesPreview` + `QuickPromptButton` tap-targets.

Fas 3 (final polish) — completed (in-review). `GAP-viewser-mobile-responsive-final-polish`
landat 4 commits ovanpå fas 1 + 2 i samma PR #117:
- `e05c443` docs(gap): complete fas 1+2 (in-review), open fas 3 — final polish.
- `18d84f5` fix(viewser): mobile responsive height + compare-modal swipe A/B.
  - `run-history.tsx` ScrollArea `h-[26rem]` → `h-[min(26rem,50dvh)]` (333px på 667px-skärm).
  - `compare-preview-modal.tsx` mobil snap-x swipe + A/B-pills + scroll-position-detection.
- `f850882` feat(viewser/canvas): device-toggle desktop preview + edge-pulse motion.
  - `viewer-panel.tsx` 4-knappars toggle 375/768/1024/Full med sessionStorage-persistence.
  - `globals.css` `.animate-fc-edge-pulse` 2.6s ease-out → 3s ease-in-out.
- `8724798` chore(viewser): term-coverage compliance.
  - Typ-namn slimmat (preset-suffix borttaget), laptop-jargong rensad, observer-API utbytt mot scroll-pos detection.

Scout-fixes (3 P0 + 12 P1) — completed (in-review). `GAP-viewser-mobile-scout-fixes`
adresserade alla högre-prioriterade fynd från scout-rapport `95f73fbf`
(composer-2.5-fast, read-only bug-hunt på diff `ea62e45^..8724798`). Landar
som 3 commits ovanpå fas 3 i samma PR #117:

- `6d0c896` docs(gap): complete fas 3 (in-review), open scout-fixes GAP.
- `cb6f43d` fix(viewser): scout P0 batch.
  - **P0 #1** — `pb-safe-or-3` utility lades till i `globals.css` (refererad i
    `ai-image-generator-dialog.tsx` sedan fas 2 men aldrig definierad → footer
    föll tillbaka till `py-3` på iPhone home-indicator-enheter).
  - **P0 #2** — iOS Safari auto-zoom-fix i hela wizarden. Alla `TextField`/
    textarea-fält i `step-primitives.tsx` + inline input/textarea/raw
    `<input>` i `content-step.tsx` (16 träffar), `foundation-step.tsx` (1) och
    `company-step.tsx` (1) gick från `text-[13px]` → `text-base md:text-[13px]`.
    Tidigare bara `prompt-builder` + dialogs adresserade i fas 2.
  - **P0 #3** — Mobile steg-chips i `discovery-wizard.tsx`. Tidigare `h-5 w-5`
    (20px) utan `min-tap`; nu `min-tap sm:min-tap-0` + `h-7 w-7` +
    `active:scale-95` + `aria-current="step"`.
  - **P1 #7** — Wizard footer-knappar (Tillbaka, Hoppa över, Fortsätt, Skapa
    sajt) fick `min-tap sm:min-tap-0`.
- `6e06129` fix(viewser): scout P1 batch.
  - **P1 #4** — `viewer-panel.tsx` hydration mismatch. `useState`-initializer
    läste sessionStorage SYNC → server "full"/klient "mobile" missmatch. Nu
    useState init = "full", async-IIFE-effect läser storage post-mount, en
    `deviceHydratedRef`-flagga förhindrar default-skrivning över sparad preset.
  - **P1 #5** — `FloatingChat` layout-flash. `useIsMobileViewport` startade
    false → desktop-placeholder syntes 1 frame innan effect. Nu
    `useIsomorphicLayoutEffect` (useLayoutEffect klient/useEffect server) +
    matchMedia-läsning innan paint.
  - **P1 #6** — iOS keyboard överlappar bottom-sheet composer. Ny
    `useKeyboardInset`-hook via `window.visualViewport`. Mobile aside får
    `style={{ bottom: inset, transition: "bottom 0.18s ease-out" }}` så
    panelen glider ovanför tangentbordet.
  - **P1 #8 + #15** — `ModePill` i prompt-builder min-tap + `aria-label`
    "Ny sajt-läge" för konsistens med "Följdprompt"-pillen.
  - **P1 #9** — compare-modal A/B-pill desync. `goToPane` anropar nu
    `setActivePane(target)` SYNC före `scrollIntoView`.
  - **P1 #10** — Ingen focus-flytt FAB → öppen chat. Ny `expandAndFocus`-
    callback + `composerRef` på composer-textarean. Båda FAB-onClick använder den.
  - **P1 #11** — Site Inspector saknade bottom-sheet drag-handle på mobil
    trots kommentar. Manuell `<div className="bottom-sheet-handle md:hidden" />`
    direkt i SheetContent + `max-md:pt-2` på SheetHeader.
  - **P1 #12** — Inspector refresh-knapp + alla `FloatingChat` mikro-kontroller
    (iterera-X, förslag-toggle, quick-prompt chips, bilaga-X) fick
    `min-tap sm:min-tap-0` + `active:scale-95`.
  - **P1 #14** — `sm:text-[15/13px]` zoom-risk på iPad portrait. `prompt-builder`
    hero-textarea + `floating-chat` composer + `color-picker` hex-input bytta
    till `md:text-[...]` (768px-breakpoint säkrare än 640px).

Inga off-limits-paths rörda i någon av faserna eller scout-fixes-passet.
Komplett check-svit grön (sprintvakt, focus, governance, rules-sync,
term-coverage --strict, ruff, tsc, ESLint, pytest 540+).

Mobile hero-flow — completed (in-review). `GAP-viewser-mobile-hero-flow`
adresserade tre fynd från manuell test på iPhone 14 Pro-viewport (393×852)
som scout-rapporten inte täckte. Operatör-driven post-scout-fix:

- `viewer-panel.tsx` mobile hero stacked layout. SM_hero.mp4 hade
  `[object-position:78%_center]` (designat för desktop bredd) → 3D-objektet
  hamnade bakom rubriken på mobil. Operatören levererade SM-mobile.mp4
  (960×960 fyrkantig, 1.1MB, off-white #f0f2ed) som mobile top-banner.
  Container blev `flex flex-col md:flex-row` med `bg-[#f0f2ed]
  md:bg-background` när hero visas så filmens bakgrund flyter sömlöst in
  i canvasen. Hero-text staplad under videon på mobil (centrerad), absolute
  overlay vänsterställd på desktop (oförändrat).
- Hero-rubriken hade hårdkodad `<br />` + `max-w-lg` → radbröts till
  "Beskriv / din sajt / så bygger / vi den" på 393px. `<br />` borttagen;
  texten flödar nu naturligt via text-balance.
- `wizard-types.ts` foundation-validering: företagsnamn-min-längd-kollen
  borttagen på operatör-begäran så snabb-test av wizarden går smidigare.
  Övriga foundation-validations (offer.length ≥ 3, businessFamily required)
  kvarstår som signal till pipeline.

Scout pass 4 — `GAP-viewser-mobile-hero-safe-zone` (in-progress). Operatören
körde fjärde scout-bug-hunt (composer-2.5-fast, read-only) på de tre senaste
commits innan PR-update. Inga P0 men tre konkreta P1:

- `viewer-panel.tsx` mobile hero safe zone. På iPhone SE (375×667) räckte
  inte 667px för video~300px + text~200px + PromptBuilder~150px → hero-
  underrad döljdes bakom composern. Container fick `md:overflow-hidden`
  + `overflow-y-auto bg-[#f0f2ed]` när `showHero=true` (desktop oförändrad).
  Hero-text container fick `pb-40 md:pb-0` så composer-overlap aldrig sker
  vid normal text. Desktop absolute-overlay-layout intakt.
- `foundation-step.tsx` + `company-step.tsx` Wizard-asterisk. Båda visade
  "Företagsnamn *" trots att validering togs bort i 59eed4c → WCAG 2.2-brott
  (visuellt obligatoriskt fält som går att lämna tomt). Label nu enbart
  "Företagsnamn" med `optional`-prop som FieldLabel renderar som "(valfritt)".
- `prompt-builder.tsx` composer safe-area. `pb-5 sm:pb-7` saknade safe-area-
  koll → composer-knappar 0px från iPhone X+ home-indicator. Bytt till
  `pb-safe-or-4 sm:pb-7` (samma standard som wizard-footer och FloatingChat).

P1 #4 (StackBlitz containerRef-höjd) parkerad eftersom default-mode
`local-next` inte påverkas — bara aktuell vid `VIEWSER_PREVIEW_MODE=auto`
eller `stackblitz` (icke-default operatör-val).

Nya PRs sedan föregående checkpoint: PR #114 — chore(gitignore): re-ignore
`__pycache__/` under `packages/generation/build/` (B146 fallout); PR #115 —
sync(jakob-be -> main): #114 gitignore hygiene (post-#113 cleanup);
PR #135 (B155 backend — applied-effect-detektion + trace-event för fri
follow-up); PR #136 (B157 + BO6 + B155-backend + quality-gate routes-discovery);
PR #137 (B157 level 4 immutable build-dir + pointer-swap + GC). Main-HEAD
nu `40b7d29` (post-merge in i christopher-ui via merge-commit pending push).

Öppen PR utanför vår lane:

- **#116** (`cursor/dossier-candidate-intake-895d`) — `feat(backoffice): add dossier
  candidate intake from local files`. Backoffice-feature, ägs av jakob-be-lane.
  Do not start yet från christopher-ui's perspektiv.

### 2026-06-01 UTC — current-focus.md före `efbb425`

Last verified state: `efbb425` i `main` (2026-06-01 UTC, steward-auto efter PR #139 — sync: christopher-ui → main, UI/UX-batch + B155 UI + ADR 0034 väg B-UI). `jakob-be` har mergat in `origin/main` och bär de 10 backend-commitsen (topp `f62bd40`: ADR 0034 väg A copyDirectives, contact-route eval-fix, placeholder-contact-suppression) ovanpå — sync-PR `jakob-be → main` är nästa steg (kräver operatörs-OK + ev. live-test). Tre read-only scouts 2026-06-01 PM: backend-diff grön, PR-triage + #139-djupgranskning utan blocker. Alla guards gröna (governance, rules_sync, term_coverage --strict, ruff, sprintvakt) + 25 nya copydir-tester. **Riktigt LLM-anrop verifierat** (copyDirectiveModel, ej mock).
Nya PRs sedan föregående checkpoint: PR #139 — sync: christopher-ui → main (UI/UX-batch + B155 UI + ADR 0034 väg B-UI), mergad. Öppna nu: #140 (`cursor/preview-runtime-bite-b-di → jakob-be`, draft, Bite B via dependency-injection), #138 + #141 (docs Cloud-setup till `main`, draft; #141 har en term-coverage-enradsfix kvar). Kommande: sync-PR `jakob-be → main`.

Aktuell priordning + färsk orchestrator-handoff: se
[`docs/handoff.md`](handoff.md) toppblocket. Kort: #139 (UI-batch inkl. B155
FloatingChat-no-op + copyDirectives väg B-UI) är mergad till `main`. Nästa:
(a) sync-PR `jakob-be → main` för backend väg A + eval-/placeholder-fixar
(operatörs-OK); (b) Bite B (#140) mergas in i `jakob-be`, helst före sync-PR;
(c) tre låg-impact UI-fynd kvar i Christophers lane. B157 nivå 4 (Stage A+B)
ligger redan i `main`.
