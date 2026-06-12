# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~16:00 — avslutningsrunda: dagens mergar landade, main synkad för produktionstest)

**Git:** `main = jakob-be` (rent träd, local == origin) efter denna rundas
main-sync. Production deployar från `main`. Tarball-omladdningen är GJORD
(efter #312/#313-mergarna, se handoff) — build-kontexten i blob speglar
`56dc754f`. Alla PR-köer är tomma; sessionsbranches och worktrees städade
(se handoff).

**Landat under eftermiddagen (squash-mergat till `jakob-be`):**

- **#310 (ADR 0056, dossier-dependencies):** dossierer deklarerar pinnade
  npm-paket som följer med in i genererad `package.json`; npm ci med
  install-fallback.
- **#311 (Projektinnehåll-panelen):** site-composition-API +
  panel i ConsoleDrawer som visar sidor/dossiers/komponenter/paket,
  deriverat ur befintliga run-artefakter (lokalt + hostat).
- **#312 (uppgift E, komponentintag v1):** kurerad shadcn-intake-CLI
  (`scripts/component_intake.py`, ADR 0054), component_builder-rollkontrakt
  (ADR 0057), zero-dep accordion-pilot synlig på FAQ, naming v40,
  repo-boundaries v13, ny pip-dep `openai-agents==0.17.5`.
- **#313 (del F+D, ärlighetsfix):** `appliedFollowupDirectiveKinds`-signal +
  `intent_not_executable` stoppar falska "Klart!" (byte-diff räcker inte
  längre som framgångsbevis); ärlig okänd-slug i `unappliedFollowupIntents`;
  honesty-gates kräver konkreta direktiv; `generateFollowupOutcomeSummary`
  ger ärlig LLM-svarsrad på varje följdprompt.

Förmiddagens ADR 0055-pass (preview-standardisering) + hotfixarna är
historik: [`docs/archive/current-focus-2026-06-12-middag.md`](archive/current-focus-2026-06-12-middag.md).

**Nästa 3 prioriteringar:**

1. **Operatörens produktionstest på `main`:** hela E2E-flödet på `/studio`
   i produktion (init → pre-built preview → no-op-följdprompt → edit-
   följdprompt → reuse), nu inklusive #312/#313-beteendet. Görs av
   operatören separat — agenter ska INTE förekomma testet.
2. **Uppgift G (nästa byggsteg):** snabb chat utan sandbox-spinn för rena
   frågor + tarball-bundling för förbyggda previews.
3. **Backlog/deferred (ej blockers):** componentSource/mountRules/
   qualityGate-dossierfälten från E; viewser-rolletikett för
   component_builder; deterministisk intent_not_executable-rad för
   no-key-fallet från F+D; B197 discovery-paritet hostat (Christophers,
   tidig rebase msg-0085); blob-/KV-prune; `changeSet` hostat;
   Preview-miljöns reuse-flagga; Safari/Firefox-E2E för B125.

**Öppna blockers:** inga hårda.

Last verified state: `56dc754f` (2026-06-12 ~16:00 UTC+2; squash-merge av
#313 ovanpå #312/#311/#310-kedjan. Avslutningsrundan: branch-/worktree-
städning, known-issues-städning (B195 flyttad till Stängda, B155-slice för
#313), handoff + detta block, `main` synkad till samma innehåll för
operatörens produktionstest. Tarball-omladdningen till blob
`build-context/current.tar.gz` gjordes direkt efter #313-mergen.)

## Öppna PR att känna till

Inga öppna just nu. #306–#313 är squash-mergade till `jakob-be` och synkade
till `main`. (#312 = komponentintag v1 / uppgift E, mergad 2026-06-12 ~15:20.
#313 = del F+D ärlighetsfix, mergad 2026-06-12 ~15:41. Äldre detaljer:
arkivet + `docs/handoff.md`.)

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
