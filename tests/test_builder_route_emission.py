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

import inspect
import json
import sys
from pathlib import Path

import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

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


def _route_href_attr(path: str) -> str:
    from scripts.build_site import _route_href

    return f"href={_route_href(path)}"


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
def test_route_href_serializes_scaffold_path_as_jsx_expression() -> None:
    """B50: scaffold route paths must not be raw-interpolated into href."""
    from scripts.build_site import _route_href

    tricky = '/kontakt" onClick={alert(1)}'

    assert _route_href("/kontakt") == '{"/kontakt"}'
    assert _route_href(tricky) == '{"/kontakt\\" onClick={alert(1)}"}'


@pytest.mark.tooling
@pytest.mark.parametrize(
    "route_path",
    [
        "kontakt",
        "//example.com",
        "/../secret",
        "/foo/../bar",
        "/foo//bar",
        "/foo/.",
        "/foo\\bar",
        "/foo?x=1",
        "/foo#section",
    ],
)
def test_route_href_rejects_non_canonical_paths(route_path: str) -> None:
    from scripts.build_site import _route_href

    with pytest.raises(SystemExit, match="scaffold route path"):
        _route_href(route_path)


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
def test_nav_items_dedupes_spel_when_scaffold_also_declares_it() -> None:
    """B52: ``/spel`` can arrive from both ``dossier_routes`` (when the
    interactive-game-loop Dossier is selected) and from a future scaffold
    that adopts the same path in its ``defaultRoutes``. The nav must list
    the route exactly once - duplicated href/label pairs would render two
    visually identical nav links pointing at the same page.
    """
    from scripts.build_site import _nav_items_from_scaffold

    routes_with_spel = [
        {"id": "home", "path": "/"},
        {"id": "spel", "path": "/spel"},
        {"id": "contact", "path": "/kontakt"},
    ]
    items = _nav_items_from_scaffold(routes_with_spel, ["/spel"])
    spel_entries = [entry for entry in items if entry[0] == "/spel"]
    assert len(spel_entries) == 1, (
        f"/spel duplicated in nav: {items!r}. _nav_items_from_scaffold must "
        "dedupe Dossier-injected /spel against scaffold defaultRoutes entries."
    )
    items_without_scaffold_spel = _nav_items_from_scaffold(
        LSB_ROUTES["defaultRoutes"], ["/spel"]
    )
    spel_in_lsb = [entry for entry in items_without_scaffold_spel if entry[0] == "/spel"]
    assert len(spel_in_lsb) == 1, (
        "Dossier-only /spel must still appear exactly once in nav even when "
        "scaffold does not declare the route."
    )


@pytest.mark.tooling
def test_render_layout_jsx_escapes_unknown_nav_label_fallback() -> None:
    """B51: when a scaffold declares a route id that is not in
    ``_NAV_LABEL_BY_ROUTE_ID`` the fallback turns the id into a Title Case
    label via ``str.title()``. That label must still pass through
    ``_jsx_safe_string`` before it is written into TSX, otherwise a future
    scaffold (or governance drift) that lets an unusual id reach the
    renderer would emit raw text into nav. Locked here so the customer-
    text discipline from B30 covers governance-driven text too.
    """
    from scripts.build_site import render_layout

    routes_with_unknown = [
        {"id": "home", "path": "/"},
        {"id": "look-book", "path": "/look-book"},
        {"id": "contact", "path": "/kontakt"},
    ]
    output = render_layout(
        _minimal_dossier(),
        dossier_routes=[],
        scaffold_default_routes=routes_with_unknown,
    )
    assert '{"Look Book"}' in output, (
        "render_layout must wrap nav label fallback in _jsx_safe_string so "
        "{\"Look Book\"} appears as a JSX expression, not raw >Look Book<."
    )
    assert ">Look Book<" not in output, (
        "render_layout leaks raw nav label fallback as JSX text. Wrap label "
        "in _jsx_safe_string (header AND footer nav)."
    )


@pytest.mark.tooling
def test_render_layout_escapes_known_nav_labels_consistently() -> None:
    """B51 follow-on: known labels (Hem, Tjänster, etc.) must also be wrapped
    so the discipline is uniform. Otherwise a reviewer cannot tell from the
    source which labels are trusted and which are not - and a future label
    added to ``_NAV_LABEL_BY_ROUTE_ID`` could silently land unescaped.
    """
    from scripts.build_site import render_layout

    output = render_layout(
        _minimal_dossier(),
        dossier_routes=[],
        scaffold_default_routes=LSB_ROUTES["defaultRoutes"],
    )
    for safe_label in ('{"Hem"}', '{"Tjänster"}', '{"Om oss"}', '{"Kontakt"}'):
        assert safe_label in output, (
            f"render_layout must wrap nav label {safe_label!r} as JSX "
            "expression for consistency with B30 + B51."
        )


@pytest.mark.tooling
@pytest.mark.parametrize("route_path", ["//example.com", "/../secret", "/foo/../bar"])
def test_route_to_page_path_rejects_non_canonical_paths(
    tmp_path: Path,
    route_path: str,
) -> None:
    from scripts.build_site import route_to_page_path

    with pytest.raises(SystemExit, match="scaffold route path"):
        route_to_page_path(tmp_path, route_path)


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

    assert _route_href_attr("/produkter") in output
    assert "Se alla produkter" in output
    assert "Produkter" in output
    # The hardcoded local-service-business CTA copy must be gone.
    assert _route_href_attr("/tjanster") not in output
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

    assert _route_href_attr("/tjanster") in output
    assert "Se alla tjänster" in output
    assert "Se alla produkter" not in output


@pytest.mark.tooling
def test_render_home_omits_listing_cross_link_when_route_missing() -> None:
    """B50/listing contract: do not invent /tjanster for new scaffolds
    that declare neither services nor products.
    """
    from scripts.build_site import render_home

    output = render_home(_minimal_dossier(), dossier_routes=[], listing_route=None)

    assert _route_href_attr("/tjanster") not in output
    assert _route_href_attr("/produkter") not in output
    assert "Se alla tjänster" not in output
    assert "Se alla produkter" not in output


@pytest.mark.tooling
def test_render_home_omits_trust_section_when_trust_signals_empty() -> None:
    """B66: an empty trustSignals list must not render an empty
    "Varför oss" block.

    Prompt-generated Project Inputs currently carry ``trustSignals=[]``.
    Rendering the heading with an empty ``<ul>`` made every demo site
    look unfinished. The section should be omitted until the brief layer
    can supply real trust signals.
    """
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["trustSignals"] = []
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )

    assert "Varför oss" not in output
    assert "trust-0" not in output


@pytest.mark.tooling
def test_render_home_keeps_trust_section_when_trust_signals_present() -> None:
    """B66 positive lock: curated examples with real trust signals keep
    the trust section unchanged.
    """
    from scripts.build_site import render_home

    output = render_home(
        _minimal_dossier(),
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )

    assert "Varför oss" in output
    assert "Tio år i branschen" in output


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1C (B95): hero ortstag is suppressed when the
# location is country-only (``city == country``). The brief sometimes
# returns ``locationHint="Sverige"`` (no city) which used to surface as
# an ortstag on the e-commerce demo prompt.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_render_home_omits_hero_location_tag_when_country_only() -> None:
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["location"] = {
        "city": "Sverige",
        "country": "Sverige",
        "serviceAreas": ["Sverige"],
    }
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )

    assert "<MapPin" not in output.split("</section>", 1)[0], (
        "Country-only location must not render a MapPin ortstag in the "
        "hero section."
    )
    assert '<span>{"Sverige"}</span>' not in output


@pytest.mark.tooling
def test_render_home_keeps_hero_location_tag_when_real_city() -> None:
    """Positive lock: real cities still get the ortstag."""
    from scripts.build_site import render_home

    output = render_home(
        _minimal_dossier(),
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )
    hero = output.split("</section>", 1)[0]
    assert "<MapPin" in hero
    assert '<span>{"Stockholm"}</span>' in hero


@pytest.mark.tooling
def test_render_home_country_only_marker_is_case_insensitive() -> None:
    """B95: the marker should match even when city/country differ in
    casing or surrounding whitespace, so a brief that returns ``"SVERIGE"``
    is still treated as country-only."""
    from scripts.build_site import _location_is_country_only

    assert _location_is_country_only(
        {"city": "Sverige", "country": "Sverige"}
    )
    assert _location_is_country_only(
        {"city": "  sverige ", "country": "Sverige"}
    )
    assert _location_is_country_only(
        {"city": "Sweden", "country": "sweden"}
    )
    assert not _location_is_country_only(
        {"city": "Stockholm", "country": "Sverige"}
    )
    assert not _location_is_country_only({"city": "", "country": "Sverige"})


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1C (B96): hero CTA is scaffold- and conversion-goal
# aware. Before the fix "Begär offert" was hardcoded in render_home and
# render_services regardless of scaffold, which made the e-commerce
# demo case (3.9 / 10 in re-Scout) lose conversion credibility.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hero_cta_label_defaults_to_quote_when_no_signals() -> None:
    from scripts.build_site import _hero_cta_label

    assert _hero_cta_label({}) == "Begär offert"
    assert _hero_cta_label({"language": "en"}) == "Request a quote"


@pytest.mark.tooling
def test_hero_cta_label_uses_shop_verb_for_ecommerce_scaffold() -> None:
    from scripts.build_site import _hero_cta_label

    sv = _hero_cta_label({"language": "sv", "scaffoldId": "ecommerce-lite"})
    en = _hero_cta_label({"language": "en", "scaffoldId": "ecommerce-lite"})
    assert sv == "Shoppa nu"
    assert en == "Shop now"


@pytest.mark.tooling
def test_hero_cta_label_uses_shop_verb_for_purchase_conversion_goal() -> None:
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": ["product_purchase"],
    }
    assert _hero_cta_label(dossier) == "Shoppa nu"


@pytest.mark.tooling
def test_hero_cta_label_uses_booking_verb_for_booking_conversion_goal() -> None:
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": ["booking_request", "call"],
    }
    assert _hero_cta_label(dossier) == "Boka tid"
    en_dossier = {**dossier, "language": "en"}
    assert _hero_cta_label(en_dossier) == "Book a time"


@pytest.mark.tooling
def test_hero_cta_label_shop_beats_booking_in_priority() -> None:
    """Mixed conversion goals: shop intent leads regardless of order."""
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "ecommerce-lite",
        "conversionGoals": ["booking_request", "product_purchase"],
    }
    assert _hero_cta_label(dossier) == "Shoppa nu"


@pytest.mark.tooling
def test_hero_cta_label_uses_booking_business_type_fallback() -> None:
    """B100: short booking prompts may have conversionGoals=[] from briefModel."""
    from scripts.build_site import _hero_cta_label

    for business_type in (
        "hair-salon",
        "naprapat-clinic",
        "naprapath clinic",
        "naprapatklinik",
        "dentist",
    ):
        dossier = {
            "language": "sv",
            "scaffoldId": "local-service-business",
            "conversionGoals": [],
            "company": {"businessType": business_type},
        }
        assert _hero_cta_label(dossier) == "Boka tid"


@pytest.mark.tooling
def test_hero_cta_label_uses_shop_business_type_fallback() -> None:
    """B100: commerce business types should shop even without goals."""
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": [],
        "company": {"businessType": "webshop"},
    }

    assert _hero_cta_label(dossier) == "Shoppa nu"


# ---------------------------------------------------------------------------
# B150 — _normalize_business_type must collapse multi-word business types
# whose head noun is a registered booking/shop slug. briefModel sometimes
# emits "massage studio", "yoga studio", "personal trainer studio"; before
# B150 those compact slugs ("massage-studio") did not match any of the
# CTA-resolver sets, and the hero CTA fell through to "Begär offert"
# instead of "Boka tid" / "Shoppa nu".
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b150_normalize_business_type_collapses_massage_studio() -> None:
    """B150: ``"massage studio"`` → ``"massage"`` so the booking CTA fires.

    Verifies both the space-form and the dash-form normalise to the
    registered ``_BOOKING_BUSINESS_TYPES`` slug.
    """
    from scripts.build_site import _normalize_business_type

    assert _normalize_business_type("massage studio") == "massage"
    assert _normalize_business_type("massage-studio") == "massage"
    assert _normalize_business_type("Massage Studio") == "massage"


@pytest.mark.tooling
def test_b150_normalize_business_type_collapses_compound_booking_slugs() -> None:
    """B150: compound booking-type slugs with non-booking suffix words
    ("studio", "shop", "salong") must collapse to the registered head.
    """
    from scripts.build_site import _normalize_business_type

    # personal-training is a registered booking slug; -studio suffix
    # must not break the match.
    assert _normalize_business_type("personal-training studio") == "personal-training"
    # barber-shop is itself registered, so the direct compact-match wins
    # before the head-prefix fallback fires.
    assert _normalize_business_type("barber-shop") == "barber-shop"
    # Three-word compound: head is "barber" (registered), even though
    # "barber-shop" is also registered — the loop prefers the LONGEST
    # registered prefix, so "barber-shop-studio" → "barber-shop".
    assert _normalize_business_type("barber-shop studio") == "barber-shop"


@pytest.mark.tooling
def test_b150_normalize_business_type_preserves_unknown_compound_unchanged() -> None:
    """B150 defensive: ``_normalize_business_type`` must never invent
    slugs the CTA-resolver does not recognise. An unknown compound
    business type ("yoga studio" — yoga is not registered) passes
    through unchanged.
    """
    from scripts.build_site import _normalize_business_type

    # "yoga" is NOT in _BOOKING_BUSINESS_TYPES or _SHOP_BUSINESS_TYPES,
    # so the head-prefix fallback does not fire and the compact slug
    # remains intact for the caller to handle.
    assert _normalize_business_type("yoga studio") == "yoga-studio"
    assert _normalize_business_type("unknown business kind") == "unknown-business-kind"


@pytest.mark.tooling
def test_b150_hero_cta_label_fires_booking_for_massage_studio() -> None:
    """B150 integration: when briefModel emits ``"massage studio"`` and
    no conversionGoals, the hero CTA falls back through the normalised
    business type into ``"Boka tid"`` instead of generic ``"Begär offert"``.
    """
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": [],
        "company": {"businessType": "massage studio"},
    }
    assert _hero_cta_label(dossier) == "Boka tid"


@pytest.mark.tooling
def test_b150_hero_cta_label_fires_booking_for_dash_form_personal_training_studio() -> None:
    """B150 integration: ``"personal-training-studio"`` → booking CTA via
    the longest-registered-prefix fallback (``"personal-training"`` is
    registered).
    """
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": [],
        "company": {"businessType": "personal-training-studio"},
    }
    assert _hero_cta_label(dossier) == "Boka tid"


@pytest.mark.tooling
def test_b150_naprapat_explicit_mapping_still_wins() -> None:
    """B150 compat: the explicit ``naprapat*`` prefix mapping must keep
    firing before the new generic head-prefix fallback. The old contract
    where every naprapat variant maps to ``"naprapat-clinic"`` stays.
    """
    from scripts.build_site import _normalize_business_type

    for variant in (
        "naprapat",
        "naprapath",
        "naprapatklinik",
        "naprapath-clinic",
        "Naprapat AB",
    ):
        assert _normalize_business_type(variant) == "naprapat-clinic", (
            f"naprapat variant {variant!r} must collapse to 'naprapat-clinic'"
        )


@pytest.mark.tooling
def test_hero_cta_label_explicit_goals_beat_business_type_fallback() -> None:
    """B100: explicit conversionGoals remain the highest priority."""
    from scripts.build_site import _hero_cta_label

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": ["booking_request"],
        "company": {"businessType": "webshop"},
    }

    assert _hero_cta_label(dossier) == "Boka tid"


@pytest.mark.tooling
def test_render_home_emits_scaffold_aware_hero_cta_for_ecommerce() -> None:
    """B96: render_home must surface the shop verb in the hero CTA
    when the Project Input pins ecommerce-lite."""
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "ecommerce-lite"
    dossier["conversionGoals"] = ["product_purchase", "shop_visit"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "products", "path": "/produkter"},
    )

    assert "Shoppa nu" in output
    assert "Begär offert" not in output


@pytest.mark.tooling
def test_render_home_emits_booking_hero_cta_for_booking_business() -> None:
    """B96: a service business with booking_request CTA reads 'Boka tid'
    rather than the generic 'Begär offert' that frisör / naprapatklinik
    used to receive."""
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "local-service-business"
    dossier["conversionGoals"] = ["booking_request"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )

    assert "Boka tid" in output
    assert "Begär offert" not in output


@pytest.mark.tooling
def test_render_home_falls_back_to_quote_cta_for_default_service_business() -> None:
    """B96 positive lock: today's hardcoded "Begär offert" must remain
    the default for service-business projects without booking signals,
    so painter-palma-style demos do not regress."""
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "local-service-business"
    dossier["conversionGoals"] = ["quote_request", "call"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )

    assert "Begär offert" in output
    assert "Shoppa nu" not in output
    assert "Boka tid" not in output


@pytest.mark.tooling
def test_render_services_uses_same_hero_cta_label_as_home() -> None:
    """B96: render_services' bottom CTA must follow the same variant
    helper so the two pages stay aligned."""
    from scripts.build_site import render_services

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "local-service-business"
    dossier["conversionGoals"] = ["booking_request"]
    dossier["language"] = "sv"
    output = render_services(dossier)

    assert "Boka tid" in output
    assert "Begär offert" not in output


# ---------------------------------------------------------------------------
# B101 (Re-Verifierings-Scout 3 2026-05-18): hero CTA href must match the
# CTA label. The pre-fix render_home always linked the primary hero
# button at the scaffold contact route, so a "Shoppa nu" label on the
# e-handel-case pointed at /kontakt instead of /produkter. The new
# helper ``_hero_cta_target_path`` routes shop variants to the products
# listing when one exists, and falls back to contact for every other
# variant or scaffold without a products route.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hero_cta_target_path_routes_shop_variant_to_products() -> None:
    from scripts.build_site import _hero_cta_target_path

    dossier = {
        "language": "sv",
        "scaffoldId": "ecommerce-lite",
        "conversionGoals": ["product_purchase", "shop_visit"],
    }
    listing = {"id": "products", "path": "/produkter"}

    assert (
        _hero_cta_target_path(dossier, listing, "/kontakt") == "/produkter"
    )


@pytest.mark.tooling
def test_hero_cta_target_path_falls_back_to_contact_when_no_products_listing() -> None:
    """A scaffold that signals shop intent but never declares a products
    route must keep the hero CTA pointing at contact - inventing
    ``/produkter`` for a scaffold that has no products page would leave
    the click on a 404.
    """
    from scripts.build_site import _hero_cta_target_path

    dossier = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": ["product_purchase"],
    }
    services_listing = {"id": "services", "path": "/tjanster"}

    assert (
        _hero_cta_target_path(dossier, services_listing, "/kontakt") == "/kontakt"
    )
    assert _hero_cta_target_path(dossier, None, "/kontakt") == "/kontakt"


@pytest.mark.tooling
def test_hero_cta_target_path_keeps_contact_for_booking_and_quote_variants() -> None:
    """Booking and quote variants do not have a "list of bookable slots"
    surface today, so the hero CTA continues to point at the contact
    route the scaffold already wires up.
    """
    from scripts.build_site import _hero_cta_target_path

    booking = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": ["booking_request"],
    }
    quote = {
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": ["quote_request"],
    }
    products_listing = {"id": "products", "path": "/produkter"}

    assert (
        _hero_cta_target_path(booking, products_listing, "/kontakt") == "/kontakt"
    )
    assert (
        _hero_cta_target_path(quote, products_listing, "/kontakt") == "/kontakt"
    )


@pytest.mark.tooling
def test_render_home_hero_cta_links_to_products_when_shop_variant() -> None:
    """B101: the primary hero CTA href on an e-commerce build must point
    at /produkter, matching the "Shoppa nu" label, not the scaffold
    contact route.
    """
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "ecommerce-lite"
    dossier["conversionGoals"] = ["product_purchase", "shop_visit"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "products", "path": "/produkter"},
    )

    hero_section = output.split("</section>", 1)[0]
    assert "Shoppa nu" in hero_section
    primary_cta_href = _route_href_attr("/produkter")
    assert primary_cta_href in hero_section, (
        "B101: hero-CTA 'Shoppa nu' måste länka till /produkter, "
        "inte /kontakt."
    )
    # Bottom-of-page "Kontakta oss" CTA is allowed to keep contact_href.
    assert _route_href_attr("/kontakt") in output, (
        "Bottom 'Kontakta oss' CTA på home must continue pointing at "
        "the scaffold contact route - only the hero primary CTA changes."
    )


@pytest.mark.tooling
def test_render_home_hero_cta_links_to_contact_when_booking_variant() -> None:
    """B101 positive lock: bokningsdrivna service-businesses (frisör,
    naprapat) ska fortfarande gå till kontakt-routen från hero, så
    "Boka tid" landar på rätt yta för verksamheter utan online-bokning.
    """
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "local-service-business"
    dossier["conversionGoals"] = ["booking_request"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
    )

    hero_section = output.split("</section>", 1)[0]
    assert "Boka tid" in hero_section
    assert _route_href_attr("/kontakt") in hero_section
    assert _route_href_attr("/produkter") not in output


@pytest.mark.tooling
def test_render_home_hero_cta_uses_threaded_contact_path_for_quote_variant() -> None:
    """B45 + B101: when no products route is declared but the scaffold
    moves contact to /kontakta-oss, the quote-variant hero CTA must
    follow the threaded contact_path, not regress to a hardcoded
    /kontakt.
    """
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "local-service-business"
    dossier["conversionGoals"] = ["quote_request"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "services", "path": "/tjanster"},
        contact_path="/kontakta-oss",
    )

    hero_section = output.split("</section>", 1)[0]
    assert "Begär offert" in hero_section
    assert _route_href_attr("/kontakta-oss") in hero_section
    assert _route_href_attr("/kontakt") not in output


@pytest.mark.tooling
def test_render_home_hero_cta_links_to_threaded_products_path() -> None:
    """B101 end-to-end-shape: even when the scaffold moves products to
    a non-default path (``/butik``) the hero CTA must follow the
    listing route the renderer was handed, not invent a path.
    """
    from scripts.build_site import render_home

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "ecommerce-lite"
    dossier["conversionGoals"] = ["product_purchase"]
    dossier["language"] = "sv"
    output = render_home(
        dossier,
        dossier_routes=[],
        listing_route={"id": "products", "path": "/butik"},
        contact_path="/kontakta-oss",
    )

    hero_section = output.split("</section>", 1)[0]
    assert "Shoppa nu" in hero_section
    assert _route_href_attr("/butik") in hero_section
    # Bottom "Kontakta oss" still uses threaded contact_path.
    assert _route_href_attr("/kontakta-oss") in output
    assert _route_href_attr("/kontakt") not in output


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1C (B94): render_about omits the team section when
# the Project Input has no team members. Prompt-generated Project
# Inputs never populate team today, so the section rendered an empty
# "<ul>" on every demo /om-oss page in the re-Verifierings-Scout
# 2026-05-15 run.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_render_about_omits_team_section_when_team_empty() -> None:
    from scripts.build_site import render_about

    dossier = _minimal_dossier()
    dossier["company"]["team"] = []
    output = render_about(dossier)

    assert "Teamet" not in output
    assert "grid-cols-3" not in output or "Teamet" not in output


@pytest.mark.tooling
def test_render_about_omits_team_section_when_team_missing() -> None:
    """B94: a dossier without the optional ``team`` key behaves the
    same as ``team=[]`` so the renderer never crashes on missing data."""
    from scripts.build_site import render_about

    dossier = _minimal_dossier()
    dossier["company"].pop("team", None)
    output = render_about(dossier)

    assert "Teamet" not in output


@pytest.mark.tooling
def test_render_about_keeps_team_section_when_members_present() -> None:
    """B94 positive lock: curated examples with real team members keep
    the team section unchanged so painter-palma-style demos do not
    regress."""
    from scripts.build_site import render_about

    output = render_about(_minimal_dossier())

    assert "Teamet" in output
    assert "Test Person" in output
    assert "Roll" in output


@pytest.mark.tooling
def test_render_about_omits_service_areas_when_country_only() -> None:
    """B104: /om-oss should mirror hero country-only suppression."""
    from scripts.build_site import render_about

    dossier = _minimal_dossier()
    dossier["location"] = {
        "city": "Sverige",
        "country": "Sverige",
        "serviceAreas": ["Sverige"],
    }
    output = render_about(dossier)

    assert "Områden vi arbetar i" not in output
    assert "<MapPin" not in output


@pytest.mark.tooling
def test_render_about_keeps_service_areas_for_real_city() -> None:
    """B104 positive lock: real local service areas still render."""
    from scripts.build_site import render_about

    output = render_about(_minimal_dossier())

    assert "Områden vi arbetar i" in output
    assert "Norrmalm" in output


# ---------------------------------------------------------------------------
# B98 — render_about must suppress the "Områden vi arbetar i"-block for
# e-handel (ecommerce-lite scaffold) even when the location is a real
# city. E-commerce ships from one location and the "areas we work in"
# heading reads as a service-business assumption that does not fit.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b98_render_about_omits_service_areas_for_ecommerce_lite() -> None:
    """B98: ecommerce-lite scaffold must not render the location-section
    on /om-oss. The heading "Områden vi arbetar i" + the MapPin icon
    are service-business-flavoured and read awkwardly for e-handel,
    even when the location is a real city (not country-only)."""
    from scripts.build_site import render_about

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "ecommerce-lite"
    # Real city (not country-only) so the B104 country-only check
    # would otherwise allow the section to render. B98 suppresses
    # it via the new scaffold check.
    dossier["location"] = {
        "city": "Stockholm",
        "country": "Sverige",
        "serviceAreas": ["Stockholm", "Norrmalm", "Södermalm"],
    }
    output = render_about(dossier)

    assert "Områden vi arbetar i" not in output, (
        "ecommerce-lite must not show the 'Områden vi arbetar i' section "
        "even with real local service areas."
    )


@pytest.mark.tooling
def test_b98_render_about_keeps_service_areas_for_local_service_business() -> None:
    """B98 negative: scaffolds other than ecommerce-lite still get the
    location-section when the location is a real city. The B104 country-
    only check + the new B98 ecommerce-lite check compose — neither
    should accidentally suppress local-service-business output."""
    from scripts.build_site import render_about

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "local-service-business"
    output = render_about(dossier)

    assert "Områden vi arbetar i" in output
    assert "Norrmalm" in output


@pytest.mark.tooling
def test_b98_render_about_keeps_service_areas_when_scaffold_unspecified() -> None:
    """B98 defensive: a dossier without ``scaffoldId`` must NOT trigger
    the new ecommerce-lite suppression. Backwards-compat with older
    callers that pre-date the scaffold-aware about block."""
    from scripts.build_site import render_about

    dossier = _minimal_dossier()
    # No scaffoldId — _minimal_dossier() does not set one by default.
    dossier.pop("scaffoldId", None)
    output = render_about(dossier)

    assert "Områden vi arbetar i" in output


# ---------------------------------------------------------------------------
# B97 — render_section_contact_info must vary the kontakt-page hero
# body paragraph by CTA-variant (shop / booking / quote). The original
# "Beskriv jobbet kort … med tider och offert." paragraph assumed a
# quote-driven service business and read awkwardly for e-handel (orders
# / returns / delivery) and booking (book-a-time) businesses.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b97_contact_page_hero_body_quote_variant_default_unchanged() -> None:
    """B97 byte-stability: the quote-variant body must stay identical
    to the pre-fix copy so existing local-service-business renders
    do not regress.
    """
    from scripts.build_site import render_section_contact_info

    dossier = _minimal_dossier()
    # _minimal_dossier is a Malmö elektriker — quote-variant by default.
    output = render_section_contact_info(dossier)

    assert "Beskriv jobbet kort så återkommer vi inom en arbetsdag med tider och offert." in output
    # The variant-specific shop and booking copies must NOT leak into
    # the quote-variant output.
    assert "Frågor om beställning" not in output
    assert "Berätta kort vad du söker" not in output


@pytest.mark.tooling
def test_b97_contact_page_hero_body_shop_variant_for_ecommerce_lite() -> None:
    """B97: ecommerce-lite scaffold + shop-variant must show the
    order/delivery/return-flavoured body, not the quote-flavoured one.
    """
    from scripts.build_site import render_section_contact_info

    dossier = _minimal_dossier()
    dossier["scaffoldId"] = "ecommerce-lite"
    dossier["conversionGoals"] = ["purchase"]
    output = render_section_contact_info(dossier)

    assert "Frågor om beställning, leverans eller retur? Vi återkommer inom en arbetsdag." in output
    # The quote-variant copy with "jobbet" + "offert" must not appear
    # for an e-commerce contact page.
    assert "tider och offert" not in output
    assert "Beskriv jobbet kort" not in output


@pytest.mark.tooling
def test_b97_contact_page_hero_body_booking_variant_for_booking_business() -> None:
    """B97: booking-business + booking conversion goal must show the
    book-a-time-flavoured body. Verified through the booking-business-
    type fallback path in _hero_cta_variant.
    """
    from scripts.build_site import render_section_contact_info

    dossier = _minimal_dossier()
    dossier["conversionGoals"] = []
    dossier["company"]["businessType"] = "naprapat-clinic"
    output = render_section_contact_info(dossier)

    assert "Berätta kort vad du söker — vi återkommer inom en arbetsdag med en tid som passar." in output
    assert "tider och offert" not in output


@pytest.mark.tooling
def test_b97_contact_page_hero_body_english_quote_variant() -> None:
    """B97: language=en + quote-variant emits the English quote copy."""
    from scripts.build_site import render_section_contact_info

    dossier = _minimal_dossier()
    dossier["language"] = "en"
    output = render_section_contact_info(dossier)

    assert "Tell us briefly about the job and we'll get back within one business day with times and a quote." in output


@pytest.mark.tooling
def test_b97_contact_page_hero_body_english_shop_variant() -> None:
    """B97: language=en + shop-variant emits the English order/return copy."""
    from scripts.build_site import render_section_contact_info

    dossier = _minimal_dossier()
    dossier["language"] = "en"
    dossier["scaffoldId"] = "ecommerce-lite"
    dossier["conversionGoals"] = ["purchase"]
    output = render_section_contact_info(dossier)

    assert "Questions about your order, delivery or return? We get back to you within one business day." in output


@pytest.mark.tooling
def test_b97_contact_page_hero_headline_stays_generic_across_variants() -> None:
    """B97 scope-lock: only the body paragraph varies. The hero headline
    'Hör av dig' is generic enough to work across shop/booking/quote
    and must NOT be variant-branched (would inflate the change surface
    and risk regressing existing renders).
    """
    from scripts.build_site import render_section_contact_info

    for variant_dossier in (
        # quote (default)
        _minimal_dossier(),
        # shop
        {**_minimal_dossier(), "scaffoldId": "ecommerce-lite", "conversionGoals": ["purchase"]},
        # booking
        {**_minimal_dossier(), "conversionGoals": [], "company": {**_minimal_dossier()["company"], "businessType": "naprapat-clinic"}},
    ):
        output = render_section_contact_info(variant_dossier)
        assert ">Hör av dig<" in output, (
            f"Hero headline must stay 'Hör av dig' across all variants; "
            f"failed for dossier scaffoldId={variant_dossier.get('scaffoldId')!r}"
        )


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
            f"render_products must render product label {product['label']!r} via _jsx_safe_string."
        )
        assert f'{{"{product["summary"]}"}}' in output


@pytest.mark.tooling
def test_render_products_bottom_cta_uses_shop_flavoured_label() -> None:
    """B102: ``/produkter``-bottom-CTA ska följa shop-flödet, inte
    läsa som en offerttjänst. Före fixen stod "Fråga om en beställning"
    hardcoded, vilket bröt tonalitet på e-handel-cases där hero redan
    sa "Shoppa nu".
    """
    from scripts.build_site import render_products

    output = render_products(_minimal_dossier())
    assert "Hör av dig för att beställa" in output
    assert "Fråga om en beställning" not in output, (
        "B102: pre-fix offert-läsande copy får inte återinföras."
    )
    # Length-stability lock: the CTA still hangs off the same shopping
    # bag glyph and primary-button styling.
    assert "ShoppingBag" in output


@pytest.mark.tooling
def test_render_products_bottom_cta_still_links_to_contact() -> None:
    """B102 positive lock: builder MVP saknar checkout, så CTA leder
    fortfarande till kontakt-routen. Endast copyn ändras.
    """
    from scripts.build_site import render_products

    output = render_products(_minimal_dossier(), contact_path="/kontakta-oss")
    assert _route_href_attr("/kontakta-oss") in output
    assert _route_href_attr("/kontakt") not in output


@pytest.mark.tooling
def test_render_products_bottom_cta_localizes_for_english_dossier() -> None:
    """B102: the English variant must shop-localise the bottom CTA too,
    so a future ``language="en"`` e-commerce build does not regress
    to the Swedish phrase.
    """
    from scripts.build_site import render_products

    english_dossier = _minimal_dossier()
    english_dossier["language"] = "en"
    output = render_products(english_dossier)

    assert "Get in touch to order" in output
    assert "Hör av dig för att beställa" not in output


@pytest.mark.tooling
def test_commerce_bottom_cta_label_whitelist_is_safe_for_tsx() -> None:
    """Whitelist-discipline lock matching the B96/B100 _hero_cta_label
    contract: the returned string must never contain TSX-special chars
    (``<``, ``>``, ``{``, ``}``, ``"``) so direct interpolation in TSX
    stays safe without JSX-escape.
    """
    from scripts.build_site import _commerce_bottom_cta_label

    for language in ("sv", "en", "unknown"):
        label = _commerce_bottom_cta_label({"language": language})
        for forbidden in ("<", ">", "{", "}", '"'):
            assert forbidden not in label, (
                f"B102: commerce CTA label {label!r} (language={language!r}) "
                f"contains TSX-special char {forbidden!r}; whitelist must "
                "stay safe for interpolation."
            )


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
    for relative in (
        "page.tsx",
        "tjanster/page.tsx",
        "om-oss/page.tsx",
        "kontakt/page.tsx",
        "layout.tsx",
    ):
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
    assert _route_href_attr("/produkter") in layout
    assert "Tjänster" not in layout
    assert _route_href_attr("/tjanster") not in layout


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
            {"id": "contact", "path": "/kontakt", "required": True, "purpose": "Contact"},
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
    project_input_path = REPO_ROOT / "examples" / "atelje-bird.project-input.json"
    assert project_input_path.exists()

    target, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)

    # /produkter exists, /tjanster does not.
    assert (target / "app" / "produkter" / "page.tsx").exists()
    assert not (target / "app" / "tjanster" / "page.tsx").exists()

    build_result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert build_result["scaffoldId"] == "ecommerce-lite"
    assert "/produkter" in build_result["routes"]
    assert "/tjanster" not in build_result["routes"]

    quality = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))
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
    write_call_idx = body.find("paths_written = write_pages(")
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


@pytest.mark.tooling
def test_build_route_scan_receives_all_emitted_default_routes() -> None:
    """B69: Quality Gate route-scan must receive every emitted default
    route, not only routes marked ``required=true`` in routes.json.

    Both active scaffolds emit ``/om-oss`` but mark it
    ``required=false``. Passing only ``required_routes`` to the gate let
    a broken generated about page slip through without a route-scan
    finding. Aggregate QualityResult severity is intentionally not
    changed in this sprint; the lock here is that the gate input is
    ``routes_all_with_dossiers``.
    """
    import inspect

    from scripts import build_site

    body = inspect.getsource(build_site.build)
    call_idx = body.find("quality_payload, repair_payload = run_phase3_quality_and_repair(")
    assert call_idx > 0
    call_block = body[call_idx : call_idx + 300]
    assert "routes_all_with_dossiers" in call_block
    assert "routes_required_with_dossiers" not in call_block


@pytest.mark.tooling
def test_non_required_about_route_is_scanned_for_default_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B69 integration lock: ``/om-oss`` is emitted even though it is
    ``required=false``. A missing default export must therefore surface
    in the route-scan findings.
    """
    from packages.generation.build import renderers as build_renderers
    from scripts import build_site

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # B146 port (2026-05-25): render_about now lives in
    # ``packages.generation.build.renderers``. ``write_pages`` (also moved
    # there) calls it by local name, so monkeypatching
    # ``scripts.build_site.render_about`` no longer affects the build
    # output. We patch the canonical module instead.
    monkeypatch.setattr(
        build_renderers,
        "render_about",
        lambda _dossier: "export function AboutPage() { return null; }\n",
    )

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _target, run_dir = build_site.build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path,
    )

    quality = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))
    route_scan = {check["name"]: check for check in quality["checks"]}["route-scan"]
    assert route_scan["status"] == "failed"
    assert any("/om-oss" in finding for finding in route_scan["findings"])


# ---------------------------------------------------------------------------
# Bugbot follow-up: render_products CTA must use the scaffold's contact path
# instead of a hardcoded /kontakt.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_pick_contact_route_returns_scaffold_contact() -> None:
    """_pick_contact_route must return the scaffold's contact route."""
    from scripts.build_site import _pick_contact_route

    contact = _pick_contact_route(LSB_ROUTES["defaultRoutes"])
    assert contact["id"] == "contact"
    assert contact["path"] == "/kontakt"


@pytest.mark.tooling
def test_pick_contact_route_returns_none_when_missing() -> None:
    """Route/Nav Mutation V1 Slice B (ADR 0060): the contact route can be removed,
    so a missing contact route is a valid state - _pick_contact_route returns None
    (was SystemExit in Slice A). write_pages then resolves a mailto:/tel: CTA
    fallback (or omits the CTA) instead of inventing a dead /kontakt link.
    """
    from scripts.build_site import _pick_contact_route

    assert _pick_contact_route([{"id": "home", "path": "/"}]) is None


@pytest.mark.tooling
def test_render_products_uses_threaded_contact_path() -> None:
    """Bugbot fix: render_products must not hardcode /kontakt. The CTA
    href must match the contact_path kwarg threaded by write_pages.
    """
    from scripts.build_site import render_products

    output = render_products(_minimal_dossier(), contact_path="/kontakta-oss")
    assert _route_href_attr("/kontakta-oss") in output, (
        "render_products CTA must interpolate contact_path; the hardcoded "
        "/kontakt that Bugbot caught on PR #19 must not return."
    )
    # The hardcoded /kontakt must not appear when an override was passed.
    # A naive regression would leave both the literal and the f-string.
    assert _route_href_attr("/kontakt") not in output, (
        "render_products CTA still contains hardcoded /kontakt despite "
        "contact_path override - Bugbot regression."
    )


@pytest.mark.tooling
def test_render_products_default_contact_path_is_kontakt() -> None:
    """Backward compat: calling render_products without contact_path must
    still produce /kontakt so existing unit tests + the local-service-
    business scaffold (which uses /kontakt) keep working without
    threading.
    """
    from scripts.build_site import render_products

    output = render_products(_minimal_dossier())
    assert _route_href_attr("/kontakt") in output


@pytest.mark.tooling
def test_contact_ctas_use_threaded_contact_path_across_renderers() -> None:
    """B45: layout, home and services CTAs must use the threaded
    scaffold contact path, matching the render_products B13 follow-up.
    """
    from scripts.build_site import render_home, render_layout, render_services

    custom_routes = [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "services", "path": "/tjanster", "required": True, "purpose": "Services"},
        {"id": "about", "path": "/om-oss", "required": True, "purpose": "About"},
        {"id": "contact", "path": "/kontakta-oss", "required": True, "purpose": "Contact"},
    ]
    dossier = _minimal_dossier()

    outputs = [
        render_layout(dossier, [], scaffold_default_routes=custom_routes),
        render_home(
            dossier,
            [],
            listing_route={"id": "services", "path": "/tjanster"},
            contact_path="/kontakta-oss",
        ),
        render_services(dossier, contact_path="/kontakta-oss"),
    ]

    for output in outputs:
        assert _route_href_attr("/kontakta-oss") in output
        assert _route_href_attr("/kontakt") not in output


@pytest.mark.tooling
def test_route_hrefs_are_serialized_across_route_renderers() -> None:
    """B50: route paths with JSX-special characters must stay data, not
    become raw TSX syntax in generated href attributes.
    """
    from scripts.build_site import render_home, render_layout, render_products, render_services

    contact_path = '/kontakt" onClick={alert(1)}'
    listing_path = '/tjanster"{bad}'
    custom_routes = [
        {"id": "home", "path": "/", "required": True, "purpose": "Home"},
        {"id": "services", "path": listing_path, "required": True, "purpose": "Services"},
        {"id": "contact", "path": contact_path, "required": True, "purpose": "Contact"},
    ]
    dossier = _minimal_dossier()

    outputs = [
        render_layout(dossier, [], scaffold_default_routes=custom_routes),
        render_home(
            dossier,
            [],
            listing_route={"id": "services", "path": listing_path},
            contact_path=contact_path,
        ),
        render_services(dossier, contact_path=contact_path),
        render_products(dossier, contact_path=contact_path),
    ]

    for output in outputs:
        assert _route_href_attr(contact_path) in output
        assert f'href="{contact_path}"' not in output
    assert _route_href_attr(listing_path) in outputs[0]
    assert _route_href_attr(listing_path) in outputs[1]
    assert f'href="{listing_path}"' not in outputs[1]


@pytest.mark.tooling
def test_contact_renderer_helpers_do_not_literal_code_kontakt_href() -> None:
    """B45 source lock: renderer helpers may keep /kontakt as a default
    kwarg/fallback, but must not literal-code ``href="/kontakt"``.
    """
    from scripts import build_site

    for fn_name in (
        "render_layout",
        "render_home",
        "render_services",
        "render_products",
    ):
        source = inspect.getsource(getattr(build_site, fn_name))
        assert 'href="/kontakt"' not in source, (
            f'{fn_name} still literal-codes href="/kontakt" instead '
            "of interpolating the scaffold contact path."
        )


@pytest.mark.tooling
def test_write_pages_threads_scaffold_contact_path_into_render_products(
    tmp_path: Path,
) -> None:
    """End-to-end smoke for the dispatch: write_pages must pass the
    scaffold's contact path into render_products, not a hardcoded value.

    We build a synthetic scaffold whose contact route lives at
    ``/kontakta-oss`` and verify the products page links there.
    """
    from scripts.build_site import write_pages

    custom_routes = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "products", "path": "/produkter", "required": True, "purpose": "Products"},
            {"id": "contact", "path": "/kontakta-oss", "required": True, "purpose": "Contact"},
        ]
    }
    write_pages(tmp_path, _minimal_dossier(), custom_routes, [])
    produkter = (tmp_path / "app" / "produkter" / "page.tsx").read_text(encoding="utf-8")
    assert _route_href_attr("/kontakta-oss") in produkter
    assert _route_href_attr("/kontakt") not in produkter


@pytest.mark.tooling
def test_write_pages_threads_contact_path_into_all_contact_ctas(
    tmp_path: Path,
) -> None:
    """B45 end-to-end dispatch: write_pages must pass the scaffold's
    contact path into layout, home, services and products.
    """
    from scripts.build_site import write_pages

    custom_routes = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "services", "path": "/tjanster", "required": True, "purpose": "Services"},
            {"id": "products", "path": "/produkter", "required": True, "purpose": "Products"},
            {"id": "about", "path": "/om-oss", "required": True, "purpose": "About"},
            {"id": "contact", "path": "/kontakta-oss", "required": True, "purpose": "Contact"},
        ]
    }
    write_pages(tmp_path, _minimal_dossier(), custom_routes, [])

    for relative in (
        "layout.tsx",
        "page.tsx",
        "tjanster/page.tsx",
        "produkter/page.tsx",
    ):
        output = (tmp_path / "app" / relative).read_text(encoding="utf-8")
        assert _route_href_attr("/kontakta-oss") in output
        assert _route_href_attr("/kontakt") not in output


@pytest.mark.tooling
def test_write_pages_without_contact_route_retargets_and_leaves_no_dead_link(
    tmp_path: Path,
) -> None:
    """Slice B (ADR 0060): a route set without a contact route is now valid (the
    contact page can be removed). write_pages succeeds, retargets the CTAs to a
    real channel (mailto: the dossier email) and never invents a dead /kontakt
    link.
    """
    from scripts.build_site import write_pages

    routes_without_contact = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "services", "path": "/tjanster", "required": True, "purpose": "Services"},
        ]
    }

    written = write_pages(tmp_path, _minimal_dossier(), routes_without_contact, [])
    assert written == ["/", "/tjanster"]
    for page in (tmp_path / "app").rglob("*.tsx"):
        output = page.read_text(encoding="utf-8")
        assert _route_href_attr("/kontakt") not in output, (
            f"{page.relative_to(tmp_path)} invented a dead /kontakt link"
        )
    home = (tmp_path / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "mailto:hej@test.se" in home


@pytest.mark.tooling
def test_write_pages_rejects_non_canonical_scaffold_route(tmp_path: Path) -> None:
    """B50 follow-up: scaffold routes must not escape the site route space."""
    from scripts.build_site import write_pages

    routes_with_escaping_path = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "about", "path": "/../secret", "required": True, "purpose": "About"},
            {"id": "contact", "path": "/kontakt", "required": True, "purpose": "Contact"},
        ]
    }

    with pytest.raises(SystemExit, match=r"must not contain .* path segments"):
        write_pages(tmp_path, _minimal_dossier(), routes_with_escaping_path, [])


@pytest.mark.tooling
def test_write_pages_omits_listing_cross_link_when_listing_route_missing(
    tmp_path: Path,
) -> None:
    """A scaffold with home/contact but no services/products must not
    emit a homepage CTA to a route it never writes.
    """
    from scripts.build_site import write_pages

    routes_without_listing = {
        "defaultRoutes": [
            {"id": "home", "path": "/", "required": True, "purpose": "Home"},
            {"id": "contact", "path": "/kontakt", "required": True, "purpose": "Contact"},
        ]
    }

    write_pages(tmp_path, _minimal_dossier(), routes_without_listing, [])
    home = (tmp_path / "app" / "page.tsx").read_text(encoding="utf-8")

    assert _route_href_attr("/tjanster") not in home
    assert _route_href_attr("/produkter") not in home
    assert "Se alla tjänster" not in home
    assert "Se alla produkter" not in home
