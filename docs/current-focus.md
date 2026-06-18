# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-16 ~04:50 — gpt-5.5 överallt live i prod; edit-flödesdiagnos klar)

**Git:** `main = jakob-be = origin/main = origin/jakob-be = 1c9a4e18`. Production
deployar från `main`; build-context (Python-motorn) omuppladdad + i synk (KV-sha matchar HEAD).

**Stora planen + orientering:** orienteringsblocket överst i [`docs/handoff.md`](handoff.md).
Nattens fullständiga överlämning + den definitiva edit-flödesdiagnosen:
[`docs/handover-next-agent.md`](handover-next-agent.md).

**Landat i natt (2026-06-16 02–05, operatörsstyrt pass):**
- **llm-models v14** (`c360a931`): hela chat-/generationskedjan → gpt-5.5; rejält höjda
  maxOutputTokens (16000–24000), aldrig xhigh. Fixar `<no output>`: Responses-API:t räknar
  reasoning-tokens i utdatataket, så ett för lågt tak gav tyst mock-fallback. rerankModel → gpt-5.5
  (gpt-5.5-mini finns INTE på kontot, verifierat mot riktig nyckel). Real-key-smoke + 372 tester gröna.
- **scaffoldModel-konsistensfix** (`5d3cd56d`): rollen saknade reasoningEffort/maxOutputTokens.
- **chat-tak 1500 → 15000** (`1c9a4e18`): samma `<no output>`-klass i Viewser-skalets TS-chatt
  (`apps/viewser/lib/openai.ts`), som v14 inte rörde.
- **#343 + #344** (backoffice-refaktorer) mergade. Build-context **omuppladdad** → v14 live i prod.
- **Prod live-verifierat i webbläsaren:** riktig gpt-5.5-restaurangsajt byggdes (inget mock), och en
  följdprompt (namnbyte → v2) landade via Python-motorn. OpenClaw är INTE globalt read-only.

**Nästa 3 prioriteringar:**

1. **Edit-flödesdiagnos (NY #1):** rika edits (component_add/route_remove/section/route_add/rename)
   no-op:ar i PROD men APPLICERAR lokalt via samma dirigent-ingång (`apply_followup_to_json`, bevisat
   på både restaurant-hospitality och local-service-business, nyckel på). Hostat ger `bridge.applied=false`
   → ärlig "inte inkopplad"-rad → faller till full `build_site.py`-rebuild (bara copy-merges). Trolig rot:
   den hydrerade bas-kontexten i sandboxen får routern att klassa edit:en till en V0/ej-inkopplad intent.
   Behöver dirigentens decision-trace för en prod-sajt (site-4d8d1a1b) + action-bridge V1 / hydrerings-paritet.
   Allt i [`docs/handover-next-agent.md`](handover-next-agent.md).
2. **Hostad edit-perf** — kall bygg-sandbox (pip+npm+next build = minuter), TTL-410. Höj TTL,
   `VIEWSER_SANDBOX_REUSE`, pip-cache, skippa next build för direktiv-edits.
3. **generativ V2 / reviews-trust synliga** (ADR 0059/0061).

**Öppna blockers:** inga hårda — edit-flödet är en kapacitets-/wiring-lucka, inte en regression
(copy-edits + init bygger korrekt i prod).

**Noterat:** `.github/workflows/governance.yml` har en ocommittad ändring i arbetsträdet som inte
kommer från detta pass (annan agent/operatör) — lämnad orörd.

Last verified state: `1c9a4e18` (2026-06-16 ~04:50 UTC+2; v14 + scaffold-fix + chat-tak + #343/#344
på main → prod; build-context uppladdad; prod-bygge + följdprompt live-verifierat). Öppen PR: #324
(Christophers viewser UI/UX — väntar operatörens browser-check). Föregående: `0f2e5758`.

## Öppna PR att känna till

Christophers viewser-frontend-lane: **fem PR:er, alla CLEAN/MERGEABLE mot färska
`jakob-be` (cae8971) och grön CI**. (`ai-bug-review` skippas på alla PR sedan
gpt-5.5-modellbumpen `dae2019` — *"temperature does not support 0 with this
mode"*; "skipped", inte "fail", så ej blockerande, men AI-review-skyddet är de
facto av tills review-workflowens `temperature` justeras.) Konfliktfria
sinsemellan och mot Jakobs
backend (rör varken `route.ts`, `hosted-build-runner.ts`, discovery eller
studio-flödet). Redo att review:as + mergas i valfri ordning; **#324 hålls för
operatörens browser-check** eftersom den rör hostad UI direkt.

- **#324** (`feat/viewser-uiux-prod-polish`): UI/UX-putts för hostad prod —
  banner-overlap, jargong, bygg-text + canary-skript. (Väntar browser-check.)
- **#371** (`feat/viewser-generative-visible`): visar genererade komponenter
  (bildgrid/CTA) i chattens "Ändrat"-lista (ADR 0061-yta).
- **#372** (`feat/viewser-uiux-copy-polish`): jargong-fri discovery-wizard
  (hero/header/footer → klar svenska).
- **#373** (`feat/viewser-product-page`): riktig `/produkt`-sida (ersätter
  placeholder-stub).
- **#374** (`feat/viewser-error-404-favicon`): frontend-metadata — branded
  404/error, PWA-manifest + brand-ikoner, OG-bild, FAQ-sida. OBS: justerade en
  föräldralös triangel-`favicon.ico` till samma "S"-mark som `apple-icon.png`
  (apple-icon orörd); revertbart om triangeln var avsiktlig.

Detaljer i inbox: `msg-c-0094` (samlad) konsoliderar de grenlokala notiserna
`msg-c-0089`–`0093`.

Mergat och i `main` (= 0f2e5758): #338 (Fas 1), #341 (generativ V1, ADR 0061),
#342 (generativ-fixar), #340 (ADR 0062), #337 (known-issues-arkiv), temperature-fix
+ blob-admin. Tidigare: #336/#334/#335 (nav_hide/route_remove-fix/docs),
#328/#332/#333, #320/#329/#330/#331.

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
