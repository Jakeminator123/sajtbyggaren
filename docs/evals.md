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
| `quick` | `atelje-bird`, `painter-palma`, `foto-ram`, `arcade-hall` | `--skip-build` (filer skrivs, npm hoppas över) |
| `full` | `painter-palma`, `atelje-bird` | Inget `--skip-build` (`npm install` + `npm run build`) |

`quick` tar i regel under en minut. `full` kan ta flera minuter per case
eftersom npm körs på riktigt.

### Output

För varje suite-körning skrivs en summary till
`data/evals/eval-runs/<evalRunId>.json`. Innehåll per case:

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

## Manuella scorecards

Manuella 1-10-poäng sparas separat, en fil per suite-körning, under
`data/evals/manual-scorecards/<evalRunId>.json`. Filerna är
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

## Avgränsningar

- Ingen `quality-result.json`-ändring. Numerisk score blandas inte in i
  Quality Gate.
- Ingen ändring i `scripts/build_site.py` eller i
  `packages/generation/`. Eval-suite är en read-only iakttagare.
- Ingen CI-integration i V1. Suiten körs manuellt när operatören vill
  se om kedjan lever.
