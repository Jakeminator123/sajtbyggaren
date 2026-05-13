"""Regression tests for B13 scaffold-driven route emission.

Before B13 ``scripts/build_site.py`` was hardcoded against
``local-service-business`` routes (``/tjanster``, ``/om-oss``,
``/kontakt``) which blocked activation of the
``ecommerce-lite -> commerce-base`` mapping: a Project Input pinned at
``ecommerce-lite`` produced a degraded Quality Gate result because
``/produkter`` was never written (see ``docs/known-issues.md`` B13 +
B20).

These tests lock the new contract:

* ``write_pages`` reads the scaffold's ``routes.json`` and dispatches to
  a renderer per route id.
* ``_nav_items_from_scaffold`` derives nav from the scaffold paths +
  Swedish labels lookup.
* ``_pick_listing_route`` returns the right route so ``render_home``
  cross-links at ``/produkter`` for ecommerce-lite and ``/tjanster``
  for local-service-business.
* ``render_products`` emits a valid TSX page with the products grid
  and a default export.
* Building the ``atelje-bird`` (ecommerce-lite) fixture end-to-end with
  ``--skip-build`` writes ``/produkter`` and produces Quality Gate
  ``status=ok`` with the route-scan check green.

If a future refactor drops scaffold awareness, these tests fail loudly
so the regression cannot land silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


LSB_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "services", "path": "/tjanster", "required": True, "purpose": "Services"},
        {"id": "about", "path": "/om-oss", "required": False, "purpose": "About"},
        {"id": "contact", "path": "/kontakt", "required": True, "purpose": "Contact"},
    ]
}

ECOMMERCE_ROUTES = {
    "defaultRoutes": [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "products", "path": "/produkter", "required": True, "purpose": "Products"},
        {"id": "about", "path": "/om-oss", "required": False, "purpose": "About"},
        {"id": "contact", "path": "/kontakt", "required": True, "purpose": "Contact"},
    ]
}


def _minimal_dossier() -> dict:
    return {
        "siteId": "test-site",
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
            {"id": "interior-painting", "label": "Inomhusmålning", "summary": "Tak och väggar."},
            {"id": "exterior-painting", "label": "Fasadmålning", "summary": "Fasader."},
        ],
        "trustSignals": ["Tio år i branschen"],
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "hej@test.se",
            "addressLines": ["Storgatan 1", "111 11 Stockholm"],
            "openingHours": "Mån-Fre 9-17",
        },
    }


# ---------------------------------------------------------------------------
# Nav + listing-route helpers
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_nav_label_for_known_route_id_uses_lookup() -> None:
    from scripts.build_site import _nav_label_for_route

    assert _nav_label_for_route("home") == "Hem"
    assert _nav_label_for_route("services") == "Tjänster"
    assert _nav_label_for_route("products") == "Produkter"
    assert _nav_label_for_route("about") == "Om oss"
    assert _nav_label_for_route("contact") == "Kontakt"


@pytest.mark.tooling
def test_nav_label_for_unknown_route_id_falls_back_to_title_case() -> None:
    """An unregistered scaffold route id must still produce a readable
    label so a new scaffold cannot silently surface a blank nav entry.
    """
    from scripts.build_site import _nav_label_for_route

    assert _nav_label_for_route("look-book") == "Look Book"
    assert _nav_label_for_route("service_area") == "Service Area"


@pytest.mark.tooling
def test_nav_items_from_scaffold_uses_scaffold_paths() -> None:
    """B13 core: nav is driven by the scaffold's defaultRoutes, not by
    a hardcoded list in build_site.py.
    """
    from scripts.build_site import _nav_items_from_scaffold

    items = _nav_items_from_scaffold(LSB_ROUTES["defaultRoutes"], [])
    assert items == [
        ("/", "Hem"),
        ("/tjanster", "Tjänster"),
        ("/om-oss", "Om oss"),
        ("/kontakt", "Kontakt"),
    ]

    items = _nav_items_from_scaffold(ECOMMERCE_ROUTES["defaultRoutes"], [])
    assert items == [
        ("/", "Hem"),
        ("/produkter", "Produkter"),
        ("/om-oss", "Om oss"),
        ("/kontakt", "Kontakt"),
    ]


@pytest.mark.tooling
def test_nav_items_includes_dossier_route_when_present() -> None:
    """interactive-game-loop's /spel must still surface in the nav so the
    Pacman teaser does not vanish under the new scaffold-driven nav.
    """
    from scripts.build_site import _nav_items_from_scaffold

    items = _nav_items_from_scaffold(LSB_ROUTES["defaultRoutes"], ["/spel"])
    assert ("/spel", "Spel") in items
    items_no_dossier = _nav_items_from_scaffold(LSB_ROUTES["defaultRoutes"], [])
    assert ("/spel", "Spel") not in items_no_dossier


@pytest.mark.tooling
def test_pick_listing_route_prefers_services_then_products() -> None:
    from scripts.build_site import _pick_listing_route

    assert _pick_listing_route(LSB_ROUTES["defaultRoutes"]) == {
        "id": "services",
        "path": "/tjanster",
        "required": True,
        "purpose": "Services",
    }
    assert _pick_listing_route(ECOMMERCE_ROUTES["defaultRoutes"]) == {
        "id": "products",
        "path": "/produkter",
        "required": True,
        "purpose": "Products",
    }


@pytest.mark.tooling
def test_pick_listing_route_returns_none_when_neither_present() -> None:
    """A scaffold that declares neither services nor products must not
    cause render_home to crash: it just drops the listing cross-link.
    """
    from scripts.build_site import _pick_listing_route

    routes = [
        {"id": "home", "path": "/"},
        {"id": "contact", "path": "/kontakt"},
    ]
    assert _pick_listing_route(routes) is None


# ---------------------------------------------------------------------------
# render_home: listing-route awareness
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_render_home_links_to_products_for_ecommerce_lite() -> None:
    from scripts.build_site import render_home

    listing = {"id": "products", "path": "/produkter"}
    output = render_home(_minimal_dossier(), dossier_routes=[], listing_route=listing)

    assert 'href="/produkter"' in output
    assert "Se alla produkter" in output
    assert "Produkter" in output
    # The hardcoded local-service-business CTA copy must be gone.
    assert 'href="/tjanster"' not in output
    assert "Se alla tjänster" not in output


@pytest.mark.tooling
def test_render_home_links_to_services_for_local_service_business() -> None:
    """Regression: the default local-service-business flow must keep
    the same CTA copy as before B13 so the existing painter-palma
    smoke tests still see /tjanster on the home page.
    """
    from scripts.build_site import render_home

    listing = {"id": "services", "path": "/tjanster"}
    output = render_home(_minimal_dossier(), dossier_routes=[], listing_route=listing)

    assert 'href="/tjanster"' in output
    assert "Se alla tjänster" in output
    assert "Se alla produkter" not in output


# ---------------------------------------------------------------------------
# render_products: shape contract
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_render_products_emits_default_export_and_product_items() -> None:
    """render_products must produce a Next.js page with a default
    export and one article per service item in the Project Input.
    """
    from scripts.build_site import _DEFAULT_EXPORT_RE, render_products

    dossier = _minimal_dossier()
    output = render_products(dossier)

    assert _DEFAULT_EXPORT_RE.search(output) is not None, (
        "render_products must emit `export default function ProductsPage` "
        "so Next can mount /produkter."
    )
    # One article per product (= service entry in Project Input).
    for product in dossier["services"]:
        assert f'{{"{product["label"]}"}}' in output, (
            f"render_products must render product label {product['label']!r} "
            "via _jsx_safe_string."
        )
        assert f'{{"{product["summary"]}"}}' in output


@pytest.mark.tooling
def test_render_products_uses_jsx_safe_string_for_customer_text() -> None:
    """B30 parity for the new renderer: customer-supplied text must go
    through _jsx_safe_string so JSX-special characters cannot break the
    build.
    """
    from scripts.build_site import render_products

    dossier = _minimal_dossier()
    dossier["services"] = [
        {"id": "weird", "label": "<Mug> {curly}", "summary": "Less < than 20"},
    ]
    output = render_products(dossier)

    assert '{"<Mug> {curly}"}' in output
    assert '{"Less < than 20"}' in output
    # Raw < right after a > would indicate the helper was bypassed.
    assert "><Mug>" not in output


# ---------------------------------------------------------------------------
# write_pages: scaffold-driven dispatch
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_write_pages_emits_local_service_business_routes(tmp_path: Path) -> None:
    """Regression: the existing 4-page LSB flow must keep working
    exactly as before B13.
    """
    from scripts.build_site import write_pages

    written = write_pages(tmp_path, _minimal_dossier(), LSB_ROUTES, [])

    assert written == ["/", "/tjanster", "/om-oss", "/kontakt"]
    for relative in ("page.tsx", "tjanster/page.tsx", "om-oss/page.tsx",
                     "kontakt/page.tsx", "layout.tsx"):
        assert (tmp_path / "app" / relative).exists(), (
            f"Expected app/{relative} to exist after write_pages."
        )
    # The legacy hardcoded /produkter must NOT appear for LSB.
    assert not (tmp_path / "app" / "produkter" / "page.tsx").exists()


@pytest.mark.tooling
def test_write_pages_emits_ecommerce_lite_routes(tmp_path: Path) -> None:
    """B13 core: ecommerce-lite scaffold must produce /produkter, not
    /tjanster. This was the route-scan failure that blocked B20 step 2.
    """
    from scripts.build_site import write_pages

    written = write_pages(tmp_path, _minimal_dossier(), ECOMMERCE_ROUTES, [])

    assert written == ["/", "/produkter", "/om-oss", "/kontakt"]
    assert (tmp_path / "app" / "produkter" / "page.tsx").exists()
    # /tjanster is NOT in ecommerce-lite's routes - must not be emitted.
    assert not (tmp_path / "app" / "tjanster" / "page.tsx").exists()
    # Layout is always written + must have the ecommerce-lite nav (Produkter).
    layout = (tmp_path / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "Produkter" in layout
    assert 'href="/produkter"' in layout
    assert "Tjänster" not in layout
    assert 'href="/tjanster"' not in layout


@pytest.mark.tooling
def test_write_pages_unknown_route_id_raises(tmp_path: Path) -> None:
    """A scaffold that lists a route id with no registered renderer must
    surface the error at write time, not silently produce a missing
    route that Quality Gate later reports without an owner.
    """
    from scripts.build_site import write_pages

    bogus = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "lookbook", "path": "/lookbook", "required": True, "purpose": "Lookbook"},
        ]
    }
    with pytest.raises(SystemExit) as exc:
        write_pages(tmp_path, _minimal_dossier(), bogus, [])
    assert "lookbook" in str(exc.value)
    assert "renderer" in str(exc.value)


# ---------------------------------------------------------------------------
# End-to-end smoke for the ecommerce-lite fixture
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_ecommerce_lite_fixture_writes_produkter_and_passes_route_scan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B13 end-to-end: building the atelje-bird (ecommerce-lite) fixture
    with --skip-build must write /produkter and produce a green
    Quality Gate route-scan check. Before B13 the same input made
    route-scan fail with ``/produkter (saknas)`` which kept
    SCAFFOLD_TO_STARTER pinned at marketing-base.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = (
        REPO_ROOT / "examples" / "atelje-bird.project-input.json"
    )
    assert project_input_path.exists()

    target, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)

    # /produkter exists, /tjanster does not.
    assert (target / "app" / "produkter" / "page.tsx").exists()
    assert not (target / "app" / "tjanster" / "page.tsx").exists()

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    assert build_result["scaffoldId"] == "ecommerce-lite"
    assert "/produkter" in build_result["routes"]
    assert "/tjanster" not in build_result["routes"]

    quality = json.loads(
        (run_dir / "quality-result.json").read_text(encoding="utf-8")
    )
    by_name = {check["name"]: check for check in quality["checks"]}
    assert by_name["route-scan"]["status"] == "ok", (
        "ecommerce-lite route-scan must pass after B13 - missing "
        f"findings: {by_name['route-scan'].get('findings')}"
    )
    assert quality["status"] == "ok"



# ---------------------------------------------------------------------------
# Bugbot fyndet: "Writing pages: ..." print must run BEFORE write_pages.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_writing_pages_announcement_runs_before_write_pages() -> None:
    """Source-level lock for the Bugbot fix on PR #19.

    The announcement print must precede the ``write_pages(`` call so the
    operator sees which step is in flight if ``write_pages`` raises
    SystemExit (e.g. unknown scaffold route id). Locking the order via
    source inspection rather than capsys because the announcement is UX
    glue, not testable runtime state.
    """
    import inspect

    from scripts import build_site

    body = inspect.getsource(build_site.build)
    print_idx = body.find('"Writing pages: "')
    write_call_idx = body.find("write_pages(\n        target, dossier")
    assert print_idx > 0 and write_call_idx > 0, (
        "Both the 'Writing pages: ' print and the write_pages(target, dossier, ...) "
        "call must appear in build(). If you renamed either, update this test."
    )
    assert print_idx < write_call_idx, (
        "The 'Writing pages: ' print must run BEFORE write_pages() so the "
        "operator sees which step is in flight if write_pages raises "
        "SystemExit. Bugbot caught this on PR #19; do not move the print "
        "back below the call."
    )


@pytest.mark.tooling
def test_build_verifies_write_pages_return_matches_announced_routes() -> None:
    """Companion lock for the Bugbot fix: the announcement is honest only
    if build() verifies that write_pages returned the same paths it
    announced. Without the check a silent dispatch drift (renderer added
    but path mismatched) would print the wrong list with no traceback.
    """
    import inspect

    from scripts import build_site

    body = inspect.getsource(build_site.build)
    assert "if paths_written != routes_to_write" in body, (
        "build() must compare write_pages' return value against the "
        "list announced by the print above. Dropping the check lets "
        "the print say one thing while write_pages emits another."
    )
