# ADR 0024 - Discovery Resolver: canonical terms och seam

**Status:** accepted
**Datum:** 2026-05-18
**Beroenden:** ADR 0012 (vocabulary compression), ADR 0013 (schema-lock
innan Sprint 2B), ADR 0014 (Sprint 2B planning-helper), ADR 0017
(Sprint 3B-next real codegenModel).

## Kontext

B121 dokumenterade en öppen arkitekturskuld: discovery-sanning passerade
fyra implicita lager — `WizardAnswers` → tempfil → `briefModel` →
`_apply_discovery_overrides` — utan en explicit konfliktlösare.
Resultatet var att frontend-overlayen blev en parallell sanning för
`scaffoldId`, `variantId`, `requestedCapabilities` och fältmapping mot
Project Input. Bakgrund:

- `apps/viewser/components/discovery-wizard/wizard-constants.ts` höll
  egen lista över `WizardCategoryId`, `ScaffoldHint` och `defaultVariantId`.
- `scripts/prompt_to_project_input._apply_discovery_overrides` hade en
  hårdkodad ekvivalent som patchade fältvis utan spårning av varför ett
  värde vann.
- Backoffice kunde inte förklara varför ett fält fick sitt värde — det
  fanns ingen ``fieldSources``-modell.

`.cursor/BUGBOT.md` säger att nya canonical termer måste antingen
registreras i `naming-dictionary.v1.json` med en åtföljande ADR, eller
allowlistas under `COMMON_WORDS` i `scripts/check_term_coverage.py`. PR
#34 introducerar fem canonical termer som driver hela seamen mellan
overlay och backend — dessa hör hemma i naming-dictionary, inte i
term-coverage-allowlist, eftersom de är vokabulär operatorn ser i
Backoffice/Doctor och inte bara Python-implementation-symboler.

Denna ADR registrerar termerna och låser seamen så framtida sprintar
inte återinför "discovery overrides"-språket utanför resolvern.

## Beslut

### Fem nya canonical termer i naming-dictionary v17

| Term | Definition (kort) |
| --- | --- |
| `Discovery Payload` | Strukturerad payload från Viewser-overlayen till `POST /api/prompt`. Schema: `discovery-payload.schema.json`. |
| `Discovery Resolver` | Backend-modul i `packages/generation/discovery/resolve.py` som svetsar ihop Discovery Payload, Site Brief-kandidat och Discovery Taxonomy till `(resolved Project Input, DiscoveryDecision)`. |
| `Discovery Decision` | Spårbart resultat från resolvern. Skrivs som extra fält `discoveryDecision` på prompt-input meta-sidecaren. Schema: `discovery-decision.schema.json`. |
| `Discovery Taxonomy` | Canonical mapping från `WizardCategoryId` till `targetScaffoldId`/`activeScaffoldId`/`fallbackScaffoldId`/`defaultVariantId`/`expectedStarterId`/`requestedCapabilities`/`candidateDossiers`. Policy: `discovery-taxonomy.v1.json`. |
| `Field Source` | Strängenum som beskriver var ett Project Input-fält kom från: `wizard`, `scrape`, `brief`, `taxonomy`, `default`, `operator`, `pinned`. Bor i `DiscoveryDecision.fieldSources`. |

Full text finns i `governance/policies/naming-dictionary.v1.json:terms`
(post version 17). Alias `discoveryOverrides`, `discoveryPatcher` och
"discovery-fält-mapping"-formuleringar läggs på `aliasesForbidden` så de
inte återinförs.

### Field-source-prioritet (canonical)

Resolvern följer en deterministisk vinstordning per Project Input-fält:

1. `wizard` — operatorn skrev/klickade explicit i overlayen.
2. `scrape` — wizardfältet är tomt och URL-skrapning fyllde det.
3. `brief` — wizard/scrape är tomma men `briefModel` hade ett värde.
4. `taxonomy` — gäller `scaffoldId`, `variantId`, `expectedStarterId`,
   `requestedCapabilities` (och `candidateDossiers` som separat begrepp).
5. `default` — placeholder från `site_brief_to_project_input` används
   sist och får `default` som fieldSource.
6. `operator` / `pinned` — reserverade för Backoffice-pin (PR C) och
   Project Input `starterId`-pin. Inte använda av resolvern i PR A.

### Seam mot planning

`packages.generation.planning.produce_site_plan` är fortsatt canonical
för faktisk starter-resolution och `filter_capabilities`. Resolvern
levererar bara `expectedStarterId` som *förväntat* värde härlett från
`planning.SCAFFOLD_TO_STARTER`; den tar inte beslut om vilken Dossier
som monteras. `candidateDossiers` är *kandidater* från taxonomin, inte
`selectedDossiers.required`.

### Engine Run-kontraktet förblir åtta filer

`Discovery Decision` är ingen ny Engine Run-artefakt. Den skrivs som
extra fält på den befintliga prompt-input meta-sidecaren
(`data/prompt-inputs/<siteId>.vN.meta.json`). `engine-run.v1.json`
ändras inte.

## Schema-diff

Inga befintliga schemas mutas. Tre nya schemas läggs till:

```
governance/schemas/
  + discovery-payload.schema.json
  + discovery-decision.schema.json
  + discovery-taxonomy.schema.json
```

Naming-dictionary version bumpas:

```
naming-dictionary.v1.json:
  version: 16 → 17
  terms:
    + discoveryPayload
    + discoveryResolver
    + discoveryDecision
    + discoveryTaxonomy
    + fieldSource
```

## Konsekvenser

- `scripts/check_term_coverage.py --strict` accepterar de fem nya
  termerna eftersom de finns i naming-dictionary; Python-implementation-
  symboler som speglar dem (`FallbackWarning`, `FieldSourceLiteral`,
  `SelectionSource`, `SupportStatus`, `TaxonomyCategory`) allowlistas
  separat i `COMMON_WORDS` enligt samma mönster som `PlanningChoice` /
  `RejectedCapability` / `BriefResult`.
- `scripts/prompt_to_project_input._apply_discovery_overrides` är från
  och med PR #34 en tunn wrapper runt `apply_discovery_overrides` i
  resolver-paketet. CLI-kontrakt `--discovery` och stdout-nycklar är
  oförändrade.
- Followup-runs ärver `discoveryDecision` från föregående version via
  `generate_followup`, så Backoffice/Doctor behåller synlighet för
  `categoryIds`, `fieldSources` och `fallbackWarnings` även för v2+.
- Framtida Backoffice-pin (PR C) får skriva `operator`/`pinned` som
  field source utan att schemat behöver bumpas.

## Vad ADR 0024 INTE beslutar

- Ingen ny stor scaffold-arkitektur. `scaffold-contract.v1.json`
  oförändrat.
- Inga nya Dossier-klasser utanför `soft`/`hard`.
- Ingen ändring av operatorflödet (ADR 0012). Resolvern lever inom
  steg 1 ("Init Prompt → Project Input").
- Ingen ändring av Engine Run-kontraktet eller `engine-run.v1.json`.
- Inga frontend-ändringar i `apps/viewser/` (det är PR B).
- Ingen Backoffice-edit av taxonomi (det är PR C).
- Ingen ny PreviewRuntime, auth, billing, deploy eller custom domain.

## Verifiering

- `governance/decisions/`-listan får 0024 som efterföljande ADR efter
  0023.
- `python scripts/governance_validate.py` validerar nya policies +
  schemas (17/17 efter discovery-taxonomy.v1).
- `python scripts/check_term_coverage.py --strict` är grön eftersom de
  fem nya termerna är registrerade.
- `tests/test_discovery_taxonomy.py` och `tests/test_discovery_resolver.py`
  täcker taxonomy coverage, field-source-prioritet, fallback warnings,
  multi-select-tie-break (active > fallback > planned), `disabled`-vägen
  och followup-arvet av `discoveryDecision`.
- `tests/test_naming_consistency.py` säkrar att de fem termerna är
  unika i naming-dictionary.
