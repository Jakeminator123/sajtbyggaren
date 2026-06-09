"""Visible section_add: home-page inline section injection (slice 0 + 1).

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
