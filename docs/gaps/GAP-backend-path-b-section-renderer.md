# GAP-backend-path-b-section-renderer

```yaml
id: GAP-backend-path-b-section-renderer
type: Gap/Runtime
owner: jakob
title: Section-driven renderer + scaffold runtime expansion (Path B)
whyNow: |
  Idag är 12 av 14 designade scaffolds blockerade på rendering. Bara
  `local-service-business` + `ecommerce-lite` har route-renderers i
  `scripts/build_site.py:write_pages`. Resultatet: 6 av 8 wizard-families
  faller tillbaka till samma LSB-scaffold med samma 4 routes och samma
  section-shape — operatören upplever (med rätta) att "alla scaffolds
  ser likadana ut". Path B löser detta strukturellt: en section-driven
  dispatcher kostar ~20–26h en gång och låser sedan upp varje framtida
  scaffold för ~30 min styck istället för ~6–8h.
paths:
  - scripts/build_site.py
  - packages/generation/discovery/resolve.py
  - packages/generation/planning/plan.py
  - packages/generation/orchestration/scaffolds/restaurant-hospitality/**
  - tests/test_builder_*.py
  - tests/test_discovery_resolver.py
  - tests/test_starter_scaffold_mapping.py
  - tests/test_builder_route_emission.py
  - examples/restaurant-bistro.project-input.json
doNotTouch:
  - apps/viewser/**
  - governance/policies/scaffold-contract.v1.json
acceptanceCriteria:
  - "scripts/build_site.py byter ut per-route-id if/elif-kedjan i write_pages mot en section-driven dispatcher (_SECTION_RENDERERS + render_route_generic)."
  - "Befintliga LSB- och commerce-snapshots är byte-identiska före/efter refaktoreringen (snapshot-diff = 0 bytes)."
  - "_RUNTIME_SCAFFOLD_HINTS i resolve.py utökas med restaurant-hospitality (warm-bistro, marketing-base)."
  - "SCAFFOLD_TO_STARTER och _DEFAULT_VARIANT_BY_SCAFFOLD är redan utökade i PR #68 — verifiera att dessa fortfarande är konsistenta."
  - "python scripts/build_site.py --dossier examples/restaurant-bistro.project-input.json producerar /meny + /bokning-routes utan SystemExit."
  - "Nya section-renderers för restaurang: menu-preview, menu-list, menu-grouping, dietary-key, booking-cta, booking-form-or-embed, opening-hours, atmosphere-gallery, address-and-map, chef-story."
  - "Hero-style fallback-chain (_HERO_STYLE_BY_VARIANT → _HERO_STYLE_BY_TONE → 'gradient') verifierat för warm-bistro, nordic-fine-dining, casual-cafe, midnight-bar via test."
  - "Ny test: tests/test_builder_route_emission.py::test_restaurant_emits_menu_and_booking_routes."
  - "Ny test: tests/test_builder_sections_dispatch.py som verifierar att en okänd section-id ger SystemExit med pedagogiskt felmeddelande, inte tyst skipper."
  - "test_discovery_resolver.py::test_scaffold_hint_restaurant_hospitality_planned_ignored vänder från 'ignored' till 'honored'."
  - "Backward-compat shims: render_home/render_services/render_about/render_contact/render_products behålls och delegerar internt till render_route_generic så ingen extern test bryter."
checks:
  - python scripts/sprintvakt_check.py
  - python scripts/governance_validate.py
  - python scripts/rules_sync.py --check
  - python scripts/check_term_coverage.py --strict
  - python -m ruff check .
  - python -m pytest tests/ -q -x
  - python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build  # snapshot-bevarande
  - python scripts/build_site.py --dossier examples/restaurant-bistro.project-input.json --skip-build  # ny end-to-end
collisionRisk: red
reviewer: christopher
status: queued
createdAt: 2026-05-25T04:50:00Z
updatedAt: 2026-05-25T04:50:00Z
notes:
  - "Detalj-design och step-by-step-migration finns i docs/scaffold-runtime-extension-needed.md (förkonverterade utkastet)."
  - "Effort: 20-26h (extraktion 8-12h, registry 1h, dispatcher 2h, shims 1h, restaurant sections 4-6h, hero 15min, whitelist 15min, tests 4h)."
  - "Efter Path B kostar varje framtida scaffold ~30 min (whitelist + ev. nya section-types) i stället för 6-8h."
  - "Christopher kan generera fixture-filer (examples/restaurant-bistro.project-input.json, examples/restaurant-cafe.project-input.json) en gång scaffold-shape är låst."
  - "Strategiskt val innan start: vilken ordning ska de 12 inaktiva scaffolds aktiveras? restaurant-hospitality först (existerande variants + dossiers redo) — sedan clinic-healthcare / professional-services / real-estate parallellt eftersom de delar marketing-base-starter."
```

## Strategiskt val: aktiveringsordning

När Path B-refaktoreringen är klar kan scaffolds aktiveras parallellt. Förslag på prioritet baserat på (a) hur ofta operatörer faktiskt kommer hit (b) hur färdig deklarationen redan är:

| Prio | Scaffold | Status idag | Effort efter Path B |
|---|---|---|---|
| 1 | `restaurant-hospitality` | sections.json + 4 variants + 5 dossiers redo | ~30 min |
| 2 | `clinic-healthcare` | inget | ~2-3h (sections.json + 1-2 variants) |
| 3 | `professional-services` | inget | ~2-3h |
| 4 | `real-estate` | inget | ~3-4h (objekts-listing kräver ny dossier) |
| 5 | `agency-studio` | inget | ~2-3h (kan återanvända portfolio-dossiers) |
| 6 | `consultant-expert` | inget | ~2h |
| 7 | `nonprofit-community` | inget | ~2h |
| 8 | `event-campaign` | inget | ~2h |
| 9 | `app-landing` | inget | ~1h (smal sajt) |
| 10 | `course-education` | docs-base krävs | ~6h (nytt starter-paket) |
| 11 | `portfolio-creator` | portfolio-base krävs | ~6h (nytt starter-paket) |
| 12 | `agency-studio` (2) | portfolio-base krävs | ~3h |
| 13 | `saas-product` | saas-base krävs | ~8h (nytt starter-paket) |

Dessa estimat förutsätter att Path B-dispatchern landar först. Total för att aktivera alla 12 (efter Path B): ~40-50h, fördelat över ~6-8 PRs.

## Källa

`docs/scaffold-runtime-extension-needed.md` har den fullständiga tekniska designen (registry-shape, render_route_generic-pseudokod, migration-order, acceptance-gates). Detta GAP är den formella sprintvakt-bokföringen av samma arbete.
