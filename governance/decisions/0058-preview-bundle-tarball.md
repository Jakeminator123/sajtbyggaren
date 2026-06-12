# ADR 0058 — Preview Bundle: tarball-paketerad hostad preview-källa

**Status:** Accepted
**Datum:** 2026-06-12 (uppgift G del G2, operatörsmandat Jakob)
**Beroenden:** ADR 0048 (hostad byggväg i sandbox), ADR 0055 (pre-built
blob-artefakter + sessions-reuse med buildId-invalidering), B195
(manifest-baserad blob-servering), naming-dictionary v41 (`Preview Bundle`,
`HostedSiteCurrentPointer`).
**Implementering:** 2026-06-12, uppgift G-passet på `jakob-be`
(`apps/viewser/lib/hosted-build-runner.ts`,
`apps/viewser/lib/hosted-preview-bundle.ts`,
`apps/viewser/lib/vercel-sandbox-runner.ts`).

## Kontext

Prod-incidenten 2026-06-12 (site-3e7d71ad): hostad preview-uppstart tog 6–7
minuter (totalt 12–13 min med bygget). Rotorsaken var källinhämtningen:
`collectSourceFromBlob` listar och hämtar hundratals enskilda blob-filer
(sedan ADR 0055 även hela den förbyggda `.next`-outputen) in i
serverless-funktionen och skriver dem fil-för-fil in i preview-sandboxen.
Hotfixen samma dag parallelliserade nedladdningen (16 samtidiga fetchar) —
bättre, men fortfarande långsamt och skört: per-fil-vägen skalar med
fil-antalet och lever nära vakterna (4 000 filer / 64 MB).

Samtidigt finns tarball-mönstret redan i kedjan: den hostade byggsandboxen
skapas från build-kontextens tar.gz (`source { type: "tarball" }`,
ADR 0048), och run-artefakterna persisteras som en tarball per version
(B199). Det som saknades var samma paketering för själva preview-källan.

## Beslut

### 1. Byggtid: en `Preview Bundle` per lyckat bygge

Orkestrerings-skriptet i `hosted-build-runner.ts` paketerar — EFTER
fil-för-fil-uploaden och B195-manifestet — EXAKT det publicerade fil-setet
(served-manifest; `.env`-skydd och skip-kataloger är redan applicerade) som
EN tar.gz och publicerar den till blob:

    preview-bundles/<siteId>/<buildId>/preview-bundle.tar.gz

Layoutmotivering (minsta ärliga layout): buildId-scopad path gör varje bundle
immutabel per bygge — ingen stale-overwrite-problematik som `generated/`
(B195) och en atomär pekar-swap (pekaren flyttas först när uploaden
bevisligen lyckades). Gamla bundlar ackumuleras i blob med samma medvetna
prune-skuld som `generated/` och `run-artifacts/` (spårat operatörsbeslut).

Ärlighetsvillkor för publicering:

- bara när fil-setet bär en komplett next-build (`.next/BUILD_ID` — då kan
  preview-sidan lita på att bundle ⇒ pre-built),
- bara inom blob-källans tak (4 000 filer / 64 MB okomprimerat — samma tak
  som `collectSourceFromBlob`-vakterna; höjs de ska det ske på alla ställen
  samtidigt),
- best-effort: ett bundle-fel faller ALDRIG bygget (fil-för-fil-källan är
  redan publicerad) och loggas med orsak.

### 2. Pekaren bär bundle-referensen

`HostedSiteCurrentPointer` (`viewser:site:<siteId>:current`) får de additiva
fälten `previewBundleUrl`, `previewBundleBytes` och `previewBundleFileCount`
— ENBART när uploaden bevisligen lyckades. Det är den minsta utökningen:
pekaren läses redan per preview-start (buildId-invalideringen, ADR 0055) och
bär byggets identitet; bundlen är samma byggs källa.

### 3. Preview-tid: tarball-först med ärlig fil-för-fil-fallback

`vercel-sandbox-runner.ts` provar bundlen FÖRST i den hostade blob-grenen
(via `lib/hosted-preview-bundle.ts`): pekarläsning + HEAD-probe + komprimerat
storlekstak (64 MB, samma anda som blob-källans byte-tak), och skapar vid
träff sandboxen med `source { type: "tarball" }` — ingen blob-listning, inga
per-fil-fetchar, ingen writeFiles-upload; extraktionen sker i sandbox-infran
vid create. Fallback-regler:

- saknad pekare/saknat fält (sajt byggd före detta beslut), död blob eller
  för stor tarball → dagens fil-för-fil-väg, med tydlig logg-rad per orsak,
- bundlen provas bara när pre-built-vägen får användas: den ärliga
  fallbacken till fulla bygg-vägen (`allowPrebuilt=false`) och
  kill-switchen (`VIEWSER_SANDBOX_UPLOAD_BUILT=0`) tar alltid
  fil-för-fil-vägen,
- ett create-kast i bundle-läget (korrupt tarball) är fallback-berättigat —
  fulla vägen provas EN gång, ingen loop (samma mönster som pre-built-
  fallbacken i ADR 0055).

### 4. Mätbarhet

Källinhämtningstiden mäts i BÅDA vägarna (`sourceMs` i timings) och den
strukturerade preview-start-loggraden (`sandbox-preview-start`) bär nu även
vilken källväg som togs (`preview-bundle` | `blob-files` | `disk`), så
vinsten och fallback-frekvensen är verifierbara i runtime-loggarna utan
klient.

## Konsekvenser

- Hostad preview-källinhämtning går från hundratals sekventiella/16-parallella
  blob-fetchar + writeFiles-upload till EN pekarläsning + HEAD + en
  tarball-extraktion i sandboxen — förväntat sekunder i stället för minuter
  (verifieras i prod-loggarna via `sourceMs`/`totalMs` + `source`).
- Dubbel lagring per bygge (per-fil under `generated/` + bundle under
  `preview-bundles/`) är ett medvetet val: per-fil-källan är fallbacken och
  B195-manifestkontraktet förblir orört. Att avveckla per-fil-uploaden är ett
  separat framtida beslut när bundle-vägen är prod-bevisad.
- Blob-prune-skulden växer (en bundle per bygge) — samma spårade
  operatörsbeslut som `generated/`/`run-artifacts/`-prune.
- Sajter byggda före detta beslut fungerar oförändrat (fil-för-fil-vägen).

## Lås

`tests/test_viewser_preview_bundle.py` (source-locks: served-manifest-källan,
taken, best-effort-publiceringen, pekarvillkoret, tarball-först + fallback,
loggning/mätning, read-only-läsaren och KV-nyckel-pariteten) +
`apps/viewser/lib/hosted-preview-bundle.test.ts` (pekar-parsern).
