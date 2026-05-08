# Handoff – Sajtbyggaren

**Datum:** 2026-05-08
**Senaste commit på `main`:** uppdateras vid varje pre-Sprint cleanup. Kör `git log --oneline -1` för aktuell HEAD.
**Aktiv branch:** `main` (per `governance/rules/branch-discipline.md` är direkt commit + push mot `origin/main` standardflödet — PR används bara när operatören uttryckligen ber om det).

Detta är en operatörsfri översikt så att en ny agent kan ta över på 5 minuter utan att läsa hela transkriptet.

## Vad är Sajtbyggaren

En policy-driven hemsidegenerator som ersätter `Jakeminator123/sajtmaskin`. Mål: 9/10 kvalitet, ingen plattformsinlåsning, governance som sanningskälla.

Tre lager:

- **`governance/`** – JSON-policies + JSON-Schemas + ADR. Sanningskällan.
- **`backoffice/` + `backend.py`** – Streamlit-administration (inte runtime).
- **`packages/` + `apps/`** – framtida runtime + kund-UI (mestadels tom än).

## Vad funkar idag

- ADR 0001–0014 + 15 policies + matchande schemas.
- 4 automatiska checks: `governance_validate.py`, `rules_sync.py`, `check_term_coverage.py --strict`, `pytest`. GitHub Actions kör alla på push/PR.
- **Sprint 2A (PR #7, `3dbffe4`):** både `scripts/build_site.py` och `scripts/dev_generate.py` anropar riktiga `briefModel` (gpt-5.4) via OpenAI med Pydantic structured output när `OPENAI_API_KEY` finns; mock-fallback annars. `site-brief.json` markeras med `briefSource` (`real` / `mock-no-key` / `mock-llm-error`) och `modelUsed`. `has_openai_api_key()`-helpern stripar whitespace så `"   "` räknas som saknad nyckel.
- **Sprint 2B:** `packages/generation/planning/produce_site_plan` är enda källan för Site Plan + Generation Package. Båda scripten anropar samma helper - `dev_generate.py` utan pinning (planSource `real` / `mock-no-key` / `mock-llm-error`), `build_site.py` med `pinned={scaffoldId, variantId}` från Project Input (planSource `pinned`, planningModel skippas eftersom operatörens val är auktoritativt). Capability-filter ("tom dossier-lista = gap") körs centralt så `selectedDossiers.rejected[]` alltid speglar verkligheten. Builder läser `starterId` från planen istället för att hårdkoda `marketing-base`. **B19 stängd.**
- **ADR 0013 schema-låsning:** site-brief, site-plan, generation-package och sections har JSON Schemas under `governance/schemas/`. Båda scripten validerar artefakter vid skrivning via `packages/generation/artifacts/validate.py`. `capability-map.v1.json` registrerar 12 capability-slugs (men bara `interactive-game` har en riktig Dossier idag). `site-plan.schema.json:planSource` accepterar nu också `pinned` (Sprint 2B).
- `scripts/build_site.py`: deterministisk Builder MVP - skriver alla canonical artefakter inkl. `generated-files/`-snapshot. `npm install`/`npm run build` har timeouts (600s/300s) som ger `status=failed` istället för att hänga. `--skip-build` för snabb iteration.
- `scripts/dev_generate.py`: mock-pipeline för regression - skriver alla 8 artefakter + `trace.ndjson` (fas 1+2 anropar real LLM när nyckel finns; fas 3 är fortsatt mock placeholder).
- Backoffice (`streamlit run backend.py`) visar Status, Governance, LLM Engine, Building Blocks, Engine Runs, Evals, Playground.
- Två scaffolds har innehåll: `local-service-business` (variant `nordic-trust`) och `ecommerce-lite` (variant `clean-store`, Sprint 2B). Båda mappar till `marketing-base`-starter via `SCAFFOLD_TO_STARTER` i `packages/generation/planning/plan.py`. `interactive-game-loop`-dossiern är den enda implementerade Dossiern idag.

## Vad är mock än så länge

- Fas 3: `codegenModel`, Repair Pipeline (`packages/generation/repair/`), Quality Gate (`packages/generation/quality-gate/`), Preview Runtime - alla planerade Sprint 3-5.
- `data/starters/commerce-base/` är fortfarande oharmoniserad zip/README. Ecommerce-lite mappar därför till `marketing-base` tills en separat starter-harmoniserings-sprint plockar upp `vercel/commerce`-zipen, kör Next-codemods och bryter ut Shopify-integrationen till en hard Dossier (se issue-id b20 i `docs/known-issues.md`).
- Övriga 12 scaffold-IDs i `scaffold-contract.v1.json` har inget content under `packages/generation/orchestration/scaffolds/<id>/` - bara `local-service-business` och `ecommerce-lite` har körbara filer.
- `apps/web` finns inte alls.
- 11 av 12 capability-slugs i `capability-map.v1.json` har tom `dossiers`-lista. Hård-Dossier-import (resend-contact-form, stripe-checkout, clerk-auth, commerce-shopify, etc. från `referens/min-ide-templates/` och `data/starters/commerce-base/commerce-main.zip`) sker tidigast i Sprint 3. `produce_site_plan` registrerar dem som `selectedDossiers.rejected[]` med `comment` från capability-map som motivering.

## Beslutsläge för arkitektur-frågor

Tre arkitekturförslag från tidiga reviewer-utlåtanden är **avgjorda av ADR** och hör inte längre hemma som "öppna beslut":

| Förslag                                               | Status                                                                                                          | Referens                                          |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 6-stegs-flow (`Plan → Generate → ...`) ersätter 3-fas | **Avvisat.** Canonical är `understand → plan → build`.                                                          | `engine-run.v1.json`, `llm-flow-concepts.v1.json` |
| 4 dossier-typer (`site/feature/integration/data`)     | **Avvisat.** Endast `soft` och `hard` per ADR 0012. Övriga är på `naming-dictionary.v1.json:globallyForbidden`. | ADR 0012                                          |
| 5 starters istället för 14                            | **Accepterat som plan.** Just nu finns bara `marketing-base` med innehåll. De andra fyra är gitkeep-mappar.     | README "Starter"-listan                           |
| Scaffolds som ärvt arbetsmaterial, inte hugget i sten | **Accepterat.**                                                                                                 | ADR 0011                                          |

## Reading order för ny agent

Läs i denna ordning:

1. `AGENTS.md` (top-level rules + venv-setup)
2. `docs/glossary.md` (alla termer)
3. `governance/policies/naming-dictionary.v1.json` (kanon)
4. `governance/policies/engine-run.v1.json` (artefaktkedjan)
5. `governance/policies/repo-boundaries.v1.json` (vad får importera vad)
6. `governance/decisions/0001` till `0014` (varför vi gör som vi gör — särskilt 0012 vocabulary compression, 0013 schema-låsning, 0014 Sprint 2B planning helper)
7. `governance/rules/branch-discipline.md` (commit + push direkt mot main är standard, inte PR)
8. `docs/migration-plan.md` (sprint-läget)
9. `docs/known-issues.md` (öppna och stängda buggar med IDs)

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

- Aldrig commit utan att alla 4 guards passerar (se ovan)
- Standardflöde: commit + push direkt mot `origin/main`. PR används bara när operatören explicit ber om det. Detaljer i `governance/rules/branch-discipline.md`.
- Commit-meddelanden på engelska, dokumentation på svenska
- ÅÄÖ ska skrivas korrekt – aldrig `\u00f6` eller ASCII-translit

## Stil i kommunikation

- Kod, identifierare, commits, branchnamn: **engelska**
- Operatörs-UI, dokumentation, ADR, agent-svar: **svenska**
- Slutanvändar-prompter och genererade sajter: **språkagnostiska** (detekteras av `briefModel`)
