# Coach: Föreslagen LLM-flöde-arkitektur

Detta är rå-/referensmaterial, inte canonical kontrakt. Canonical läge är
`docs/current-focus.md`, `docs/llm-golden-path-handoff.md` och befintliga
policies/ADR.

> Skiss från en extern coach-/reviewer-LLM som operatören konsulterade
> under planeringen av LLM Golden Path v1. Skissen är en **mental modell**
> som hjälper resonemang om kärnflödet. Den introducerar **inte** nya
> canonical-namn. Flera av de föreslagna objekt-namnen dubblerar
> begrepp som redan finns i repo:t under andra namn — mappningen
> tydliggörs i §"Mappning till befintliga begrepp" nedan.

---

## Kärnprincip

Användarupplevelsen ska kännas som en rak v0/Lovable-liknande linje.
Internt är systemet en pipeline med tydliga artefakter och flera små
beslutspunkter:

```text
Olika ingångar -> samma pipeline -> samma artefakter -> samma versionering -> samma preview
```

Alltså ska följande ingångar **inte** bli separata motorer; de ska alla
mata in i samma kontextobjekt:

- fri prompt
- wizard/discovery
- starter-val
- scaffold-val
- variant-val
- dossier/capability-val
- follow-up
- asset-upload

Detta matchar North Star: småföretagaren ska kunna beskriva sitt
företag, få en trovärdig mobilklar sajt, och förbättra den med
följdprompter utan att systemet tappar kontext eller kvalitet.

## Föreslagen pipeline (12 steg)

Den föreslagna stegordningen, presenterad som mental modell:

```text
1. Request Intake
   v
2. Context Assembler
   v
3. Discovery Resolver
   v
4. Project Input
   v
5. Site Brief
   v
6. Site Plan
   v
7. Dossier / Capability Assembly
   v
8. Generation Package
   v
9. File Generation / Patch Application
   v
10. Quality Gate + Repair
   v
11. Preview Snapshot
   v
12. Version / Run History
```

Det viktiga är att detta är samma pipeline oavsett om användaren börjar
med en fri prompt eller om grunden redan är långt kommen via starter,
scaffold, variant och dossier.

## Steg-för-steg-beskrivning

### 1. Request Intake

Här normaliseras allt som kommer in. Input kan vara:

- `mode`: `"init"` eller `"followup"`
- raw prompt
- discovery payload
- projectId
- baseVersion
- selected starter id
- selected scaffold id
- selected variant id
- selected dossiers
- uploaded assets
- scraped data
- operator pins

Output bör vara ett enda internt objekt — coach-skissen kallar det en
*request envelope*. (Mappar i repo:t till Project Input plus
meta-sidecar; ingen ny canonical-typ behövs.)

Felet i gamla sajtmaskin var att flera initieringsvägar, namn, API:er
och runtime-flöden växte ihop till en svårstyrd massa. Sajtbyggaren
ska ha tydliga begrepp och artefaktkedjor, men governance ska hjälpa
bygget, inte kväva det.

### 2. Context Assembler

Här avgör systemet hur mycket kontext LLM:en får.

**För init:**

- raw prompt
- discovery answers
- taxonomy
- tillgängliga scaffolds
- tillgängliga variants
- starter registry
- capability map
- ev. assets/scrape

**För followup:**

- projectId
- current version
- previous Project Input
- previous Site Brief
- previous Site Plan
- previous Generation Package
- file manifest
- quality result
- preview state
- conversation history
- new user message

Det här är där produkten kan bli mer v0-lik: användaren upplever bara
"chatta vidare", men internt vet systemet exakt vilken version, vilket
run och vilka filer som påverkas.

### 3. Discovery Resolver — inte LLM som arkitekt

Det här är enligt coachen den viktigaste delen.

LLM ska inte på fri hand bestämma scaffold, starter, variant och
dossiers. Den kan föreslå, tolka och fylla i luckor — men den slutliga
mappningen ska vara resolver/governance-styrd.

Discovery Resolver bör ta:

- category
- answers
- assets
- hints
- raw prompt
- scrape/upload-fält
- taxonomy
- scaffold registry
- starter registry
- capability map

och producera en Discovery Decision (canonical) med fält som:

```text
discovery decision:
  categoryIds
  contentBranch
  targetScaffoldId
  selectedScaffoldId
  fallbackScaffoldId?
  selectedVariantId
  expectedStarterId
  requestedCapabilities
  candidateDossiers
  fieldSources
  fallbackWarnings
  operatorReviewRequired
```

Den tydliga modellgränsen bör vara:

- Frontend skickar category, answers, assets och hints.
- Resolvern avgör scaffold, variant och expected starter.
- Planning är canonical för faktisk starter-resolution och capability
  filtering.
- Dossier candidates är inte samma sak som mounted/required dossiers.

Detta är mycket viktigt. En taxonomy kan föreslå candidate dossiers,
men de ska inte automatiskt bli `selectedDossiers.required` bara för
att taxonomy nämner dem.

### 4. Project Input

Project Input är kundens faktiska data och valda bygginriktning.

Det bör innehålla:

- projectId
- siteId
- version
- company
- contact
- location
- services/products
- brand
- conversionGoals
- scaffoldId
- variantId
- starterId / expectedStarterId
- requestedCapabilities
- selectedDossiers
- assets
- source/provenance

Det här ska vara första stora "låset" i flödet.

När en starter/scaffold/variant redan är vald, ska LLM inte börja om.
Den ska få ett Project Input där det står: det här är redan bestämt;
fyll i det som saknas; förbättra copy, struktur och prioritering inom
dessa ramar.

### 5. Site Brief

Här får LLM:en vara stark. Site Brief bör svara på:

- Vad är företaget?
- Vilken målgrupp?
- Vilket förtroende behöver byggas?
- Vad ska besökaren göra?
- Vilken ton?
- Vilka lokala signaler?
- Vilka viktigaste tjänster/produkter?
- Vilka invändningar ska sidan hantera?

Men Site Brief ska inte vara fri arkitektur. Den ska utgå från Project
Input och Discovery Decision. LLM-roll: `briefModel`. Inte "hela
generatorn".

### 6. Site Plan

Site Plan är sid- och sektionsstrukturen:

- pages, routes, sections
- navigation
- CTA-struktur
- contact route
- content priorities
- required components

Här bör systemet vara delvis deterministiskt. Scaffold/starter
bestämmer vilka typer av routes och sektioner som är tillåtna. LLM kan
hjälpa med prioritering, copy-intention och branschlogik, men inte
bryta scaffold-kontraktet.

Exempel:

```text
local-service-business
  -> Hem
  -> Tjänster
  -> Om
  -> Kontakt

ecommerce-lite
  -> Hem
  -> Produkter
  -> Om
  -> Kontakt / Köpintresse
```

### 7. Dossier / Capability Assembly

Här ska dossiers in, men kontrollerat.

I detta flöde definieras:

- **Capability** = vad sajten behöver kunna eller uttrycka.
- **Dossier** = återanvändbart kunskaps- eller funktionspaket som
  hjälper generationen.

Exempel: contact-form, local-seo, service-pages, gallery, testimonials,
opening-hours, products, booking-intent.

Men igen: candidate är inte samma som mounted.

Det ska finnas ett steg som säger:

```text
requestedCapabilities -> selectedDossiers.required/optional -> dossier bundle
```

Inte: "LLM nämnde något -> montera dossier direkt".

### 8. Generation Package

Det här är "arbetsordern" till filgeneratorn. Generation Package
innehåller:

- project input
- discovery decision
- site brief
- site plan
- scaffold spec
- starter spec
- variant tokens
- dossier bundle
- content blocks
- asset manifest
- generation rules

Detta är artefakten som gör flödet reproducerbart. Om något blir fel
ska du kunna fråga "varför blev denna sida så här?" och se kedjan:

```text
Prompt -> Discovery Decision -> Project Input -> Site Brief -> Site Plan -> Generation Package -> filer
```

### 9. File Generation / Patch Application

Här skiljer sig init och followup.

**Init:**

```text
Generation Package -> full generated site
```

**Follow-up:**

```text
current snapshot + user message
  -> followup intent
  -> patch plan
  -> changed artifacts
  -> affected files only
```

Detta är helt centralt. En follow-up ska inte bli en ny init.

Follow-up bör ha egna artefakter. Coachen skissar dem så här (mappar
till befintliga begrepp — se sista sektionen):

```text
followup intent:
  type: copy | design | structure | asset | capability | bugfix | mixed
  targetPages
  targetSections
  requestedChange
  preserveConstraints

patch plan:
  projectId
  baseVersion
  nextVersion
  affectedArtifacts
  affectedFiles
  regenerationMode
  risks
```

Regressionstestet ska låsa att follow-up behåller samma projectId,
bump:ar version, skapar ny run, behåller tidigare val och ändrar rätt
delar utan att börja om från noll.

### 10. Quality Gate + Repair

Quality Gate ska inte bara säga "build grön". Den bör successivt
kontrollera:

- build/typecheck
- route-scan
- saknade sidor
- trasiga länkar
- kontakt-CTA
- mobil layout smoke
- tomma/generiska sektioner
- AI-placeholder-copy
- metadata
- governance/naming

Coachens rekommendation: repair delas på sikt upp i flera roller:

- syntax repair model
- content repair model
- route repair
- quality critic

Men första versionen kan vara enklare:

```text
quality_result.json -> repair_plan.json -> repair_result.json
```

### 11. Preview Snapshot

Preview ska vara ett resultat av artefaktkedjan, inte en separat
produktvärld. Coachen skissar en *preview snapshot*-typ:

```text
preview snapshot:
  projectId
  version
  runId
  files
  routes
  previewUrl / localPath
  runtimeKind
  qualityStatus
```

StackBlitz bör inte kapa LLM-flödet ännu. Den dokumenterade
runtime-stegen är sund:

1. Local/generated preview
2. StackBlitz preview
3. Production-like runtime/deploy check

StackBlitz är bra som användarnära preview/edit-yta, men VM/deploy-
liknande kontroll behövs senare som hårdare verifiering.

### 12. Version / Run History

Det här är limmet mellan init och follow-up. Coachens skiss av minsta
*project version*-kontrakt:

```text
project version:
  projectId
  version
  parentVersion?
  runId
  mode: init | followup
  request envelope
  discovery decision
  project input ref
  site brief ref
  site plan ref
  generation package ref
  file manifest ref
  quality result ref
  preview snapshot ref
```

Det är det här som gör att en framtida agent-/operatörs-yta kan bli
riktigt stark: agenten kan förstå aktuell version, filmanifest,
genererad kod, senaste meddelanden och vad användaren försöker göra.
Den gamla agent-idén från sajtmaskins företrädare bör återanvändas som
produktidé, inte som gammal arkitektur.

## Begreppshierarki: starter / scaffold / variant / dossier

Coachen föreslår tydlig begreppsdelning:

- **Starter** = teknisk bas / implementerbar grund.
  Exempel: `commerce-base`, `service-base`, `content-base`.
- **Scaffold** = sajttypens struktur och kontrakt.
  Exempel: `local-service-business`, `ecommerce-lite`, `clinic`,
  `restaurant`.
- **Variant** = visuell riktning inom scaffold.
  Exempel: `nordic-trust`, `clean-store`, `premium-local`.
- **Dossier** = återanvändbar capability- eller kunskapsmodul.
  Exempel: `local-seo`, `contact-form`, `testimonials`,
  `service-pages`.
- **Project Input** = kundens data plus valda/pinnade byggblock.
- **Site Brief** = LLM-tolkad företagsstrategi/content brief.
- **Site Plan** = konkret sidstruktur.
- **Generation Package** = komplett arbetsorder till generatorn.

En grundsajt som redan startats från starter + scaffold + variant +
dossier ska gå in ungefär här:

```text
request envelope
  v
Discovery Resolver validerar pins
  v
Project Input är redan delvis rikt
  v
LLM skapar/förbättrar brief och copy
  v
Plan/Package/Files
```

Och INTE här:

```text
Fri LLM-prompt som själv gissar allt från noll
```

## LLM-roller (förslag, inte canonical kontrakt)

En enda prompt ska inte ta allt. Coachen rekommenderar separata
roller/kontrakt, även om vissa kan dela modell bakom kulisserna:

1. `briefModel` — tolkar företag, erbjudande, målgrupp, tonalitet,
   lokala signaler.
2. `contentModel` — konkret copy för hero, sektioner, tjänster, CTA,
   metadata.
3. `followupIntentModel` — klassar följdprompt: copy, design,
   structure, asset, capability, bugfix.
4. `patchPlanModel` — föreslår vilka artefakter/filer som ska ändras.
5. `repairModel` — fixar quality/build/content-problem inom tydlig ram.
6. `qualityCriticModel` — bedömer output mot quality traits.

Det som inte ska vara LLM-roll i första hand:

- scaffold resolver
- starter resolver
- variant validation
- capability map validation
- dossier mounting
- versioning
- run identity
- file path safety
- governance checks

De ska vara deterministiska.

## Är det dokumenterade flödet bra?

Coachens bedömning: **8/10 som riktning**.

**Styrkorna:**

- Rätt North Star.
- Prioritering av `prompt -> hemsida -> preview -> följdprompt -> ny version`.
- Sajtmaskin som referens, inte som arkitektur att kopiera.
- Artefakter som Project Input, Site Brief, Site Plan, Generation
  Package, Quality Result.
- Början på separation av starter/scaffold/variant/dossier.
- Förståelse att v0/Lovable är kvalitetsribba, inte exakt produktmall.

**Svagheterna/riskerna:**

- Discovery/logik kan fortfarande bli splittrad mellan frontend,
  backend och governance.
- LLM kan få tolka saker som borde vara deterministic.
- Candidate dossiers kan blandas ihop med selected/mounted dossiers.
- Follow-up kan råka bli historisk/ärvd kontext utan tydlig markering.
- För många features runt runtime/auth/deploy/backoffice kan kapa
  kärnflödet.

Det positiva är att senare notes visar att discovery/provenance-frågorna
redan verkar vara i rätt riktning: `selectionSource`, disabled
fallback, `operatorReviewRequired`-brus, tie-break och
`inheritedFromVersion` har identifierats som rätt sorts saker att fixa
i resolvern.

## Slutlig arkitekturprincip (citat)

Coachen rekommenderade följande styrregel:

> Sajtbyggaren har en huvudpipeline. Init, follow-up, starter-init,
> scaffold-init, variant-init, dossier-init och asset-driven ändring
> är inte separata generation engines. De är olika ingångar till
> samma pipeline.
>
> LLM:en får tolka, skriva, prioritera, förbättra och föreslå.
> Resolver, planning, versionering, starter/scaffold/variant/dossier-
> validering och quality gates äger de beslut som måste vara
> reproducerbara.

## Mappning till befintliga begrepp

Coach-skissen använder flera objekt-namn som **inte** ska införas som
nya canonical-typer i repo:t — de dubblerar begrepp som redan finns.
Tabellen mappar coachens föreslagna namn (alltid kursiv-prosa nedan)
till de canonical artefakter som redan implementerar samma idé:

| Coach-skiss (mental modell) | Befintligt canonical |
|---|---|
| *request envelope* | Project Input + meta-sidecar |
| *generation context* | Project Input |
| *patch plan* | Follow-up intent + semantic merge i `merge_followup_project_input` |
| *project version* | Immutable `data/prompt-inputs/<siteId>.vN.*` + run-katalog `data/runs/<runId>/` |
| *preview snapshot* | Snapshot under `data/runs/<runId>/generated-files/` + Preview Runtime-abstraktion |
| Discovery Decision | `DiscoveryDecision` (canonical, finns) |
| Followup Intent | `FollowupIntent` (canonical, finns) |
| Site Brief / Site Plan / Generation Package | Canonical, finns |

Att införa *request envelope*, *patch plan*, *project version* eller
*preview snapshot* som nya canonical-namn kräver ADR och skulle vara
dubbletter. Det är **inte** i scope för LLM Golden Path v1.

## Föreslagen första bite (coachens version, ej accepterad)

Coachen föreslog som första uppgift att skapa
`docs/llm-flow-architecture-v1.md` och implementera kontrakt för
*request envelope*, *generation context*, Discovery Decision, Followup
Intent, *patch plan*, *project version*.

Den föreslagna uppgiften reviderades efter Scout-audit:n. Scout
konstaterade att de befintliga canonical artefakterna redan täcker
samma kontrakt under andra namn. Den faktiska första bite blev därför
mycket smalare: lås existerande flöde med en namngiven smoke-test och
en operatör-runbook. Se Scout-audit och PR #124 för det landade
scope:t.
