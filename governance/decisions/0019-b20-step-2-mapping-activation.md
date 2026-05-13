# ADR 0019 - B20 step 2: aktivera ecommerce-lite -> commerce-base mapping

**Status:** accepted
**Datum:** 2026-05-13
**Beroenden:** ADR 0011 (Scaffolds som inherited arbetsmaterial),
ADR 0014 (Sprint 2B planning helper + `SCAFFOLD_TO_STARTER`),
ADR 0017 (Sprint 3B-next: `codegenModel` scope-låst till
`marketing-base`), ADR 0018 (B20 commerce-base vendor-only
checkpoint).

## Kontext

ADR 0018 satte commerce-base som vendor-only checkpoint och var
explicit om vad den **inte** beslutade: "ADR 0018 aktiverar **inte**
runtime-mappningen ecommerce-lite -> commerce-base. Det är PR 16b:s
scope" och "kräver egen ADR". `.cursor/BUGBOT.md` formaliserar
samma princip i sin "Mapping and routing risk"-sektion: "Any change
to this dict needs an ADR in the same PR."

ADR 0018 listar fem konkreta beroenden för att aktiveringen ska
vara säker (vendor done, scaffold-driven page-emission, route-scan
ok för en ad-hoc ecommerce-lite-build, parallell flipp av README +
SCAFFOLD_TO_STARTER, regressionstest, B20 stängs i known-issues).
Sedan ADR 0018 har dessa beroenden uppfyllts:

- **Vendor (Beroende 1 från ADR 0018:s Beroenden-lista är implicit;
  det här är extra-läget därutöver):** `data/starters/commerce-base/`
  vendoriserad i PR #16 commit `4b4c3af` från `vercel/commerce`
  upstream `1df2cf6f6c935f4782eed27351fa18f276917a4d`. Hårda krav
  uppfyllda; bygger lokalt utan Shopify-env (ADR 0018 beslutsdel).
- **Scaffold-driven page-emission (Beroende 1):**
  `scripts/build_site.py:write_pages` läser nu scaffoldens
  `routes.json` och dispatchar per route id (B13b, mergad i
  `fda1464` via PR #19). Ny `render_products` för `/produkter`,
  scaffold-driven nav via `_nav_items_from_scaffold`, och
  scaffold-driven contact CTA via `_pick_contact_route`.
- **Route-scan ok för ecommerce-lite-build (Beroende 2):**
  `examples/atelje-bird.project-input.json` ecommerce-lite-fixturen
  ger Quality Gate route-scan `status=ok` med `/produkter`-emission.
- **Regressionstest (Beroende 4):** `tests/test_builder_route_emission.py`
  (21 tester, mergad i PR #19) inklusive
  `test_ecommerce_lite_fixture_writes_produkter_and_passes_route_scan`
  låser att `app/produkter/page.tsx` emitteras och
  `app/tjanster/page.tsx` INTE emitteras för ecommerce-lite.

ADR 0018:s Beroenden 3 och 5 (parallell flipp av mappnings-rad +
runtime dict, och stängning av B20 i known-issues.md) är denna
PR:s scope och beslutas härmed.

## Beslut

`packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER`
ändras från `{"local-service-business": "marketing-base",
"ecommerce-lite": "marketing-base"}` till
`{"local-service-business": "marketing-base",
"ecommerce-lite": "commerce-base"}`. Den canonical mappnings-raden
i `data/starters/README.md`s `scaffold-starter-mapping`-block
ändras parallellt från `ecommerce-lite: marketing-base
(B20: temporary; canonical target is commerce-base after
harmonisation)` till `ecommerce-lite: commerce-base` (utan note).

`tests/test_starter_scaffold_mapping.py::test_b20_temporary_mapping_is_explicit`
behåller sitt skydd men auto-skippar positivt när starter är
`commerce-base` (testet är skrivet att bara kräva B20-marker när
mappningen ÄR temporär). Övriga tester i samma fil låser drift
mellan canonical mapping, runtime dict, on-disk starters och
Starter Registry.

## Vad ADR 0019 INTE beslutar

- ADR 0019 utvidgar **inte** `_REAL_CODEGEN_STARTERS` i
  `packages/generation/codegen/codegen.py`. ADR 0017:s
  `marketing-base`-only-spik gäller fortfarande; ecommerce-lite
  kommer köra genom `source=deterministic-v1` codegen tills en
  separat ADR-utökning ovanpå 0017 vidgar real-codegen-scope.
- ADR 0019 löser **inte** de pre-existing hardcoded
  `/kontakt`-CTAs i `render_home/render_services/render_layout`
  som B13b explicit lämnade orörda (lever fortsatt som teknisk
  skuld utan eget B-ID).
- ADR 0019 löser **inte** dependency-konflikten mellan
  `scripts/build_site.py:write_pages` (hardcodar `lucide-react`-
  imports per renderer) och `commerce-base/package.json` (har bara
  `@heroicons/react`). Den konflikten är synlig först när full
  `npm run build` körs på en `.generated/<ecommerce-lite-site>/`
  och påverkar inte `--skip-build`-acceptansen som
  `docs/current-focus.md` "Next action" steg 5 definierar för B20
  step 2. Fix-vägen kräver operatörsbeslut (lägg `lucide-react` i
  `commerce-base/package.json` med lockfil-uppdatering, eller gör
  `write_pages` icon-bibliotek-agnostisk per starter) och får eget
  B-ID när vägen är vald.

## Konsekvenser

- B20 stänger som "vendor done + mapping activated"; spåret flyttas
  till "Stängda - regression-test säkrar fixet" i
  `docs/known-issues.md` med squash-merge-SHA i denna PR:s
  post-merge mainline-steward-commit.
- `commerce-base` blir produktiv runtime-target för `ecommerce-lite`-
  scaffolden med `source=deterministic-v1` codegen. Real
  codegenModel-scope är fortsatt scope-låst per ADR 0017.
- Test-suiten blir 381 passed + 3 skipped (env-gated), samma
  baseline som pre-PR.
- En ny dependency-konflikt (lucide-react vs @heroicons/react)
  blir synlig vid full `npm run build` och spåras separat när
  operatör väljer fix-väg (se "Vad ADR 0019 INTE beslutar").

## Referenser

- `governance/decisions/0018-b20-commerce-base-harmonisering.md` -
  vendor-only checkpoint och dess Beroenden-lista som denna ADR
  uppfyller.
- `governance/decisions/0017-sprint-3b-next-real-codegen-model.md` -
  varför `_REAL_CODEGEN_STARTERS` förblir `{"marketing-base"}`.
- `governance/decisions/0014-sprint-2b-planning-helper.md` -
  ursprunget för `SCAFFOLD_TO_STARTER`-dict:en.
- `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER` -
  runtime-mappningen som ADR 0019 ändrar.
- `data/starters/README.md` `scaffold-starter-mapping`-block -
  canonical mappningen som ADR 0019 ändrar parallellt.
- `tests/test_starter_scaffold_mapping.py` - governance-tester
  som fångar drift mellan canonical mapping, runtime dict,
  on-disk starters och Starter Registry.
- `tests/test_builder_route_emission.py` - regressionstesterna
  som låser scaffold-driven route emission (B13b, PR #19).
- `examples/atelje-bird.project-input.json` - ecommerce-lite-
  fixturen som verifierar att aktiveringen producerar
  `/produkter` och inte `/tjanster`.
- `.cursor/BUGBOT.md` "Mapping and routing risk" - regeln som
  kräver ADR vid varje `SCAFFOLD_TO_STARTER`-ändring.
