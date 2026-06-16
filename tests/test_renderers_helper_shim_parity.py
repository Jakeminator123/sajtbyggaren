"""Lock the renderers -> render_helpers direct-import contract.

The hero/commerce-CTA cluster and ``_collect_icons_for_pages`` were
extracted into ``packages.generation.build.render_helpers`` (megafiles-plan
Del 1 slice 5) but ``packages.generation.build.renderers`` still reached
them through the lazy ``_call_build_site`` shim against
``scripts.build_site``. The shim broke the repo boundary (package code must
not call up into ``scripts/``), so these helpers are now imported from
``render_helpers`` directly.

These tests are mechanical identity checks (no HTML snapshotting): they
assert the renderer-visible helper is the exact same function object as the
one in ``render_helpers`` and the one ``scripts.build_site`` re-exports. If a
future change re-introduces a wrapper shim for any of them, the identity
breaks and these tests fail loudly. They also pin the CTA-label whitelist
values so the rewire cannot silently change rendered copy.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.build_site as bs  # noqa: E402 - sys.path tweak above
from packages.generation.build import render_helpers as rh  # noqa: E402
from packages.generation.build import renderers as r  # noqa: E402

# Helpers rewired off the shim in this slice. Each must resolve to ONE
# function object shared by renderers, render_helpers and the build_site
# re-export.
_REWIRED_HELPERS = (
    "_hero_cta_variant",
    "_hero_cta_label",
    "_hero_cta_target_path",
    "_commerce_bottom_cta_label",
    "_collect_icons_for_pages",
)


@pytest.mark.parametrize("name", _REWIRED_HELPERS)
def test_rewired_helper_is_single_object_across_modules(name: str) -> None:
    """renderers.<helper> is render_helpers.<helper> is build_site.<helper>."""
    rendered = getattr(r, name)
    helper = getattr(rh, name)
    reexport = getattr(bs, name)
    assert rendered is helper, (
        f"renderers.{name} must import {name} directly from render_helpers, "
        "not wrap it in a _call_build_site shim."
    )
    assert rendered is reexport, (
        f"renderers.{name} must stay identical to the scripts.build_site "
        f"re-export so existing callsites keep the same behaviour."
    )


def test_hero_cta_label_whitelist_values_unchanged() -> None:
    """Rewire preserves the exact CTA-label copy per variant + language."""
    assert r._hero_cta_label({}) == "Begär offert"
    assert r._hero_cta_label({"language": "en"}) == "Request a quote"
    assert r._hero_cta_label({"scaffoldId": "ecommerce-lite"}) == "Shoppa nu"
    assert (
        r._hero_cta_label({"conversionGoals": ["booking_request"]}) == "Boka tid"
    )


def test_hero_cta_variant_values_unchanged() -> None:
    """Variant resolution is byte-identical to the pre-rewire behaviour."""
    assert r._hero_cta_variant({}) == "quote"
    assert r._hero_cta_variant({"scaffoldId": "ecommerce-lite"}) == "shop"
    assert r._hero_cta_variant({"conversionGoals": ["booking_request"]}) == "booking"


def test_commerce_bottom_cta_label_values_unchanged() -> None:
    assert r._commerce_bottom_cta_label({}) == "Hör av dig för att beställa"
    assert r._commerce_bottom_cta_label({"language": "en"}) == "Get in touch to order"


def test_hero_cta_target_path_routes_shop_to_products() -> None:
    dossier = {"conversionGoals": ["product_purchase"]}
    products = {"id": "products", "path": "/produkter"}
    assert r._hero_cta_target_path(dossier, products, "/kontakt") == "/produkter"
    assert r._hero_cta_target_path({}, products, "/kontakt") == "/kontakt"


def test_collect_icons_for_pages_includes_game_icon_for_spel_route() -> None:
    icons = r._collect_icons_for_pages([{"id": "arcade-games"}], ["/spel"])
    assert "Gamepad2" in icons
    assert "ArrowRight" in icons
    assert icons == sorted(icons)
