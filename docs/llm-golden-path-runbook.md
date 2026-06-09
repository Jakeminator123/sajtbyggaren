---
status: active
owner: backend
truth_level: source
last_verified_commit: f56ac30
---

# Runbook: LLM Golden Path v1

Detta är den smala vertikala skivan av Sajtbyggarens kärnflöde. Hela
kedjan är wired i repo:t; runbooken finns för att nästa agent inte ska
återuppfinna eller bygga en parallell initieringsväg.

`Golden Path` är ett canonical begrepp (ADR 0038, `naming-dictionary.v1.json`).
Det betyder huvudflödet OCH den smala motor-skiva som bevisar att det lever -
inte alla tester eller all eval. För att inte fler `golden_*`-ytor ska driva
isär: detta är den enda kanoniska entrypoint-ytan.

| Yta | Var | Roll |
| --- | --- | --- |
| Flöde/runbook | `docs/llm-golden-path-runbook.md` (denna fil) | Sanningskälla för flödet |
| Mätning (kommando) | `scripts/run_golden_path_eval.py` | Deterministisk scorecard, default offline |
| Tester som låser | `tests/test_golden_path_eval.py`, `tests/test_llm_golden_path_smoke.py` | Pinnar routing + artefaktkontrakt |
| Eval-output | `data/evals/summaries/golden-path/`, `data/evals/artifacts/golden-path/` | Summary + isolerad arbetsmapp |
| Backoffice | "Evals och telemetri" + Översikt (read-only golden-status) | Operatörens iakttagelse |

Ordet "golden" i snapshot-/golden-master-tester (t.ex.
`tests/test_section_treatments_json_parity.py`) är **inte** Golden Path - det är
"snapshot baseline". Se begreppskartan i [`docs/glossary.md`](glossary.md).

Kärnflödet är:

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

Internt motsvarar det:

```text
prompt
  -> generate (prompt_to_project_input)
  -> v1 project-input + meta-sidecar
  -> build (build_site) -> Engine Run v1 + genererade filer
följdprompt
  -> generate_followup (ärver projectId, discoveryDecision, projectDna)
  -> v2 project-input snapshot
  -> build -> Engine Run v2 (engineMode=followup, previousVersion=1)
```

## CLI-flöde

Init-prompt:

```bash
python scripts/prompt_to_project_input.py \
  "Skapa en hemsida för en elektriker i Malmö." \
  --site-id electrician-malmo \
  --project-id golden-path-demo
python scripts/build_site.py \
  --dossier data/prompt-inputs/electrician-malmo.project-input.json \
  --skip-build
```

Följdprompt:

```bash
python scripts/prompt_to_project_input.py \
  "Gör tonen mer premium." \
  --followup-site-id electrician-malmo
python scripts/build_site.py \
  --dossier data/prompt-inputs/electrician-malmo.project-input.json \
  --skip-build
```

`--skip-build` hoppar `npm install` + `next build`. Plocka bort flaggan när
du faktiskt vill ha en kompilerad preview under `../sajtbyggaren-output/`.
Utan `OPENAI_API_KEY` faller briefModel + planningModel tillbaka till mock
och skriver `briefSource=mock-no-key` respektive `planSource=mock-no-key`.

## Viewser-flöde (klick-väg)

1. Starta Viewser (Next.js-appen under `apps/viewser/`).
2. Skriv init-prompten i prompt-byggaren och bekräfta valen i
   discovery-wizarden.
3. Klicka "Bygg". Viewser POSTar till `/api/prompt`, som shellar
   `prompt_to_project_input.generate` och kör `build` direkt efter — samma
   pipeline som CLI:n.
4. När previewen visas, öppna floating-chatten och skicka en följdprompt.
   Viewser POSTar samma endpoint i `mode="followup"`, vilket bumpar
   versionen och ger en ny run du kan växla mellan i versions-tabben.

## Artefakter att verifiera per run

Varje `data/runs/<runId>/` ska innehålla åtta canonical run-artefakter
plus en generated-files-snapshot (`trace.ndjson` är NDJSON, övriga är JSON):

- `input.json`
- `site-brief.json`
- `site-plan.json`
- `generation-package.json`
- `quality-result.json`
- `repair-result.json`
- `build-result.json`
- `trace.ndjson`
- `generated-files/app/page.tsx`

## Tester som låser kedjan

```bash
python -m pytest tests/test_llm_golden_path_smoke.py -v
python -m pytest tests/test_followup_versioning_regression.py -v
```

Smoke-testet låser den grova artefakt-kontraktet (åtta filer per run + chain
v1->v2 med samma projectId, version 1/2, previousVersion + followUpPrompt,
engineMode followup). Followup-versioning-regressionen pinnar det finare
semantiska merge-kontraktet (tone shift, projectDna, ärvd discovery-beslut).

## Vad som inte ingår i v1

Codegen-fasen kör ett deterministiskt codegen v1-manifest från
`packages/generation/codegen/`. Riktiga codegenModel-anrop och full
Sprint 3B-codegen/repair-gren (ADR 0017) ligger utanför denna låsning.
Pipelinen är redan wired och vissa mekaniska repair-fixes finns redan
under `packages/generation/repair/fixes/`; det är LLM-grenen i
codegen-steget och resten av Sprint 3B-omfånget som är stubbat.
