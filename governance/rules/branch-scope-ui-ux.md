---
description: På scoped frontend-branches (`christopher-*`, `frontend/*`, `ui/*`, `ux/*`) äger agenten UI/UX i viewser-appen och designsystemet för genererade sajter. Backend-motorn (API-routes, server-lib, scripts, codegen, runtime-policies, schemas, infra) är off-limits utan operatörens OK. Backend ägs separat på `main`.
alwaysApply: true
---

# Branch-scope - UI/UX vs Backend

## När gäller regeln

Aktiv när `git branch --show-current` matchar något av följande mönster:

- `christopher-*`
- `frontend/*`
- `ui/*`
- `ux/*`

På `main` och andra branches gäller `branch-discipline.md` som vanligt
och denna regel träder ur kraft.

## Off-limits-paths (rör inte utan operatörens OK)

Allt här är backend-motorn. Read är OK, edit är inte OK.

### Server-lagret i viewser-appen

- `apps/viewser/app/api/**`
- `apps/viewser/lib/**` (alla server-runners, asset-store-pipeline,
  openai-klient, scrape-runner, build-runner, prompt-runner, runs,
  project-inputs, stackblitz-files, localhost-guard, utils)
- `apps/viewser/middleware.ts`, `apps/viewser/next.config.ts`
- `apps/viewser/package.json`, `apps/viewser/package-lock.json`

### Python-stacken

- `scripts/**` (alla `.py` och `.ps1`)
- `backoffice.py`, `backoffice/**`
- `packages/generation/{codegen,discovery,engine,quality_gate,repair,build,brief,planning,maintenance,artifacts}/`
- `pyproject.toml`, `pyrightconfig.json`, `requirements*.txt`

### Runtime-policies och kontrakt

- `governance/policies/{repo-boundaries,engine-run,embedding-policy,llm-models,llm-flow-concepts,fix-registry,naming-dictionary,capability-map,dossier-contract,preview-runtime-policy}.v1.json`
- `governance/schemas/**` (alla JSON-schemas)

### Repo-infra

- `.github/**` (CI/CD)
- `.cursor/**` (genererad spegel - kör `python scripts/rules_sync.py`
  efter ändring i `governance/rules/`, redigera aldrig spegeln direkt)
- `AGENTS.md` (uppdateras bara på explicit operatörsbeslut)
- `data/runs/**`, `data/uploads/**` (genererat - rör aldrig)
- `examples/**`, `tests/test_*.py`

## Inte off-limits (design för genererade sajter ÄR ditt jobb)

För att slutkundens sajter ska bli snygga, interaktiva och personaliserade
får agenten arbeta fritt här:

- `data/starters/**` (Next.js-scaffolds för genererade sajter)
- `packages/generation/orchestration/scaffolds/**/variants/*.json`
- Design-bärande policies under `governance/policies/`:
  `scaffold-contract`, `scaffold-selection`, `discovery-taxonomy`,
  `dossier-selection`, `page-quality-traits`, `starter-registry`,
  `project-dna`
- Hela viewser-appens presentationslager: `apps/viewser/app/**/*.tsx`
  och `*.css` *utanför* `app/api/`, `apps/viewser/components/**`,
  `apps/viewser/public/**`, `apps/viewser/components.json`, tailwind-,
  postcss- och eslint-config

Om en design-policy-ändring kräver schema-ändring i `governance/schemas/`:
stoppa och fråga operatören. Det är gränssnitt mellan zonerna.

## Vad agenten gör om uppgift kräver off-limits-ändring

1. Stoppa innan edit av en off-limits-fil.
2. Skriv kort förslag till operatören: vilken fil, varför, minimal
   backend-ändring kollegan kan göra.
3. Vänta på explicit grönt ljus. Tre möjliga svar:
   - "Hoppa över det", eller
   - "Backend-kollegan tar det" (UI-uppgiften pausas), eller
   - "Gör det själv ändå" (commit-body taggas `[scope-leak]` +
     `Approved by operator: <kort motivering>`).

## Pull-first-disciplin

Backend-kollegan pushar ofta direkt till `main`. För att slippa merge-konflikter:

1. **Vid sessionsstart:** `git fetch origin` och kolla
   `git rev-list --count HEAD..origin/main`. Om > 0: dra in före nytt arbete.
2. **Om lokala commits finns:** `git merge origin/main` och lös konflikter
   med scope-regeln - off-limits-filer tar `--theirs` (main vinner),
   in-scope-filer behåller `--ours`.
3. **Om inga lokala commits finns och din scoped-branch är en tillfällig
   integrationsbranch som operatören bekräftat:** `git reset --hard origin/main`
   är snabbast. Stoppa och fråga om du är osäker — `reset --hard` förstör
   outpushat arbete och kan inte ångras.
4. **Före push:** kör `git fetch origin && git status` igen så remote inte
   rört sig mellan steg.

## Pre-commit-check

Före varje commit på `christopher-ui` kör agenten:

```bash
git diff --cached --name-only
```

och dubbelkollar att inga off-limits-paths är med. Om några är med:
unstage:a (`git restore --staged <fil>`) eller stoppa för operatörsbeslut
enligt sektionen ovan.

## De fyra guards före push

Som branch-discipline.md kräver. För docs/rules/governance-ändring räcker
de fyra första; kör pytest också vid kod- eller policy-ändring som kan
påverka tester:

1. `python scripts/governance_validate.py`
2. `python scripts/rules_sync.py --check`
3. `python scripts/check_term_coverage.py --strict`
4. `python -m pytest -q` (vid kod/policy-ändring)

Alla ska vara gröna. Aldrig commit + push på rött.

## Push-disciplin

- `git fetch origin && git status` direkt före push.
- `git push --force-with-lease` är OK på din egen scoped frontend-branch
  endast om operatören uttryckligen bekräftat att branchen är solo-ägd och
  tillfällig. Vid "stale info"-fel kör `git fetch --prune` och sen
  `git push -u origin <branch>` som ny branch.
- Aldrig `--force` eller `--force-with-lease` på `main`, `develop` eller
  någon delad branch.

## Vad regeln inte gör

- Ersätter inte CODEOWNERS eller server-side GitHub-skydd.
- Hindrar inte operatören själv från att redigera backend manuellt - bara
  agenten. Operatören är alltid sista beslutsfattare.
