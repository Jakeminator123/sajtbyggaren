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
- **`B13` Låg** - `scripts/build_site.py` innehåller produktlogik vilket
  bryter mot `repo-boundaries.v1.json:39`. Naturlig flytt blir
  `packages/generation/build/` när ramverket växer.
- **`P2B-COMMERCE` Låg** (öppen 2026-05-08) - `data/starters/commerce-base/`
  innehåller bara en README och en oharmoniserad `commerce-main.zip` (kopia
  av `vercel/commerce`). Ecommerce-lite-scaffolden (Sprint 2B) använder
  `marketing-base` som starter tills commerce-base är harmoniserad: Next 16,
  shadcn/ui, TypeScript strict, npm-lock istället för pnpm-lock, och
  Shopify-integrationen flyttad ut till en hard Dossier (planerat
  `commerce-shopify` per `capability-map.v1.json`). Naturlig fix: separat
  starter-harmoniserings-sprint som packar upp zipen, kör Next-codemods,
  rensar copy och bryter ut produkt-grid/cart/checkout till soft- och
  hard-Dossiers. Tills dess är scaffold + starter avsiktligt frikopplade -
  `produce_site_plan` mappar `ecommerce-lite -> marketing-base` via
  `SCAFFOLD_TO_STARTER`-konstanten i `packages/generation/planning/plan.py`.

## Stängda - regression-test säkrar fixet

- **`B12` Låg** (stängd 2026-05-08) - smoke-tester skrev tidigare till
  riktiga `.generated/` och `data/runs/` istället för `tmp_path`, vilket
  spammade run-historiken med ~10-15 mappar per `pytest`-körning.
  Fix: `e376439`. `scripts/build_site.py::build()` accepterar nu en
  `runs_dir`-parameter och `--runs-dir`-flagga, och alla tester i
  `tests/test_builder_smoke.py`, `tests/test_builder_hardening.py` och
  `tests/test_dossier_mounting.py` skickar in `tmp_path`. Verifierat
  2026-05-08: `data/runs/` har 6 mappar både före och efter en full
  `pytest tests/ -q`-körning.
- **`B14` Låg** (stängd 2026-05-08) - efter Sprint 2A drev tre docstrings
  isär från koden: `README.md` "Engine Run"-stycket sa fortfarande att
  dev-drivern kör utan LLM-anrop, `scripts/dev_generate.py` modul-docstring
  sa "fully mocked: no LLM calls", och `packages/generation/brief/__init__.py`
  påstod att `extract_site_brief` returnerar `SiteBrief` (canonical signatur
  är `BriefResult`). Fix: docs-only commit som synkar alla tre med
  verkligheten. README listar nu också ADR 0010-0013. Test: dokumentations-
  ändringar fångas av `check_term_coverage --strict` om nya termer smyger in.
- **`B15` Medel** (stängd 2026-05-08) - `OPENAI_API_KEY` med whitespace-
  only värde (t.ex. `"   "`, `"\n"`) räknades som satt i fem callsites
  (`packages/generation/brief/extract.py`, `scripts/dev_generate.py`,
  `scripts/build_site.py`, `backoffice/views/status.py`,
  `backoffice/views/playground.py`). Det skickade real-LLM-vägen mot
  OpenAI med en tom nyckel och föll med en otydlig auth-error istället
  för att rent fall back till mock. Fix: ny `has_openai_api_key()`-helper
  i `packages/generation/brief/models.py` strippar och kollar non-empty.
  Alla fem callsites importerar samma helper. Test:
  `tests/test_brief_model_resolver.py::test_has_openai_api_key_treats_whitespace_as_missing`
  (parametriserad över fem whitespace-varianter) plus tre tester för
  unset / empty / surrounding whitespace.
- **`B16` Medel** (stängd 2026-05-08) - `scripts/build_site.py::run_npm`
  saknade `timeout`-parameter; ett hängande `npm install` eller `npm run
  build` skulle blockera buildern på obestämd tid och lämna
  `data/runs/<runId>/` halvskrivet. Fix: konstanterna
  `NPM_INSTALL_TIMEOUT_SECONDS = 600` och `NPM_BUILD_TIMEOUT_SECONDS = 300`,
  `subprocess.TimeoutExpired` fångas i `run_npm` och returnerar
  `(False, elapsed, "timeout: ...")` så `build-result.json` får
  `status=failed` istället för att processen hänger. Test:
  `tests/test_builder_hardening.py::test_run_npm_returns_failure_on_timeout`
  och `test_build_calls_run_npm_with_documented_timeouts`.
- **`B17` Medel** (stängd 2026-05-08) - `scripts/dev_generate.py`
  build-fasen läste fortfarande gamla nycklar (`scaffold`,
  `scaffoldVariant`) från Generation Package när placeholder-filen
  skrevs, trots att ADR 0013 låste den canonical formen till
  `scaffoldId` / `variantId` / `starterId`. Resultatet: placeholder
  innehöll `// scaffold: None` istället för faktiska värden. Inget
  produktionsproblem (det är en mock-fil) men exakt det driftmönster
  som ADR 0013 var skriven för att blockera. Fix: byt
  `generation_package.get('scaffold')` → `.get('scaffoldId')`,
  `.get('scaffoldVariant')` → `.get('variantId')` plus tillägg av
  `starterId`. Test:
  `tests/test_dev_generate.py::test_dev_generate_placeholder_uses_canonical_field_names`.
- **`B19` Medel** (stängd 2026-05-08, Sprint 2B) - Två nästan-parallella
  init-pipelines: `scripts/build_site.py` (Project Input → Next.js + alla
  artefakter) och `scripts/dev_generate.py` (prompt → mock artefakter)
  skrev samma artefakttyper men via olika kod-vägar - exakt det
  driftmönster ADR 0013 var skriven för att blockera. Sprint 2B introducerar
  `packages/generation/planning/produce_site_plan` som enda källan för
  Site Plan + Generation Package. Båda scripten är tunna wrappers ovanpå
  helpern: builder skickar `pinned={scaffoldId, variantId}` från Project
  Input (planSource=`pinned`), `dev_generate` lämnar `pinned=None` så
  helpern kan välja via planningModel (real när `OPENAI_API_KEY` finns,
  annars mock-no-key/mock-llm-error). Capability-map.v1-principen "tom
  dossier-lista = gap" hanteras centralt så `selectedDossiers.rejected[]`
  alltid speglar verkligheten. Builder läser nu också `starterId` från
  planen istället för att hårdkoda `marketing-base` i `copy_starter`-anropet,
  vilket gör `produce_site_plan` faktiskt auktoritativ.
  Fix: Sprint 2B-commit. Tester:
  `tests/test_planning.py::test_b19_dev_generate_imports_produce_site_plan`,
  `tests/test_planning.py::test_b19_build_site_imports_produce_site_plan`,
  `tests/test_planning.py::test_b19_neither_script_keeps_legacy_local_planner_function`,
  `tests/test_planning.py::test_registry_contains_at_least_two_scaffolds_with_content`.
- **`B18` Medel** (stängd 2026-05-08) - Konceptuell namnkrock: termer
  som `service-list`, `service-area`, `reviews`, `trust-badges`,
  `contact-cta`, `trust-proof` användes både som **sektioner** (i
  `local-service-business/sections.json`, vilket är korrekt per ADR
  0012) och som **Dossier-IDs** (i `compatible-dossiers.json` och
  `selectedDossiers.recommended` på alla tre Project Inputs:
  `painter-palma`, `arcade-hall`, `foto-ram`). Det är samma
  vokabulär-läcka som ADR 0012 var skriven för att rensa.
  Fix: rensade `compatible-dossiers.json` (ingen sektion listad som
  Dossier längre, comment-fältet förklarar varför), tomma `recommended`-
  listor i alla tre Project Inputs (med rationale som dokumenterar
  beslutet), `dev_generate.py` mock-plan skriver `selectedDossiers: []`
  istället för `["contact-form", "reviews"]`. Capability-map principle
  uppdaterad: "empty capability list = gap, not feature - planningModel
  must not pretend to implement a capability that has no Dossier".

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
