# docs-base

Specialstarter för `course-education`-scaffolden. Dokumentations-/kursstruktur via Nextra.

## Status

Tom. Operatör har laddat ned ZIP - väntar på unzip + harmonisering.

## Källa

Fork av [shuding/nextra](https://github.com/shuding/nextra).

OBS: Nextra-repot innehåller flera exempel. Vi vill ha `docs`-startern.

## Setup-instruktioner

1. Unzippa det nedladdade arkivet
2. Kopiera **bara** `examples/docs/` (eller `examples/swr-site/`) till `data/starters/docs-base/`
3. Ta bort `.git/`-spår
4. Verifiera build:
   ```powershell
   cd data/starters/docs-base
   npm install
   npm run build
   ```
5. Harmonisera (se `data/starters/README.md`)

## Krav på harmonisering

`shuding/nextra` ger oss:
- Markdown-driven sidor
- Sidebar-navigering
- Sökfunktion
- Light/dark mode
- Tailwind

Det vi måste göra:
- Uppgradera till Next.js 16
- Lägg till shadcn/ui via `npx shadcn@latest init` (saknas)
- Säkerställ TypeScript strict
- Anpassa route-strukturen så scaffolden kan injicera `/program/[id]`, `/lectures`, `/resources`
- Ta bort default-dokumentationsinnehåll

## Scaffolds som använder denna bas

- `course-education`

## Specialfall

Nextra-strukturen är något annorlunda än övriga starters - scaffolden måste hantera Nextra:s page-konvention. Dokumentera detta i scaffold-mapp när vi bygger `course-education`-scaffolden.

## Förbjudna ändringar

- Ta bort Nextra-pluginet (det är vad som ger sidebar/sök/markdown gratis)
