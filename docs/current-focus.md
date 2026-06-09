# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/07-docs-focus-handoff.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-09)

**Git:** `main = 16278c1` (PR #212 officiell). `jakob-be = a9504d7`, rent träd,
**38 commits före main** — sedan föregående checkpoint (`2ffce4a`) har landat på
`jakob-be`: Lane A docs-honesty-cleanup (merge `76b5ae4`), Cursor-regel-
konsolidering 29→12 via #218 (`4139285` + merge `11b4f19`), OpenClaw
F1-readiness-plan (plan-only, gated; `6e08ce9` + merge `0c89942`), Glue 1 —
färsk build persisterar hittbar Project Input — via #219 (`892ef8e` + merge
`2ad3655`) och docs-steward-städning (handoff-slim + current-focus-refresh) via
#220 (merge `a9504d7`). Sync `jakob-be → main` väntar **operatörsbeslut** — pusha
aldrig main per slice.

**Riktning (icke förhandlingsbar):** OpenClaw är en conductor/bridge på den
befintliga in-repo-motorn — inte en ny parallell motor, inte extern Docker/
Gateway i nuvarande fas, inte fri filpatch. In-repo-källan ENBART
(`packages/generation/orchestration/openclaw/`, `scripts/run_openclaw_followup.py`,
`scripts/verify_openclaw.py`, `apps/viewser/lib/openclaw-runner.ts`,
`apps/viewser/app/api/prompt/route.ts`). Plan:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](heavy-llm-flow/openclaw-2.0-conductor.md).
`sajtmaskin` + `C:\Users\jakem\Desktop\openclaw` = strikt read-only (AGENTS.md).

**Nästa 3 prioriteringar:** (Glue 1-gaten är nu grön via #219 — se nedan.)

1. **Synlig render av `section_add`** + sida/position-placering — gör mount-only
   (`applied=true` men `appliedVisibleEffect=false`) till faktiskt synligt i
   preview. Största produkthävstången nu.
2. Följdprompt copy-fix: "ändra denna text X till Y" ska göra literal replace via
   `packages/generation/followup/copy_directives.py` (inte parafrasera/regenerera)
   och ge ärlig no-op när inget kunde appliceras. Egen lane — delad bygg-write-set,
   kör ej parallellt med prio 1.
3. **OpenClaw F1 — registry-runtime:** gör `docs/openclaw-workspace/action-registry.json`
   körbar (kod läser registret och väljer roll), inte bara dokumentation.
   Readiness-planen finns i `docs/heavy-llm-flow/openclaw-f1-readiness.md`
   (plan-only). *Gås igenom med operatören innan kod skrivs.*

**Öppna blockers:**

- Glue 1 — **stängd via #219**: en färsk build persisterar nu en hittbar Project
  Input på disk (CLI/exempel-vägen; prompt-vägen skrev redan sidecaren). Inte
  längre en gate för synlig `section_add`.
- `section_add` är mount-only för alla nio sanktionerade typer; synlig render +
  exakt placering återstår (Sprint-3B-spåret).
- Följdprompt copy: "ändra denna text X till Y" parafraserar/regenererar i stället
  för literal replace, och ärlig no-op-feedback saknas (UI). Rotorsak i
  docs/gaps/GAP-followup-prompt-content-passthrough.md.

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

Last verified state: `a9504d7` (2026-06-09 UTC, `jakob-be` HEAD — efter #218 (`11b4f19`), OpenClaw F1-readiness-plan (`0c89942`), Glue 1 via #219 (`2ad3655`) och docs-steward-städning via #220 (`a9504d7`); `main` = `16278c1` via PR #212, sync till main väntar operatörsbeslut).
Nya PRs sedan föregående checkpoint: PR #218 (Cursor-regler 29→12), PR #219 (Glue 1 — färsk build persisterar Project Input) och PR #220 (docs-steward: handoff-slim + current-focus-refresh). Alla mergade på `jakob-be`, ej `main`.

## Öppna PR att känna till

- **#156** (`feat/live-preview → jakob-be`): hostad `/live`-loop. **Parkerad pga
  säkerhet** — live-lane, INTE vår att merga/fixa.
- **#216** (`cursor/floating-chat-split-61b7 → christopher`): FloatingChat-split i
  Christophers lane — numera stängd (spliten är inne på `jakob-be` via #217).

Christophers UI-arbete sker på `christopher` (gamla `christopher-ui` är fryst
legacy med parkerad auth/billing).

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
