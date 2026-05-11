# 0018 - B20 commerce-base harmonisering

Datum: 2026-05-11

## Status

Accepterad.

## Kontext

`ecommerce-lite` hade scaffold-innehåll men körde temporärt på
`marketing-base` eftersom `data/starters/commerce-base/` saknade körbar kod.
Operatören godkände att källan hämtas från `vercel/commerce`, under villkor
att upstream-commiten pinnas och att startern inte kräver riktiga
Shopify-nycklar för build.

## Beslut

`commerce-base` importeras från `vercel/commerce` commit
`1df2cf6f6c935f4782eed27351fa18f276917a4d` och harmoniseras till repo-kraven:

- Next.js 16
- TypeScript strict
- Tailwind 4
- shadcn-konfiguration
- npm-lockfil
- ESLint flat config och Prettier
- minimal `.env.example`, ingen `.env`

Shopify får ligga kvar som bytbar adapter under `lib/shopify`, men adaptern
måste vara valfri. Utan Shopify-env ska startern bygga och visa tom live-data,
inte kräva secrets.

När startern bygger grönt mappar `SCAFFOLD_TO_STARTER`:

```text
ecommerce-lite -> commerce-base
```

## Konsekvenser

- B20 stängs som starter-hygienbugg.
- `ecommerce-lite` använder nu sin avsedda commerce-starter.
- Cart, checkout, betalning och live-produktintegration är fortfarande hard
  Dossier-spår och ingår inte som krav i basstartern.
- Real codegenModel-scope ändras inte; det är fortsatt begränsat till
  `marketing-base` tills ett separat codegen-spår breddar stödet.
