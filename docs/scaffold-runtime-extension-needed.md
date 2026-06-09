---
status: historical
owner: backend
truth_level: historical-reference
last_verified_commit: f56ac30
---

# Scaffold runtime extension — handoff to Jakob

> **Arkivnot (lane A, 2026-06):** Historiskt (kärngapet är stängt, se status nedan).
> Behålls *på plats* eftersom sökvägen är inbäddad i runtime-kommentarer
> (`packages/generation/planning/plan.py`, `packages/generation/build/renderers.py`,
> `tests/test_backoffice_discovery_control.py`) och i en `docs/workboard.json`-relaterad
> sprintvakt-seed. Sanningskälla för nuläget: `docs/current-focus.md`.

**Status:** KLAR / HISTORIK (uppdaterad 2026-06-08). Kärngapet är stängt:
`restaurant-hospitality` är runtime-aktiv (`_RUNTIME_SCAFFOLD_HINTS` i
`packages/generation/discovery/resolve.py`, via Path A per-route-armar) och
Path B section-dispatchern (`render_route_generic` + `_SECTION_RENDERERS` i
`packages/generation/build/dispatcher.py`) finns sedan B146-porten. Dokumentet
behålls som referens för nästa scaffold; det blockerar inget längre.
(Ursprunglig status: Required before week-1 scaffold expansion can run end-to-end.)
**Owner:** Jakob (backend).
**Branch scope:** This document describes work in `scripts/`, `packages/generation/discovery/`, `packages/generation/planning/` and `tests/` — all off-limits for `christopher-*` branches per `governance/rules/branch-scope-ui-ux.md`.

## Sync with main (post PR #63, 2026-05-24)

PR #63 (`f9312ec`) closed gaps 1 (`vibe.useCustomColors`) and 3 (`directives.scaffoldHint` override) from `docs/archive/backend-handoff-2026-05-22.md`. Jakob's commit message already calls out the same runtime gap this document describes:

> Bara runtime-aktiva scaffolds (local-service-business, ecommerce-lite) får override:a. Planned scaffolds (**restaurant-hospitality** m.fl.) ignoreras eftersom build_site.py inte kan rendera dem.

So `restaurant-hospitality` is already wired through the wizard → resolver path; the only thing keeping it from rendering is the three lock-ins below. The existing test `tests/test_discovery_resolver.py::test_scaffold_hint_restaurant_hospitality_planned_ignored` will need to flip from "ignored" to "honored" once the whitelist is extended.

## What we shipped this PR (UI/UX side)

Christopher's PR adds, **declaratively**, the inputs the existing pipeline expects:

| Artefact | Path | Status |
|---|---|---|
| `restaurant-hospitality` scaffold | `packages/generation/orchestration/scaffolds/restaurant-hospitality/` | ✅ All 6 contract files |
| 4 restaurant variants | `…/restaurant-hospitality/variants/{warm-bistro,nordic-fine-dining,casual-cafe,midnight-bar}.json` | ✅ Schema-valid (matches W1-06 4-variant target) |
| `menu-display` dossier | `packages/generation/orchestration/dossiers/soft/menu-display/` | ✅ Manifest + instructions |
| `booking-cta` dossier | `packages/generation/orchestration/dossiers/soft/booking-cta/` | ✅ Manifest + instructions |
| `mailto-contact-form` dossier | `packages/generation/orchestration/dossiers/soft/mailto-contact-form/` | ✅ Manifest + instructions |
| `image-gallery` dossier | `packages/generation/orchestration/dossiers/soft/image-gallery/` | ✅ Manifest + instructions (universal brick-and-mortar block) |
| `opening-hours` dossier | `packages/generation/orchestration/dossiers/soft/opening-hours/` | ✅ Manifest + instructions (with OpeningHoursSpecification JSON-LD) |
| `reviews-display` dossier | `packages/generation/orchestration/dossiers/soft/reviews-display/` | ✅ Manifest + instructions (with Review/AggregateRating JSON-LD) |
| `map-embed` dossier | `packages/generation/orchestration/dossiers/soft/map-embed/` | ✅ Manifest + instructions (OpenStreetMap, no API key) |
| `capability-map.v1.json` | `governance/policies/` | ✅ 7 new capabilities (`menu`, `booking`, `contact-form`, `gallery`, `hours`, `reviews`, `location`) now point to real dossiers |
| `restaurant-hospitality/compatible-dossiers.json` | scaffold dir | ✅ `recommended` expanded to 5 dossiers covering hours/map/gallery/reviews/contact |
| `tooling/scaffold-generator/` | `tooling/scaffold-generator/` | ✅ CLI that generates the same shape declaratively from a spec.yaml — see "Scaling" below |

All four guards (`governance_validate`, `rules_sync --check`, `check_term_coverage --strict`, `ruff`) pass plus 220 pytest-tester.

**Dossier-count: 4 → 8.** Capability-map went from 1 → 7 capabilities with real dossier bindings. All 5 new dossiers are reusable across future scaffolds (portfolio-creator, clinic-healthcare, real-estate, professional-services) without modification — same instructions, different recommended-list per scaffold.

### Batch 3 follow-up (2026-05-24, same day)

After batch 2 we kept building declaratively. Batch 3 adds 3 more universal soft-dossiers and 4 more variants:

| Artefact | Path | Status |
|---|---|---|
| `pricing-table` dossier | `packages/generation/orchestration/dossiers/soft/pricing-table/` | ✅ Manifest + instructions (capability: `pricing`) |
| `faq-accordion` dossier | `packages/generation/orchestration/dossiers/soft/faq-accordion/` | ✅ Manifest + instructions (capability: `faq-section`, closes existing gap) |
| `video-hero` dossier | `packages/generation/orchestration/dossiers/soft/video-hero/` | ✅ Manifest + instructions (capability: `hero-video`) |
| 2 new LSB variants | `…/local-service-business/variants/{sunrise-startup,family-warmth}.json` | ✅ Schema-valid — fills startup-modern + family-friendly vibe gaps |
| 2 new ecommerce-lite variants | `…/ecommerce-lite/variants/{artisan-market,vintage-curio}.json` | ✅ Schema-valid — fills handmade + collector vibe gaps |
| `wizard-constants.ts` VIBE_OPTIONS | `apps/viewser/components/discovery-wizard/wizard-constants.ts` | ✅ 10 → 14 vibes (4 new variants exposed via wizard step 2) |
| `capability-map.v1.json` | `governance/policies/` | ✅ 2 new (`pricing`, `hero-video`) + `faq-section` gap closed |

**Totals after batch 3:** 11 soft dossiers (was 4 before batch 1), 14 variants for runtime-active scaffolds (was 10), 1 gap closed (`faq-section`). The 3 new dossiers are reusable across every existing and future scaffold — pricing-table for any service business with tiered packages, faq-accordion universally, video-hero for media-heavy verticals.

No new backend dependencies introduced by batch 3 — `faq-accordion`, `pricing-table` and `video-hero` use the same `selectedDossiers` pipeline that codegen already plans to consume in Sprint 3+. Wizard step-2 now exposes the 4 new variants automatically via `vibesForScaffold()`.

## What is NOT yet wired (the runtime gap this doc exists for)

Three hardcoded lock-ins in the codegen layer prevented the new scaffold from rendering when this doc was first written. None of them were bugs introduced by this PR — they were existing assumptions baked in when the runtime supported exactly 2 scaffolds.

### Status after PR #68 post-review fixes (2026-05-25)

In response to reviewer feedback on PR #68, two of the three lock-ins below have been closed inside this PR as explicit `[scope-leak]` commits with operator approval:

| Gap | Status | Closed by |
|---|---|---|
| #2 `SCAFFOLD_TO_STARTER` + `_DEFAULT_VARIANT_BY_SCAFFOLD` | resolved | `plan.py` 1+1 entries for `restaurant-hospitality` |
| Wiring touch in `_PAGE_TO_CAPABILITY` + `_CAPABILITY_ALIASES` | resolved | `resolve.py` 3 dict updates + 3 alias entries (`faq`→`faq-section`, `map`→`location`, `testimonials`→`reviews`) |
| #1 `_RUNTIME_SCAFFOLD_HINTS` whitelist | intentionally deferred | not added — see note below |
| #3 `write_pages` route-id dispatch | resolved via Path A (Issue #90) | `scripts/build_site.py` `render_menu` + `render_booking` + two new `elif` arms in `write_pages`. Path B (section-driven generic dispatcher) is still the long-term direction; Path A keeps the surface area small while only one new restaurant-flavoured scaffold needs to build. |

**Why `_RUNTIME_SCAFFOLD_HINTS` is intentionally deferred:** Adding `restaurant-hospitality` to that whitelist would route operator scaffold-hints (and Backoffice discovery target-mappings) at restaurant, but `write_pages` cannot yet render `/meny` or `/bokning` routes. Adding the hint without #3 would convert today's clean planner-side `RuntimeError` into a noisier "first route id has no renderer" `SystemExit` at build time without delivering any user value. The hint should land in the same PR as the section-renderer registry so the wizard, planner and builder all flip green together.

**Why we did close #2 + the wiring touch:** Both are pure dispatch-table additions with no runtime-side dependency on the renderer work. `SCAFFOLD_TO_STARTER` was the actual blocker the reviewer flagged — `restaurant-hospitality` being `enabled: true` in `scaffold-contract.v1.json` while missing from the starter map could crash `produce_site_plan()` if any pinned-scaffold or real-LLM call selected it. Same logic for the `_PAGE_TO_CAPABILITY` mismatch — `faq-section` / `location` / `reviews` were registered in `capability-map.v1.json` but the wizard label → capability lookup still emitted the unregistered legacy slugs, so the dossier-activation path was effectively gated behind a broken map.

### Original gap description

Each lock-in is still documented below for context, even where it has now been closed; the renderer section (#3) is the live work item for Jakob's runtime PR.

### 1. `_RUNTIME_SCAFFOLD_HINTS` whitelist

> Status: intentionally deferred to Jakob runtime PR — see the status table above for rationale.

Currently in `packages/generation/discovery/resolve.py:654`:

```python
_RUNTIME_SCAFFOLD_HINTS: dict[str, tuple[str, str, str]] = {
    "local-service-business": (
        "local-service-business",
        "nordic-trust",
        "marketing-base",
    ),
    "ecommerce-lite": ("ecommerce-lite", "clean-store", "commerce-base"),
}
```

**Action:** Add a `restaurant-hospitality` entry (and accept that this dict will keep growing as week-1/2/3 lands more scaffolds):

```python
"restaurant-hospitality": (
    "restaurant-hospitality",
    "warm-bistro",
    "marketing-base",
),
```

Default variant choice (`warm-bistro`) matches what feels most universally on-brand for an unspecified restaurant brief. Test `tests/test_discovery_resolver.py` will need a new fixture for the scaffold hint.

### 2. `SCAFFOLD_TO_STARTER` map

> Status: resolved in PR #68 post-review commits (2026-05-25) — entry added to both `SCAFFOLD_TO_STARTER` and `_DEFAULT_VARIANT_BY_SCAFFOLD` as `[scope-leak]`.

Currently in `packages/generation/planning/plan.py:64`:

```python
SCAFFOLD_TO_STARTER: dict[str, str] = {
    "local-service-business": "marketing-base",
    "ecommerce-lite": "commerce-base",
}
```

**Action:** Same entry for `restaurant-hospitality`:

```python
"restaurant-hospitality": "marketing-base",
```

Restaurants reuse `marketing-base` (Next.js + Tailwind, same as LSB). No new starter needed in week 1. Test `tests/test_starter_scaffold_mapping.py` will need a new case.

### 3. `write_pages` route-id dispatch (THE BIG ONE)

This is the actual blocker. Currently in `scripts/build_site.py:4614-4645`:

```python
for route in default_routes:
    route_id = route["id"]
    path = route["path"]
    if route_id == "home":
        content = render_home(...)
    elif route_id == "services":
        content = render_services(dossier, contact_path=contact_route["path"])
    elif route_id == "products":
        content = render_products(dossier, contact_path=contact_route["path"])
    elif route_id == "about":
        content = render_about(dossier)
    elif route_id == "contact":
        content = render_contact(dossier)
    else:
        raise SystemExit(
            "Builder failed: scaffold route id "
            f"{route_id!r} has no renderer. Either add a renderer to "
            "write_pages, or remove the route from the "
            "scaffold's routes.json."
        )
```

The restaurant scaffold introduces two new route ids (`menu`, `booking`) and reuses two existing ones (`home`, `about`, `contact`). Without an extension here, `python scripts/build_site.py --dossier examples/<restaurant>.project-input.json` will exit non-zero on the very first non-mapped route.

**We recommend Path B — section-driven generic dispatcher (chosen by Christopher 2026-05-24).**

## The recommended fix: section-driven generic dispatcher (Path B)

Today, `write_pages` is a per-route-id `if/elif` chain. Each new scaffold that introduces a novel route forces a new `elif` branch and a new `render_<route>(dossier)` function. This pattern collapses at scale (10+ scaffolds × ~2 novel routes each = 20+ `elif` arms in one file).

Path B changes the contract: **a route renders the sections declared for it in the scaffold's `sections.json`**. New routes are free; new section *types* are the only thing that requires backend work, and only once per section type — not per scaffold.

### Proposed architecture

#### a. New section-renderer registry

```python
# scripts/build_site.py (new section near existing render_* functions)

# Section ID → callable that returns the JSX fragment for that section,
# given the dossier and a section-config dict from sections.json.
#
# Adding a new scaffold that introduces a never-before-seen section ID
# adds exactly one entry here. Scaffolds that reuse existing section
# IDs pay zero backend cost.
_SECTION_RENDERERS: dict[str, Callable[[dict, dict], str]] = {
    # Universal / cross-scaffold
    "hero": render_section_hero,
    "service-summary": render_section_service_summary,
    "trust-proof": render_section_trust_proof,
    "contact-cta": render_section_contact_cta,
    "contact-info": render_section_contact_info,
    "about-story": render_section_about_story,
    "team": render_section_team,

    # local-service-business
    "services-intro": render_section_services_intro,
    "service-list": render_section_service_list,

    # ecommerce-lite
    "product-grid": render_section_product_grid,
    "product-spotlight": render_section_product_spotlight,

    # restaurant-hospitality (NEW for this PR)
    "menu-preview": render_section_menu_preview,
    "menu-list": render_section_menu_list,
    "menu-grouping": render_section_menu_grouping,
    "dietary-key": render_section_dietary_key,
    "booking-cta": render_section_booking_cta,
    "booking-form-or-embed": render_section_booking_form_or_embed,
    "opening-hours": render_section_opening_hours,
    "atmosphere-gallery": render_section_atmosphere_gallery,
    "address-and-map": render_section_address_and_map,
    "chef-story": render_section_chef_story,
}
```

#### b. Generic per-route renderer

```python
def render_route_generic(
    dossier: dict,
    route: dict,
    scaffold_sections: dict,
) -> str:
    """Render a route by composing its declared sections in order.

    Pulls the section list for this route from sections.json,
    looks up each section's renderer in _SECTION_RENDERERS, and
    concatenates the output in a standard page shell. Replaces
    the per-route-id if/elif chain — and crucially, makes new
    scaffold routes work without touching build_site.py.
    """
    route_id = route["id"]
    section_specs = scaffold_sections.get("routes", {}).get(route_id, {}).get("sections", [])
    if not section_specs:
        raise SystemExit(
            f"Builder failed: scaffold sections.json declares no sections for "
            f"route id {route_id!r}. Add the route to sections.json with at "
            f"least one section spec, or remove it from routes.json."
        )

    body_fragments: list[str] = []
    for spec in section_specs:
        section_id = spec["id"]
        renderer = _SECTION_RENDERERS.get(section_id)
        if renderer is None:
            raise SystemExit(
                f"Builder failed: section id {section_id!r} (used by route "
                f"{route_id!r}) has no renderer in _SECTION_RENDERERS. Add "
                f"one render_section_{section_id.replace('-', '_')} function "
                f"and register it. This is a one-time cost per section type; "
                f"all future scaffolds reusing this section pay zero."
            )
        body_fragments.append(renderer(dossier, spec))

    return _wrap_page_shell(route, body_fragments)
```

#### c. Caller change in `write_pages`

```python
for route in default_routes:
    content = render_route_generic(dossier, route, scaffold_sections)
    write(route_to_page_path(target, route["path"]), content)
```

#### d. Backward compat shim (zero regression risk)

For Sprint-A risk reduction, keep the existing `render_home/services/about/contact/products` functions and have them delegate internally:

```python
def render_home(dossier, dossier_routes, *, listing_route, contact_route, hero_directives_path=None):
    # Existing callers (tests, edge cases) still pass through this entrypoint.
    # Internally it now composes from sections.json's "home" route entry.
    ...
```

This guarantees the 200+ existing snapshot tests (`tests/test_builder_*.py`) keep passing without rewriting.

### Migration order (recommended)

1. Extract existing per-route renderers (`render_home`, `render_services`, `render_about`, `render_contact`, `render_products`) into per-section renderers — `render_section_hero`, `render_section_service_summary`, etc. Use LSB's `sections.json` as the truth-source for which sections each LSB route should compose.
2. Add the `_SECTION_RENDERERS` registry, populated initially with everything extracted.
3. Add `render_route_generic` and wire it into `write_pages`.
4. Keep `render_home` / `render_services` / etc. as thin shims that delegate to `render_route_generic` for the relevant route id — this protects the existing test surface.
5. Add the new restaurant section renderers (`render_section_menu_list`, `render_section_booking_cta`, etc.) — these are the only new work after the refactor.
6. Add entries to `_HERO_STYLE_BY_VARIANT` for the 3 new restaurant variants (`warm-bistro`, `nordic-fine-dining`, `casual-cafe`). The fallback chain (`_HERO_STYLE_BY_TONE` → `"gradient"`) covers gracefully even if you skip this in Sprint A, so it is optional.
7. Activate by adding the two whitelist entries (`_RUNTIME_SCAFFOLD_HINTS`, `SCAFFOLD_TO_STARTER`).

### Effort estimate

| Step | Estimate |
|---|---|
| 1. Extract per-section renderers from existing per-route renderers | 8–12h |
| 2. Add registry + shim | 1h |
| 3. Add `render_route_generic` | 2h |
| 4. Keep backward-compat thin renderers | 1h |
| 5. Add 8 new restaurant section renderers | 4–6h |
| 6. Add 3 variant→hero-style entries | 15min |
| 7. Add whitelist + map entries | 15min |
| 8. New tests (`test_builder_sections_dispatch.py`, restaurant snapshot, resolver fixture) | 4h |
| Aggregated | ~20–26h |

After Path B lands, **each future scaffold costs Jakob ~30 minutes** (two whitelist entries + maybe one or two new section types if the scaffold introduces something genuinely novel). Today every new scaffold costs ~6–8 hours.

## Acceptance gates for the runtime PR

Before merging the runtime extension, please confirm:

- [ ] `python scripts/build_site.py --dossier examples/<lsb>.project-input.json` produces byte-identical output vs main (snapshot diff) — proves the refactor is invisible to existing scaffolds.
- [ ] `python scripts/build_site.py --dossier examples/<restaurant>.project-input.json` exits 0 and produces a `/meny` and `/bokning` page with the declared sections rendered (a new fixture under `examples/` will be needed; happy to write it together).
- [ ] `python -m pytest tests/ -v` is green — no snapshot breakage on LSB or commerce.
- [ ] One new regression test: `tests/test_builder_route_emission.py::test_restaurant_emits_menu_and_booking_routes`.
- [ ] `_HERO_STYLE_BY_VARIANT` either has entries for the 3 new variants OR the fallback chain is exercised in a test that proves the variants render *some* valid hero style.

## Test fixtures we'll need (operator-facing)

- `examples/restaurant-bistro.project-input.json` — a realistic restaurant brief with a menu (3 courses, 9 items), opening hours, phone, address. I can produce this once Path B lands.
- `examples/restaurant-cafe.project-input.json` — same shape but smaller-scope café (no booking, just walk-in + opening hours + lunch menu).

## Small wiring touch in `_PAGE_TO_CAPABILITY` (resolve.py)

> Status: resolved in PR #68 post-review commits (2026-05-25) — both `_PAGE_TO_CAPABILITY` and `_CAPABILITY_ALIASES` updated as `[scope-leak]`. `faq`/`map`/`testimonials` remain as legacy aliases pointing to the new canonical slugs so older briefModel/Project-Input payloads still route correctly.

Week 1 batch 2 added four new capability slugs (`gallery`, `hours`, `reviews`, `location`) with real dossiers. The existing wizard-page-label → capability mapping in `packages/generation/discovery/resolve.py:88` (`_PAGE_TO_CAPABILITY`) already maps `"Bildgalleri" → "gallery"` and `"Meny / Matsedel" → "menu"` — so those wizard pages now auto-route to a real dossier without further changes. Two existing entries were misaligned with the new clean capability names and have now been updated:

| Wizard page label | Currently maps to | Should map to | Reason |
|---|---|---|---|
| `"Kundrecensioner"` | `"testimonials"` (unknown) | `"reviews"` (now registered) | `reviews-display` dossier covers this exact wizard page |
| `"Karta / Hitta hit"` | `"map"` (unknown) | `"location"` (now registered) | `map-embed` dossier covers this exact wizard page |
| `"Vårt team"` | `"team"` (unknown) | `"team"` (still unknown until team-display lands) | Keep as `capability-unknown` warning — no dossier yet |

Alternative: add aliases to `_CAPABILITY_ALIASES` so existing wizard payloads route to the new canonical capability without breaking any URL the wizard team has already shipped. Either approach closes the wizard → resolver → planner wire for these four restaurant-relevant pages.

## What happens if we DON'T do Path B

Path A (per-route hardcoded `elif`) is the minimal alternative. We add `render_menu`, `render_booking`, etc. as new `elif` branches. It works for restaurant, but:

- Every new scaffold in weeks 2/3/4 forces a similar `elif` push.
- By scaffold #6 (real-estate's `/objekt`), `write_pages` is 200+ lines of `elif` and unmaintainable.
- The codegen layer becomes the bottleneck for every UI/UX iteration.

Path B is more upfront work (~20–26h vs ~6h) but resolves the architecture for the whole 10-scaffold expansion in one shot.

## Questions / coordination

I'm happy to:

- Pair on extracting the existing render_* functions into section renderers (I can stage them as no-op refactor PRs you sign off on).
- Generate restaurant + clinic + portfolio test fixtures once you tell me the shape your sections.json expects.
- Adjust the restaurant scaffold's `sections.json` if any section ID I picked conflicts with naming conventions you'd prefer.

Ping me in PR review and we'll iterate.

— Christopher
