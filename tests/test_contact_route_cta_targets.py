"""Regression coverage locking contact-CTA / contact_path route targets.

These tests pin the route a CTA points at so a scaffold or starter can
never link a call-to-action to a missing or wrong route. They are
test-only: they exercise the shared builder helpers
(``_hero_cta_target_path``, ``_pick_contact_route``) and the full
``write_pages`` output without touching any rendering or section logic.

Complementary to ``tests/test_contact_route_regression.py`` (which locks
the threaded ``contact_path`` plumbing and SystemExit on bad scaffold
paths). The scenarios here instead lock the *target selection* contract:

1. The local-service-business primary hero CTA resolves to the scaffold's
   real contact route path.
2. For every shipped scaffold, no rendered CTA href targets a route path
   that is absent from that scaffold's ``defaultRoutes``.
3. ``_hero_cta_target_path`` falls back to ``contact_path`` whenever there
   is no products listing route to jump to.
4. ``_pick_contact_route`` returns the contact route when present and
   fails fast (as designed) when the scaffold omits it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"

# Matches both bare (`href="/x"`) and JSX-wrapped (`href={"/x"}`) hrefs.
HREF_RE = re.compile(r'href=\{?(".*?")\}?')

# Every shipped scaffold ships a routes.json with a contact route. Listing
# the ids here keeps the per-scaffold test deterministic and offline (it
# never globs the filesystem for an unexpected directory mid-run).
SHIPPED_SCAFFOLDS = (
    "agency-studio",
    "clinic-healthcare",
    "ecommerce-lite",
    "local-service-business",
    "professional-services",
    "restaurant-hospitality",
)


def _minimal_dossier() -> dict:
    """Return a deterministic local-service-business project input.

    Mirrors the fixture shape in ``test_contact_route_regression`` so the
    two suites stay in lockstep, but is duplicated locally so this file is
    self-contained and can be read in isolation.
    """
    return {
        "siteId": "contact-cta-target-test",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Test AB",
            "businessType": "test",
            "tagline": "En kort tagline",
            "story": "En kort story om Test AB.",
            "team": [{"name": "Test Person", "role": "Roll"}],
        },
        "location": {
            "city": "Stockholm",
            "country": "Sverige",
            "serviceAreas": ["Norrmalm"],
        },
        "services": [
            {"id": "interior-painting", "label": "Inomhusmalning", "summary": "Tak."},
            {"id": "exterior-painting", "label": "Fasadmalning", "summary": "Fasader."},
        ],
        "trustSignals": ["Tio ar i branschen"],
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "hej@test.se",
            "addressLines": ["Storgatan 1", "111 11 Stockholm"],
            "openingHours": "Man-Fre 9-17",
        },
        "conversionGoals": ["quote_request"],
    }


def _href_values(output: str) -> list[str]:
    return [json.loads(match.group(1)) for match in HREF_RE.finditer(output)]


def _internal_route_hrefs(output: str) -> list[str]:
    """Return hrefs that target an in-site route (start with ``/``).

    Anchor links (``#main-content``), ``mailto:``/``tel:`` actions and
    absolute ``https://`` font/CDN hrefs are not route targets and are
    intentionally excluded.
    """
    return [href for href in _href_values(output) if href.startswith("/")]


def _load_scaffold_routes(scaffold_id: str) -> dict:
    return json.loads((SCAFFOLDS_DIR / scaffold_id / "routes.json").read_text(encoding="utf-8"))


def _declared_route_paths(scaffold_id: str) -> set[str]:
    routes = _load_scaffold_routes(scaffold_id)
    return {route["path"] for route in routes["defaultRoutes"]}


def _scaffold_dossier(scaffold_id: str) -> dict:
    dossier = _minimal_dossier()
    dossier["scaffoldId"] = scaffold_id
    dossier["variantId"] = None
    if scaffold_id == "ecommerce-lite":
        dossier["conversionGoals"] = ["product_purchase", "shop_visit"]
    return dossier


def test_local_service_primary_cta_targets_real_contact_route() -> None:
    """LSB hero (quote variant) must point at the scaffold's contact path."""
    from packages.generation.build.render_helpers import _hero_cta_target_path

    routes = _load_scaffold_routes("local-service-business")
    contact_path = next(r["path"] for r in routes["defaultRoutes"] if r["id"] == "contact")

    target = _hero_cta_target_path(
        _minimal_dossier(),
        listing_route={"id": "services", "path": "/tjanster"},
        contact_path=contact_path,
    )

    assert target == contact_path
    assert contact_path in _declared_route_paths("local-service-business")


@pytest.mark.parametrize("scaffold_id", SHIPPED_SCAFFOLDS)
def test_scaffold_cta_hrefs_never_target_undeclared_route(
    scaffold_id: str,
    tmp_path: Path,
) -> None:
    """No rendered CTA may link to a path missing from defaultRoutes."""
    from scripts.build_site import write_pages

    routes = _load_scaffold_routes(scaffold_id)
    declared = _declared_route_paths(scaffold_id)

    write_pages(tmp_path, _scaffold_dossier(scaffold_id), routes, [])

    rendered = sorted(tmp_path.rglob("*.tsx"))
    assert rendered, f"{scaffold_id} should render at least one page."

    for page in rendered:
        for href in _internal_route_hrefs(page.read_text(encoding="utf-8")):
            assert href in declared, (
                f"{scaffold_id}:{page.relative_to(tmp_path)} links to {href!r} "
                f"which is not a declared defaultRoutes path ({sorted(declared)})."
            )


def test_hero_cta_target_falls_back_to_contact_without_products_listing() -> None:
    """Shop CTA with no products listing must land on contact_path."""
    from packages.generation.build.render_helpers import _hero_cta_target_path

    shop_dossier = _minimal_dossier()
    shop_dossier["scaffoldId"] = "ecommerce-lite"
    shop_dossier["conversionGoals"] = ["product_purchase", "shop_visit"]
    contact_path = "/kundservice"

    # No listing route at all, and a non-products listing route, both fall back.
    assert _hero_cta_target_path(shop_dossier, None, contact_path) == contact_path
    services_listing = {"id": "services", "path": "/tjanster"}
    assert _hero_cta_target_path(shop_dossier, services_listing, contact_path) == contact_path

    # Sanity anchor: with a real products listing the shop CTA jumps to it,
    # so the fallback above is genuinely the no-listing branch.
    products_listing = {"id": "products", "path": "/produkter"}
    assert _hero_cta_target_path(shop_dossier, products_listing, contact_path) == "/produkter"


def test_pick_contact_route_returns_contact_and_fails_fast_when_missing() -> None:
    """_pick_contact_route returns the contact route or exits, by design."""
    from packages.generation.build.render_helpers import _pick_contact_route

    with_contact = [
        {"id": "home", "path": "/"},
        {"id": "services", "path": "/tjanster"},
        {"id": "contact", "path": "/kontakta-oss"},
    ]
    contact = _pick_contact_route(with_contact)
    assert contact["id"] == "contact"
    assert contact["path"] == "/kontakta-oss"

    without_contact = [
        {"id": "home", "path": "/"},
        {"id": "services", "path": "/tjanster"},
    ]
    with pytest.raises(SystemExit):
        _pick_contact_route(without_contact)
