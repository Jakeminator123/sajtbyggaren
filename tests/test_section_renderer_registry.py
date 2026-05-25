"""Path B step 6 — section-renderer registry + dispatcher tests.

These tests lock the contract for ``_SECTION_RENDERERS`` and
``render_route_generic`` so a future refactor cannot quietly break the
section-driven dispatcher Path B is built on.

Specifically they verify:

- The registry contains every section id the LSB ``sections.json``
  declares for its routes (so an LSB scaffold using the dispatcher
  cannot raise ``SystemExit`` for a missing renderer).
- Each registered renderer accepts ``dossier`` plus a kwarg-only
  signature compatible with the dispatcher's call convention.
- ``render_route_generic`` composes required sections in declaration
  order, then optional sections, and routes per-renderer kwargs only
  to the renderers that accept them.
- Unknown section ids and unknown route ids raise descriptive
  ``SystemExit`` errors so a typo in a scaffold's sections.json
  surfaces early instead of producing an empty page.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.build_site as bs  # noqa: E402 - sys.path tweak above


def _read_lsb_sections() -> dict:
    sections_path = (
        REPO_ROOT
        / "packages"
        / "generation"
        / "orchestration"
        / "scaffolds"
        / "local-service-business"
        / "sections.json"
    )
    return json.loads(sections_path.read_text(encoding="utf-8"))


def test_section_registry_contains_lsb_extracted_sections() -> None:
    """The registry must expose every section extracted in steps 1-5.

    Commits 1-5 of Path B extracted hero, service-summary,
    service-list, trust-proof, about-story, team, contact-cta,
    contact-info, products-intro and product-grid into reusable
    section renderers. This test locks them so a future refactor
    cannot quietly drop one.
    """
    expected = {
        "hero",
        "service-summary",
        "service-list",
        "trust-proof",
        "about-story",
        "team",
        "contact-cta",
        "contact-info",
        "products-intro",
        "product-grid",
    }
    missing = sorted(expected - bs._SECTION_RENDERERS.keys())
    assert missing == [], (
        "_SECTION_RENDERERS must register every section extracted in "
        "Path B steps 1-5. Missing: " + ", ".join(missing)
    )


def test_section_registry_aliases_services_summary() -> None:
    """``services-summary`` and ``service-summary`` resolve identically.

    LSB's sections.json uses the singular ``service-summary`` id; older
    callsites and audit reports referred to it as ``services-summary``.
    Both must dispatch to the same renderer so a stylistic disagreement
    in scaffold authoring does not surface as a missing-section
    SystemExit.
    """
    assert (
        bs._SECTION_RENDERERS["service-summary"]
        is bs._SECTION_RENDERERS["services-summary"]
    )


def test_lsb_sections_json_referenced_sections_are_known() -> None:
    """LSB sections.json must not reference an unregistered section.

    Sections that have not yet been extracted into their own renderer
    are tracked here so a future refactor either extracts them (and
    removes the entry) or registers an alias.
    """
    lsb_sections = _read_lsb_sections()
    referenced: set[str] = set()
    for route_block in lsb_sections.values():
        if not isinstance(route_block, dict):
            continue
        for key in ("requiredSections", "optionalSections"):
            value = route_block.get(key)
            if isinstance(value, list):
                referenced.update(str(item) for item in value if isinstance(item, str))

    not_yet_extracted = {
        "services-intro",
        "service-area",
        "reviews",
        "certifications",
    }
    candidates = referenced - not_yet_extracted

    missing = sorted(candidates - bs._SECTION_RENDERERS.keys())
    assert missing == [], (
        "Either register a renderer for these LSB sections or add them "
        "to the not-yet-extracted allowlist: " + ", ".join(missing)
    )


def test_lsb_sections_json_declares_home_optional_extensions() -> None:
    """LSB home must list story, gallery, testimonials and faq as optionals.

    Path B step 10 extended LSB's sections.json so a future caller
    swap (write_pages → render_route_generic) can pick the four
    home-page extras up from the scaffold contract instead of from
    the inline calls in render_home. Locking the entries prevents a
    future scaffold edit from quietly dropping one of them.
    """
    lsb_sections = _read_lsb_sections()
    home_optional = lsb_sections["home"].get("optionalSections", [])
    expected = {"story", "gallery", "testimonials", "faq"}
    missing = sorted(expected - set(home_optional))
    assert missing == [], (
        "LSB home.optionalSections must declare story, gallery, "
        "testimonials and faq so render_route_generic can compose "
        "the home page from the scaffold contract. Missing: "
        + ", ".join(missing)
    )


def test_section_registry_renderers_accept_dossier_first() -> None:
    """Every registered renderer must accept dossier as first positional.

    The dispatcher passes ``dossier`` positionally and kwargs by name;
    a renderer that took something else first would crash at runtime.
    """
    for section_id, renderer in bs._SECTION_RENDERERS.items():
        sig = inspect.signature(renderer)
        params = list(sig.parameters.values())
        assert params, (
            f"Section renderer for {section_id!r} must accept at least "
            "the dossier positional parameter."
        )
        first = params[0]
        assert first.name == "dossier", (
            f"Section renderer for {section_id!r} must take dossier as "
            f"its first parameter (got {first.name!r})."
        )


def test_render_route_generic_composes_required_then_optional() -> None:
    """Required sections render in order, then optional sections."""
    captured: list[str] = []

    def _stub(_id: str):
        def _renderer(dossier: dict) -> str:  # noqa: ARG001 - dossier ignored
            captured.append(_id)
            return f"<!--{_id}-->"
        return _renderer

    saved = dict(bs._SECTION_RENDERERS)
    bs._section_renderer_kwargs.cache_clear()
    try:
        bs._SECTION_RENDERERS.clear()
        bs._SECTION_RENDERERS.update(
            {
                "alpha": _stub("alpha"),
                "beta": _stub("beta"),
                "gamma": _stub("gamma"),
            }
        )
        body = bs.render_route_generic(
            {},
            route_id="home",
            scaffold_sections={
                "home": {
                    "requiredSections": ["alpha", "beta"],
                    "optionalSections": ["gamma"],
                }
            },
        )
    finally:
        bs._SECTION_RENDERERS.clear()
        bs._SECTION_RENDERERS.update(saved)
        bs._section_renderer_kwargs.cache_clear()

    assert captured == ["alpha", "beta", "gamma"]
    assert body == "<!--alpha--><!--beta--><!--gamma-->"


def test_render_route_generic_passes_only_accepted_kwargs() -> None:
    """A renderer must receive only the kwargs its signature accepts."""
    seen_kwargs: dict[str, dict] = {}

    def _renderer_a(dossier: dict, *, contact_path: str) -> str:  # noqa: ARG001
        seen_kwargs["a"] = {"contact_path": contact_path}
        return "A"

    def _renderer_b(dossier: dict) -> str:  # noqa: ARG001
        seen_kwargs["b"] = {}
        return "B"

    saved = dict(bs._SECTION_RENDERERS)
    bs._section_renderer_kwargs.cache_clear()
    try:
        bs._SECTION_RENDERERS.clear()
        bs._SECTION_RENDERERS.update({"a": _renderer_a, "b": _renderer_b})
        body = bs.render_route_generic(
            {},
            route_id="home",
            scaffold_sections={
                "home": {"requiredSections": ["a", "b"]}
            },
            contact_path="/kontakt",
            unrelated_kwarg="should-be-dropped",
        )
    finally:
        bs._SECTION_RENDERERS.clear()
        bs._SECTION_RENDERERS.update(saved)
        bs._section_renderer_kwargs.cache_clear()

    assert body == "AB"
    assert seen_kwargs == {"a": {"contact_path": "/kontakt"}, "b": {}}


def test_render_route_generic_rejects_unknown_section_id() -> None:
    """Typos in sections.json must raise a descriptive SystemExit."""
    with pytest.raises(SystemExit) as exc_info:
        bs.render_route_generic(
            {},
            route_id="home",
            scaffold_sections={
                "home": {"requiredSections": ["does-not-exist"]}
            },
        )
    message = str(exc_info.value)
    assert "does-not-exist" in message
    assert "render_section_does_not_exist" in message


def test_render_route_generic_returns_empty_for_unknown_route() -> None:
    """Unknown route id returns empty body so callers can fall back."""
    body = bs.render_route_generic(
        {},
        route_id="does-not-exist",
        scaffold_sections={"home": {"requiredSections": ["hero"]}},
    )
    assert body == ""


def test_load_scaffold_sections_caches_per_directory() -> None:
    """Repeated calls for the same scaffold dir hit the cache."""
    scaffold_dir = (
        REPO_ROOT
        / "packages"
        / "generation"
        / "orchestration"
        / "scaffolds"
        / "local-service-business"
    )
    bs._SCAFFOLD_SECTIONS_CACHE.pop(scaffold_dir, None)
    first = bs._load_scaffold_sections(scaffold_dir)
    second = bs._load_scaffold_sections(scaffold_dir)
    assert first is second
    assert "home" in first


def test_load_scaffold_sections_returns_empty_for_missing_file(
    tmp_path: Path,
) -> None:
    """A scaffold without sections.json yields an empty dict."""
    bs._SCAFFOLD_SECTIONS_CACHE.pop(tmp_path, None)
    result = bs._load_scaffold_sections(tmp_path)
    assert result == {}


# ---------------------------------------------------------------------------
# Path B step 7 — restaurant-hospitality section renderers.
# ---------------------------------------------------------------------------


def _read_restaurant_sections() -> dict:
    sections_path = (
        REPO_ROOT
        / "packages"
        / "generation"
        / "orchestration"
        / "scaffolds"
        / "restaurant-hospitality"
        / "sections.json"
    )
    return json.loads(sections_path.read_text(encoding="utf-8"))


def test_section_registry_covers_restaurant_menu_route() -> None:
    """Every required + optional section on /menu has a renderer."""
    restaurant_sections = _read_restaurant_sections()
    menu_block = restaurant_sections["menu"]
    referenced = set(menu_block.get("requiredSections", []))
    referenced.update(menu_block.get("optionalSections", []))

    optional_not_yet_extracted = {"wine-pairings", "menu-download-cta", "lunch-rotation-note"}
    candidates = referenced - optional_not_yet_extracted

    missing = sorted(candidates - bs._SECTION_RENDERERS.keys())
    assert missing == [], (
        "_SECTION_RENDERERS must cover restaurant /menu sections that "
        "are not on the not-yet-extracted allowlist. Missing: "
        + ", ".join(missing)
    )


def test_section_registry_covers_restaurant_booking_route() -> None:
    """Every required + optional section on /booking has a renderer."""
    restaurant_sections = _read_restaurant_sections()
    booking_block = restaurant_sections["booking"]
    referenced = set(booking_block.get("requiredSections", []))
    referenced.update(booking_block.get("optionalSections", []))

    missing = sorted(referenced - bs._SECTION_RENDERERS.keys())
    assert missing == [], (
        "_SECTION_RENDERERS must cover every section on the restaurant "
        "/booking route. Missing: " + ", ".join(missing)
    )


def test_render_route_generic_emits_restaurant_menu_route() -> None:
    """Composing /menu via dispatcher produces non-empty JSX with intro + list."""
    body = bs.render_route_generic(
        {"services": [{"id": "house-wine", "label": "Husets vin", "summary": "30 cl glas."}]},
        route_id="menu",
        scaffold_sections={
            "menu": {
                "requiredSections": ["menu-intro", "menu-list", "dietary-key"],
                "optionalSections": [],
            }
        },
    )
    assert "Vad vi serverar just nu" in body
    assert "Husets vin" in body
    assert "Kostmarkeringar" in body


def test_render_route_generic_emits_restaurant_booking_route() -> None:
    """Composing /booking via dispatcher includes intro + phone fallback."""
    body = bs.render_route_generic(
        {"contact": {"phone": "08-123 45 67", "email": "boka@example.se", "openingHours": "Tis-Sön 17-22"}},
        route_id="booking",
        scaffold_sections={
            "booking": {
                "requiredSections": [
                    "booking-intro",
                    "booking-form-or-embed",
                    "hours-summary",
                    "fallback-phone",
                ],
                "optionalSections": [],
            }
        },
    )
    assert "Boka en plats hos oss" in body
    assert "08-123 45 67" in body
    assert "boka@example.se" in body
    assert "Tis-Sön 17-22" in body


def test_hours_summary_returns_empty_when_no_dossier_hours() -> None:
    """Section is skipped silently when the operator has not set hours."""
    assert bs.render_section_hours_summary({"contact": {}}) == ""
    assert bs.render_section_hours_summary({}) == ""


def test_fallback_phone_returns_empty_without_phone_or_email() -> None:
    """Section is skipped silently when neither channel is configured."""
    assert bs.render_section_fallback_phone({"contact": {}}) == ""
    assert bs.render_section_fallback_phone({}) == ""


# ---------------------------------------------------------------------------
# Section design-treatments — Phase 1 pilot (sprint 2026-05-25).
#
# The first treatment-aware section is selected-work-preview on
# agency-studio /home. The dispatcher must:
#
# - resolve to ``editorial-stack`` (default) for any unknown variant
#   so future variants always have a defined visual state,
# - resolve to ``asymmetric-grid`` for ``studio-monochrome`` so the
#   variant→treatment map in build_site stays the single source of
#   truth,
# - keep ``editorial-stack`` byte-identical to the pre-pilot output
#   so existing snapshots and other agency-studio variants are not
#   silently changed by introducing the dispatch layer.
# ---------------------------------------------------------------------------


_AGENCY_STUDIO_FIXTURE_DOSSIER: dict = {
    "services": [
        {"id": "case-1", "label": "Case 1", "summary": "Summary 1."},
        {"id": "case-2", "label": "Case 2", "summary": "Summary 2."},
        {"id": "case-3", "label": "Case 3", "summary": "Summary 3."},
        {"id": "case-4", "label": "Case 4", "summary": "Summary 4."},
        {"id": "case-5", "label": "Case 5", "summary": "Summary 5."},
    ]
}


def test_treatment_for_section_returns_default_when_variant_id_missing() -> None:
    """No variant -> default treatment.

    A renderer that opts into treatment dispatch must always have a
    safe fallback when called outside of a Path B native scaffold or
    before the dispatcher has resolved a variant id.
    """
    assert (
        bs._treatment_for_section(
            None,
            "selected-work-preview",
            default="editorial-stack",
        )
        == "editorial-stack"
    )


def test_treatment_for_section_returns_default_for_unknown_variant() -> None:
    """Unknown variant -> default treatment.

    Future variants should not have to register every section in the
    treatment map up front; an unmapped variant simply inherits the
    section's default until an operator or LLM-pick overrides it.
    """
    assert (
        bs._treatment_for_section(
            "experimental-variant-not-yet-registered",
            "selected-work-preview",
            default="editorial-stack",
        )
        == "editorial-stack"
    )


def test_treatment_for_section_returns_default_for_unmapped_section() -> None:
    """Variant that registers other sections -> default for this one.

    A variant might register a treatment for one section but not for
    another; the helper must return the requested section's default
    rather than leaking the wrong treatment id.
    """
    assert (
        bs._treatment_for_section(
            "studio-monochrome",
            "section-not-in-map",
            default="some-default",
        )
        == "some-default"
    )


def test_treatment_for_section_resolves_studio_monochrome_pilot_pin() -> None:
    """Pilot mapping: studio-monochrome -> asymmetric-grid for selected-work-preview."""
    assert (
        bs._treatment_for_section(
            "studio-monochrome",
            "selected-work-preview",
            default="editorial-stack",
        )
        == "asymmetric-grid"
    )


def test_selected_work_preview_default_treatment_is_editorial_stack() -> None:
    """No variant -> editorial-stack output (the pre-pilot baseline).

    Locks the byte-identical guarantee: introducing treatment
    dispatch must not change the output for variants that inherit
    the default treatment. The presence of "Case 01" + the absence
    of the asymmetric-grid surface tokens (translate-y / card surface)
    are how we recognize the editorial-stack treatment.
    """
    body = bs.render_section_selected_work_preview(_AGENCY_STUDIO_FIXTURE_DOSSIER)
    assert "Case 01" in body
    assert "Studio nº" not in body
    assert "md:translate-y-12" not in body
    assert "bg-[color:var(--card)]" not in body


def test_selected_work_preview_editorial_warm_keeps_default_treatment() -> None:
    """editorial-warm inherits editorial-stack (the section default).

    Phase 1 swapped only studio-monochrome to asymmetric-grid; Phase 2
    swaps bold-electric to marquee-row. editorial-warm remains on
    editorial-stack so the warm agency keeps reading as a calm
    magazine spread rather than competing with the other two agency
    variants. The byte-identical guarantee against pre-pilot snapshots
    is preserved for this variant specifically.
    """
    body = bs.render_section_selected_work_preview(
        _AGENCY_STUDIO_FIXTURE_DOSSIER,
        variant_id="editorial-warm",
    )
    assert "Case 01" in body
    assert "Studio nº" not in body
    assert "Studio reel" not in body
    assert "md:translate-y-12" not in body
    assert "snap-x snap-mandatory" not in body


def test_selected_work_preview_studio_monochrome_uses_asymmetric_grid() -> None:
    """studio-monochrome -> asymmetric-grid output.

    The pilot demo case: same fixture, different variant id, visibly
    different DOM. The asymmetric-grid markers we lock are:

    - "Studio nº NN" eyebrow (vs the editorial-stack "Case NN"),
    - per-card card surface (``bg-[color:var(--card)]``) with
      ``rounded-[var(--radius-lg)]`` + generous padding,
    - ``md:translate-y-12`` on every other card so the grid breaks
      its own baseline.
    """
    body = bs.render_section_selected_work_preview(
        _AGENCY_STUDIO_FIXTURE_DOSSIER,
        variant_id="studio-monochrome",
    )
    assert "Studio nº 01" in body
    assert "Studio nº 02" in body
    assert "Case 01" not in body
    assert "Studio reel" not in body
    assert "bg-[color:var(--card)]" in body
    assert "rounded-[var(--radius-lg)]" in body
    assert "md:translate-y-12" in body


def test_selected_work_preview_bold_electric_uses_marquee_row() -> None:
    """bold-electric -> marquee-row output (Phase 2).

    Phase 2 expansion: bold-electric flips from the editorial-stack
    default it inherited in Phase 1 to a horizontal scroll-snap
    rail. The markers we lock are:

    - "Studio reel · NN" eyebrow (distinct from editorial's "Case NN"
      and asymmetric-grid's "Studio nº NN"),
    - ``snap-x snap-mandatory`` on the rail so cards snap into
      view instead of free-scrolling,
    - rendered card count is 6 (vs 4 in the other treatments),
      verified by checking that "Studio reel · 06" is present and
      "Studio reel · 07" is not. The fixture has 5 services so
      the slice ``services[:6]`` produces exactly 5 cards in
      practice; this test still locks the 6-card cap so a future
      treatment edit does not silently change the rail length.
    """
    body = bs.render_section_selected_work_preview(
        _AGENCY_STUDIO_FIXTURE_DOSSIER,
        variant_id="bold-electric",
    )
    assert "Studio reel" in body
    assert "Studio reel · 01" in body
    assert "snap-x snap-mandatory" in body
    assert "overflow-x-auto" in body
    assert "Case 01" not in body
    assert "md:translate-y-12" not in body


def test_selected_work_preview_marquee_caps_at_six_cards() -> None:
    """marquee-row treatment caps at 6 cards regardless of fixture size.

    Locks the contract that the rail keeps a sensible upper bound so
    a dossier with 20 case studies does not produce an unwieldy
    rail. The 5-service fixture exercises the under-cap path; a
    7-service synthetic dossier exercises the cap.
    """
    seven_services = {
        "services": [
            {"id": f"case-{i}", "label": f"Case {i}", "summary": f"Summary {i}."}
            for i in range(1, 8)
        ]
    }
    body = bs.render_section_selected_work_preview(
        seven_services,
        variant_id="bold-electric",
    )
    assert "Studio reel · 06" in body
    assert "Studio reel · 07" not in body


# ---------------------------------------------------------------------------
# treatment-list (clinic-healthcare) — Phase 2
#
# Three treatments mapped 1:1 against clinic variants:
#   clinic-calm        -> minimal-rows  (default, byte-identical)
#   warm-care          -> split-cards   (2-col, accent-tinted rail)
#   modern-precision   -> numbered-stack (mono numerals, thin separators)
# ---------------------------------------------------------------------------


_CLINIC_FIXTURE_DOSSIER: dict = {
    "services": [
        {"id": "tx-1", "label": "Behandling 1", "summary": "Beskrivning 1."},
        {"id": "tx-2", "label": "Behandling 2", "summary": "Beskrivning 2."},
        {"id": "tx-3", "label": "Behandling 3", "summary": "Beskrivning 3."},
    ]
}


def test_treatment_list_default_is_minimal_rows() -> None:
    """No variant -> minimal-rows (byte-identical pre-Phase-2 default).

    Locks the contract that introducing treatment dispatch on
    treatment-list does not change the output for callers that do
    not pin a variant. The presence of the rounded-2xl border-card
    rail and the absence of split-cards / numbered-stack markers is
    how we recognize the minimal-rows treatment.
    """
    body = bs.render_section_treatment_list(_CLINIC_FIXTURE_DOSSIER)
    assert (
        "rounded-2xl border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-8"
    ) in body
    assert "border-l-[color:var(--accent)]" not in body
    assert "font-mono text-3xl tracking-tight" not in body


def test_treatment_list_clinic_calm_keeps_default_treatment() -> None:
    """clinic-calm inherits the section default minimal-rows.

    Phase 2 deliberately does NOT register clinic-calm in
    _SECTION_TREATMENTS_BY_VARIANT so the calm clinic keeps the
    pre-Phase-2 menu feel. This test catches a future map edit that
    would silently flip the calm clinic to a different treatment.
    """
    body = bs.render_section_treatment_list(
        _CLINIC_FIXTURE_DOSSIER,
        variant_id="clinic-calm",
    )
    assert (
        "rounded-2xl border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-8"
    ) in body
    assert "border-l-[color:var(--accent)]" not in body
    assert "font-mono text-3xl tracking-tight" not in body


def test_treatment_list_warm_care_uses_split_cards() -> None:
    """warm-care -> split-cards.

    The split-cards markers we lock are:
    - ``md:grid-cols-2`` 2-col layout for the list,
    - the accent-tinted left rail (``border-l-[color:var(--accent)]``)
      that is unique to the split-cards treatment,
    - the warmer ``bg-[color:var(--card)]`` card surface vs the flat
      ``--background`` panel used by minimal-rows.
    """
    body = bs.render_section_treatment_list(
        _CLINIC_FIXTURE_DOSSIER,
        variant_id="warm-care",
    )
    assert "md:grid-cols-2" in body
    assert "border-l-[color:var(--accent)]" in body
    assert "bg-[color:var(--card)]" in body
    assert "font-mono text-3xl tracking-tight" not in body


def test_treatment_list_modern_precision_uses_numbered_stack() -> None:
    """modern-precision -> numbered-stack.

    The numbered-stack markers we lock are:
    - large monospaced numeral (``font-mono text-3xl tracking-tight``),
    - the 6rem-wide left column reserved for the numeral
      (``md:grid-cols-[6rem_1fr]``),
    - per-row ``border-b`` separator instead of card chrome,
    - first row is "01", third row is "03" (sequence is 01-indexed).
    """
    body = bs.render_section_treatment_list(
        _CLINIC_FIXTURE_DOSSIER,
        variant_id="modern-precision",
    )
    assert "font-mono text-3xl tracking-tight" in body
    assert "md:grid-cols-[6rem_1fr]" in body
    assert ">{\"01\"}<" in body
    assert ">{\"03\"}<" in body
    assert "rounded-2xl border" not in body


def test_treatment_list_returns_empty_when_services_missing() -> None:
    """No services -> empty string regardless of treatment.

    The dispatcher relies on every treatment agreeing on the empty
    fallback so a clinic without published services does not surface
    an empty list scaffold under any variant.
    """
    for variant in (None, "clinic-calm", "warm-care", "modern-precision"):
        assert (
            bs.render_section_treatment_list({}, variant_id=variant) == ""
        )
        assert (
            bs.render_section_treatment_list(
                {"services": []},
                variant_id=variant,
            )
            == ""
        )


# ---------------------------------------------------------------------------
# practice-grid (professional-services) — Phase 2
#
# Three treatments mapped 1:1 against PS variants:
#   consulting-modern  -> dense-grid (default, byte-identical)
#   legal-classic      -> tabular (no card chrome, thin separators)
#   accounting-trust   -> grouped (2-col, numbered eyebrows)
# ---------------------------------------------------------------------------


_PS_FIXTURE_DOSSIER: dict = {
    "services": [
        {"id": "p-1", "label": "Praktik 1", "summary": "Omfång 1."},
        {"id": "p-2", "label": "Praktik 2", "summary": "Omfång 2."},
        {"id": "p-3", "label": "Praktik 3", "summary": "Omfång 3."},
    ]
}


def test_practice_grid_default_is_dense_grid() -> None:
    """No variant -> dense-grid (byte-identical pre-Phase-2 default).

    Locks the contract that introducing treatment dispatch on
    practice-grid does not change the output for callers that do
    not pin a variant. The 3-col card surface (`p-7` cards on flat
    background) is the dense-grid signature; tabular and grouped
    must be absent.
    """
    body = bs.render_section_practice_grid(_PS_FIXTURE_DOSSIER)
    assert (
        "rounded-lg border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-7"
    ) in body
    assert "md:grid-cols-[14rem_1fr_auto]" not in body
    assert "Område 01" not in body


def test_practice_grid_consulting_modern_keeps_default_treatment() -> None:
    """consulting-modern inherits dense-grid (the section default)."""
    body = bs.render_section_practice_grid(
        _PS_FIXTURE_DOSSIER,
        variant_id="consulting-modern",
    )
    assert (
        "rounded-lg border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-7"
    ) in body
    assert "md:grid-cols-[14rem_1fr_auto]" not in body


def test_practice_grid_legal_classic_uses_tabular() -> None:
    """legal-classic -> tabular.

    The tabular markers we lock are:
    - the column-header strip (``Praktikområde / Omfång / Kontakt``),
    - the 14rem-wide name column ``md:grid-cols-[14rem_1fr_auto]``,
    - per-row ``border-b`` separators with no card chrome
      (``rounded-lg`` + ``p-7`` must be absent on rows).
    """
    body = bs.render_section_practice_grid(
        _PS_FIXTURE_DOSSIER,
        variant_id="legal-classic",
    )
    assert "Praktikområde" in body
    assert "Omfång" in body
    assert "md:grid-cols-[14rem_1fr_auto]" in body
    assert (
        "rounded-lg border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-7"
    ) not in body


def test_practice_grid_accounting_trust_uses_grouped() -> None:
    """accounting-trust -> grouped.

    The grouped markers we lock are:
    - the numbered ``Område NN`` eyebrow with accent colour
      (``text-[color:var(--accent)]``),
    - the 2-col layout (``md:grid-cols-2`` — vs dense-grid's
      3-col ``lg:grid-cols-3``),
    - card surface ``bg-[color:var(--card)]`` instead of dense-
      grid's flat ``--background``,
    - the eyebrow sequence is 01-indexed and increments.
    """
    body = bs.render_section_practice_grid(
        _PS_FIXTURE_DOSSIER,
        variant_id="accounting-trust",
    )
    assert "Område 01" in body
    assert "Område 02" in body
    assert "Område 03" in body
    assert "md:grid-cols-2" in body
    assert "lg:grid-cols-3" not in body
    assert "bg-[color:var(--card)]" in body


def test_practice_grid_returns_empty_when_services_missing() -> None:
    """No services -> empty string regardless of treatment."""
    for variant in (
        None,
        "consulting-modern",
        "legal-classic",
        "accounting-trust",
    ):
        assert (
            bs.render_section_practice_grid({}, variant_id=variant) == ""
        )
        assert (
            bs.render_section_practice_grid(
                {"services": []},
                variant_id=variant,
            )
            == ""
        )


# ---------------------------------------------------------------------------
# expertise-areas (professional-services /home) — Phase 2
#
# Two treatments:
#   numbered-2col (default)  -> legal-classic, accounting-trust (default-keep)
#   tag-cluster              -> consulting-modern
# ---------------------------------------------------------------------------


def test_expertise_areas_default_is_numbered_2col() -> None:
    """No variant -> numbered-2col (byte-identical pre-Phase-2 default).

    Locks the contract that introducing treatment dispatch on
    expertise-areas does not change the output for callers that do
    not pin a variant. The left-rail border on each card and the
    numeric eyebrow are how we recognize numbered-2col; the
    tag-cluster pill markers must be absent.
    """
    body = bs.render_section_expertise_areas(_PS_FIXTURE_DOSSIER)
    assert "border-l border-[color:var(--border)] pl-6" in body
    assert (
        "rounded-full border border-[color:var(--border)] "
        "bg-[color:var(--card)] px-5 py-2"
    ) not in body


def test_expertise_areas_legal_classic_keeps_default_treatment() -> None:
    """legal-classic inherits numbered-2col (the section default).

    The classic law-firm variant pins its variation on /expertis
    (practice-grid -> tabular); the home expertise-areas section
    keeps the numbered-2col baseline so the home reads
    consistently with the rest of the legal scaffold.
    """
    body = bs.render_section_expertise_areas(
        _PS_FIXTURE_DOSSIER,
        variant_id="legal-classic",
    )
    assert "border-l border-[color:var(--border)] pl-6" in body
    assert (
        "rounded-full border border-[color:var(--border)] "
        "bg-[color:var(--card)] px-5 py-2"
    ) not in body


def test_expertise_areas_accounting_trust_keeps_default_treatment() -> None:
    """accounting-trust inherits numbered-2col (the section default).

    The audit / advisory variant pins its variation on /expertis
    (practice-grid -> grouped); the home expertise-areas section
    keeps numbered-2col so the home reads as a consistent
    "thoroughness" statement.
    """
    body = bs.render_section_expertise_areas(
        _PS_FIXTURE_DOSSIER,
        variant_id="accounting-trust",
    )
    assert "border-l border-[color:var(--border)] pl-6" in body
    assert (
        "rounded-full border border-[color:var(--border)] "
        "bg-[color:var(--card)] px-5 py-2"
    ) not in body


def test_expertise_areas_consulting_modern_uses_tag_cluster() -> None:
    """consulting-modern -> tag-cluster.

    The tag-cluster markers we lock are:
    - the rounded-full pill (each practice area is a single-line
      pill carrying its label),
    - the wrapping ``flex flex-wrap`` cluster container instead of
      a fixed grid,
    - the joined summary line beneath the cluster (joined with
      "·" middots) — exactly one summary block, not one per
      practice area.
    """
    body = bs.render_section_expertise_areas(
        _PS_FIXTURE_DOSSIER,
        variant_id="consulting-modern",
    )
    assert (
        "rounded-full border border-[color:var(--border)] "
        "bg-[color:var(--card)] px-5 py-2"
    ) in body
    assert "flex flex-wrap" in body
    assert "border-l border-[color:var(--border)] pl-6" not in body
    assert " · " in body


def test_expertise_areas_returns_empty_when_services_missing() -> None:
    """No services -> empty string regardless of treatment."""
    for variant in (
        None,
        "consulting-modern",
        "legal-classic",
        "accounting-trust",
    ):
        assert (
            bs.render_section_expertise_areas({}, variant_id=variant) == ""
        )
        assert (
            bs.render_section_expertise_areas(
                {"services": []},
                variant_id=variant,
            )
            == ""
        )


# ---------------------------------------------------------------------------
# service-list (local-service-business) — Phase 2
#
# Four treatments mapped against LSB variants:
#   nordic-trust       -> tabular           (formal service catalogue)
#   warm-craft         -> alternating-rows  (left/right rhythm)
#   clinical-calm      -> icon-strip        (compact contents bar)
#   midnight-counsel   -> card-grid (default-keep)
#   pulse-fit          -> card-grid (default-keep)
# ---------------------------------------------------------------------------


_LSB_FIXTURE_DOSSIER: dict = {
    "services": [
        {"id": "snickeri", "label": "Snickeri", "summary": "Snickeri-jobb."},
        {"id": "renovering", "label": "Renovering", "summary": "Renovering."},
        {"id": "trädgård", "label": "Trädgård", "summary": "Trädgårdsskötsel."},
        {"id": "platta", "label": "Platta", "summary": "Plattläggning."},
    ]
}


def test_service_list_default_is_card_grid() -> None:
    """No variant -> card-grid (byte-identical pre-Phase-2 default).

    Locks the contract that introducing treatment dispatch on
    service-list does not change the output for callers that do
    not pin a variant. The 3-col gradient-headered card grid with
    hover-lift transitions is the card-grid signature; the other
    three treatments must be absent.
    """
    body = bs.render_section_service_list(
        _LSB_FIXTURE_DOSSIER,
        contact_path="/kontakt",
    )
    assert "lg:grid-cols-3" in body
    assert (
        "rounded-xl border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-6 transition-all"
    ) in body
    assert "md:flex-row-reverse" not in body
    assert "md:grid-cols-[3rem_14rem_1fr]" not in body


def test_service_list_midnight_counsel_keeps_default_treatment() -> None:
    """midnight-counsel inherits card-grid (the section default)."""
    body = bs.render_section_service_list(
        _LSB_FIXTURE_DOSSIER,
        contact_path="/kontakt",
        variant_id="midnight-counsel",
    )
    assert "lg:grid-cols-3" in body
    assert "md:flex-row-reverse" not in body


def test_service_list_pulse_fit_keeps_default_treatment() -> None:
    """pulse-fit inherits card-grid (the section default).

    Phase 2 deliberately keeps pulse-fit on the default; the
    energetic gym variant gets its motion from the hero block,
    not from the service-list. Phase 3 may flip it to
    ``alternating-rows`` based on operator feedback.
    """
    body = bs.render_section_service_list(
        _LSB_FIXTURE_DOSSIER,
        contact_path="/kontakt",
        variant_id="pulse-fit",
    )
    assert "lg:grid-cols-3" in body
    assert "md:flex-row-reverse" not in body


def test_service_list_nordic_trust_uses_tabular() -> None:
    """nordic-trust -> tabular.

    Markers we lock for the tabular treatment:
    - the 3-col grid-template ``md:grid-cols-[3rem_14rem_1fr]``
      (icon / label / summary columns),
    - the swedish column header strings (the service name and
      description labels) with mono / uppercase / tracking-widest
      styling,
    - per-row ``border-b`` separator instead of card chrome.
    """
    body = bs.render_section_service_list(
        _LSB_FIXTURE_DOSSIER,
        contact_path="/kontakt",
        variant_id="nordic-trust",
    )
    assert "md:grid-cols-[3rem_14rem_1fr]" in body
    assert "Tjänst" in body
    assert "Beskrivning" in body
    assert (
        "rounded-xl border border-[color:var(--border)] "
        "bg-[color:var(--background)] p-6 transition-all"
    ) not in body


def test_service_list_warm_craft_uses_alternating_rows() -> None:
    """warm-craft -> alternating-rows.

    Markers we lock for the alternating-rows treatment:
    - ``md:flex-row-reverse`` is applied to even-indexed rows so
      the layout flips back-and-forth (a 4-service fixture
      produces exactly two flipped rows: cards 2 and 4),
    - the larger ``size-16`` icon tile (vs the ``size-12`` used
      by card-grid),
    - rows are list items inside a ``flex flex-col gap-6`` ``ul``,
      not a CSS grid.
    """
    body = bs.render_section_service_list(
        _LSB_FIXTURE_DOSSIER,
        contact_path="/kontakt",
        variant_id="warm-craft",
    )
    assert body.count("md:flex-row-reverse") == 2
    assert "size-16 shrink-0 items-center justify-center rounded-2xl" in body
    assert "lg:grid-cols-3" not in body


def test_service_list_clinical_calm_uses_icon_strip() -> None:
    """clinical-calm -> icon-strip.

    Markers we lock for the icon-strip treatment:
    - the rounded-full pill container (4-service fixture produces
      exactly 4 pills with the icon-pill class signature),
    - the wrapping ``flex flex-wrap`` for the strip itself,
    - the summaries grid below (``border-t pt-6`` cards).
    """
    body = bs.render_section_service_list(
        _LSB_FIXTURE_DOSSIER,
        contact_path="/kontakt",
        variant_id="clinical-calm",
    )
    assert (
        body.count(
            "rounded-full border border-[color:var(--border)] "
            "bg-[color:var(--background)] px-4 py-2"
        )
        == 4
    )
    assert "flex flex-wrap" in body
    assert "border-t border-[color:var(--border)] pt-6" in body
    assert "md:flex-row-reverse" not in body


def test_service_list_returns_empty_when_services_missing() -> None:
    """No services -> empty string regardless of treatment."""
    for variant in (
        None,
        "nordic-trust",
        "warm-craft",
        "clinical-calm",
        "midnight-counsel",
        "pulse-fit",
    ):
        assert (
            bs.render_section_service_list(
                {},
                contact_path="/kontakt",
                variant_id=variant,
            )
            == ""
        )
        assert (
            bs.render_section_service_list(
                {"services": []},
                contact_path="/kontakt",
                variant_id=variant,
            )
            == ""
        )


def test_selected_work_preview_returns_empty_when_services_missing() -> None:
    """No services -> empty string regardless of treatment.

    The dispatcher relies on this so a scaffold can declare the
    section in sections.json without forcing the operator to pre-
    populate case studies. Both treatments must agree on the empty
    fallback or future variant flips will surface an empty card grid.
    """
    for variant in (None, "studio-monochrome", "editorial-warm"):
        assert (
            bs.render_section_selected_work_preview({}, variant_id=variant)
            == ""
        )
        assert (
            bs.render_section_selected_work_preview(
                {"services": []},
                variant_id=variant,
            )
            == ""
        )
