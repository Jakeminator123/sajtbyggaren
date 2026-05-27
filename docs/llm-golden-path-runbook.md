# Runbook: LLM Golden Path v1

Detta är den smala vertikala skivan av Sajtbyggarens kärnflöde. Hela
kedjan är wired i repo:t; runbooken finns för att nästa agent inte ska
återuppfinna eller bygga en parallell initieringsväg.

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

Varje `data/runs/<runId>/` ska innehålla åtta JSON-filer plus en
genererad-filer-snapshot:

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

Codegen-fasen kör en deterministisk codegen v1-manifest från
`packages/generation/codegen/`. Riktiga codegenModel-anrop och mekaniska
repair-fixes är Sprint 3B (ADR 0017) och ligger utanför denna låsning.
Pipelinen är redan wired; det är bara LLM-grenen i codegen-steget som är
stubbad.
