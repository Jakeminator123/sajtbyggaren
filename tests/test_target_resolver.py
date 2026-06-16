"""Tests for the follow-up Target Resolver V1 (packages/generation/followup/target_resolver).

The deterministic, offline resolver that turns a natural Swedish place
expression into a confident, scaffold-validated structured target. These tests
lock the new contract:

- routeId resolution: known page phrases map to the scaffold's routeId; an
  off-scaffold page ("tjänstesidan" on an e-commerce site) and an unknown phrase
  resolve to None (never an invented page);
- placement reuse: the router's coarse top/bottom position is mirrored onto the
  schema's route-order enum, everything else defaults to before-contact;
- confidence/fallback: only an explicit, validated page clears
  CONFIDENCE_THRESHOLD; a relative expression or a coarse-only signal stays below
  it so the caller keeps its current default (no behaviour change);
- determinism: same input -> same output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.followup.target_resolver import (  # noqa: E402
    CONFIDENCE_THRESHOLD,
    resolve_target,
)
from packages.generation.orchestration.router.models import (  # noqa: E402
    RouterDecision,
    RouterTarget,
)

pytestmark = pytest.mark.core


# Mirrors local-service-business/routes.json: home/services/contact required,
# about optional. There is no products/menu route, so those phrases must resolve
# to None on this scaffold.
_LSB_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True},
        {"id": "services", "path": "/tjanster", "required": True},
        {"id": "about", "path": "/om-oss", "required": False},
        {"id": "contact", "path": "/kontakt", "required": True},
    ]
}

# Mirrors ecommerce-lite/routes.json: products instead of services.
_ECOM_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True},
        {"id": "products", "path": "/produkter", "required": True},
        {"id": "about", "path": "/om-oss", "required": False},
        {"id": "contact", "path": "/kontakt", "required": True},
    ]
}


def _decision(position=None, section_id=None, ordinal=None):
    """A minimal RouterDecision whose target carries the coarse fields read."""
    target = RouterTarget(
        position=position, sectionId=section_id, sectionOrdinal=ordinal
    )
    return RouterDecision(
        messageKind="edit_instruction", editKind="section_add", target=target
    )


# ---------------------------------------------------------------------------
# routeId resolution
# ---------------------------------------------------------------------------


def test_known_page_phrase_resolves_route_id():
    res = resolve_target(
        "lägg till en FAQ-sektion på kontaktsidan", _decision(), _LSB_ROUTES
    )
    assert res["routeId"] == "contact"
    assert res["confidence"] >= CONFIDENCE_THRESHOLD
    assert res["placement"] == "before-contact"


def test_startsidan_resolves_home():
    res = resolve_target("lägg till en banner på startsidan", _decision(), _LSB_ROUTES)
    assert res["routeId"] == "home"
    assert res["confidence"] >= CONFIDENCE_THRESHOLD


def test_tjanstesidan_resolves_services_on_lsb():
    res = resolve_target("lägg till priser på tjänstesidan", _decision(), _LSB_ROUTES)
    assert res["routeId"] == "services"


def test_products_phrase_resolves_on_ecommerce():
    res = resolve_target(
        "lägg till en banner på produktsidan", _decision(), _ECOM_ROUTES
    )
    assert res["routeId"] == "products"


def test_off_scaffold_page_resolves_none():
    """A services page does not exist on the e-commerce scaffold -> honest None."""
    res = resolve_target("lägg till priser på tjänstesidan", _decision(), _ECOM_ROUTES)
    assert res["routeId"] is None
    assert res["confidence"] < CONFIDENCE_THRESHOLD
    assert "finns inte" in res["rationale"].lower()


def test_unknown_phrase_resolves_none():
    res = resolve_target("gör texten mer formell", _decision(), _LSB_ROUTES)
    assert res["routeId"] is None
    assert res["confidence"] == 0.0


def test_word_boundary_avoids_substring_false_positive():
    """"kontakt" must NOT match inside "kontaktformulär" (a component, not a page)."""
    res = resolve_target("lägg till ett kontaktformulär", _decision(), _LSB_ROUTES)
    assert res["routeId"] is None


# ---------------------------------------------------------------------------
# placement reuse (router position -> schema enum)
# ---------------------------------------------------------------------------


def test_placement_reuses_router_bottom():
    res = resolve_target(
        "lägg till en FAQ längst ner på kontaktsidan",
        _decision(position="bottom"),
        _LSB_ROUTES,
    )
    assert res["routeId"] == "contact"
    assert res["placement"] == "bottom"
    assert res["confidence"] >= CONFIDENCE_THRESHOLD


def test_placement_reuses_router_top():
    res = resolve_target(
        "lägg till en banner överst på startsidan",
        _decision(position="top"),
        _LSB_ROUTES,
    )
    assert res["placement"] == "top"
    assert res["routeId"] == "home"


def test_left_right_center_fall_to_default_placement():
    """left/right/center are intra-section, not route-order -> default slot."""
    res = resolve_target(
        "lägg till X till vänster på kontaktsidan",
        _decision(position="left"),
        _LSB_ROUTES,
    )
    assert res["placement"] == "before-contact"
    assert res["routeId"] == "contact"


# ---------------------------------------------------------------------------
# confidence / fallback (non-regressive by design)
# ---------------------------------------------------------------------------


def test_relative_expression_does_not_resolve_page():
    """"under tjänster" = below the services SECTION, not the services page."""
    res = resolve_target(
        "lägg till en faq-sektion under tjänster", _decision(), _LSB_ROUTES
    )
    assert res["routeId"] is None
    assert res["confidence"] < CONFIDENCE_THRESHOLD
    assert "relativ" in res["rationale"].lower()


def test_coarse_position_only_stays_below_threshold():
    """A position but no page -> caller falls back to its current default."""
    res = resolve_target(
        "lägg till en faq längst ner", _decision(position="bottom"), _LSB_ROUTES
    )
    assert res["routeId"] is None
    assert res["placement"] == "bottom"
    assert res["confidence"] < CONFIDENCE_THRESHOLD


def test_empty_prompt_resolves_none():
    res = resolve_target("", _decision(), _LSB_ROUTES)
    assert res["routeId"] is None
    assert res["confidence"] == 0.0


def test_malformed_scaffold_routes_resolves_none_safely():
    """A missing/malformed routes payload never crashes and never invents a page."""
    res = resolve_target("lägg till X på kontaktsidan", _decision(), {})
    assert res["routeId"] is None
    assert res["confidence"] < CONFIDENCE_THRESHOLD
    assert res["placement"] == "before-contact"


# ---------------------------------------------------------------------------
# sectionId resolution + determinism
# ---------------------------------------------------------------------------


def test_section_map_resolves_ordinal_to_section_id():
    res = resolve_target(
        "ändra andra sektionen på startsidan",
        _decision(ordinal=2),
        _LSB_ROUTES,
        section_map={"home": ["hero", "services", "contact-cta"]},
    )
    assert res["routeId"] == "home"
    assert res["sectionId"] == "services"


def test_section_id_passthrough_from_decision():
    res = resolve_target(
        "lägg till X på kontaktsidan", _decision(section_id="hero"), _LSB_ROUTES
    )
    assert res["sectionId"] == "hero"


def test_determinism():
    prompt = "lägg till en FAQ-sektion på kontaktsidan längst ner"
    decision = _decision(position="bottom")
    first = resolve_target(prompt, decision, _LSB_ROUTES)
    second = resolve_target(prompt, decision, _LSB_ROUTES)
    assert first == second
    assert first["routeId"] == "contact"
