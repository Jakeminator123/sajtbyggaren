# portfolio-base

Specialstarter för `portfolio-creator` och `agency-studio`-scaffolds. MDX-baserad med SEO, RSS, dynamiska OG-bilder.

## Status

Tom. Operatör har laddat ned ZIP - väntar på unzip + harmonisering.

## Källa

Fork av [vercel/examples → solutions/blog](https://github.com/vercel/examples/tree/main/solutions/blog).

OBS: full-repot är stort. Vi behöver bara `solutions/blog`-undermappen.

## Setup-instruktioner

1. Unzippa det nedladdade arkivet
2. Kopiera **bara** `solutions/blog/` till `data/starters/portfolio-base/`
3. Ta bort `.git/`-spår om de finns
4. Verifiera build:
   ```powershell
   cd data/starters/portfolio-base
   npm install
   npm run build
   ```
5. Harmonisera (se `data/starters/README.md`)

## Krav på harmonisering

`vercel/examples/solutions/blog` ger oss:
- MDX-stöd
- SEO-mönster
- RSS-flöde
- Dynamiska OG-bilder
- Tailwind v4
- Geist-fonten

Det vi måste göra:
- Uppgradera till Next.js 16 om behövs
- Lägg till shadcn/ui via `npx shadcn@latest init` (saknas)
- Säkerställ TypeScript strict
- Anpassa route-strukturen så scaffolden kan injicera `/portfolio`, `/case-studies`, `/about`
- Ta bort default-blogginlägg (lorem ipsum)

## Scaffolds som använder denna bas

- `portfolio-creator`
- `agency-studio`

## Förbjudna ändringar

- Ta bort MDX-stödet (det är vad som gör startern användbar för case studies)
- Ta bort SEO-baseline (sitemap, robots, JSON-LD)
