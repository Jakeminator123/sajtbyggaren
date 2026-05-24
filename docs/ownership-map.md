# Ownership Map

Den här kartan är en praktisk startpunkt för Team Parallel Work v1. Den låser
inte människor till filer för alltid, men den ska stoppa oavsiktliga krockar.

| Area | Primär ägare | Reviewer | Typiska filer/mappar | Får frontend ändra? | Får backend ändra? | Kräver contract-PR? |
| --- | --- | --- | --- | --- | --- | --- |
| Product North Star / roadmap | Jakob | Frontend-medutvecklare | `docs/current-focus.md`, `docs/handoff.md`, `docs/known-issues.md`, `docs/product-operating-context.md` | Bara docs-review eller explicit prompt | Ja | Nej, om inga shared data-shapes ändras |
| Generation backend | Jakob | Frontend-medutvecklare vid UI-effekt | `packages/generation/**`, `backend.py`, `scripts/build_site.py`, `scripts/dev_generate.py` | Nej, inte utan explicit beslut | Ja | Ja, om UI/API-shape påverkas |
| Planning / taxonomy / governance | Jakob | Extra review | `governance/**`, `packages/generation/planning/**`, `packages/generation/discovery/**` | Nej | Ja, med extra review | Ja, om frontend konsumerar ny shape |
| Starters / scaffolds / dossiers | Jakob | Extra review | `data/starters/**`, `packages/generation/orchestration/**`, `packages/generation/orchestration/scaffolds/**`, `packages/generation/orchestration/dossiers/**` | Nej, inte utan explicit beslut | Ja, via PR och review | Ja, om preview/UI-data ändras |
| Viewser / frontend app | Frontend-medutvecklare | Jakob | `apps/viewser/**` | Ja | Ja, men backend ska säga till om UI ändras | Ja, om backend contract eller run-shape ändras |
| Preview shell / preview UI | Shared | Båda | `apps/viewser/components/viewer-panel.tsx`, `apps/viewser/lib/stackblitz-files.ts`, framtida preview-runtime | Ja, för UI | Ja, för runtime/contract | Ja vid dataformatändring |
| Follow-up/version UI | Shared | Båda | `apps/viewser/components/run-history.tsx`, `apps/viewser/components/prompt-builder.tsx`, `apps/viewser/lib/runs.ts`, run/version-artifacts | Ja, för listor, knappar och UX | Ja, för version/run-state | Ja |
| Quality/evals display | Shared | Båda | `scripts/mini_eval.py`, `apps/viewser/components/run-details-panel.tsx`, `docs/quality.md`, eval-output docs | Ja, för presentation | Ja, för score/eval-result | Ja, om result-shape ändras |
| Tests | Delat efter yta | Båda vid shared contract | `tests/**`, `apps/viewser/**`, contract tests när de finns | Ja, frontendtester | Ja, backendtester | Ja, för contracttester |
| Cursor/agent workflow | Jakob / Steward | Frontend-medutvecklare vid team-effekt | `docs/agent-prompts.md`, `docs/orchestrator-playbook.md`, `governance/rules/**`, `.cursor/rules/**` | Bara efter explicit prompt | Ja | Nej, om det bara är workflow |

## Konfliktregel

Om en ändring kräver samma fil från två spår ska featurearbetet pausas och en
liten contract- eller docs-PR göras först. Efter merge kan frontend och backend
fortsätta parallellt mot samma överenskomna shape.

## När kartan ska ändras

Uppdatera kartan när en ny delad yta skapas, när Viewser börjar konsumera en ny
backend-shape, eller när en ny ägare faktiskt tar över ett område.

## Branch-konventioner

`branch-discipline.md` säger att standardflödet är arbete direkt på `main`. När
operatören uttryckligen begär parallellt teamarbete (PR-flöde, feature-branch)
gäller följande namnkonventioner. De signalerar ägarskap och triggar rätt
agent-rules (se `governance/rules/branch-scope-ui-ux.md`).

| Område | Branch-mönster | Exempel |
| --- | --- | --- |
| Backend / governance / scripts | `jakob/*`, `backend/*`, `jakob-be` | `jakob-be`, `jakob/wizard-gap-4`, `backend/quality-gate-v2` |
| Frontend / UI / UX | `christopher-*`, `frontend/*`, `ui/*`, `ux/*` | `christopher-ui-2`, `frontend/asset-store-v2` |
| Docs / agent-workflow | `cursor/*` | `cursor/branch-conventions`, `cursor/marketing-base` |
| Tooling / CI | `tooling/*`, `ci/*` | `tooling/ruff-update` |

`main` är sanningen. Pushas aldrig direkt med `--force`. Efter squash-merge är
feature-branchen "konsumerad" — starta en ny branch från nya `main` för nästa
arbete, pulla aldrig en redan squash-mergad branch.
