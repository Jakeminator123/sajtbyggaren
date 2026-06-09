---
status: active
owner: backend
truth_level: summary
last_verified_commit: f56ac30
---

# Evals — observabilitet, inte kvalitetsbetyg

Det här dokumentet beskriver hur Sajtbyggarens lokala eval-suite fungerar
just nu och vilket format manuella scorecards har. Det är inte ett
generellt eval-ramverk — det är en liten observability-loop ovanpå
`scripts/build_site.py` så att operatören snabbt kan se om kedjan lever.

## Vad evals är (och inte är)

Evals är just nu smoke- och regressionssignal. De svarar på frågan
"kedjan från Project Input till färdig Next.js-sajt fungerar än, och
vilken fas levereras av riktig LLM kontra mock/pinned?".

De är inte ett 1-10 kvalitetsbetyg. Numerisk poängsättning av faktisk
hemsidekvalitet sker manuellt i ett separat scorecard (se nedan), inte i
`quality-result.json`.

## CLI

```
python scripts/run_eval_suite.py quick
python scripts/run_eval_suite.py full
```

### Lägen

| Mode | Cases | Build |
| ---- | ----- | ----- |
| `quick` | `atelje-bird`, `painter-palma`, `foto-ram`, `arcade-hall`, `cafe-bistro`, `clinic-tandvard`, `advokatbyra-novum`, `studio-bjork` | `--skip-build` (filer skrivs, npm hoppas över) |
| `full` | `painter-palma`, `atelje-bird`, `cafe-bistro`, `clinic-tandvard`, `advokatbyra-novum`, `studio-bjork` | Inget `--skip-build` (`npm install` + `npm run build`) |

`quick` tar i regel under två minuter. `full` kan ta flera minuter per
case eftersom npm körs på riktigt.

Full-suite täcker en case per aktiv on-disk-scaffold:

| Scaffold | Case | Starter | Variant |
| -------- | ---- | ------- | ------- |
| `local-service-business` | `painter-palma` | `marketing-base` | `nordic-trust` |
| `ecommerce-lite` | `atelje-bird` | `commerce-base` | `clean-store` |
| `restaurant-hospitality` | `cafe-bistro` | `marketing-base` | `warm-bistro` |
| `clinic-healthcare` | `clinic-tandvard` | `marketing-base` | `clinic-calm` |
| `professional-services` | `advokatbyra-novum` | `marketing-base` | `legal-classic` |
| `agency-studio` | `studio-bjork` | `marketing-base` | `studio-monochrome` |

Det är fortfarande lika många full-cases som scaffolds som har en aktiv
on-disk-implementation; placeholder-scaffolds (som idag faller tillbaka
till `local-service-business`) täcks inte separat. CLI-help-texten
(`python scripts/run_eval_suite.py --help`) listar de aktuella cases
dynamiskt så denna tabell ska aldrig vara source of truth.

Den aktuella case-listan har sin kodkälla i `QUICK_CASES` och
`FULL_CASES` i `scripts/run_eval_suite.py`. Backoffice-knappar och
CLI-hjälptext läser samma listor så antal och namn inte driver isär.

### Output

För varje suite-körning skrivs en summary till
`data/evals/summaries/suite/<evalRunId>.json`. Full-mode genererad
Next.js-output landar parallellt under
`data/evals/artifacts/suite/<evalRunId>/<siteId>/` så varje case kör en
ren `npm install` utan att återanvända ett tidigare suite-pass
`node_modules`. Innehåll per case:

- `siteId`, `dossierPath`, `runId`, `skipBuild`, `elapsedSeconds`
- `briefSource`, `planSource`
- `scaffoldId`, `variantId`, `starterId`
- `selectedDossiers`, `rejectedCapabilities`
- `qualityStatus`, `qualityChecks`
- `repairStatus`, `buildStatus`
- `error` (null om allt gick igenom)

Dessa nio spårfält är de operatören tittar på för att avgöra om en run
använde riktig `briefModel`, mock-fallback, pinned plan eller
deterministisk build.

## Golden path scorecard

`scripts/run_golden_path_eval.py` är det deterministiska grind-lagret för
de fyra baseline-prompter som produktkompassen listar. Defaultläget är
offline: scriptet kräver ingen `OPENAI_API_KEY`, kör ingen npm-build och
bygger inga embeddings.

Körning:

```bash
python scripts/run_golden_path_eval.py --mode deterministic
```

Output ligger uppdelat i två rötter (post evals-folder-plan):

- `data/evals/summaries/golden-path/<evalId>.json` — maskinläsbar
  summary med alla fyra case.
- `data/evals/summaries/golden-path/<evalId>.md` — operatörsrapport med
  scorecard, embeddings-status och starter-/dossier-status.
- `data/evals/artifacts/golden-path/<evalId>/` — isolerad arbetsmapp
  med `prompt-inputs/`, `runs/`, `generated/`, `cases/`.

Retention styrs av `SAJTBYGGAREN_MAX_GOLDEN_PATH_EVALS`; gamla `<evalId>/`-
mappar och matchande `<evalId>.json`/`.md` rensas i samma pass.

Baseline-prompter:

1. "Skapa en hemsida för en elektriker i Malmö."
2. "Skapa en hemsida för en frisörsalong i Göteborg."
3. "Skapa en hemsida för en naprapatklinik i Stockholm."
4. "Skapa en hemsida för en liten e-handel som säljer keramik."

Score-dimensioner:

| Dimension | Vad den fångar |
| --- | --- |
| `clarity` | Förstår man direkt vad företaget gör? |
| `cta` | Finns tydlig nästa handling? |
| `trust` | Känns företaget legitimt och trovärdigt? |
| `industryFit` | Passar struktur och route-val branschen? |
| `copySpecificity` | Undviker generisk AI-copy och placeholder-känsla? |
| `mobileFirstFirstImpression` | Finns rimligt hero/section-flöde för första skärm? |
| `contactPath` | Fungerar kontaktvägen och är den branschanpassad? |
| `scaffoldFit` | Är vald scaffold, variant och starter rimliga? |

Gate-regel för embeddings enligt ADR 0026:

- snitt över fyra case måste vara minst 7.0/10
- inget enskilt case får vara under 6.5/10
- annars sätts `embeddingsReadiness` och `nextGate` till `no-go`

Rapporten innehåller också read-only inventory:

- vilka scaffolds, starters och dossiers som finns på disk
- vilka scaffolds/starters som är runtime-aktiva via befintlig mapping
- vilka starters/scaffolds som bara finns på disk
- vilka baseline-case som först behöver bättre signal/copy/render i stället
  för embeddings eller starter-importer

`--mode real-llm` finns som explicit opt-in för framtida jämförelse och
kräver `OPENAI_API_KEY`. Defaultläget ska vara det som grind-agenter kör.

## Manuella scorecards

Manuella 1-10-poäng sparas separat, en fil per suite-körning, under
`data/evals/summaries/manual-scorecards/<evalRunId>.json`. Filerna är
gitignorerade — mappen behålls i git via en `.gitkeep`.

Sex dimensioner plus en fritext-notering per case:

```json
{
  "evalRunId": "eval-20260525T064500.123Z-a1b2c3d4",
  "createdAt": "2026-05-25T06:45:00.123Z",
  "items": [
    {
      "siteId": "painter-palma",
      "runId": "20260525T...-painter-palma",
      "clarity": 7,
      "trust": 8,
      "design": 6,
      "cta": 5,
      "copy": 7,
      "overall": 7,
      "notes": "Hero ok, footer-länkar trasiga"
    }
  ]
}
```

| Dimension | Vad operatören tittar på |
| --------- | ------------------------ |
| `clarity` | Är erbjudandet tydligt på första skärm? |
| `trust` | Förtroende — sociala bevis, kontakt, profil. |
| `design` | Visuell helhet, typografi, hierarki. |
| `cta` | Tydlig nästa-handling, inte gömd i footer. |
| `copy` | Texterna känns naturliga, inte AI-mall. |
| `overall` | Helhetsintryck (inte ett medelvärde av övriga). |
| `notes` | Fritext, det operatören vill komma ihåg. |

Alla värden är heltal 1-10. `notes` är valfri men rekommenderad.

## Var det körs ifrån

Backoffice-vyn "Evals och telemetri" (Streamlit) har två knappar som
spawnar `scripts/run_eval_suite.py` som subprocess och visar den senaste
suite-körningens summary + ett scorecard-formulär per case. Scriptet är
också körbart direkt från terminal — backoffice är ett tunt UI-lager
ovanpå.

## Scaffold selection probe

`scripts/run_scaffold_selection_probe.py` är en separat liten observability-
loop som svarar på en specifik fråga: **vilka scaffolds väljer planern
faktiskt när man pekar verkliga prompts på den?** Det är ortogonalt mot
eval-suiten ovan — den proben kör `scripts/dev_generate.py` (inte
`scripts/build_site.py`) så `planSource` blir `real` istället för
`pinned`.

### Vad den testar

För varje scaffold som listas i
`governance/policies/scaffold-contract.v1.json` (`primaryScaffoldRegistry`)
finns ett kort representativt prompt. Proben:

1. Kör `dev_generate.py "<prompt>" --phase all` (mock-build, ingen npm).
2. Läser `data/runs/<runId>/site-brief.json` och `site-plan.json`.
3. Registrerar `scaffoldId`, `variantId`, `starterId`,
   `selectedDossiers`, `rejectedCapabilities`, `briefSource`,
   `planSource`, samt om scaffolden faktiskt har en katalog på disk
   under `packages/generation/orchestration/scaffolds/<id>/`.
4. Skriver en summary till
   `data/evals/summaries/scaffold-probe/<probeId>.json` och en parallell
   markdown-rapport `<probeId>.md`.

Syftet är att synliggöra skillnaden mellan **scaffolds som finns i
registry** (14 i nuläget) och **scaffolds som planern kan välja**
(de med `scaffold.json` på disk — `load_scaffold_registry` skippar
placeholders). Placeholder-fall faller idag tillbaka till
`local-service-business`; proben gör det matningsmässigt synligt.

### Hur man kör

```
python scripts/run_scaffold_selection_probe.py
```

Förutsättning: `OPENAI_API_KEY` måste vara satt — annars kör `briefModel`
och `planningModel` mock och proben mäter inte LLM-val. Total körtid
är ungefär 14 × 15 s = 3-4 minuter.

Användbara flaggor:

- `--runs-dir <path>` — override för var enskilda runs hamnar.
- `--evals-dir <path>` — override för var summary-/rapportfilerna hamnar.
- `--report <path>` — explicit markdown-rapport-sökväg.
- `--quiet` — bara skriv ut `probeId=<id>` på stdout.

### Output

Per case loggas:

- `promptId`, `prompt`
- `expectedScaffold` + `expectedHasDirectory` / `expectedHasScaffoldJson`
  / `expectedHasStarterMapping`
- `runId`
- `briefSource`, `planSource`
- `scaffoldId`, `variantId`, `starterId`
- `selectedDossiers`, `rejectedCapabilities`
- `selectedMatchesExpected` (boolean)
- `comment` — kort kategorisering ("planner picked the intended
  scaffold" / "registry-placeholder (no directory on disk)" / etc.)

Outputs ligger under `data/evals/summaries/scaffold-probe/` och är
gitignorerade på samma sätt som övriga eval-artefakter — mappen behålls
via `.gitkeep`.

## Avgränsningar

- Ingen `quality-result.json`-ändring. Numerisk score blandas inte in i
  Quality Gate.
- Ingen ändring i `scripts/build_site.py` eller i
  `packages/generation/`. Eval-suite och scaffold-proben är read-only
  iakttagare.
- Ingen CI-integration i V1. Suiten och proben körs manuellt när
  operatören vill se om kedjan lever.
