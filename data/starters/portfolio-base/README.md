# portfolio-base

Specialstarter för `portfolio-creator` och `agency-studio`-scaffolds.
Basen är MDX-baserad och behåller SEO-mönster, RSS, dynamiska OG-bilder
och Geist-fonten från upstream.

## Status

Byggbar basstarter. Vendoriserad och harmoniserad 2026-05-14 från
`vercel/examples` undermapp `solutions/blog`.

## Källa

Upstream: [vercel/examples → solutions/blog](https://github.com/vercel/examples/tree/main/solutions/blog)

Pinned commit: `72aaac1ba427596689d1a149c3d6c0a6351d14e9`

Endast `solutions/blog`-undermappen är relevant. Full-repot ska inte
kopieras in i denna starter.

Upstream-licens: MIT, bevarad i `license.md`.

## Kommandon

```powershell
cd data/starters/portfolio-base
npm install
npm run build
npm run lint
npm run prettier:check
```

## Harmonisering från upstream

Det här är kvar från `solutions/blog`:

- MDX-rendering via `next-mdx-remote`
- SEO-bas med sitemap, robots och JSON-LD för case studies
- RSS-flöde
- dynamisk OG-route
- syntax highlighting via `sugar-high`
- Tailwind 4
- Geist-fonten

Det här är ändrat för Sajtbyggaren:

- Next.js och React harmoniserade med övriga starters.
- TypeScript strict aktiverat.
- shadcn/ui-bas tillagd med `components.json`, `lib/utils.ts` och
  `components/ui/button.tsx`.
- npm används som enda paketmanager och `package-lock.json` committas.
- ESLint flat config och Prettier tillagda.
- `.env.example` finns; riktiga `.env`-filer ignoreras.
- Vercel analytics och speed insights är borttagna.
- Upstream default-copy, deploy/source-länkar och default-blogginlägg är
  borttagna.
- Route-strukturen är anpassad för scaffold-injektion:
  `/portfolio`, `/case-studies`, `/case-studies/[slug]` och `/about`.
- Case study-MDX läses från `content/case-studies/`. Basen committar inga
  defaultposter där.

## Scaffolds som använder denna bas

- `portfolio-creator`
- `agency-studio`

## Förbjudna ändringar

- Ta inte bort MDX-stödet; det är starterns case study-yta.
- Ta inte bort SEO-baseline: sitemap, robots, JSON-LD, RSS och OG-route.
- Lägg inte till auth, databas, betalning, CMS eller analytics i basen.
- Lägg inte in riktiga `.env`-filer.
- Lägg inte tillbaka default-blogginlägg eller kundspecifik copy.
