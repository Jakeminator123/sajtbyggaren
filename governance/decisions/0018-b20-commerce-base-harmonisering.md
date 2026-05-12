# ADR 0018 - B20 commerce-base: vendor-only checkpoint

**Status:** accepted
**Datum:** 2026-05-12
**Beroenden:** ADR 0011 (Scaffolds som inherited arbetsmaterial),
ADR 0014 (Sprint 2B planning helper + `SCAFFOLD_TO_STARTER`),
ADR 0017 (Sprint 3B-next: `codegenModel` scope-låst till
`marketing-base`).

## Kontext

`docs/known-issues.md` B20 har sedan 2026-05-08 spårat att
`data/starters/commerce-base/` bara innehöll en `README.md` plus en
oharmoniserad `commerce-main.zip` (operator-local). Den ursprungliga
canonical-mappningen `ecommerce-lite -> commerce-base` är
temporärt-uppmärkt som `ecommerce-lite -> marketing-base (B20: ...)`
tills startern kan köra på riktigt.

Första försöket att stänga B20 (PR #16, två commits) blandade två
oberoende steg i samma PR:

1. **Vendorisera + harmonisera** `data/starters/commerce-base/` från
   `vercel/commerce` upstream (commit `4b4c3af`).
2. **Flippa runtime-mappningen** `ecommerce-lite -> commerce-base` i
   `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER`,
   `data/starters/README.md` mappnings-block, och relaterade tester
   (commit `58c5e63`).

Sanity på branchen visade att vendoreringen i steg 1 är ren och säker
(`npm ci` + `npm run build` + `npm run lint` gröna; alla pytest gröna;
Shopify-anrop skippas gracefully utan env). Steg 2:s mapping-flipp
gjorde däremot Quality Gate `status=degraded` för en ad-hoc
`ecommerce-lite`-generation: route-scan failade med
`/produkter -> app\produkter\page.tsx (saknas)`.

Rotorsaken till failure är inte commerce-base eller mappningen i sig
utan att `scripts/build_site.py` är hårdkodad mot
`local-service-business`-routes (`/tjanster`, `/om-oss`, `/kontakt`)
på fyra nivåer: `_nav_items()`, hardcoded CTA i `render_home`,
`write_pages()`, och avsaknaden av en `render_products()`. Detta är
B13-skulden ("Produktlogik kvar i `scripts/build_site.py`") som
`docs/known-issues.md` har spårat sedan tidigare och som hör hemma i
ett eget refactor-spår eller bredd av `codegenModel`-scope (kräver
egen ADR ovanpå ADR 0017).

## Beslut

PR #16 splittas. Mapping-flippen `58c5e63` reverteras. ADR 0018
omdefinieras till en **vendor-only checkpoint**: den dokumenterar att
commerce-base finns vendoriserad på disk och bygger, men säger
explicit att runtime-mappningen ecommerce-lite -> commerce-base är
pausad tills route-emission-spåret är löst.

Konkret state efter PR #16 (post-revert):

- `data/starters/commerce-base/` är vendoriserad från `vercel/commerce`
  upstream commit `1df2cf6f6c935f4782eed27351fa18f276917a4d`. Den
  uppfyller hårda krav i `data/starters/README.md`: Next.js 16,
  TypeScript strict, Tailwind 4, shadcn/ui-konfiguration, npm-lockfil,
  ESLint flat + Prettier, ingen `.env`.
- `npm ci` + `npm run build` + `npm run lint` gröna inifrån
  `data/starters/commerce-base/`. Shopify-anrop guard:as så builden
  inte kräver Shopify-env.
- `SCAFFOLD_TO_STARTER` i `packages/generation/planning/plan.py` står
  kvar med `ecommerce-lite: marketing-base`.
- `data/starters/README.md` mappnings-block står kvar med raden
  `ecommerce-lite: marketing-base (B20: temporary; canonical target is
  commerce-base after harmonisation)`.
- `tests/test_starter_scaffold_mapping.py::test_b20_temporary_mapping_is_explicit`
  förväntar fortfarande att raden är temporärt-uppmärkt med B20-noten.
- `docs/known-issues.md` B20-post står kvar som **öppen** men noterar
  att Steg 1 (vendor) är landad och Steg 2 (mapping-flipp) väntar på
  B13 / route-emission.

## Vad ADR 0018 INTE beslutar

- ADR 0018 aktiverar **inte** runtime-mappningen ecommerce-lite ->
  commerce-base. Det är PR 16b:s scope.
- ADR 0018 utvidgar **inte** `codegenModel`-scope. ADR 0017:s
  `marketing-base`-only-spik gäller fortfarande.
- ADR 0018 löser **inte** B13:s hårdkodning i `scripts/build_site.py`.
  Den fixen kräver antingen scaffold-driven page-emission-refactor av
  build_site.py eller en utvidgning av `codegenModel`-scope så
  ecommerce-lite går igenom real codegen. Båda kräver egen ADR.

## Beroenden för att aktivera mapping-flippen

PR 16b ska minst leverera:

1. `scripts/build_site.py` (eller en ersättande page-emission-väg)
   som producerar `app/produkter/page.tsx` när
   `scaffoldId=ecommerce-lite`, och som inte längre producerar
   `app/tjanster/page.tsx` för andra scaffolds än
   `local-service-business`.
2. Quality Gate route-scan ok för en ad-hoc `ecommerce-lite` +
   `commerce-base`-build (`/produkter` finns med default export).
3. Flippa raden `ecommerce-lite: marketing-base (B20: ...)` ->
   `ecommerce-lite: commerce-base` i `data/starters/README.md` och
   parallellt i `SCAFFOLD_TO_STARTER`.
4. Regressionstest som lås:er beteendet: ecommerce-lite-build får inte
   emittera `/tjanster` och måste emittera `/produkter`.
5. Stäng B20 i `docs/known-issues.md` med datum + fix-SHA enligt
   review-checklisten som redan står i B20-posten.

## Konsekvenser

- B20 håller status **vendor done, activation blocked by B13 route-
  emission**.
- commerce-base finns nu som referens-starter på disk: kan inspekteras,
  reviewas, lint:as och byggas utan att påverka existerande
  generation-flöden. Det är värdefullt även utan mapping-flipp eftersom
  det fryser den exakta `vercel/commerce`-versionen vi siktar på.
- `marketing-base` fortsätter vara fallback för `ecommerce-lite`. Tills
  PR 16b landar är `(B20: ...)`-noten i mappnings-blocket fortsatt
  rätt signal till reviewer.

## Referenser

- `data/starters/commerce-base/README.md` - starterns egen README med
  vendor-historik.
- `data/starters/README.md` - canonical mappnings-block och hårda krav.
- `docs/known-issues.md` B20 - öppen post med scope-fillista och
  review-checklist.
- `governance/decisions/0017-sprint-3b-next-real-codegen-model.md` -
  `codegenModel` scope-låst till `marketing-base`.
- `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER` -
  runtime-mappningen.
- `tests/test_starter_scaffold_mapping.py` - governance-tester som
  fångar drift mellan canonical mappning, runtime dict, on-disk
  starters, och B20-markeringen.
