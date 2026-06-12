# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~05:45 — gryningsstängning: #306 + #307 mergade och i produktion, lane grön)

**Git:** `main = jakob-be = a67a25b0` (rent träd, local == origin, CI grön).
Production (`sajtbyggaren-viewser.vercel.app`) deployar från `main` och kör
`a67a25b0`-kedjan. Build-context-tarballen omladdad EFTER #307-mergen, så
hostade sandbox-byggen kör samma kod som `main`.

**Mergat i gryningen (båda via cloud-PR → vår lane-review → squash):**

- **#306 — B198 del b** (`d1a1b98d`): synlig contact-form-render på
  ecommerce-lite. Surfas mot befintliga kontakt-routen, ENBART när
  `resend-contact-form` är monterad (mailto förblir ärligt mount-only).
- **#307 — hostad follow-up-paritet** (`a67a25b0`): B199-hydrering (kanoniska
  run-artefakter tarballas till blob + hydreras i sandboxen), OpenClaw
  apply-söm i sandbox med answer-only-gate och ärlig legacy-fallback
  (`engine`-attribution, aldrig fejkad apply-success), `baseRunId`/
  `markedSections` forwardas, rikt hostat svar via KV-result. Sex nya
  regressionstester. v1-begränsning: artefakt-pekaren spårar senaste
  versionen; `changeSet` är `null` hostat.
- Före merge lagades två röda källkods-lås på basen (`64aaeea4`):
  run-details-panel clear-before-fetch + versions-tab under 1300 rader
  (regression från `691bd835`). Lärdom inskriven: full svit före lane-push,
  inte bara riktade tester.

**Nästa 3 prioriteringar:**

1. **E2E-verifiera #307 i produktion:** hostat init-bygge → följdprompt
   (edit via OpenClaw apply) → ren fråga (answer-only utan bygge) på
   `/studio`, och bekräfta `engine`-attribution + rikt svar i UI:t.
2. **B197 (Christophers, pågår):** snabb review när PR kommer. OBS:
   `hosted-build-runner.ts` är kraftigt omskriven av #307 — be honom rebasa
   tidigt om hans gren rör den.
3. **Uppföljningar i prioritetsordning:** per-run artefakt-historik
   (historisk `baseRunId` + `changeSet` hostat, B199 v2), blob-prune-strategi
   för `generated/`-prefixet, operatörsbesluten (Token Meter-priser,
   Christophers lokala blob-store `3xqg…`).

**Öppna blockers:** inga hårda. B197/B199-v2 är spår, inte blockers.

Last verified state: `a67a25b0` (2026-06-12 ~05:45 UTC+2; `main = jakob-be`,
rent träd, CI grön på båda, prod READY, tarball == main. #306 + #307 mergade;
inga öppna PR:ar.)

## Öppna PR att känna till

Inga öppna PR:ar (2026-06-12 ~05:45). #306 och #307 är squash-mergade till
`jakob-be` och ff:ade till `main`.

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
