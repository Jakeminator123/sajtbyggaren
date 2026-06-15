"""Tests for route_directives (Route/Nav Mutation V1, ADR 0060).

The deterministic resolver that turns the router's best-effort route_remove
targets into disable-able scaffold routeIds. It validates each id against the
site's scaffold ``defaultRoutes`` and enforces the required-page guard, so:

- a non-required scaffold route (``about``) resolves to ``disabled``;
- a required route (``contact``/``services``) is refused in Slice A;
- ``home`` is always refused (the landing page is never removable);
- an unknown id, or a None target (the router saw a page removal but could not
  name the page), is refused with an honest reason - never a fabricated route.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.followup.route_directives import (  # noqa: E402
    resolve_disabled_routes,
)

pytestmark = pytest.mark.core

# Mirrors local-service-business/routes.json: home/services/contact required,
# about optional.
_LSB_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True},
        {"id": "services", "path": "/tjanster", "required": True},
        {"id": "about", "path": "/om-oss", "required": False},
        {"id": "contact", "path": "/kontakt", "required": True},
    ]
}


def test_non_required_route_resolves_to_disabled():
    disabled, refused = resolve_disabled_routes(["about"], _LSB_ROUTES)
    assert disabled == ["about"]
    assert refused == []


def test_required_route_is_refused_in_slice_a():
    disabled, refused = resolve_disabled_routes(["contact"], _LSB_ROUTES)
    assert disabled == []
    assert len(refused) == 1
    assert refused[0]["routeId"] == "contact"
    assert "obligatorisk" in refused[0]["reason"].lower()


def test_home_is_always_refused():
    disabled, refused = resolve_disabled_routes(["home"], _LSB_ROUTES)
    assert disabled == []
    assert refused[0]["routeId"] == "home"
    assert "startsidan" in refused[0]["reason"].lower()


def test_unknown_route_is_refused():
    disabled, refused = resolve_disabled_routes(["banana"], _LSB_ROUTES)
    assert disabled == []
    assert refused[0]["routeId"] == "banana"
    assert "finns inte" in refused[0]["reason"].lower()


def test_none_target_is_refused_with_clear_reason():
    """The router saw a page removal but could not name the page (routeId None)."""
    disabled, refused = resolve_disabled_routes([None], _LSB_ROUTES)
    assert disabled == []
    assert refused[0]["routeId"] == "(okänd)"


def test_allow_required_opens_contact_removal_for_slice_b():
    """Slice B (allow_required=True) lets the contact route be disabled; Slice A
    (the default) keeps it. Locks the seam route/nav V1 leaves for the CTA-
    retarget slice without changing Slice A behaviour."""
    disabled_a, _ = resolve_disabled_routes(["contact"], _LSB_ROUTES)
    assert disabled_a == []
    disabled_b, refused_b = resolve_disabled_routes(
        ["contact"], _LSB_ROUTES, allow_required=True
    )
    assert disabled_b == ["contact"]
    assert refused_b == []
    # home stays refused even with allow_required (never removable).
    disabled_home, refused_home = resolve_disabled_routes(
        ["home"], _LSB_ROUTES, allow_required=True
    )
    assert disabled_home == []
    assert refused_home[0]["routeId"] == "home"


def test_dedupes_and_preserves_order():
    disabled, _ = resolve_disabled_routes(["about", "about"], _LSB_ROUTES)
    assert disabled == ["about"]


def test_malformed_scaffold_routes_refuses_safely():
    """A missing/malformed routes payload refuses every target (never crashes,
    never disables a route by accident)."""
    disabled, refused = resolve_disabled_routes(["about"], {})
    assert disabled == []
    assert refused and refused[0]["routeId"] == "about"
