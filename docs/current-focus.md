# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~03:30 — nattpass: hostad paritet-fixar shippade, två cloud-prompter köade)

**Git:** `main = jakob-be` (rent träd, local == origin). Senaste
kod/canvas-commit `575af63b`; detta docs-pass ligger ovanpå. Production
(`sajtbyggaren-viewser.vercel.app`) kör senaste app-bygget; rena docs-pushar
skippar prod-rebuild med flit (`ignoreCommand` jämför mot
`VERCEL_GIT_PREVIOUS_SHA`, fallback `HEAD^`), så prod kan peka på senaste
app-ändringen snarare än main-HEAD — väntat monorepo-beteende.

**Shippat i natt (efter midnattsblocket):**

- Banner-ärlighet: "lokalt" = operatörens lokala miljö, inte den hostade
  vyn (`4162a14a`).
- Flagg-medveten hostad notis: med `VIEWSER_ENABLE_HOSTED_BUILD=1` säger
  bannern att byggen kör i Vercel Sandbox, bara historik/artefakter är
  lokala (`bc074edb`).
- Hostad builder-paritet, live-bevisad: FloatingChat tänds när ett bygge
  slutförts i sessionen även med tom `/api/runs`, och följdprompt-byggen
  överlever rebuild hostat via selectedSiteId-fallback (`cdd6785d`,
  `b4f6e2d2`).
- Hostade artifacts/trace/files-404:or tystade i UI:t (lugn notis + latch i
  stället för rött fel och meningslös polling) + B199 dokumenterar
  blob-utredningen (`691bd835`).
- Härdad preview readiness-poll: 502/503/429 räknas inte som "klar", så
  hostad preview inte visar sandbox-uppstart som fel (`15ea0fda`).
- Canvas-rättningar: `OPENAI_MODEL` är `gpt-5.4` i prod (`ed0a2039`),
  autogen-facts regenererad (llmModelsVersion 12, hard-dossier 1)
  (`42a54945`), env/fallback-callout rättad (`575af63b`).
- Sedan midnattspasset: `main` låst med ruleset "protect-main-production-lane"
  och `ignoreCommand`-fällan fixad (`74dc9218`).

**Verifierat/avlivat i natt:**

- Pipen är hybrid (`gpt-5.4` för brief/plan/copy, deterministisk codegen) —
  inte "rent mekaniskt".
- Ingen automatisk `gpt-5.4` → `gpt-5.5`-modellfallback finns (det var en
  sammanblandning); kod-fallbacken `gpt-5.5` träffar bara när env-nyckeln
  saknas.
- Env-domar (lämna osatta på Vercel): `OPENCLAW_ROUTER_LLM_FALLBACK` är
  no-op i hostad väg och `VIEWSER_SANDBOX_REUSE` är disk-only (ingen effekt
  hostat).
- Extern review verifierad: hostat KÖR-7-paritetsgapet är PARTIELLT, inte
  total avsaknad — legacy-vägen kör copy-directives.

**Öppna issues:** B199 (hostad artefakt-hydrering — förutsättning för hostad
KÖR-7), B197 (discovery-paritet hostat), B198 del b (contact-form-render;
fungerar redan hostat via legacy-vägen).

**Köade cloud-prompter (PR:as mot jakob-be):**

1. Hostad follow-up-paritet — tre ordnade commits (B199-hydrering → sandbox
   apply-seam → request/response-paritet), root-cause-ledd, körs först.
2. B198 del b contact-form-render — oberoende spår.

Vår action: reviewa inkommande cloud-PR:ar snabbt (lane review-SLA).

Last verified state: `84d4facf` (2026-06-12 ~03:30 UTC+2; `main = jakob-be`,
rent träd, local == origin. Nattpassets kod/canvas-checkpoint `575af63b` +
docs-pass ovanpå. Hostad paritet-fixar `4162a14a`/`bc074edb`/`cdd6785d`/
`b4f6e2d2`/`691bd835`/`15ea0fda` + canvas-rättningar `ed0a2039`/`42a54945`/
`575af63b`. Öppen draft-PR: #306 (B198 del b).)

## Öppna PR att känna till

**#306** (cloud-lane, draft mot `jakob-be`): B198 del b — synlig
contact-form-render på ecommerce-lite. Det är köad cloud-prompt 2; reviewa
snabbt enligt lane-grindens review-SLA när den lämnar draft. Fortfarande
väntad: köad cloud-prompt 1 (hostad follow-up-paritet — B199-hydrering →
sandbox apply-seam → request/response-paritet).

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
