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

Last verified state: `3b61c7362f1726b424d3331eacf216d2a939a3be` (2026-05-26 late evening UTC, post Gap 10 product-image merge).

Nya commits sedan föregående checkpoint (`0f3bd67`):

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

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`. Christopher jobbar default på `christopher-ui`.
- `main` är canonical/sanningsbranch. Operatören eller agenten öppnar PR
  från arbets-branchen mot `main` när "en ny officiell version ska in" —
  ingen schemalagd cadence, det är ett beslut per leveransfönster.
- Efter merge: arbets-branchen synkas till `origin/main` (`git reset --hard
  origin/main` + `--force-with-lease`-push), inte via separat PR.
- Detaljerade regler: [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md).

## Pågående/öppna PR:s just nu

Inga öppna PRs på `jakob-be` eller `main`. `jakob-be` är resetad till
`origin/main` 2026-05-26 PM (commit `1004122`) plus 35 commits ovanpå
(listan ovan). Nästa sync-PR till `main` är operatörens beslut — bra läge
nu när Gap 4 + 5, Gap 6 + 7, Gap 9 och Gap 10 är inne.

**Christophers `origin/christopher-ui`** — efter PR #117 är hans branch
synkad mot post-#117-main. Han har under operator-OK scope-leak
implementerat hela `GAP-backend-build-trace-endpoint` (3 endpoints + UI +
5 bug-hunt-fixes). Ej PR:ad mot `main`; Jakob är reviewer. Workboardens
`owner` är medvetet kvar på `jakob` så Sprintvakt-lane-policyn passerar.

## Direkt nästa fokus

1. **Backend-Gap fixar baserade på C4-audit** (cloud-grind levererade
   audit 2026-05-26 i PR #121, `0f3bd67`; Gap 4 + 5 stängdes 2026-05-26
   evening i `b89a3d2` + `1b91ca6`; Gap 6 + 7 stängdes i `ea6e141`;
   Gap 9 stängdes i `365c1d7`; Gap 10 stängdes i PR #122 / `3b61c73`).
   Status efter Gap 10: 11 stängda, 0 delvis, 0 öppna.
2. **Sync-PR `jakob-be → main`** — `jakob-be` är 35 commits framför
   `origin/main`. Bra läge nu när backend-gap-batchen är klar.
   Operatörens beslut.

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

1. Sync-PR `jakob-be → main`.
2. Christophers `GAP-backend-build-trace-endpoint`-PR (när han öppnar den).
3. B49 (docs-base page-map sidebar) — låg prio, behövs innan
   `course-education → docs-base` aktiveras.
4. B13a arkitektur-flytt — kvarstår som öppen post, kräver egen sprint
   + sannolikt egen ADR.
5. B53, B47, BO4-followup-cancel — låga, ingen blocker.

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
