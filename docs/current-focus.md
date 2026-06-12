# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~12:00 — hostad preview-standardisering, ADR 0055)

**Git:** `main = jakob-be` (rent träd, local == origin). Förmiddagspasset är
landat direkt på `jakob-be` på operatörsmandat (Jakob ~11:00) och synkat till
`main`. Production deployar från `main`. **Tarball-omladdning KRÄVS efter
main-mergen** (passet rör `packages/preview-runtime/` + `governance/`) —
gjord i avslutningen, verifiera KV-URL:en vid tvivel.

**Landat i förmiddagspasset (operatörsbeslut: Vercel Sandbox + Blob är
STANDARD för användarpreviews; StackBlitz förblir pausad, ej avvecklad):**

- **Docs-sanering:** föråldrade B194-/run-historik-påståenden rättade
  (deploy-guide, prompt-JSDoc, `.env.example`, `preview-runtime.md`,
  rättelsenot i ADR 0033).
- **Preview-refresh-gate:** followups med visibleEffect `none`/`registered`
  river inte preview-sandboxen — `previewRunId` skiljs från `selectedRunId`
  i studio-sidan; FloatingChat trådar signalen via delade
  `readFollowupVisibleEffect`. Lås: `tests/test_viewser_preview_refresh_gate.py`.
- **Byggstart stoppar previewn:** `startHostedBuild` stoppar
  preview-sessionen före `Sandbox.create` (paritet med lokala build-runner;
  best-effort).
- **Pre-built hostat (ADR 0055):** bygget laddar upp `.next` (minus
  cache/trace) till blob; preview-sandboxen kör `npm install --omit=dev` +
  `next start`, ärlig fallback utan komplett `.next`.
- **Default-flippen:** tomt `VIEWSER_PREVIEW_MODE` = `vercel-sandbox`
  (registry, policy v4, next.config, dev.mjs, viewer-panel; `.env.example`-
  mallen sätter `local-next` explicit för lokal dev).
- **Reuse i prod:** sessions-snabbväg med buildId-invalidering mot
  `viewser:site:<siteId>:current` + liveness-probe; `VIEWSER_SANDBOX_REUSE=1`
  satt i Vercel (Production+Development; Preview-miljön blockerades av en
  CLI-bugg — sätt manuellt i dashboarden vid behov).

**Tillägg ~13:30 (hotfix-pass efter prod-E2E-incidentutredningen):** tre
fixar direkt på `jakob-be` + ff `main` (operatörsmandat): (1) hostad
preview-POST snabbare — blob-filerna laddas nu ner med begränsad samtidighet
(16 parallella, `downloadBlobEntries` i `generated-blob-source.ts`; vakter
och fel-semantik oförändrade, enhetstester utökade); (2) ärlig submit-gate i
FloatingChat — de tysta early-returns loggar nu `console.warn` med vilken
vakt som stoppade, upptagen-läget visar statusrads-hint och saknad siteId ger
ärligt fel i chatten (vakterna är oförändrade i styrka); (3) lyckad
sandbox-preview-start loggar EN server-side JSON-rad med fas-timings +
prebuilt/reused-flaggor i `vercel-sandbox-runner.ts`. Plus deploy-fix:
`ignoreCommand` i `apps/viewser/vercel.json` är nu fail-open när
`VERCEL_GIT_PREVIOUS_SHA` saknas i den grunda klonen (gav "fatal: bad
object" + deploy-ERROR på första hotfix-pushen).

**Nästa 3 prioriteringar:**

1. **E2E-verifiera hela standardvägen i produktion** på `/studio`: init →
   preview (pre-built, kolla `timings`) → no-op-följdprompt (previewn ska
   INTE rivas) → edit-följdprompt (ny version → invalidering → ny sandbox)
   → re-POST (reused:true). Även B199 v2/#307-flödet från morgonpasset.
2. **B197 (Christophers, pågår):** `hosted-build-runner.ts` +
   `vercel-sandbox-runner.ts` ändrade IGEN — tidig rebase krävs
   (msg-0085).
3. **Uppföljningar:** blob-/KV-prune (mer angeläget nu — `.next` i
   `generated/`), `changeSet` hostat, Preview-miljöns reuse-flagga,
   Safari/Firefox-E2E för B125-stängning.

**Öppna blockers:** inga hårda.

Last verified state: `9671de59` (2026-06-12 ~13:20 UTC+2; squash-merge av #310
— feat(build) dossier-deklarerade dependencies in i genererad package.json,
ADR 0056 — ovanpå focus-bumpen `3c8e5aa7`. Full CI-svit grön på PR-head,
MERGEABLE/CLEAN, `main` ff:ad till samma SHA. **Tarball-omladdningen är GJORD**
direkt efter mergen (#310 rörde `scripts/` + `governance/`): build-kontexten
ompaketerad från merge-commiten och uppladdad till blob
`build-context/current.tar.gz`, KV-nyckeln `viewser:build-context:url`
uppdaterad — hostade byggen kör nu rätt Python-kod. Hotfix-passet ovan
(~13:30) rebasades ovanpå denna SHA — #310-mergen landade mitt under passet,
ytorna var disjunkta precis som förutsett. Hela grindkedjan — ruff,
governance_validate, rules_sync --check, term-coverage --strict, full
pytest-svit (-n auto), tsc --noEmit, eslint och blob-source-testerna — körd
grön lokalt på hotfix-ändringarna efter rebasen, och kodcommits pushas DIREKT
efter den här docs-commiten så prod-rebuild inte cancelas av ignoreCommand.)

## Öppna PR att känna till

Inga öppna just nu. #306, #307, #308, #309 och #310 är squash-mergade
till `jakob-be` och ff:ade till `main`. (#310 = feat(build)
dossier-deklarerade dependencies in i genererad package.json, ADR 0056,
mergad 2026-06-12 ~13:20 — tarball-omladdning gjord direkt efter, se
Last verified state. #309 = test(eval) deterministisk
conductor-classification-baseline, testfil-only, mergad 2026-06-12 ~12:55 —
Vercel prod-rebuild kan ha cancelats av ignoreCommand, väntat. #308 =
docs(heavy-llm-flow) ärlighetspass, mergad ~12:45 efter rebase + fyra
review-fixar; konflikten i `handoff-orchestration.md` löstes till PR:ens stubb.)

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
