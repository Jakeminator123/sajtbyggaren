# Lane C2 — build_site.py beteendebevarande slices (Builder, cloud)

> **Förberedd lane — starta manuellt, EN slice i taget.** Detta är
> *exekveringen* av `docs/refactor/megafiles-plan.md` Del 2. Lane C (planen) tog
> fram kartan; den här lanen flyttar koden i små, beteendebevarande steg.
>
> **Skillnad mot lane A/B/C:** dessa slices är **sekventiella, inte parallella**.
> Varje slice rör `scripts/build_site.py`:s import-/re-export-header, så två
> öppna slices krockar i den filen. Starta slice N+1 först när slice N är mergad
> in i `jakob-be`.

## Ordningsregel (produktbevis först)

Refaktorn får **inte** starta förrän kärnloopen är produktbevisad och stabil:
gating så att en färsk build hittar projekt-input på disk, och **synlig** render
av `section_add`. Se `docs/refactor/megafiles-plan.md` (Ordningsregel) +
`docs/current-focus.md`. Refaktor är beteendebevarande hygien och alltid lägre
prioriterad än produktbevis.

Filordning i planen: `packages/generation/build/renderers.py` städas **före**
`build_site.py`. Kör helst renderers-slice 1 (restaurang-familjen) innan slice 1
nedan. build_site.py-slicerna är ändå rena och väl testade, så de kan tas i
samma grind-pass när produktbeviset är grönt.

---

## Gemensamma regler (klistra in tillsammans med EN slice nedan)

```text
ROLL: Builder-agent i Jakeminator123/sajtbyggaren. Surgical, BETEENDEBEVARANDE
extraktion ur scripts/build_site.py — inga buggfixar, ingen omskrivning av
funktionsbody. Bara filflytt + re-exports. Kopiera ordagrant.

SETUP (Ubuntu cloud-VM, bash; ingen venv-aktivering krävs om setup körts):
  git switch jakob-be && git pull origin jakob-be
  git switch -c <slice-branch>     # exakt namn står i slicen nedan
  python -m pip install -r requirements.txt   # om inte redan gjort

LÄS FÖRST (read-only): AGENTS.md; docs/refactor/megafiles-plan.md (Del 2);
tests/test_build_site_size.py (invarianterna); governance/rules/code-in-english.md.

INVARIANTER som varje slice MÅSTE lämna gröna (tests/test_build_site_size.py):
  - ingen inline quality-gate/repair-logik i scripts/;
  - direkta importer av packages.generation.codegen + packages.generation.repair kvar;
  - produce_site_plan förblir enda plan-källan (ingen mock-plan);
  - i build(): snapshot_generated_files anropas EFTER run_phase3_quality_and_repair;
  - build() definierar _rerender_after_repair och skickar in den i fas-3-wiringen;
  - run_phase3_quality_and_repair förblir tunn (< 60 rader);
  - degraded-status propageras till overall-status i build().
  => Rör därför ALDRIG build(), main(), run_phase3_quality_and_repair,
     snapshot-kedjan eller version/följdprompt-vägen i denna lane.

RE-EXPORT + SHIM-REGEL (kritisk): scripts/build_site.py bevarar ytan
"from scripts.build_site import X" via ivriga re-exports + en __getattr__-shim.
renderarna i packages/generation/build/renderers.py når dessutom TILLBAKA in i
build_site via en lat shim (_call_build_site / _build_site_module). Så när du
flyttar en symbol som renderarna eller testerna använder MÅSTE du lägga kvar en
re-export i build_site.py, annars resolvar getattr(build_site, "<symbol>") inte
längre och renderarna/testerna bryts. Lägg re-exporten överst, direkt efter de
befintliga build-paket-importerna. Lokalisera via SYMBOLNAMN, aldrig radnummer.

CIRKULÄR IMPORT: om den flyttade koden anropar tillbaka in i build_site, bryt
cykeln genom att (a) flytta även hjälparen, (b) lat import i funktionsbody, eller
(c) öppna draft-PR och fråga operatören. Hellre stannad branch än korrupt merge.

GRÖNT FÖRE PUSH (kopiera siffrorna i rapporten):
  python -m ruff check .                          # 0 findings
  python -m pytest tests/ -q                       # grön (samma pass/skip som baseline)
  python scripts/governance_validate.py
  python scripts/rules_sync.py --check
  python scripts/check_term_coverage.py --strict
  python scripts/build_site.py --dossier examples/painter-palma.project-input.json --skip-build
    # verifiera artefakt-paritet: diff:a data/runs/<runId>/generated-files/ före/efter flytten

LEVERANS: push den tillfälliga branchen, MERGA INTE själv. Operatören mergar in
i jakob-be (direkt eller via PR för review-bonus). Öppna ingen PR mot main.
Lista ALLA ändrade filer i rapporten (olistade filer = scope-läckage).

RAPPORT (exakt format):
  Branch pushad: <slice-branch> (redo för merge in i jakob-be).
  Flyttat: <symboler> -> <målmodul>. build_site.py: <före> -> <efter> rader.
  Re-exports kvar: <lista>. Guards gröna: ruff 0, pytest <pass>/<skip>,
  governance 19/19, rules_sync OK, term-coverage --strict OK. Artefakt-paritet
  för painter-palma bekräftad. Ändrade filer: <lista>.

MODELL: Composer 2.5 eller GPT-5-codex (mekaniskt, deterministisk noggrannhet).
```

---

## Slice 1 — färg-/token-systemet -> `build/tokens.py`

```text
<slice-branch>: cursor/buildsite-slice1-tokens

MÅL: flytta färg-/token-systemet till packages/generation/build/tokens.py.
SYMBOLER (lokalisera via namn): _HEX_COLOR_RE, _TONE_COLOR_TOKENS,
  _normalise_hex_color, _foreground_for_background, _hex_to_hsl, _hsl_to_hex,
  _build_color_scale, _token_overrides_from_project_input, _typography_for_variant,
  _normalize_tone_key, _typography_overlay_for_tone, _motion_css_block,
  variant_css, patch_globals_css, patch_package_json.
RE-EXPORT KVAR (shim + tester): variant_css, patch_globals_css, patch_package_json,
  _build_color_scale, _token_overrides_from_project_input (+ övriga flyttade
  publika namn som build() eller tester refererar).
LUCKA ATT TÄPPA FÖRE FLYTT: litet enhetstest som låser färg-/token-utdata
  (color-scale + css-block) för en representativ project-input -> byte-paritet.
PARITETSTESTER: test_builder_smoke, test_builder_hardening, test_b154_next_dev_tdz.
PR-titel: refactor(builder): extract color/token system to build/tokens.py
```

## Slice 2 — asset-pipelinen -> `build/assets.py`

```text
<slice-branch>: cursor/buildsite-slice2-assets

MÅL: flytta asset-/media-pipelinen till packages/generation/build/assets.py.
SYMBOLER: _is_valid_asset_ref, resolve_media_asset, iter_asset_refs,
  _iter_public_upload_refs, _iter_mood_refs, _is_allowed_asset_source_url,
  _fetch_asset_bytes_from_url, _asset_requires_derived_public_output,
  _is_svg_favicon, _convert_favicon_to_ico, _convert_og_image_to_1200x630_png,
  _write_derived_media_asset, _operator_asset_candidate_dirs,
  _operator_asset_variant_candidates, _resolve_operator_asset_source,
  _private_mood_asset_extension, _private_mood_asset_stem,
  _public_product_asset_extension, _public_product_asset_stem,
  _copy_product_images, copy_operator_uploads, copy_mood_assets.
OBS: _fetch_asset_bytes_from_url använder requests -> assets.py importerar requests.
RE-EXPORT KVAR: resolve_media_asset, iter_asset_refs, copy_operator_uploads,
  copy_mood_assets (build() + tester använder dem).
LUCKA ATT TÄPPA FÖRE FLYTT: enhetstest runt favicon-/og-konvertering +
  uppladdnings-kopiering (testas idag mest indirekt via byggar-smoke).
PARITETSTESTER: test_builder_favicon_ogimage, test_operator_uploads,
  test_product_image_pipeline, test_mood_isolation, test_build_media_rendering.
PR-titel: refactor(builder): extract asset pipeline to build/assets.py
```

## Slice 3 — prompt-meta-läsarna -> `build/prompt_meta.py`

```text
<slice-branch>: cursor/buildsite-slice3-prompt-meta

MÅL: flytta prompt-meta-läsarfamiljen till packages/generation/build/prompt_meta.py.
SYMBOLER: load_prompt_input_meta, _prompt_meta_path_for_dossier, _prompt_meta_mode,
  _prompt_meta_project_id, _prompt_meta_version, _prompt_meta_previous_version,
  _prompt_meta_raw_prompt, _prompt_meta_placeholder_contact_fields,
  _prompt_meta_followup_intent_id, _prompt_meta_wizard_must_have,
  _persist_init_project_input_sidecar, _has_copy_directives,
  _placeholder_contact_warning_message.
  (_prompt_meta_unapplied_followup_intents får följa med om den blir cirkelfri;
   annars lämna kvar och importera den lata vägen.)
RE-EXPORT KVAR: load_prompt_input_meta, _has_copy_directives, alla _prompt_meta_*
  som build()/build_targeted_version/tester refererar.
PARITETSTESTER: test_builder_smoke, test_followup_versioning_regression.
PR-titel: refactor(builder): extract prompt-meta readers to build/prompt_meta.py
```

## Slice 4 — brief-genereringen -> `packages/generation/brief/`

```text
<slice-branch>: cursor/buildsite-slice4-brief

MÅL: flytta brief-genereringen in i det befintliga paketet
  packages/generation/brief/ (ny modul, t.ex. site_brief.py bredvid models.py +
  extract.py).
SYMBOLER: build_site_brief, build_site_brief_mock, resolve_brief_model,
  project_input_to_brief_prompt, _mock_brief_after_llm_failure,
  _mood_visual_note_blocks, _apply_operator_directive_note.
  (_intent_guard_warnings stannar — den hör till plan-/intent-gruppen, inte brief.)
RE-EXPORT KVAR: build_site_brief, build_site_brief_mock, resolve_brief_model,
  project_input_to_brief_prompt (tester + build() använder dem).
PARITETSTESTER: test_builder_brief, test_brief_model_resolver.
PR-titel: refactor(builder): move brief generation into packages/generation/brief
```

## Slice 5 — nav/cta/business-type-hjälparna -> `build/render_helpers.py`

```text
<slice-branch>: cursor/buildsite-slice5-render-helpers

OBS: kör SIST och koordinera med renderers-slice 5 (samma målmodul) så att en
  delad symbol inte definieras på två ställen. Detta är slicen som krymper den
  lata shimmen mellan renderarna och byggaren — målet är ETT hem i paketet.
MÅL: flytta de delade nav/cta/business-type-hjälparna till
  packages/generation/build/render_helpers.py.
SYMBOLER: _icon_for_service, _phone_href, _normalize_business_type,
  _hero_cta_variant, _hero_cta_label, _commerce_bottom_cta_label,
  _hero_cta_target_path, _location_is_country_only, _nav_label_for_route,
  _nav_items_from_scaffold, _pick_contact_route, _pick_listing_route,
  _collect_icons_for_pages.
FÖRBJUDET: konsolidera ALDRIG _normalize_business_type med
  prompt_to_project_input.py — det är B110 och kräver egen ADR.
RE-EXPORT KVAR: _nav_items_from_scaffold, _pick_contact_route, _pick_listing_route
  + alla som renderarna når via shimmen.
PARITETSTESTER: test_builder_route_emission, test_contact_route_regression,
  hela byggar-sviten.
PR-titel: refactor(builder): extract shared render helpers to build/render_helpers.py
```

---

## Efter alla fem slices

`scripts/build_site.py` ska vara kvar som tunn cli + orkestrering: import-/
re-export-header, konstanter, `build()`, `build_targeted_version()`,
`run_followup_chain()`, den tunna `run_phase3_quality_and_repair()` och `main()`.
All produktlogik bor då i `packages/generation/`. Verifiera mot
`tests/test_build_site_size.py` att invarianterna fortfarande håller, och uppdatera
`docs/refactor/megafiles-plan.md` (bocka av Del 2-slicerna) i en separat docs-commit.
