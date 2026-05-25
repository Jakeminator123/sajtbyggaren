# ADR 0031 — section-treatments som additiv directive (Phase 3 schema-bump)

**Status:** Accepted
**Datum:** 2026-05-25
**Beroenden:** ADR 0011 (Scaffolds som inherited working material), ADR 0013 (Schema locking), ADR 0027 (semantic follow-up merge — additiv directive-precedent), GAP-section-design-treatments.

## Kontext

Phase 1 + Phase 2 av section design treatments levererade visuell unikhet
inom samma section-id genom variant-default-mappningar i scripts/build_site.py
(`_SECTION_TREATMENTS_BY_VARIANT` + `_treatment_for_section`). Idag finns 14
treatments fördelade över 5 sektioner (selected-work-preview, treatment-list,
practice-grid, expertise-areas, service-list).

Resolve-ordningen i Phase 1+2 är två-tier:

1. variant-default (om varianten finns i `_SECTION_TREATMENTS_BY_VARIANT`)
2. section-default (`default`-arg till `_treatment_for_section`)

Phase 3 (operator-pin + LLM-pick) lägger till en tredje tier framför
variant-default: en explicit pin från operatören eller från LLM-planen.
Den pinnen måste landa någonstans i Project Input-shape så att both
`scripts/build_site.py` och `packages/generation/{brief,planning}` ser
samma sanning.

Tre lokationsalternativ stod på bordet:

- **A — Nytt top-level-fält `sectionTreatments`.** Mest synligt i UI och
  prompt-template; samtidigt mest invasivt mot existerande Project Input-
  konsumenter och kontrakt-bryter `produce_site_plan`s helper-signaturer.
- **B — Per-variant-konfiguration i `data/variants/<variantId>/`.** Skulle
  återanvända en existerande source-of-truth, men variants är dela-bara
  artefakter i `data/`, inte operator-input. En operator-pin är per-build,
  inte per-variant — fel data-domain.
- **C — Additiv directive under `directives.sectionTreatments`.** Samma
  precedent som `directives.layoutHint` (Wizardens hero-layout-override)
  och samma mönster som ADR 0027 introducerade för semantic follow-up
  merge: directives är tänkta som per-build operator-overrides ovanpå
  scaffold/variant-baseline.

## Beslut

`directives.sectionTreatments` är operator-pin-bäraren för Phase 3.

1. `governance/schemas/project-input.schema.json` får
   `directives.sectionTreatments` som ny additiv property med
   `additionalProperties: false`.
2. Property-schemat är en sluten enum-tabell per section-id. Tillåtna
   treatment-IDs speglar exakt vad som registrerats i Phase 1+2-tabellen
   `_SECTION_TREATMENTS_BY_VARIANT` plus varje sections egen default:
   - `selected-work-preview`: `editorial-stack` | `asymmetric-grid` | `marquee-row`
   - `treatment-list`: `minimal-rows` | `split-cards` | `numbered-stack`
   - `practice-grid`: `dense-grid` | `tabular` | `grouped`
   - `expertise-areas`: `numbered-2col` | `tag-cluster`
   - `service-list`: `card-grid` | `alternating-rows` | `icon-strip` | `tabular`
3. Tomt objekt eller saknad property faller tillbaka till variant- och
   section-defaults. Existerande examples slipper schema-bump i samma commit.
4. `_treatment_for_section` får i Phase 3-implementation en ny
   resolve-ordning operator-pin > variant-default > section-default. Helper-
   signaturen utökas med en `operator_treatments: dict[str, str] | None`-
   parameter som tråds genom `_call_section_renderer` precis som
   `variant_id` redan är.
5. `briefModel`-prompten lär sig nya fältet via en `SECTION_TREATMENTS_HINT`-
   block som listar tillgängliga treatments per scaffold/variant. Mock-
   fallback returnerar tom dict så non-key-pathen aldrig kraschar och
   fortsatt matchar pre-Phase-3-snapshots.
6. `planningModel`-prompten får använda `directives.sectionTreatments` som
   hint vid section-ordering/visibility men får inte mutera fältet (Phase 3
   räknar med att operatören är auktoritativ; LLM-pick är en separat tier
   som beslutas i Phase 4).
7. UI-pinnar mappar wizard-svar till `directives.sectionTreatments`-shape:n
   i `apps/viewser/components/discovery-wizard/wizard-payload.ts`. UI:t
   speglar enum-tabellen i `treatment-options.ts` (ny fil).

## Konsekvenser

Positiva:

- Backwards-compatible. Inga existerande Project Input-snapshots invalideras
  eftersom `directives.sectionTreatments` är optional och tomt-state-
  beteendet matchar pre-Phase-3 exakt.
- Schema-validatorn fångar typos innan bygget startar — operatören kan inte
  pinna `tabbular` istället för `tabular` utan att schema-validate misslyckas.
- En enda källa-av-sanning för UI-state, prompt-template och Python-
  resolution. UI:t läser samma directives som builder.
- Phase 4 (LLM-pick som separat tier) får en ren utbyggnadspunkt: en
  parallell `directives.llmSectionTreatments` kan introduceras utan att
  röra operator-pin-tier:n.

Negativa:

- Enum-listan i schemat duplicerar treatment-katalogen i
  `_SECTION_TREATMENTS_BY_VARIANT`. När en ny treatment registreras måste
  båda källorna uppdateras i samma commit. Test-fil
  `tests/test_project_input_schema.py` får ett guard-test som korssäkrar
  enum-listan mot Python-tabellen så driften syns på CI.
- Närmare termen "treatment" är inte registrerad i naming-dictionary.
  Beslut: håll det som lokal designterm tills V2 där sectionTreatments
  blir en egen domän med egen ADR-bump till `naming-dictionary.v1.json`.

## Utanför scope

- LLM-pick som separat tier (Phase 4).
- Treatment-katalog-utvidgning bortom Phase 1+2:s 14 treatments.
- Versionerade treatments (om en treatment behöver ändra layout senare).
- Operator-pin per scaffold-route eller per-page.
- UI-design för operator-pin på dossier-nivå (dossier-section-treatments är
  inte i scope; pin är på scaffold-section-id-nivån).
