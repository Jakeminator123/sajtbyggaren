# Known issues + audit-derived bug log

Den här filen är vår **kanoniska bugg-/aning-lista**. Varje gång en bugg
hittas i en audit eller via en operatör läggs den in här med ett ID och en
tillhörande regressionstest. Innan ett ID stryks från listan måste testet
passera och en commit-referens länkas under "Fix".

Format per bugg:

> `<ID> - <Allvar>` - kort beskrivning. Källa: audit-rapport eller person.
> Fix: commit-sha eller "open". Test: filnamn::testnamn.

## Allvarsskala

- **Hög**: säkerhetshål, datakorruption, race conditions som kan korrumpera
  state.
- **Medel**: kontraktsbrott, namnskugga, dålig observability, men ingen
  korruption.
- **Låg**: kosmetiska, dokumentations-eftersläpningar, framtidsrisk.

## Round 1 audit (2026-05-07) - tre subagents granskade Builder MVP

### Säkerhets/race - alla fixade i round 2

- **`B4` Hög** - `.env`-guard i `scripts/build_site.py:67` var case-sensitive;
  `.ENV`, `.Env.Local` slank igenom.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_env_guard_blocks_case_variants`.
- **`B5` Hög** - `copy_starter` ignorerade inte `.env*`; en starter med
  `.env.local` skulle kopierats igenom.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_copy_starter_ignore_blocks_env_files`.
- **`B6/B10` Hög** - `runId` hade bara sekundprecision; två regenerationer
  inom samma sekund kunde dela run-mapp och truncera trace.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_run_id_unique_under_rapid_calls`.
- **`B7` Hög** - `patch_layout` / `patch_globals_css` / `patch_package_json`
  använde direkt `Path.write_text` istället för guarded helper.
  Fix: `c466f58`+ (alla tre går via `write()`).
- **`BO3` Hög** - `backoffice/views/governance.py:66` skrev policy
  non-atomiskt; crash mellan truncate och write skulle korrumpera.
  Fix: `c466f58`+ (`atomic_write_text`).

### Kontraktsbrott - alla fixade i round 2

- **`B1` Medel-Hög** - Phase 3 saknade `generated-files/`,
  `repair-result.json`, `quality-result.json` enligt `engine-run.v1.json`.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_all_eight_engine_run_artifacts_present`.
- **`B2/BO1` Medel-Hög** - `build-result.json` saknade `modelUsage`; ingen
  token-spårning ens som nollor.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_build_result_has_model_usage_stub`.
- **`B8/B9` Medel** - route-guard kollade bara att filer fanns, inte att
  pages hade `export default`.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_route_guard_blocks_missing_default_export`.
- **`B11` Hög** - `generatedFilesDir` pekade på dev preview istället för
  canonical snapshot under `data/runs/<runId>/generated-files/`.
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_generated_files_dir_points_to_run_snapshot`.

### Konsistens - alla fixade i round 2

- **`B3` Medel** - trace event-namn `input_written` vs `dev_generate.py`'s
  `input.written` (snake vs dotted).
  Fix: `c466f58`+. Test: `tests/test_builder_hardening.py::test_trace_event_names_use_dotted_form`.
- **`BO5` Medel** - Backoffice visade scaffolds med `_status: placeholder`
  som "Implementerad: ja".
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_placeholder_detector_recognises_status_field`.
- **`N1` Låg** - `docs/glossary.md` saknade Site/Feature/Integration/Data
  Dossier (registrerade i naming-dictionary v7).
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_glossary_lists_four_dossier_types`.
- **`N2` Låg** - `docs/architecture/pipeline-mapping.md` ljög om vad som
  står i `globallyForbidden`.
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_pipeline_mapping_does_not_misclaim_globally_forbidden`.
- **`N3` Låg** - `packages/generation/orchestration/dossiers/` finns inte
  fysiskt trots att policies pekar dit.
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_dossier_owner_path_exists_on_disk`.
- **`N4` Medel** - `preview-runtime-policy.v1.json` självmotsade sig
  ("no F2/F3 tier" + "F3-likt scenario", "tier-3 SDK:er").
  Fix: `c466f58`+. Test: `tests/test_naming_consistency.py::test_preview_runtime_policy_self_consistent`.

## Öppna - inte fixade än

- **`BO2` Medel** - Backoffice trace viewer är rå dataframe;
  `data/runs/<runId>/trace.ndjson` borde grupperas per fas och färgas efter
  status. Beror på round 3.
- **`BO4` Medel** - `backoffice/views/playground.py:46-53` blockerar 180s i
  subprocess; ingen async / cancellation. Beror på round 3.
- **`B12` Låg** - smoke-tester skriver till riktiga `.generated/` och
  `data/runs/` istället för `tmp_path`. Härdade tester i
  `test_builder_hardening.py` använder `tmp_path` där det går; smoke-tester
  i `test_builder_smoke.py` rör fortfarande verklig disk för slutgiltig
  verifiering. Acceptabelt så länge `.gitignore` håller dem utanför git.
- **`B13` Låg** - `scripts/build_site.py` innehåller produktlogik vilket
  bryter mot `repo-boundaries.v1.json:39`. Naturlig flytt blir
  `packages/generation/build/` när ramverket växer.

## Process

- En bugg som hittas i en audit MÅSTE få ett ID här (`<bokstav><nummer>`)
  innan den fixas.
- En fix MÅSTE komma med en regressionstest. Tester utan koppling till en
  ID i den här filen får finnas men är inte regression-tester.
- "Fix" markeras med kort commit-sha; det räcker att den första commiten
  ligger där eftersom följdfixar refererar tillbaka.
- "Test" pekar på en konkret `tests/<file>.py::<test_name>` som blockerar
  regression i framtida körningar.

## Allmänna principer som inte blir buggar förrän de bryts

- Builder skriver aldrig riktiga `.env`-filer.
- Engine Run-trace är append-only.
- `understand` / `plan` / `build` är canonical; reviewer-vokabulär är intern
  läs-karta.
- En Dossier-realisering är scaffold-specifik; en Dossier-definition är
  portabel.
- Backoffice får läsa allt och skriva via guarded helpers; aldrig direkt mot
  `data/runs/` eller `packages/`.
