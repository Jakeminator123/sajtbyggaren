# commerce-base

Specialstarter för `ecommerce-lite`-scaffolden. Hög-prestanda e-handel med Server Components.

## Status

Tom. Operatör har laddat ned ZIP - väntar på unzip + harmonisering.

## Källa

Fork av [vercel/commerce](https://github.com/vercel/commerce).

## Setup-instruktioner

1. Unzippa det nedladdade arkivet till `data/starters/commerce-base/`
2. Ta bort `.git/` från den unzippade mappen
3. Verifiera build:
   ```powershell
   cd data/starters/commerce-base
   npm install
   npm run build
   ```
4. Harmonisera (se `data/starters/README.md`)

## Krav på harmonisering

`vercel/commerce` ger oss:
- Next.js (vilken version operatör behöver verifiera vid unzip)
- Tailwind
- App Router + RSC
- Shopify-adapter i `lib/shopify`

Det vi måste göra:
- Uppgradera till Next.js 16 om behövs
- Lägg till shadcn/ui via `npx shadcn@latest init` (templaten levereras inte med shadcn enligt Vercel-listningen)
- Säkerställ TypeScript strict
- Ta bort hårdkodad copy
- Behåll `lib/shopify` men dokumentera den som **bytbar** via en hard Dossier (kan ersättas med Medusa, BigCommerce, egen JSON, Airtable)

## Adaptermönster

Codegen ska kunna byta provider via `lib/<provider>.ts` med samma interface. Standard: Shopify. Kan bytas via hard Dossiers som `commerce-shopify`, `commerce-medusa`, etc.

## Scaffolds som använder denna bas

- `ecommerce-lite`

## Förbjudna ändringar

- Ta bort `lib/<provider>` adapter-laget (vi vill kunna byta backend)
- Hårdkoda Shopify-anrop utanför `lib/shopify`
