# ADR 0026 — Embeddings-implementation parkeras tills contract propagation är klar

**Status:** Accepted — operativ parkering
**Datum:** 2026-05-21 (status förtydligad 2026-06-15)
**Beroenden:** ADR 0005 (scaffold-/dossier-modell med embedding-driven
selection), ADR 0012 (vocabulary compression), ADR 0024 (Discovery Resolver).

## Uppdatering (2026-06-15) — parkeringen gäller fortfarande

Status flyttad från `Proposed` till **`Accepted — operativ parkering`**: detta är
inte längre ett förslag utan det gällande, medvetna driftläget. Verifierat mot
koden 2026-06-15 — embeddings är fortfarande INTE byggda i prod-flödet: inga
`embeddingModel`-anrop i `packages/` eller `scripts/`, och `embedding-policy.v1.json`
anropas inte i någon byggväg. Scaffold-/dossier-selection sker deterministiskt
(jfr Discovery Resolver, ADR 0024). **Triggervillkoren nedan är oförändrade** och
avgör fortsatt när parkeringen ska lyftas (notera dock att utbudet vuxit till
6 scaffolds på disk sedan 2026-05-21 — fortfarande långt under 30-enheters-
triggern). Beslutet i sak ändras inte; bara dess status görs ärlig.

## Kontext

Embeddings-policy finns definierad (`governance/policies/embedding-policy.v1.json`)
och låser kontraktet för fem domäner (scaffolds, dossiers, reference-templates,
section-patterns, style-signatures), men implementationen är inte byggd.
`data/embedding-index/`-mappen är gitignored som förberedelse; inga aktiva
`embeddingModel`-anrop finns i prod-flödet idag.

Case 4 sköldpaddssoppa (2026-05-19) gav 5.0/10 trots att `briefModel` fångade
`pageCount`, `tone` och `servicesMentioned` korrekt — root cause är att
downstream-kod ignorerar signalerna:

- B137 (Medel): `company.tagline` läcker rå prompt-/beskrivningstext till
  Hero-sektionen.
- B138 (Medel): `pageCount`-läckage från brief till routePlan — planner
  ignorerar det explicit begärda sidantalet.
- B139 (Låg-medel): `tone`-extraction propageras inte till brand-tokens i
  `variant_css`.
- B140 (Låg): `brand.primaryColorHex` ignoreras av `variant_css` — separat
  data-kanal från B139.
- B141 (Låg-medel): `_assemble_generation_package()` skriver bara
  `siteBriefRef`, inte `siteBrief`-objektet, så downstream-kod läser
  `tone`/`businessType` från en död pipeline.

Embeddings hade adresserat ett annat problem: scaffold-/dossier-/variant-
selection vid växande utbud. Att bygga en ny signal-källa när befintliga
signaler inte ens propageras korrekt genom kedjan är kontraproduktivt.

## Beslut

Vänta med embeddings-implementation tills:

1. B137 + B138 stängda — LLM-output håller hela vägen från brief till
   rendering utan att signaler tappas.
2. B139/B140/B141 stängda eller medvetet parkerade med dokumenterad
   rationale i respektive bugg-post.
3. Mini-eval på 4 baseline-prompts visar ≥7/10 utan regressioner
   (elektriker Malmö, frisör Göteborg, naprapatklinik Stockholm, keramik
   e-handel).
4. Selection-problemet kan isoleras — vilka case som faktiskt skulle
   gynnas av embeddings vs vilka som inte gör det. Idag finns 2 aktiva
   scaffolds och <10 dossiers; manuell mappning räcker.

## Alternativ som övervägdes

| Alternativ | Bedömning |
| --- | --- |
| Bygg embeddings nu parallellt | Risk: lägga till en signal-källa när vi inte ens använder befintliga. Ökad komplexitet utan mätbar nytta förrän kontraktspropagering fungerar. |
| Vänta 6 månader | Risk: dossier-/scaffold-utbudet växer, manuell selection skalar inte. Om utbudet passerar ~30 enheter blir det ohållbart utan retriever. |
| Parkera tills contract propagation klar (detta förslag) | Balans: fokus på kontraktets stabilitet först; embeddings byggs sedan mot ett tydligare och mätbart problem. |

## Konsekvenser

Positiva:

- Fokus på att befintliga signaler propageras korrekt genom hela kedjan
  innan en ny signal-källa introduceras.
- Embeddings byggs sedan mot ett isolerat och mätbart problem i stället för
  som generell "förbättring" utan baseline.
- Undviker att lägga infrastruktur-komplexitet (modellval, index-pipeline,
  cache, TTL) i ett system vars grundläggande kontrakt inte håller.

Negativa:

- Selection-skalning rör sig inte framåt. Om dossier-utbudet växer snabbt
  (>30 enheter) behöver vi accelerera oberoende av contract-propagation-
  status.
- Om contract-propagation-fixen drar ut på tiden förblir embeddings parkerade
  längre än nödvändigt.

## Triggers för att lyfta parkeringen

- Case 4 uppnår ≥6.8/10 i re-eval.
- Fyra demo-case (baseline-prompter) samtliga gröna (≥7/10, inget <6.5).
- Dossier-utbud passerar 30 enheter (oavsett contract-status — skalning
  trumfar).

## Implementation outline (för senare sprint)

1. Indexering: `data/embedding-index/` (redan gitignored, infrastruktur
   förberedd).
2. Embedding-model-roll: registreras i `governance/models.v1.json` med
   kontrakterade parametrar.
3. Retriever-helper: `packages/generation/embeddings/` — indexering +
   sökning + caching.
4. Integration: dossier-rationale + scaffold-rationale i
   `DiscoveryDecision.fieldSources`.
5. Mätbarhet: case-poäng före/efter per scaffold-/dossier-selection.

## Öppna frågor för operatör

- Vilken modell används för embeddings? (lokal vs OpenAI `text-embedding-3-small`
  vs annat.)
- Cache-strategi: eviction-policy, TTL, max index-storlek.
- Cost vs latency-tradeoff vid varje prompt-körning.
- Ska embeddings-scoren exponeras i Backoffice/Doctor som
  selection-diagnostik?

## Vad ADR 0026 inte beslutar

- Ingen implementation av embeddings i detta steg.
- Ingen ändring i `packages/`, `scripts/`, `apps/` eller `backoffice/`.
- Ingen ny policy eller schema — `embedding-policy.v1.json` kvarstår orörd.
- Ingen stängning av selection-relaterade buggar.
- Inget modellval.
