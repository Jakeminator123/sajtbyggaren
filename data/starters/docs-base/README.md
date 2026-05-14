# docs-base

Specialstarter för `course-education`-scaffolden. Dokumentations-/kursstruktur via Nextra.

## Status

Byggbar basstarter. Den är bara starter-underlag i denna PR och aktiveras
inte i runtime-mappningen.

## Källa

Fork av [shuding/nextra](https://github.com/shuding/nextra), importerad från
`examples/docs/`.

Pinned commit: `36ba79c2b13d20cbbe9394d251bb0fc8fb7ed724`

Upstream MIT-licens bevaras i `license.md`. Runtime-/vendor-branding,
source-länkar och demo-routes från upstream-exemplet är borttagna så basen är
neutral.

## Kommandon

```powershell
cd data/starters/docs-base
npm install
npm run build
npm run lint
npm run prettier:check
```

## Krav på harmonisering

Harmoniserad enligt starter-kraven i `data/starters/README.md`:

- Next.js 16
- TypeScript strict
- Tailwind 4
- shadcn/ui-bas via `components.json`
- npm `package-lock.json`
- ESLint flat config
- Prettier
- minimal `.env.example`

`shuding/nextra/examples/docs` ger oss:

- Markdown/MDX-driven sidor via Nextra-pluginet och `/docs/[[...mdxPath]]`
- Hybrid sökfunktion (Nextra `Search`-komponent + `pagefind`-postbuild
  som indexerar `.next/server/app`)
- Light/dark mode via inline boot-skript + `ThemeToggle`-komponent
- Tailwind 4

## Nextra-specialfall

Nextra-pluginet är avsiktligt kvar i `next.config.mjs`. Startern behåller
docs-themes CSS, Nextras MDX-resolver (`importPage`/`generateStaticParamsFor`)
och light/dark-mönster.

Startern skapar inga top-level app routes för `/program`, `/lectures` eller
`/resources`. De lämnas för framtida scaffold-injektion av
`course-education`. Neutral placeholder-content ligger under Nextra docs-
innehållet.

## Manual sidebar discipline

Sidomenyn i `src/app/layout.tsx` (`<aside>`-blocket) är **manuellt
underhållen**. Den listar fyra fasta länkar (`/docs`, `/docs/course-shell`,
`/docs/authoring`, `/docs/scaffold-slots`) och läser inte från `_meta.ts`-
filerna i `src/app/` eller `src/content/`.

Konsekvens: när en scaffold (eller framtida content-uppdatering) lägger
till en ny MDX-fil i `src/content/` måste samma sprint också uppdatera
`<aside>`-blocket i `src/app/layout.tsx` så att den nya sidan dyker upp
i sidomenyn. Annars är pagen routbar via `/docs/<slug>` men osynlig i
nav.

`_meta.ts`-filerna är kvar som Nextra-plugin-metadata för en framtida
migrering till page-map-driven layout, men styr inte synlig navigation
idag. Detta spåras som öppen följd-uppgift i `docs/known-issues.md`
("page-map-driven sidebar för docs-base") och bör lösas innan startern
aktiveras i `SCAFFOLD_TO_STARTER`.

## Scaffolds som använder denna bas

- `course-education`

## Förbjudna ändringar

- Ta inte bort Nextra-pluginet.
- Lägg inte riktiga `.env`-filer i startern.
- Lägg inte till auth, databas, betalning, CMS eller analytics.
- Lägg inte in deploy/source CTA:er.
- Gör inte startern till kundspecifik kurscopy.
- Aktivera inte runtime-mappning utan separat beslut och PR.

## Runtime-status

`docs-base` är inte kopplad till `SCAFFOLD_TO_STARTER` i denna PR. Planering
och runtime fortsätter använda befintlig mapping tills en separat aktivering
beslutas.
