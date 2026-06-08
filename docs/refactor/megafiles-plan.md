---
title: Refaktorplan för backend-megafilerna
status: förslag (plan only — ingen kod körs i denna lane)
ägare: backend (lane C, Scout/Steward)
datum: 2026-06-09
---

# Refaktorplan för backend-megafilerna

Den här filen är en **plan, inte en åtgärd**. Den kartlägger de tre största
backend-filerna och föreslår en ordnad serie mycket små, beteendebevarande
extraktioner (slices) som var och en kan mergas självständigt. Inga slices körs
i denna lane — varje slice blir sitt eget lilla framtida arbete med egna
paritetstester.

## Ordningsregel (läs först)

Refaktorn får **inte** starta förrän kärnloopen är produktbevisad och stabil:

> prompt -> företagshemsida -> preview -> följdprompt -> ny version

Konkret betyder det att de två öppna produktblockerna i
[`docs/current-focus.md`](../current-focus.md) ska vara gröna först:

1. gating så att en färsk build hittar projekt-input på disk
   (`data/prompt-inputs/<siteId>.project-input.json`), och
2. **synlig** render av section_add med sid- och positionsplacering
   (idag är section_add mount-only: `applied=true` men `appliedVisibleEffect=false`).

Motivet: megafilerna är motorhjärtat. Att städa dem innan följdprompt-loopen är
bevisad stabil riskerar att maskera eller införa regressioner i exakt den yta
som ska levereras. Refaktor är beteendebevarande hygien — den är alltid lägre
prioriterad än produktbevis. Denna regel upprepas per fil nedan och
sammanfattas sist.

## Lässpår och avgränsningar

- Alla radnummer nedan är **vägledande ögonblicksbilder** (2026-06-09). Filerna
  växer; lokalisera alltid om via symbolnamn (funktions-/klassnamn), inte via rad.
- Kod-identifierare hålls på engelska; denna plan-text är på svenska
  (per `AGENTS.md`).
- Repo-gränsen som styr allt nedan: produkt-, kontroll- och reparationslogik bor
  i `packages/generation/`; `scripts/` ska bara hålla tunn koppling (wiring) och
  command-line-ingångar. Flera slices nedan flyttar logik *nedåt* in i paket som
  redan finns.
- Skydds-tester som redan låser invarianter får inte brytas av någon slice. Den
  viktigaste är `tests/test_build_site_size.py` (se del 2).

### Nuvarande storlek

| Fil | Rader (2026-06-09) | Roll |
| --- | --- | --- |
| `packages/generation/build/renderers.py` | 5551 | sid- och sektionsrenderare för den deterministiska byggaren |
| `scripts/build_site.py` | 5266 | byggar-ingång + orkestrering (faser 1–3) + version/följdprompt |
| `scripts/prompt_to_project_input.py` | 3697 | prompt/brief -> projekt-input, samt följdprompt-merge |

### Befintliga paketlager (extraktionsmål finns redan)

`packages/generation/` innehåller redan: `artifacts`, `brief`, `build`,
`codegen`, `discovery`, `engine`, `followup`, `maintenance`, `orchestration`,
`planning`, `quality_gate`, `repair`. Under `build/` finns redan syskonmodulerna
`blueprint_render.py`, `contact_placeholders.py`, `dispatcher.py`,
`immutable_builds.py`, `renderers.py`, `static_assets.py`, `subprocesses.py` och
`targeted_render.py`. Det betyder att de flesta slices nedan flyttar kod till
**redan existerande** lager med ett etablerat registrerings-mönster — inte till
nyuppfunna platser.

---

## Del 1 — `packages/generation/build/renderers.py` (städas först)

### 1.1 Ansvarskarta och naturliga sömmar

Modulen rymmer både sidrenderare (`render_home` m.fl.) och sektionsrenderare
(`render_section_*`). Sektionsrenderarna registreras vid import-tid i
dispatcher-registret via `.update(...)`-block, så registret är fyllt innan någon
anropare använder det.

| Grupp | Representativa symboler | Ungefärligt radspann | Naturlig söm? |
| --- | --- | --- | --- |
| Rena format-/util-hjälpare | `_js_string_literal`, `_jsx_safe_string`, `_route_href`, `_phone_href`, `_normalise_hex_color`, `_nav_items_from_scaffold`, `_pick_contact_route`, `_pick_listing_route`, `route_to_page_path`, `write` | 119–227 | delvis (många är tunna omslag runt den lata shimmen mot byggaren) |
| Layout | `render_layout` | 228–599 | ja, nästan fristående |
| Hero-subsystem | `render_section_hero`, `_hero_style_for`, `_render_hero_block`, `_render_hero_background_video`, `_render_hero_usp_chips`, `_extract_usps`, `_unsplash_hero_url` | 600–788, 2356–2786 | ja (sammanhållet) |
| Generiska sektionsrenderare | produkter/commerce, kontakt, trust, om/team, tjänster, faq, galleri, testimonials, story | 789–1474, 2784–3036, 3792–3917 | ja |
| Restaurang/hospitality | `render_section_menu_*`, `render_section_booking_*`, hours/policy-stubbar, `_render_restaurant_route`, `render_menu`, `render_booking` | 3369–4051 | ja (mycket sammanhållet, registerdrivet) |
| Behandling/credential/expertis/practice | `render_section_treatment_*`, `render_section_credentials`, `render_section_expertise_areas`, `render_section_practice_grid` | 4052–4672 | ja |
| Professional-services + agency | `render_section_industries_served`, `render_section_partners_grid`, `render_section_insights_list`, `render_section_selected_work_*`, `render_section_capabilities_row`, `render_section_manifesto_block`, `render_section_process_steps`, `render_section_client_roster` | 4673–5235 | ja |
| Collection-/sidrenderare | `render_services`, `render_treatments`, `render_expertise`, `render_work`, `render_about`, `render_contact`, `render_gallery`, `render_team`, `render_pricing`, `render_portfolio`, `render_map`, `render_products`, `render_faq` | 1475–1943, 1944–2184, 3037–3368 | delvis |
| Dispatch-lim | `_dispatched_page_function_name`, `_collect_dispatched_icons`, `_render_dispatched_route`, `write_pages` | 5236–5551 | ja (tydlig ingång) |

De starkaste sömmarna är de fyra sektionsfamiljerna (restaurang,
behandling/expertis, professional/agency, samt hero-subsystemet). De är redan
registerdrivna och har få interna beroenden utåt.

### 1.2 Beroenden ut och in

**Importerar från** (redan i paketet):
- `packages.generation.build.blueprint_render` (render-blueprint-vyn + applicering på dossier)
- `packages.generation.build.contact_placeholders` (`is_placeholder_*` / `real_*`)
- `packages.generation.build.dispatcher` (`_SECTION_RENDERERS`, `_load_scaffold_sections`, `_operator_pin_for_section`, `_treatment_for_section`, `render_route_generic`)
- `packages.generation.build.static_assets` (`render_robots_txt`, `render_sitemap_xml`, `render_not_found`, m.fl.)

**Cirkulär söm att hantera försiktigt:** modulen når dessutom *tillbaka* in i
`scripts/build_site.py` för delade hjälpare via en lat shim
(`_build_site_module` / `_lazy_attr` / `_call_build_site`). Det betyder att
`scripts/build_site.py` importerar renderarna ivrigt samtidigt som renderarna
lazily anropar byggaren. Den här riktningen är fel mot repo-gränsen (paket ska
inte bero på `scripts/`) och bör krympas av refaktorn, inte växa.

**Importeras av:** `scripts/build_site.py` (ivrig + lat re-export),
`packages/generation/build/dispatcher.py`,
`packages/generation/build/targeted_render.py` (via byggaren),
`packages/generation/followup/section_directives.py`,
`packages/generation/orchestration/apply/apply.py`, samt renderar-testerna.

**Gräns att respektera:** all renderlogik bor i `packages/generation/build/`.
Den får inte importera uppåt från `scripts/`. Slices ska minska den lata
shimmen, inte lägga till i den.

### 1.3 Beteendebevarande slices (minsta först)

Varje slice flyttar en redan sammanhållen grupp till en ny syskonmodul under
`packages/generation/build/` och åter-registrerar sektionsrenderarna i
dispatcher-registret på exakt samma sätt. `renderers.py` fortsätter att
re-exportera de flyttade namnen så att externa stavningar
(`from ... import render_section_*`) fungerar oförändrat tills en senare,
separat upprydning.

| # | Vad flyttas | Vart | Paritetstester |
| --- | --- | --- | --- |
| 1 | restaurang/hospitality-familjen | `packages/generation/build/sections_restaurant.py` | `test_builder_restaurant_routes`, `test_builder_route_emission`, `test_section_renderer_registry` |
| 2 | behandling/credential/expertis/practice-familjen | `packages/generation/build/sections_treatments.py` | `test_section_treatments_resolve`, `test_section_treatments_prompts`, `test_section_treatments_json_parity`, `test_section_renderer_registry` |
| 3 | professional-services + agency-familjen | `packages/generation/build/sections_professional.py` | `test_section_renderer_registry`, `test_builder_route_emission` |
| 4 | hero-subsystemet | `packages/generation/build/hero.py` | `test_renderer_blueprint`, `test_build_media_rendering`, `test_visual_direction_pick` |
| 5 | rena format-/util-hjälpare (sist; rör den lata shimmen) | `packages/generation/build/render_helpers.py` | `test_lucide_react_consistency`, `test_kor1c_copy_render`, hela renderar-sviten |

Slice 5 är medvetet sist eftersom den tvingar fram en konfrontation med den lata
shimmen mot byggaren: målet är att de delade hjälparna får ett enda hem i
paketet i stället för att pendla mellan `scripts/build_site.py` och
`renderers.py`. Den slicen kan behöva delas i ännu mindre steg (en hjälpargrupp
i taget) och kräver att del-2-slicen som flyttar samma hjälpare nedåt
koordineras, så att en symbol inte definieras på två ställen samtidigt.

### 1.4 Testtäckning och luckor

Skyddar beteendet idag:
`test_section_renderer_registry`, `test_renderer_blueprint`,
`test_builder_restaurant_routes`, `test_builder_route_emission`,
`test_section_treatments_resolve`, `test_section_treatments_prompts`,
`test_section_treatments_json_parity`, `test_build_media_rendering`,
`test_lucide_react_consistency`, `test_wizard_route_emission`,
`test_kor1c_copy_render`, `test_visual_direction_pick`.

Luckor att täppa **före** första slicen:
- ett register-fullständighetstest som låser den exakta mängden registrerade
  section-id efter en modulsplit, så att ett bortglömt `.update(...)` fångas
  direkt (i dag verifierar `test_section_renderer_registry` registret men inte
  nödvändigtvis att summan är oförändrad efter en flytt).
- en byte-paritetssele (golden output) för minst en route per scaffold-familj,
  så att rendrings-utdata är låst innan någon grupp flyttas.

### 1.5 Stopp-/grind-regel

Starta `renderers.py`-slices först när den synliga section_add-rendern och
följdprompt-loopen är stabil (produktbevis först). `renderers.py` städas före de
övriga två filerna eftersom dess sömmar är renast.

---

## Del 2 — `scripts/build_site.py`

### 2.1 Ansvarskarta och naturliga sömmar

| Grupp | Representativa symboler | Ungefärligt radspann | Naturlig söm? |
| --- | --- | --- | --- |
| io-/path-/util-hjälpare | `utc_now`, `make_run_id`, `load_json`, `write`, `write_json`, `resolve_generated_dir`, `_to_repo_relative` | 187–372 | ja |
| Prompt-meta-läsare | `load_prompt_input_meta` + hela `_prompt_meta_*`-familjen | 372–630 | ja |
| trace-hjälpklass | trace-klassen (ndjson-spår) | 631–671 | ja |
| Starter-kopiering/cleanup | `copy_starter`, `cleanup_flat_layout`, `_npm_install_inputs_changed`, `_ignore_*` | 672–822 | ja |
| Asset-pipeline | `resolve_media_asset`, `iter_asset_refs`, favicon/og-konvertering, `copy_operator_uploads`, `copy_mood_assets`, `_copy_product_images` | 822–1433 | ja (sammanhållet) |
| Färg-/token-system | `_normalise_hex_color`, `_hex_to_hsl`, `_hsl_to_hex`, `_build_color_scale`, `_token_overrides_from_project_input`, `_typography_*`, `_motion_css_block`, `variant_css`, `patch_globals_css`, `patch_package_json` | 1434–2310 | ja (rent, väl testat) |
| Nav/cta/business-type-hjälpare | `_hero_cta_*`, `_nav_items_from_scaffold`, `_pick_contact_route`, `_pick_listing_route`, `_collect_icons_for_pages` | 2311–2785 | delvis (dubbletter mot renderarna via shimmen) |
| Dossier-val/mount | `selected_required_dossiers`, `resolve_dossier_dir`, `load_selected_dossier_manifests`, `mount_dossier_components`, `write_dossier_routes` | 2785–2908 | ja |
| Route-assertions | `required_routes`, `all_default_routes`, `route_to_page_path`, `assert_routes_present` | 2908–2977 | ja |
| Brief-generering | `build_site_brief_mock`, `build_site_brief`, `project_input_to_brief_prompt`, `_mock_brief_after_llm_failure`, `resolve_brief_model` | 2977–3247 | ja (paketet `brief` finns redan) |
| Intent-guard + plan-artefakter | `_intent_guard_warnings`, `build_plan_artefakts`, `write_phase1_understand`, `write_phase2_plan` | 3248–3502 | delvis |
| Snapshot/diff/synlig-effekt | `snapshot_generated_files`, `_find_previous_*_snapshot`, `_visible_snapshot*`, `_detect_followup_applied_visible_effect` | 3503–3684 | ja |
| Fas-3 tunn wiring | `run_phase3_quality_and_repair` | 3685–3741 | ja (storleksvaktad < 60 rader) |
| Build-result + orkestrering | `write_build_result`, `build` | 3766–4439 | nej — `build` är mycket stor och invariantlåst |
| Version/följdprompt | `_append_targeted_render_event`, `build_targeted_version`, `run_followup_chain`, `_apply_result_mismatch` | 4440–5172 | delvis |
| command-line | `main` | 5173–slut | ja |

### 2.2 Beroenden ut och in

**Importerar från:** `packages.generation.build.{subprocesses, renderers,
static_assets, dispatcher}` samt `packages.generation.codegen`,
`packages.generation.repair` och `produce_site_plan` (planeringslagret), plus
`requests`. Modulen re-exporterar renderar-/dispatcher-/static-asset-namn både
ivrigt och via en lat `__getattr__`-shim.

**Importeras av:** `scripts/dev_generate.py`, eval- och verifierings-skript
(`scripts/run_eval_suite.py`, `scripts/run_golden_path_eval.py`,
`scripts/mini_eval.py`, `scripts/verify_run.py`), `scripts/gc_old_builds.py`,
`scripts/prune_generated_previews.py`,
`packages/generation/maintenance/auto_prune.py`,
`packages/generation/build/targeted_render.py`, samt en stor del av testsviten.

**Gräns att respektera:** produkt-/kontroll-/reparationslogik ska ligga i
`packages/generation/`; `scripts/build_site.py` håller tunn wiring. Detta
hävdas redan av `tests/test_build_site_size.py`.

**Invarianter som varje slice måste hålla gröna** (från
`tests/test_build_site_size.py`):
- ingen inline-implementation av quality-gate- eller repair-funktioner i scripts;
- direkta importer av `packages.generation.codegen` och `packages.generation.repair` kvar;
- `produce_site_plan` förblir enda plan-källan (ingen andra plan-väg, ingen mock-plan);
- `snapshot_generated_files` anropas **efter** `run_phase3_quality_and_repair` i `build`;
- `build` definierar re-render-closuren och skickar in den i fas-3-wiringen;
- `run_phase3_quality_and_repair` förblir tunn (< 60 rader);
- `degraded`-status propageras till overall-status i `build`.

### 2.3 Beteendebevarande slices (minsta/lägst risk först)

| # | Vad flyttas | Vart | Paritetstester |
| --- | --- | --- | --- |
| 1 | färg-/token-systemet (rent, väl testat) | `packages/generation/build/tokens.py` | `test_builder_smoke`, `test_builder_hardening`, `test_b154_next_dev_tdz` |
| 2 | asset-pipelinen (favicon/og-konvertering + uppladdningar) | `packages/generation/build/assets.py` | `test_builder_favicon_ogimage`, `test_operator_uploads`, `test_product_image_pipeline`, `test_mood_isolation`, `test_build_media_rendering` |
| 3 | prompt-meta-läsarfamiljen | `packages/generation/build/prompt_meta.py` | `test_builder_smoke`, `test_followup_versioning_regression` |
| 4 | brief-genereringen | in i `packages/generation/brief/` (finns redan) | `test_builder_brief`, `test_brief_model_resolver` |
| 5 | nav/cta/business-type-hjälparna (delade med renderarna) | `packages/generation/build/render_helpers.py` (samma hem som del 1 slice 5) | `test_builder_route_emission`, `test_contact_route_regression`, hela byggar-sviten |

`build`, `run_phase3_quality_and_repair`, snapshot-kedjan och version/följdprompt-
vägen **flyttas inte ut** ur scripts. De får på sin höjd refaktoreras genom att
extrahera interna closures lokalt — aldrig genom att flytta orkestreringen, som
skulle bryta storleksvaktens `build`/snapshot/re-render-assertions. Slice 5
koordineras med del 1 slice 5 så att en delad hjälpare hamnar på exakt ett ställe.

### 2.4 Testtäckning och luckor

Skyddar beteendet idag:
`test_build_site_size` (invariantlåset), `test_builder_smoke`,
`test_builder_hardening`, `test_builder_favicon_ogimage`,
`test_operator_uploads`, `test_product_image_pipeline`, `test_mood_isolation`,
`test_builder_brief`, `test_brief_model_resolver`, `test_targeted_render`,
`test_followup_chain_cli`, `test_followup_versioning_regression`,
`test_immutable_builds`, `test_quality_gate`, `test_repair_fixes`,
`test_codegen`, `test_artifact_schemas`.

Luckor att täppa **före** slice 1–2:
- ett fokuserat enhetstest som låser färg-/token-utdata (skala + css-block) för
  en representativ projekt-input, så token-modulen kan flyttas med byte-paritet.
- ett enhetstest runt favicon-/og-konverteringen och uppladdnings-kopieringen
  (i dag testas de mest indirekt via byggar-smoke), så asset-modulen kan flyttas
  säkert.

### 2.5 Stopp-/grind-regel

Samma produktbevis-först-regel. Dessutom: varje slice här måste lämna alla
invarianter i `tests/test_build_site_size.py` gröna. `build_site.py` städas efter
`renderers.py`.

---

## Del 3 — `scripts/prompt_to_project_input.py`

### 3.1 Ansvarskarta och naturliga sömmar

| Grupp | Representativa symboler | Ungefärligt radspann | Naturlig söm? |
| --- | --- | --- | --- |
| Site-id-slug + scaffold-val | `slugify_site_id`, `_site_id_text_without_master_prompt_header`, `pick_scaffold` | 692–771 | ja |
| Härlednings-hjälpare (förstabygge) | `_derive_company_name`, `_derive_story`, `_derive_tagline`, `_build_services`, `_placeholder_services`, `_placeholder_contact`, `_placeholder_location` | 772–1468 | ja |
| Brief -> projekt-input | `site_brief_to_project_input` | 1469–1586 | ja (tydlig ingång) |
| Schema-validering + versionering + skrivning | `_validate_against_schema`, `_current_*_path`, `_versioned_*_path`, `_write_immutable_snapshot`, `_atomic_write_text`, `write_project_input` | 1587–1718 | ja |
| Läsare av befintligt tillstånd | `read_existing_meta`, `read_existing_project_input`, `read_base_run_snapshot` | 1719–1870 | ja |
| Följdprompt-intent-klassning | `classify_followup_intent` + hjälpare (`_has_tone_shift_signal`, `_looks_like_raw_followup_prompt`, `_tone_words_from_prompt`, `_avoid_words_from_prompt`) | 1871–2099 | ja |
| Semantisk patch + projekt-dna-snapshot | `_apply_semantic_patch`, `_semantic_source_entry`, `_copy_directive_*`, `_theme_directive_llm_eligible`, `_build_project_dna_snapshot` | 2099–2712 | ja (sammanhållet) |
| Följdprompt-merge | `merge_followup_project_input` | 2713–2915 | ja (tydlig ingång) |
| Capability-map + oapplicerade intents | `_load_capability_map`, `_capability_is_mounted`, `_is_unapplied_hero_rewrite`, `compute_unapplied_followup_intents` | 2916–3055 | ja |
| Discovery-applicering | `_apply_discovery_products`, `_apply_discovery_overrides`, `_load_discovery_file`, `_wizard_must_have_from_discovery` | 3056–3244 | ja |
| generate / generate_followup / command-line | `generate`, `generate_followup`, `main` | 3245–slut | ja |

### 3.2 Beroenden ut och in

**Importerar från:** `packages.generation.brief`, `packages.generation.planning`,
`packages.generation.discovery`, `packages.generation.followup` samt
schema-valideringen.

**Importeras av:** `scripts/dev_generate.py`, `scripts/classify_message.py`,
`scripts/run_openclaw_followup.py`, `scripts/mini_eval.py`,
`scripts/run_golden_path_eval.py`,
`packages/generation/orchestration/apply/apply.py`,
`packages/generation/followup/text.py`, samt prompt-/följdprompt-/discovery-
testerna.

**Gräns att respektera:** härlednings- och merge-logik bör migrera *in i*
`packages/generation/followup/` och `packages/generation/discovery/` (paket som
redan finns), så att `scripts/prompt_to_project_input.py` blir en tunn
command-line- och orkestreringsfil. Den här filen matar följdprompt-loopen och är
därför särskilt känslig — den ska inte röras förrän loopen är bevisad stabil.

### 3.3 Beteendebevarande slices (minsta först)

| # | Vad flyttas | Vart | Paritetstester |
| --- | --- | --- | --- |
| 1 | följdprompt-intent-klassning | in i `packages/generation/followup/` | `test_followup_honest_no_op`, `test_intent_guard`, `test_page_intent` |
| 2 | semantisk patch + projekt-dna-snapshot | in i `packages/generation/followup/` | `test_followup_copy_directives`, `test_followup_theme_directives` |
| 3 | capability-map + oapplicerade intents | in i `packages/generation/followup/` | `test_followup_versioning_regression`, `test_followup_honest_no_op` |
| 4 | discovery-appliceringen | in i `packages/generation/discovery/` | `test_discovery_resolver`, `test_discovery_payload`, `test_discovery_taxonomy` |
| 5 | härlednings-hjälpare (förstabygge) | nytt lager `packages/generation/intake/` | `test_prompt_to_project_input`, `test_contact_placeholder_fallback` |

`generate`, `generate_followup` och `main` förblir den tunna command-line-/
orkestreringsfilen. `merge_followup_project_input` flyttas först när en
byte-paritetssele finns för dess utdata (se luckor).

### 3.4 Testtäckning och luckor

Skyddar beteendet idag:
`test_prompt_to_project_input`, `test_followup_versioning_regression`,
`test_followup_copy_directives`, `test_followup_theme_directives`,
`test_followup_honest_no_op`, `test_followup_chain_cli`,
`test_project_input_schema`, `test_immutable_builds`, `test_discovery_resolver`,
`test_discovery_payload`, `test_discovery_taxonomy`, `test_intent_guard`,
`test_page_intent`, `test_contact_placeholder_fallback`.

Luckor att täppa **före** slices:
- en paritetssele som låser `merge_followup_project_input`-utdata för en
  representativ följdprompt (kopia, tema, section_add) innan logiken byter paket.
- ett enhetstest för `_build_project_dna_snapshot` som låser snapshot-formen, så
  att den semantiska patchen kan flyttas med bevarat beteende.

### 3.5 Stopp-/grind-regel

Samma produktbevis-först-regel, med extra eftertryck: denna fil driver
följdprompt-loopen, så den är sist i kön och rörs inte förrän loopen är
bevisad stabil. `prompt_to_project_input.py` städas sist av de tre.

---

## Sammanfattning

### Konsoliderad ordningsregel

Refaktorn startar inte förrän kärnloopen är produktbevisad och stabil: gating av
projekt-input på disk och **synlig** section_add-render ska vara gröna först.
Refaktor är beteendebevarande hygien och alltid lägre prioriterad än produktbevis.

### Filordning och första steg

1. `packages/generation/build/renderers.py` (renast sömmar) — börja med
   restaurang/hospitality-familjen.
2. `scripts/build_site.py` — börja med färg-/token-systemet.
3. `scripts/prompt_to_project_input.py` — börja med följdprompt-intent-klassning.

### Detta är ett förslag

Lanen föreslår, den utför inte. Ingen slice körs här. Varje framtida slice är sin
egen lilla ändring med namngivna paritetstester, och varje slice ska lämna
`tests/test_build_site_size.py` och de övriga skydds-testerna gröna. Repo-gränsen
(`packages/generation/`-lager; `scripts/` håller tunn wiring) respekteras i varje
steg, och den lata shimmen mellan renderarna och byggaren ska krympas av
refaktorn, inte växa.
