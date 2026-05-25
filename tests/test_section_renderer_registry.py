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
        "faq",
        "certifications",
    }
    candidates = referenced - not_yet_extracted

    missing = sorted(candidates - bs._SECTION_RENDERERS.keys())
    assert missing == [], (
        "Either register a renderer for these LSB sections or add them "
        "to the not-yet-extracted allowlist: " + ", ".join(missing)
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
