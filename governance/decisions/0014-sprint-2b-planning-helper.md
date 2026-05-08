# ADR 0014 - Sprint 2B planning helper as single source of truth

**Status:** accepted  
**Datum:** 2026-05-08  
**Beroenden:** ADR 0009 (Engine Run + Model Roles), ADR 0012 (vocabulary compression), ADR 0013 (schema-lock before Sprint 2B)

## Kontext

Efter ADR 0013 var artefaktkontrakten låsta (`site-brief`, `site-plan`,
`generation-package`) men körningen hade fortfarande två separata planvägar:

1. `scripts/build_site.py` byggde Site Plan/Generation Package från Project Input.
2. `scripts/dev_generate.py` byggde samma artefakter från prompt med en lokal mock.

Detta var buggen b19 i `docs/known-issues.md`: två nästan-parallella pipelines
som kunde driva isär trots schema-låsning.

Samtidigt krävde Sprint 2B att selectorn hade minst två verkliga scaffolds att
välja mellan. Endast `local-service-business` hade innehåll.

## Beslut

### 1) En enda plan-entrypoint

Vi introducerar `packages/generation/planning/produce_site_plan()` som **enda**
kodvägen för att producera:

- `site-plan.json`
- `generation-package.json`

`scripts/build_site.py` och `scripts/dev_generate.py` får endast vara tunna wrappers.
All planlogik (LLM-path, fallback-path, capability-filter, scaffold/variant-val,
starter-map) ska bo i planning-paketet.

### 2) Gemensam fallback-modell för fas 2

`produce_site_plan()` följer samma truth-field-mönster som fas 1:

- `planSource=real` när planningModel körs framgångsrikt
- `planSource=mock-no-key` när `OPENAI_API_KEY` saknas
- `planSource=mock-llm-error` när planningModel-försök failar

Builder-pathen använder dessutom:

- `planSource=pinned` när Project Input explicit pinnar `scaffoldId`/`variantId`
  (operatörens val är auktoritativt och ska inte väljas om av planningModel)

### 3) Capability-map principen är centraliserad

`capability-map.v1.json`-principen *\"empty dossiers list = gap, not feature\"*
verkställs i helpern. Gaps ska synas i `selectedDossiers.rejected[]`, inte
försvinna i script-specifik logik.

### 4) Andra scaffolden i Sprint 2B

`ecommerce-lite` tillkommer med alla obligatoriska scaffold-filer.
I Sprint 2B mappar både `local-service-business` och `ecommerce-lite` till
`marketing-base` via `SCAFFOLD_TO_STARTER`.

`commerce-base` harmonisering (unzip av `vercel/commerce`, Next 16-anpassning,
provider-isolering, Dossier-extraktion) är ett separat efterföljande arbete.

## Konsekvenser

- b19 kan stängas med testbara guards: båda script importerar samma helper och
  legacy plan-funktioner får inte återintroduceras.
- Builder läser `starterId` från planen istället för att hårdkoda `marketing-base`.
- `site-plan.schema.json` måste tillåta `planSource=pinned`.
- Backoffice och docs måste beskriva fas 2 som real-or-mock (inte \"alltid mock\").
- Commerce-startern förblir out-of-scope i Sprint 2B; tracked separat i known issues.

## Vad detta INTE är

- Inte Sprint 3: ingen `codegenModel`, ingen Repair Pipeline, ingen Quality Gate.
- Inte starter-harmonisering för `commerce-base`.
- Inte hard Dossier-import (Stripe/Clerk/Shopify/Supabase m.fl.).
- Inte follow-up-flöde.

## Alternativ vi övervägde

1. **Behålla två planvägar och bara \"hålla dem synkade\" manuellt.**  
   Avvisat: exakt driftmönstret bakom b19.

2. **Låta buildern fortsätta vara ensam källa och göra dev-generate till adapter.**  
   Avvisat: dev-drivern är canonical regression-path för prompt->artefakter och måste
   kunna verifiera samma planlogik.

3. **Skjuta upp planningModel helt och göra helpern mock-only.**  
   Avvisat i Sprint 2B: målet var real planningModel-path med samma fallback-mönster
   som briefModel.

## Verifiering

Sprint 2B anses levererad när:

- `tests/test_planning.py` passerar inklusive b19-guards.
- `scripts/build_site.py` och `scripts/dev_generate.py` båda producerar schema-validerade
  planartefakter via `produce_site_plan()`.
- `governance_validate`, `rules_sync --check`, `check_term_coverage --strict`,
  `pytest`, `ruff` är gröna.
