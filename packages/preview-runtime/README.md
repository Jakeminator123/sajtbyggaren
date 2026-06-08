# `packages/preview-runtime/`

Adapter-gräns mellan **kärnflödets generation-output** (`packages/generation/`,
`scripts/build_site.py`, genererade filer under `data/runs/<runId>/generated-files/`)
och **previewen som kör/visar sajten** för operatören och slutkunden.

Generation-lagret slutar vid genererad output. Det vet ingenting om StackBlitz,
Vercel, Fly, eller lokal `next start`. Preview Runtime tar vid där.

## Status (uppdaterad 2026-06-08)

> Tidigare versioner av denna fil sa "Bite A — skelett, inga konsumenter
> wirade än" och "Bite B — kommande sprint". Det var STALE: Bite B landade i
> PR #140 och en `vercel-sandbox`-adapter (ADR 0033) tillkom. Statusen nedan
> speglar koden, inte den gamla planen.

**Bite A — skelett. KLAR + utökad.** Typkontrakt + registry + adaptrar.
Typunionen `PreviewRuntimeKind` är numera **fyra** värden inkl.
`vercel-sandbox` (naming-dictionary **v19**, ADR 0033), inte tre.

**Bite B — wiring. KLAR (PR #140).** Adaptrarna får sina konkreta handlers via
dependency injection (`configurePreviewRuntimeHandlers`):

- `local` → `apps/viewser/lib/` (`next start` via injicerad handler)
- `stackblitz` → `apps/viewser/lib/stackblitz-files.ts` (file-payload till
  `@stackblitz/sdk`)
- `vercel-sandbox` → `apps/viewser/lib/vercel-sandbox-*` (publik
  `…vercel.run`-https-iframe, ADR 0033 — primärt förstahandsval)
- `fly` → fortfarande `unsupported`-stub (reserverad slot, se nedan)

`apps/viewser/lib/preview-runtime-server.ts` injicerar handlers, tsconfig-
path-aliaset `@preview-runtime` finns, och `app/api/preview/[siteId]/route.ts`
+ `apps/viewser/lib/preview-runtime.test.ts` konsumerar paketet via
`currentViewserRuntime()`/`currentRuntime()`.

**Bite C — UI-refaktor (Christophers lane).** Server-halvan är klar
(`route.ts` går via runtime-registret). Klient-flippen i
`apps/viewser/components/viewer-panel.tsx` (`IS_LOCAL_NEXT_MODE` /
`IS_STACKBLITZ_MODE` / `IS_VERCEL_SANDBOX_MODE` bakom en runtime-resolver) var
blockerad av ett **riktigt kontraktsproblem**, inte bara lane-ägarskap:
`normalizePreviewMode()` är **lossy** — den slår ihop `local-next` + `auto` +
`local` → `"local"`, men klienten måste skilja `local-next` (COEP av →
StackBlitz-embed ogiltig) från `auto` (COEP på → StackBlitz-embed legitim).
**Avblockerat 2026-06-08** med en klient-säker, ren export:
`resolvePreviewRuntimeDescriptor(raw)` (se `src/descriptor.ts`) som bevarar
`rawMode` (`auto` ≠ `local-next`) + `prefersCoep` + `canFallbackToStackblitz`
utan server-only-beroenden, så den kan tree-shakas in i en Next-klientbundle.
Christopher gör klient-refaktorn i sin lane mot descriptorn (driv den från
`NEXT_PUBLIC_VIEWSER_PREVIEW_MODE`). Relaterat: B125 (cross-browser-preview)
är till stor del adresserad av `vercel-sandbox` som inte kräver COEP.

## Canonical-namn (naming-dictionary v19)

Alla namn är låsta:

- `Preview Runtime` (`previewRuntime`) — abstraktionen
- `PreviewRuntimeKind` (`previewRuntimeKind`) — sluten typunion `"vercel-sandbox" | "local" | "stackblitz" | "fly"` (v19; `vercel-sandbox` är primärt förstahandsval, ADR 0033)
- `PreviewRuntimeConfig` (`previewRuntimeConfig`) — config till `start()`
- `Preview Session` (`previewSession`) — aktiv session
- `Preview File` (`previewFile`) — fil i payload
- `Preview Result` (`previewResult`) — output från Engine Run

Förbjudna alias för `previewRuntime` och relaterade `globallyForbidden`-
termer listas i `governance/policies/naming-dictionary.v1.json` (sök
efter `previewRuntime.aliasesForbidden` + `globallyForbidden`).
`tests/test_no_legacy_terms.py` är CI-grinden som blockerar dem i
product files.

## `fly`-slot:en — reconciliation mot ADR 0028

Reviewer-fynd 2026-05-27 (post Bite A): typunionen `stackblitz | local | fly`
matchar inte rakt av varken ADR 0028:s tre nivåer (LocalRuntime,
StackBlitzRuntime, production-/deploy-check) eller ADR 0030:s fyra
adapter-mode-namn (`local-next`, `static-export`, `stackblitz`,
framtida `vercel-preview`). `fly` är ett arvsord från ADR 0003 där
`FlyRuntime` ursprungligen var kandidat för produktionslik verifiering.

För att hålla Bite A låst utan naming-dict-bump i samma PR:

- `fly` motsvarar i nuläget **ADR 0028 nivå 3** ("production-/deploy-check")
  — alltså den slot där en framtida `FlyRuntime` eller annan
  production-lik runtime (vercel-hosted, docker-baserad, etc.) kan landa.
- Implementation är TBD. ADR 0028 säger explicit att "om den sista nivån
  senare behöver kodnamn, interface eller policyfält ska det låsas i en
  ny governance-ändring innan kod skrivs".
- Inget kod-anrop använder `kind: "fly"` än; adapter-stubsen i
  `adapters/fly.ts` returnerar `unsupported`.

Detta är dokumenterad reconciliation, inte en arkitektur-fix. Eventuell
omdöpning av `fly` till mer neutralt namn (t.ex. `production`) kräver
naming-dictionary-bump till v18 + egen ADR-not och tas inte i Bite A/B/C.

## `vercel-sandbox`-adaptern (ADR 0033) — landad

`vercel-sandbox` är implementerad (`src/adapters/vercel-sandbox.ts`) och är det
primära förstahandsvalet per ADR 0033: previewen är en publik
`…vercel.run`-https-iframe som bäddas utan cross-origin-isolation, så den
funkar i alla browsers (löser i praktiken B125:s Chromium-only-begränsning).
Typunionen bumpades till v19 för att rymma den. (Den tidigare planerade
`vercel-preview`-adaptern i ADR 0030 #4 är en separat, ännu icke-byggd slot;
`vercel-sandbox` är det som faktiskt landade.)

## Env-var

`VIEWSER_PREVIEW_MODE` är fortsatt input-env-var per
`apps/viewser/.env.example`. Värden:

- `local-next` → normaliseras till `kind: "local"` (COEP av)
- `stackblitz` → `kind: "stackblitz"` (COEP på)
- `vercel-sandbox` → `kind: "vercel-sandbox"` (COEP av; publik https-iframe, ADR 0033)
- `fly` → `kind: "fly"` (unsupported-stub)
- `auto` → normaliseras till `kind: "local"` (default; men COEP på — `auto` ≠ `local-next`, se `resolvePreviewRuntimeDescriptor`)

Klienten (browsern) har inte `VIEWSER_PREVIEW_MODE` i runtime — använd
`NEXT_PUBLIC_VIEWSER_PREVIEW_MODE` + `resolvePreviewRuntimeDescriptor()` där.

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
