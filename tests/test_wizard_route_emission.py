"""Regression tests for wizard-driven route emission (B132 follow-up
sprint 2026-05-21).

Locks the contract that ``packages.generation.planning.plan`` adds
selected wizard mustHave pages to the routePlan and that
``scripts.build_site.write_pages`` dispatches them via
``_WIZARD_ROUTE_RENDERERS`` for ``local-service-business``. Wizard
pages that need a real integration (booking, newsletter, editorial)
stay warning-only with specific reason strings so operators can tell
them apart from "scaffold has no such surface".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _minimal_dossier() -> dict:
    return {
        "siteId": "wizard-route-test",
        "company": {
            "name": "Wizard AB",
            "businessType": "electrician",
            "tagline": "Lokal elektriker i Malmö",
            "story": "Wizard AB är en lokal elektrikerfirma i Malmö.",
            "team": [
                {"name": "Test Person", "role": "Elektriker"},
                {"name": "Andra Personen", "role": "Projektledare"},
            ],
        },
        "location": {
            "city": "Malmö",
            "country": "Sverige",
            "serviceAreas": ["Malmö", "Lund"],
        },
        "services": [
            {"id": "interior-wiring", "label": "Elinstallation", "summary": "Säkra elinstallationer i hemmet."},
            {"id": "service-call", "label": "Servicebesök", "summary": "Felsökning och åtgärd."},
        ],
        "trustSignals": ["Auktoriserade installatörer"],
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "hej@wizard.se",
            "addressLines": ["Storgatan 1", "211 11 Malmö"],
            "openingHours": "Mån-Fre 8-17",
        },
    }


LSB_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "services", "path": "/tjanster", "required": True, "purpose": "Services"},
        {"id": "about", "path": "/om-oss", "required": False, "purpose": "About"},
        {"id": "contact", "path": "/kontakt", "required": True, "purpose": "Contact"},
    ]
}


# ---------------------------------------------------------------------------
# plan.py: _wizard_extra_routes helper
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_wizard_extra_routes_returns_supported_routes_for_lsb() -> None:
    from packages.generation.planning.plan import _wizard_extra_routes

    extras = _wizard_extra_routes(
        "local-service-business",
        ["FAQ", "Bildgalleri", "Vårt team", "Priser och paket", "Portfolio / Case", "Karta / Hitta hit"],
        scaffold_default_paths={"/", "/tjanster", "/om-oss", "/kontakt"},
    )

    assert [route["id"] for route in extras] == [
        "faq", "gallery", "team", "pricing", "portfolio", "map",
    ]
    assert [route["path"] for route in extras] == [
        "/faq", "/galleri", "/team", "/priser", "/portfolio", "/karta",
    ]
    for route in extras:
        assert isinstance(route.get("purpose"), str) and route["purpose"]


@pytest.mark.tooling
def test_wizard_extra_routes_skips_unsupported_pages() -> None:
    from packages.generation.planning.plan import _wizard_extra_routes

    extras = _wizard_extra_routes(
        "local-service-business",
        ["Bokning online", "Nyhetsbrev", "Blogg / Nyheter", "Okänt val"],
        scaffold_default_paths={"/", "/kontakt"},
    )

    assert extras == []


@pytest.mark.tooling
def test_wizard_extra_routes_returns_empty_for_unsupported_scaffold() -> None:
    from packages.generation.planning.plan import _wizard_extra_routes

    extras = _wizard_extra_routes(
        "ecommerce-lite",
        ["FAQ", "Bildgalleri"],
        scaffold_default_paths={"/", "/produkter", "/kontakt"},
    )

    assert extras == []


@pytest.mark.tooling
def test_wizard_extra_routes_dedupes_against_scaffold_defaults() -> None:
    """A scaffold that already declares ``/faq`` wins; the wizard
    helper does not duplicate the path on routePlan.
    """
    from packages.generation.planning.plan import _wizard_extra_routes

    extras = _wizard_extra_routes(
        "local-service-business",
        ["FAQ", "Bildgalleri"],
        scaffold_default_paths={"/", "/faq", "/kontakt"},
    )

    assert [route["id"] for route in extras] == ["gallery"]


# ---------------------------------------------------------------------------
# build_site.py: _extract_wizard_extra_routes helper
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_extract_wizard_extra_routes_reads_site_plan_routeplan() -> None:
    from scripts.build_site import _extract_wizard_extra_routes

    site_plan = {
        "routePlan": [
            {"id": "home", "path": "/", "purpose": "x"},
            {"id": "services", "path": "/tjanster", "purpose": "x"},
            {"id": "about", "path": "/om-oss", "purpose": "x"},
            {"id": "contact", "path": "/kontakt", "purpose": "x"},
            {"id": "faq", "path": "/faq", "purpose": "x"},
            {"id": "gallery", "path": "/galleri", "purpose": "x"},
        ]
    }
    extras = _extract_wizard_extra_routes(site_plan, LSB_ROUTES)

    assert extras == [
        {"id": "faq", "path": "/faq"},
        {"id": "gallery", "path": "/galleri"},
    ]


@pytest.mark.tooling
def test_extract_wizard_extra_routes_ignores_unknown_ids() -> None:
    """A future routePlan entry with an id the builder does not know
    must not crash here — write_pages will surface that case as its
    own SystemExit at dispatch time when it actually happens.
    """
    from scripts.build_site import _extract_wizard_extra_routes

    site_plan = {
        "routePlan": [
            {"id": "home", "path": "/", "purpose": "x"},
            {"id": "contact", "path": "/kontakt", "purpose": "x"},
            {"id": "future-thing", "path": "/future", "purpose": "x"},
        ]
    }
    assert _extract_wizard_extra_routes(site_plan, LSB_ROUTES) == []


# ---------------------------------------------------------------------------
# Render helpers: shape contract for each wizard route
# ---------------------------------------------------------------------------


def _route_href_attr(path: str) -> str:
    from scripts.build_site import _route_href
    return f"href={_route_href(path)}"


@pytest.mark.tooling
def test_render_faq_emits_default_export_and_questions() -> None:
    from scripts.build_site import _DEFAULT_EXPORT_RE, render_faq

    output = render_faq(_minimal_dossier())
    assert _DEFAULT_EXPORT_RE.search(output) is not None
    assert "Vanliga frågor" in output
    assert '{"Hur snabbt får jag svar?"}' in output
    assert '{"Vilka områden täcker ni?"}' in output
    # Opening-hours-derived question fires when contact.openingHours
    # is set on the dossier.
    assert '{"När har ni öppet?"}' in output
    assert "Mån-Fre 8-17" in output


@pytest.mark.tooling
def test_render_faq_threads_contact_path() -> None:
    from scripts.build_site import render_faq

    output = render_faq(_minimal_dossier(), contact_path="/kontakta-oss")
    assert _route_href_attr("/kontakta-oss") in output
    assert _route_href_attr("/kontakt") not in output


@pytest.mark.tooling
def test_render_gallery_falls_back_when_no_images() -> None:
    from scripts.build_site import _DEFAULT_EXPORT_RE, render_gallery

    output = render_gallery(_minimal_dossier())
    assert _DEFAULT_EXPORT_RE.search(output) is not None
    assert "Bilder från våra senaste uppdrag" in output
    # Honest fallback: do not invent stock images.
    assert "<img" not in output


@pytest.mark.tooling
def test_render_gallery_renders_uploaded_images() -> None:
    from scripts.build_site import render_gallery

    dossier = _minimal_dossier()
    dossier["gallery"] = [
        {"assetId": "a1", "filename": "case-1.webp", "alt": "Inomhusmålning Stockholm"},
        {"assetId": "a2", "filename": "case-2.webp", "alt": "Fasadmålning Solna"},
    ]
    output = render_gallery(dossier)
    assert "/uploads/case-1.webp" in output
    assert "/uploads/case-2.webp" in output
    assert '"Inomhusmålning Stockholm"' in output


@pytest.mark.tooling
def test_render_team_uses_member_initials_and_falls_back_when_empty() -> None:
    from scripts.build_site import render_team

    output = render_team(_minimal_dossier())
    assert "Test Person" in output
    assert "Andra Personen" in output

    empty = _minimal_dossier()
    empty["company"]["team"] = []
    fallback = render_team(empty)
    assert "Test Person" not in fallback
    assert "Vi presenterar teamet här" in fallback


@pytest.mark.tooling
def test_render_pricing_uses_pris_efter_offert_for_each_service() -> None:
    from scripts.build_site import render_pricing

    output = render_pricing(_minimal_dossier())
    # No invented price points: every service falls back to the
    # offert-CTA copy.
    assert output.count("Pris efter offert") == 2
    assert '{"Elinstallation"}' in output
    assert '{"Servicebesök"}' in output


@pytest.mark.tooling
def test_render_portfolio_combines_gallery_and_services() -> None:
    from scripts.build_site import render_portfolio

    dossier = _minimal_dossier()
    dossier["gallery"] = [
        {"assetId": "a1", "filename": "case-1.webp", "alt": "Renovering villa"},
    ]
    output = render_portfolio(dossier)
    assert "/uploads/case-1.webp" in output
    assert '{"Renovering villa"}' in output
    assert '{"Elinstallation"}' in output


@pytest.mark.tooling
def test_render_map_emits_google_maps_link_when_address_available() -> None:
    from scripts.build_site import render_map

    output = render_map(_minimal_dossier())
    assert "Storgatan 1" in output
    assert "Malm" in output  # service-area / city
    assert "https://www.google.com/maps/search/?api=1&query=" in output
    # The href is wrapped in _js_string_literal which double-quotes the
    # value, but the literal URL must still be findable as a substring.
    assert "Storgatan%201" in output


# ---------------------------------------------------------------------------
# write_pages: dispatch contract for extra_routes
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_write_pages_dispatches_extra_routes_to_renderers(tmp_path: Path) -> None:
    from scripts.build_site import write_pages

    extras = [
        {"id": "faq", "path": "/faq"},
        {"id": "gallery", "path": "/galleri"},
        {"id": "team", "path": "/team"},
        {"id": "pricing", "path": "/priser"},
        {"id": "portfolio", "path": "/portfolio"},
        {"id": "map", "path": "/karta"},
    ]
    written = write_pages(tmp_path, _minimal_dossier(), LSB_ROUTES, [], extra_routes=extras)

    assert written == [
        "/", "/tjanster", "/om-oss", "/kontakt",
        "/faq", "/galleri", "/team", "/priser", "/portfolio", "/karta",
    ]
    for relative in (
        "faq/page.tsx",
        "galleri/page.tsx",
        "team/page.tsx",
        "priser/page.tsx",
        "portfolio/page.tsx",
        "karta/page.tsx",
    ):
        assert (tmp_path / "app" / relative).exists(), (
            f"Expected app/{relative} to exist after write_pages with extras"
        )


@pytest.mark.tooling
def test_write_pages_extra_route_with_unknown_id_raises(tmp_path: Path) -> None:
    from scripts.build_site import write_pages

    with pytest.raises(SystemExit, match="wizard extra route"):
        write_pages(
            tmp_path,
            _minimal_dossier(),
            LSB_ROUTES,
            [],
            extra_routes=[{"id": "doesnt-exist", "path": "/x"}],
        )


@pytest.mark.tooling
def test_write_pages_extra_routes_do_not_duplicate_scaffold_paths(
    tmp_path: Path,
) -> None:
    """If routePlan accidentally repeats a scaffold default path under a
    wizard id (defensive case), write_pages must skip the duplicate
    rather than write the same file twice.
    """
    from scripts.build_site import write_pages

    extras = [{"id": "faq", "path": "/"}]
    written = write_pages(tmp_path, _minimal_dossier(), LSB_ROUTES, [], extra_routes=extras)
    assert written == ["/", "/tjanster", "/om-oss", "/kontakt"]


@pytest.mark.tooling
def test_nav_items_from_scaffold_includes_extra_routes_before_contact() -> None:
    """Wizard extras land in the nav between the scaffold body and the
    contact entry so visitors find them naturally before the contact
    CTA at the end of the menu.
    """
    from scripts.build_site import _nav_items_from_scaffold

    extras = [
        {"id": "faq", "path": "/faq"},
        {"id": "gallery", "path": "/galleri"},
    ]
    items = _nav_items_from_scaffold(LSB_ROUTES["defaultRoutes"], [], extras)
    assert items == [
        ("/", "Hem"),
        ("/tjanster", "Tjänster"),
        ("/om-oss", "Om oss"),
        ("/faq", "Vanliga frågor"),
        ("/galleri", "Galleri"),
        ("/kontakt", "Kontakt"),
    ]


@pytest.mark.tooling
def test_nav_items_dedupe_extra_routes_against_scaffold() -> None:
    from scripts.build_site import _nav_items_from_scaffold

    extras = [{"id": "about", "path": "/om-oss"}]
    items = _nav_items_from_scaffold(LSB_ROUTES["defaultRoutes"], [], extras)
    # /om-oss already in scaffold; nav must not list it twice.
    om_oss_entries = [entry for entry in items if entry[0] == "/om-oss"]
    assert len(om_oss_entries) == 1


# ---------------------------------------------------------------------------
# B148 — _nav_items_from_scaffold must place wizard extras before the
# contact route's actual path, not before the hardcoded "/kontakt".
# Scaffolds like restaurant-hospitality use "/hitta-hit" for the contact id.
# ---------------------------------------------------------------------------


RESTAURANT_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "menu", "path": "/meny", "required": True, "purpose": "Menu"},
        {"id": "booking", "path": "/bokning", "required": True, "purpose": "Booking"},
        {"id": "about", "path": "/om-oss", "required": False, "purpose": "About"},
        {"id": "contact", "path": "/hitta-hit", "required": True, "purpose": "Contact"},
    ]
}


@pytest.mark.tooling
def test_b148_nav_inserts_extras_before_non_default_contact_path() -> None:
    """B148: restaurant-hospitality's contact route is /hitta-hit, not
    /kontakt. Wizard extras (FAQ, team, karta) must still land *before*
    the contact entry in the nav, not appended to the end.

    Before the fix, the contact insertion-anchor was hardcoded to
    ``"/kontakt"``, which made the lookup return ``None`` for
    restaurant-hospitality and caused wizard extras to be appended after
    the contact entry — exactly the kind of nav-ordering brist that
    showed up in the Golden Path eval's ``dominantProblem=contact``
    signal.
    """
    from scripts.build_site import _nav_items_from_scaffold

    extras = [
        {"id": "faq", "path": "/faq"},
        {"id": "gallery", "path": "/galleri"},
    ]
    items = _nav_items_from_scaffold(RESTAURANT_ROUTES["defaultRoutes"], [], extras)
    # Labels come from _NAV_LABEL_BY_ROUTE_ID: booking → "Boka bord",
    # contact → "Kontakt" (the contact-id label, regardless of path).
    assert items == [
        ("/", "Hem"),
        ("/meny", "Meny"),
        ("/bokning", "Boka bord"),
        ("/om-oss", "Om oss"),
        ("/faq", "Vanliga frågor"),
        ("/galleri", "Galleri"),
        ("/hitta-hit", "Kontakt"),
    ]


@pytest.mark.tooling
def test_b148_nav_appends_extras_when_scaffold_lacks_contact_route() -> None:
    """B148 defensive: a (future) scaffold without a contact id at all
    must not crash nav-building. Wizard extras simply append to the end,
    matching the pre-fix fallback behaviour for the no-anchor case.
    """
    from scripts.build_site import _nav_items_from_scaffold

    no_contact_routes = [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "about", "path": "/om-oss", "required": False, "purpose": "About"},
    ]
    extras = [{"id": "faq", "path": "/faq"}]
    items = _nav_items_from_scaffold(no_contact_routes, [], extras)
    # No contact route → extras append to the tail (same as before B148).
    assert items == [
        ("/", "Hem"),
        ("/om-oss", "Om oss"),
        ("/faq", "Vanliga frågor"),
    ]


@pytest.mark.tooling
def test_b148_nav_preserves_local_service_business_behavior() -> None:
    """B148 compat: local-service-business still places extras before
    /kontakt — the pre-fix behavior for the most common scaffold must
    stay byte-stable so no existing nav rendering regresses.
    """
    from scripts.build_site import _nav_items_from_scaffold

    extras = [{"id": "team", "path": "/team"}]
    items = _nav_items_from_scaffold(LSB_ROUTES["defaultRoutes"], [], extras)
    assert items == [
        ("/", "Hem"),
        ("/tjanster", "Tjänster"),
        ("/om-oss", "Om oss"),
        ("/team", "Team"),
        ("/kontakt", "Kontakt"),
    ]


@pytest.mark.tooling
def test_render_layout_with_extra_routes_writes_nav_labels() -> None:
    from scripts.build_site import render_layout

    extras = [{"id": "faq", "path": "/faq"}, {"id": "team", "path": "/team"}]
    output = render_layout(
        _minimal_dossier(),
        dossier_routes=[],
        scaffold_default_routes=LSB_ROUTES["defaultRoutes"],
        extra_routes=extras,
    )
    assert '{"Vanliga frågor"}' in output
    assert '{"Team"}' in output
    assert _route_href_attr("/faq") in output
    assert _route_href_attr("/team") in output


# ---------------------------------------------------------------------------
# Route/Nav Mutation V1 (ADR 0060): directives.disabledRoutes filter
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_disabled_route_ids_read_from_directives() -> None:
    from scripts.build_site import _disabled_route_ids_from_dossier

    assert _disabled_route_ids_from_dossier(
        {"directives": {"disabledRoutes": ["about", "  ", "about"]}}
    ) == {"about"}
    # Missing/malformed directive -> empty set (never drops a route by accident).
    assert _disabled_route_ids_from_dossier({}) == set()
    assert _disabled_route_ids_from_dossier({"directives": {}}) == set()
    assert _disabled_route_ids_from_dossier(
        {"directives": {"disabledRoutes": "about"}}
    ) == set()


@pytest.mark.tooling
def test_filter_disabled_routes_drops_non_required_keeps_required() -> None:
    from scripts.build_site import _filter_disabled_routes

    # about (non-required) is dropped.
    filtered = _filter_disabled_routes(LSB_ROUTES, {"about"})
    assert [r["id"] for r in filtered["defaultRoutes"]] == [
        "home", "services", "contact",
    ]
    # contact (required) is NEVER dropped here (defense-in-depth, Slice A).
    kept = _filter_disabled_routes(LSB_ROUTES, {"contact"})
    assert [r["id"] for r in kept["defaultRoutes"]] == [
        "home", "services", "about", "contact",
    ]
    # No disabled ids -> returns the input object unchanged (byte-identical path).
    assert _filter_disabled_routes(LSB_ROUTES, set()) is LSB_ROUTES


@pytest.mark.tooling
def test_disabled_route_is_not_written_and_drops_from_nav(tmp_path: Path) -> None:
    """With about disabled, build's activeRoutes seam means write_pages never
    emits /om-oss and the nav drops the "Om oss" link (ADR 0060)."""
    from scripts.build_site import (
        _filter_disabled_routes,
        _nav_items_from_scaffold,
        write_pages,
    )

    active = _filter_disabled_routes(LSB_ROUTES, {"about"})
    written = write_pages(tmp_path, _minimal_dossier(), active, [])
    assert written == ["/", "/tjanster", "/kontakt"]
    assert not (tmp_path / "app" / "om-oss" / "page.tsx").exists()

    items = _nav_items_from_scaffold(active["defaultRoutes"], [])
    assert ("/om-oss", "Om oss") not in items
    assert [href for href, _ in items] == ["/", "/tjanster", "/kontakt"]


@pytest.mark.tooling
def test_disabled_route_removes_nav_link_in_layout(tmp_path: Path) -> None:
    from scripts.build_site import _filter_disabled_routes, render_layout

    active = _filter_disabled_routes(LSB_ROUTES, {"about"})
    output = render_layout(
        _minimal_dossier(),
        dossier_routes=[],
        scaffold_default_routes=active["defaultRoutes"],
    )
    assert "Om oss" not in output
    assert _route_href_attr("/om-oss") not in output
