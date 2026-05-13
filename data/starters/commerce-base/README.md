# commerce-base

Specialstarter för `ecommerce-lite`-scaffolden. Basen är importerad från
`vercel/commerce` och harmoniserad för Sajtbyggaren.

## Status

Byggbar basstarter. Verifieras med npm och ska kunna bygga utan riktiga
Shopify-nycklar.

## Källa

Upstream: [vercel/commerce](https://github.com/vercel/commerce)

Pinned commit: `1df2cf6f6c935f4782eed27351fa18f276917a4d`

Upstream-runtime-branding rensad: WelcomeToast-komponenten, Vercel
Deploy-knappen i footern, "View the source"-länken till
`github.com/vercel/commerce` och "Created by Vercel"-noten är borttagna
så startern är ett neutralt basprojekt. Akademisk attribution till
upstream lever kvar i denna README och i `license.md` enligt
upstream-licensens villkor.

## Kommandon

```powershell
cd data/starters/commerce-base
npm install
npm run build
npm run lint
```

## Shopify-adapter

Shopify finns kvar som bytbar adapter under `lib/shopify`. Den är valfri:
tomma Shopify-värden i `.env.example` ska fortfarande ge en byggbar bas.
När adaptern aktiveras måste `SHOPIFY_STORE_DOMAIN` och
`SHOPIFY_STOREFRONT_ACCESS_TOKEN` sättas tillsammans.

Auth, databas, betalning, checkout och CMS-koppling ingår inte som krav i
basen. Sådana integrationer ska komma via hard Dossiers.

## Runtime-deps utöver upstream

`lucide-react` (matchar `marketing-base`-versionen) lades till 2026-05-13
per [ADR 0020](../../../governance/decisions/0020-commerce-base-lucide-react.md)
för att stödja `scripts/build_site.py:write_pages`-renderers som
hardcodar `import from "lucide-react"`. Den underliggande
arkitekturskulden (icon-bibliotek-agnostisk codegen) kvarstår som
öppen architecturpost; tilläggsbeslutet är dokumenterat i ADR 0020:s
"INTE beslutar"-sektion.

## Scaffolds som använder denna bas

- `ecommerce-lite`

## Förbjudna ändringar

- Lägg inte riktiga `.env`-filer i startern.
- Kräv inte auth, databas, betalning, CMS eller Shopify-env för build.
- Hårdkoda inte Shopify-anrop utanför adapterlagret under `lib/shopify`.
- Gör inte denna bas till en färdig kundsajt med kundspecifik copy.
