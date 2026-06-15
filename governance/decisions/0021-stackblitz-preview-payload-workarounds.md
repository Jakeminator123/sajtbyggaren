# ADR 0021 - StackBlitz preview: payload-workarounds for WebContainer

**Status:** superseded av 0033 (StackBlitz-vägen pausad — payload-workarounds ligger inte längre på den aktiva preview-vägen; StackBlitz-adaptern rörs inte, se 0055)
**Datum:** 2026-05-15
**Beroenden:** ADR 0003 (preview-runtime StackBlitz-first),
ADR 0011 (Scaffolds som inherited arbetsmaterial).

## Kontext

Viewser previewar generated runs via StackBlitz SDK och WebContainer.
Under denna session blev payload-hygienen förbättrad stegvis, men två
uppströmsproblem kvarstod i kombinationen Next 16 + WebContainer:

1. `next build` försöker använda Turbopack i miljöer där den inte stöds,
   med fel av typen:

   ```
   Turbopack is not supported on this platform ... use next build --webpack
   ```

2. Production-build i WebContainer kan krascha på default-sidan
   `/_global-error` med:

   ```
   Invariant: Expected workStore to be initialized
   ```

Samtidigt byggde samma generated dir lokalt (utanför WebContainer) grönt i
de verifierade fallen. Det pekar på runtime-krock mellan Next och
WebContainer, inte på en generell builder-regression.

Ytterligare risk som identifierades: om `package-lock.json` saknas i payloaden
kan `npm install` i StackBlitz lösa en annan dependency tree än lokal builder,
särskilt med `^`-ranges i starters.

## Beslut

Vi behåller en smal in-memory payload-patcher i
`apps/viewser/lib/stackblitz-files.ts` för StackBlitz-preview:

- `package.json` patchas i payloaden så:
  - `scripts.dev = "next dev --webpack"`
  - `scripts.build = "next build --webpack"`
  - `stackblitz.startCommand = "npm run build && npm run start"`
- `package-lock.json` inkluderas i payloaden och undantas från
  `MAX_FILE_BYTES`-gränsen (men räknas fortfarande mot total payload-size).
- Om generated output saknar `app/global-error.tsx` injiceras en minimal
  override i payloaden för att undvika Next 16 default-prerendern som
  triggar `workStore`-felet i WebContainer.
- `.env*` fortsätter filtreras bort från payloaden, med exakt allowlist för
  `.env.example`.

Patchningen sker endast i preview-payloaden och skriver inte tillbaka till
run-artifacts på disk.

## Vad ADR 0021 INTE beslutar

- Ingen ändring av `data/starters/`.
- Ingen ändring av `scripts/build_site.py`.
- Ingen ändring av `packages/preview-runtime/stackblitz`.
- Ingen versionspinning eller migration bort från Next 16 i denna sprint.
- Ingen migration bort från StackBlitz/WebContainer-runtime.

## Konsekvenser

- Preview-runtime kan bete sig annorlunda än lokal builder eftersom den kör i
  WebContainer och med payload-specifik patchning.
- Lokal builder (run-artifacts + Quality Gate) förblir källa-i-sanning för
  produktkvalitet; StackBlitz-preview är en visningsyta.
- Drift-risken minskar genom att lockfilen nu följer med till preview, vilket
  minskar skillnader i dependency resolution mellan lokalt och StackBlitz.
- Workarounden för `app/global-error.tsx` är avsiktligt temporär och bör ses
  som kompatibilitetslager tills uppströmsfix finns.

## Omprövning

När Next.js och WebContainer fungerar stabilt utan dessa workarounds ska
`patchPackageJsonForStackblitz` och `global-error`-injektionen reduceras eller
tas bort i en separat ändring med verifierad grön preview utan specialfall.

## Referenser

- [vercel/next.js#92656](https://github.com/vercel/next.js/issues/92656)
- [stackblitz/webcontainer-core#2045](https://github.com/stackblitz/webcontainer-core/issues/2045)
- [stackblitz/webcontainer-core#1978](https://github.com/stackblitz/webcontainer-core/issues/1978)
- [stackblitz/webcontainer-core#1739](https://github.com/stackblitz/webcontainer-core/issues/1739)
