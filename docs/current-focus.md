# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~18:45 — kvällens avslutningsrunda: #314/#315 landade, slutlig main-sync)

**Git:** `main = jakob-be` (rent träd, local == origin) efter denna rundas
slutsynk. Production deployar från `main`. Tarball-omladdningen är GJORD
efter #314 (verifierad via blob-uploadedAt 17:51:48, 27 s efter mergen) —
build-kontexten i blob speglar `de04e8f6`. #315 krävde ingen omladdning
(endast `apps/viewser/` + `tests/`). Alla PR-köer är tomma.

**Landat under kvällen (squash-mergat till `jakob-be`):**

- **#314 (uppgift G, `de04e8f6` — stänger B200/B201, ADR 0058):**
  G1 hostad answer-only — ren fråga med hög konfidens besvaras på sekunder
  utan sandbox-spinn (`apps/viewser/lib/hosted-answer-only.ts`, kortslutning
  före `startHostedBuild`); G2 preview-bundle-tarball — bygget paketerar
  publicerade fil-setet som EN tarball i blob, preview-sandboxen skapas
  direkt från den (`source=preview-bundle` i loggarna) med ärlig
  fil-för-fil-fallback för äldre sajter. Naming v41.
- **#315 (uppgift H, restpost-svep, `54de9b9c`):** dedikerad deterministisk
  `intent_not_executable`-rad i FloatingChat (no-key-fallbacken säger ärligt
  att önskemålet saknar byggförmåga — aldrig "var mer specifik"-rådet;
  LLM-answerText från #313 vinner fortsatt); rolletiketten
  `component_builder` → "komponenter" (ADR 0057). Plus hygientak-split:
  copy-directive-/change-set-låsen bor nu i
  `tests/test_viewser_copy_change_set.py`.

Eftermiddagens runda (#310–#313 + första main-synken) är historik:
[`docs/archive/current-focus-2026-06-12-em.md`](archive/current-focus-2026-06-12-em.md).

**Nästa 3 prioriteringar:**

1. **Operatörens produktions-E2E på `main`** (görs av operatören separat —
   agenter ska INTE förekomma testet). Konkreta verifieringspunkter:
   (i) ren fråga i chatten ska svara på sekunder utan sandbox;
   (ii) första hostade bygget efter merge skapar första preview-bundlen —
   andra previewn därefter ska starta på sekunder (kolla `sourceMs` +
   `source=preview-bundle` i runtime-loggarna; äldre sajter tar
   fil-för-fil-fallback tills de byggs om);
   (iii) no-op-följdprompt ska ge ärlig no-op-rad, aldrig grön "Klart!".
2. **Uppgift I (nästa byggsteg): B197 discovery-paritet hostat** — idag
   skickas endast prompttexten in i sandboxen; discovery-svar/
   konversationskontext trådas inte. (Koordinera med Christophers spår,
   msg-0085 begärde tidig rebase på `hosted-build-runner.ts`.)
3. **Backlog/deferred (ej blockers):** dossierfälten componentSource/
   mountRules/qualityGate från E (kräver design/ADR först — ej specade i
   ADR 0054/0057); targeted-apply-trådning av
   `appliedFollowupDirectiveKinds`; blob-prune-skulden + dubbellagring av
   källan per bygge tills bundle-vägen är prod-bevisad (ADR 0058); G1:s
   medvetna klassificeringslatens (~1–3 s, 8 s tak) på byggvägen;
   `changeSet` hostat; Preview-miljöns reuse-flagga; Safari/Firefox-E2E
   för B125.

**Öppna blockers:** inga hårda.

Last verified state: `54de9b9c` (2026-06-12 ~18:45 UTC+2; squash-merge av
#315 ovanpå #314. #315-mergen krävde en hygientak-split i CI-rundan
(`test_viewser_floating_chat.py` 1221 > 1200 rader — copy-directive-/
change-set-låsen flyttade till `tests/test_viewser_copy_change_set.py`,
samma mönster som tidigare splittar). Kvällsrundan: handoff + detta block,
slutlig `jakob-be` → `main`-sync så operatörens produktions-E2E kör på
dagens fulla leverans.)

## Öppna PR att känna till

Inga öppna just nu. #306–#315 är squash-mergade till `jakob-be` och synkade
till `main`. (#314 = uppgift G snabb chat + preview-bundle, mergad
2026-06-12 ~17:51. #315 = uppgift H restpost-svep, mergad 2026-06-12 ~18:26.
Äldre detaljer: arkivet + `docs/handoff.md`.)

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
