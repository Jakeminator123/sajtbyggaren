# Branschtäckning i Backoffice

Backoffice har en branschtäckningssektion i Kontrollplan. Syftet är att ge
operatören en sammanhållen bild av vilka branscher som faktiskt har stöd,
vilka som går via fallback och vilka som behöver mer underlag.

Sektionen ändrar inte runtime, policies eller canonical assets. Den läser
befintliga källor och kan bara starta explicita candidate-actions som skriver
till candidate-mappar.

## Kedjan som visas

Branschtäckningen binder ihop följande kedja:

```text
SNI-kod
  -> wizardCategoryId
  -> contentBranch
  -> targetScaffoldId / selectedRuntimeScaffoldId
  -> defaultVariantId / expectedStarterId
  -> requestedCapabilities
  -> Dossier-underlag och candidate-luckor
```

`targetScaffoldId` är målbilden i Discovery Taxonomy. Den får peka mot en
planerad scaffold. `selectedRuntimeScaffoldId` visas bara när Asset Graph
kan se en runtimebar och implementerad scaffold. Det hindrar vyn från att
råka behandla en planerad målbild som faktiskt runtime-stöd.

## Varför SNI inte väljer runtime

SNI är bara en branschsignal. Den kan hjälpa operatören se att SNI 56 pekar
mot restaurang eller att SNI 691 pekar mot juridik, men SNI får inte välja
starter, scaffold, variant eller Dossier direkt.

Discovery Taxonomy är fortsatt bryggan från `wizardCategoryId` till
scaffold, variant, starter och capabilities. Därför visar Backoffice både
SNI-mappningen och downstream-konsekvensen, men utan att införa någon ny
runtime-konsumtion av SNI.

## Coverage, fallback och stöd

Vyn skiljer på flera saker som annars lätt blandas ihop:

- `supportStatus` kommer från Discovery Taxonomy.
- `targetScaffoldStatus` och `selectedScaffoldStatus` kommer från Asset Graph.
- `coverageStatus` är vyns huvudstatus för operatören.
- `needsAttention` och `attentionReasons` visar varför en rad behöver review.

`coverageStatus` kan vara:

- `active_native` — kategorin är aktiv och target-scaffolden är runtimebar.
- `active_fallback` — kategorin är aktiv, men kör via fallback eller har en
  asset-avvikelse.
- `planned` — Discovery Taxonomy säger fortfarande planned.
- `fallback_only` — det finns en runtimebar fallback men ingen native målbild.
- `missing_mapping` — kategorin saknar SNI-mappning.

En rad kan alltså till exempel vara `planned` och samtidigt ha
`needsAttention=true` med `policy_asset_divergence` om scaffolden finns på
disk men taxonomin ännu inte är uppdaterad.

## Recommended actions

Recommended actions är beslutsstöd, inte automatiska ändringar.

- `add_sni_mapping` betyder att SNI-kartan kan behöva breddas.
- `create_variant_candidate` kan skapa en disabled Variant-kandidat under
  `data/variant-candidates/`.
- `create_soft_dossier_candidate` kan skapa en disabled soft Dossier-kandidat
  under `data/dossier-candidates/`.
- `review_capability_gap` betyder att capability-gapet bör granskas manuellt,
  särskilt om det rör hard eller extern integration.
- `review_taxonomy_status` betyder att policy och faktisk asset-status inte
  längre berättar samma sak.
- `create_scaffold_candidate` är read-only i denna version. Ingen scaffold-
  candidate skrivs.
- `promote_planned_scaffold_later` betyder att en planned/fallback-rad kan
  behöva policy-review i en separat sprint.

Candidate-knapparna kräver explicit operatortryck. De använder befintliga
generatorer med `use_llm=False` som default i branschtäckningsvyn och skriver
bara till candidate-mappar. De promoterar aldrig till canonical variants eller
canonical Dossiers.

## Dossiers är capability-underlag

I dagens repo är Dossiers capability-moduler, inte fria branschbeskrivningar.
Branschtäckningsvyn skapar därför bara soft Dossier candidates för säkra
capability-gap. Branschspecifik kunskap som inte är en capability bör få en
egen governance-definierad artefakttyp i en senare iteration, eller en
explicit uppdatering av Dossier-kontraktet.
