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

- Markdown-driven sidor
- Sidebar-navigering
- Sökfunktion
- Light/dark mode
- Tailwind

## Nextra-specialfall

Nextra-pluginet är avsiktligt kvar i `next.config.mjs`. Startern behåller
docs-theme, sidebar, sök, markdown/MDX och light/dark-mönster.

Startern skapar inga top-level app routes för `/program`, `/lectures` eller
`/resources`. De lämnas för framtida scaffold-injektion av
`course-education`. Neutral placeholder-content ligger under Nextra docs-
innehållet.

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
