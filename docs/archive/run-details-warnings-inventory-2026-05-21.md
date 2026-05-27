# Run Details warnings-inventering

HEAD: 8ba2b201d27af2878731ff25286d5bb3b5c6fe40

## Existerande warning-fält

### Site-plan

- `pageIntentWarnings`: array — emitteras av
  `packages/generation/planning/plan.py:_page_intent_warnings()` när
  `wizardMustHave` från prompt-meta innehåller en sida som har route-intent
  men vald scaffold saknar motsvarande path i `routePlan`.
  - Format:
    `{"page": "...", "expectedPath": "...", "reason": "..."}`
  - Schema: `governance/schemas/site-plan.schema.json` låser `page`,
    `expectedPath` och `reason`.
  - Flöde: `scripts/prompt_to_project_input.py` skriver `wizardMustHave`
    till meta-sidecaren, `scripts/build_site.py` läser den via
    `_prompt_meta_wizard_must_have()`, skickar den till `produce_site_plan()`
    och kopierar sedan `site_plan["pageIntentWarnings"]` till
    `build-result.json`.
  - Visas i dag: Backoffice visar fältet som rå JSON i Engine Runs-fliken
    "Site Plan + Package". Run Details laddar `site-plan.json` men renderar
    inte `pageIntentWarnings` strukturerat i `SitePlanSection`.

- `selectedDossiers.rejected`: array — emitteras av
  `packages/generation/planning/plan.py:filter_capabilities()` och bevaras
  via `_selected_dossiers_payload()` när en requested capability saknar
  Dossier, saknas i capability-map eller pekar på disabled default Dossier.
  - Format: `{"id": "...", "reason": "..."}`
  - Schema: `governance/schemas/site-plan.schema.json` accepterar detta
    under object-formen av `selectedDossiers`.
  - Visas i dag: Backoffice visar rå JSON. Run Details visar scaffold,
    variant, starter och routePlan, men inte `selectedDossiers` eller
    `selectedDossiers.rejected`.

- `planSource`: string och `planError`: string | null — emitteras av
  `produce_site_plan()` som sanningsfält för planner-vägen. `planSource` kan
  vara `real`, `mock-no-key`, `mock-llm-error`, `mock-pre-sprint-2b` eller
  `pinned`; `planError` sätts vid fallback efter planningModel-fel.
  - Visas i dag: Backoffice visar rå JSON. Run Details renderar inte
    `planSource` eller `planError`.

- `fallbackWarnings`: finns inte i `site-plan.json` i dagens kontrakt.
  Namnet finns i Discovery Decision-sidecaren, se "Sidecar-meta" nedan.

### Build-result

- `status`: string — emitteras av `scripts/build_site.py` som
  buildens sammanfattande status. Värdet `degraded` används som varning när
  Quality Gate rapporterar mjuka fel, medan `failed` används för blockerande
  fel. `skipped` används när build körs med `--skip-build`.
  - Visas i dag: Run History visar amber status-dot för `degraded` och
    `warning`; PromptBuilder visar "Build klar med varning" för `degraded`.
    Run Details visar status-badge i `BuildSection`.
  - Backoffice: Engine Runs visar hela `build-result.json` som rå JSON.

- `pageIntentWarnings`: array — kopia av `site-plan.json:pageIntentWarnings`
  som skrivs av `scripts/build_site.py:write_build_result()`.
  - Format: samma som site-plan.
  - Visas i dag: Backoffice visar rå JSON under "Build Result". Run Details
    läser `build-result.json` men renderar inte detta fält i `BuildSection`.

- `placeholderContactFields`: array — emitteras av
  `scripts/build_site.py:_prompt_meta_placeholder_contact_fields()` när
  meta-sidecaren innehåller kända kontaktfält som fylldes med B88-
  platshållare.
  - Tillåtna fält i buildern: `phone`, `email`, `addressLines`,
    `openingHours`.
  - Visas i dag: Run Details `BuildSection` renderar en amber varningsruta
    med `data-testid="placeholder-contact-warning"` och texten
    "Kontakt-fält är platshållare: ...". Backoffice visar rå JSON.

- `placeholderContactMessage`: string — emitteras samtidigt som
  `placeholderContactFields` av
  `scripts/build_site.py:_placeholder_contact_warning_message()`.
  - Format: engelskspråkig operatörsrad, till exempel
    "Contact fields phone, email are placeholder values - operator must fill
    these before publishing."
  - Visas i dag: Backoffice visar rå JSON. Run Details använder i praktiken
    `placeholderContactFields` och renderar egen svensk text, inte detta
    meddelandefält.

- `npmSteps[].ok` och `npmSteps[].logExcerpt`: array med buildsteg — skrivs
  av builderns npm-körning. Ett steg med `ok=false` är en konkret
  fel-/varningssignal för builddiagnos.
  - Visas i dag: Run Details `BuildSection` listar `npmSteps`; vid
    `logExcerpt` visas utdraget i en `pre`-ruta. Backoffice visar rå JSON.

- `codegen.riskNotes`: array — emitteras av
  `packages/generation/codegen/` via `scripts/build_site.py` när
  codegenModel-vägen har risknoteringar. Deterministisk/mock-väg lämnar den
  tom.
  - Format: `string[]`, policy cap 0-3 enligt ADR 0017 och Pydantic-modellen.
  - Visas i dag: Run Details `CodegenSection` renderar listan under rubriken
    `riskNotes:`. Backoffice visar rå JSON.

- `codegen.error`: string — optional, sätts när codegen-resultatet har ett
  fel men build-resultatet ändå skrivs.
  - Visas i dag: Run Details `CodegenSection` renderar `error:` i röd ruta.
    Backoffice visar rå JSON.

### Quality-result

- `status`: string — emitteras av
  `packages/generation/quality_gate/gate.py`. `degraded` betyder att bara
  mjuka checks fallerade; `failed` betyder blockerande typecheck eller
  build-status.
  - Visas i dag: Run Details `QualitySection` visar status-badge. Backoffice
    visar rå JSON och trace-vyn kan visa varnings-/felstatus från events.

- `checks[].findings`: array — emitteras av Quality Gate-checkarna:
  - `typecheck`: TypeScript-rader, cappade till 50.
  - `route-scan`: saknade route-filer eller routes utan default export.
  - `build-status`: misslyckade npm-steg.
  - `policy-compliance`: förbjudna `.env`-filer i genererad output.
  - Visas i dag: Run Details `QualitySection` visar upp till fem findings
    per check och en "... och N till"-rad. Backoffice visar rå JSON.

- `checks[].detail`: string — kort operatörssammanfattning per check.
  - Visas i dag: Backoffice visar rå JSON. Run Details visar inte `detail`
    när det finns findings; komponenten visar namn, status och findings.

- `summary`: string — enradssammanfattning från Quality Gate.
  - Visas i dag: Backoffice visar rå JSON. Run Details renderar inte
    `summary`.

### Repair-result

- `status`: string — emitteras av
  `packages/generation/repair/repair.py`. Varningsrelevanta värden är
  särskilt `no-fix-applied` och `partial-fix`.
  - Visas i dag: Run Details `RepairSection` visar status-badge.
    Backoffice visar rå JSON.

- `remainingErrors`: array — emitteras av Repair Pipeline som ofixade
  Quality Gate-fynd i formatet `<check-name>: <finding>`.
  - Visas i dag: Run Details `RepairSection` renderar upp till fem rader i
    röd text och en "... och N till"-rad. Backoffice visar rå JSON.

- `reason`: string — operator-facing förklaring till repair-status.
  - Visas i dag: Backoffice visar rå JSON. Run Details renderar inte
    `reason`.

- `mechanicalFixesApplied[]` / `llmFixesApplied[]`: arrays — inte rena
  warnings, men kan bära misslyckade fixförsök via `success=false` och
  `detail`.
  - Visas i dag: Run Details listar `mechanicalFixesApplied`, men den
    nuvarande TS-typen läser äldre/alternativa fält (`status`,
    `description`) snarare än schemafält som `success` och `detail`.
    Backoffice visar rå JSON.

### Sidecar-meta

- `placeholderContactFields`: array — skrivs av
  `scripts/prompt_to_project_input.py` i prompt-input meta-sidecaren när
  kontaktfält fyllts med fallbackvärden. `scripts/build_site.py` filtrerar
  listan till kända fält och kopierar den till `build-result.json`.
  - Visas i dag: indirekt i Run Details via `build-result.json`.
    Backoffice Engine Runs läser inte prompt-input meta-sidecaren i sin
    run-vy.

- `wizardMustHave`: array — skrivs av `scripts/prompt_to_project_input.py`
  från discovery payload och används av buildern för att skapa
  `pageIntentWarnings`.
  - Visas i dag: indirekt som `pageIntentWarnings` i `site-plan.json` och
    `build-result.json`, men Run Details renderar inte varningen
    strukturerat.

- `discoveryDecision.fallbackWarnings`: array — emitteras av
  `packages/generation/discovery/resolve.py` och skrivs som del av
  `discoveryDecision` på meta-sidecaren. Follow-up-flödet ärver fältet när
  ingen ny discovery payload finns.
  - Format enligt `governance/schemas/discovery-decision.schema.json`:
    `{"code": "...", "message": "...", "categoryId"?: "...",
    "scaffoldId"?: "...", "capabilityId"?: "...", "dossierId"?: "..."}`
  - Koder i schemat: `category-unknown`, `category-planned`,
    `category-fallback`, `category-disabled`, `scaffold-runtime-missing`,
    `variant-missing`, `starter-mapping-missing`, `capability-unknown`,
    `capability-gap`, `dossier-missing`.
  - Koder som resolvern tydligt emitterar i dag: category-varianterna,
    `starter-mapping-missing`, `capability-unknown` och `capability-gap`.
  - Visas i dag: Backoffice Building Blocks visar `fallbackWarnings` i
    Discovery Dry Run och category mapping-tabellen sammanfattar mapping-
    warnings. Run Details och Engine Runs-vyn laddar inte meta-sidecaren och
    visar därför inte dessa run-specifika warnings.

## Var visas warnings idag

### Run Details

- `apps/viewser/components/run-history.tsx`
  - `RunHistory` visar bara run-meta från `apps/viewser/lib/runs.ts`.
  - `listRuns()` läser `build-result.json` men plockar bara `status`,
    `siteId`, `projectId`, `version` och filesystem-tid. Inga warning-arrays
    förs in i historikraden.
  - `StatusDot` färgar `degraded` och `warning` amber.

- `apps/viewser/components/run-details-panel.tsx`
  - `BuildSection`:
    - visar `build.status` med `StatusBadge`.
    - renderar `placeholderContactFields` som explicit amber warning-ruta i
      början av Build-kortet.
    - listar routes och npmSteps, inklusive `logExcerpt`.
    - renderar inte `build.pageIntentWarnings`.
  - `SitePlanSection`:
    - visar scaffold, variant, starter och routePlan.
    - renderar inte `sitePlan.pageIntentWarnings`, `selectedDossiers.rejected`,
      `planSource` eller `planError`.
  - `QualitySection`:
    - visar Quality Gate-status.
    - renderar `checks[].findings` under respektive check.
    - renderar inte `checks[].detail` eller `summary` separat.
  - `RepairSection`:
    - visar Repair Pipeline-status.
    - listar `mechanicalFixesApplied`.
    - renderar `remainingErrors` i rött.
    - renderar inte `reason`.
  - `CodegenSection`:
    - renderar `codegen.riskNotes`.
    - renderar `codegen.error` i röd ruta.

### Backoffice

- `backoffice/views/engine_runs.py`
  - Engine Runs listar förväntade artefakter och visar `site-plan.json`,
    `generation-package.json`, `build-result.json`, `repair-result.json` och
    `quality-result.json` via `st.json(..., expanded=False)`.
  - Det finns ingen specialrendering för `pageIntentWarnings`,
    `placeholderContactFields`, `riskNotes`, `findings` eller
    `remainingErrors`; operatören måste öppna JSON.

- `backoffice/views/_trace.py`
  - Trace-vyn klassar events som `warning` när status eller text innehåller
    warning/degraded-token.
  - Den visar metricen "Varningar", expanderar faser med varningar och
    renderar warning-events med `st.warning`.
  - Det är event-baserat och inte en direkt rendering av warning-fälten i
    artefakterna.

- `backoffice/views/building_blocks.py` och `backoffice/discovery_control.py`
  - Building Blocks visar Discovery Dry Run-resultat med `fallbackWarnings`
    som rå JSON.
  - `category_mapping_rows()` har en `fallbackWarnings`-kolumn som
    sammanfattar discovery-taxonomy/mapping-varningar per kategori.
  - Detta är governance/discovery-yta, inte Run Details för en faktisk run.

## Var Intent Guard-warning bör hamna

Antagande: Builder lägger `intentGuardWarnings: array` i `site-plan.json`.

Rekommendation:

1. Rendera `intentGuardWarnings` i `RunDetailsPanel` -> `SitePlanSection`,
   direkt efter routePlan och före eventuella framtida selectedDossiers-
   detaljer.
2. Följ samma visuella mönster som `placeholderContactFields`: amber border,
   amber bakgrund, kort rubrik och en kompakt lista.
3. Håll Intent Guard separerad från Build/Quality Gate. Det är en planerings-
   och intent-matchningssignal, inte ett npm/buildfel.
4. Om buildern även kopierar fältet till `build-result.json` senare bör UI:t
   välja en canonical källa för rendering. Förslagsvis `site-plan.json` i
   Site Plan-sektionen, för att undvika dubbel visning.

Föreslaget format att stödja i UI:

```json
{
  "intentGuardWarnings": [
    {
      "kind": "page-count-mismatch",
      "expected": "2 pages",
      "actual": "4 routes",
      "reason": "Prompt asked for 2 pages but selected scaffold emits default route set."
    }
  ]
}
```

Text-skiss:

```text
Site Plan
scaffold: local-service-business · variant: nordic-trust · starter: marketing-base

Intent-varningar
- page-count-mismatch: Prompt bad om 2 sidor, men vald scaffold emitterar 4 routes.

routePlan:
- / — home
- /tjanster — services
...
```

Existerande mönster att följa:

- `pageIntentWarnings` är redan planeringsnära och hör semantiskt hemma i
  `SitePlanSection`.
- `placeholderContactFields` visar hur en konkret operator-varning får en
  amber ruta och kort förklaring utan att blockera resten av Run Details.
- `QualitySection` och `RepairSection` bör inte bli catch-all för
  intent-varningar; de är för verifiering och repair efter generering.

## Gaps + nice-to-haves

- Run Details saknar ett sammanhållet warnings-aggregat. I dag måste
  operatören läsa flera sektioner och rå JSON för att förstå total
  varningsbild.
- `pageIntentWarnings` finns i både `site-plan.json` och `build-result.json`
  men renderas inte strukturerat i Run Details. Det är den tydligaste luckan
  för Intent Guard-arbetet att följa upp.
- `selectedDossiers.rejected` är en viktig capability-gap-signal men syns
  inte i Run Details.
- `planError` och `planSource=mock-llm-error` syns inte i Run Details trots
  att de förklarar planner-fallback.
- `fallbackWarnings` från Discovery Decision är run-relevant men lever i
  prompt-input meta-sidecaren, inte i Engine Run-artefaktbundlen som
  `readRunArtefacts()` returnerar. En framtida UI-agent behöver antingen
  läsa meta-sidecaren eller låta buildern kopiera en sammanfattning till en
  run-artefakt.
- Kommande `pageCountWarning` bör vara tydligt avgränsad från
  `intentGuardWarnings`:
  - Om `pageCountWarning` bara gäller numerisk mismatch mellan prompt och
    routes kan den vara en `kind` inom `intentGuardWarnings`.
  - Om den blir ett separat toppnivåfält bör UI:t fortfarande rendera den i
    samma Site Plan-warningblock, men med egen label så operatören ser
    skillnad mellan sidantal, route-intent och övrig intent-matchning.
- Backoffice Engine Runs visar allt som rå JSON. En enkel "Warnings"-
  expander ovanför JSON-flikarna skulle kunna aggreggera `pageIntentWarnings`,
  `placeholderContactFields`, `quality.checks[].findings`,
  `repair.remainingErrors`, `codegen.riskNotes` och framtida
  `intentGuardWarnings`.
