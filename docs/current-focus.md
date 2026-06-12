# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~07:30 — B199 v2: hostad run-historik + artefakt-läsning + omladdnings-återställning)

**Git:** `main = jakob-be` (rent träd, local == origin). B199 v2-passet är
landat direkt på `jakob-be` på operatörsmandat och synkat till `main`.
Production deployar från `main`. Ingen tarball-omladdning behövs — passet
rör bara `apps/viewser/` + tester/docs (orkestrerings-skriptet genereras av
TS-koden, inte av build-context-tarballen).

**Landat i morgonpasset (B199 v2, operatörsmandat efter bannerfrågan):**

- **Hostad run-historik/artefakter/inspector:** orkestrerings-skriptet
  publicerar durabelt KV-index (`HostedRunIndexEntry`, naming-dictionary
  v39) per lyckat bygge; ny `lib/hosted-run-history.ts` läser indexet +
  artefakt-tarballen från blob; `/api/runs?siteId=` (siteId =
  capability-nyckel, ingen global listning) + artifacts/trace serveras
  hostat. B199 STÄNGD i known-issues.
- **Omladdnings-återställning:** builder-valet persisteras i
  sessionStorage och återställs efter hård reload (lokalt + hostat).
  Bannern är eget fält (`hostedBanner`) och armar aldrig 404-latchen;
  banner-texten omskriven till nya läget.
- **Init-paritet + historisk baseRunId:** init-svar bär kanonisk
  build_site-runId; historisk `baseRunId` hydrerar sin egen versions
  artefakter via runId-indexet (siteId-bundet).
- 14 nya källkods-lås i `tests/test_viewser_hosted_run_history.py`.

**Nästa 3 prioriteringar:**

1. **E2E-verifiera B199 v2 + #307 i produktion** på `/studio`: init →
   historik/inspector → omladdning (builder-läget kvar) → edit-följdprompt
   (OpenClaw apply) → ren fråga (answer-only), kolla `engine`-attribution.
2. **B197 (Christophers, pågår):** snabb review när PR kommer. OBS:
   `hosted-build-runner.ts` är ändrad av BÅDE #307 och B199 v2 — be honom
   rebasa tidigt.
3. **Uppföljningar:** blob-/KV-prune-strategi (`generated/` +
   run-index-nycklarna), `changeSet` hostat, operatörsbesluten (Token
   Meter-priser, Christophers lokala blob-store `3xqg…`).

**Öppna blockers:** inga hårda. B197 och `changeSet`-hostat är spår, inte
blockers.

Last verified state: `261f0c63` (2026-06-12 ~09:10 UTC+2; B199 v2-kodcommiten
på `jakob-be`, synkas till `main` i samma push — rent träd, full svit
(`pytest -n auto`) + ruff + governance + term-coverage + tsc + eslint gröna
lokalt).

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
