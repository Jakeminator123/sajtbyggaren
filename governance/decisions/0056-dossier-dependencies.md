# ADR 0056 — Dossier-deklarerade dependencies in i genererad package.json

**Status:** Accepted
**Datum:** 2026-06-12
**Beroenden:** ADR 0012 (dossier-klasserna soft/hard), ADR 0053
(hard-dossier-kontrakt + montering i `scripts/build_site.py`), schemat
[`dossier.schema.json`](../schemas/dossier.schema.json) (fältet `dependencies`
finns redan) och agentguiden
[`packages/generation/orchestration/dossiers/AGENT-GUIDE.md`](../../packages/generation/orchestration/dossiers/AGENT-GUIDE.md).
**Implementering:** 2026-06-12 — liten ny modul
[`packages/generation/build/dossier_dependencies.py`](../../packages/generation/build/dossier_dependencies.py),
kirurgisk ändring i `scripts/build_site.py` (`patch_package_json` +
install-grenen) och tester i `tests/test_build_dossier_dependencies.py`.

## Kontext

Schemat `dossier.schema.json` har sedan länge ett `dependencies`-fält (en lista
med strängar), men det konsumeras i dag av noll kod. `patch_package_json` i
`scripts/build_site.py` skriver bara om `name` i den genererade `package.json`,
och hela dependency-setet kommer från starterns committade lockfile via
`npm ci`. En monterad dossier kan alltså leverera komponentfiler men inte de
npm-paket komponenterna behöver.

Operatörsvisionen är att en följdprompt som "lägg in three.js" på sikt ska
kunna uppdatera användarprojektets `package.json` och bygga om. I dag finns
ingen väg dit. Det här beslutet bygger *mekanismen*: en operatörskuraterad,
schema-validerad dossier får deklarera pinnade dependencies som buildern slår
ihop in i den genererade `package.json` för de dossiers som faktiskt monteras
på ett bygge.

Ingen språkmodell väljer dependencies här. Det är förenligt med förbudet i
[`docs/openclaw-workspace/TOOLS.md`](../../docs/openclaw-workspace/TOOLS.md)
("nya dependencies utan policy + operatörsgodkännande"): den
operatörskuraterade, schema-validerade dossier-manifesten *är* den sanktionerade
policy- och godkännandekanalen.

## Beslut

1. **Konsumtion.** I `patch_package_json`-steget slår buildern ihop
   `manifest.dependencies` från alla monterade dossiers in i den genererade
   `package.json`. Hopslagningen sker mot starterns `dependencies` och rör inte
   `devDependencies` eller andra fält. När inget paket lagts till lämnas
   `dependencies` orört, så utan dossier-deklarerade dependencies blir den
   skrivna `package.json` byte-identisk med dagens namn-omskrivning.

2. **Pinnade versioner krävs.** Endast exakt (`1.2.3`) eller tilde (`~1.2.3`)
   accepteras. Caret-intervall (`^1.2.3`), öppna intervall, `*`, dist-taggar
   (`latest`), git/url/workspace-specar och saknad version avvisas som hårt
   byggfel.

   *Motivering:* exakt pin ger full reproducerbarhet; tilde låser fortfarande
   minor och major och släpper bara in patch-uppdateringar (säkerhets-/buggfix),
   vilket håller determinismen acceptabel för en operatörskuraterad post. Caret
   släpper in minor-höjningar och undergräver determinismen — därför avvisat.

3. **Kollision = hårt byggfel, ingen tyst vinnare.** Två monterade dossiers som
   deklarerar samma paket med olika pin, eller en dossier som pinnar ett paket
   som starterns `dependencies` redan har med en annan spec, stoppar bygget med
   ett tydligt felmeddelande. En identisk om-deklaration är en no-op. En dossier
   får alltså aldrig tyst skriva över starterns pinnade `next`/`react`.

4. **Ärlig install-fallback.** När hopslagningen lagt till minst ett paket
   matchar starterns committade lockfile inte längre `package.json`, så `npm ci`
   skulle (korrekt) vägra. Buildern faller då ärligt tillbaka till `npm install`
   och skriver ett trace-event (`npm.install.dependency_drift`, status
   `warning`) så avvikelsen syns i run-historiken. Statusen `warning` valdes
   medvetet framför `degraded` eftersom `degraded` på run-nivå har en egen
   betydelse (route-scan/policy-compliance mjukfel); avvikelsen här är en
   förväntad, neutral notis i samma kategori som `dossier.design_mode`. Utan
   tillagda paket är beteendet oförändrat (`npm ci` när lockfile finns).

## Konsekvenser

- En dossier kan nu leverera både kod och de npm-paket koden kräver, helt
  styrt av operatören via manifesten.
- Builds där en dossier lagt till ett paket går via `npm install` i stället för
  `npm ci`. Det är en medveten, spårad avvikelse, inte en tyst sådan.
- `resend-contact-form` har `dependencies: []` och påverkas inte; dess byggväg
  är oförändrad.

## Icke-scope

- **En språkmodell som väljer eller lägger till dependencies.** Det är
  uttryckligen inte med här. Recept-styrda capabilities (t.ex. `three_3d_scene`)
  som höjer apply-taket är ett senare Fas 3-beslut i
  [`docs/heavy-llm-flow/openclaw-2.0-conductor.md`](../../docs/heavy-llm-flow/openclaw-2.0-conductor.md).
  Det här beslutet levererar bara den deterministiska mekanismen som ett sådant
  framtida recept kan bygga vidare på.
- Ändringar i `devDependencies`, lockfile-generering eller transitive pinning
  utöver den `npm install`-fallback som beskrivs ovan.
