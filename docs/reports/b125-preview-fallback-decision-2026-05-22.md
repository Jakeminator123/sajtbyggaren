# B125 preview-fallback decision sprint

**Datum:** 2026-05-22
**Status:** beslutsunderlag, ingen implementation
**ADR:** [ADR 0025](../../governance/decisions/0025-browser-fallback-preview.md)

## Sammanfattning

Rekommendationen är att behålla StackBlitz/WebContainer som snabb preview där
embeddet fungerar, men inte göra embedded StackBlitz/WebContainer till enda
previewvägen.

- V1-väg: server-byggd statisk preview som browseroberoende fallback.
- Sekundär fallback-väg: "Öppna i StackBlitz" som manuell escape hatch när
  statisk fallback saknas eller fallerar.
- ADR 0025 ska vara `Proposed` tills operatören har valt hosting, TTL,
  retention, budgettak och om Vercel får användas temporärt.

## Nuvarande preview-läge

- Viewser är en localhost-only operator-prototyp, inte canonical
  Preview Runtime.
- Nuvarande previewflöde:
  1. PromptBuilder kör `/api/prompt`.
  2. Viewser triggar `scripts/build_site.py`.
  3. Builder skriver run-artefakter under `data/runs/<runId>/` och generated
     files.
  4. `GET /api/runs/<runId>/files` bygger en filtrerad StackBlitz-payload från
     `build-result.generatedFilesDir`, `data/runs/<runId>/generated-files/`
     eller `build-result.devPreviewDir`.
  5. ViewerPanel kör `@stackblitz/sdk.embedProject(...)`.
- StackBlitz-payloaden patchas redan för Next 16/WebContainer:
  `next dev/build --webpack`, lockfil, `stackblitz.startCommand`,
  `.env*`-filter och `app/global-error.tsx`-override.
- Viewser-hosten sätter COEP/COOP-headers och ViewerPanel sätter
  iframe-`credentialless` runt StackBlitz SDK-embeddet.
- `packages/preview-runtime/` är ännu inte implementerat.
- Engine Run-policyn säger redan att Preview Runtime ska köras separat efter
  fas 1-3 och producera Preview Result, men `preview-result.json` finns inte
  i nuvarande Viewser-spår.
- När visuell preview inte fungerar används Run Details och
  `scripts/verify_run.py` som artefaktbaserad verifiering.

## B59/B125-risk

- B59 är det tidigare Chromium-spåret: `Unable to run Embedded Project`,
  VM-handshake-timeout och credential-problem. B123/B124 minskar risken genom
  COEP/COOP + iframe-`credentialless`, men grön end-to-end-preview är
  fortfarande ett verifieringskrav.
- B125 är bredare: embedded StackBlitz/WebContainer är inte tillräckligt
  robust som enda previewväg för Sajtbyggaren.
- Riskerna är cross-origin isolation, Service Workers, storage-/cookie-
  restriktioner, tredjepartsiframe-policy och runtime-skillnader mellan
  browsers.
- Chromium är primär fungerande väg. Firefox och Safari har begränsningar,
  beta-/alpha-läge eller andra praktiska friktioner enligt WebContainers-
  dokumentationen, särskilt för embedded projekt.
- Låsta browsermiljöer kan också blockera StackBlitz-domäner eller
  browser-API:er även när användaren kör Chromium.
- Slutpublicerade kundsajter påverkas inte; de är vanlig Next.js. Risken
  gäller preview-fliken i Sajtbyggarens UI.

## Jämförelse av V1-kandidater

| Kandidat | Bedömning |
| --- | --- |
| Server-byggd statisk preview | Rekommenderad V1-väg. Browseroberoende eftersom resultatet är vanlig webb, låg driftkostnad med TTL/retention, mindre attackyta än levande dev-servrar. Nackdel: långsammare uppdatering och kräver hosting-/retention-beslut. |
| Lokal `next dev`-park | Bra känsla och snabb feedback efter start, men hög driftkostnad, port-/processhantering och större attackyta. För nära sajtmaskins/Fly-kostnadsproblem för att vara V1-default. |
| "Öppna i StackBlitz" | Bra sekundär escape hatch och billig att bygga. Inte bra huvudväg eftersom kunden lämnar Sajtbyggaren och fortsatt påverkas av StackBlitz/browser-policyer. |
| Vercel preview-deployments | Praktisk och snabb bootstrap om operatören accepterar Vercel. Nackdel: leverantörsberoende, kostnad per build och tidig koppling mellan preview-fallback och extern deployplattform. |
| Enkel artifact/browser preview | Bra diagnostik om den visar run-artefakter, men inte kundpreview om den bara visar filer/JSON. Om den bygger riktig HTML blir den i praktiken samma spår som server-byggd statisk preview. |

## Rekommendation

V1-vägen bör vara server-byggd statisk preview:

1. Buildern producerar redan en vanlig Next.js-sajt.
2. En server-byggd preview kan visas i iframe som vanlig webb utan
   WebContainer-runtime.
3. Kostnad och säkerhet kan styras med statisk hosting, TTL och retention.
4. StackBlitz kan fortsätta vara snabbväg där embeddet fungerar.

Sekundär fallback bör vara en manuell "Öppna i StackBlitz"-länk:

1. Den är en escape hatch, inte huvud-UX.
2. Den är användbar när statisk fallback saknas, inte hunnit byggas eller
   fallerar.
3. Den ska inte räknas som tillräcklig launch-fallback för Safari, Firefox
   eller låsta miljöer.

## Operatörsbeslut före implementation

Operatören behöver välja:

1. Hostingval: egen VPS, Cloudflare R2/CDN, annan statisk hosting eller
   temporär extern plattform.
2. TTL och retention: hur länge preview-URL:er lever och när gamla previews
   rensas.
3. Budgettak: kostnad per build, per månad och vid samtidiga användare.
4. Statisk export kontra serverad build: om alla nuvarande routes kan visas
   statiskt eller om vissa behöver serveras från en byggd Next.js-app.
5. Om Vercel får användas temporärt som bootstrap.

## Out of scope i denna sprint

- Ingen implementation.
- Ingen Viewser-runtimekod.
- Ingen `apps/viewser`-ändring.
- Inga dependencies.
- Ingen mini-eval runner.
- Ingen SNI-runtime.
- Inga starters.
- Ingen Project DNA V2.
- Ingen variant-promotion.
- Inga embeddings.
- Ingen `.cursor/rules/`-ändring.

## Vad nästa Builder-sprint skulle göra

Nästa Builder-sprint ska börja med kontraktet och metadata innan UI:

1. Definiera Preview Result-metadata för fallbackstatus, URL, expiry,
   `sourceRunId`, fallbackorsak och felorsak.
2. Bygga server-byggd statisk preview från befintlig generated site efter
   ordinarie builder-körning.
3. Publicera artefakten till operatörsvald hosting med TTL och retention.
4. Skriva fallback-URL, expiry och felorsak till run-/preview-artefakter så
   Run Details kan visa statusen.
5. Lägga browser-/feature-detection i Viewser: embedded StackBlitz när det är
   rimligt, annars fallback-iframe.
6. Lägga manuell "Öppna i StackBlitz"-länk när både embed och statisk fallback
   saknas eller fallerar.
7. Lägga tester för metadata, browserbeslut, fallback-error UI och att secrets
   inte publiceras.

## Exakt nästa Builder-prompt

```text
!grind

Du jobbar i repo:t `sajtbyggaren`.

Sprint:
B125 preview-fallback implementation V1, efter operatörsbeslut på ADR 0025.

Förutsättning:
ADR 0025 är godkänd av operatören. Använd vald hosting, TTL/retention och budgettak från operatörens beslut. Om de saknas: stoppa och fråga, implementera inte.

Mål:
Implementera server-byggd statisk preview som fallback när embedded StackBlitz/WebContainer inte stöds tillräckligt bra eller fallerar, utan att ändra mini-eval runner, SNI-runtime, Project DNA V2, starters, variant-promotion eller embeddings.

Krav:
1. Börja med governance-kontraktet: Preview Runtime/Preview Result ska ha tydlig metadata för `status`, `url`, `expiresAt`, `sourceRunId`, `fallbackReason` och felorsak.
2. Håll StackBlitz som default där embeddet fungerar stabilt.
3. I icke-stödda eller låsta browsermiljöer, eller efter StackBlitz-timeout, ska Viewser visa server-byggd statisk preview-URL i iframe.
4. Om statisk preview saknas eller fallerar ska UI:t visa manuell "Öppna i StackBlitz"-länk som nödfallback.
5. Secrets och `.env*` får aldrig publiceras i preview-output.
6. Lägg TTL/retention och cleanup enligt ADR-beslutet.
7. Lägg tester för metadata, browserbeslut, fallback-error UI och att befintlig StackBlitz-payload-säkerhet inte regresserar.

Rör inte:
- `scripts/mini_eval.py`
- mini-eval runner
- SNI-runtime
- Project DNA V2
- starters
- variant-promotion
- embeddings
- orelaterad Viewser UI
- `.cursor/rules/`

Kör minst:
- python scripts/governance_validate.py
- python scripts/rules_sync.py --check
- python scripts/check_term_coverage.py --strict
- python -m pytest tests/test_viewser_isolation_headers.py tests/test_viewser_files.py tests/test_decisions_and_docs.py -q
- relevanta nya tester för preview-fallbacken

Slutrapport:
- valt hosting-/TTL-antagande
- hur fallback väljs
- var fallback metadata skrivs
- risker och kvarvarande operatörsbeslut
- ändrade filer
```
