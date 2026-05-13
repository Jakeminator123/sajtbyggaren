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
- **`B13a` Låg** - `scripts/build_site.py` innehåller produktlogik vilket
  bryter mot `repo-boundaries.v1.json:39`. Naturlig flytt blir
  `packages/generation/build/` när ramverket växer. (Sprint 2B audit-fix
  uppdaterade importgränserna så planning/brief/artifacts-importer inte
  längre bryter policyn, men den större arkitektur-skulden kvarstår.)
  Tidigare kallad `B13`; splittad i `B13a` (arkitektur-flytt, denna post)
  och `B13b` (route-emission) den 2026-05-13 efter att
  `docs/current-focus.md` började använda namnet "B13" för bara den
  ena halvan.
- **`B13b` Låg** (öppen 2026-05-13, status: **kod klar, inväntar merge av
  PR #19**) - `scripts/build_site.py:write_pages` var hårdkodad mot
  `local-service-business`-routes (`/tjanster`, `/om-oss`, `/kontakt`)
  på fyra nivåer (`_nav_items()`, hardcoded `/tjanster`-CTA i
  `render_home`, `write_pages()`, avsaknad av `render_products`). Det
  blockerade aktiveringen av `ecommerce-lite -> commerce-base` (B20
  step 2): ad-hoc-generation gav Quality Gate `status=degraded` med
  route-scan failure `"/produkter -> app\produkter\page.tsx
  (saknas)"`.

  **Fix i PR #19 (`feat/b13-route-emission`):** `write_pages` läser nu
  scaffoldens `routes.json` och dispatchar per route id
  (home/services/products/about/contact). Ny `render_products`-
  renderer för `/produkter`. Nya helpers `_nav_items_from_scaffold`,
  `_pick_listing_route`, `_NAV_LABEL_BY_ROUTE_ID`,
  `_LISTING_COPY_BY_ROUTE_ID`. Okänt route-id ger `SystemExit` så
  scaffolds inte tyst kan saknas en renderer. Ny
  `examples/atelje-bird.project-input.json` (ecommerce-lite-fixture)
  för end-to-end-smoke. Test:
  `tests/test_builder_route_emission.py` (14 tester) låser
  scaffold-driven dispatch + ecommerce-lite-smoken
  `test_ecommerce_lite_fixture_writes_produkter_and_passes_route_scan`.

  Flyttas till "Stängda - regression-test säkrar fixet" efter merge
  (Standard loop steg 7).
- **`B20` Låg** (öppen 2026-05-08, status: **vendor done, activation
  blocked by B13b route-emission until PR #19 merges**) - status
  uppdaterad 2026-05-13.

  **Steg 1 (vendor) landad i PR #16 commit `4b4c3af`:**
  `data/starters/commerce-base/` är nu vendoriserad och harmoniserad
  från `vercel/commerce` upstream commit
  `1df2cf6f6c935f4782eed27351fa18f276917a4d`. Hårda krav uppfyllda
  enligt `data/starters/README.md`: Next.js 16, TypeScript strict,
  Tailwind 4, shadcn-konfiguration, `package-lock.json`, ESLint flat
  + Prettier, ingen `.env`. `npm ci` + `npm run build` + `npm run lint`
  gröna lokalt; Shopify-anrop guard:ade så builden inte kräver
  Shopify-env. Se [ADR
  0018](../governance/decisions/0018-b20-commerce-base-harmonisering.md).

  **Steg 2 (mapping-flipp) pausad — blockerad av B13b:** ett tidigt
  försök att flippa runtime-mappningen i samma PR (commit `58c5e63`,
  reverterad i `a3d4828`) avslöjade att `scripts/build_site.py` är
  hårdkodad mot `local-service-business`-routes på fyra nivåer
  (`_nav_items()`, hardcoded `/tjanster`-CTA i `render_home`,
  `write_pages()`, avsaknad av `render_products`). Ad-hoc
  `ecommerce-lite`-generation gav Quality Gate `status=degraded` med
  route-scan failure `"/produkter -> app\produkter\page.tsx
  (saknas)"`. `packages/generation/codegen/codegen.py` är dessutom
  scope-låst till `marketing-base` (ADR 0017), så ecommerce-lite kan
  inte heller köra real `codegenModel`. Tills detta är löst mappar
  `produce_site_plan` fortfarande `ecommerce-lite -> marketing-base`
  via `SCAFFOLD_TO_STARTER`-konstanten i
  `packages/generation/planning/plan.py`, och raden i
  `data/starters/README.md` mappnings-blocket står kvar med
  `(B20: temporary; ...)`-noten.

  **Nästa PR (PR #19 / B13b route-emission):** måste antingen refaktorera
  `scripts/build_site.py` så page-emission drivs av scaffolds
  `routes.json` per scaffold (nya renderers för product-grid,
  products-intro, shop-cta), eller utvidga `codegenModel`-scope till
  ecommerce-lite + commerce-base (kräver ny ADR ovanpå ADR 0017).
  Först därefter kan mapping-flippen göras säkert.

  Filer som hör till detta spår och som mainline-arbete inte ska röra
  så länge en feature-agent jobbar på B20 (se branch-discipline.md
  "Parallella agenter"):

  - `data/starters/commerce-base/` (allt under)
  - `data/starters/README.md` (mappnings-blocket + commerce-base Status-rad)
  - `packages/generation/planning/plan.py` (`SCAFFOLD_TO_STARTER`)
  - `tests/test_starter_scaffold_mapping.py`
  - `scripts/build_site.py` (för PR #19 / B13b-spåret)
  - `packages/generation/codegen/codegen.py` (om scope utvidgas)

  Review-checklist när B20 stängs (för cloud-reviewer eller operatör
  som signerar av PR 16b):

  1. `data/starters/commerce-base/` har faktisk starter-kod (åtminstone
     `package.json`, `app/`-mapp, `components/`, lockfil).
  2. `cd data/starters/commerce-base && npm install && npm run build`
     går igenom utan att kräva Shopify-env eller annan extern secret.
  3. Hårda krav uppfyllda enligt `data/starters/README.md`: Next.js 16,
     TypeScript strict, Tailwind 4, shadcn/ui initialiserad,
     `package-lock.json` (inte `pnpm-lock.yaml`), ESLint flat + Prettier,
     inga `.env`-filer.
  4. Ingen hårdkodad kundcopy, hårdkodade färger eller hårdkodade
     CTA-länkar. Shopify-anrop bor endast under `lib/<provider>/`;
     adapter-mönstret är intakt så `lib/medusa/`, `lib/bigcommerce/`
     etc. kan kopplas in via hard Dossier.
  5. `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER` har
     `ecommerce-lite: commerce-base`.
  6. `data/starters/README.md`:s `scaffold-starter-mapping`-block har
     raden `ecommerce-lite: commerce-base` utan `(B20: ...)`-noten.
  7. Alla governance-tester i `tests/test_starter_scaffold_mapping.py`
     gröna - särskilt `test_b20_temporary_mapping_is_explicit` som
     stänger sig av automatiskt när mappningen flippas.
  8. `python scripts/build_site.py --dossier <ecommerce-input>` (eller
     närmaste motsvarande dossier-exempel som plockar
     `ecommerce-lite`) producerar `build-result.json` status=ok och
     `quality-result.json` status=ok. Specifikt: `app/produkter/page.tsx`
     emitteras, `app/tjanster/page.tsx` emitteras INTE för ecommerce-
     lite-scaffolden.
  9. Denna B20-post flyttas till "Stängda - regression-test säkrar
     fixet"-avsnittet med datum + fix-SHA.

## Stängda - regression-test säkrar fixet

- **`B43` Medel** (stängd 2026-05-11, post-review-2 audit) -
  `apps/viewser/components/viewer-panel.tsx` success-path-grenen hade
  cancelled-guard FÖRE `await import("@stackblitz/sdk")` men inga
  guards EFTER. Två awaits till (dynamisk import + `embedProject`)
  exekverade utan ny cancelled-check, så om operatör bytte runId
  mid-flight rann den gamla embedProject färdig och mountade stale
  preview i den always-mounted ref-divden (post-PR-#13 ref-div är
  alltid monterad — så avmontering räddar inte längre). Fix:
  cancelled-check EFTER dynamic import + cleanup-branch EFTER
  embedProject som rensar `containerRef.current.innerHTML` om
  cancelled blev true under embed-flight. Test:
  `tests/test_viewser_files.py::test_viewer_panel_guards_cancelled_after_dynamic_import_and_embed`
  kräver minst 2 cancelled-referenser i success-path-blocket OCH
  source-lockar att `innerHTML = ""`-cleanup existerar inom en
  `if (cancelled)`-gren.

- **`B42` Medel** (stängd 2026-05-11, post-review-2 audit) -
  `apps/viewser/lib/build-runner.ts` använde
  `runIdMatch?.[1] ?? (await detectLatestRunIdByMtime())` i BÅDA
  success- och failure-grenarna. När `scripts/build_site.py`
  kraschar FÖRE den skriver ut `runId: ...` (t.ex. KeyError på
  Project Input-load, FileNotFoundError på scaffold-lookup),
  faller mtime-fallbacken tillbaka till TIDIGARE run-dir på disk
  och felaktigt märker den som denna build:s "strukturerade
  failure" (B40-kontraktet). UI:t fick då en gammal run med
  fel siteId returnerad som om den var det aktuella failed-
  resultatet. Reviewer flaggade detta i post-review-2-audit som
  "B40 sväljer riktiga fel". Fix: ny `runIdFromStdout`-variabel
  som STRIKT använder process-stdout i failure-grenen.
  Success-grenen behåller mtime-fallback eftersom `exitCode === 0`
  garanterar att senaste dir IS denna build:s. Test:
  `tests/test_viewser_files.py::test_build_runner_returns_structured_failure_instead_of_throwing`
  utökad med assertion som söker upp `if (exitCode !== 0) { ... }`-
  blocket och kräver att `detectLatestRunIdByMtime` INTE förekommer
  där.

- **`B41` Medel** (stängd 2026-05-09, Builder UX MVP smoke-test) -
  `npm run build` mot `.generated/painter-palma/` hade failat Next 16
  prerendering på `/_global-error` med
  `TypeError: Cannot read properties of null (reading 'useContext')`.
  Nattdiagnosen verifierade att både en helt färsk
  `.generated/painter-palma/` och `data/starters/marketing-base/`
  byggde grönt med samma `next@16.2.5` / `react@19.2.4`, vilket pekade
  bort från kundcopy, Dossier-montering och starter-dependencies. Den
  kvarvarande driftkällan var `scripts/build_site.py:copy_starter`:
  funktionen bevarade både `node_modules/` och `.next/` mellan
  regenerationer. `node_modules/` är en avsiktlig npm-cache, men `.next/`
  är framework-genererad build output och kan bära stale prerender-state
  över template- eller dependency-ändringar. Fixen bevarar därför bara
  `node_modules/` och tar bort `.next/` vid varje regeneration innan
  startern kopieras in. Verifierat med färsk
  `python scripts/build_site.py --dossier examples/painter-palma.project-input.json`
  utan `OPENAI_API_KEY`: `build-result.json:status=ok`,
  `quality-result.json:status=ok`, `generated-files/` finns. Standalone
  `cd data/starters/marketing-base && npm run build && npm run lint`
  passerar också. Fix: `fix(starters): repair marketing base build`.
  Test: `tests/test_builder_hardening.py::
  test_copy_starter_drops_stale_next_cache_but_preserves_node_modules`.

- **`B40` Medel** (stängd 2026-05-09, Builder UX MVP smoke-test) -
  `apps/viewser/lib/build-runner.ts:runBuildOnce` kastade
  ovillkorligt en error så fort `scripts/build_site.py` exit:ade
  med kod != 0. Det bröt det dokumenterade Builder MVP-kontraktet
  (`docs/architecture/builder-mvp.md` "Builder-guards"): när
  `npm install` / `npm run build` failar skriver `build_site.py`
  ändå alla canonical artefakter (`build-result.json` med
  `status=failed`, `quality-result.json`, `repair-result.json`,
  `generated-files/`-snapshot) och exit:ar 1 - exit-koden är en
  **avsiktlig** signal till operatören, inte en crash. Wrappers
  exception droppade dock runId:et på golvet, vilket gjorde att
  `/api/build` returnerade 500 utan att UI:t fick en runId att
  navigera till. Run History uppdaterades inte och RunDetailsPanel
  fick aldrig se den strukturerade failure-rapporten. Upptäckt under
  smoke-test efter `e80148c` när marketing-base-startern råkade
  failed på `/_global-error`-prerendering (separat issue, se nedan).
  Fix: i `exitCode !== 0`-grenen försöker wrappers nu läsa
  `build-result.json` från disk via samma `readBuildResult(runId)`-
  helper som success-pathen. Lyckas läsningen returneras
  `{runId, buildResult}` precis som vid framgång - UI:t ser då en
  failed run i Run History och kan rendera artefaktpanelerna
  pedagogiskt. Endast när läsningen failar (exit !=0 + ingen
  strukturerad output på disk) kastar wrappers exception som
  tidigare. Test: `tests/test_viewser_files.py::
  test_build_runner_returns_structured_failure_instead_of_throwing`
  (source-lock på "structured-failure"-comment + `readBuildResult(runId)`
  i exit-branch).

- **`B38` Medel** (stängd 2026-05-09, post-3C-lite-audit-2) -
  `scripts/dev_generate.py:run_phase_build` byggde `modelUsage`-
  envelopen via `compose_model_usage(base_source="mock-no-key", ...)`.
  Värdet var hårdkodat trots att `compose_model_usage`-helperns
  dokumenterade semantik säger att `base_source` är `briefSource`-
  värdet och spårar hur OVERALL pipeline kördes (`real` /
  `mock-no-key` / `mock-llm-error`). Resultat: en operator som körde
  `python scripts/dev_generate.py "..."` med `OPENAI_API_KEY` satt
  fick `site-brief.json:briefSource=real` men
  `build-result.json:modelUsage.source=mock-no-key`. Det bryter
  Sprint 2A-invarianten och skulle få Builder UX-paneler att visa
  fel modellstatus när de läser dev_generate-runs. Fix:
  `run_phase_build` tar nu en valfri `site_brief: dict | None`-
  parameter och läser `briefSource` därifrån; `main()` skickar in
  briefen från Phase 1 (eller läser `site-brief.json` från disk
  när `--phase build` körs ensam). Default-fallback är fortfarande
  `mock-no-key` så bakåtkompatibla anrop inte spricker. Test:
  `tests/test_artefact_schema_3c_lite.py::test_dev_generate_modelusage_source_follows_brief_source`
  (parametriserad över real/mock-no-key/mock-llm-error utan att kräva
  riktig OpenAI-call - `site_brief["briefSource"]` muteras direkt) +
  `test_dev_generate_modelusage_source_defaults_to_mock_no_key_without_brief`
  (låser fallback-pathen).

- **`B39` Låg** (stängd 2026-05-09, post-3C-lite-audit-2) -
  `docs/handoff.md` "Skiriptyta"-sektionen sade generiskt
  "`--runs-dir` för isolerade test-paths" - men flaggnamnet skiljer
  sig per script: `scripts/build_site.py` har `--runs-dir`,
  `scripts/dev_generate.py` har `--data-runs-dir`. Risk: nästa
  agent copy-paste:ar fel flagga och misslyckas tyst eller skriver
  till fel path. Samtidigt rättades `known-issues.md:138` line-ref
  för B35 (`scripts/build_site.py:1565` → faktiskt
  `scripts/build_site.py:1523` där `run_dir.mkdir(...)` sitter).
  Fix: handoff förtydligad per-script + line-ref korrigerad.
  Inga regression-tester - detta är ren doc-drift utan
  runtime-impact, men nämns här så framtida audit ser att fyndet
  inte var nytt vid Builder UX MVP-runda.

- **`B33` Medel** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  `scripts/dev_generate.py:run_phase_build` skrev `build-result.json`
  utan `modelUsage`-fältet. När operatören körde dev_generate med
  `OPENAI_API_KEY` aktiverade `produce_codegen_artefakt` real LLM
  (matching marketing-base), `codegen.source` blev `real`, men
  build-result.json saknade ändå modelUsage. Backoffice / Builder UX
  som läser alla runs (mock + real builder) skulle hamna i
  shape-mismatch. Fix: flyttat composition-logiken till
  `packages/generation/artifacts/model_usage.py:compose_model_usage`
  (publik shared helper); både `scripts/build_site.py:write_build_result`
  och `scripts/dev_generate.py:run_phase_build` anropar samma
  helper med samma codegen_summary-shape (riskNotes + usage
  inkluderade). Test:
  `tests/test_artefact_schema_3c_lite.py::test_dev_generate_writes_modelusage_into_build_result`
  + `test_compose_model_usage_lives_in_shared_artifacts_module`.

- **`B34` Låg** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  Drift-guards i `tests/test_artefact_schema_3c_lite.py:207-248`
  jämförde bara top-level Pydantic-fält mot top-level schema
  ``properties``. Nested ``$defs/checkResult`` (vs `CheckResult`-
  modellen) och ``$defs/repairFix`` (vs `RepairFix`-modellen) var
  inte fält-låsta, så ett tillagt Pydantic-fält på `CheckResult`
  utan motsvarande `$defs/checkResult.properties`-bump skulle
  passera testet trots att artefakten-på-disk och in-memory-modellen
  drev isär. Test-claim "schema↔Pydantic locked" var överdrivet.
  Fix: ny `_assert_no_drift`-helper + `_schema_property_names(schema,
  defs_key=...)`-parameter; två nya tester
  (`test_quality_result_nested_check_result_matches_pydantic`,
  `test_repair_result_nested_repair_fix_matches_pydantic`)
  täcker nested-drift för båda artefakterna.

- **`B35` Låg** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  `docs/architecture/builder-mvp.md` påstod att schema-överträdelse
  fails build "innan `data/runs/<runId>/` skapas". Det stämmer inte:
  `run_dir.mkdir(...)` körs i Phase 0 init (`scripts/build_site.py:1523`)
  innan Phase 1 / 2 / 3 — och schema-validators för
  `quality-result.json` / `repair-result.json` kör först i Phase 3.
  Ett sent schemafel lämnar därför en partial run-dir med
  Phase 1+2-artefakter på disk. Inte en runtime-bug men fel ops-
  förväntan. Fix: doc-stycket omskrivet att vara ärligt om vad
  validatorn faktiskt gör (skyddar de två specifika artefakterna,
  inte hela run-dir); operatörer som vill ha all-or-nothing får
  rensa partial run-dir manuellt.

- **`B36` Låg** (stängd 2026-05-09, post-Sprint-3C-lite-review) -
  Schemafilernas description-fält refererade `tests/test_artefact_schema_drift.py`
  som inte finns i repot; korrekt filnamn är
  `tests/test_artefact_schema_3c_lite.py`. Onboarding-fel som ledde
  ny agent fel när hen följde länken från schemat. Fix: båda schemafiler
  uppdaterade till korrekt filnamn med tillägget "(top-level + nested
  $defs)" så scope är tydlig.

- **`B29` Hög** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  `governance/schemas/project-input.schema.json` (introducerat i
  PR #10 / commit `124b13f`) markerade `services[].summary`,
  `company.tagline`, `company.story`, `location.serviceAreas` och alla
  fyra `contact.*`-fält som **valfria**, men `scripts/build_site.py`-
  renderers indexerar dem ovillkorligt (t.ex. `svc["summary"]`,
  `company["tagline"]`, `contact["addressLines"]`). En schema-valid
  Project Input kraschade därför med `KeyError` mid-build, **innan**
  Quality Gate hann skriva ett strukturerat felresultat. Fix: stramat
  schemat så `required` reflekterar builder-kontraktet. Övriga
  fält (`team`, `founded`, `region`) är fortsatt valfria eftersom
  buildern hanterar deras frånvaro via `.get()`. Test:
  `tests/test_builder_audit_post_3b_next.py::
  test_company_required_includes_tagline_and_story` plus de övriga
  per-fält-låsen + en negativ test
  (`test_schema_rejects_payload_missing_company_tagline`).

- **`B30` Hög** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  Renderers i `scripts/build_site.py` (`render_home`, `render_services`,
  `render_about`, `render_contact`) interpolerade rå kundtext direkt
  in i TSX/JSX via f-strings utan escape. Tecken som `<`, `>`, `{`,
  `}` eller `"` i kundnamn / tagline / service-summary / address-rader
  kunde producera ogiltig TSX som `next build` (eller en typecheck-
  pass) skulle avvisa. Fix: ny `_jsx_safe_string(text)`-helper som
  wrapar all dynamic text i `{"..."}` JSX-expression-form via
  `json.dumps`. Alla raw f-string-interpoleringar i de fyra renderers
  passerar genom helpern. `_phone_href`-resultat (digit-only) behåller
  kvotad attribut-form via `_jsx_safe_string("tel:" + ...)` för
  konsistens. `_member_initials`-helper extraheras ur den tidigare
  inline-expressionen i `render_about` så att initial-strängen är ett
  plain-string-värde innan escape. Test:
  `tests/test_builder_audit_post_3b_next.py::
  test_jsx_safe_string_wraps_text_as_jsx_expression`,
  `test_render_home_jsx_escapes_special_characters`,
  `test_render_contact_jsx_escapes_phone_and_email`,
  `test_renderers_use_jsx_safe_string_for_customer_text`
  (källkods-lock som kräver att alla fyra renderers anropar helpern).

- **`B31` Medel** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  `scripts/build_site.py:write_phase1_understand` anropade
  `dossier_path.relative_to(REPO_ROOT)` utan fallback. CLI:n accepterar
  godtycklig `--dossier`-path, så en operator som pekar på en
  ad-hoc-fixture utanför repot fick en `ValueError`-stack-trace
  istället för ett strukturerat fel. Den befintliga
  `_to_repo_relative()`-helpern (rad 131-142) hade redan rätt
  beteende (try/except). Fix: bytt till helpern. Test:
  `test_to_repo_relative_handles_external_path` +
  `test_write_phase1_understand_does_not_raise_on_external_path`
  (källkods-lock).

- **`B32` Låg** (stängd 2026-05-09, post-Sprint-3B-next-review) -
  `scripts/build_site.py:run_npm` byggde bara
  `partial_text` från `exc.stdout` när `isinstance(exc.stdout, bytes)`,
  och fall till `else`-grenen som inte hanterade `exc.stdout=None +
  exc.stderr="<error log>"`-fallet. Operatören tappade den enda
  diagnostik npm-timeout producerade. Fix: ny
  `_coerce_subprocess_text(stream)`-helper hanterar `None | bytes |
  str` enhetligt; `run_npm` decodar `exc.stdout` och `exc.stderr`
  separat och konkatenerar. Test:
  `test_coerce_subprocess_text_handles_all_three_types`,
  `test_run_npm_timeout_preserves_stderr_when_stdout_is_none`,
  `test_run_npm_timeout_preserves_stderr_with_bytes_stream`.

- **`B28` Låg** (stängd 2026-05-08, audit-4) - `tests/test_docs_freshness.py`
  parsade ruffs felräknings-output med regexen `r"Found\s+(\d+)\s+error"`
  (utan `errors?`). Reviewer-claim: "regex fails to match on 2+ findings,
  actual = -1, safety assertion fails". Verifiering visade att claimet
  är **tekniskt felaktigt** - `re.search` tillåter partiell match så
  `error` matchar som prefix av `errors`, vilket bevisades med
  `re.search(r"Found\s+(\d+)\s+error", "Found 5 errors.")` → match,
  group1=`'5'`. Men förslaget är ändå värt att applicera av tre
  defensiva skäl: (1) codifierar intent istället för att lita på
  substring-prefix-tillfällighet, (2) framtidssäkrar mot ruff-format-
  ändringar, (3) samma strukturella lärdom som B27 ("regex som råkar
  fungera men inte uttrycker intent"). Fix: bytt till
  `r"Found\s+(\d+)\s+errors?"` med explicit `s?`, kompilerad en gång
  som modul-konstant `_RUFF_FOUND_RE`. Test:
  `tests/test_docs_freshness.py::test_ruff_found_regex_handles_singular_and_plural`
  med fyra explicita assertioner (singular+plural+stort tal+full
  ruff-output med både singular- och plural-fall).
- **`B27` Låg** (stängd 2026-05-08, audit-3) - `tests/test_docs_freshness.py`
  använde `dossier_id in readme` (Python `str in str` substring-match) för
  att verifiera att en disk-Dossier nämns i `dossiers/README.md`. Det gav
  falsk-positiv för överlappande IDs: en hypotetisk `game`-Dossier på disk
  skulle räknas som "nämnd" bara för att README:n nämner
  `interactive-game-loop` (`'game' in 'interactive-game-loop' == True`).
  Bevis: `python -c "print('game' in 'interactive-game-loop')"` → `True`.
  Risk-fönster: idag bara en Dossier på disk så testet passerade ändå,
  men så fort en andra Dossier vars id är substring av den första
  importerades skulle testet ge tyst "OK" trots att README:n inte hade
  uppdaterats. Fix: ny `_id_appears_as_token()`-helper i samma fil som
  matchar med custom token-boundary `(?<![\w-])id(?![\w-])` så att hyphen
  räknas som id-tecken, inte token-separator. Tester:
  `tests/test_docs_freshness.py::test_dossier_readme_implementation_status_matches_disk`
  (uppdaterad till att använda helpern), och nya
  `tests/test_docs_freshness.py::test_id_appears_as_token_distinguishes_overlapping_dossier_ids`
  som täcker sex överlapps-scenarier (full id, prefix, suffix, mid-substring,
  hyphen-prefix, hyphen-suffix) plus ett "bara id"-scenario.
- **`B23` Låg** (stängd 2026-05-08, post-audit-2) - Bug C end-to-end:
  `build_plan_artefakts` i `scripts/build_site.py` anropar
  `validate_site_plan(site_plan)` EFTER `merge_operator_selected_with_helper`,
  men det specifika anrops-ordet var inte regression-skyddat. Två rena
  enhetstester fanns för mergens beteende, ett brett schema-test fanns
  för validatorn, men inget test gjorde det olagligt att flytta tillbaka
  validate-anropet till **före** mergen. Fix: nytt source-regex-test
  som hittar `merge_operator_selected_with_helper(` och
  `validate_site_plan(site_plan)` i funktionsbody:n och säkrar att
  validate kommer efter merge. Samma stil som B19-skyddstesterna.
  Test: `tests/test_planning.py::test_b23_build_site_revalidates_site_plan_after_operator_merge`.
- **`B24` Låg** (stängd 2026-05-08, post-audit-2) - Bug A coverage gap:
  `merge_operator_selected_with_helper` har tre kodpaths (operator=None,
  list, dict) men bara None- och dict-paths var direkt testade. List-pathen
  (`plan.py:535-544`) var funktionellt korrekt vid läsning men hade inget
  test som blockerade en framtida regression där t.ex. helperns
  `rejected[]` tappas när operator skickar en plain list. Fix: två nya
  tester för list-form-mergen. Test:
  `tests/test_planning.py::test_merge_operator_list_with_no_helper_signal_returns_plain_list`,
  `tests/test_planning.py::test_merge_operator_list_with_helper_gap_promotes_to_object_form`.
- **`B25` Låg** (stängd 2026-05-08, post-audit-2) - `AGENTS.md` Gotchas-
  stycket sade "only 4 findings remain, all in the bug-bear family"
  trots att `python -m ruff check .` returnerade `All checks passed!`
  (0 findings). Drift uppstod i en tidigare ruff-städ-commit som inte
  uppdaterade AGENTS.md. Risk: ny agent läser docs och tror 4 findings
  är "intentional", lägger tillbaka dem för konsistens. Fix: AGENTS.md
  uppdaterad till "baseline is **0 findings**" + ny pytest-guard
  `tests/test_docs_freshness.py::test_agents_md_ruff_baseline_claim_matches_reality`
  som parsar AGENTS.md för "baseline is **N findings**", kör ruff,
  och bryter om siffrorna inte matchar.
- **`B26` Låg** (stängd 2026-05-08, post-audit-2) -
  `packages/generation/orchestration/dossiers/README.md` sade "Inga
  Dossiers är implementerade än" trots att `soft/interactive-game-loop/`
  fanns på disk med `manifest.json`, `instructions.md` och
  `components/pacman-game.tsx`. `docs/handoff.md:29` hade redan korrekt
  status, så de två dokumenten motsa varandra. Risk: ny agent läser
  README (ägar-pathens lokala doc) före handoff och skriver om
  `pacman-game` från scratch. Fix: README uppdaterad med korrekt status
  + `interactive-game-loop`-länk + förklaring att övriga 11 capability-
  slugs är gap. Ny pytest-guard
  `tests/test_docs_freshness.py::test_dossier_readme_implementation_status_matches_disk`
  walkar `soft/`, `hard/` och bryter om README påstår 0 Dossiers när disk
  har minst en, eller om en disk-Dossier inte nämns vid id i README.
- **`B21` Medel** (stängd 2026-05-08) - `filter_capabilities()` i
  `packages/generation/planning/plan.py` antog att `default` i
  `capability-map.v1.json` alltid fanns i capabilityns `dossiers`-lista.
  Om policyn drev isär kunde plan-helpern välja en Dossier som inte var
  tillåten av samma entry. Fix: fail-loud runtime-check i helpern
  (`default not in dossiers` -> `RuntimeError`) + dedupe av
  `requestedCapabilities` för att undvika dubbletter i `rejected[]`.
  Tester: `tests/test_planning.py::test_filter_capabilities_raises_when_default_not_in_dossiers`,
  `tests/test_planning.py::test_filter_capabilities_dedupes_input`.
- **`B22` Medel** (stängd 2026-05-08) - alla scaffold-filer pekade på
  `$schema=governance/schemas/scaffold.schema.json` men filen saknades.
  Det gav falsk trygghet i IDE/validering och ingen central guard för
  scaffold.json-fälten. Fix: ny
  `governance/schemas/scaffold.schema.json`, `validate_scaffold()` i
  `packages/generation/artifacts/validate.py`, auto-validering i
  `packages/generation/planning/load_scaffold_registry()`, samt ny testfil
  `tests/test_scaffold_schema.py`.
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
  Fix: `c70392e` (Sprint 2B-commit), tightened by `6582040` (post-audit-1
  cleanup) och `e8143cf` (hygiene pass). Tester:
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
