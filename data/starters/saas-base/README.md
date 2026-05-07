# saas-base

Specialstarter för `saas-product`-scaffolden. Multi-tenant, subdomain-routing, organisations-/team-modell.

## Status

Tom. Operatör har laddat ned ZIP - väntar på unzip + harmonisering.

## Källa

Fork av [vercel/platforms](https://github.com/vercel/platforms).

## Setup-instruktioner

1. Unzippa det nedladdade arkivet till `data/starters/saas-base/`
2. Ta bort `.git/` från den unzippade mappen (vi vill inte ha nästlad git-historik)
3. Verifiera att `package.json` finns och peka:
   ```powershell
   cd data/starters/saas-base
   npm install
   npm run build
   ```
4. Harmonisera till våra hårda krav (se `data/starters/README.md`)

## Krav på harmonisering

`vercel/platforms` ger oss redan:
- Next.js 15 (uppgradera till 16)
- Tailwind 4
- shadcn/ui
- Multi-tenant-logik
- Redis-koppling

Det vi måste göra:
- Uppgradera till Next.js 16
- Säkerställ TypeScript strict
- Ta bort default-innehåll (logotyper, copy, hårdkodade färger)
- Dokumentera Redis som **förutsättning** för denna starter (till skillnad från övriga starters)
- ADR om att Redis är OK i denna starter eftersom multi-tenant kräver det

## Scaffolds som använder denna bas

- `saas-product`

## Förbjudna ändringar

- Ta bort multi-tenant-logiken (det är hela poängen med denna starter)
- Lägga till Stripe, Clerk eller annan auth-leverantör som bas - de hör till Integration Dossier
