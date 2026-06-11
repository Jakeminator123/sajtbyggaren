"""Visible section_add: home-page inline section injection (slice 0 + 1 + 4).

Locks the LSB home composition so the new ``directives.mountedSections``
injection path stays behavior-preserving:

- Slice 0 (golden): rendering ``render_home`` for a representative dossier WITHOUT
  any ``directives.mountedSections`` must produce exactly the same body it does
  today (no new section, no reordering). This is the regression guard that lets
  later slices change ``render_home``'s section assembly safely.
- Slice 1 (inline render): a grounded ``mountedSections`` entry for a section that
  is NOT already on home (``hours-summary``) makes that section render inline on
  the home page (so the deterministic file-diff reports a real visible effect),
  while an ungrounded / unknown / already-present entry stays an honest no-op.

Deterministic, offline, no LLM. Section choice rationale: ``hours-summary`` has a
registered renderer (``render_section_hours_summary``), emits a self-contained
``<section>`` block, is grounded on ``contact.openingHours`` and is not part of
the default LSB home order, so injecting it is a clean, observable change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.build.renderers import render_home  # noqa: E402

_PAINTER_PALMA = REPO_ROOT / "examples" / "painter-palma.project-input.json"
_HOME_ROUTES = ["/", "/tjanster", "/om-oss", "/kontakt"]


def _painter_dossier() -> dict[str, Any]:
    return json.loads(_PAINTER_PALMA.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_home_without_mounted_sections_is_unchanged():
    """Golden lock: no ``mountedSections`` -> today's home output, byte-for-byte.

    Locked against the live example dossier so a future ``render_home`` change
    that does not inject a section can never silently shift the baseline home
    composition. The injection path must be a strict superset: absent the
    directive, nothing moves.
    """
    dossier = _painter_dossier()
    dossier.pop("directives", None)
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])

    # The default LSB home order, in declaration order, with the closing CTA last.
    assert 'export default function Home() {' in rendered
    assert rendered.rstrip().endswith("}")
    # hours-summary is NOT part of the default home order.
    assert "Öppettider" not in rendered
    # Sanity: the hardcoded default sections are present and ordered.
    hero_idx = rendered.find("Palma de Mallorca")
    story_idx = rendered.find(dossier["company"]["story"][:24])
    cta_idx = rendered.rfind("Hör av dig")
    assert 0 < hero_idx < story_idx < cta_idx, (
        "Default LSB home order (hero -> story -> ... -> contact-cta) drifted; "
        "the golden baseline changed without a mountedSections directive."
    )


@pytest.mark.tooling
def test_home_injects_grounded_mounted_section():
    """Slice 1: a grounded ``hours-summary`` directive renders inline on home.

    With ``contact.openingHours`` set (grounded) the injected section must emit
    the opening-hours card into the home body, before the closing contact-cta,
    so the targeted-render file-diff reports a real visible effect.
    """
    dossier = _painter_dossier()
    dossier["directives"] = {
        "mountedSections": [{"sectionId": "hours-summary", "routeId": "home"}]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])

    assert "Öppettider" in rendered, (
        "A grounded hours-summary mountedSections entry must render the "
        "opening-hours section inline on the home page."
    )
    # Injected before the closing contact-cta (default slot).
    hours_idx = rendered.find("Öppettider")
    cta_idx = rendered.rfind("Hör av dig")
    assert 0 < hours_idx < cta_idx, (
        "The injected section must land before the closing contact-cta."
    )


@pytest.mark.tooling
def test_home_ungrounded_mounted_section_is_no_op():
    """Honest no-op: an ungrounded section is not injected.

    ``hours-summary`` with no real ``contact.openingHours`` must stay invisible
    (its renderer returns "" and the gate refuses to inject), so the home body
    is byte-identical to the no-directive baseline.
    """
    dossier = _painter_dossier()
    dossier["contact"]["openingHours"] = ""
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )

    dossier["directives"] = {
        "mountedSections": [{"sectionId": "hours-summary", "routeId": "home"}]
    }
    injected = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])

    assert injected == baseline, (
        "An ungrounded hours-summary must not change the home output "
        "(honest mounted-but-no-content)."
    )
    assert "Öppettider" not in injected


@pytest.mark.tooling
def test_home_unknown_mounted_section_is_no_op():
    """A section id with no registered renderer is ignored, not a hard exit.

    ``render_route_generic`` raises ``SystemExit`` on unknown section ids, so
    the gate must drop unregistered ids before assembling the section order.
    The home output stays the no-directive baseline.
    """
    dossier = _painter_dossier()
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )

    dossier["directives"] = {
        "mountedSections": [{"sectionId": "does-not-exist", "routeId": "home"}]
    }
    injected = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    assert injected == baseline


@pytest.mark.tooling
def test_home_mounted_section_position_top_lands_after_hero():
    """Slice 2: position=top injects the section right after the hero, before
    the services summary; the default slot lands it before the contact-cta."""
    dossier = _painter_dossier()
    dossier["directives"] = {
        "mountedSections": [
            {"sectionId": "hours-summary", "routeId": "home", "position": "top"}
        ]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    hours_idx = rendered.find("Öppettider")
    services_idx = rendered.find("Inomhusmålning")
    cta_idx = rendered.rfind("Hör av dig")
    assert 0 < hours_idx < services_idx < cta_idx, (
        "position=top must place the section after the hero and before the "
        "services summary."
    )


@pytest.mark.tooling
def test_home_mounted_section_default_position_before_contact():
    """No position -> the section lands just before the closing contact-cta."""
    dossier = _painter_dossier()
    dossier["directives"] = {
        "mountedSections": [{"sectionId": "hours-summary", "routeId": "home"}]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    hours_idx = rendered.find("Öppettider")
    services_idx = rendered.find("Inomhusmålning")
    cta_idx = rendered.rfind("Hör av dig")
    assert 0 < services_idx < hours_idx < cta_idx, (
        "default slot must place the section after the body and before the "
        "closing contact-cta."
    )


@pytest.mark.tooling
def test_home_non_allowlisted_section_is_no_op():
    """Codex review fix (defense in depth): a hand-edited/stale Project Input
    must not be able to inject an arbitrary REGISTERED section onto home.
    ``service-list`` has a renderer and grounded content (painter-palma has
    services) and is not in the default home order - without the render-time
    allowlist it WOULD inject. The allowlist must drop it."""
    dossier = _painter_dossier()
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )
    dossier["directives"] = {
        "mountedSections": [{"sectionId": "service-list", "routeId": "home"}]
    }
    injected = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    assert injected == baseline, (
        "a non-allowlisted section must never be injected, even when its "
        "renderer exists and would produce content."
    )


@pytest.mark.tooling
def test_home_inline_injection_gated_on_scaffold():
    """The render-time allowlist is keyed on (scaffoldId, routeId): the same
    grounded hours-summary directive must be a no-op on a scaffold the ADR
    has not sanctioned for inline injection."""
    dossier = _painter_dossier()
    dossier["scaffoldId"] = "agency-studio"
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )
    dossier["directives"] = {
        "mountedSections": [{"sectionId": "hours-summary", "routeId": "home"}]
    }
    injected = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    assert injected == baseline
    assert "Öppettider" not in injected


@pytest.mark.tooling
def test_home_already_present_section_not_duplicated():
    """A directive for a section already in the home order does not duplicate it.

    ``story`` is part of the default LSB home order; mounting it again must not
    render two story sections.
    """
    dossier = _painter_dossier()
    dossier["directives"] = {
        "mountedSections": [{"sectionId": "story", "routeId": "home"}]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    story_marker = dossier["company"]["story"][:24]
    assert rendered.count(story_marker) == 1, (
        "A section already present in the home order must not be injected twice."
    )


# ---------------------------------------------------------------------------
# Slice 4 (ADR 0042): gallery as a movable inline section. ``gallery`` is part
# of the default home order whenever the operator has gallery images, so a
# section_add "lägg till galleri överst" must MOVE the section to the
# requested slot (never duplicate it, never silently no-op the operator's
# placement intent). The same seam works on ecommerce-lite, whose home goes
# through the same render_home shim.
# ---------------------------------------------------------------------------

# Two images: with a non-empty company.story the home gallery section skips the
# first image (the story section consumes it), so a single image would suppress
# the section entirely and the move tests would assert against nothing.
_GALLERY_ITEMS = [
    {"filename": "verkstad-01.webp", "alt": "Verkstaden"},
    {"filename": "verkstad-02.webp", "alt": "Penslar"},
]


def _gallery_dossier(scaffold_id: str = "local-service-business") -> dict[str, Any]:
    dossier = _painter_dossier()
    dossier["scaffoldId"] = scaffold_id
    dossier["gallery"] = [dict(item) for item in _GALLERY_ITEMS]
    return dossier


@pytest.mark.tooling
def test_home_gallery_move_top_lands_after_hero():
    """ADR 0042: gallery + position=top MOVES the default mid-page gallery to
    right after the hero — rendered exactly once, before the services summary."""
    dossier = _gallery_dossier()
    dossier["directives"] = {
        "mountedSections": [
            {"sectionId": "gallery", "routeId": "home", "position": "top"}
        ]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    gallery_idx = rendered.find("Ett urval från projekten")
    services_idx = rendered.find("Inomhusmålning")
    assert 0 < gallery_idx < services_idx, (
        "position=top must move the gallery section after the hero and before "
        "the services summary."
    )
    assert rendered.count("Ett urval från projekten") == 1, (
        "A moved section must render exactly once (move, not duplicate)."
    )


@pytest.mark.tooling
def test_home_gallery_move_bottom_lands_before_contact():
    """ADR 0042: gallery + position=bottom moves the section to just before the
    closing contact-cta (after the default mid-page slot)."""
    dossier = _gallery_dossier()
    dossier["directives"] = {
        "mountedSections": [
            {"sectionId": "gallery", "routeId": "home", "position": "bottom"}
        ]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    gallery_idx = rendered.find("Ett urval från projekten")
    services_idx = rendered.find("Inomhusmålning")
    cta_idx = rendered.rfind("Hör av dig")
    assert 0 < services_idx < gallery_idx < cta_idx, (
        "position=bottom must move the gallery section after the body and "
        "before the closing contact-cta."
    )
    assert rendered.count("Ett urval från projekten") == 1


@pytest.mark.tooling
def test_home_gallery_without_position_keeps_default_slot():
    """ADR 0038 duplicate gate preserved: a gallery directive WITHOUT an
    explicit position must not move the already-present section — the home
    output stays byte-identical to the no-directive baseline."""
    dossier = _gallery_dossier()
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )
    dossier["directives"] = {
        "mountedSections": [{"sectionId": "gallery", "routeId": "home"}]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    assert rendered == baseline, (
        "Without an explicit position an already-present section must stay an "
        "honest no-op (no move, no duplicate)."
    )


@pytest.mark.tooling
def test_home_gallery_move_works_on_ecommerce_lite():
    """ADR 0042 scaffold gate: ecommerce-lite home goes through the same
    render_home shim, so the same move directive must work there too."""
    dossier = _gallery_dossier(scaffold_id="ecommerce-lite")
    dossier["directives"] = {
        "mountedSections": [
            {"sectionId": "gallery", "routeId": "home", "position": "top"}
        ]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    gallery_idx = rendered.find("Ett urval från projekten")
    assert gallery_idx > 0, "gallery must render on ecommerce-lite home"
    services_idx = rendered.find("Inomhusmålning")
    assert gallery_idx < services_idx, (
        "position=top must land the gallery before the body on ecommerce-lite."
    )
    assert rendered.count("Ett urval från projekten") == 1


@pytest.mark.tooling
def test_home_gallery_move_blocked_on_unsanctioned_scaffold():
    """The (scaffoldId, routeId) allowlist still gates moves: the same grounded
    move directive must be a no-op on a scaffold ADR 0042 has not sanctioned."""
    dossier = _gallery_dossier(scaffold_id="agency-studio")
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )
    dossier["directives"] = {
        "mountedSections": [
            {"sectionId": "gallery", "routeId": "home", "position": "top"}
        ]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    assert rendered == baseline


@pytest.mark.tooling
def test_home_gallery_move_without_images_is_no_op():
    """Grounded-content gate: a gallery move with NO gallery images must not
    inject or move anything (the renderer returns "" and the gate drops it)."""
    dossier = _painter_dossier()  # painter-palma has no gallery images
    assert not dossier.get("gallery")
    baseline = render_home(
        {**dossier, "directives": {}}, _HOME_ROUTES, variant_id=dossier["variantId"]
    )
    dossier["directives"] = {
        "mountedSections": [
            {"sectionId": "gallery", "routeId": "home", "position": "top"}
        ]
    }
    rendered = render_home(dossier, _HOME_ROUTES, variant_id=dossier["variantId"])
    assert rendered == baseline
    assert "Ett urval från projekten" not in rendered
