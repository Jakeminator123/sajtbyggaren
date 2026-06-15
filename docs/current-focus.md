# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-15 ~17:30 — route_remove härdat, delivery-bias + build-context-guard mergade)

**Git:** `main = jakob-be = origin/main = origin/jakob-be = cd9bb0ba` (+ denna
rundas SystemExit-fix- och docs-commits). Production deployar från `main`.

**Stora planen + orientering för nästa agent:** läs det auktoritativa
orienteringsblocket ÖVERST i [`docs/handoff.md`](handoff.md). Där bor den fulla
beskrivningen (north star, de två flödena + action-bryggan, 4-fas-planen) — den
upprepas inte här. Denna fil håller bara status, nästa prioriteringar och blockers.

**Landat senast:** Route/Nav Mutation V1 (ADR 0060) — ta bort sida + nav +
interna länkar: #328 (Slice A), #332 (Slice B, contact + CTA-retarget + länk-scan),
#333 (härdning, 5 review-fynd) + en SystemExit-fix i `_base_disabled_route_ids`.
Dessutom #320 (bygg-kort), #329 (test-tiers), #330 (delivery-bias,
`docs/delivery-bias.md`), #331 (build-context-guard, `npm run build-context:check`).

**Nästa 3 prioriteringar** (faser/fullständig kapacitetslista i [`docs/handoff.md`](handoff.md)):

1. **Fas 1 — beslutsenhet:** `run_followup_chain` ska KONSUMERA dirigentens
   routerbeslut i st.f. att klassa om (rad ~4189). Tunn, ren vinst.
2. **nav-only** (`nav_edit`: "dölj i menyn men behåll sidan") — liten, naturlig
   efter route_remove-fynd 4.
3. **generativ komponent V1** (fas 4) — störst effekt mot "lägg till"-glappet.

**Öppna blockers:** inga hårda.

Last verified state: `cd9bb0ba` (2026-06-15 ~17:30 UTC+2; #330 + #331 mergade,
route_remove SystemExit-fix + stor-plan-docs denna runda). Öppen PR: #324
(Christophers viewser UI/UX — väntar operatörens browser-check). Föregående:
`1b998d70` (#333 route_remove-härdning).

## Öppna PR att känna till

- **#324** (`feat/viewser-uiux-prod-polish`, Christopher): viewser UI/UX-putts
  (banner-overlap, jargong, bygg-text + canary-skript). CLEAN + grön CI, men det
  är UI → hålls för operatörens browser-check innan merge.

Mergat denna runda (2026-06-15) och i `main`: #328/#332/#333 (route_remove V1 +
härdning), #320 (bygg-kort), #329 (test-tiers), #330 (delivery-bias), #331
(build-context-guard). Cloud-agenterna bakom #330/#331 är klara (kan stängas).

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
