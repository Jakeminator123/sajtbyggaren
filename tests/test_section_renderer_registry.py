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
    """editorial-warm + bold-electric inherit editorial-stack in pilot.

    Phase 1 only swaps studio-monochrome; the other two agency-studio
    variants must remain on the byte-identical default treatment so
    pre-pilot snapshots are not silently invalidated.
    """
    for variant in ("editorial-warm", "bold-electric"):
        body = bs.render_section_selected_work_preview(
            _AGENCY_STUDIO_FIXTURE_DOSSIER,
            variant_id=variant,
        )
        assert "Case 01" in body, (
            f"variant {variant!r} must inherit editorial-stack "
            "in pilot"
        )
        assert "Studio nº" not in body
        assert "md:translate-y-12" not in body


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
    assert "bg-[color:var(--card)]" in body
    assert "rounded-[var(--radius-lg)]" in body
    assert "md:translate-y-12" in body


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
