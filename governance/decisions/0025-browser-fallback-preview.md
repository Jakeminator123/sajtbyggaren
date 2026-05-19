# ADR 0025 - Browser-fallback för WebContainer-preview (B125)

**Status:** Proposed
**Datum:** 2026-05-19
**Beroenden:** ADR 0003 (preview-runtime StackBlitz-first), ADR 0021
(StackBlitz preview-payload-workarounds), B59, B123, B124, B125.

## Kontext

Viewser använder embedded StackBlitz/WebContainer som första användarnära
preview-yta. Det ger en viktig skalningsfördel: kompute körs i kundens egen
browser i stället för i Sajtbyggarens servermiljö.

Begränsningen är browser-stöd. Embedded WebContainer-preview fungerar
officiellt bara i Chromium-baserade browsers med stöd för iframe-attributet
`credentialless` (Chrome 110+, Edge, Brave, Vivaldi). Safari, inklusive
iPhone, och Firefox kan inte ladda embeddet. För svenska SMB-slutkunder
blockerar det uppskattningsvis 25-35% av användarna från att använda
preview-fliken i Sajtbyggarens UI.

Det här påverkar bara Viewser-preview under utveckling. Slutpublicerade
kund-sajter är vanlig Next.js och fungerar i alla browsers; de påverkas inte
av detta beslut.

B59 är förhistorien: 2026-05-15 testades flera header-lägen utan en grön
preview. B123 och B124 löste därefter Chromium-spåret genom host-headers
(`Cross-Origin-Embedder-Policy: credentialless`,
`Cross-Origin-Opener-Policy: same-origin`) och ett `credentialless`-attribut
på iframen som StackBlitz SDK skapar. Det räcker för Chromium, men löser inte
Safari eller Firefox eftersom själva browserstödet saknas.

B125 kräver därför en fallback för icke-Chromium-användare innan extern
kundyta kan lanseras.

## Beslut

Vi väljer kandidat 1: server-byggd statisk preview som browser-fallback.

När embedded WebContainer inte stöds ska Viewser visa en iframe med en
server-byggd, statisk preview-URL i stället för StackBlitz-embeddet.
Sajtbyggarens befintliga builder producerar redan en vanlig Next.js-sajt;
fallbacken ska bygga eller exportera en statisk visningsversion, publicera
den till vald statisk hosting och länka den till aktuell run.

Motivering:

- Fungerar i Chromium, Safari och Firefox eftersom resultatet är vanlig
  statisk webb.
- Undviker Vercel-inlåsning som defaultväg.
- Undviker kostnadsprofilen hos en levande `next dev`-process per kund.
- Passar preview-flikens read-only-karaktär: användaren behöver se sajten,
  inte editera kod i preview-runtimen.
- Bevarar StackBlitz/WebContainer som snabb standardpreview för Chromium,
  men ger en robust fallback där embeddet inte kan köras.

## Konsekvenser

Positiva konsekvenser:

- Alla större browsers får en fungerande preview-väg.
- Kostnaden kan hållas låg med statiska filer, cache och retention.
- Fallbacken är leverantörsneutral; operatören kan välja egen VPS,
  Cloudflare R2, egen CDN eller annan statisk hosting senare.
- Säkerhetsytan är mindre än för levande dev-servrar eftersom previewn är
  statisk och tidsbegränsad.
- Beslutet ändrar inte publiceringsflödet för slutkundens riktiga sajt.

Negativa konsekvenser:

- Uppdateringar blir långsammare än WebContainer-hot-reload. Förväntad
  latency är ungefär 30-60 sekunder per ny preview beroende på build och
  upload.
- Fallbacken är mindre interaktiv än en levande dev-server.
- Vissa Next.js-funktioner kan kräva export-/rendering-regler innan de kan
  visas statiskt.
- Operatören måste besluta hosting, kostnadstak, preview-TTL och retention.
- Build- och publiceringsfel behöver synas tydligt i Run Details så
  icke-Chromium-användare inte hamnar i en tom iframe.

## Alternativ som övervägdes

| Kandidat | Latency | Kostnad | Säkerhet | Operatörs-UX | Kund-UX | Implementation 1-10 | Pros | Cons |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| Server-byggd statisk preview | Medel, cirka 30-60s | Låg med statisk hosting och TTL | Bra, statisk read-only-yta | Hanterbar när hosting/retention är vald | Bra i alla browsers, men inte hot-reload | 6 | Browseroberoende, billig, leverantörsneutral, passar read-only-preview | Kräver export/build-publicering, TTL, rensning och felvisning |
| Lokal `next dev`-process som same-origin iframe | Låg efter start | Hög vid många samtidiga kunder | Svårare, levande processer per kund | Tung drift, port-/processhantering | Bäst känsla med snabb uppdatering | 8 | Snabb feedback och nära lokal dev-upplevelse | Skalar dåligt, liknar sajtmaskins/Fly-kostnadsproblem, större attackyta |
| "Öppna i StackBlitz"-fallback-knapp | Låg implementation, extern laddtid varierar | Mycket låg | Bra för Sajtbyggaren, flyttar runtime externt | Enkel att bygga och drifta | Sämst: kunden lämnar varumärket och får extern flik | 2 | Minst kod, kan vara temporär nödlösning | Inte embedded, beta-stöd i Safari/Firefox, svag produktupplevelse |
| Vercel preview-deployments per build | Medel, ofta snabb men beror på kö/build | Medel-hög vid många builds | Bra om secrets/preview scopes hanteras rätt | Enkel initialt men leverantörsbunden | Bra, riktig URL i alla browsers | 5 | Snabb väg till fungerande preview-URL, etablerat flöde | Vercel-beroende, kostnad per build, kopplar fallback till extern deploy-plattform |

## Migrationsplan

1. Lägg till ett fallback-kontrakt i preview-lagret: en run kan ha en
   `fallbackPreviewUrl` och en status för fallback-bygget.
2. Bygg en statisk preview-artefakt från befintlig generated site efter
   ordinarie builder-körning.
3. Publicera artefakten till vald statisk hosting med tydlig TTL och
   retention.
4. Skriv fallback-URL, expiry och felorsak till befintliga run-/build-
   artefakter så Run Details kan visa statusen.
5. Lägg browser-/feature-detection i Viewser: använd embedded WebContainer
   när iframe-`credentialless` stöds; visa fallback-iframe när det inte stöds.
6. Lägg en manuell fallback-väg även i Chromium när StackBlitz-embeddet
   fallerar efter timeout.
7. Lägg tester för browserbeslut, fallback-metadata, felvisning och att
   slutpublicerade kund-sajter inte ändras av preview-fallbacken.

## Öppna frågor

- Vilken statisk hosting ska användas först: egen VPS, Cloudflare R2,
  egen CDN eller annan lösning?
- Vilket kostnadstak gäller per build och per månad?
- Vilken preview-TTL ska gälla, och när ska gamla previews rensas?
- Hur ska secrets hanteras så fallback-builden aldrig exponerar privata
  värden i statisk output?
- Räcker statisk export för alla nuvarande starters, eller behöver vissa
  routes renderas via en enkel serverad build i stället?
- Ska Chromium-användare kunna välja statisk fallback manuellt när
  WebContainer är långsam eller trasig?
- Ska fallback-hostingen vara helt separat från framtida publiceringsflöde,
  eller återanvända delar av samma pipeline?

## Vad ADR 0025 inte beslutar

- Ingen implementation av fallbacken i detta steg.
- Ingen ändring i `apps/`, `packages/`, `scripts/build_site.py` eller
  `packages/preview-runtime/`.
- Ingen stängning av B125; posten kan stängas först när fallbacken är
  implementerad och verifierad.
- Ingen ändring av slutpublicerade kund-sajter eller deras browserstöd.
- Ingen ny default bort från StackBlitz/WebContainer för Chromium.
