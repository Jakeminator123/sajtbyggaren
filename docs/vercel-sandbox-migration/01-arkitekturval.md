# Arkitekturval (besluten per gap)

Varje gap har flera vägar. Skriv en ADR under `governance/decisions/` per beslut
(numren nedan är platshållare — ta nästa lediga). Uppdatera den här filen med valda
nummer när ADR:erna landat.

## G1 — Byggorkestrering (ADR-förslag: bygg-runtime)
- A. Kör Python-byggaren i en sandbox. Ladda upp generation-paketen plus
  `scripts/build_site.py` till en sandbox (`node24` har även python3), kör pipen
  där, skriv ut artefakter till blob-lagring. Minst omskrivning; återanvänder all
  befintlig deterministisk kod.
- B. Slå ihop bygg och preview i samma sandbox. En sandbox bygger sajten och kör
  `next start` direkt — sparar ett hopp och en uppladdning.
- C. Porta byggaren till Node. Störst arbete men tar bort Python helt. Inte
  rekommenderat på kort sikt (pipen är stor och Python-tung).
- Rekommendation: börja med A eller B (Python i sandbox), C som långsiktig möjlighet.

## G2 — Lagring (ADR-förslag: artifact-store)
- Genererade sajter och artefakter -> en object-store. Projektet har REDAN en
  blob-store provisionerad (`BLOB_READ_WRITE_TOKEN` och `BLOB_STORE_ID` drogs av
  `vercel env pull`), och `ASSET_STORE_DRIVER=vercel-blob` finns redan som driver.
  Återanvänd det mönstret för hela bygg-outputen.
- `current.json`-pekaren och run-metadata -> en liten databas eller nyckel-värde-
  lagring (t.ex. en marketplace-provisionerad Postgres, Redis via Upstash, eller
  Edge Config för bara pekaren). Pekaren får inte ligga på lokal disk hostat.

## G3 — Sandbox-sessioner (ADR-förslag: session-store)
- Ersätt minnes-mappen i `apps/viewser/lib/vercel-sandbox-sessions.ts` med ett delat
  lager (siteId eller userId -> sandbox-id, url, createdAt, ttl) som överlever
  instansbyten. SDK:n kan återansluta till en levande sandbox via dess namn, så
  lagra namnet.

## G4 — Auth och tenant (ADR-förslag: auth-och-tenant)
- Ersätt `assertLocalhost` med riktig auth. Plugin-skillen auth beskriver Clerk
  (native i Vercel Marketplace), Descope och Auth0. Lägg auth i middleware och
  scope:a varje siteId och preview till en användare så ingen kan starta eller se
  andras sandboxar.
- Behåll localhost-läget som ett alternativ för lokal drift (env-flagga), men låt
  hostat kräva auth.

## G5 — Snabb uppstart (ADR-förslag: sandbox-snapshots)
- Dagens kallstart är ~25-30 s (`npm install` + `next build` i sandboxen varje
  gång). Plugin-skillen vercel-sandbox visar mönstret: bygg en snapshot som
  pre-installerar beroenden en gång, boota sedan från den (under en sekund).
- För previewen: pre-bygg en bas-snapshot med de vanliga npm-beroendena för den
  genererade mallen, så bara sajtens egna filer plus ett snabbt `next build`
  återstår. Överväg en warm-pool av redan startade sandboxar för "instant preview".

## G6 — Modern preview-yta (ADR-förslag: preview-ux)
- Behåll iframe:n mot vercel.run (funkar i alla webbläsare). Lägg till: streaming av
  byggloggar, element-inspektor och klicka-för-att-redigera (via postMessage mot
  iframe:n), versionshistorik med delbara länkar, och en tydlig "ingen synlig
  ändring"-signal (`appliedVisibleEffect` false; kopplar till bugg B).

## G7 — Kostnad och livscykel (ADR-förslag: sandbox-lifecycle)
- Idle-stop (stoppa sandbox när användaren slutar titta), ttl-städning, kvoter per
  användare, och kostnadsloggning (runnern returnerar redan kostnadssignaler vid
  stopp).

## G8 — De två buggarna
- A: avbrutna byggen ska skriva `build-result.json` även vid hård kill, eller
  markeras failed i stället för att hänga pending eller grå.
- B: riktig layout-codegen (sprint 3B) så layout-följdprompter ger en synlig
  ändring, inte bara copy-direktiv.
