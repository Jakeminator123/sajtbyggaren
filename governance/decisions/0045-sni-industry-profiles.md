# ADR 0045 — Branschberedskap: full SNI-täckning + branschprofiler per huvudgrupp

**Status:** Accepted
**Datum:** 2026-06-10
**Beroenden:** ADR 0024 (Discovery Resolver är canonical söm för
scaffold/variant-val). Referens: `docs/backoffice/industry-coverage.md`
(SNI → kategori → scaffold-kedjan för operatörer) och
[`docs/agent-inbox.jsonl`](../../docs/agent-inbox.jsonl) (topic:
sni-branschberedskap).

## Kontext

Operatören vill att ALLA branscher är förberedda så att varje bransch får en
hemsida anpassad efter sina behov. Repot har sedan tidigare en deterministisk
SNI 2025-spegel (`data/taxonomies/sni/sni-2025.v1.json`, 1 882 items) men:

1. `sni-discovery-map.v1.json` täckte bara ~20 av 87 huvudgrupper — de flesta
   SNI-koder resolvade till `unknown`.
2. Det fanns ingen plats där en bransch behov (sektioner, funktioner,
   copy-vinkel, trust-signaler, primär CTA) kunde uttryckas — anpassningen
   slutade vid kategori-nivån (25 wizard-kategorier).
3. SNI var uttryckligen parkerad som runtime-signal (ADR 0025/0027 noterar
   parkeringen). Wizard-branschsöket matchade bara de 25 kategorierna +
   en handfull synonymer.

Operatörsbeslut 2026-06-10: (a) mappa alla SNI-koder till BEFINTLIGA 25
kategorier först (inga nya scaffolds nu), (b) definiera branschanpassningar
per SNI-huvudgrupp (87 profiler).

## Beslut

1. **Full SNI → kategori-täckning.** `sni-discovery-map.v1.json` (version 2)
   får `divisionMappings` för alla 87 huvudgrupper plus `groupOverrides` där
   en huvudgrupp spänner över flera kategorier (t.ex. 96 konsumenttjänster →
   salon som default, men 961 tvätteri / 963 begravning → business).
   Täckningen låses av test: varje division/group/class/subclass-item i
   SNI-spegeln ska resolva till en kategori som finns i
   `discovery-taxonomy.v1.json` — 0 unknown.
2. **Branschprofiler per huvudgrupp.** Ny policy
   `governance/policies/industry-profiles.v1.json` (+ schema) med en profil
   per SNI-huvudgrupp: `extraCapabilities` (canonical capability-slugs som
   utökar kategorins `requestedCapabilities`), `recommendedPages`,
   `copyAngle`, `toneHints`, `trustSignals`, `primaryCta` (samma etiketter
   som wizardens CTA-val) och `imageryHints`. Profilen väljer ALDRIG
   scaffold/variant/starter/dossier — det avgör Discovery Taxonomy som idag
   (princip ärvd från `sni-discovery-map`-policyn, nu schema-låst även för
   profiler). Skelett genereras deterministiskt av
   `scripts/generate_industry_profiles.py` (merge-läge: kurerade profiler
   skrivs aldrig över); kurering sker direkt i policy-JSON i batchar per
   SNI-avdelning, med `curated`-flaggan som ärlig markör för hur långt
   kureringen kommit.
3. **SNI blir en runtime-signal via Discovery-sömmen (parkeringen hävs).**
   Wizard-payloaden får `answers.sniCode` (payload-schemats `answers` är
   öppet; inget schema-brott). Resolvern (`resolve_discovery`):
   (a) härleder `categoryIds` från SNI-koden NÄR `answers.siteType` är tom
   (wizardens explicita kategori-val vinner alltid), (b) mergar profilens
   `extraCapabilities` med source `taxonomy` efter wizard-valen,
   (c) appenderar copyAngle/trustSignals som bransch-kontext i
   `directives.notesForPlanner` (befintlig, redan plumbad söm till
   planningModel — briefModel-integration är en senare slice) och
   (d) skriver `sniCode` + `industryProfileId` i `DiscoveryDecision`
   (decision-schemat utökas med två optionella fält). Utan `sniCode` eller
   utan profil-träff är beteendet byte-identiskt med idag — ärlig no-op.
4. **Wizard-branschsöket söker hela SNI.** Ny localhost-route
   `/api/sni-search` i viewser läser SNI-spegeln server-side och matchar
   alla 1 882 etiketter (diakritik-okänsligt). Ett SNI-val sätter kategori +
   familj som idag OCH skickar med `sniCode` + förifyller funktions-/CTA-val
   från profilen (operatören kan ändra allt).

## Ärlighetsgrindar

- En profil kan bara begära capabilities som finns i
  `capability-map.v1.json` (testlåst); gap/unknown-klassificeringen i
  resolvern gäller oförändrat så Backoffice ser om en bransch begär en
  capability utan implementerad Dossier.
- Profilens `wizardCategoryId` måste vara identisk med vad
  `resolve_sni_discovery_category` ger för samma kod (testlåst) — en
  profil kan inte smyg-omdirigera en bransch till en annan kategori.
- `curated: false`-profiler bär bara kategori-defaults — de är ärliga
  baslinjer, inte påhittad branschkunskap.

## Konsekvenser

- Alla 1 882 SNI-koder landar i en kategori med scaffold/variant/starter —
  ingen bransch faller till unknown.
- 87 branschprofiler ger varje huvudgrupp en explicit, versionerad plats för
  branschens behov; kurering kan ske inkrementellt utan kodändringar.
- Backoffice SNI-diagnostiken visar 100 % täckning och profil-status.
- `sizePercent`-läget från toolIntent påverkas inte; inga ändringar i
  build/renderers.

## Utanför scope (kommande slices)

- Nya kategorier/scaffolds där SNI visar luckor (operatörens fas 2-beslut).
- briefModel-prompt-integration av copyAngle (planner-vägen via
  notesForPlanner räcker i v1).
- Profiler på SNI-gruppnivå (287) — schemat tillåter framtida
  `groupProfiles` utan brott.
