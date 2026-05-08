# Handoff – Sajtbyggaren

**Datum:** 2026-05-08
**Senaste commit på `main`:** `c8d8043` (docstring-sync efter Sprint 2A; PR #7 `3dbffe4` är den senaste merge-commit:en)
**Aktiv branch:** `main`

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator som ersätter `Jakeminator123/sajtmaskin`. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:
- **`governance/`** – JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- **`backoffice/` + `backend.py`** – Streamlit-administration (inte runtime).
- **`packages/` + `apps/`** – framtida runtime + kund-UI (mestadels tom än).

## Vad funkar idag

- ADR 0001–0012 + 14 policies + matchande schemas
- 4 automatiska checks: `governance_validate.py`, `rules_sync.py`, `check_term_coverage.py --strict`, `pytest`
- GitHub Actions kör alla på push/PR
- **Sprint 2A klar (PR #7, `3dbffe4`):** både `scripts/build_site.py` och `scripts/dev_generate.py` anropar riktiga `briefModel` (gpt-5.4) via OpenAI med Pydantic structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `site-brief.json` markeras med `briefSource` (`real` / `mock-no-key` / `mock-llm-error`) och `modelUsed`.
- `scripts/build_site.py`: deterministisk Builder MVP - skriver alla canonical artefakter inkl. `generated-files/`-snapshot, kör `npm install` + `npm run build` på `.generated/<siteId>/`, gated bakom `--skip-build` för snabb iteration.
- `scripts/dev_generate.py`: mock-pipeline för regression - skriver alla 8 artefakter + `trace.ndjson` (fas 2-3 är mock).
- Backoffice (`streamlit run backend.py`) visar Status, Governance, LLM Engine, Building Blocks, Engine Runs, Evals, Playground.
- `local-service-business`-scaffolden + `marketing-base`-startern + `interactive-game-loop`-dossiern finns implementerade.

## Vad är mock än så länge

- Fas 2 `planningModel`: scaffold/variant/dossier-val är deterministisk stub (planeras Sprint 2B).
- Fas 3: `codegenModel`, Repair Pipeline (`packages/generation/repair/`), Quality Gate (`packages/generation/quality-gate/`), Preview Runtime - alla planerade Sprint 3-5.
- Övriga scaffold-IDs i `scaffold-contract.v1.json` har inget content under `packages/generation/orchestration/scaffolds/<id>/`.
- `apps/web` finns inte alls.

## Öppna beslut som operatör måste ta

Reviewer-konversation i `referens/utlatanden/konversation-allmant-arkitektur.txt` föreslår tre arkitekturskift som inte är bekräftade än:

1. **6-stegs-flow** (`Plan → Generate → Verify → Repair → Preview → Release`) ersätter dagens 3-fas (`understand → plan → build`).
2. **4 dossier-typer** (`site / feature / integration / data`) på en separat axel från `soft / hybrid / hard`.
3. **5 starters** (`marketing-base`, `saas-base`, `commerce-base`, `portfolio-base`, `docs-base`) under `data/starters/<id>/` istället för 14.
4. **Scaffolds är arvet, inte hugget i sten** – se `governance/decisions/0011-scaffolds-as-inherited-working-material.md`.

## Reading order för ny agent

Läs i denna ordning:

1. `AGENTS.md` (top-level rules)
2. `docs/glossary.md` (alla termer)
3. `governance/policies/naming-dictionary.v1.json` (kanon)
4. `governance/policies/engine-run.v1.json` (artefaktkedjan)
5. `governance/policies/repo-boundaries.v1.json` (vad får importera vad)
6. `governance/decisions/0001` till `0011` (varför vi gör som vi gör)
7. `referens/utlatanden/konversation-allmant-arkitektur.txt` (reviewerns omtag)
8. `docs/migration-plan.md` (sprint-läget)

## Köra och testa

```powershell
# Lokal venv (rekommenderat - .venv/ är gitignorerad)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Backoffice
streamlit run backend.py

# Engine Run i mock-pipeline (anropar briefModel om OPENAI_API_KEY finns)
python scripts/dev_generate.py "Skapa hemsida för en elektriker i Malmö"

# Builder MVP - genererar riktig Next.js-sajt
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build

# Med riktig briefModel
$env:OPENAI_API_KEY = "sk-..."
python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build

# Alla checks
python scripts/governance_validate.py
python scripts/rules_sync.py --check
python scripts/check_term_coverage.py --strict
python -m pytest -q
```

## Commit-krav

- Aldrig commit utan att alla 4 checks passerar
- Alltid PR-flöde, aldrig push direkt till `main`
- Commit-meddelanden på engelska, dokumentation på svenska
- ÅÄÖ ska skrivas korrekt – aldrig `\u00f6` eller ASCII-translit

## Stil i kommunikation

- Kod, identifierare, commits, branchnamn: **engelska**
- Operatörs-UI, dokumentation, ADR, agent-svar: **svenska**
- Slutanvändar-prompter och genererade sajter: **språkagnostiska** (detekteras av `briefModel`)
