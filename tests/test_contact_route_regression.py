"""Regression coverage for generated Contact CTA route targets."""

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
HREF_RE = re.compile(r'href=\{?(".*?")\}?')


def _minimal_dossier() -> dict:
    return {
        "siteId": "contact-route-test",
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
            {
                "id": "interior-painting",
                "label": "Inomhusmålning",
                "summary": "Tak och väggar.",
            },
            {
                "id": "exterior-painting",
                "label": "Fasadmålning",
                "summary": "Fasader.",
            },
        ],
        "trustSignals": ["Tio år i branschen"],
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "hej@test.se",
            "addressLines": ["Storgatan 1", "111 11 Stockholm"],
            "openingHours": "Mån-Fre 9-17",
        },
        "conversionGoals": ["quote_request"],
    }


def _route_href_attr(path: str) -> str:
    from scripts.build_site import _route_href

    return f"href={_route_href(path)}"


def _href_values(output: str) -> list[str]:
    return [json.loads(match.group(1)) for match in HREF_RE.finditer(output)]


def _load_scaffold_routes(scaffold_id: str) -> dict:
    return json.loads((SCAFFOLDS_DIR / scaffold_id / "routes.json").read_text(encoding="utf-8"))


def test_pick_contact_route_uses_scaffold_canonical_contact_route() -> None:
    """A moved contact route must be selected by route id, not by path."""
    from scripts.build_site import _pick_contact_route

    restaurant_routes = _load_scaffold_routes("restaurant-hospitality")

    contact_route = _pick_contact_route(restaurant_routes["defaultRoutes"])

    assert contact_route["id"] == "contact"
    assert contact_route["path"] == "/hitta-hit"


def test_core_contact_ctas_are_non_empty_and_share_threaded_contact_path() -> None:
    from scripts.build_site import render_home, render_products, render_services

    dossier = _minimal_dossier()
    contact_path = "/kontakta-oss"
    outputs = {
        "home": render_home(
            dossier,
            [],
            listing_route={"id": "services", "path": "/tjanster"},
            contact_path=contact_path,
        ),
        "services": render_services(dossier, contact_path=contact_path),
        "products": render_products(dossier, contact_path=contact_path),
    }

    for page_name, output in outputs.items():
        hrefs = _href_values(output)
        assert hrefs, f"{page_name} should render at least one CTA href."
        assert all(href for href in hrefs), f"{page_name} should not render empty hrefs."
        assert _route_href_attr(contact_path) in output
        assert _route_href_attr("/kontakt") not in output


def test_ecommerce_contact_ctas_do_not_fall_back_to_local_service_contact_route(
    tmp_path: Path,
) -> None:
    from scripts.build_site import write_pages

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "ecommerce-lite"
    dossier["variantId"] = "clean-store"
    dossier["conversionGoals"] = ["product_purchase", "shop_visit"]
    ecommerce_routes = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "products", "path": "/butik", "required": True, "purpose": "Products"},
            {"id": "about", "path": "/om-oss", "required": False, "purpose": "About"},
            {
                "id": "contact",
                "path": "/kundservice",
                "required": True,
                "purpose": "Contact",
            },
        ]
    }

    written = write_pages(tmp_path, dossier, ecommerce_routes, [])

    assert written == ["/", "/butik", "/om-oss", "/kundservice"]
    home = (tmp_path / "app" / "page.tsx").read_text(encoding="utf-8")
    products = (tmp_path / "app" / "butik" / "page.tsx").read_text(encoding="utf-8")
    layout = (tmp_path / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert _route_href_attr("/butik") in home
    for output in (home, products, layout):
        assert _route_href_attr("/kundservice") in output
        assert _route_href_attr("/kontakt") not in output
        assert _route_href_attr("/tjanster") not in output


def test_renderer_defaults_keep_deterministic_contact_fallback() -> None:
    from scripts.build_site import render_home, render_products, render_services

    dossier = _minimal_dossier()
    outputs = [
        render_home(dossier, [], listing_route={"id": "services", "path": "/tjanster"}),
        render_services(dossier),
        render_products(dossier),
    ]

    for output in outputs:
        assert _route_href_attr("/kontakt") in output
        assert all(href for href in _href_values(output))


@pytest.mark.parametrize(
    "bad_contact_path",
    [
        "",
        "mailto:hej@test.se",
        "tel:+46701234567",
        "https://example.com/contact",
        "//example.com/contact",
    ],
)
def test_contact_route_rejects_empty_or_external_scaffold_paths(
    tmp_path: Path,
    bad_contact_path: str,
) -> None:
    from scripts.build_site import write_pages

    routes = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "services", "path": "/tjanster", "required": True, "purpose": "Services"},
            {
                "id": "contact",
                "path": bad_contact_path,
                "required": True,
                "purpose": "Contact",
            },
        ]
    }

    with pytest.raises(SystemExit):
        write_pages(tmp_path, _minimal_dossier(), routes, [])
