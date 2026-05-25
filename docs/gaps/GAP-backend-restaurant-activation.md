# GAP-backend-restaurant-activation

```yaml
id: GAP-backend-restaurant-activation
type: Gap/Runtime
owner: jakob
title: Aktivera restaurant-hospitality scaffold runtime end-to-end (Path A)
whyNow: |
  Scout 2026-05-25 (composer-2.5-fast) identifierade strukturell
  homogenitet som den kritiska bristen för "fantastiska sajter":
  6 av 8 wizard-familjer pekar mot local-service-business inklusive
  Restaurang/Café — som borde peka mot restaurant-hospitality men gör
  det inte (wizard-constants.ts:140 sätter scaffoldHint till
  "local-service-business").

  Path A-renderers finns redan på plats:
    - render_menu i scripts/build_site.py
    - render_booking i scripts/build_site.py
    - restaurant-hospitality finns i SCAFFOLD_TO_STARTER (plan.py:83)
    - restaurant-hospitality har scaffold-spec på disk

  Tre filer behöver ändras för att aktivera end-to-end:
    1. _RUNTIME_SCAFFOLD_HINTS i packages/generation/discovery/resolve.py
       — whitelist restaurant-hospitality
    2. BUSINESS_FAMILIES[restaurant].scaffoldHint i wizard-constants.ts
       — byt från "local-service-business" till "restaurant-hospitality"
    3. _HERO_STYLE_BY_VARIANT i scripts/build_site.py — lägg till
       hero-styles för warm-bistro, nordic-fine-dining, casual-cafe,
       midnight-bar (eller motsvarande variant-id som finns på disk
       för restaurant-hospitality)

  Detta är medvetet en SMAL Path A-aktivering som validerar
  scaffold-konceptet INNAN Path B (section-driven renderer, ~20-26h)
  byggs. När Path B landar kan vi aktivera de övriga 11 inaktiva
  scaffolds i samma rytm.

  Operatör-godkänd scope-leak: Christopher utför arbetet på
  christopher-ui (operator-citat 2026-05-25 04:24: "mindre ändringar
  i Backend behövs … vi jobbar egentligen båda backend och frontend").
  Owner=jakob behålls i workboard så Sprintvakt-lane-policyn passerar;
  arbetet bär [scope-leak] Approved by operator-tag i commit. Samma
  precedent som GAP-backend-build-trace-endpoint i commit 74a355b.
paths:
  - packages/generation/discovery/resolve.py
  - apps/viewser/components/discovery-wizard/wizard-constants.ts
  - scripts/build_site.py
  - tests/test_discovery_resolver.py
  - tests/test_starter_scaffold_mapping.py
  - tests/test_builder_restaurant_routes.py
  - examples/restaurant-bistro.project-input.json
doNotTouch:
  - apps/viewser/components/builder/**
  - apps/viewser/components/discovery-wizard/steps/**
  - packages/generation/orchestration/scaffolds/local-service-business/**
  - packages/generation/orchestration/scaffolds/ecommerce-lite/**
  - governance/policies/scaffold-contract.v1.json
  - data/variants/local-service-business/**
  - data/variants/ecommerce-lite/**
acceptanceCriteria:
  - "_RUNTIME_SCAFFOLD_HINTS i resolve.py innehåller restaurant-hospitality med rätt default-variant."
  - "BUSINESS_FAMILIES[restaurant].scaffoldHint i wizard-constants.ts är 'restaurant-hospitality'."
  - "_HERO_STYLE_BY_VARIANT i build_site.py innehåller styles för alla restaurant-hospitality-varianter som finns på disk."
  - "python scripts/build_site.py --dossier examples/restaurant-bistro.project-input.json --skip-build returnerar exit 0."
  - "Genererad sajt har /meny och /bokning som routes (inte LSB-routes /tjanster)."
  - "Nytt test i tests/test_discovery_resolver.py: restaurant-wizard-payload ger scaffoldId='restaurant-hospitality' (inte fallback)."
  - "Nytt test i tests/test_builder_restaurant_routes.py verifierar att /meny + /bokning emiteras för restaurant-hospitality."
  - "Befintliga LSB- och ecommerce-tester passerar oförändrade — ingen regression."
  - "Inga ändringar i Path B-skopet (write_pages dispatch är fortfarande hårdkodad route-renderers — det blir nästa GAP)."
checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/rules_sync.py --check
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q -x
  - cd apps/viewser && npx tsc --noEmit
  - cd apps/viewser && npm run lint
note: |
  Effort: 6-8h. Quick-win från scout 2026-05-25. Beslut: Path A nu (denna
  GAP), Path B nästa sprint (GAP-backend-path-b-section-renderer).
  Section design-treatments väntar tills Path B är klar.
```
