# ADR 0013 – Schema-låsning före Sprint 2B

**Status:** accepted
**Datum:** 2026-05-08
**Beroenden:** ADR 0009 (Engine Run och Model Roles), ADR 0012 (vocabulary compression), `engine-run.v1.json`, `scaffold-contract.v1.json`

## Kontext

Sprint 2A (PR #7, `3dbffe4`) kopplade in `briefModel` i `scripts/build_site.py` och `scripts/dev_generate.py`. Sprint 2B kommer koppla in `planningModel`. Innan dess har vi tre läckor i artefaktkontraktet:

1. **`engine-run.v1.json` säger att artefakter finns men låser inte fältformaten.** `siteBrief`, `sitePlan` och `generationPackage` har en filename, ett `writtenBy` och ett `purpose`-fält men inget JSON Schema som säger vilka fält som måste finnas.
2. **`scripts/build_site.py` och `scripts/dev_generate.py` skriver delvis olika fält-namn för samma artefakt.** Builder skriver `briefSource`, `modelUsed`, `briefError`. `dev_generate.py` skriver samma plus `_status`. Pydantic-klassen SiteBrief i `packages/generation/brief/extract.py` använder `business_type` (snake_case) medan artefakten skrivs med `businessTypeGuess`. Tre delvis-olika sanningskällor.
3. **`local-service-business/sections.json` finns** och `scaffold-contract.v1.json` säger att den är obligatorisk, men det finns inget schema som validerar att andra scaffolds skriver `sections.json` i samma form. Reviewerns formulering: *"Gapet är inte 'saknad fil', utan att sections.json saknar schema/validering."*

Om `planningModel` kopplas in nu mot dessa lösa kontrakt kommer Sprint 2B-koden låsa fast den nuvarande dialekten i två script samtidigt – det är exakt så `Jakeminator123/sajtmaskin` började driva isär.

Reviewer-input som ledde fram till denna ADR finns i `konversation.txt` (samtal 2026-05-08, två oberoende reviewers) och sammanfattas i [`docs/migration-plan.md`](../../docs/migration-plan.md) Sprint 2B-stycket.

## Beslut

Innan Sprint 2B börjar kodas låser vi fyra schemas och en policy. Inget annat ändras i samma vända.

### Nya filer som låses

| Fil | Roll |
|---|---|
| `governance/schemas/site-brief.schema.json` | JSON Schema för `data/runs/<runId>/site-brief.json` (artefakten skriven av fas 1 Understand). |
| `governance/schemas/site-plan.schema.json` | JSON Schema för `data/runs/<runId>/site-plan.json` (artefakten skriven av fas 2 Plan). |
| `governance/schemas/generation-package.schema.json` | JSON Schema för `data/runs/<runId>/generation-package.json`. |
| `governance/schemas/sections.schema.json` | JSON Schema för `<scaffoldId>/sections.json` (route → required/optional sections + orderRules). |
| `governance/policies/capability-map.v1.json` | Policy som mappar abstrakta capability-slugs (t.ex. interactive-game, payments, analytics) till kandidat-Dossier-IDs. Förutsättning för `planningModel`-rerank. |
| `governance/schemas/capability-map.schema.json` | JSON Schema för `capability-map.v1.json`. |

### Ändringar i befintliga policies

- `engine-run.v1.json`: artefakt-objekt får ett valfritt `schema`-fält som pekar på rätt schema. Bara fas 1+2-artefakter får schema i denna runda; `repair-result.json`, `quality-result.json` och `build-result.json` lämnas utan schema tills Sprint 3.
- `engine-run.schema.json`: tillåter det nya valfria `schema`-fältet på artefakt-objekt.
- `scaffold-contract.v1.json`: `requiredFiles`-listan får en `validatedAgainst`-tabell som pekar `sections.json` mot `sections.schema.json`.
- `scaffold-contract.schema.json`: tillåter det nya valfria `validatedAgainst`-fältet.
- `naming-dictionary.v1.json`: lägger till canonical entry för `capabilityMap` (alias-form med mellanslag tillåts via aliasesAllowed).

### Runtime-konsekvenser

`scripts/build_site.py` och `scripts/dev_generate.py` ska validera artefakter mot dessa schemas innan filerna skrivs. Validering sker via en delad helper `packages/generation/artifacts/validate.py` så det inte blir två kopior av jsonschema-anropet.

`tests/` får tre nya regression-tester:

1. `test_artifact_schemas.py` — varje site-brief/site-plan/generation-package som någon test-build skriver ska matcha schemat.
2. `test_sections_schema.py` — `local-service-business/sections.json` (och alla framtida `<scaffoldId>/sections.json`) ska matcha `sections.schema.json`.
3. `test_capability_map.py` — `capability-map.v1.json` matchar sitt schema och alla nämnda dossier-IDs finns under `packages/generation/orchestration/dossiers/{soft,hard}/`.

## Vad detta INTE är

- **Inte Sprint 2B-kod.** Ingen `planningModel`-anrop, ingen Selector, inga embeddings.
- **Inte ny scaffold-content.** Andra scaffolden (saas-product eller dylikt) kommer i en separat ADR efter Sprint 2B.
- **Inte hard Dossier-import.** MIN_IDE-content (clerk-auth, stripe-checkout, etc.) plockas in stegvis i Sprint 3, en per gång, inte big-bang.
- **Inte pre-brief variant-hint.** MIN_IDE:s `VariantHints`-projektion till `briefModel` skulle bryta `engine-run.v1.json` (fas 1 får inte välja Variant). Eventuell context-augmentation diskuteras separat efter Sprint 2B.
- **Inte follow-up-axel-rework.** Reviewer föreslog `interactionKind` som ny axel ovanpå `project-dna.v1.json`:s 8 intents. Detta är intressant men påverkar inte Sprint 2B-blockern och tas i en egen ADR.
- **Inte rename av befintliga termer.** "Deep Brief" är fortsatt `aliasesAllowed` för `Project Input` enligt ADR 0012. "delta-brief" läggs däremot på `globallyForbidden` i samma vända som naming-dictionary uppdateras (Commit 4).

## Konsekvens

- Schemat är sanningskällan. Pydantic `SiteBrief` i `packages/generation/brief/extract.py` ska härleda sina fält från schemat (eller validera mot det vid serialisering). Två sanningskällor accepteras under en migrationsperiod – schemat är den som vinner vid konflikt.
- `scripts/build_site.py` och `scripts/dev_generate.py` får inte längre skriva fält som inte finns i schemat. `_status`-fältet (idag både i builder och dev_generate) tas bort till förmån för `briefSource` som redan är canonical.
- `planningModel`-arbetet i Sprint 2B kan nu härleda en `SitePlan`-Pydantic-class direkt från `site-plan.schema.json` istället för att uppfinna ett tredje fält-format.
- `scaffold-contract.v1.json` blir striktare: framtida scaffolds får inte mergas till `main` om deras `sections.json` inte validerar.
- Backoffice (Streamlit) kan på sikt rendera artefakter med schema-driven validering, men ingen UI-förändring i denna runda.

## Alternativ vi övervägde

- **Hoppa över schema-låsningen och köra Sprint 2B direkt.** Avvisat. Det är exakt så `Jakeminator123/sajtmaskin` började – två script som drev isär artefaktformaten under tre sprintar.
- **Härleda schemas från Pydantic-class:erna automatiskt.** Möjligt senare. Just nu vill vi att schemat är skriven först och tydlig, och att Pydantic-klassen anpassas till det. Annars låser vi fast vad än Pydantic råkar tycka i en migrationsfas.
- **Lägg också `repair-result.json`, `quality-result.json` och `build-result.json` på schema nu.** Avvisat. Sprint 3 kommer designa Repair Pipeline och Quality Gate på riktigt och dessa artefakter får sin slutgiltiga form då. Att låsa skelett-format nu skulle låsa in Sprint 1-arvet i onödan.

## Mätbart efter PR

- `python scripts/governance_validate.py` grön (med fyra nya schemas + en ny policy validerade).
- `python scripts/rules_sync.py --check` grön.
- `python scripts/check_term_coverage.py --strict` grön.
- `python -m pytest -q` grön (tre nya tester ovanpå befintliga ~110).
- `python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build` skriver en `data/runs/<runId>/site-brief.json` som validerar mot `site-brief.schema.json`.
- `python scripts/dev_generate.py "Skapa hemsida för en elektriker i Malmö"` skriver `site-brief.json`, `site-plan.json` och `generation-package.json` som alla validerar mot sina respektive schemas.

## Referenser

- ADR 0009 — Engine Run och Model Roles (etablerar artefaktkedjan som låses här)
- ADR 0012 — Vocabulary compression (etablerar Project Input/Site Brief/Generation Package som canonical termer)
- `governance/policies/engine-run.v1.json` (uppdateras med `schema`-pekare)
- `governance/policies/scaffold-contract.v1.json` (uppdateras med `validatedAgainst`-tabell)
- `konversation.txt` (reviewer-input 2026-05-08)
