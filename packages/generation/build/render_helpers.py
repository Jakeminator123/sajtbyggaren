"""Delade nav/cta/business-type-hjälpare för den deterministiska byggaren.

Extraherat ordagrant ur ``scripts/build_site.py`` enligt
``docs/refactor/megafiles-plan.md`` (Del 1 slice 5 + Del 2 slice 5),
beteendebevarande. Det här är slicen som ger de delade hjälparna ETT hem i
paketet i stället för att de pendlar mellan ``scripts/build_site.py`` och
``packages/generation/build/renderers.py``.

Funktionerna här är rena (nollkoppling): de anropar INGA io-hjälpare
(``utc_now``/``load_json``/``write``/``_to_repo_relative``) och inget annat i
``scripts/build_site.py``, så ingen lat ``package -> scripts``-import behövs och
import-grafen förblir cykelfri.

``scripts/build_site.py`` re-exporterar dessa namn (ivriga attribut-binds) så att
``from scripts.build_site import ...`` fortsätter resolva. ``renderers.py``
importerar nu de delade format-/CTA-hjälparna (``_jsx_safe_string``,
``_contact_href``, ``_filled_contact_cta``, ``_route_href``,
``_text_contact_cta``) DIREKT härifrån. Den lata shimmen
(``_call_build_site("<name>", …)`` -> ``getattr(scripts.build_site, "<name>")``)
finns kvar i ``renderers.py`` för de hjälpare/konstanter som ännu inte brutits ut
ur ``scripts.build_site``; eftersom build_site re-exporterar flera av namnen
härifrån landar den shimmen ändå i samma funktioner.

``_LISTING_COPY_BY_ROUTE_ID`` och ``_RUNTIME_TOKEN_LISTENER_JS`` stannar kvar i
``scripts/build_site.py`` (de nås av renderarna via ``_lazy_attr`` men ingen
flyttad funktion här använder dem).
"""

from __future__ import annotations

import json

SERVICE_ICONS: dict[str, str] = {
    "interior-painting": "Paintbrush",
    "exterior-painting": "House",
    "color-consultation": "Palette",
    "renovation-painting": "Hammer",
    "arcade-games": "Gamepad2",
    "retro-consoles": "Joystick",
    "tournaments": "Trophy",
    "tournaments-monthly": "Trophy",
    "birthday-parties": "Cake",
    "private-events": "PartyPopper",
    "food-drinks": "Coffee",
    "merch-shop": "ShoppingBag",
}
DEFAULT_SERVICE_ICON = "Sparkles"


def _icon_for_service(service_id: str) -> str:
    return SERVICE_ICONS.get(service_id, DEFAULT_SERVICE_ICON)


def _phone_href(phone: str) -> str:
    return phone.replace(" ", "").replace("(", "").replace(")", "")


# Default Swedish nav labels per scaffold route id. Unknown ids fall back
# to a slug-to-Title-Case form via _nav_label_for_route. Centralised so
# different scaffolds share the same vocabulary (e.g. "contact" -> "Kontakt"
# everywhere) without duplicating literals in each renderer.
_NAV_LABEL_BY_ROUTE_ID: dict[str, str] = {
    "home": "Hem",
    "services": "Tjänster",
    "products": "Produkter",
    "about": "Om oss",
    "contact": "Kontakt",
    # B132 follow-up sprint 2026-05-21: wizardMustHave-driven extras
    # land as real routes for local-service-business via the new
    # _wizard_extra_routes helper in packages/generation/planning/plan.py.
    # Labels here keep the nav copy operator-facing in Swedish without
    # forcing each renderer to repeat the same string.
    "faq": "Vanliga frågor",
    "gallery": "Galleri",
    "map": "Hitta hit",
    "team": "Team",
    "pricing": "Priser",
    "portfolio": "Portfolio",
    # restaurant-hospitality scaffold routes — Issue #90. The scaffold's
    # routes.json declares Swedish slugs ``/meny`` and ``/bokning``; the
    # nav must use restaurant-flavoured labels rather than fall through
    # to ``_nav_label_for_route``'s slug-to-title-case fallback. We also
    # override the "contact" label for restaurants by relying on the
    # generic "Kontakt" entry above — the scaffold uses route id
    # ``contact`` so it picks up the same label as LSB/commerce.
    "menu": "Meny",
    "booking": "Boka bord",
    # Runtime-active Path B scaffolds (clinic-healthcare,
    # professional-services, agency-studio) use these route ids.
    "treatments": "Behandlingar",
    "expertise": "Expertis",
    "work": "Arbeten",
}


# Demo-baseline-fix 1C (B96): hero CTA copy keyed on scaffold + conversion
# goals. ``ecommerce-lite`` (or any project whose conversionGoals signal
# purchase intent) gets a shopping verb; bokningsdrivna verksamheter
# (``booking_request`` i conversionGoals) får boka-verbet; resten faller
# tillbaka på "Begär offert" som var hardcoded före re-Verifierings-Scout
# 2026-05-15.
_HERO_CTA_VARIANT_LABELS: dict[str, dict[str, str]] = {
    "shop": {"sv": "Shoppa nu", "en": "Shop now"},
    "booking": {"sv": "Boka tid", "en": "Book a time"},
    "quote": {"sv": "Begär offert", "en": "Request a quote"},
}

_SHOP_CONVERSION_GOALS: frozenset[str] = frozenset({"product_purchase", "shop_visit", "purchase"})
_BOOKING_CONVERSION_GOALS: frozenset[str] = frozenset({"booking_request", "book_appointment"})
_SHOP_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        "e-commerce",
        "ecommerce",
        "ecommerce-shop",
        "ecommerce-store",
        "online-shop",
        "shop",
        "webshop",
        "webbshop",
    }
)
_BOOKING_BUSINESS_TYPES: frozenset[str] = frozenset(
    {
        "hair-salon",
        "hairdresser",
        "frisör",
        "barber",
        "barber-shop",
        "naprapat-clinic",
        "naprapath-clinic",
        "naprapat",
        "naprapath",
        "naprapatklinik",
        "chiropractor",
        "chiropractic-clinic",
        "massage",
        "massage-therapist",
        "physiotherapist",
        "physiotherapy-clinic",
        "dentist",
        "dental-clinic",
        "personal-training",
        "personal-trainer",
    }
)


def _normalize_business_type(value: object) -> str:
    """Normalize briefModel business type variants for CTA fallback lookup.

    B150: briefModel sometimes emits multi-word business types
    ("massage studio", "yoga studio", "personal trainer studio"). The
    compact slug ("massage-studio") does not appear in
    ``_BOOKING_BUSINESS_TYPES`` or ``_SHOP_BUSINESS_TYPES``, which made
    ``_hero_cta_variant`` fall through to the generic "Begär offert" CTA
    instead of firing "Boka tid" / "Handla nu" for these branscher. We
    therefore try progressively shorter dash-prefixes and return the
    longest prefix that is itself a registered slug. The function never
    invents new slugs — it can only return strings that the CTA-resolver
    already knows about, or the unchanged compact form.
    """
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    compact = raw.replace("_", "-").replace(" ", "-")
    if compact.startswith("naprapat") or compact.startswith("naprapath"):
        return "naprapat-clinic"
    if compact in {"frisor", "frisör", "hairdresser"}:
        return "hair-salon"
    if compact in {"webshop", "webbshop", "online-shop"}:
        return "e-commerce"
    if compact in _BOOKING_BUSINESS_TYPES or compact in _SHOP_BUSINESS_TYPES:
        return compact
    if "-" in compact:
        parts = compact.split("-")
        for n in range(len(parts) - 1, 0, -1):
            prefix = "-".join(parts[:n])
            if prefix in _BOOKING_BUSINESS_TYPES or prefix in _SHOP_BUSINESS_TYPES:
                return prefix
    return compact


def _hero_cta_variant(dossier: dict) -> str:
    """Return the hero CTA variant key for this Project Input.

    Explicit conversion goals win first. Business type is then used as
    the B100 fallback for short prompts where briefModel leaves
    ``conversionGoals=[]``. The scaffold id remains the final defensive
    fallback because operators sometimes pin ``ecommerce-lite`` without
    filling conversionGoals.
    """
    scaffold_id = (dossier.get("scaffoldId") or "").strip().lower()
    company = dossier.get("company") or {}
    business_type = _normalize_business_type(company.get("businessType"))
    goals = {
        str(goal).strip().lower()
        for goal in (dossier.get("conversionGoals") or [])
        if isinstance(goal, str)
    }
    if goals & _SHOP_CONVERSION_GOALS:
        return "shop"
    if goals & _BOOKING_CONVERSION_GOALS:
        return "booking"
    if business_type in _SHOP_BUSINESS_TYPES:
        return "shop"
    if business_type in _BOOKING_BUSINESS_TYPES:
        return "booking"
    if scaffold_id == "ecommerce-lite":
        return "shop"
    return "quote"


def _hero_cta_label(dossier: dict) -> str:
    """Return the hero CTA label string for this Project Input.

    Reads ``dossier["language"]`` (defaults to ``sv``) and routes
    through ``_hero_cta_variant`` so render_home and render_services
    share the same wording. Values are drawn from the whitelist in
    ``_HERO_CTA_VARIANT_LABELS`` so the returned string is safe to
    interpolate into TSX without JSX-escaping (it never contains
    angle brackets, quotes or curlies).
    """
    language = (dossier.get("language") or "sv").strip().lower()
    if language not in ("sv", "en"):
        language = "sv"
    variant = _hero_cta_variant(dossier)
    return _HERO_CTA_VARIANT_LABELS[variant][language]


# B102 (re-Verifierings-Scout 3 2026-05-18): commerce-CTA på /produkter
# var hardcoded till "Fråga om en beställning" / "ShoppingBag"-glyfen, vilket
# läste som en offerttjänst snarare än shop-flöde. Vi behåller länken mot
# kontakt-routen (ingen checkout finns ännu i builder MVP) men byter
# verbet så tonen följer hero-CTA "Shoppa nu". Whitelist-baserade
# strängar håller TSX-interpolationen säker utan JSX-escape.
_COMMERCE_BOTTOM_CTA_LABELS: dict[str, str] = {
    "sv": "Hör av dig för att beställa",
    "en": "Get in touch to order",
}


def _commerce_bottom_cta_label(dossier: dict) -> str:
    """Return the /produkter bottom-CTA label string.

    B102: "Fråga om en beställning" lät som en offert/förfrågan-tjänst
    på e-handel-cases där hero redan stod "Shoppa nu". Den nya copyn
    håller fortfarande den verbala dörren öppen mot kontakt-routen (ingen
    checkout finns i builder MVP) men landar i shop-tonalitet via verbet
    "beställa" / "order". Returvärdet är hämtat från en whitelist så
    interpolationen i TSX är säker utan JSX-escape.
    """
    language = (dossier.get("language") or "sv").strip().lower()
    if language not in _COMMERCE_BOTTOM_CTA_LABELS:
        language = "sv"
    return _COMMERCE_BOTTOM_CTA_LABELS[language]


def _hero_cta_target_path(
    dossier: dict,
    listing_route: dict | None,
    contact_path: str | None,
) -> str | None:
    """Return the route the hero CTA should link to.

    B101 (re-Verifierings-Scout 3 2026-05-18): a hero CTA labelled
    "Shoppa nu" / "Shop now" used to point at the scaffold contact
    route even when the build emitted a real ``/produkter`` listing,
    so the operator-visible button promised one thing and the click
    landed somewhere else. The new rule: when the CTA variant is
    ``shop`` and the scaffold actually emits a products listing, the
    hero CTA jumps to that listing route. Booking and quote variants
    keep contact as the primary target because there is no equivalent
    "list of bookable slots" surface in the current scaffolds. Shop
    variants fall back to contact when the scaffold has no products
    route - the label still reads "Shoppa nu" but at least the click
    lands on a real page instead of inventing ``/produkter`` for
    scaffolds that never declared it.
    """
    variant = _hero_cta_variant(dossier)
    if (
        variant == "shop"
        and listing_route is not None
        and listing_route.get("id") == "products"
        and listing_route.get("path")
    ):
        return listing_route["path"]
    return contact_path


def _location_is_country_only(location: dict) -> bool:
    """Return True when ``location.city`` equals ``location.country``.

    Demo-baseline-fix 1C (B95): when the brief returns a country name
    as ``locationHint`` (or omits it entirely), ``_placeholder_location``
    falls back to ``city == country`` as a marker. ``render_home`` uses
    this helper to suppress the hero ortstag rather than rendering the
    country name as if it were a city.
    """
    city = (location.get("city") or "").strip().lower()
    country = (location.get("country") or "").strip().lower()
    return bool(city) and city == country


def _nav_label_for_route(route_id: str) -> str:
    """Return the Swedish nav label for a scaffold route id.

    Known ids use the centralised lookup. Unknown ids fall back to a
    human-readable form so an early-preview scaffold can still produce
    a sensible nav without first registering its labels here.
    """
    if route_id in _NAV_LABEL_BY_ROUTE_ID:
        return _NAV_LABEL_BY_ROUTE_ID[route_id]
    return route_id.replace("-", " ").replace("_", " ").title()


def _nav_items_from_scaffold(
    scaffold_default_routes: list[dict],
    dossier_routes: list[str],
    extra_routes: list[dict] | None = None,
    hidden_nav_route_ids: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Build the (href, label) nav items for header + footer.

    Driven by the scaffold's ``defaultRoutes`` (so different scaffolds
    can emit different nav structures) plus any Dossier-contributed
    routes that should appear in the nav. Currently the only such
    Dossier-route is ``/spel`` (interactive-game-loop); when more
    Dossiers add navigable pages this branch widens.

    Dossier-routes are deduped against the scaffold paths so a future
    scaffold that adopts ``/spel`` in ``defaultRoutes`` does not get
    the entry rendered twice (B52). Scaffold order is preserved; the
    Dossier-injected route lands at the end, after the scaffold's own
    nav structure.

    ``extra_routes`` carries wizard-driven routes (B132 follow-up
    sprint 2026-05-21): they land after scaffold defaults but before
    the contact CTA in the nav order. Same dedupe rule as for
    dossier routes — a path already declared by the scaffold or by a
    dossier wins, so emitting a wizard extra cannot duplicate the
    visible nav item.

    ``hidden_nav_route_ids`` carries nav_hide routeIds (Route/Nav
    Mutation V1, ADR 0060, route_editor): a scaffold route whose id is
    in this set keeps its page but is SKIPPED from the nav (href,label)
    list, so the header/footer link disappears while the page stays.
    This is the only nav_hide seam — the page write, route guards and
    _pick_contact_route all keep the full route set.
    """
    hidden = hidden_nav_route_ids or set()
    items: list[tuple[str, str]] = [
        (route["path"], _nav_label_for_route(route["id"]))
        for route in scaffold_default_routes
        if route.get("id") not in hidden
    ]
    existing_paths = {href for href, _ in items}
    if extra_routes:
        # B148: look up the contact route's actual path from the scaffold
        # rather than hardcoding "/kontakt". restaurant-hospitality uses
        # "/hitta-hit" and future scaffolds may pick other ids — the
        # insert-before-contact heuristic must follow the scaffold, not
        # the most common path. Mirrors the lookup pattern in
        # ``_pick_contact_route`` (no SystemExit here — nav-building must
        # stay defensive even if a scaffold lacks a contact route, in
        # which case wizard-extras simply append to the end).
        contact_path = next(
            (
                route.get("path")
                for route in scaffold_default_routes
                if route.get("id") == "contact"
            ),
            None,
        )
        contact_idx: int | None = None
        if isinstance(contact_path, str) and contact_path:
            contact_idx = next(
                (i for i, (href, _label) in enumerate(items) if href == contact_path),
                None,
            )
        for route in extra_routes:
            if not isinstance(route, dict):
                continue
            path = route.get("path")
            route_id = route.get("id") or ""
            if not isinstance(path, str) or not path or path in existing_paths:
                continue
            entry = (path, _nav_label_for_route(route_id))
            if contact_idx is not None:
                items.insert(contact_idx, entry)
                contact_idx += 1
            else:
                items.append(entry)
            existing_paths.add(path)
    if "/spel" in dossier_routes and "/spel" not in existing_paths:
        items.append(("/spel", "Spel"))
        existing_paths.add("/spel")
    return items


def _pick_contact_route(
    scaffold_default_routes: list[dict],
) -> dict | None:
    """Return the scaffold's contact route, or ``None`` when there is none.

    Renderers that link operators to the contact page route hrefs
    through this helper so a scaffold that ever moves the contact id
    to ``/kontakta-oss`` keeps its CTAs aligned with the nav.

    Route/Nav Mutation V1 Slice B (ADR 0060): a ``route_remove`` follow-up can
    now disable the (required) contact route, so ``activeRoutes`` may legitimately
    carry no contact route. This returns ``None`` in that case instead of raising
    ``SystemExit``; ``write_pages`` resolves a ``mailto:``/``tel:`` CTA fallback
    (or omits the CTA) via ``_contact_cta_target`` + ``_contact_href`` so the
    builder never crashes and never emits a dead ``/kontakt`` link.
    """
    for route in scaffold_default_routes:
        if route.get("id") == "contact":
            return route
    return None


def _pick_listing_route(
    scaffold_default_routes: list[dict],
) -> dict | None:
    """Return the scaffold's primary listing route (services or products).

    Used by ``render_home`` to point the secondary CTA at the right
    place: ``/tjanster`` for local-service-business, ``/produkter``
    for ecommerce-lite. Returns ``None`` for scaffolds that declare
    neither (the home page then omits the listing cross-link entirely
    instead of inventing a path that has no matching route).
    """
    by_id = {r["id"]: r for r in scaffold_default_routes}
    for candidate in ("services", "products", "treatments", "expertise", "work"):
        if candidate in by_id:
            return by_id[candidate]
    return None


def _collect_icons_for_pages(services: list[dict], dossier_routes: list[str]) -> list[str]:
    used: set[str] = {
        DEFAULT_SERVICE_ICON,
        "Phone",
        "Mail",
        "MapPin",
        "Clock",
        "ShieldCheck",
        "ArrowRight",
        "Quote",
    }
    for svc in services:
        used.add(_icon_for_service(svc["id"]))
    if "/spel" in dossier_routes:
        used.add("Gamepad2")
    return sorted(used)


# ---------------------------------------------------------------------------
# Shared JSX-formatting + contact-CTA helpers (megafiles-plan Del 1 slice 5).
#
# Moved here from scripts/build_site.py (_jsx_safe_string, _validated_site_
# route_path, _route_href, _contact_href) and from
# packages/generation/build/renderers.py (_filled_contact_cta,
# _text_contact_cta) so the cross-family formatting/CTA helpers have ONE home
# in the package instead of living in build_site.py + renderers.py and being
# reached through lazy shims. Pure (json + string ops only): no io-helpers, no
# scripts/ import, so the import graph stays cycle-free. build_site.py and
# renderers.py re-export these names so every existing spelling keeps resolving.
# ---------------------------------------------------------------------------


def _jsx_safe_string(text: str) -> str:
    """Wrap user-supplied text as a safe JSX expression ``{"<json-encoded>"}``.

    Routing the value through ``json.dumps`` ensures every JSX-special
    character (``<``, ``>``, ``{``, ``}``, ``&``, ``"``, ``\\``) becomes valid
    JS string-literal content, so a customer name with ``<`` or ``{`` cannot
    produce invalid TSX that ``next build`` would reject mid-pipeline.
    """
    return "{" + json.dumps(text, ensure_ascii=False) + "}"


def _validated_site_route_path(route_path: str) -> str:
    """Return a scaffold route path after fail-fast canonical validation."""
    if not isinstance(route_path, str) or not route_path.startswith("/"):
        raise SystemExit(
            "Builder failed: scaffold route path must be an absolute "
            f"site path starting with '/' (got {route_path!r})."
        )
    if route_path.startswith("//"):
        raise SystemExit(
            "Builder failed: scaffold route path must be a root-relative "
            f"site path, not a protocol-relative URL (got {route_path!r})."
        )
    if "\\" in route_path or "?" in route_path or "#" in route_path:
        raise SystemExit(
            "Builder failed: scaffold route path must be a canonical site "
            f"path without backslashes, query strings or fragments (got {route_path!r})."
        )
    if route_path != "/":
        segments = route_path.split("/")[1:]
        if any(segment in {"", ".", ".."} for segment in segments):
            raise SystemExit(
                "Builder failed: scaffold route path must not contain empty, "
                f"'.' or '..' path segments (got {route_path!r})."
            )
    return route_path


def _route_href(route_path: str) -> str:
    """Return a scaffold route path as a safe JSX href attribute value."""
    route_path = _validated_site_route_path(route_path)
    return _jsx_safe_string(route_path)


def _contact_href(contact_target: str | None) -> str | None:
    """Return a JSX-safe href for a contact CTA, or ``None`` to omit the anchor.

    A scaffold ``/`` route path is validated as a canonical site path via
    ``_route_href``; a ``mailto:``/``tel:`` action is passed through (JSX-safe);
    anything else returns ``None`` so the caller omits the anchor instead of
    emitting a dead/invalid href (ADR 0060 Slice B).
    """
    if not contact_target:
        return None
    if contact_target.startswith("/"):
        return _route_href(contact_target)
    if contact_target.startswith(("mailto:", "tel:")):
        return _jsx_safe_string(contact_target)
    return None


def _filled_contact_cta(
    contact_path: str | None,
    label: str,
    *,
    indent: str = "          ",
    lead_icon: str = "",
) -> str:
    """Filled primary contact-CTA button, or ``""`` when there is no target.

    Slice B (ADR 0060): the shared filled "Begär offert"/"Boka tid"/shop button
    used by the service-list, collection, products and wizard-route renderers.
    Returns ``""`` when contact was removed with no ``mailto:``/``tel:`` fallback
    so the page omits the button instead of linking to a dead ``/kontakt`` route.
    Byte-identical to the previous inline anchor when a target exists.
    """
    href = _contact_href(contact_path)
    if href is None:
        return ""
    return f'{indent}<a href={href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{lead_icon}{label}<ArrowRight className="size-4" /></a>\n'


def _text_contact_cta(
    contact_path: str | None,
    label: str,
    *,
    indent: str = "          ",
    class_name: str = (
        "inline-flex w-fit items-center gap-2 text-sm font-medium "
        "underline-offset-4 hover:underline"
    ),
    icon_size: str = "size-4",
) -> str:
    """Underlined text contact-CTA link, or ``""`` when there is no target.

    Slice B (ADR 0060): the shared clinic/professional/agency "Boka tid" /
    "Diskutera ärende" / "Diskutera projekt" link. Same omit-on-no-target rule
    as ``_filled_contact_cta``; byte-identical to the previous inline anchor
    when a target exists.
    """
    href = _contact_href(contact_path)
    if href is None:
        return ""
    return f'{indent}<a href={href} className="{class_name}">{label}<ArrowRight className="{icon_size}" /></a>\n'
