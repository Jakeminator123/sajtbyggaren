# KÖR 1a — Blueprint schema skeleton

> Första halvan av blueprint-bron. **Bara schema + validators + mock-fixtures.** Ingen
> LLM-promptändring, ingen renderer-ändring. Liten, ofarlig, snabb.

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md).
**Beror på:** inget.

---

## Mål

Lägg till de **valfria** blueprint-fälten i de tre befintliga schemana + validators +
mock-fixtures. Inga modeller fyller dem ännu (det är `kor-1b`/`kor-1c`). Resultatet:
artefakterna *kan* bära blueprint, allt validerar, inga regressioner.

## Output (kontrakt)

| Schema | Nya `optional`-fält |
|--------|---------------------|
| `site-brief.schema.json` | `businessFacts {facts, unknowns}`, `positioning {oneLiner, differentiator, audienceNeed, localAngle, tone, avoid}`, `contentStrategy {heroAngle, trustStrategy, offerStrategy, avoidGenericClaims}`, `conversion {primaryAction, primaryCta, secondaryCta, contactPriority, ctaRules}` |
| `site-plan.schema.json` | `sectionPlan { "<routeId>.<sectionId>": {goal, copyIntent, visualTreatment, ctaRole, proofSources?} }` |
| `generation-package.schema.json` | `contentBlocks { "<routeId>.<sectionId>": {...} }`, `visualDirection {mood, density, heroStyle, colorIntent, sectionTreatments, imageBriefs, layoutSignals}`, `qualityRisks []` |

## Scope (filer)

- `governance/schemas/site-brief.schema.json`
- `governance/schemas/site-plan.schema.json`
- `governance/schemas/generation-package.schema.json`
- `packages/generation/artifacts/` (validators som accepterar nya fält)
- `governance/policies/naming-dictionary.v1.json` (**minsta nödvändiga** termer — se nedan)
- `tests/test_artifact_schemas.py` (+ ev. nya fixtures)

**Off-limits:** `extract.py`/`plan.py` promptlogik (det är `kor-1b`/`kor-1c`),
renderers, preview/adaptrar.

## Naming-dictionary: håll friktionen nere

Registrera **minsta nödvändiga term-set** som `check_term_coverage --strict` faktiskt
kräver. Utgångspunkt: **top-level fältgrupper** (`businessFacts`, `positioning`,
`contentStrategy`, `conversion`, `sectionPlan`, `contentBlocks`, `visualDirection`,
`qualityRisks`) — **inte** varje nested leaf (`positioning.oneLiner`,
`businessFacts.unknowns`, …) om inte testet uttryckligen flaggar dem. Varje nested
leaf-property ska inte bli en canonical term.

## Konkret arbete

1. Lägg fälten som `optional` i schemana (adressering `<routeId>.<sectionId>` enligt
   `01` §5). Inget blir `required`.
2. Uppdatera validators så de godkänner både med och utan blueprint.
3. Lägg mock-fixtures (ett exempel-blueprint per baseline-bransch) för senare tester.
4. Registrera de **top-level fältgrupper** term-coverage kräver — inte fler.

## Checks (scope-baserat)

`git diff --stat` · `python scripts/governance_validate.py` (schema rörda) ·
`python scripts/check_term_coverage.py --strict` (kör för att se exakt vilket minsta
term-set som krävs) · `python -m pytest tests/test_artifact_schemas.py -q`.

## Definition of done

- Nya fält finns, alla `optional`; befintliga artefakter validerar oförändrat.
- Mock-fixtures finns för de fyra baseline-branscherna.
- Minsta nödvändiga termer registrerade (top-level grupper). Scope-relevanta checks gröna.
- Ingen prompt/renderer rörd.

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 1a - lagg blueprint-falten som OPTIONAL i site-brief/site-plan/generation-
package-schemana + validators + mock-fixtures, enligt 01-artefakt-kontrakt-blueprint.md.

Krav:
- Bara schema/validators/fixtures. INGEN promptlogik (1b/1c), ingen renderer.
- Allt optional; befintliga artefakter ska validera oforandrat.
- Adressering <routeId>.<sectionId>.
- Naming-dictionary: registrera MINSTA nodvandiga term-set (helst top-level faltgrupper,
  inte varje nested leaf) - kor check_term_coverage --strict for att se vad som faktiskt kravs.

Definition of done: nya optionalfalt validerar med/utan blueprint, mock-fixtures for
fyra baseline-branscher, minsta term-set registrerat, term-coverage + governance_validate +
schema-tester grona.
```
