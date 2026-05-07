# marketing-base

Generell starter för 9 av 14 scaffolds. Inte en Vercel-template - byggs själv via `create-next-app` enligt Vercel Academy-mönstret.

## Status

Tom. Setup väntar på Node.js i operatörens PATH.

## Setup-instruktioner

Kör i `data/starters/`:

```powershell
npx create-next-app@latest marketing-base --typescript --tailwind --app --eslint --use-npm --no-src-dir --import-alias "@/*"
cd marketing-base
npx shadcn@latest init --yes --base-color slate
```

Efter setup, verifiera:

```powershell
npm run build
```

Ska bygga utan fel. Sedan committa hela mappen till `data/starters/marketing-base/`.

## Anpassningar utöver default

När create-next-app + shadcn init är klara, gör följande innan första commit:

1. Ta bort default-innehåll i `app/page.tsx` (Vercel-logotypen, beskrivande text)
2. Ta bort `app/favicon.ico` och `public/`-bilder från Next.js default
3. Skriv om `app/layout.tsx` så `metadata` är minimal (bara `title: ""` och `description: ""`)
4. Sätt `tsconfig.json:compilerOptions.strict: true` om det inte redan är det
5. Lägg till `prettier` + `prettier-plugin-tailwindcss` i devDependencies
6. Skapa minimal `.env.example` (bara kommentarer)
7. Skapa `README.md` (denna fil) med setup-historik

## Vad som inte får finnas

- Hårdkodad copy ("Welcome to Next.js" etc.)
- Hårdkodade färger (allt går via Tailwind/CSS-variabler)
- Auth, databas, betalningar (hör till Integration Dossier)
- Bilder eller fonter utöver shadcn/ui-defaults

## Scaffolds som använder denna bas

- `local-service-business`
- `professional-services`
- `restaurant-hospitality`
- `clinic-healthcare`
- `real-estate`
- `nonprofit-community`
- `event-campaign`
- `app-landing`
- `consultant-expert`
