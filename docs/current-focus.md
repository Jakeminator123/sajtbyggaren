# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-09, kväll)

**Git:** `main = 16278c1` (PR #212, oförändrad). `jakob-be = 4144ecf`, rent träd,
**87 commits före main**. Idag landade på `jakob-be` (merge-tåg, ett i taget, alla guards gröna):

- **#235** `fix(builder)`: hissa Google Fonts `@import` överst i genererad `globals.css`.
- **#237** `fix(builder)`: gör `build_site.py` auto-prune **opt-in** (`--allow-prune`). En
  manuell/smoke `--dossier`-build raderar inte längre `data/prompt-inputs/`-sidecars,
  `data/runs/` eller `.generated/` när `SAJTBYGGAREN_MAX_*`-caps är satta i `.env`. Viewser
  opt:ar in explicit (`build-runner.ts`), så produktflödets retention är oförändrad.
- **#236** `refactor(builder)`: brief-generering → `packages/generation/brief/site_brief.py`
  (megafil-slice 4; `build_site_brief` inte längre inline; painter-palma-paritet höll).
- **#229** `docs`: Cloud Agent preview-mode-not (retargetad `main → jakob-be`, docs-only).
- **#228** `feat(viewser)`: lätt review-summary på sista wizard-steget + UI-honesty-slices.

Sync `jakob-be → main` väntar **operatörsbeslut** — pusha aldrig main per slice.

**Riktning (icke förhandlingsbar):** OpenClaw är en conductor/bridge på den
befintliga in-repo-motorn — inte en ny parallell motor, inte extern Docker/
Gateway i nuvarande fas, inte fri filpatch. In-repo-källan ENBART
(`packages/generation/orchestration/openclaw/`, `scripts/run_openclaw_followup.py`,
`scripts/verify_openclaw.py`, `apps/viewser/lib/openclaw-runner.ts`,
`apps/viewser/app/api/prompt/route.ts`). Plan:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](heavy-llm-flow/openclaw-2.0-conductor.md).
`sajtmaskin` + `C:\Users\jakem\Desktop\openclaw` = strikt read-only (AGENTS.md).

**Live-loop-bevis (2026-06-09): GRÖNT.** Manuell /studio-körning på `bil-ab-17331b`:
följdprompt "gör sajten grönvit" → ny version (v6→v9), bygge + alla quality gates ok, och
preview-iframen renderade automatiskt nya versionen utan krasch (local-next). Data-/
versionslagret grönt (`themeApplied: true`, stabilt `projectId`). **Caveat:** färgskiftet
syntes knappt — sajten var redan grön (lågkontrast-testfall, ingen loop-bugg). Verifiera
tema-applicering med en kontrastfärg (t.ex. "gör sajten mörkblå") i eval-fasen.

**Nästa prioriteringar:**

1. **Slice 5 — render helpers → `packages/generation/build/render_helpers.py`** (sista
   megafil-slicen på planen; prompten är skriven + verifierad och nu avblockad efter #236).
   19 funktioner + 11 konstanter, beteendebevarande, draft-PR mot `jakob-be`. Branca av
   **senaste** `jakob-be` (`4144ecf`), lokalisera symboler via namn (inte radnummer).
2. **Evals / golden path + manuell score** — nu när loopen är grön: kör
   `scripts/run_golden_path_eval.py --mode deterministic` + `scripts/run_eval_suite.py quick`,
   sätt manuell 1–10 i Backoffice. Inkludera kontrastfärg-testet ovan.
3. **Synlig render av `section_add`** + sida/position — fortfarande mount-only
   (`applied=true`, `appliedVisibleEffect=false`). Störst produkthävstång efter slicen.
   (Följdprompt copy literal-replace + OpenClaw F1 registry-runtime står kvar därefter.)

**Öppna blockers / att-göra:**

- **#225** (`cursor/test-suite-hygiene-foundation-3737 → jakob-be`, draft): testsvit-hygien.
  i konflikt mot nya `jakob-be` efter #236 — behöver **rebase av författaren** mot
  `4144ecf` (konflikt i `test_viewser_files`/storleksvakt). Inte mergad, inte vår att tvinga.
- **Manuell review-summary wizard-check (#228):** klick-checken på Bilder-steget (hoppa steg,
  kontakt/about-popup) täcks INTE av automatiska tester — separat manuell 5/5-verifiering kvar.
- `section_add` mount-only för alla nio typer; synlig render + placering återstår.
- Följdprompt copy: "ändra X till Y" parafraserar i stället för literal replace; ärlig
  no-op-feedback saknas (UI). Rotorsak i docs/gaps/GAP-followup-prompt-content-passthrough.md.

**Cloud-lanes (status):**

| Lane | Vad | Status |
| --- | --- | --- |
| A — docs-honesty-cleanup | architecture/glossary-honesty + arkivflytt + frontmatter + checker | **inne** på `jakob-be` via merge `76b5ae4` |
| B — FloatingChat-split | split `floating-chat.tsx` → syskonmoduler (behavior-preserving) | **inne** på `jakob-be` via #217 (`2ffce4a`); #216 mot `christopher` redundant |
| C — backend-refaktorplan | megafil-refaktorplan (docs-only) | **inne** via #215 (`2dadf09`) — ingen refaktor körd, gated |
| Regel-konsolidering | Cursor-regler 29→12 (docs/governance) | **inne** via #218 (`11b4f19`); hygien-regeln bor nu i `governance/rules/07-docs-focus-handoff.md` |

**OpenClaw F1-readiness (separat lokal lane):** readiness-/install-planen har
landat plan-only och gated i `docs/heavy-llm-flow/openclaw-f1-readiness.md`
(`6e08ce9`; ingen runtime-kod; gated på synlig section_add + refaktor-beslut).

Last verified state: `4144ecf` (2026-06-09 UTC, `jakob-be` HEAD — efter dagens merge-tåg #235 (`b584638`), #237 prune-fix (`13bf768`), #236 brief-slice4 (`3aefa0d`), #229 docs (`a74ad24`) och #228 review-summary (`4144ecf`); `main` = `16278c1`, sync till main väntar operatörsbeslut).
Nya PRs sedan föregående checkpoint: #235, #237, #236, #229, #228 — alla mergade på `jakob-be`, ej `main`. Live-loop-beviset kördes grönt (se ovan).

## Öppna PR att känna till

- **#225** (`cursor/test-suite-hygiene-foundation-3737 → jakob-be`, draft): testsvit-hygien.
  i konflikt efter #236 — väntar på författar-rebase mot `4144ecf`. Inte vår att tvinga.
- **#156** (`feat/live-preview → jakob-be`): hostad `/live`-loop. **Parkerad pga säkerhet**
  (publik POST utan auth/rate-limit kan starta sandboxar) — INTE vår att merga/fixa.

Slice 5-prompten (render helpers) är skriven och avblockad men **ännu inte PR:ad**; körs via
cloud-agent (måste re-synca till `4144ecf` först — dess snapshot är ~70 commits gammal) eller
lokalt. Christophers UI-arbete sker på `christopher` (gamla `christopher-ui` är fryst legacy).

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
- Detaljer: [`governance/rules/branch-discipline.md`](../governance/rules/branch-discipline.md).

## Loopen vi följer

Se [`docs/agent-handbook.md`](agent-handbook.md) ("Standard loop"). Kort: Scout
vid behov → arbete på arbets-branch → guards gröna → push → vid behov PR mot
`main` → post-merge-sync. Orkestrering över längre pass:
[`docs/orchestrator-playbook.md`](orchestrator-playbook.md).

Operatörspreferens: svenska, kort och koncist, gärna matris/tabell. Förklara
dev-uttryck med korta parenteser första gången per konversation. Mönstret i
[`governance/rules/reply-style.md`](../governance/rules/reply-style.md).

## Arkiv

Historiska statusblock + checkpoint-kedjan ligger i arkivet:

- [`docs/archive/current-focus-2026-06-08-pre-slim.md`](archive/current-focus-2026-06-08-pre-slim.md)
  (full snapshot precis före denna slimning).
- [`docs/archive/current-focus-history-2026-05-26.md`](archive/current-focus-history-2026-05-26.md)
  (äldre checkpoint-kedja).

För commit-historik: `git log --oneline origin/main` eller
`git log --oneline origin/jakob-be`.

## Föregående checkpoint

Tidigare "Last verified state"-block och äldre "Current objective"-block är
flyttade till arkivet ovan (per `governance/rules/07-docs-focus-handoff.md`).
Auto-bump-verktyget lägger nya korta checkpoint-block här vid main-sync; håll
högst ett kvar och flytta resten till arkivet.
