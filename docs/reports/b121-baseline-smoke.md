# B121 Baseline Smoke (PR D)

End-to-end-verifiering av Discovery-kedjan
`overlay -> Discovery Payload -> Discovery Resolver -> Project Input ->
produce_site_plan -> Generation Package -> build/preview` mot fyra
produktbaseline-prompter. Smoke-runs gjordes från
`feature/b121-baseline-smoke` (avgrenad från `main` på `89680fa` — merge
för B121 PR C / Backoffice Discovery Control).

## Resultat per case

| Case | categoryIds | selectedScaffoldId | selectedVariantId | expectedStarterId | starterId (Site Plan / Generation Package) | fallbackWarnings (count + codes) | Build status | Klar för close |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `elektriker Malmö` | `["business"]` | `local-service-business` | `nordic-trust` | `marketing-base` | `marketing-base` / `marketing-base` | 1: `capability-gap` (contact-form) | ok (npm install 34.2 s, npm run build 42.6 s) | yes |
| `frisör Göteborg` | `["salon"]` | `local-service-business` | `nordic-trust` | `marketing-base` | `marketing-base` / `marketing-base` | 2: `capability-unknown` (booking), `capability-gap` (contact-form) | ok (npm run build 51.0 s, andra körningen — se "Notes") | yes |
| `naprapatklinik Stockholm` | `["healthcare"]` | `local-service-business` | `nordic-trust` | `marketing-base` | `marketing-base` / `marketing-base` | 5: `category-planned` (clinic-healthcare), `capability-unknown` (booking, faq), `capability-gap` (contact-form, faq-section) | ok (npm install 32.9 s, npm run build 31.6 s) | yes |
| `liten e-handel som säljer keramik` | `["ecommerce"]` | `ecommerce-lite` | `clean-store` | `commerce-base` | `commerce-base` / `commerce-base` | 3: `capability-unknown` (ecommerce), `capability-gap` (contact-form, payments) | ok (npm install 37.4 s, npm run build 45.1 s) | yes |

Kolumnen "Klar för close" är per-case-svar på frågan "kedjan håller och
ingen unik blocker upptäcktes i detta case".

## Observationer

### 1. `elektriker Malmö` — happy path, business

- `selectionSource = taxonomy`, `targetScaffoldId == selectedScaffoldId`,
  `operatorReviewRequired = false`. Branch `business` är active i
  Discovery Taxonomy.
- `capability-gap` på `contact-form` är förväntat: Capability Map säger
  att Dossiern (`resend-contact-form`, hard) är planerad import för
  Sprint 3 men ännu inte i repo:t.
- `selectedDossiers.required` förblir `[]` på Project Input, och
  `Site Plan.selectedDossiers.rejected` listar `contact-form` med korrekt
  reason. `candidateDossiers` lyfts inte automatiskt in i `required`.
- `fieldSources` visar wizard-vinst på company.name/tagline,
  contact.phone/email/addressLines, requestedCapabilities och
  conversionGoals; brief-vinst på company.story och services. Förväntat.

### 2. `frisör Göteborg` — happy path, salon

- `selectionSource = taxonomy`, branch `salon` är active.
- `mustHave: ["Bokning online", "Kontaktformulär"]` översätts till
  capability-slugs `booking` och `contact-form`. `booking` saknas helt i
  Capability Map, så Discovery Resolver loggar en `capability-unknown`
  warning (inte gap). Det är samma signal som planning får i `Site Plan`
  och flagas i Backoffice — kontraktet håller.
- `operatorReviewRequired = true` enligt resolver-regeln att
  `capability-unknown` triggar review (men inte `capability-gap`).
  Förväntat och samma kontrakt som dokumenterat i resolverns docstring.

### 3. `naprapatklinik Stockholm` — planned/fallback path

- `selectionSource = fallback`, `targetScaffoldId = clinic-healthcare`,
  `selectedScaffoldId = local-service-business`. Detta är exakt det
  scenario som taxonomy-policyn beskriver för `healthcare`: planned
  scaffold, fallback till `local-service-business` med `marketing-base`.
- `fallbackWarnings` innehåller `category-planned` med `categoryId =
  healthcare`, `scaffoldId = clinic-healthcare`. Det matchar
  smoke-kravet att naprapat ska generera `category-planned`-warning.
- Ytterligare warnings (`capability-unknown` för booking + faq,
  `capability-gap` för contact-form + faq-section) är konsistenta med
  Capability Map-läget och dyker upp som rejected i `Site Plan`.
- `operatorReviewRequired = true`. Build körs ändå genom till status =
  ok eftersom fallback-scaffolden är runtime-mappad.

### 4. `liten e-handel som säljer keramik` — happy path, ecommerce

- `selectionSource = taxonomy`, `selectedScaffoldId = ecommerce-lite`,
  `selectedVariantId = clean-store`, `expectedStarterId = commerce-base`.
- Build använder `commerce-base` starter, route-listan visar
  `/`, `/produkter`, `/om-oss`, `/kontakt`. Build status ok.
- `capability-gap` på `payments` (planerad `stripe-checkout` Dossier)
  och `contact-form`, plus `capability-unknown` på det interna
  `ecommerce`-aliaset från `mustHave: ["Webshop / Produkter"]`. Inga
  blockers — branchens taxonomy-mappning, Capability Map och
  rejected-listan är synkade.

### Notes

- Frisör-byggen failade i den första 4-i-rad-runden med
  `Next.js build worker exited with code: 3221226505 and signal: null`
  (Windows STATUS_STACK_BUFFER_OVERRUN, transient Next webpack-worker
  fel som dyker upp när flera Next-builds kör efter varandra på samma
  Windows-host). Omkörning av enbart frisör med samma Project Input
  och samma starter (`marketing-base`) gick till status ok på 51.0 s.
  Felet är miljöberoende, inte ett discovery- eller builder-fynd, och
  blockerar inte B121-stängningen. Värt att notera om vi senare ser det
  igen i CI eller flera Builder-prompter i rad.
- Smoke-runs körde i `init`-läge med `briefSource = real` (riktig
  briefModel-anrop). Discovery-decision skrevs till
  prompt-input meta-sidecaren under en temp-katalog (`%TEMP%`) så
  `data/prompt-inputs/` och `data/runs/` rörs inte i repo:t.
- Resolver fyllde `discoveryDecision` på meta-sidecaren med alla
  schema-obligatoriska fält: `categoryIds`, `contentBranch`,
  `selectedScaffoldId`, `targetScaffoldId`, `selectedVariantId`,
  `requestedCapabilities`, `candidateDossiers`, `fallbackWarnings`,
  `fieldSources`, `selectionSource`, `operatorReviewRequired`,
  `expectedStarterId` och `rationale`.
- För alla fyra case bekräftades: `Project Input.scaffoldId` ==
  `discoveryDecision.selectedScaffoldId`, `Project Input.variantId` ==
  `discoveryDecision.selectedVariantId`,
  `Site Plan.starterId` == `Generation Package.starterId` ==
  `discoveryDecision.expectedStarterId`,
  `selectedDossiers.required = []` (candidateDossiers lyfts inte in
  automatiskt; taxonomyn har också tomma `candidateDossiers` i
  policy-läge idag).

## B121 close-recommendation

Alla fyra produktbaseline-prompter klarar end-to-end-kedjan från
Discovery Payload till färdig Build Result, med korrekt
Discovery Decision, korrekt scaffold/variant/starter-mappning, korrekta
fallback-warnings för planned/fallback-spår och korrekt avgränsning
mellan `candidateDossiers` och `selectedDossiers.required`.
**B121 är close-ready.**

Föreslagen Steward-bump efter PR D merge: flytta B121-raden i
`docs/known-issues.md` från "**PR A + PR B + PR C sealed**, B121 ej helt
stängd förrän Prompt 5 Scout-audit + PR D baseline-smoke" till
**closed/resolved** och ta bort raden ur queue:n i
`docs/current-focus.md`. Uppdatera "Last verified state" till PR D
merge-commit. Inga nya B-id:n behöver öppnas — frisör-Next-worker-felet
är miljöberoende och spåras inte som produktbug.

## Hur smoken kördes

Per case:

```
python scripts/prompt_to_project_input.py "<prompt>" \
    --site-id <smoke-site-id> \
    --output-dir <tempdir>/prompt-inputs \
    --discovery <tempdir>/payloads/<case>.discovery.json
python scripts/build_site.py \
    --dossier <tempdir>/prompt-inputs/<smoke-site-id>.v1.project-input.json \
    --runs-dir <tempdir>/runs \
    --generated-dir <tempdir>/generated
```

Discovery Payload-shape per case följer
`governance/schemas/discovery-payload.schema.json`
(`schemaVersion: 1`, `rawPrompt`, `contentBranch`, `scaffoldHint`,
`answers.{siteType, companyName, offer, mustHave, primaryCta,
contact}`). Wizardens egna `composeMasterPrompt`-text simulerades inte
— Discovery Resolver är canonical för fältval och briefModel anropades
med rå prompt enligt skarpt produktflöde.

Verifierade artefakter per case:

- prompt-input meta-sidecar: `meta.discoveryDecision` (alla
  obligatoriska fält enligt
  `governance/schemas/discovery-decision.schema.json`).
- Project Input: `scaffoldId`, `variantId`, `requestedCapabilities`,
  `conversionGoals`, `selectedDossiers.required = []`.
- `data/runs/<runId>/site-plan.json` (`starterId`, `scaffoldId`,
  `variantId`, `planSource = pinned`, `selectedDossiers.rejected`).
- `data/runs/<runId>/generation-package.json` (`starterId`,
  `scaffoldId`, `variantId`).
- `data/runs/<runId>/build-result.json` (`status`, `npmSteps`,
  `runDurationMs`).

## Guards som följde med

Körningar efter smoke-passet (alla från `feature/b121-baseline-smoke`):

- `python -m ruff check .` — 0 findings.
- `python scripts/governance_validate.py` — 17 policies OK.
- `python scripts/rules_sync.py --check` — alla speglar i synk.
- `python scripts/check_term_coverage.py --strict` — 0 nya kandidater.
- `python scripts/list_open_bugs.py` — bug-scope oförändrad jämfört med
  `main` (27 active, 0 misplaced).
- `python -m pytest tests/test_discovery_resolver.py
  tests/test_discovery_taxonomy.py` — 54 passed.

Inga produktfiler ändrades i denna PR. Resolver, taxonomy, frontend
overlay och Backoffice control är orörda; det enda som tillkommer är
denna rapport.
