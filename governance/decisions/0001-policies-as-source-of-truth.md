# ADR 0001: Policies som sanningskälla

- Status: accepterat
- Datum: 2026-05-07

## Kontext

I `Jakeminator123/sajtmaskin@master` växte sanningskällan utspritt: glossary i `docs/`, regler i `.cursor/rules/`, kvalitetsbegrepp inbakade i kod (`src/lib/gen/...`), prompt-kärna i `config/prompt-core/`, och tier-uppdelningen för quality gate utspridd över flera moduler. Det skapade namnskuggor (`brief`, `scaffold`, `context`, `autofix`) och svår styrbarhet.

## Beslut

Sajtbyggaren har **en** sanningskälla per koncept: en JSON-fil under `governance/policies/`. Allt annat (kod, docs, `.cursor/rules/`) härleds från den.

Konkret:

- Page-kvalitet: `governance/policies/page-quality-traits.v1.json`
- LLM-flöde och fasansvar: `governance/policies/llm-flow-concepts.v1.json`
- Begrepp och förbjudna alias: `governance/policies/naming-dictionary.v1.json`
- Mappägarskap: `governance/policies/repo-boundaries.v1.json`
- Preview Runtime-strategi: `governance/policies/preview-runtime-policy.v1.json`

Varje policy har ett strikt JSON Schema i `governance/schemas/` som valideras av `scripts/governance_validate.py`.

## Konsekvenser

- Code review blockerar koncept som inte finns i en policy.
- Cursor-regler är speglar (`scripts/rules_sync.py`), inte original.
- Backoffice (`backend.py`) är primär redigeringsyta för policies.
- Ändringar i en policy höjer dess `version` och `policyId`-suffix (`.v2`, `.v3`).
