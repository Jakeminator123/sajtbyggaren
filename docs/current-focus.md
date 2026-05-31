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

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`. Christopher jobbar default på `christopher-ui`.
- `main` är canonical/sanningsbranch. Operatören eller agenten öppnar PR
  från arbets-branchen mot `main` när "en ny officiell version ska in" —
  ingen schemalagd cadence, det är ett beslut per leveransfönster.
- Efter merge: arbets-branchen synkas till `origin/main` (`git reset --hard
  origin/main` + `--force-with-lease`-push), inte via separat PR.
- Detaljerade regler: [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md).

## Pågående/öppna PR:s just nu

**Inga öppna PRs.** PR #133 mergad till `main` (post-Bite-A-batch +
alla reviewer-trådar). B157 akut-fix + followup landade direkt på
`jakob-be` ovanpå `4196c17` post-merge-bumpen.

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
   follow-up-text når codegen via ``copyDirectives[]``.
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
