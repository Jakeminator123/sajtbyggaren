# ADR 0015 - Sprint 3A: codegenModel v1 + Quality Gate + Repair Pipeline

**Status:** accepted
**Datum:** 2026-05-08
**Beroenden:** ADR 0009 (Engine Run + Model Roles), ADR 0013 (schema-lock),
ADR 0014 (Sprint 2B planning helper)

## Kontext

Efter Sprint 2B är fas 1 (briefModel) och fas 2 (planningModel via
`produce_site_plan`) på plats. Fas 3 i `scripts/build_site.py` är
fortfarande deterministisk: kopierar starter, patchar, mountar Dossiers
och skriver `repair-result.json` + `quality-result.json` som **skeleton-
artefakter** med `status=not-run`.

Sprint 3A levererar smalaste fungerande slice av riktig fas 3:

1. `packages/generation/codegen/` - `codegenModel v1` (deterministisk
   manifest-emitter; LLM-anrop kommer i v2).
2. `packages/generation/quality_gate/` - kör typecheck, route-scan,
   build-status och policy-compliance och skriver `quality-result.json`
   med riktiga checks.
3. `packages/generation/repair/` - tar Quality Gate-resultatet och
   producerar strukturerat `repair-result.json` (deterministisk no-op
   eller mekanisk fix; LLM-fix kommer senare).

`scripts/build_site.py` får tunn wiring som anropar de tre paketen.
Ingen ny produktlogik flyttas till scripts/.

## Beslut

### 1) Python-paketnamn använder underscore

`engine-run.v1.json` (v2) och `repo-boundaries.v1.json` (v7) skrev båda
sökvägen som `packages/generation/quality-gate/` med bindestreck. Det
strider mot Python-import-syntax: `import packages.generation.quality-gate`
är ett syntaxfel eftersom bindestreck inte är giltiga i identifierare.

Resten av `packages/generation/`-ytan använder en-ords-mappar (brief,
planning, artifacts) implicit utan denna kollision. När en två-ords-
mapp behövs är **underscore canonical**.

`engine-run.v1.json` bumps to v3 och `repo-boundaries.v1.json` bumps to
v8 där samtliga `quality-gate`-strängar ersätts av `quality_gate`. Inget
filsystem-objekt behöver bytas eftersom mappen skapas i denna sprint.

### 2) codegenModel v1 är ett manifest-kontrakt, inte LLM-anrop

`packages/generation/codegen/produce_codegen_artefakt()` returnerar ett
strukturerat manifest (`CodegenResult` med `files: list[CodegenFile]`)
som beskriver vad fas 3 har skrivit. Sprint 3A v1 är **deterministisk**:
manifestet adapteras från builderns faktiska output (routes, dossier-
komponenter, patchade konfig-filer).

Senare sprintar ersätter v1-implementationen med riktigt `codegenModel`-
anrop som emittar `CodegenFile` *innan* skrivning. Då blir
`scripts/build_site.py` en tunn skrivare av manifest-entries och B13
(produktlogik i scripts/) stängs i samma rörelse.

`codegen-result.json` skrivs **inte** som canonical artefakt eftersom
`engine-run.v1.json:artifacts` listar exakt åtta artefakter och codegen-
metadatat ryms inom `build-result.json`. Manifestet feedas till Quality
Gate och Repair Pipeline in-memory.

### 3) Quality Gate kör fyra checks

`packages/generation/quality_gate/run_quality_gate()` kör:

- **typecheck** - delegerar till `npx tsc --noEmit` när `node_modules`
  finns; `status=skipped` när build hoppades över.
- **route-scan** - jämför required routes från Site Plan mot faktiska
  filer under `app/`. `status=ok` när alla required routes finns,
  annars `failed` med lista över saknade.
- **build-status** - läser status från npm install + npm run build
  som builder redan kört; aggregerar till `ok` / `failed` / `skipped`.
- **policy-compliance** - scannar target för förbjudna `.env*`-filer
  (utom `.env.example`). Återanvänder `_FORBIDDEN_ENV_PATTERN` från
  builder. `status=ok` om inga finns.

`QualityResult.status` aggregeras till `ok` (alla checks ok eller
skipped), `degraded` (någon check failed men typecheck/build var ok)
eller `failed` (typecheck eller build failed).

### 4) Repair Pipeline har strukturerat no-fix-applied-läge

`packages/generation/repair/run_repair_pipeline()` tar
`QualityResult` och returnerar `RepairResult` med:

- `status="not-needed"` när `quality_result.status == "ok"`
- `status="no-fix-applied"` när något check failed men v1 ännu inte
  implementerar mekaniska fixes. `remainingErrors[]` listar de failed
  checks så operatören ser exakt vad som inte lagades.
- `mechanicalFixesApplied=[]` och `llmFixesApplied=[]` är alltid tomma
  i v1.

Sprint 3B/4 lägger till mekaniska fixes (typ `add export default`,
`auto-import missing module`) och Sprint 5+ lägger till LLM-fix när
mekaniska inte räcker. Kontraktet (`RepairResult`-typen) är låst nu.

### 5) Tunn wiring i scripts/build_site.py

`scripts/` har enligt `repo-boundaries.v1.json:39` förbud mot
"produktlogik" och får importera bara från
`packages/generation/{brief,planning,artifacts}`. Sprint 3A utökar
`mayImportFrom` med de tre nya paketen. Det är tunn wiring, inte
produktlogik:

```python
# scripts/build_site.py (Phase 3, slutet)
codegen_result = produce_codegen_artefakt(generation_package, ...)
quality_result = run_quality_gate(target, run_dir, codegen_result, ...)
repair_result = run_repair_pipeline(quality_result, target, ...)
write_json(run_dir / "quality-result.json", quality_result.model_dump(by_alias=True))
write_json(run_dir / "repair-result.json", repair_result.model_dump(by_alias=True))
```

Skeleton-funktionerna `write_repair_result_skeleton` och
`write_quality_result_skeleton` tas bort.

B13 förvärras inte av Sprint 3A: ny logik landar uteslutande i
`packages/generation/`. När B13 stängs i en framtida sprint flyttas
write_pages/mount_dossier_components/patch_globals_css till
`packages/generation/build/` eller `packages/generation/codegen/`.

## Konsekvenser

- Pipelines slutar producera `status=not-run`-skeleton; varje run får
  riktiga Quality Gate- och Repair-resultat.
- `npm run build` förblir auktoritativ build-status; Quality Gate
  aggregerar utan att duplicera.
- Repair Pipeline är ärlig om sin nuvarande v1-skala (no-op när inget
  går att fixa mekaniskt) i stället för att låtsas vara klar.
- B13 förvärras inte. Sprint 3A skapar tre nya paket men flyttar inte
  existerande produktlogik från `scripts/build_site.py`.
- `engine-run.v1.json` bumps till v3, `repo-boundaries.v1.json` till v8.
  Ingen schema-ändring (path är fri-form-sträng).

## Vad detta INTE är

- **Inte real `codegenModel`-LLM-anrop.** v1 är deterministisk; LLM-
  drivna codegen-anrop kommer i Sprint 3B.
- **Inte mekaniska fixes.** Repair Pipeline v1 är no-fix-applied när
  något failar; mekaniska fixes kommer senare.
- **Inte LLM-fixes.** LLM-fix-vägen är dokumenterad i `RepairResult`-
  kontraktet men inte implementerad.
- **Inte StackBlitzRuntime.** Preview Runtime bidrar inte till fas 3
  i Sprint 3A.
- **Inte B13-stängning.** B13 (produktlogik i `scripts/build_site.py`)
  kvarstår; Sprint 3A undviker att förvärra den men stänger den inte.
- **Inte commerce-base harmonisering** eller hard Dossier-import.

## Alternativ vi övervägde

1. **Hålla skeleton-artefakterna till Sprint 3B.**
   Avvisat: skeleton-läget täcker över faktiska build-fel
   (typecheck-misstag fångas inte). Riktiga checks ger värde redan
   i v1 även om Repair är no-op.

2. **Behålla `quality-gate/` med bindestreck och importera via
   `importlib`.**
   Avvisat: hackigt, bryter mot Python-paketkonventionen i resten av
   `packages/generation/`, och löser inte att underscore är canonical
   för flerords-Python-paket.

3. **Lägga `codegenModel v1` direkt i `scripts/build_site.py`.**
   Avvisat: förvärrar B13 markant (Sprint 3A-ytan landar i scripts/
   istället för packages/).

4. **Skapa `packages/generation/build/` redan nu (som
   `engine-run.v1.json:phases.build.ownerPackage` redan pekar på).**
   Avvisat i Sprint 3A: kräver flytt av write_pages/mount_dossier/
   patch_*-funktionerna ur scripts/build_site.py, vilket är B13:s
   stängning. För stor scope. Reserveras för Sprint 3B/4.

## Verifiering

Sprint 3A anses levererad när:

- `packages/generation/codegen/`, `packages/generation/quality_gate/`
  och `packages/generation/repair/` finns med public API + tester.
- `scripts/build_site.py` skriver `quality-result.json` och
  `repair-result.json` via de tre paketen, inte via skeleton.
- `tests/test_codegen.py`, `tests/test_quality_gate.py`,
  `tests/test_repair.py` passerar.
- `tests/test_build_site_size.py` skyddar att skeleton-funktionerna
  inte återinförs och att scripts/ inte sväller med produktlogik.
- `governance_validate`, `rules_sync --check`,
  `check_term_coverage --strict`, `pytest`, `ruff` är gröna.
