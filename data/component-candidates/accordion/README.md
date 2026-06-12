# Komponentkandidat: accordion

Genererad av det **kurerade shadcn-intaget** (`scripts/component_intake.py`, ADR 0054). Detta är en KANDIDAT för granskning - inte en canonical fil.

## Härkomst
- Prompt: `accordion for an FAQ section, accessible, zero new dependencies if possible`
- Modell: `gpt-5.4`
- shadcn-items: accordion
- Innehållshash: `sha256:2b93884ffa2f099b9238639ee80259cd12c348759534c75d4969c2ac5ded957a`
- Krävda npm-deps: (inga - zero-dep)

## Granskningsinstruktion (operatör)
1. Läs `component.tsx`. Verifiera tillgänglighet, att inga fakta hittas på, och att importvägarna är `@/components/ui` + `@/lib/utils`.
2. **Beroenden:** kandidaten får INTE dra in ett nytt npm-beroende i en Starter utan policy + operatörsgodkännande. Om `requiredNpmDeps` inte redan finns i mål-Startern: behåll det native mönstret i stället.
3. Kurera in i en Starter via en EGEN PR: kopiera till `data/starters/<starterId>/components/ui/`, kör `python scripts/generate_component_manifests.py` och committa manifestet.
4. Koppla ev. capability → komponent i `governance/policies/capability-map.v1.json` (`components`-nyckeln, ADR 0040) så korskontrollen i `scripts/governance_validate.py` blir grön.

> Intaget skriver ALDRIG direkt i `data/starters/` eller `packages/generation/orchestration/`. Promotering är ett operatörsbeslut via granskad PR.
