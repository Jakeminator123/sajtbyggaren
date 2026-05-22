# ADR 0025 - Browser-fallback för WebContainer-preview (B125)

**Status:** Proposed
**Datum:** 2026-05-19, uppdaterad 2026-05-22
**Beroenden:** ADR 0003 (preview-runtime StackBlitz-first), ADR 0021
(StackBlitz preview-payload-workarounds), B59, B123, B124, B125.

## Kontext

Viewser använder embedded StackBlitz/WebContainer som första användarnära
preview-yta. Det ger en viktig skalningsfördel: kompute körs i kundens egen
browser i stället för i Sajtbyggarens servermiljö.

Begränsningen är inte att Safari eller Firefox är allmänt omöjliga som
browsers. Begränsningen är att embedded StackBlitz/WebContainer inte är
tillräckligt robust som enda previewväg för Sajtbyggaren. Riskerna ligger i
cross-origin isolation, Service Workers, storage-/cookie-restriktioner,
tredjepartsiframe-policy och runtime-skillnader mellan browsers. Chromium är
den primära fungerande vägen för nuvarande embed. Firefox och Safari har
begränsningar, beta-/alpha-läge eller andra praktiska friktioner enligt
WebContainers-dokumentationen, särskilt när WebContainer-projekt körs embedded
i en annan produkt.

För svenska SMB-slutkunder innebär detta att en betydande andel användare kan
hamna utan stabil preview-flik om Sajtbyggaren bara erbjuder embedded
StackBlitz/WebContainer. README och B125 uppskattar risken till ungefär
25-35% av användarna, med extra risk i låsta browsermiljöer.

Det här påverkar bara preview-fliken i Sajtbyggarens UI. Slutpublicerade
kund-sajter är vanlig Next.js och fungerar i moderna browsers; de påverkas
inte av detta beslut.

B59 är förhistorien: 2026-05-15 testades flera header-lägen utan en grön
preview. B123 och B124 löste därefter Chromium-spåret genom host-headers
(`Cross-Origin-Embedder-Policy: credentialless`,
`Cross-Origin-Opener-Policy: same-origin`) och ett `credentialless`-attribut
på iframen som StackBlitz SDK skapar. Det reducerar risken för Chromium, men
det löser inte behovet av en browseroberoende fallback.

## Nuvarande preview-läge

- Viewser är fortfarande en localhost-only operator-prototyp, inte en
  canonical Preview Runtime.
- Viewser-flödet är i dag: PromptBuilder -> `/api/prompt` ->
  `scripts/build_site.py` -> run-artefakter och generated files ->
  `GET /api/runs/<runId>/files` -> `@stackblitz/sdk.embedProject(...)`.
- `apps/viewser/lib/stackblitz-files.ts` bygger en filtrerad StackBlitz-
  payload från `build-result.generatedFilesDir`,
  `data/runs/<runId>/generated-files/` eller `build-result.devPreviewDir`.
- StackBlitz-payloaden patchas redan med Next 16/WebContainer-workarounds:
  `next dev/build --webpack`, lockfil, `stackblitz.startCommand`,
  `.env*`-filter och `app/global-error.tsx`-override.
- `apps/viewser/next.config.ts` sätter COEP/COOP-headers, och
  `apps/viewser/components/viewer-panel.tsx` sätter iframe-`credentialless`
  runt StackBlitz SDK-embeddet.
- `packages/preview-runtime/` är ännu inte implementerat.
- `governance/policies/engine-run.v1.json` säger redan att Preview Runtime
  körs separat efter fas 1-3 och producerar Preview Result, men
  `preview-result.json` är inte byggt i nuvarande Viewser-spår.

## Rekommenderat beslut (Proposed)

Vi rekommenderar kandidat 1: server-byggd statisk preview som
browseroberoende fallback för preview-fliken.

När embedded StackBlitz/WebContainer inte stöds tillräckligt bra, eller när
embeddet fallerar efter timeout, ska Sajtbyggaren kunna visa en iframe med en
server-byggd preview-URL. Sajtbyggarens befintliga builder producerar redan en
vanlig Next.js-sajt; fallbacken ska bygga eller exportera en statisk
visningsversion, publicera den till vald statisk hosting och länka den till
aktuell run.

Sekundär fallback-väg är en manuell "Öppna i StackBlitz"-länk. Den är en
escape hatch när statisk fallback saknas eller fallerar, inte V1-huvudvägen.

ADR:n är medvetet kvar som Proposed. Den ska inte markeras Accepted förrän
operatören har valt hosting, TTL/retention, budgettak, statisk export kontra
serverad build och om Vercel får användas temporärt.

Motivering för V1-vägen:

- En server-byggd statisk preview är browseroberoende eftersom resultatet är
  vanlig webb i stället för embedded WebContainer-runtime.
- Kostnaden kan hållas låg med statiska filer, cache och retention.
- Säkerhetsytan är mindre än för levande dev-servrar eftersom previewn är
  read-only och tidsbegränsad.
- Vägen bevarar StackBlitz/WebContainer som snabb standardpreview när den
  fungerar, men gör preview-fliken lanserbar för fler kundmiljöer.
- Valet undviker att göra Vercel till obligatorisk plattform innan operatören
  har tagit ett explicit hostingbeslut.

## Konsekvenser

Positiva konsekvenser:

- Preview-fliken får en robust väg även när embedded StackBlitz/WebContainer
  inte räcker.
- Fallbacken passar preview-flikens read-only-karaktär: användaren behöver se
  sajten, inte editera kod i preview-runtimen.
- Driftkostnaden kan styras med TTL, retention och statisk hosting.
- Slutpubliceringsflödet för kundens riktiga sajt ändras inte.

Negativa konsekvenser:

- Uppdateringar blir långsammare än WebContainer-hot-reload. Förväntad
  latency är ungefär 30-60 sekunder per ny preview beroende på build och
  upload.
- Fallbacken är mindre interaktiv än en levande dev-server.
- Vissa Next.js-funktioner kan kräva export-/rendering-regler innan de kan
  visas statiskt.
- Operatören måste besluta hosting, budgettak, TTL och retention.
- Build- och publiceringsfel behöver synas tydligt i Run Details så
  användaren inte hamnar i en tom iframe.

## Alternativ som övervägdes

| Kandidat | Latency | Kostnad | Säkerhet | Operatörs-UX | Kund-UX | Implementation 1-10 | Pros | Cons |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| Server-byggd statisk preview | Medel, cirka 30-60s | Låg med statisk hosting och TTL | Bra, statisk read-only-yta | Hanterbar när hosting/retention är vald | Bra i browsers och låsta miljöer som kan visa vanlig webb | 6 | Browseroberoende, billig, leverantörsneutral, passar read-only-preview | Kräver export/build-publicering, TTL, rensning och felvisning |
| Lokal `next dev`-park | Låg efter start | Hög vid många samtidiga kunder | Svårare, levande processer per kund | Tung drift, port-/processhantering | Bäst känsla med snabb uppdatering | 8 | Snabb feedback och nära lokal dev-upplevelse | Skalar dåligt, liknar sajtmaskins/Fly-kostnadsproblem, större attackyta |
| "Öppna i StackBlitz" | Låg implementation, extern laddtid varierar | Mycket låg | Bra för Sajtbyggaren, flyttar runtime externt | Enkel att bygga och drifta | Svagare: kunden lämnar Sajtbyggaren och får extern flik | 2 | Minst kod, bra manuell escape hatch | Inte embedded, beroende av StackBlitz browserstöd och policyer, svag produktupplevelse |
| Vercel preview-deployments per build | Medel, ofta snabb men beror på kö/build | Medel-hög vid många builds | Bra om secrets/preview scopes hanteras rätt | Enkel initialt men leverantörsbunden | Bra, riktig URL i browsers | 5 | Snabb väg till fungerande preview-URL, etablerat flöde | Vercel-beroende, kostnad per build, kopplar fallback till extern deploy-plattform |
| Enkel artifact/browser preview | Låg om den bara visar befintliga artefakter | Mycket låg | Bra om read-only och utan secrets | Enkel som diagnostik | Otillräcklig som kundpreview om den bara visar filer/JSON | 3 | Kan återanvända Run Details och generated files för felsökning | Visar inte en faktisk sajt utan extra render/build; om den bygger HTML blir den i praktiken statisk preview-spåret |

## Operatörsbeslut som krävs före implementation

- Hostingval: egen VPS, Cloudflare R2/CDN, annan statisk hosting eller
  temporär extern plattform.
- TTL och retention: hur länge preview-URL:er lever och när gamla previews
  rensas.
- Budgettak: kostnad per build, per månad och vid samtidiga användare.
- Statisk export kontra serverad build: om alla nuvarande routes kan visas
  statiskt eller om vissa behöver serveras från en byggd Next.js-app.
- Om Vercel får användas temporärt som bootstrap trots att V1-rekommendationen
  inte ska låsa produkten till Vercel.

## Nästa Builder-sprint

En senare implementation ska börja med kontraktet, inte med UI. Föreslagen
ordning:

1. Definiera Preview Result-metadata för fallbackstatus, URL, expiry,
   `sourceRunId`, fallbackorsak och felorsak.
2. Bygg server-byggd statisk preview från befintlig generated site efter
   ordinarie builder-körning.
3. Publicera artefakten till operatörsvald hosting med TTL och retention.
4. Skriv fallback-URL, expiry och felorsak till run-/preview-artefakter så Run
   Details kan visa statusen.
5. Lägg browser-/feature-detection i Viewser: använd embedded StackBlitz när
   det är rimligt, annars fallback-iframe.
6. Lägg manuell "Öppna i StackBlitz"-länk när både embed och statisk fallback
   saknas eller fallerar.
7. Lägg tester för metadata, browserbeslut, fallback-error UI och att secrets
   inte publiceras.

## Vad ADR 0025 inte beslutar

- Ingen implementation av fallbacken i detta steg.
- Ingen ändring i Viewser-runtimekod eller `apps/viewser/`.
- Ingen ändring i `packages/`, `scripts/build_site.py` eller
  `packages/preview-runtime/`.
- Ingen ändring i mini-eval runner-spåret.
- Ingen SNI-runtime, Project DNA V2, starters, variant-promotion eller
  embeddings.
- Inga nya dependencies.
- Ingen ändring i `.cursor/rules/`.
- Ingen stängning av B125; posten kan stängas först när fallbacken är
  implementerad och verifierad.
- Ingen ändring av slutpublicerade kund-sajter eller deras browserstöd.
- Ingen ny default bort från StackBlitz/WebContainer där embeddet fungerar.
