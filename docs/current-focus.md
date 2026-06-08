# Aktuellt fokus

Detta är projektets enda aktuella köplan. Varje agent läser denna fil **först**.
Den hålls kort med flit (`governance/rules/current-focus-hygiene.md`): bara
aktuellt statusblock — äldre block ligger i arkivet. Full överlämning:
[`docs/handoff.md`](handoff.md). Startpromptar/rollgränser:
[`docs/agent-prompts.md`](agent-prompts.md).

## Status nu (2026-06-08)

**Git:** `main = 16278c1` (PR #212 officiell — hero-fix, Bite C, `section_add`-
breddning, governance/cleanup). `jakob-be = e03e1d1`, rent träd, **7 commits
före main** (runda-2-batch: FloatingChat-honesty, dev.mjs-fix, lane-grant,
AddModuleDialog-fix, docs-städning). Sync `jakob-be → main` väntar
**operatörsbeslut** — pusha aldrig main per slice.

**Riktning (icke förhandlingsbar):** OpenClaw är en conductor/bridge på den
befintliga in-repo-motorn — inte en ny parallell motor, inte extern Docker/
Gateway i nuvarande fas, inte fri filpatch. In-repo-källan ENBART
(`packages/generation/orchestration/openclaw/`, `scripts/run_openclaw_followup.py`,
`scripts/verify_openclaw.py`, `apps/viewser/lib/openclaw-runner.ts`,
`apps/viewser/app/api/prompt/route.ts`). Plan:
[`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](heavy-llm-flow/openclaw-2.0-conductor.md).
`sajtmaskin` + `C:\Users\jakem\Desktop\openclaw` = strikt read-only (AGENTS.md).

**Nästa 3 prioriteringar:**

1. **Glue 1 (gating, backend):** verifiera att en färsk build → följdprompt
   hittar Project Input på disk (`data/prompt-inputs/<siteId>.project-input.json`).
   Utan detta kan `section_add` inte ens köra på en nybyggd sajt.
2. **Synlig render av `section_add`** + sida/position-placering — gör mount-only
   (`applied=true` men `appliedVisibleEffect=false`) till faktiskt synligt i
   preview. Största produkthävstången nu. Förutsätter prio 1 grön.
3. **OpenClaw F1 — registry-runtime:** gör `docs/openclaw-workspace/action-registry.json`
   körbar (kod läser registret och väljer roll), inte bara dokumentation.
   *Lokalt nästa stordåd — gås igenom med operatören innan kod skrivs.*

**Öppna blockers:**

- Glue 1 osäker på en färsk sajt (handoff-fynd "ingen Project Input på disk")
  — gating för synlig `section_add`.
- `section_add` är mount-only för alla nio sanktionerade typer; synlig render +
  exakt placering återstår (Sprint-3B-spåret).

**Parallella lanes (FÖRBEREDDA, ej startade):** prompt-filer ligger i
[`docs/agent-prompts/cloud-grind/`](agent-prompts/cloud-grind/). Hårda,
disjunkta write-set:

| Lane | Roll | Branch | Write-set | Off-limits |
| --- | --- | --- | --- | --- |
| A — docs-honesty-rest | Steward | `jakob-be` | SOUL/TOOLS fas-nyans, status-ord, docs-checker | runtime-kod |
| B — FloatingChat-split | Builder | `christopher` | `apps/viewser/components/builder/floating-chat.tsx` + nya syskonfiler | `/api/prompt`, Python, kontrakt |
| C — backend-refaktorplan | Scout/Steward | `jakob-be` | en ny `docs/`-planfil | all kod |

**Lane B-not:** refaktor (inte buggfix) i Christophers UI-lane → behavior-
preserving + per-ändrings-OK (det stående grant:et täcker bara buggfixar).

Last verified state: `e03e1d1` (2026-06-08 UTC, `jakob-be` HEAD — manuell focus-refresh + slimning per current-focus-hygiene; `main` = `b49d1f7`/`16278c1` via PR #212, runda-2-sync väntar operatörsbeslut).
Nya PRs sedan föregående checkpoint: ingen ny merge till `main` sedan PR #212 (sync(jakob-be->main): hero-fix + Bite C + section_add broadening + governance/cleanup batch).

## Öppna PR att känna till

- **#156** (`feat/live-preview → jakob-be`): hostad `/live`-loop (prompt →
  sandbox → preview). **Parkerad pga säkerhet** — live-lane, INTE vår att
  merga/fixa.
- **#213** (`cursor/dev-env-setup-a8bd`): docs — Cloud Agent
  `VIEWSER_PREVIEW_MODE`-override-not. Liten docs-PR; granska/merga vid tillfälle.

Ingen öppen backend/heavy-LLM-PR mot `jakob-be`. Christophers UI-arbete sker på
`christopher` (gamla `christopher-ui` är fryst legacy med parkerad auth/billing).

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
flyttade till arkivet ovan (per `governance/rules/current-focus-hygiene.md`).
Auto-bump-verktyget lägger nya korta checkpoint-block här vid main-sync; håll
högst ett kvar och flytta resten till arkivet.
