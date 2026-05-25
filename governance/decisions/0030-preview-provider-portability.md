# ADR 0030 — Preview/deploy-providers är adapters, inte kanoniskt beroende

**Status:** Accepted
**Datum:** 2026-05-25
**Beroenden:** ADR 0003 (PreviewRuntime-abstraktion), ADR 0025 (browser-fallback-
preview), ADR 0028 (Runtime Ladder),
`docs/product-operating-context.md` (avsnitten "Runtime och preview" + "Förhållande
till lovable och sajtmaskin").

## Kontext

Vercel-plugin har installerats i operatörens IDE och en parallell agent har börjat
scout:a Vercel-spåret för preview/deploy. Operatören och produktcoachen vill att
arbetet med Vercel kan fortsätta — Vercel kan mycket väl visa sig vara den bästa
hosted previewn — men inte att Sajtbyggaren blir låst vid en enda leverantör.

Bakgrunden ekar gamla `sajtmaskin`-misstaget som
[`docs/product-operating-context.md`](../../docs/product-operating-context.md) varnar
för: "auth, credits, domäner, integrationslager, media, för många starter-spår,
deploy-spår och agentfunktioner fanns samtidigt och gjorde helheten svårstyrd". Att
binda kärnflödet till en leverantörs runtime upprepar samma misstag fast på en annan
axel: nu pratar vi om hur preview, build och deploy är arrangerade, inte vad sajten
gör.

Samtidigt äger operatören redan tre runtime-nivåer enligt ADR 0028 (`LocalRuntime`,
`StackBlitzRuntime`, production-/deploy-check). Plus nya bug-nivå-poster i
[`docs/known-issues.md`](../../docs/known-issues.md) — i synnerhet `B125`
(Safari/Firefox-fallback för embedded WebContainer-preview) — listar Vercel
preview-deployments som **fallback-kandidat #4**, men explicit kvalificerar:
"drar in Vercel-beroende som operatören explicit vill undvika där det går".

## Beslut

**Preview/deploy-providers är adapters bakom `PreviewRuntime`-abstraktionen, inte
det kanoniska runtime-kontraktet. Sajtbyggaren får använda Vercel om det är ett bra
val, men kärnflödet får inte bero på att Vercel finns.**

Konkret innebär det följande tre regler. Alla tre är hårda gränser; brott kräver en
ny ADR som överlever review.

### Regel 1 — Generated output är vanlig Next.js

`scripts/build_site.py` och `packages/generation/codegen/` får aldrig emittera kod
som kräver en specifik leverantörsplattform för att starta lokalt. En genererad
kund-sajt ska kunna `npm install && npm run build && npm run start` på vilken
Node.js-värd som helst — operatörens dator, en Docker-container, en server, en
Vercel-deploy, en Fly-VM. Vercel-specifika optimeringar (`@vercel/og`,
`@vercel/blob` med exklusiv hosting-resolver, edge-runtime-direktiv som inte
gracefully degraderar, etc.) får inte hardcoded:as i renderers eller i starter-
package.json.

Praktisk skiljelinje: en starter får importera `@vercel/blob` så länge starter-
sajten kan starta utan `BLOB_READ_WRITE_TOKEN` (graceful skip + tom assets-state).
Den får INTE kasta runtime-fel om token saknas.

### Regel 2 — Preview-runtime är pluggable

`PreviewRuntime`-abstraktionen från ADR 0003/ADR 0028 ska räcka för minst följande
fyra adapters:

| Nivå | Adapter | Roll |
| ---- | ------- | ---- |
| 1 | `local-next` | Primär dev-preview ([`apps/viewser/lib/local-preview-server.ts`](../../apps/viewser/lib/local-preview-server.ts) spawnar `next start -p 41xx`); ägs av oss, samma-maskin, http, funkar i alla browsers |
| 2 | `static-export` (framtida) | Robust fallback; `next build && next export` deployad till valfri host (egen VPS, Cloudflare R2, S3, etc.) |
| 3 | `stackblitz` | Browser/WebContainer-fallback; embeds via `@stackblitz/sdk` när Chromium-isolation är möjlig |
| 4 | `vercel-preview` (framtida adapter) | Hosted preview/deploy via Vercel — bra hosted preview-yta, inte enda vägen |
| 5 | Framtida: Docker-runtime, Fly-runtime, etc. | Portabilitetstest senare |

Varje adapter måste:

- Implementera `PreviewRuntime`-interfacet (`start`, `stop`, returnera
  `PreviewSession` med URL).
- Kunna tappa ut tyst — om adaptern inte är konfigurerad eller fungerar, får
  `PreviewRuntime`-konsumenten en strukturerad fail som låter den välja nästa
  adapter eller visa pedagogiskt fel (samma mönster som `apps/viewser/components/
  viewer-panel.tsx` redan gör för `local-next` → `stackblitz`-fallbackgrenarna).
- Inte läcka leverantörsspecifika begrepp (URL-format, cookie-strukturer,
  ID-prefixer) genom abstraktionsgränsen.

### Regel 3 — Forbjudna kopplingar

Följande är **inte tillåtet** utan en ny ADR som motiverar undantaget:

| Förbjudet | Plats där det får ej finnas |
| --------- | ----------------------------- |
| Direkt-import av `@vercel/...` SDK i `packages/generation/` | All generation core |
| `scripts/build_site.py` kräver Vercel-env för att producera output | All builder-kod |
| Genererad sajt kräver Vercel för att starta lokalt | All renderer-output |
| Preview-success beror på en enda leverantör | All `PreviewRuntime`-konsumenter (i synnerhet `apps/viewser/components/viewer-panel.tsx`) |
| Vercel-API-anrop på CI-steg som inte är explicit deploy | All `.github/workflows/` utom `vercel-deploy*.yml` (om/när det skapas) |

Tillåtet:

| Tillåtet | Begränsning |
| -------- | ----------- |
| Vercel-MCP-server för operatörens egna debugging | Operator-only; körs inte i kärnflödet |
| `apps/viewser/`-deploy till Vercel | Endast Sajtbyggarens eget admin-UI, inte genererad output |
| `@vercel/blob` i starter-deps | Måste graceful degrade utan token (se Regel 1; framtida asset-store-driver-ADR kvalificerar portabilitet bortom local+vercel-blob) |
| Hosted preview-deploys via Vercel | Som adapter, inte default; måste ha en non-Vercel fallback i `PreviewRuntime`-listan |

## Vad ADR 0030 INTE beslutar

- Vilka konkreta adapters som faktiskt ska implementeras härnäst. ADR 0030
  säger bara att Vercel inte får vara enda vägen; vilken adapter som blir
  nästa byggmål bestäms i en separat sprint-prio (sannolikt `local-next` är
  redan primär, sedan B125-fallback).
- Den exakta implementationen av en eventuell `VercelRuntime`-adapter. Det är
  egen ADR när det blir aktuellt.
- Hur `@vercel/blob` ska bytas mot en provider-agnostisk asset-store-driver.
  Det är framtida arbete som kräver en egen ADR; ingen existerande ADR
  täcker asset-store-portabilitet idag.
- Om Sajtbyggaren själv ska deployas på Vercel. Det är en separat operatörs-
  driftsfråga, inte en runtime-arkitekturfråga.

## Konsekvenser

Positiva:

- Vercel-spårets agent får en tydlig adapter-gräns att jobba mot. Den kan
  scout:a + föreslå utan att kärnflödet blir beroende.
- B125-fallback-listan i [`docs/known-issues.md`](../../docs/known-issues.md)
  får en uppdaterad principbas: alla fyra kandidater (egen statisk export,
  lokal `next dev`, "öppna i StackBlitz", Vercel preview-deployments) bedöms
  mot samma adapter-kontrakt, inte mot olika kvalitetsnivåer.
- Dokumenterad överlevnad av en framtida Vercel-incident eller pris-höjning:
  vi kan byta provider utan att röra `packages/generation/` eller renderer-
  output.
- Säkerställer att gamla `sajtmaskin`-misstaget (kontraktssjuk bredd genom
  vendor-binding) inte upprepas — explicit reflekterat i
  [`docs/product-operating-context.md`](../../docs/product-operating-context.md).

Negativa:

- Något extra arbete vid implementation av varje adapter (måste passera
  abstraktionsgränsen, inte koppla in sig direkt). Acceptabelt — adapter-
  pattern har redan etablerats av ADR 0003/0028.
- Vercel-specifika optimeringar som hade gett snabb vinst kan tillfälligt
  vara förbjudna att hardcoda. Vi accepterar lite långsammare leverans i
  utbyte mot framtida portabilitet.

## Adapter-checklista (för varje ny preview-/deploy-adapter)

Innan en ny adapter mergas måste följande vara uppfyllt:

1. Implementerar `PreviewRuntime`-interfacet (eller motsvarande deploy-
   abstraktion när den landas).
2. Har en non-trivial fallback-strategi: vad händer när adaptern inte fungerar
   för en specifik run?
3. Existerande adapter-listans precedens behålls (`local-next` är primär för
   operator-bygda sajter, andra är fallbacks).
4. Inga Vercel-/leverantörsspecifika begrepp läcker till
   `packages/generation/`, `scripts/build_site.py`, `data/starters/`, eller
   `governance/policies/`.
5. Genererad output kan startas lokalt utan adaptern.
6. ENV-vars som adaptern kräver är opt-in, inte krav för normal lokal build.
7. ADR-referens i PR-beskrivningen som länkar tillbaka till ADR 0030 + ev.
   nyare ADR som kvalificerar adaptern.

## Mot parallella agenter (operator-direktiv)

Vercel-spårets agent får:

- scout:a Vercel-möjligheter (preview, deploy, marketplace, AI Gateway,
  workflow, sandbox, etc.)
- föreslå adapter-shape via ADR-utkast eller diff-skiss

Vercel-spårets agent får INTE:

- ändra `packages/generation/`-core
- ändra `scripts/build_site.py`
- ändra `data/starters/*/package.json` på ett sätt som binder till Vercel
- ändra det kontrakt en genererad sajt har (måste fortsätta vara vanlig
  Next.js)
- mergea Vercel-beroende kod utan att denna ADR är uppfylld

Brott mot dessa regler ska blockas av reviewer (operatören eller annan agent
i review-rollen) innan merge.

## Referenser

- [ADR 0003 — Preview Runtime StackBlitz First](0003-preview-runtime-stackblitz-first.md)
  (etablerar `PreviewRuntime`-abstraktionen som denna ADR bygger vidare på)
- [ADR 0025 — Browser-fallback preview](0025-browser-fallback-preview.md)
- [ADR 0028 — Runtime Ladder](0028-runtime-ladder.md)
- [ADR 0021 — StackBlitz preview payload-workarounds](0021-stackblitz-preview-payload-workarounds.md)
- [`docs/product-operating-context.md`](../../docs/product-operating-context.md)
- [`docs/known-issues.md` — B125](../../docs/known-issues.md)
- [`apps/viewser/components/viewer-panel.tsx`](../../apps/viewser/components/viewer-panel.tsx)
  (referens-implementation av adapter-fallback i `local-next` ↔ `stackblitz`)
