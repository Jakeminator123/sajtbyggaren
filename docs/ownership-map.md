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

`branch-discipline.md` beskriver standardflödet "jobba direkt på `main`". När
operatören uttryckligen begär parallellt team-arbete (PR-flöde) gäller följande
namn- och livscykel-konventioner.

### Permanenta team-branches (always-on, en per teammedlem)

Varje teammedlem har en stabil branch namngiven efter sin domän. Den är inte en
feature-branch utan en **arbets-branch** — ett dagligt utgångsläge mellan main-
synkar. PR:ar från arbets-branchen till `main` när "sanningen" ska uppdateras.

| Teammedlem | Domän | Branch | Cursor-rule som matchar |
| --- | --- | --- | --- |
| Jakob | Backend, governance, scripts, codegen | `jakob-be` | `branch-scope-ui-ux.md` matchar **inte** — Jakob får röra all backend |
| Christopher | Frontend, viewser, UI/UX | `christopher` | `branch-scope-ui-ux.md` (off-limits för backend) |

> **Branch-not:** Christophers aktiva arbets-branch är `christopher` (avstamp
> från `jakob-be`). Den gamla `christopher-ui` är **fryst legacy** — den bär
> parkerad auth/billing (`NEXT_PUBLIC_AUTH_ENABLED`, default AV) som tas in
> långt senare och rörs inte utan operatörens OK. Se
> [`governance/rules/christopher-active-branch.md`](../governance/rules/christopher-active-branch.md)
> och [ADR 0035](../governance/decisions/0035-auth-billing-scope-gate.md).

### Livscykel för arbets-branchen

1. **Skapa en gång:** `git switch main && git switch -c <branch> && git push -u origin <branch>`. Arbets-branchen lever ovanpå main.
2. **Commit + push** dina ändringar på arbets-branchen löpande. Två commits per logiskt steg är OK, men håll ofta små.
3. **PR till main när du vill släppa något:** `gh pr create --base main --head <branch>`. Squash-merge i regel.
4. **Efter merge:** synka arbets-branchen mot main innan nästa commit:

   ```
   git switch <branch>
   git fetch origin
   git reset --hard origin/main
   git push --force-with-lease origin <branch>
   ```

   `--force-with-lease` är OK eftersom arbets-branchen är solo-ägd (regeln i `branch-scope-ui-ux.md` tillåter det explicit).

5. **Pulla aldrig en redan squash-mergad branch** med `git pull` — det skapar en merge-commit + konflikter mot squash-en på main. Reset eller skapa om från main.

### Tillfälliga feature-branches (när uppgiften är stor eller delas)

| Område | Branch-mönster | Exempel |
| --- | --- | --- |
| Backend-feature | `jakob/<feature>`, `backend/<feature>` | `jakob/wizard-gap-4`, `backend/quality-gate-v2` |
| Frontend-feature | `frontend/<feature>`, `ui/<feature>`, `ux/<feature>` | `frontend/asset-store-v2` |
| Docs / agent-workflow | `cursor/<syfte>` | `cursor/branch-conventions`, `cursor/marketing-base` |
| Tooling / CI | `tooling/*`, `ci/*` | `tooling/ruff-update` |

Tillfälliga branches startas från `main` (eller arbets-branchen om de bygger på
oppushat arbete), PR:as till main, raderas efter merge.

### Main

`main` är sanningen. Pushas aldrig med `--force`. Inga direkta pushes från
teammedlemmar utan operator-OK — allt går via PR.
