# `packages/preview-runtime/`

Adapter-gräns mellan **kärnflödets generation-output** (`packages/generation/`,
`scripts/build_site.py`, genererade filer under `data/runs/<runId>/generated-files/`)
och **previewen som kör/visar sajten** för operatören och slutkunden.

Generation-lagret slutar vid genererad output. Det vet ingenting om StackBlitz,
Vercel, Fly, eller lokal `next start`. Preview Runtime tar vid där.

## Status

**Bite A — skelett (denna PR).** Typkontrakt + registry + tre adapter-stubs.
Inga konsumenter wirade än. Adapter-stubsen returnerar `unsupported` med
tydlig "Bite B-wiring saknas"-text. Filerna kompilerar men anropas inte
från någon befintlig fil.

**Bite B — wiring (kommande sprint).** Adaptrarna delegerar till befintlig
kod i `apps/viewser/lib/`:

- `local` → `apps/viewser/lib/local-preview-server.ts` (`next start`)
- `stackblitz` → `apps/viewser/lib/stackblitz-files.ts` (file-payload till
  `@stackblitz/sdk`)
- `fly` → ingen implementation — reserverad enligt naming-dictionary v17

Bite B kräver tsconfig path-alias eller npm-workspace så `apps/viewser/` kan
importera härifrån. Det är bytetypen i Bite B, inte i Bite A.

**Bite C — UI-refaktor (kräver Christopher-koordinering).** Flytta
`IS_LOCAL_NEXT_MODE`/`IS_STACKBLITZ_MODE`-grenarna i
`apps/viewser/components/viewer-panel.tsx` bakom `currentRuntime()`.
`apps/viewser/components/**` är Christophers reserverade lane per
`governance/rules/branch-scope-ui-ux.md`.

## Canonical-namn (naming-dictionary v17)

Alla namn är låsta:

- `Preview Runtime` (`previewRuntime`) — abstraktionen
- `PreviewRuntimeKind` (`previewRuntimeKind`) — sluten typunion `"stackblitz" | "local" | "fly"`
- `PreviewRuntimeConfig` (`previewRuntimeConfig`) — config till `start()`
- `Preview Session` (`previewSession`) — aktiv session
- `Preview File` (`previewFile`) — fil i payload
- `Preview Result` (`previewResult`) — output från Engine Run

Förbjudna alias: `VM`, `sandbox`, `preview-host`, `vercelSandbox`, `webcontainer`.

## Eventuell framtida `vercel-preview`-adapter

ADR 0030 (Preview-Provider Portability) listar `vercel-preview` som adapter
#4. **Det kräver naming-dictionary-bump till v18** (utöka
`PreviewRuntimeKind`-typunionen) och egen ADR per ADR 0030 §"Vad ADR 0030
INTE beslutar". Tas inte i Bite A/B/C.

## Env-var

`VIEWSER_PREVIEW_MODE` är fortsatt input-env-var per
`apps/viewser/.env.example`. Värden:

- `local-next` → normaliseras till `kind: "local"`
- `stackblitz` → `kind: "stackblitz"`
- `auto` → normaliseras till `kind: "local"` (default)

Eventuellt namnbyte till `SITE_RUNTIME_ADAPTER` är **inte** prioriterat och
kräver separat operator-beslut. ADR 0030 stödjer bakåtkompatibilitet
("byt inte namnet aggressivt").

## Referenser

- [ADR 0003 — Preview Runtime StackBlitz First](../../governance/decisions/0003-preview-runtime-stackblitz-first.md)
- [ADR 0028 — Runtime Ladder](../../governance/decisions/0028-runtime-ladder.md)
- [ADR 0030 — Preview-Provider Portability](../../governance/decisions/0030-preview-provider-portability.md)
- [ADR 0025 — Browser Fallback Preview](../../governance/decisions/0025-browser-fallback-preview.md)
- [`docs/architecture/preview-runtime.md`](../../docs/architecture/preview-runtime.md)
- [`docs/reports/preview-runtime-matrix-2026-05-25.md`](../../docs/reports/preview-runtime-matrix-2026-05-25.md)
- [`governance/policies/naming-dictionary.v1.json`](../../governance/policies/naming-dictionary.v1.json) (canonical-namnen)
