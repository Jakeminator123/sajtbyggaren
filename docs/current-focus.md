# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-11 ~13:30 — hostad publik drift LIVE, dagens pass stängt)

**Git:** `main = jakob-be = a314fe5a` (tom diff, rent träd). Pre-sync-backuper:
`backup-main-2026-06-11-pre-sync` (= `26b2464`) + äldre `backup-170-BRA`.
Produktionen (`sajtbyggaren-viewser.vercel.app`) deployas från `main` och kör
HEAD — verifierad Ready efter dagens sync.

**Stora bilden (P2 SKEPPAD + publik drift PÅ, operatörsbeslut 2026-06-11):**
vem som helst kan skapa en användarsajt på prod-URL:en — prompt → Python-pipen
körs i en Vercel-sandbox (build-kontext-tarball från blob) → bygget publiceras
till blob (`generated/<siteId>/`, manifest-baserad servering) → KV (Upstash
Redis) bär pekare/status/sessioner → sandbox-preview i iframen. Skydd i drift:
rate-limit per IP (ADR 0050), sandbox-TTL, B196-fixad statusroute. Den gamla
driftspärren är HÄVD (operatörsbeslut, se known-issues + inbox msg-0071).

**Dagens facit (2026-06-11, sju PR:ar mergade + 2 main-syncar):**

- **#284** hostat bygge i Vercel-sandbox + kv-store-adapter + publik
  rate-limit (ADR 0048/0049/0050); spoofsäker klient-IP fixad före merge.
- **#286** Vercel-env-konsolidering: 22 rader "All Environments", noll
  branch-avvikelser; lokala env-filer städade; matris i
  `docs/operations/hosted-viewser-manual.md`.
- **#287** B195: manifest-baserad servering stänger stale-blob-gapet.
- **#288** review-sweep: B196 stängd (siteId-bunden statusroute), KV-preflight
  före Sandbox.create, hostad icke-stream-väg väntar in done/failed
  server-side (202-buggen i floating-chat/use-followup-build eliminerad),
  #283-granskningens tre fynd fixade (sektionsmedveten bastext, tom-bas
  no-op, hero-pin-paritet), deploy-dokumentet omskrivet för publik v1.
  B197 trackad (discovery-paritet hostat, P3).
- **#289** guard-snabbning (operatörsbeslut): riktade tester är lokal
  default; full svit = CI:s jobb på PR; full svit lokalt med pytest-xdist
  `-n auto` (~5 min i stället för ~13). Regel i
  `governance/rules/04-branch-and-team.md` guard 5 + `docs/testing.md`.
- **#290** analysrapporten `docs/reports/sajtmaskin-vs-sajtbyggaren-analys-2026-06-10.md`
  landad med term-disciplin (form-only; innehållet orört). Term-coverage är
  åter helt grön för alla agenter.
- Operatörsmanual: `docs/operations/hosted-viewser-manual.md` (läs vid drift).
- Blob-upload-buggen i produktion (tyst noll-varvs-loop) fixad + verifierad
  med riktiga byggen (`fa268c5`, `0494e7f`).

**Riktning (operatörens kritiska gallring av analysrapporten — rapporten är
uppslagsbok, INTE backlog):** sajtmaskin är strikt read-only-referens.
Antaget därifrån: contact-dossier först, eval-baseline-grind, autofix som
ARBETSREGEL (egna haverier → fixer-regel + test; ingen blind portning).
Avvisat/parkerat: hård radgräns-CI, truth_level-svep, scaffold-expansion,
apps/web, deploy-paket (alla bakom framtida operatörsbeslut).

**Nästa prioriteringar (i ordning):**

1. **Christophers lane-rebase** (klartecken skickat, msg-0072): #269 +
   Verktyg fas 1–3 + bildbyte-guarden + #285-konsolidering mot jakob-be
   (HEAD `a314fe5a`). route.ts-threading läggs OVANPÅ hostade grenen;
   naming-dictionary tar v35. Vår toolIntent-backend-halva läggs ovanpå
   när rebasen landat.
2. **Första hard-dossier: resend-contact-form** (skördelista A4) — stänger
   `contact`-svagheten från Golden Path-evalen (8.2/10). Kräver schema
   v2-ADR (nästa lediga: 0051). Pipeline: candidate → reviewed → verified
   → enabled.
3. **Eval-baseline-grind i CI** (skördelista A3): committad baseline +
   regressionsregler ovanpå `run_golden_path_eval.py`/`run_eval_suite.py`.
   Draft-PR mot `jakob-be` öppnad från `feat/eval-baseline-grind`: committad
   baseline i `tests/evals/golden-path-baseline.json` (spårad, ej gitignorad),
   `scripts/eval_gate.py` + `tests/test_eval_gate.py`, eget Node-fritt
   CI-jobb `eval-baseline` (kör även `mini_eval.py`). Väntar operatörens merge.
4. **P3 — hostad followup + snabb uppstart:** persistera run-state (B194),
   discovery-paritet (B197), sandbox-snapshots/idle-stop (ADR 0041-spåret).
5. **Token Meter-priser (operatören, valfritt):** USD-priserna i Vercel-env
   sattes till 0 vid konsolideringen — sätt riktiga värden om kostnadsvisning
   önskas hostat.

**Öppna blockers / att-göra:**

- B192 (answer-only rött i dialog-vägen) — deferrad bakom Christophers
  #269-rebase, samma fil.
- B194/B197 — P3-spår (trackade, ej blockerare).
- B155 hålls öppen (kvarvarande targets).
- `christopher`-lanen äger: `use-followup-build.ts`, dialogerna,
  viewser-frontend/inspector — rör ej.

Last verified state: `a314fe5a` (2026-06-11 ~13:30 UTC+2; `origin/jakob-be =
origin/main = a314fe5a` efter dagens andra main-sync — #288/#289/#290 mergade
+ inbox msg-0072 till Christopher. Pre-sync-backup:
`backup-main-2026-06-11-pre-sync`. Produktions-deploy från main verifierad
Ready; hostad publik drift PÅ med rate-limit + B195/B196 stängda. ADR-liggare:
nästa lediga **0051**; 0046 hålls av öppna #285.)

## Öppna PR att känna till

- **#285** (`chgenberg`, nu retargetad mot `jakob-be`): ADR 0046 — markera
  modul i preview. Granskad (GO-med-fixar). Christopher konsoliderar den i
  sin lane-rebase (route.ts ovanpå #284/#288:s hostade gren; dictionary →
  v35; inspector-grunden ska landa EN gång med #269).
- **#269** (`christopher → jakob-be`): bär Verktyg fas 1–3 + bildbyte-guard +
  inspector-lanen. **Väntar Christophers rebase — hans action.** Klartecken
  skickat (msg-0072). Rör inte denna PR-yta.
- **#156** (`feat/live-preview → jakob-be`): parkerad arkitektur-referens
  (publik POST utan skydd); ersatt i praktiken av P2-leveransen — kan stängas
  vid tillfälle (operatörsbeslut).

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

### 2026-06-11 UTC — current-focus.md före `a314fe5a`

Last verified state: `758d8dd` (2026-06-11 ~11:20 UTC+2; #287 + #286 mergade,
main ff till jakob-be, backup-170-BRA). Fulla blocket:
[`docs/archive/current-focus-2026-06-11-fm.md`](archive/current-focus-2026-06-11-fm.md).
