# ADR 0020 - commerce-base: lägg till lucide-react som runtime-dep

**Status:** accepted
**Datum:** 2026-05-13
**Beroenden:** ADR 0011 (Scaffolds som inherited arbetsmaterial),
ADR 0018 (B20 commerce-base vendor-only checkpoint),
ADR 0019 (B20 step 2 mapping-aktivering).

## Kontext

ADR 0019 aktiverade `ecommerce-lite -> commerce-base`-routingen i
`SCAFFOLD_TO_STARTER`. Aktiveringen gick grön på
`--skip-build`-nivå (Quality Gate route-scan ok, `app/produkter/
page.tsx` emitteras), men full `npm run build` mot
`.generated/atelje-bird/` fallerade direkt efter merge med:

```
Module not found: Can't resolve 'lucide-react'
```

i fem genererade filer (`app/page.tsx`, `app/produkter/page.tsx`,
`app/om-oss/page.tsx`, `app/kontakt/page.tsx`, `app/layout.tsx`).
Roten: `scripts/build_site.py:write_pages`-renderers
(`render_home`, `render_about`, `render_contact`, `render_layout`,
`render_products`) hardcodar `import { ... } from "lucide-react"`.
`marketing-base/package.json` har `lucide-react` som dep så
konflikten har inte synts förut. `commerce-base/package.json`
deklarerade bara `@heroicons/react`.

Operatör väljer mellan två fix-vägar (dokumenterade i `docs/known-
issues.md` "Known follow-up" på den stängda B20-posten):

- **A: Lägg `lucide-react` i `commerce-base/package.json`.**
  Snabbast. Starter-doktrinen i `data/starters/README.md` rad 105
  säger att nya deps i en starter kräver operatörsgodkännande.
- **B: Gör `write_pages` icon-bibliotek-agnostisk per starter.**
  Bredare refactor av deterministic-v1 codegen, troligen kräver
  starter-config-fil eller inline-SVG-strategy. Egen sprint.

## Beslut

Väg A. `data/starters/commerce-base/package.json:dependencies`
får ett nytt entry `"lucide-react": "^1.14.0"` (samma version
som `marketing-base` använder, så de två starterna delar exakt
samma lucide-version och `write_pages` kan generera identiska
imports oavsett starter). `data/starters/commerce-base/
package-lock.json` uppdateras via `npm install` så lockfilen
spårar den exakta installerade versionen.

Operator-godkännandet för dep-tillägget givet av operatör 2026-05-13
i sessionen som mergade PR #20 (B20 step 2). `.cursor/BUGBOT.md`
"Do not touch data/starters/commerce-base/ ... without a
referenced ADR in the PR description"-regeln uppfylls genom denna
ADR.

## Vad ADR 0020 INTE beslutar

- ADR 0020 löser **inte** den underliggande arkitekturskulden:
  `scripts/build_site.py:write_pages` hardcodar fortfarande
  lucide-imports. Om en framtida starter inte använder lucide
  uppstår samma konflikt igen. Den bredare refactorn (väg B)
  kvarstår som öppen architecturpost; spåras under B13a-
  arkitekturflytten eller ett separat icon-strategy-spår när
  operatör prioriterar.
- ADR 0020 utvidgar **inte** scope för vad commerce-base får
  innehålla utöver lucide-react. Övriga "Förbjudna ändringar"
  i `data/starters/commerce-base/README.md` står kvar (inga
  riktiga `.env`-filer, ingen krav på auth/db/payment/CMS/Shopify-
  env för build, inga hårdkodade Shopify-anrop utanför
  `lib/shopify`, ingen kundspecifik copy).
- ADR 0020 löser **inte** de pre-existing hardcoded
  `/kontakt`-CTAs i `render_home/render_services/render_layout`
  som B13b explicit lämnade orörda (separat teknisk skuld).

## Konsekvenser

- Full `npm run build` mot `.generated/atelje-bird/` (eller
  någon annan ecommerce-lite-genererad sajt) går nu grönt.
  Verifierat 2026-05-13: 11/11 statiska sidor genereras inkl
  `/produkter`, plus commerce-base:s egna dynamiska routes
  (`/product/[handle]`, `/search`, `/search/[collection]`,
  `/[page]`, `/api/revalidate`) renderas på begäran.
- `cd data/starters/commerce-base && npm run build` förblir
  grönt med den nya dep:en (verifierat: 13 routes prerendered
  inkl Shopify-skip-loggrad utan att kräva env).
- `node_modules`-storlek på en `.generated/<ecommerce-lite-site>/`
  ökar med 1 paket (`lucide-react@1.14.0`, ~liten ikon-bib).
  Inga övriga dep-effekter.
- B20:s "Known follow-up" i `docs/known-issues.md` flyttas till
  "Stängda - regression-test säkrar fixet" med denna PR:s
  squash-merge-SHA.

## Referenser

- `governance/decisions/0019-b20-step-2-mapping-activation.md` -
  aktiveringen som gjorde lucide-konflikten synlig.
- `governance/decisions/0018-b20-commerce-base-harmonisering.md` -
  vendor-only checkpoint; commerce-base:s grundläggande hårda krav.
- `data/starters/commerce-base/README.md` - starterns
  "Förbjudna ändringar"-lista som denna ADR inte rör.
- `data/starters/marketing-base/package.json` - referens-versionen
  av `lucide-react` som ADR 0020 matchar.
- `scripts/build_site.py` - där hardcoded `lucide-react`-importerna
  bor; arkitekturskulden för icon-bibliotek-agnostisk codegen
  väntar på separat sprint.
- `.cursor/BUGBOT.md` "Starter-specific rules" - regeln som
  kräver ADR-referens vid commerce-base-ändring.
