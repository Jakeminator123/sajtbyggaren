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

### Demo-baseline gap från verifierings-Scout 2026-05-15 (efter 1A)

Verifierings-Scout körde fyra skarpa prompts (`elektriker Malmö`,
`frisör Göteborg`, `naprapatklinik Stockholm`, `liten e-handel som
säljer keramik`) via `prompt_to_project_input.py` + `build_site.py`
och scorade totalsnitt 6.2 / 10. Tre fynd hamnade i 1A-hotfixen
(B61/B62/B63, stängda). Fyra ytterligare gap kvarstår som öppna
produkt-buggar:

- **`B64` Hög** - `SiteBrief` (`packages/generation/brief/extract.py`)
  saknar `company_name`-fält. Prompts som "Skapa hemsida för Volt & Co
  i Malmö" får H1 "Elektriker i Malmö" eftersom
  `_derive_company_name()` bara läser `businessTypeGuess` +
  `locationHint`. Riktigt företagsnamn extraheras inte. Kräver
  brief-schema-bump + ADR. Fix: `885431b` (ADR 0022 + Site Brief `companyName`). Test: `tests/test_prompt_to_project_input.py::test_site_brief_company_name_overrides_derived_h1`, `tests/test_extract_site_brief.py::test_site_brief_to_artifact_real_run`.
- **`B65` Hög** - Kontaktuppgifter är alltid placeholder
  (`+46 8 000 00 00`, `kontakt@example.se`, "Adress saknas"). Brief
  saknar contact_phone/email/address-fält och `_placeholder_contact()`
  returnerar fasta värden. Kräver brief-schema-bump + ADR (samma som
  B64). Fix: `885431b` (ADR 0022 + Site Brief contact fields). Test: `tests/test_prompt_to_project_input.py::test_site_brief_contact_fields_override_placeholders`, `tests/test_extract_site_brief.py::test_site_brief_to_artifact_real_run`.
- **`B66` Medel** - `scripts/build_site.py:930-935` "Varför oss"-
  sektion renderas alltid trots tom `trustSignals`. `<h2>Varför oss</h2>`
  är hårdkodad i `render_home`; när `trustSignals=[]` (alltid efter
  prompt-flödet idag) blir det stor rubrik + tom `<ul>`. Fix:
  conditional rendering eller fyll med generic-by-business-type-
  fallback. Fix: `885431b`. Test: `tests/test_builder_route_emission.py::test_render_home_omits_trust_section_when_trust_signals_empty`.
- **`B67` Låg** - `scripts/build_site.py` hårdkodar `lang="sv"` på
  rad 786 och svensk UI-copy ("Begär offert", "Hör av dig idag",
  "Kontakta oss", "Se alla tjänster", "Spela direkt", "Beskriv kort
  vad du behöver så återkommer vi inom en arbetsdag.") på rad 605,
  799, 881, 908, 939-941, 982, 1054, 1132. README + brief stöder
  `language="en"` men renderer ignorerar det. Engelska sajter får
  svensk UI. Källa: verifierings-Scout 2026-05-15. Fix: i18n-
  arkitektur - parameterisera renderer-strings per language. Egen
  sprint, inte i 1B-scope. Fix: open. Test: open.

### Bug-sweep 2026-05-15 (tre parallella subagents efter 1A-hotfix)

Tre read-only subagents granskade (1) brief + prompt-helper pipeline,
(2) builder renderers + scaffolds + Quality Gate, (3) Viewser app +
run/follow-up-flöde. 21 fynd, sorterade på `Probability × Impact`:

- **`B69` Hög** - Quality Gate route-scan får bara `required_routes()`
  (subset där `required: true`), men `write_pages` emitterar alla
  `defaultRoutes`. Scaffolden `local-service-business/routes.json`
  har `about` (`/om-oss`) som `required: false`. Resultat: en
  `/om-oss/page.tsx` utan default export eller med trasig syntax
  kan landa på `main` utan att route-scan flaggar det. Quality Gate
  rapporterar `ok` trots brott mot eget kontrakt. Källa: builder-
  renderer-bug-sweep 2026-05-15. Fix: skicka `all_default_routes +
  dossier_routes` till Quality Gate istället för bara `required`-
  subsetet, ELLER ändra scaffold-routes så alla emitterade är
  `required: true`. Bevis: `scripts/build_site.py:1327`
  (`required_routes()` filtrerar på `required=True`),
  `packages/generation/quality_gate/gate.py:81-94` (kommentar
  bekräftar att gate tar `required`-subsetet). Fix: `885431b` (route-scan receives all emitted routes; aggregate severity unchanged). Test: `tests/test_builder_route_emission.py::test_non_required_about_route_is_scanned_for_default_export`, `tests/test_builder_route_emission.py::test_build_route_scan_receives_all_emitted_default_routes`.
- **`B70` Hög** - `apps/viewser/lib/localhost-guard.ts:5-10` parsar
  Host-headern fel för IPv6 localhost. `hostHeader.split(":")[0]` på
  `"[::1]:3000"` ger `"["` (alla `:` splittar, inklusive de inom
  bracket); efterföljande `replace(/^\[|\]$/g, "")` på `"["` ger tom
  sträng → `isAllowedHost` returnerar `false` → 403. IPv6 localhost
  blockas alltid trots att `"::1"` finns i `LOCAL_HOST_NAMES`. Källa:
  viewser-app-bug-sweep 2026-05-15. Fix: parsa Host enligt RFC 3986
  (separera `[ipv6]:port` med regex). Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_localhost_guard_parses_bracketed_ipv6_hosts`.
- **`B71` Hög** - Follow-up merge fryser `company.story`,
  `company.tagline`, `tone` i strid med egen docstring.
  `scripts/prompt_to_project_input.py:merge_followup_project_input`
  docstring säger att kandidat bidrar med "additive signals (new
  services, capabilities, conversion goals and a visible story note)",
  men koden tar aldrig `story` från kandidat, och `tone` lämnas orörd
  när det redan är ett dict. Källa: brief-pipeline-bug-sweep
  2026-05-15. Två val: (a) uppdatera docstring + test att matcha
  faktisk byte-stabil semantic, eller (b) semantic patching nu
  (kräver ADR, hör hemma i Project DNA-sprinten). Fix: open. Test:
  open.
- **`B72` Medel** - `apps/viewser/lib/runs.ts:40-84` `listRuns` läser
  `build-result.json` för alla run-kataloger trots att svaret bara
  behåller `limit` poster. O(N) disk-läsningar per `GET /api/runs`,
  skalar obegränsat när `data/runs/` fylls. Källa: viewser-app-bug-
  sweep 2026-05-15. Fix: stat alla först, sortera på mtime descending,
  slice till limit, läs `build-result.json` bara för survivors. Fix:
  open. Test: open.
- **`B73` Medel** - Tagline-fallback innehåller "Project Input-filen"
  dev-jargong i den fallback-gren som triggar när både businessType
  och location saknas. Samma slag som B61 men på en kvarvarande edge-
  fallback i `scripts/prompt_to_project_input.py:_derive_tagline`.
  Källa: brief-pipeline-bug-sweep 2026-05-15. Fix: byt till neutral
  demosäker svensk fras eller tom sträng. Fix: `885431b` (docstring + byte-stability lock; semantic patching deferred to Project DNA). Test: `tests/test_prompt_to_project_input.py::test_followup_merge_keeps_story_tagline_and_tone_byte_stable`, `tests/test_prompt_to_project_input.py::test_followup_merge_docstring_describes_conservative_semantics`.
- **`B74` Medel** - `scripts/dev_generate.py:365-393` mock-pipeline
  anropar `produce_codegen_artefakt(routes_written=[])`. Codegen-
  manifestet skriver då noll routes för mock-driven trots att real
  build alltid spelar in dem. Artefakt-konsumenter får inkonsekvent
  bild av vad mocken täcker. Källa: builder-renderer-bug-sweep
  2026-05-15. Fix: synthesisera `['/', '/tjanster', '/om-oss',
  '/kontakt']` från scaffold eller läs
  `generation-package.json:planEntries`. Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_list_runs_slices_before_reading_build_results`.
- **`B75` Medel** - `governance/schemas/project-input.schema.json`
  saknar `additionalProperties: false` på root och underobjekt
  (`company`, `contact`, `location`, `services`-items, `tone`,
  `selectedDossiers`). En felstavad/extra nyckel passerar
  `jsonschema`-valideringen tyst och kan ge `KeyError` nedströms.
  Jämför `site-brief.schema.json` som låser
  `additionalProperties: false`. Källa: brief-pipeline-bug-sweep
  2026-05-15. Fix: lägg till `additionalProperties: false`; kör full
  test-suite (kan exponera latenta extra-fält). Fix: open. Test:
  open.
- **`B76` Medel** - `apps/viewser/lib/runs.ts:203-211 readRunArtefacts`
  och `apps/viewser/components/run-details-panel.tsx:531-544` saknar
  `site-plan.json`. Bara `build-result`, `quality-result`,
  `repair-result`, `site-brief` läses. Plan-fas-krascher blir svåra
  att diagnostisera i RunDetailsPanel. Källa: viewser-app-bug-sweep
  2026-05-15. Fix: lägg till `site-plan.json` i artefakt-bundle + ny
  UI-sektion. Fix: `885431b`. Test: `tests/test_prompt_to_project_input.py::test_derive_tagline_falls_back_when_brief_is_empty`.
- **`B77` Medel** - `scripts/build_site.py:mount_dossier_components`
  upptäcker filnamnskollisioner bara mellan dossiers, inte mellan
  dossier och starter. En dossier med `components/Navbar.tsx` skriver
  tyst över starter-ens egen `components/Navbar.tsx`. Docstringen
  lovar "hard collision error" men det gäller bara dossier-vs-
  dossier. Källa: builder-renderer-bug-sweep 2026-05-15. Fix: assert
  `destination` saknas före skrivning eller union catalogue keyed
  på basename. Fix: `885431b`. Test: `tests/test_dev_generate.py::test_dev_generate_codegen_manifest_includes_planned_routes`.
- **`B78` Hög-säkerhet** - `apps/viewser/lib/build-runner.ts:34-51`
  `assertDossierPathAllowed` använder `path.resolve()` som INTE följer
  symlinks. En symlink under `data/prompt-inputs/` som pekar på en
  fil utanför whitelist passerar kontrollen. Källa: viewser-app-bug-
  sweep 2026-05-15. Fix: använd `fs.realpath()` före `path.relative`-
  jämförelsen, eller `lstatSync` + reject when `isSymbolicLink()`.
  Fix: `885431b`. Test: `tests/test_project_input_schema.py::test_project_input_schema_rejects_unknown_fields`.
- **`B79` Låg** - `scripts/prompt_to_project_input.py:726-734`
  `selectedDossiers.rationale` är alltid engelska även när
  `language="sv"`. Språkblandning i artefakter. Källa: brief-
  pipeline-bug-sweep 2026-05-15. Fix: härled från `language`-flaggan.
  Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_run_details_bundle_and_panel_include_site_plan`.
- **`B80` Låg** - `apps/viewser/lib/prompt-runner.ts:137-143`
  stdout-parsing använder `match(/^siteId:\s*(.+)$/m)` - första match
  vinner. Om Python skriver flera rader som matchar tas fel värde.
  Källa: viewser-app-bug-sweep 2026-05-15. Fix: JSON-blob på sista
  raden, eller unik marker, eller sista match. Fix: `885431b`. Test: `tests/test_dossier_mounting.py::test_dossier_component_cannot_shadow_starter_component`.
- **`B81` Låg** - `brief.language` returneras av briefModel utan
  enum-validering. JSON-schemat kräver bara `minLength: 2`. Modell-
  output `language="zz"` skulle passera och driva fel språkgren.
  Källa: brief-pipeline-bug-sweep 2026-05-15. Fix: normalisera till
  `sv|en` i `_real_brief`. Fix: `885431b`. Test: `tests/test_viewser_security_1b.py::test_build_runner_realpaths_dossier_override_before_whitelist`.
- **`B82` Låg** - `packages/generation/quality_gate/checks.py:131-136`
  typecheck-filter truncates findings till rader med `"error TS"`
  eller substring `".ts"`. Wrapper-diagnostik utan markörer filtreras
  bort. Operatör ser failed status med tom findings-lista. Källa:
  builder-renderer-bug-sweep 2026-05-15. Fix: inkludera tail av raw
  stderr när noll curated findings survives. Fix: `885431b`. Test: `tests/test_prompt_to_project_input.py::test_selected_dossiers_rationale_matches_project_language`.
- **`B83` Låg** - `scripts/prompt_to_project_input.py:_build_services`
  släpper tysta dubblet-tjänster när två brief-items slugifierar till
  samma ASCII-key. Kundsidans tjänstegrid blir kortare än briefen
  anger utan spår. Källa: brief-pipeline-bug-sweep 2026-05-15. Fix:
  disambiguerande suffix på slug-id eller stderr-warning. Fix: open.
  Test: open.
- **`B84` Låg** - `apps/viewser/lib/project-inputs.ts:85-93`
  `listProjectInputs` konkatinerar `examples/` och `data/prompt-inputs/`
  utan deduplicering på `siteId`. Samma `siteId` i båda ger React-
  key-kollision i ProjectInputPicker. Källa: viewser-app-bug-sweep
  2026-05-15. Fix: `Map`-baserad dedup med explicit prioritet.
  Fix: `885431b`. Test: `tests/test_prompt_to_project_input.py::test_service_slug_collisions_get_deterministic_suffixes`.
- **`B85` Låg** - `scripts/prompt_to_project_input.py` modul-
  docstring säger att stdout-kontraktet är `siteId:` + `dossierPath:`,
  men `main()` skriver sex nycklar. Drift mellan spec och
  implementation. Källa: brief-pipeline-bug-sweep 2026-05-15. Fix:
  uppdatera docstring eller lås nycklar med source-lock-test.
  Fix: open. Test: open.
- **`B86` Låg** - `scripts/build_site.py:1387-1388` hårdkodar
  `NPM_INSTALL_TIMEOUT_SECONDS = 600` och `NPM_BUILD_TIMEOUT_SECONDS
  = 300`. Långsamma Cloud Agent VMs överskrider regelbundet, ger
  flaky failures orelaterade till site-correctness. Källa: builder-
  renderer-bug-sweep 2026-05-15. Fix: CLI-flagga eller env-knapp.
  Fix: open. Test: open.
- **`B87` Låg** - `scripts/prompt_to_project_input.py:1091-1096`
  fallbackar tyst till `model = "gpt-5.4"` när `resolve_brief_model()`
  misslyckas. Operatör märker inte att policy-konfigurationen är
  trasig. Källa: brief-pipeline-bug-sweep 2026-05-15. Fix: logga
  högt på stderr vid resolution failure. Fix: open. Test: open.

### Extern reviewer-triage 2026-05-15 (mot `d99f8ba` + `c273b1a`)

- **`B88` Hög** - `scripts/prompt_to_project_input.py:_placeholder_contact()`
  skriver dev-jargong i publika kontaktfält (`"Address placeholder - update Project Input"` /
  `"Adress saknas - uppdatera Project Input"`). Kategoriöverlapp med B61
  ("intern arbetscopy -> publik yta"), men på kontaktytan. Källa:
  extern reviewer + RO-verifierings-subagent 2026-05-15. Fix: open.
  Test: open.
- **`B89` Medel** - `packages/generation/brief/extract.py:detect_language`
  defaultar till `sv` för korta engelska prompts utan träff i
  `ENGLISH_HINTS` (t.ex. `plumber stockholm`, `barber malmo`,
  `ceramic studio`). Kategoriöverlapp med B62 men annan edge-yta. Källa:
  extern reviewer + RO-verifierings-subagent 2026-05-15. Fix: open.
  Test: open.
- **`B90` Låg-Medel** - `packages/generation/brief/extract.py:ENGLISH_HINTS`
  innehåller `"a"` och `"an"`, vilket kan ge falska engelska träffar
  (`A & O El Malmö` klassificeras som `en`). Källa: extern reviewer +
  RO-verifierings-subagent 2026-05-15. Fix: open. Test: open.
- **`B91` Medel** - `_normalize_location_hint` i
  `scripts/prompt_to_project_input.py` mappar idag i praktiken bara
  `sweden -> Sverige`; övriga vanliga engelska/svenska varianter passerar
  oförändrat. Källa: extern reviewer + RO-verifierings-subagent
  2026-05-15. Fix: open. Test: open.
- **`B92` Låg** - `_BUSINESS_TYPE_LABEL_SV` mappar
  `naprapat -> naprapatklinik`, vilket överanpassar enskild naprapat till
  klinikform i H1-fallback. Källa: extern reviewer +
  RO-verifierings-subagent 2026-05-15. Fix: open. Test: open.
- **`B93` Låg-Medel** - `_company_business_label` fallback i
  `scripts/prompt_to_project_input.py` visar rå slugtext i svensk H1
  (`företag som arbetar med pet grooming`). Svensk mening men engelsk
  slugläcka i kundcopy. Källa: extern reviewer +
  RO-verifierings-subagent 2026-05-15. Fix: open. Test: open.

### Re-Verifierings-Scout 2026-05-15 (post-Grind PR #28 mot `d0ded58`)

Re-Verifierings-Scout körde fyra demo-prompter mot fixad kod efter
Grind PR #28-mergen och rapporterade totalsnitt **5.54/10** (case-spann
3.9-6.25). Alla fyra builds var `status=ok`/`quality=ok`. Scout
flaggar själv att hen sannolikt är 0.3-0.5p strikare än Scout 1's
6.2-baseline, så jämförelsen mot baseline är osäker; det Scout är
säker på är att språk-/H1-buggar är borta och kvarvarande svagheter
är dev-jargong, generisk copy och scaffold-mismatch för e-handel.
Top kvarvarande demo-blockers: **B88** (kontakt-placeholder dev-
jargong synligt på alla fyra case), generisk service-copy ("X -
kontakta oss för mer information." återanvänds överallt), och hero-
CTA "Begär offert" hardcoded i `render_home` oavsett bransch
(bryter särskilt e-handel-trovärdighet). Audit-konfidence 7/10.

- **`B94` Medel** - `<ul>`/team-grid på `/om-oss` renderas alltid
  även när `team`-listan är tom. Visuellt tom sektion på alla fyra
  case; samma pattern som B66 (conditional section render). Källa:
  re-Verifierings-Scout 2026-05-15. Fix: open. Test: open.
- **`B95` Medel** - `_normalize_location_hint` fångar inte att brief
  returnerar `locationHint="Sverige"` (utan stad) på `liten e-handel
  som säljer keramik`-prompten. `location.city` blir då landnamnet
  och renderas som ortstag i hero. Bredare variant av B91 — Sverige-
  på-city-fältet specifikt, inte bara `"Sweden"`-translit. Källa:
  re-Verifierings-Scout 2026-05-15. Fix: open. Test: open.
- **`B96` Medel** - Hero-CTA "Begär offert" är hardcoded i
  `scripts/build_site.py:render_home` oavsett `scaffoldId` /
  `conversionGoals`. För `ecommerce-lite` + `conversionGoals=
  ["purchase"]` borde CTA vara "Shoppa nu"/"Se sortimentet". Påverkar
  främst e-handel-case (3.9/10 i re-Scout) och bryter trovärdighet
  för frisör/naprapat där "boka tid" är rätt verb. Källa: re-
  Verifierings-Scout 2026-05-15. Fix: open. Test: open.
- **`B97` Låg** - `/kontakt`-paragrafen "Beskriv jobbet kort så
  återkommer vi inom en arbetsdag med tider och offert." använder
  `jobbet`+`offert` hardcoded — passar inte e-handel-cases (frågor om
  beställning/retur/leverans). Källa: re-Verifierings-Scout
  2026-05-15. Fix: open. Test: open.
- **`B98` Låg** - "Områden vi arbetar i"-block på `/om-oss` är
  meaningless för e-handel — borde inte renderas (eller annan rubrik)
  när scaffold = `ecommerce-lite`. Källa: re-Verifierings-Scout
  2026-05-15. Fix: open. Test: open.

**B71-not (PR #28 stängde, men markerad som unverified av re-Scout):**
Re-Verifierings-Scout flaggade att follow-up byte-stabilitet inte
kan verifieras i ett första-generations-pass (kräver v1 → v2-test).
B71-stängningen i Grind hänger på kod-/docstring-spårning i
`tests/test_prompt_to_project_input.py`; ingen kritik mot lock-tester,
bara att Scout inte själv kunde verifiera invarianten. Två-pass-test
bör naturligt köras nästa gång någon ändå provkör follow-up-flödet.

### Övriga öppna

- **`BO4-followup-cancel` Låg** - `backoffice/views/playground.py` visar nu
  subprocess-status och loggutdrag medan körningen pågår, men riktig
  cancellation/background-jobb är fortfarande inte implementerat. Det bör tas
  som separat sprint om operatören behöver avbryta en redan startad körning.
- **`B13a` Låg** - `scripts/build_site.py` innehåller produktlogik vilket
  bryter mot `repo-boundaries.v1.json:39`. Naturlig flytt blir
  `packages/generation/build/` när ramverket växer. (Sprint 2B audit-fix
  uppdaterade importgränserna så planning/brief/artifacts-importer inte
  längre bryter policyn, men den större arkitektur-skulden kvarstår.)
  Tidigare kallad `B13`; splittad i `B13a` (arkitektur-flytt, denna post)
  och `B13b` (route-emission) den 2026-05-13 efter att
  `docs/current-focus.md` började använda namnet "B13" för bara den
  ena halvan.
- **`B47` Låg** - `commerce-base` Shopify-startsidan kräver Shopify-handles
  `hidden-homepage-featured-items` och `hidden-homepage-carousel`, och
  footern kräver `next-js-frontend-footer-menu`. Saknas de blir delar av
  ett färdigbyggt `commerce-base`-spår tomma. Spåra som separat
  e-commerce-sprint som antingen ger fallback-copy/produkter eller
  dokumenterar starter-kraven. Ej blocker för aktiva flöden idag (real
  codegen-scope är fortfarande `marketing-base`-only per ADR 0017).
- **`B49` Medel** - `data/starters/docs-base/src/app/layout.tsx` har en
  manuellt underhållen `<aside>`-sidebar med fyra fasta `/docs/...`-länkar
  istället för att läsa från Nextra-page-map / `_meta.ts`-filerna. Källan:
  Steward-Scout-pass på PR #24 (2026-05-14, coach + tre subagents).
  `_meta.ts`-filerna importeras inte någonstans i layouten. Fixupen i
  PR #24 (commit `3f93655`) skrev om `authoring.mdx`, `index.mdx` och
  starter-README så de tydligt säger att sidebar är manuellt
  underhållen och måste edit:as när scaffold injicerar nya MDX, men
  arkitektur-skulden står kvar. Innan `course-education -> docs-base`
  aktiveras i `SCAFFOLD_TO_STARTER` ska antingen Nextra-theme-docs
  `Layout` få fungera (PR #24-bodyn säger att den failade validering
  i miljön) eller en lokal page-map-driven sidebar bygga sig själv från
  `_meta.ts` + filsystemet. Test bör låsa relationen så framtida
  scaffold-injektion av MDX inte tyst kan saknas i nav. Ej blocker idag
  (docs-base är inte aktiverad i runtime).
- **`B53` Låg** - `governance/schemas/` saknar en `routes.schema.json` som
  validerar scaffold-routes-kontraktet som `scripts/build_site.py` redan
  hårdkräver. Buildern kräver att `routes.json` har en route med
  `id="contact"` (annars raisas `SystemExit` i `_pick_contact_route`), men
  ingen schemafil låser detta i governance-lagret. Risk: en framtida
  starter/scaffold kan tappa contact-route utan att fångas tidigt; felet
  fångas först när buildern kör. Spåra som dokumentations-/contract-
  schema-sprint som lägger till `routes.schema.json` + `validate_routes()`
  i `packages/generation/artifacts/validate.py` med auto-validering i
  `load_scaffold_registry()` (samma mönster som B22 löste för
  `scaffold.schema.json`). Ej blocker - byggtidsguarden täcker redan
  scenariot, men en schema-fil ger tidigare felfångst + IDE-stöd.
- **`B59` Medel** - StackBlitz `template:"node"`-preview (WebContainer) i
  Viewser är blockerad eller instabil i moderna Chrome-runtimes som kräver
  cross-origin isolation. Tre header-lägen testades empiriskt 2026-05-15
  (både Cursor in-app browser och lokal Chrome smoke):
  - inga isolation headers -> iframe-load blockeras med Chrome-meddelandet
    "Specify a Cross-Origin Embedder Policy to prevent this frame from being
    blocked";
  - `Cross-Origin-Embedder-Policy: require-corp` + `Cross-Origin-Opener-Policy:
    same-origin` -> iframe-load OK, men VM-handshake timeout:ar
    (`Timeout: Unable to establish a connection with the StackBlitz VM`);
  - `Cross-Origin-Embedder-Policy: credentialless` + samma COOP -> iframe-load
    OK, men StackBlitz interna `sign_in`-check faller utan credentials
    (`https://stackblitz.com/sign_in - Unsuccessful HTTP response`) och UI:t
    fastnar permanent i "Startar StackBlitz...".

  Header-experimentet committades inte. Nästa arkitekturbeslut bör vara byte
  till en lokal preview-server (per-run `next dev`-process embedded som
  same-origin iframe på `localhost:NNNN`) eller en static StackBlitz-preview
  (template `"static"` med pre-buildad HTML), inte mer header-toggling. Ej
  blocker idag: Run History + Run Details ger diagnostik utan preview, och
  lokal `npm run build` på den genererade siten fungerar fortfarande som
  verifikation. Test: open (regression-test bestäms efter arkitekturval).

### Notera (inte en bugg) - dev-preview-output utanför repo

`scripts/build_site.py` skriver dev-preview-builden till
`../sajtbyggaren-output/.generated/<siteId>` som default sedan
2026-05-14 (workspace-perf-pass). Override via `--generated-dir <path>`
eller env `SAJTBYGGAREN_GENERATED_DIR`. CI använder
`$RUNNER_TEMP/sajtbyggaren-output/.generated/`. Tester går genom
`resolve_generated_dir()` så de följer samma override. Anledningen är
att flytta tunga npm-install-/Next.js-build-output utanför Cursor-
indexerings- och file-watcher-banan så IDE:n hålls snabb. Äldre dokumen-
tation (README, builder-mvp.md, viewser-docs) nämner fortfarande
`.generated/` som om den låg i repo; uppdatera om/när det blir aktuellt
i en docs-cleanup. Ingen B-ID krävs - detta är en avsiktlig
arkitekturändring, inte en bugg.

- StackBlitz/WebContainer-preview kör tillfälligt en patchad payload
  (`next build --webpack`, `npm run build && npm run start`,
  `package-lock.json` inkluderad, `app/global-error.tsx`-override) på grund av
  kända Next 16 + WebContainer-kompatibilitetsfel. Se
  [ADR 0021](../governance/decisions/0021-stackblitz-preview-payload-workarounds.md).

(B20 stängd 2026-05-13 — se "Stängda - regression-test säkrar fixet" nedan.)

### Demo-baseline-fix 1B closure note (2026-05-15)

PR #28 / `885431b` stängde B64, B65, B66, B69, B70, B71, B72, B73, B74, B75, B76, B77, B78, B79 och B83. Kvar öppna/deferred från bug-sweep-listan: B67, B80, B81, B82, B84, B85, B86 och B87.

## Stängda - regression-test säkrar fixet

- **`B61` Hög** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) -
  `notes_for_planner` läckte som customer-facing copy på `/om-oss`,
  som `company.tagline` och som dev-jargong i service summaries efter
  demo-baseline-fix 1A. Källa: verifierings-Scout 2026-05-15.
  `scripts/prompt_to_project_input.py:_derive_story` föredrog
  `brief.notesForPlanner` som story-fallback, men briefModel skriver
  fältet på engelska som intern Phase 2-orientering ("Likely a Swedish
  electrician website targeting Malmö; prompt is minimal, so keep
  scope conservative and local."). Samma sträng landade också i
  `company.tagline` via `(notes or tagline_default)`-mönstret i
  `site_brief_to_project_input`. Plus `_service_summary` skrev
  `Justera Project Input för att förbättra texten` på rendered
  service grid (svensk dev-jargong) och `_placeholder_services` hade
  motsvarande "platshållare som genererats från din prompt"-fras.
  **Fix:** `_derive_story` ignorerar nu `notes_for_planner` helt
  (parametern kvar på signaturen för bakåtkompatibilitet, men aldrig
  använd); ny `_derive_tagline`-helper bygger taglinen från
  `businessTypeGuess` + `locationHint`; `_service_summary` returnerar
  neutral kundsvenska (`Konsultation - kontakta oss för mer
  information.`); `_placeholder_services` motsvarande engelska/svenska
  varianter. Smoke-verifierat med real briefModel: `elektriker Malmö`
  ger story `Vi är en elektriker i Malmö. Byt ut den här texten...`,
  tagline `Lokal elektriker i Malmö`, service summary `Konsultation -
  kontakta oss för mer information.` Fix: `d99f8ba`. Test:
  `tests/test_prompt_to_project_input.py::test_story_never_uses_notes_for_planner`,
  `tests/test_prompt_to_project_input.py::test_tagline_never_uses_notes_for_planner`,
  `tests/test_prompt_to_project_input.py::test_service_summaries_do_not_leak_dev_jargon`,
  `tests/test_prompt_to_project_input.py::test_placeholder_services_summary_is_customer_friendly`,
  `tests/test_prompt_to_project_input.py::test_full_pipeline_locks_no_planner_jargon_for_scout_prompt`,
  `tests/test_prompt_to_project_input.py::test_derive_tagline_builds_from_business_type_and_location`,
  `tests/test_prompt_to_project_input.py::test_derive_tagline_falls_back_when_brief_is_empty`,
  `tests/test_prompt_to_project_input.py::test_story_constructs_placeholder_when_notes_missing`
  (uppdaterad: låser nu frånvaron av "Justera Project Input"-jargong).
  **Scope-förtydligande:** stängningen gäller notesForPlanner/story/tagline/
  service-summary-ytorna i 1A-hotfixen; relaterade öppna poster i samma
  kategori är B65, B68 och B88.

- **`B62` Hög** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) -
  `packages/generation/brief/extract.py:detect_language` slog fel på
  korta svenska prompts utan stop-ord. `SWEDISH_HINTS` är en hårdkodad
  lista på ~20 vanliga ord; prompts som "frisör Göteborg" eller
  "naprapatklinik Stockholm" har inget av dessa tokens, så language
  detekterades som "en" och hela sajten genererades på engelska ("Hair
  salon in Göteborg", `country=Sweden`). Verifierat på 2 av 4
  Verifierings-Scout-case 2026-05-15. **Fix:** ny cascading heuristik:
  (1) SWEDISH_HINTS-match → sv (samma som tidigare); (2) ENGLISH_HINTS-
  match (ny lista med ~30 engelska stopord och website-shaped verbs)
  → en; (3) någon token har å/ä/ö → sv (fångar `frisör Göteborg`);
  (4) default sv (operatörspopulation ~95% svensktalande, fångar
  `naprapatklinik Stockholm`). Cascade-ordningen sätter ENGLISH_HINTS
  FÖRE å/ä/ö-checken så `electrician website in Malmö` fortsatt blir
  `en` (Malmö har ö men prompten har stark engelsk signal). Plus ny
  `_normalize_location_hint`-helper i `prompt_to_project_input.py`
  som skriver om `locationHint="Sweden"` till `Sverige` på svenska
  builds, så `location.city` inte landar som engelsk land-namn på en
  svensk sajt. Smoke-verifierat med real briefModel: `frisör Göteborg`
  ger nu `language=sv`, `H1=Frisör i Göteborg`, `country=Sverige`.
  Fix: `d99f8ba`. Test:
  `tests/test_extract_site_brief.py::test_detect_language_short_swedish_prompts_default_to_sv`
  (parametriserad över `frisör Göteborg`, `naprapatklinik Stockholm`,
  `Skapa en hemsida för Volt & Co`, `elektriker Malmö`,
  `tandläkarpraktik`, `yoga`),
  `tests/test_extract_site_brief.py::test_detect_language_english_prompts_with_swedish_chars_stay_en`
  (parametriserad över fyra engelska prompts, inkl. `electrician
  website in Malmö`),
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_translates_country_on_swedish_builds`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_preserves_english_country`,
  `tests/test_prompt_to_project_input.py::test_normalize_location_hint_preserves_real_city`,
  `tests/test_prompt_to_project_input.py::test_swedish_brief_with_country_location_renders_swedish_city`.
  **Scope-förtydligande:** stängningen gäller language-cascaden och
  `Sweden -> Sverige`-normalisering i 1A-hotfixen; relaterade öppna poster
  för end-to-end-språkstöd är B67, B89, B90 och B91.

- **`B63` Medel** (stängd 2026-05-15, demo-baseline-fix 1A-hotfix) -
  `scripts/prompt_to_project_input.py:_BUSINESS_TYPE_LABEL_SV` hade
  glipor mot briefModels faktiska businessType-slugs. briefModel
  returnerade `business_type="e-commerce"` (med bindestreck) men
  map:en hade bara `"ecommerce"` och `"ecommerce-shop"`; `naprapath-
  clinic` saknades helt. Resultat: H1 blev `Sajt för e commerce` /
  `Sajt för naprapath clinic` istället för `Webbshop` / `Naprapatklinik`.
  Källa: verifierings-Scout 2026-05-15. **Fix:** map:en utökad med
  ~10 hyphen-varianter för briefModel-slugs som faktiskt observerats
  eller är symmetri-fix för befintliga entries: `e-commerce` →
  `webbshop`, `ecommerce-store` → `webbshop`, `naprapath-clinic` →
  `naprapatklinik`, `naprapat-clinic` → `naprapatklinik`,
  `electrical-services` → `elektriker`, `electrical-contractor` →
  `elektriker`, `plumbing-services` → `rörmokare`, `barber-shop` →
  `barberare`, `flower-shop` → `blomsterhandel`, `chiropractic-clinic`
  → `kiropraktor`, `physiotherapy-clinic` → `sjukgymnast`,
  `painting-services` → `målare`, `carpentry-services` → `snickare`,
  `construction-company` → `byggfirma`. `naprapat` och `naprapath`
  pekar nu också på `naprapatklinik` (uppdaterat från `naprapat` så
  H1 läser `Naprapatklinik i Stockholm` snarare än `Naprapat i
  Stockholm`). Plus fallback i `_company_business_label` om-skriven
  från `Sajt för {slug}` till `företag som arbetar med {slug}` så
  framtida obekanta briefModel-slugs läser som svensk prosa istället
  för broken placeholder copy. Lookup strippar och lower-casar redan
  via `business_type.strip().lower()`, så `E-Commerce` /
  `  e-commerce  ` matchar också. Fix: `d99f8ba`. Test:
  `tests/test_prompt_to_project_input.py::test_business_type_map_covers_briefmodel_hyphenated_slugs`
  (parametriserad över 12 hyphen-varianter inkl. `e-commerce`,
  `naprapath-clinic`, `electrical-services`, `plumbing-services`),
  `tests/test_prompt_to_project_input.py::test_unknown_business_type_uses_swedish_fallback_phrase`,
  `tests/test_prompt_to_project_input.py::test_business_type_map_lookup_is_case_and_whitespace_safe`,
  `tests/test_prompt_to_project_input.py::test_company_name_for_e_commerce_brief_uses_swedish_label`,
  `tests/test_prompt_to_project_input.py::test_company_name_for_naprapath_clinic_brief_uses_swedish_label`,
  `tests/test_prompt_to_project_input.py::test_company_name_falls_back_for_unknown_business_type_slug`
  (uppdaterad: låser nu frånvaron av pre-hotfix `Sajt för X`-fallbacken).

- **`B60` Hög** (stängd 2026-05-15, post-merge audit av PR #27) -
  follow-up-versioneringen från PR #27 hade fyra kontraktsbrott:
  1. Versionerade snapshots inte immutabla:
     `scripts/prompt_to_project_input.py:write_project_input` skrev
     `<siteId>.vN.project-input.json` + `<siteId>.vN.meta.json` med
     `Path.write_text`, som tyst skriver över befintliga filer. Två
     samtidiga follow-ups som båda läste version=N och valde N+1
     hade skrivit över varandras snapshots; en operatör som av
     misstag återanvände ett siteId/projectId/version-tripp hade
     skrivit över v1. Det bryter PR #27:s "older versions stay
     byte-stable"-löfte.
  2. Engelsk workflow-text läckte ut i kundvänd copy:
     `merge_followup_project_input` la in `" Follow-up request: <prompt>"`
     i slutet av `company.story`. `scripts/build_site.py:render_about`
     renderar `company.story` som JSX direkt på `/om-oss`-sidan, så
     varje follow-up-prompt blev synlig som engelsk intern
     workflow-text på en svensk kundsajt. `meta.followUpPrompt` fanns
     redan som korrekt operatörs-yta för samma data.
  3. Pekar-uppdateringen var icke-atomisk: fyra sekventiella
     `Path.write_text`-anrop betydde att en process-crash mellan två
     anrop kunde lämna pointer-meta och pointer-project-input ur
     synk (t.ex. meta v=2 men pointer-project-input fortfarande v=1).
  4. `load_prompt_input_meta` föll tyst tillbaka till `init` när ett
     dossier-filnamn matchade prompt-input-mönstret men sidecaren
     saknades. En korrupt `data/prompt-inputs/`-mapp hade då
     producerat follow-up-builds märkta som init utan `projectId`/
     `version` istället för att larma operatören.
  **Fix:** `_write_immutable_snapshot` använder `open(..., "x")` så
  versionerade snapshots failar med `SystemExit` om filen redan
  finns. `_atomic_write_text` skriver via `tempfile.mkstemp` +
  `os.replace` så pointer-filer är atomic-replace istället för
  truncate-and-write. `merge_followup_project_input` bevarar nu
  `previous.company.story` byte-för-byte och låter `meta.followUpPrompt`
  vara den enda operatörs-/system-ytan för follow-up-prompten.
  `scripts/build_site.py:load_prompt_input_meta` skiljer nu på (a)
  versionerade snapshots utan sidecar och (b) current pointer under
  `data/prompt-inputs/` utan sidecar (båda failar) vs (c) curated
  examples utanför `data/prompt-inputs/` (behåller init-mode-kontraktet).
  Test:
  `tests/test_prompt_to_project_input.py::test_versioned_snapshot_refuses_overwrite`,
  `tests/test_prompt_to_project_input.py::test_followup_does_not_inject_workflow_text_into_company_story`,
  `tests/test_prompt_to_project_input.py::test_pointer_writes_use_atomic_replace`,
  `tests/test_prompt_to_project_input.py::test_generate_followup_bumps_version_and_reuses_project_id`
  (uppdaterad: lock:ar att `Follow-up request` INTE finns i
  `company.story` och att story matchar v1 byte-för-byte),
  `tests/test_builder_hardening.py::test_load_prompt_input_meta_fails_loud_when_versioned_sidecar_missing`
  (täcker versioned-, current-pointer-under-prompt-inputs- och
  curated-examples-scenarierna).

- **`B57` Medel** (stängd 2026-05-14, reviewer-fynd-follow-up efter A-mini
  cleanup) - B55-guarden från föregående sprint kollade bara
  `apps/viewser/.env` och `apps/viewser/.env.local` med hårdkodade
  Path-objekt. `.gitignore` säger däremot `.env.*` (allt) undantag
  `.env.example`, så en framtida `.env.production`, `.env.staging`,
  `.env.development` eller någon annan variant skulle kunna trackas
  utan att fångas av testet. Reviewer-fyndet (Cursor-agent, 2026-05-14)
  flaggade detta som 35% sannolikhet, 8/10 impact (secret leakage).
  **Fix:** testet kör nu `git ls-files apps/viewser/.env*` och bygger
  ett set av alla trackade matchningar. Den enda tillåtna är
  `apps/viewser/.env.example` (publik placeholder, explicit
  `!.env.example` i `.gitignore`). Alla andra trackade `.env*` failar
  testet med tydlig `git rm --cached`-remediation.
  Test:
  `tests/test_viewser_files.py::test_viewser_env_file_is_not_committed`
  (samma test, ny robust glob-baserad logik).

- **`B58` Låg** (stängd 2026-05-14, reviewer-fynd-follow-up efter A-mini
  cleanup) - B54-filtret från föregående sprint blockerade alla
  `.env*`-filer från StackBlitz-upload-loopen via prefix-check på
  `.env`. Det inkluderade `.env.example`, vilket är publik placeholder
  som **ska** följa med upp till preview så operatörer ser vilka
  env-vars sajten förväntar sig. Reviewer-fyndet (Cursor-agent, 2026-05-14)
  flaggade detta som 20% sannolikhet, 3/10 impact (dev/preview-friktion,
  funktionell regression).
  **Fix:** `isDotenvFile` i `apps/viewser/lib/stackblitz-files.ts` har
  nu explicit allowlist-check: `if (lower === ".env.example") return false`
  innan den generella `startsWith(".env")`-check:en. `.env.example` följer
  därför med upp till preview medan alla andra `.env*`-varianter
  (`.env`, `.env.local`, `.env.production`, `.ENV`, `.Env.Local`) blockas.
  Test:
  `tests/test_viewser_files.py::test_stackblitz_files_filter_dotenv_files_from_preview_upload`
  (utökad till att kräva både prefix-check, `toLowerCase()` och
  `.env.example`-allowlist),
  `tests/test_viewser_files.py::test_stackblitz_files_allow_env_example_through_filter`
  (källkods-lock på `=== ".env.example"`-pattern).

- **`B56` Medel** (stängd 2026-05-14, commit `8fae26a`) - StackBlitz-preview
  för Next 16-runs startade via `next dev` (Turbopack default), vilket kunde
  faila i WebContainer med felet "Turbopack is not supported on this
  platform ... use next dev --webpack".
  **Fix:** `apps/viewser/lib/stackblitz-files.ts` patchar nu bara
  `package.json`-bytesen som skickas till StackBlitz (ingen diskmutation av
  starter eller run-snapshot): `scripts.dev` säkras via
  `ensureWebpackFlag(...)` och `stackblitz.startCommand` sätts till
  `npm run dev`. Inline-patchen körs endast för
  `relPath === "package.json"`.
  Test:
  `tests/test_viewser_files.py::test_stackblitz_files_patches_package_json_for_webpack`,
  `tests/test_viewser_files.py::test_stackblitz_files_does_not_duplicate_webpack_flag`,
  `tests/test_viewser_files.py::test_stackblitz_files_does_not_write_back_package_json_to_disk`.

- **`B51` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `scripts/build_site.py:render_layout` skrev nav-labels direkt som JSX-
  text utan `_jsx_safe_string`-wrap. Kända route-id:n (`home`, `services`,
  `products`, `about`, `contact`) gav alltid säkra svenska labels från
  `_NAV_LABEL_BY_ROUTE_ID`-lookupen, men en framtida scaffold som
  introducerar ett okänt route-id föll via `_nav_label_for_route` till
  `route_id.replace("-", " ").replace("_", " ").title()` och labeln
  skrevs rått som JSX-text. Inkonsistent jämfört med kundtext (B30 gör
  redan all kundtext via `_jsx_safe_string`); en governance-driven
  ändring av ett route-id skulle kunna producera ogiltig TSX.
  **Fix:** header-nav och footer-nav-länkar i `render_layout` wrappar
  nu `label` i `_jsx_safe_string(label)`. Diskussion om varför labeln
  inte är "trusted" trots att den kommer från scaffold-fil: route-id är
  inte path-validerat på samma sätt som `_route_href` validerar paths
  (B50), så samma defensiva discipline appliceras nu uniformt.
  Test:
  `tests/test_builder_route_emission.py::test_render_layout_jsx_escapes_unknown_nav_label_fallback`,
  `tests/test_builder_route_emission.py::test_render_layout_escapes_known_nav_labels_consistently`.

- **`B52` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `_nav_items_from_scaffold` appenderade `("/spel", "Spel")` till
  nav-items om dossier-routen `/spel` fanns, utan dedupe mot scaffoldens
  `defaultRoutes`. För aktuella scaffolds är `/spel` inte deklarerat så
  duplicering triggas inte idag, men en framtida scaffold som adopterar
  `/spel` som default-route + samtidig interactive-game-loop-dossier
  hade gett två identiska nav-länkar.
  **Fix:** `_nav_items_from_scaffold` bygger nu en `existing_paths`-set
  av scaffold-paths och appendrar bara `/spel` från dossier-routes om
  pathen inte redan finns. Scaffold-ordning bevaras, dossier-injicerad
  `/spel` hamnar sist.
  Test:
  `tests/test_builder_route_emission.py::test_nav_items_dedupes_spel_when_scaffold_also_declares_it`.

- **`B54` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `apps/viewser/lib/stackblitz-files.ts:readRunFilesForStackblitz` läser
  varje fil under run-mappens `generated-files/`-snapshot och bundlar
  den för StackBlitz-preview-uploaden. Filterlogiken hade bara
  `FILES_TO_SKIP = {"package-lock.json"}` + `BINARY_EXTENSIONS`; den
  filtrerade **inte** `.env*`-filer explicit. Builder blockerar redan
  `.env*` från att hamna i `generated-files/` (B4/B5,
  case-insensitive ignore i `copy_starter`), så scenariot triggas
  inte i normalt flöde. Men upload-lagret bör ha egen defensiv guard
  så en framtida starter, manuell operatörsedit eller drift i buildern
  inte kan läcka en `.env`/`.env.local`/`.env.production` upp till en
  publik StackBlitz-preview.
  **Fix:** ny `isDotenvFile(basename)`-helper som returnerar
  `basename.toLowerCase().startsWith(".env")`. Walk-loopen i
  `readRunFilesForStackblitz` hoppar över filer som matchar. Speglar
  B4:s case-variant-täckning (`.ENV`, `.Env.Local`).
  Test:
  `tests/test_viewser_files.py::test_stackblitz_files_filter_dotenv_files_from_preview_upload`
  (källkods-lock som kräver att `.toLowerCase().startsWith(".env")`
  finns i filen).

- **`B55` Låg** (stängd 2026-05-14, A-mini cleanup efter B50) -
  `tests/test_viewser_files.py::test_viewser_env_file_is_not_committed`
  hette `_is_not_committed` men kontrollerade `(path).exists()`, vilket
  failed-fel på en gitignored lokal `.env.local` (en korrekt Next.js-
  dev-workflow för Viewser). Operatören fick en falsk "committed"-alarm
  trots att filen var ignorerad. Testnamn och kontroll var ur fas.
  **Fix:** ny `_is_tracked_in_git(path)`-helper kör
  `git ls-files --error-unmatch <rel>` och returnerar `True` iff filen
  är trackad. Testet kollar nu git-tracking, inte disk-existens. En
  lokal gitignored `.env.local` får finnas; en faktiskt committad
  `.env`/`.env.local` failar testet med tydligt meddelande inkluderande
  remediation (`git rm --cached`).
  Test:
  `tests/test_viewser_files.py::test_viewser_env_file_is_not_committed`
  (samma test, ny korrekt semantik).

- **`B50` Medel** (stängd 2026-05-14, commits `4940cbb` + `f787eb7`) -
  `scripts/build_site.py` interpolerade scaffold-route-paths direkt i
  TSX-attribut (`href="{contact_path}"`, `href="{listing_path}"`) och
  `_pick_contact_route()` föll tyst tillbaka till `/kontakt` när
  scaffold saknade contact-route. Fix: ny `_route_href()` serialiserar
  scaffold-route-hrefs som JSX-uttryck, `_pick_contact_route()` fail-fastar
  med route-id-lista när contact-route saknas och `render_home()` omitar
  listing-CTA:n när scaffolden saknar både `services` och `products`
  i stället för att hitta på `/tjanster`. Scout-follow-up `f787eb7`
  lägger samma kanoniska route-path-validering framför både `_route_href()`
  och `route_to_page_path()`, så protocol-relative URLs, backslashes,
  query/fragments och dot-segments inte kan bli hrefs eller page paths.
  Test:
  `tests/test_builder_route_emission.py` låser syntetisk route med
  specialtecken, saknad contact-route, saknad listing-route,
  non-canonical route paths och befintliga B13/B45-regressioner.
  `painter-palma --skip-build` verifierades isolerat under
  `.generated/b50-*` och `.generated/route-hardening-*`.

- **`B45` Låg** (stängd 2026-05-14, B45 Builder-mini-sprint) -
  `scripts/build_site.py` hade hardcoded `/kontakt`-CTAs i
  `render_layout`, `render_home` och `render_services`, trots att
  `_pick_contact_route` redan fanns och användes av `render_products`.
  En framtida scaffold som flyttar contact-routen till exempelvis
  `/kontakta-oss` skulle därför få nav + products-CTA rätt men layout/home/
  services-CTAs fel.
  **Fix:** `render_layout`, `render_home`, `render_services` och
  `render_products` route:ar nu kontakt-CTA:er via `contact_path`, och
  `write_pages()` trådar `contact_route["path"]` från scaffoldens
  `defaultRoutes` till alla fyra renderer-ytor. Direkta renderer-unit-
  tester behåller bakåtkompatibel fallback `/kontakt`.
  Fix: `6daee58`.
  Test:
  `tests/test_builder_route_emission.py::test_contact_ctas_use_threaded_contact_path_across_renderers`,
  `tests/test_builder_route_emission.py::test_contact_renderer_helpers_do_not_literal_code_kontakt_href`,
  `tests/test_builder_route_emission.py::test_write_pages_threads_contact_path_into_all_contact_ctas`.

- **`B48` Medel** (stängd 2026-05-14, follow-up-semantik sprint) -
  `scripts/dev_generate.py` exponerade `--mode followup` och
  `--project-id`, och Backoffice Playground skickade dessa vidare till
  subprocessen, men dev-driverns planfas hårdkodade fortfarande
  `engine_mode="init"` och `project_id=None` när den anropade
  `produce_site_plan()`. Resultat: `input.json` kunde säga
  `mode=followup` medan `generation-package.json` sa `engineMode=init`
  och saknade `projectId`.
  **Fix:** `run_phase_plan()` tar nu `mode` och `project_id` som
  keyword-only argument och skickar dem vidare till
  `produce_site_plan()`. `main()` trådar CLI/env-värdena från
  `--mode` / `--project-id` hela vägen till planfasen, både för
  `--phase all` och separata `--phase plan`-körningar.
  Test:
  `tests/test_dev_generate.py::test_dev_generate_followup_threads_mode_and_project_id_to_package`
  låser att `input.json` och `generation-package.json` matchar i
  follow-up-läget. `tests/test_backoffice_trace.py::test_playground_runner_forwards_followup_project_id`
  låser att Backoffice Playground-runnern skickar `--project-id` och
  `SAJTBYGGAREN_MODE=followup` till subprocessen.

- **`B44` Hög** (stängd 2026-05-14, post-audit Builder-fix) - PromptBuilder
  och `app/page.tsx` tolkade alla returnerade `runId` som lyckad build.
  `lib/build-runner.ts` returnerar medvetet `runId` + `buildResult` även
  när `buildResult.status === "failed"` (B40-kontraktet: failed runs
  måste synas i Run History), men `/api/prompt` skickade inte vidare
  status-fältet och PromptBuilder visade grön "Build klar" för fail-
  runs. Sannolikhet 85%, impact 7/10.
  **Fix:** `/api/prompt/route.ts` läser nu `build-result.json:status`
  via en defensiv `extractBuildStatus`-helper och exponerar fältet som
  `buildStatus` på response-payloaden. PromptBuilder klassificerar
  utfallet via en ny `classifyBuildStatus`-helper (`ok` /
  `degraded` / `failed` / `unknown`) och renderar tre distinkta UI-
  paneler (grön success, gul varning, röd failed). `app/page.tsx`
  tar emot `PromptBuildOutcome` i `onBuildDone` och använder
  `headerStatusForOutcome` så headern aldrig säger "Build klar via
  prompt:" för en degraderad eller failed run.
  Test:
  `tests/test_viewser_files.py::test_prompt_route_surfaces_build_status`,
  `tests/test_viewser_files.py::test_prompt_builder_classifies_failed_build_distinctly`,
  `tests/test_viewser_files.py::test_page_uses_outcome_aware_header_for_prompt_build_done`.

- **`B46` Låg** (stängd 2026-05-14, post-audit Builder-fix) - Legacy
  `apps/viewser/components/chat-panel.tsx` var inte längre monterad
  någonstans (PromptBuilder tog över i `fd67fbd`), men filen levde
  kvar och innehöll samma "runId == success"-logik som B44. Audit
  rekommenderade antingen samma status-fix eller borttagning;
  borttagning valdes för att eliminera duplicerad surface i
  stället för att underhålla två parallella prompt-/build-paneler.
  **Fix:** `components/chat-panel.tsx` raderad. `tests/test_viewser_files.py`
  uppdaterad: `chat-panel.tsx` borttaget från required-files-listan,
  `test_chat_panel_marks_prompt_as_experimental` ersatt med
  `test_chat_panel_component_is_removed` som låser borttagningen.
  `tests/test_viewser_prompt_primary.py` docstring uppdaterad,
  inline-asserts pekar nu på audit-fixen istället för "remains as a
  component for now". `scripts/check_term_coverage.py` allowlist
  rensar `ChatPanel`/`ChatPanelProps`/`BuildModelUsage` som inte
  längre finns någonstans i koden. `governance/rules/vocabulary-discipline.md`
  byter exempel `ChatPanel` mot `PromptBuilder`; `.cursor/rules/`
  spegeln synkad via `scripts/rules_sync.py`. `/api/chat`-routen
  och `lib/openai.ts` lämnas orörda — de är fortfarande standalone
  endpoints och Scout pekade inte ut dem.

- **`BO2` Medel** (stängd 2026-05-14, squash-merge `e1ad5ca` via PR #23) - Backoffice trace
  viewer dumpade tidigare bara rå dataframe för `trace.ndjson`.
  Fix: ny backoffice-helper `backoffice/views/_trace.py` läser halvskrivna
  trace-rader defensivt, summerar events, grupperar per fas, lägger filter för
  fas/status/söktext och markerar fel, varningar, quality-, repair- och
  codegen-events tydligt. Både `Engine Runs` och `Playground` använder samma
  viewer och behåller rådata i expander.
  Test: `tests/test_backoffice_trace.py::test_load_trace_events_tolerates_partial_ndjson`,
  `tests/test_backoffice_trace.py::test_trace_summary_and_severity_mark_important_events`,
  `tests/test_backoffice_trace.py::test_trace_views_use_structured_trace_viewer`.

- **`BO4` Medel** (stängd 2026-05-14, squash-merge `e1ad5ca` via PR #23) -
  `backoffice/views/playground.py` var en svart låda medan
  `scripts/dev_generate.py` körde via `subprocess.run(... timeout=180)`.
  Fix: Playground använder nu en kontrollerad `subprocess.Popen`-runner som
  visar körstatus, fas, tid, exit code och senaste loggrader under/efter
  körning. Timeout dödar endast den startade processen och bevarar fångad
  output. RunId-parsningen ligger i egen helper.
  Test: `tests/test_backoffice_trace.py::test_playground_extracts_run_id_from_supported_outputs`,
  `tests/test_backoffice_trace.py::test_playground_runner_uses_popen_not_subprocess_run`.
  Kvarvarande avgränsning: riktig cancellation/background-jobb kräver separat
  design och spåras som `BO4-followup-cancel`.

- **`B20-followup-lucide` Låg** (stängd 2026-05-13, squash-merge
  `04fc2fa` via PR #21) - följduppgift på den stängda B20-posten:
  full `npm run build` mot `.generated/atelje-bird/` (eller någon
  annan ecommerce-lite-genererad sajt) fallerade med
  `Module not found: lucide-react` eftersom
  `scripts/build_site.py:write_pages` hardcodar lucide-imports per
  renderer men `commerce-base/package.json` bara hade
  `@heroicons/react`. `marketing-base` har lucide som dep så
  konflikten var osynlig pre-B20.

  **Fix:** ny [ADR
  0020](../governance/decisions/0020-commerce-base-lucide-react.md)
  dokumenterar operatörsgivet dep-godkännande. `lucide-react`
  ^1.14.0 (matchar marketing-base:s exakta version) tillagd i
  `data/starters/commerce-base/package.json`;
  `data/starters/commerce-base/package-lock.json` regenererad via
  `npm install` (1 added package). `data/starters/commerce-base/
  README.md` ny sektion "Runtime-deps utöver upstream" som pekar
  på ADR 0020.

  Verifiering: `cd data/starters/commerce-base && npm run build`
  grön (13 routes prerendered, Shopify env-skip-loggrad);
  `cd .generated/atelje-bird && npm install && npm run build`
  grön (11 statiska sidor inkl `/produkter` plus commerce-base:s
  egna dynamiska routes); `pytest tests/ -q` 381 passed + 3 skipped;
  4 guards + ruff gröna; Cursor Bugbot på PR #21 SUCCESS-conclusion
  (inga inline-fynd).

  Out of scope (architecturskuld kvarstår): `write_pages` är
  fortfarande hardcoded mot lucide. En framtida starter utan
  lucide skulle träffa samma konflikt. Spåras i
  `docs/current-focus.md` Queue som "`write_pages` icon-bibliotek-
  agnostisk refactor".

- **`B20` Låg** (stängd 2026-05-13, squash-merge `75c980b` via PR #20)
  - aktiverade `ecommerce-lite -> commerce-base`-routingen. Spåret
  hade två steg: step 1 (vendor-import av
  `data/starters/commerce-base/` från `vercel/commerce` upstream
  `1df2cf6`) landade i PR #16 commit `4b4c3af` enligt [ADR
  0018](../governance/decisions/0018-b20-commerce-base-harmonisering.md).
  Step 2 var blockerat av B13b (route-emission) tills `fda1464`
  löste `scripts/build_site.py:write_pages` att vara scaffold-driven.

  **Fix:** ny [ADR
  0019](../governance/decisions/0019-b20-step-2-mapping-activation.md)
  aktiverar mappningen explicit (adresserar ADR 0018:s "kräver egen
  ADR" och `.cursor/BUGBOT.md` "Mapping and routing risk"-regelns
  krav på ADR i samma PR).
  `packages/generation/planning/plan.py:SCAFFOLD_TO_STARTER` har
  `ecommerce-lite: commerce-base`. `data/starters/README.md`:s
  `scaffold-starter-mapping`-block har raden
  `ecommerce-lite: commerce-base` utan `(B20: ...)`-noten,
  Status-kolumnen för `commerce-base` uppdaterad till "aktiverad i
  B20 step 2", och avsnittstexten ovanför mapping-blocket
  avgenericerad.
  `packages/generation/codegen/codegen.py:_REAL_CODEGEN_STARTERS`
  förblir `{"marketing-base"}` (ADR 0017 + ADR 0019:s "INTE
  beslutar"-sektion): ecommerce-lite kör genom
  `source=deterministic-v1` codegen tills real-codegen-scope
  utvidgas i en separat sprint med egen ADR-utökning.

  Test: `tests/test_starter_scaffold_mapping.py` (8 tester) gröna,
  inklusive `test_b20_temporary_mapping_is_explicit` som auto-skippar
  positivt när mappningen är `commerce-base`.
  `tests/test_planning.py::test_produce_site_plan_picks_ecommerce_lite_on_commerce_signal`
  source-lock uppdaterad till `commerce-base`.
  `python scripts/build_site.py --dossier
  examples/atelje-bird.project-input.json --skip-build` ger
  `build-result.json starterId=commerce-base`,
  `routes=[/, /kontakt, /om-oss, /produkter]` (inget `/tjanster`),
  `quality-result.json status=ok`.
  `app/produkter/page.tsx` emitteras, `app/tjanster/page.tsx` INTE.

  Bugbot-rundor: 1 iteration, 2 fynd. Fynd 1 (Hög: SCAFFOLD_TO_STARTER
  utan ADR) löst via ADR 0019 i `af7fac4`. Fynd 2 (Medium: PR Ready
  trots Known risks/blockers) hanterad genom att flytta
  lucide-react-noten till "Post-merge sanity needed" i PR-
  beskrivningen; Bugbots inline-comment-API rapporterade fyndet
  som carry-over på senaste commit men UI markerade fynd 1 som
  "Show resolved" och alla CI-checks (Cursor Bugbot NEUTRAL,
  governance SUCCESS, GitGuardian SUCCESS) passerade.

  **Known follow-up (stängd 2026-05-13 via PR #21 + ADR 0020 — se
  separat post nedan):** lucide-react-konflikten är löst via väg A
  (lägg dep i commerce-base). Full `npm run build` mot
  `.generated/atelje-bird/` är nu grön. `write_pages` hardcodar
  fortfarande lucide-imports vilket lämnar arkitekturskuld för en
  framtida starter som inte använder lucide; den skulden spåras
  i `docs/current-focus.md` Queue och i ADR 0020:s "INTE beslutar".

- **`B13b` Låg** (stängd 2026-05-13, squash-merge `fda1464` via PR #19) -
  `scripts/build_site.py:write_pages` var hårdkodad mot
  `local-service-business`-routes (`/tjanster`, `/om-oss`, `/kontakt`)
  på fyra nivåer (`_nav_items()`, hardcoded `/tjanster`-CTA i
  `render_home`, `write_pages()`, avsaknad av `render_products`).
  Blockerade aktiveringen av `ecommerce-lite -> commerce-base` (B20
  step 2): ad-hoc-generation gav Quality Gate `status=degraded` med
  route-scan failure `"/produkter -> app\produkter\page.tsx
  (saknas)"`.

  **Fix:** `write_pages` läser nu scaffoldens `routes.json` och
  dispatchar per route id (home/services/products/about/contact). Ny
  `render_products`-renderer för `/produkter` med scaffold-driven
  `contact_path`. Nya helpers `_nav_items_from_scaffold`,
  `_pick_listing_route`, `_pick_contact_route`, `_NAV_LABEL_BY_ROUTE_ID`,
  `_LISTING_COPY_BY_ROUTE_ID`. Okänt route-id ger `SystemExit` så
  scaffolds inte tyst kan saknas en renderer.
  "Writing pages: ..."-printet flyttat till FÖRE `write_pages`-anropet
  (Bugbot-fynd: tidigare post-call print gav operatör inga ledtrådar
  när `write_pages` misslyckades med `SystemExit`). Ny
  `examples/atelje-bird.project-input.json` (ecommerce-lite-fixture)
  för end-to-end-smoke.

  Test: `tests/test_builder_route_emission.py` (21 tester) låser
  scaffold-driven dispatch, nav/listing/contact-path-threading,
  print-ordningen samt ecommerce-lite-smoken
  `test_ecommerce_lite_fixture_writes_produkter_and_passes_route_scan`.

  Bugbot-rundor under granskning: 3 fynd, alla åtgärdade (print-order
  `7f670b8`, `/kontakt`-hardcoding i `render_products` `5ac4ab8`,
  PR-description-scope `gh pr edit`). Pre-existing hardcoded
  `/kontakt`-CTAs i `render_home/services/layout` kvarstår som
  teknisk skuld (predaterar denna PR) - tracked under "Öppna" om
  någon vill skriva ny B-ID på det.

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
