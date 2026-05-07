# Handoff – Sajtbyggaren

**Datum:** 2026-05-07
**Senaste commit på `main`:** `a17439d` (Merge PR #2)
**Aktiv branch när handoff skrevs:** `cursor/handoff-och-stadning`

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator som ersätter `Jakeminator123/sajtmaskin`. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:
- **`governance/`** – JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- **`backoffice/` + `backend.py`** – Streamlit-administration (inte runtime).
- **`packages/` + `apps/`** – framtida runtime + kund-UI (mestadels tom än).

## Vad funkar idag

- 5 ADR (0001–0010) + 13 policies + matchande schemas
- 4 automatiska checks: `governance_validate.py`, `rules_sync.py`, `check_term_coverage.py`, `pytest`
- GitHub Actions kör alla på push/PR
- `briefModel` (fas 1): riktig OpenAI-anrop med Pydantic structured output, fallback till mock
- `dev_generate.py`: kör Engine Run end-to-end och skriver 8 artefakter + `trace.ndjson` (fas 2-3 är mock)
- Backoffice (`py backend.py`) visar Status, Governance, LLM Engine, Building Blocks, Engine Runs, Evals, Playground

## Vad är mock än så länge

- Fas 2: Scaffold/Variant/Route/Dossier-selection (skriver platshållardata)
- Fas 3: Codegen, Repair Pipeline, Quality Gate, Preview Runtime
- Inget av de 14 scaffold-IDs i `scaffold-contract.v1.json` har innehåll i `packages/generation/orchestration/scaffolds/<id>/`
- `apps/web` finns inte alls

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
# Backoffice
streamlit run backend.py

# Engine Run i mock
py scripts/dev_generate.py --prompt "Skapa hemsida för en elektriker i Malmö"

# Engine Run med riktig brief (kräver OPENAI_API_KEY)
$env:OPENAI_API_KEY = "sk-..."
py scripts/dev_generate.py --prompt "..."

# Alla checks
py scripts/governance_validate.py
py scripts/rules_sync.py --check
py scripts/check_term_coverage.py --strict
py -m pytest -q
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
