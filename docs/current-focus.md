# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-12 ~00:30 — midnattsstängning: B194 live, main-sync klar, lane-grind införd)

**Git:** `main = jakob-be` (tom diff, rent träd, local == origin). Sista
kodcommit `5109cc1f` (CI-actions v6); midnattens docs-pass ligger ovanpå.
Production (`sajtbyggaren-viewser.vercel.app`) deployar från `main` och kör
B194-koden (deploy READY från `main@78417aae`, app-identisk med tippen).
Backup av för-sync-main: `backup-main-2026-06-11-pre-evening-sync-cb0f6a5`.

**Midnattens facit (efter 22:55-checkpointen):**

- **Main-sync KLAR** (operatörsbekräftad): hela kvällspasset + nattens merges
  ligger på `main`. `ignoreCommand`-fällan dokumenterad (docs-only-toppcommit
  cancelar prod-bygget → tvåstegspush eller manuell promote).
- **`ignoreCommand`-fällan FIXAD (2026-06-12 ~01:10):** `apps/viewser/vercel.json`
  jämför nu mot senast deployade SHA (`VERCEL_GIT_PREVIOUS_SHA`, fallback
  `HEAD^`), så en docs-toppcommit kan inte längre gömma kodcommits i samma
  push. Rena docs-pushar skippas fortfarande med flit — produktion pekar då
  på senaste app-ändringen, inte nödvändigtvis main-HEAD. Det är väntat
  monorepo-beteende, ingen bugg.
- **`main` låst med GitHub-ruleset (2026-06-12, operatörsbeslut):** bara
  admin (Jakobs konto, dvs. vår lane) kan uppdatera `main`; force-push och
  branch-radering blockerade för alla. Christopher-lanen når produktion
  enbart via PR → `jakob-be` → ff-push av vår lane. Rulesetet heter
  "protect-main-production-lane" (id 17578855, repo-settings). OBS: GitHub
  tillåter inte Actions-appen som bypass på user-ägda repon, så steward-
  auto-bump kan inte pusha till `main` — den triggas bara av PR mergad
  direkt till `main`, vilket lane-modellen ändå förbjuder (retargeta alltid
  till `jakob-be`, som med #305).
- **Blob-token verifierad (operatörsfråga 2026-06-12):** lokala
  `apps/viewser/.env.local` och Vercel-prod har IDENTISK `BLOB_READ_WRITE_TOKEN`
  (store `vxfg…`). "Added 15h ago" i Vercel-dashboarden är skapelsetid, inget
  har ändrats sedan dess. Kvarstående är bara Christophers lokala store-avvikelse
  (`3xqg…`, punkt 4b nedan).
- **#305** Vercel Web Analytics (Vercel-agentens PR, retargetad main→jakob-be,
  `<Analytics />` i layout.tsx + `@vercel/analytics`).
- **#292** hostad asset_set-forwarding (Christophers; ren 1-commit-rebase,
  squashad efter review).
- **#304** B194 — hostad run-state till blob (`run-state/<siteId>/v<N>/`,
  immutabelt PI/meta-par) + KV-pekare (`HostedRunStatePointer`). Krävde
  basmerge `57ceec9c` + **naming-dictionary v38** (term-coverage-grinden
  fångade oregistrerad term).
- **HOSTADE FÖLJDPROMPTER E2E-BEVISADE LIVE:** init-bygge `site-e342ef7b`
  (ok, ~141 s) → run-state v1 → följdprompt (ok, ~110 s) → v2 skapad,
  ändringen verifierad i v2-PI:n.
- **Build-context-tarballen omuppladdad** (var från 06-10 → hostade byggen
  hade kraschat på ny CLI-flagga). Rutin: ladda om efter merges som rör
  `scripts/`/`packages/`/`governance/`/`data/starters/` via
  `node apps/viewser/scripts/upload-build-context-to-blob.mjs`.
- **Obligatorisk lane-grind** för christopher-lanen i
  `governance/rules/04-branch-and-team.md` (auto-synk vid passtart, hela
  grinden före varje push, term i samma commit, auto-rebase, basmerge-
  fallback för vår lane; motkrav: kort review-SLA). Christopher har kvitterat
  (msg-c-0084) och synkat lanen till `5109cc1f`.
- CI-actions bumpade till v6 (`5109cc1f`) — Node 20-varningarna borta.
- Versionsläge: llm-models **v11**, naming-dictionary **v38**,
  dossier-contract **v4**. ADR-liggare: nästa lediga **0055** (0054
  reserverad för MCP-intagsgrinden).

**Stora bilden:** P2 skeppad, publik hostad drift PÅ (rate-limit/TTL/B195/
B196) och nu med fungerande följdprompter + asset_set hostat. Äldre block:
[`current-focus-2026-06-11-kvall.md`](archive/current-focus-2026-06-11-kvall.md)
(kvällen) och [`current-focus-2026-06-11-em.md`](archive/current-focus-2026-06-11-em.md).

**Nästa prioriteringar (i ordning):**

1. **B197 — hostad discovery-paritet (Christophers, PÅGÅR):** GO givet,
   lanen synkad. Vår action när PR:en kommer: reviewa SNABBT (nya regelns
   review-SLA — låt inte basen hinna flytta sig).
2. **B198 del b — synlig contact-form-render:** dedikerad-route-mönstret
   (faq/team) för contact-form på ecommerce-lite, så resend-formuläret
   faktiskt syns (del a + hardening är inne).
3. **ADR 0052-uppföljning (litet städ):** död `model="gpt-5.4"`-default i
   `packages/generation/brief/extract.py` (~rad 690), hårdkodad fallback i
   `scripts/prompt_to_project_input.py` (~rad 3343) → policy-defaults,
   tråda design-tooling-skripten. Plus eslint-fyndet i
   `industry-search.tsx:298` (vår yta, msg-c-0080).
4. **Operatörsbeslut (öppna):** (a) Token Meter-priser står på 0 i
   Vercel-env; (b) blob-store-unifiering — Christophers lokala `.env.local`
   pekar på en annan store (`3xqg…`) än projektets (`vxfg…`), så lokal/hostad
   delar inte asset-bibliotek (msg-c-0083); (c) klicka INTE "Revoke Token"
   i blob-dashboarden — hostade pipelinen använder `BLOB_READ_WRITE_TOKEN`.

**Öppna blockers / att-göra:**

- B155 hålls öppen (kvarvarande targets). B194 STÄNGD (#304). B197 pågår.
- Testsajten `site-e342ef7b` (E2E-beviset) ligger kvar i blob — kan raderas
  vid tillfälle.
- `christopher`-lanen äger: `use-followup-build.ts`, dialogerna,
  viewser-frontend/inspector — rör ej.

Last verified state: `5109cc1f` + midnattens docs-pass (2026-06-12 ~00:30
UTC+2; `main = jakob-be`, tom diff, rent träd. Natten: #305 + #292 + #304
mergade, B194 live + E2E-bevisad, build-context omuppladdad, naming v38,
lane-grind i regel 04, CI-actions v6. Inga öppna PR:ar.)

## Öppna PR att känna till

Inga öppna PR:ar just nu (00:30). Nästa väntade: Christophers B197-PR mot
`jakob-be` — reviewa snabbt enligt nya lane-grindens review-SLA.

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
