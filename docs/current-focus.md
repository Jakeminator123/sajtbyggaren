# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-14 ~22:00 — prod-E2E bevisad, direktiv-läckage-fix för kundkopian, docs-städning)

**Git:** alla fyra referenserna stod på `41a24d77` (#319 B204) vid rundans
start. Denna runda shippar PR `fix/directive-copy-leak` → `main` (squash) med
direktiv-fixen + docs; `jakob-be` ff-synkas så att
`main = jakob-be = origin/main = origin/jakob-be`. Production deployar från
`main`. Föregående focus-block (takeover-prep 2026-06-14 ~17:00) ligger som
historik överst i [`docs/handoff.md`](handoff.md).

**Nya PRs sedan föregående checkpoint:** #322 `fix/directive-copy-leak` (denna
runda, squash-mergad till `main` som `be3795ce`). #317 (Cloud Agent env-setup)
mergades 2026-06-14 (`7ba0cd95`); #318/#319 dessförinnan — alla redan i `main`.

**Denna runda i korthet:** (1) kärnloopen
`prompt → företagshemsida → preview → följdprompt → ny version` live-validerad
på hostad prod (#316 omfärgning, #318 "Om oss"-copy, B204 svenska tecken — alla
bekräftade landa); hostad prod-E2E via Vercel Sandbox bevisad. (2) Preview-
arkitekturen klargjord: `*.vercel.app` = Viewser-appen, `*.vercel.run` = den
efemära per-bygge-previewen (om-mintas varje bygge, cross-origin-iframe i
`/studio`) — inget felkonfigurerat. (3) `VIEWSER_SANDBOX_REUSE=1` konsekvent
över Production/Preview/Development (Preview satt via Vercel REST API).
(4) Direktiv-läckage-fixen: en deterministisk grind (`_looks_like_directive`)
som hindrar `briefModel`-instruktionstext från att renderas som synlig
"Om oss"-/hero-copy (`packages/generation/planning/blueprint.py` +
`packages/generation/brief/extract.py`, 6 nya tester). Detaljer + full
nästa-steg-lista: [`docs/handoff.md`](handoff.md).

Landat 2026-06-15 (denna runda): #321/#323 mergade; docs-drift lagad; och
`directive_leak`-kritikern (`07ed6939`) — `_looks_like_directive` lyft till en
delad signal (`packages/shared/directive_signal.py`) som både planning
(prevention, #322) och quality_gate (detektion, försvar på djupet) delar, så de
aldrig driftar. Single source, ingen dubblering. Dessutom: konduktorn (OpenClaw
Core V0 `decide`) ger nu ett grundat novel-intent planeringssvar för en tydlig
men ännu obyggbar ändring (`_edit_plan_steps` i `core.py`) i stället för en stum
action_bridge_missing — ärligt (ingen falsk success, #313), deterministiskt,
ersätter ett specialfall i stället för att lägga ett. Planeringssvaret är nu
dessutom katalog-medvetet (ADR 0059): det skiljer en känd, monterbar
katalog-sektion/-komponent från en genuint ny som ärligt kräver intag — enbart
via router-data, ingen apply/render-ändring (den synliga monteringen är nästa
verifierade pass). Och: model routing v13 (`llm-models.v1.json`) — planning/
router/verifier på gpt-5.5 (high reasoning, högre tokentak), rerank på
gpt-5.4-mini, brief → medium reasoning; centralt + reversibelt via policyn +
`llm_model_params.py` (inga hårdkodade modeller). OBS: gpt-5.5/gpt-5.4-mini
behöver real-key-smoke mot prod-nyckeln innan vi förlitar oss på dem (CI/tester
mockar utan nyckel och fångar inte modell-tillgänglighet). Slutligen: tre
review-flaggade buggar fixade — #318 additiv-vakt (`6062928c`: två citat muterar
aldrig copy), och #322-härdning (`d7dea188`: droppar directive-formade
tjänste-kort + engelska craft-termer via den delade signalen).

**Nästa 3 prioriteringar (snabba kvalitetsvinster först; full prioriterad lista i handoff):**

1. **Fritext-övertolkning → påhittade "service"-kort** (snabb–medel): fri
   prompttext blir ibland stray tjänste-kort kunden aldrig bett om; avgränsa
   till grundade tjänster (samma ärlighets-tema som directive-fixen).
2. **Tema-trohet — "Casual Café" renderas grått** (medel, kundnära): #316
   landade omfärgning via tema-utföraren, men en namngiven tema-cue mappar i
   dag till grått; höj tema-mappningens täckning så vald stämning syns.
3. **Katalog-mount: synlig render (ADR 0059)** (medel; coach-beslut 2026-06-15;
   kräver visuell check som #320): konduktorn känner nu igen monterbara
   katalog-sektioner/-komponenter (V0 `decide`, katalog-medvetet planeringssvar)
   och mount-maskineriet finns redan (`section_directives.py` + apply). KVAR för
   user-synligt värde: bredda den synliga render-vägen (reviews/trust → inline/
   dedikerad route som faq/team) så "lägg till testimonials" faktiskt syns — det
   rör prod-render, därför ett fokuserat pass med din visuella check, inte fri
   generativ kod.

Större roadmap-program (efter snabbvinsterna): B197 hostad discovery-paritet
(nu UPPLÅST sedan prod-E2E är grön; koordinera med Christophers spår
`hosted-build-runner.ts`, msg-0085) och konduktör "Steg 1" (montera
katalog-komponenter, kräver ADR-utökning av 0057). Trivialt/opportunistiskt:
normalisera `VIEWSER_SANDBOX_REUSE`-typ på Vercel (`sensitive`→`encrypted`,
rent kosmetiskt). Underlag:
[`docs/heavy-llm-flow/conductor-vision-roadmap.md`](heavy-llm-flow/conductor-vision-roadmap.md).

**Öppna blockers:** inga hårda.

Last verified state: `d7dea188` (2026-06-15 ~12:20 UTC+2; `jakob-be` = HEAD,
12+ commits före `main` = `f4e02756`: #321/#323 mergade, docs-drift,
directive_leak-kritiker + delad signal (`07ed6939`), ADR 0059 (`f481d201`) +
render-utredning (`d3c1a034`), novel-intent + katalog-medveten plan
(`9d749486`/`64800d12`), model routing v13 (`d49d1ab8`), review-fixar #318
(`6062928c`) + #322-härdning (`d7dea188`); `origin/jakob-be` i synk efter
push, working tree rent; `main`/`origin/main` orörda på `f4e02756`).
Föregående: `b4a818c1`.

## Öppna PR att känna till

Rundans egen PR #322 (`fix/directive-copy-leak`) squash-mergades till `main`
och raderades (lokal + origin). #317 (Cloud Agent env-setup, `7ba0cd95`)
mergades 2026-06-14.

Christophers tre PR (`chgenberg`, viewser-lanen) triagerades 2026-06-15: två
mergade till `jakob-be` (gröna, CLEAN, små diffar — jakob-be-lanens review-SLA),
en hålls för operatörens visuella browser-check.

- #321 (`fix/b160-marketing-header-logo-lock`): mergad till `jakob-be`
  (`cb5c943c`, squash). fix(viewser) B160 — regressions-lås utökat till tredje
  logo-renderaren (kod-fixen fanns redan); rena tester + docs.
- #323 (`fix/honest-no-op-keeps-unapplied-list`): mergad till `jakob-be`
  (`a45dc0eb`, squash). fix(viewser) — den itemiserade unapplied-listan följer
  nu med även när dirigentens answerText vinner (#313-ärlighet).
- #320 (`feat/build-progress-perceived-latency`): öppen, hålls för
  operatörens visuella check. feat(viewser), bygg-kortet känns levande under
  hostat bygge — grön CI, 1 fil (`viewer-panel.tsx`), men ren UI-känsla bör
  ses i browser innan merge.

Konsekvens: `jakob-be` ligger nu **2 commits före `main`** (`main` = `f4e02756`,
`jakob-be` = `a45dc0eb`), 0 bakom. Synk `main` ← `jakob-be` görs vid nästa
officiella version (eller direkt om operatören vill ha #321/#323 i prod nu).

#306–#319 är squash-mergade till `jakob-be` och synkade till `main`
(tip vid rundans start `41a24d77` = #319 B204). Äldre detaljer:
arkivet + `docs/handoff.md`.

Christophers UI-arbete sker på `christopher` (gamla `christopher-ui` är fryst legacy).

## Vem uppdaterar denna fil

**Agenten.** Inte operatören. Efter varje merge/sync som ändrar nästa agents
arbete: bumpa SHA:n på "Last verified state"-raden, uppdatera de tre
prioriteringarna + blockers, och flytta utgånget innehåll till arkivet (se hygien-regeln). Steward
post-push-verifierar `origin`-SHA, `git status` och `python scripts/focus_check.py`.
Uppdatera inte för ren mikrostatus som inte ändrar nästa agents arbete.

## Branchmodellen (kort)

- Jakob jobbar default på `jakob-be`; Christopher på `christopher`. `main` är
  canonical/sanningsbranch.
- PR från arbets-branch → `main` när "en ny officiell version ska in" (beslut
  per leveransfönster, ingen cadence). Efter merge synkas arbets-branchen mot
  `origin/main`.
- Detaljer: [`governance/rules/04-branch-and-team.md`](../governance/rules/04-branch-and-team.md).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) ("Standard loop"). Kort: Scout
vid behov → arbete på arbets-branch → guards gröna (riktade tester lokalt,
full svit i CI per guard 5) → push → vid behov PR mot `main` → post-merge-sync.
Orkestrering över längre pass:
[`docs/orchestrator-playbook.md`](orchestrator-playbook.md).

Operatörspreferens: svenska, kort och koncist, gärna matris/tabell. Förklara
dev-uttryck med korta parenteser första gången per konversation. Mönstret i
[`governance/rules/01-language-and-reply.md`](../governance/rules/01-language-and-reply.md).

## Arkiv

Historiska statusblock + checkpoint-kedjan ligger i arkivet:

- [`docs/archive/current-focus-2026-06-12-kvall.md`](archive/current-focus-2026-06-12-kvall.md)
  (kvällsblocket per `54de9b9c`: #314/#315-mergarna, slutlig main-sync för
  operatörens produktions-E2E).
- [`docs/archive/current-focus-2026-06-12-em.md`](archive/current-focus-2026-06-12-em.md)
  (eftermiddagsblocket per `56dc754f`: #310–#313-mergarna, branch-städning,
  första main-synken för produktionstest).
- [`docs/archive/current-focus-2026-06-12-middag.md`](archive/current-focus-2026-06-12-middag.md)
  (middagsblocket per `f642b1a5`: ADR 0055 preview-standardisering,
  hotfix-passet ~13:30, #308–#311).
- [`docs/archive/current-focus-2026-06-12-morgon.md`](archive/current-focus-2026-06-12-morgon.md)
  (morgonblocket per `261f0c63`: B199 v2 — hostad run-historik/artefakter
  live, omladdnings-återställning).
- [`docs/archive/current-focus-2026-06-12-gryning.md`](archive/current-focus-2026-06-12-gryning.md)
  (nattpassblocket per `575af63b`: hostad builder-paritet shippad, 404-tystnad,
  readiness-poll, canvas-rättningar, två cloud-prompter köade).
- [`docs/archive/current-focus-2026-06-12-natt.md`](archive/current-focus-2026-06-12-natt.md)
  (midnattsblocket per `5109cc1f`: B194 live/E2E-bevisad, main-sync klar,
  lane-grind i regel 04, CI-actions v6).
- [`docs/archive/current-focus-2026-06-11-kvall.md`](archive/current-focus-2026-06-11-kvall.md)
  (kvällsblocket per `6d740fcc`: OpenClaw-smartness #296–#303, #269, /kort-regeln).
- [`docs/archive/current-focus-2026-06-11-em.md`](archive/current-focus-2026-06-11-em.md)
  (lunchblocket per `a314fe5a`: P2-skeppningen, #284–#290-kedjan, publik drift PÅ).
- [`docs/archive/current-focus-2026-06-11-fm.md`](archive/current-focus-2026-06-11-fm.md)
  (förmiddagens fulla block: nattpasset 2026-06-10, #270–#287-kedjan, eval-facit).
- [`docs/archive/current-focus-2026-06-08-pre-slim.md`](archive/current-focus-2026-06-08-pre-slim.md)
  (full snapshot precis före slimningen 2026-06-08).
- [`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md)
  (äldre checkpoint-kedja).

För commit-historik: `git log --oneline origin/main` eller
`git log --oneline origin/jakob-be`.

## Föregående checkpoint

Tidigare "Last verified state"-block och äldre "Current objective"-block är
flyttade till arkivet ovan (per `governance/rules/07-docs-focus-handoff.md`).
Auto-bump-verktyget lägger nya korta checkpoint-block här vid main-sync; håll
högst ett kvar och flytta resten till arkivet.

### 2026-06-11 UTC — current-focus.md före `ab8755a6`

Last verified state: `a314fe5a` (2026-06-11 ~13:30 UTC+2; #288/#289/#290
mergade + andra main-syncen, publik drift PÅ). Fulla blocket:
[`docs/archive/current-focus-2026-06-11-em.md`](archive/current-focus-2026-06-11-em.md).
