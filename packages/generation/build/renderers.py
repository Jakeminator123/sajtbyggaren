"""Page renderers for the deterministic Builder MVP.

Extracted from ``scripts/build_site.py`` for B13a Step C. This module keeps
the renderer bodies intact while leaving shared builder utilities, media
helpers, CTA logic and route-pickers in ``scripts.build_site`` until the
later full architecture move.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from packages.generation.build.static_assets import (
    _render_structured_data_jsonld,
    render_global_error,
    render_not_found,
    render_og_fallback_svg,
    render_robots_txt,
    render_sitemap_xml,
)


def _build_site_module() -> ModuleType:
    main_module = sys.modules.get("__main__")
    main_file = str(getattr(main_module, "__file__", "")) if main_module else ""
    if main_module is not None and main_file.endswith("scripts/build_site.py"):
        return main_module
    module = sys.modules.get("scripts.build_site")
    if module is not None:
        return module
    from scripts import build_site

    return build_site


class _BuildSiteAttr:
    def __init__(self, name: str) -> None:
        self.name = name

    def resolve(self) -> Any:
        return getattr(_build_site_module(), self.name)

    def __getitem__(self, key: Any) -> Any:
        return self.resolve()[key]

    def __contains__(self, key: object) -> bool:
        return key in self.resolve()

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self.resolve().get(*args, **kwargs)


def _lazy_attr(name: str) -> _BuildSiteAttr:
    return _BuildSiteAttr(name)


def _resolve_lazy(value: Any) -> Any:
    if isinstance(value, _BuildSiteAttr):
        return value.resolve()
    return value


_LISTING_COPY_BY_ROUTE_ID = _lazy_attr("_LISTING_COPY_BY_ROUTE_ID")
_RUNTIME_TOKEN_LISTENER_JS = _lazy_attr("_RUNTIME_TOKEN_LISTENER_JS")


def _call_build_site(name: str, *args: Any, **kwargs: Any) -> Any:
    return getattr(_build_site_module(), name)(*args, **kwargs)


def _collect_icons_for_pages(services: list[dict], dossier_routes: list[str]) -> list[str]:
    return _call_build_site("_collect_icons_for_pages", services, dossier_routes)


def _commerce_bottom_cta_label(dossier: dict) -> str:
    return _call_build_site("_commerce_bottom_cta_label", dossier)


def _hero_cta_label(dossier: dict) -> str:
    return _call_build_site("_hero_cta_label", dossier)


def _hero_cta_target_path(
    dossier: dict,
    listing_route: dict | None,
    contact_path: str,
) -> str:
    return _call_build_site("_hero_cta_target_path", dossier, listing_route, contact_path)


def _icon_for_service(service_id: str) -> str:
    return _call_build_site("_icon_for_service", service_id)


def _js_string_literal(text: Any) -> str:
    return _call_build_site("_js_string_literal", _resolve_lazy(text))


def _jsx_safe_string(text: str) -> str:
    return _call_build_site("_jsx_safe_string", text)


def _location_is_country_only(location: dict) -> bool:
    return _call_build_site("_location_is_country_only", location)


def _member_initials(full_name: str) -> str:
    return _call_build_site("_member_initials", full_name)


def _nav_items_from_scaffold(
    scaffold_default_routes: list[dict],
    dossier_routes: list[str],
    extra_routes: list[dict] | None = None,
) -> list[tuple[str, str]]:
    return _call_build_site(
        "_nav_items_from_scaffold",
        scaffold_default_routes,
        dossier_routes,
        extra_routes,
    )


def _normalise_hex_color(value: Any) -> str | None:
    return _call_build_site("_normalise_hex_color", value)


def _normalize_business_type(value: object) -> str:
    return _call_build_site("_normalize_business_type", value)


def _normalize_tone_key(value: str) -> str:
    return _call_build_site("_normalize_tone_key", value)


def _phone_href(phone: str) -> str:
    return _call_build_site("_phone_href", phone)


def _pick_contact_route(scaffold_default_routes: list[dict]) -> dict:
    return _call_build_site("_pick_contact_route", scaffold_default_routes)


def _pick_listing_route(scaffold_default_routes: list[dict]) -> dict | None:
    return _call_build_site("_pick_listing_route", scaffold_default_routes)


def _route_href(route: str) -> str:
    return _call_build_site("_route_href", route)


def resolve_media_asset(dossier: dict, kind: str) -> dict | None:
    return _call_build_site("resolve_media_asset", dossier, kind)


def route_to_page_path(target: Path, route: str) -> Path:
    return _call_build_site("route_to_page_path", target, route)


def write(path: Path, contents: str) -> None:
    _call_build_site("write", path, contents)


def _renderer(name: str) -> Any:
    return getattr(_build_site_module(), name, globals()[name])


def render_layout(
    dossier: dict,
    dossier_routes: list[str],
    *,
    scaffold_default_routes: list[dict] | None = None,
    contact_path: str | None = None,
    extra_routes: list[dict] | None = None,
) -> str:
    """Whole-file layout.tsx with sticky header and footer.

    Nav items are built from ``scaffold_default_routes`` so different
    scaffolds emit different navigation shells (e.g. ecommerce-lite
    points at ``/produkter`` instead of ``/tjanster``). When
    ``scaffold_default_routes`` is ``None`` the renderer falls back
    to the local-service-business defaults; this keeps the unit
    tests in tests/test_builder_audit_post_3b_next.py (which only
    check JSX escaping) functional without forcing every caller to
    pass the scaffold registry.
    """
    company = dossier["company"]
    contact = dossier["contact"]
    if scaffold_default_routes is None:
        scaffold_default_routes = [
            {"id": "home", "path": "/"},
            {"id": "services", "path": "/tjanster"},
            {"id": "about", "path": "/om-oss"},
            {"id": "contact", "path": "/kontakt"},
        ]
    nav_items = _nav_items_from_scaffold(
        scaffold_default_routes,
        dossier_routes,
        extra_routes,
    )
    if contact_path is None:
        contact_path = str(_pick_contact_route(scaffold_default_routes)["path"])
    contact_href = _route_href(contact_path)
    # nav_items entries come from _nav_items_from_scaffold (canonical
    # paths + Swedish labels driven by scaffold_default_routes). Paths go
    # through _route_href which validates them as canonical site paths
    # (B50). Labels go through _jsx_safe_string so an unknown route id
    # that falls through to the ``.title()`` slug-to-Title-Case branch
    # (e.g. "look-book" -> "Look Book") cannot leak raw HTML/JSX into
    # the nav (B51). Customer-supplied values (company.name,
    # company.tagline, contact.*, addressLines) all go through
    # _jsx_safe_string for JSX positions or _js_string_literal for the
    # metadata object literal - see B30 in docs/known-issues.md.
    nav_links = "\n".join(
        f'            <a href={_route_href(href)} className="text-[color:var(--muted)] hover:text-[color:var(--foreground)] transition-colors">{_jsx_safe_string(label)}</a>'
        for href, label in nav_items
    )
    address_line = ", ".join(contact["addressLines"])

    # Operatör-uppladdad logotyp (om finns) → renderas i header och
    # footer. Annars faller vi tillbaka till bokstavs-monogram-spannet
    # som starters har använt sedan B12. Filen finns redan på plats
    # under public/uploads/ via copy_operator_uploads ovan.
    brand_block = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    operator_logo = brand_block.get("logo") if isinstance(brand_block, dict) else None
    if isinstance(operator_logo, dict) and operator_logo.get("filename"):
        logo_filename = operator_logo["filename"]
        logo_alt = operator_logo.get("alt") or f"{company['name']} logotyp"
        logo_width = operator_logo.get("width")
        logo_height = operator_logo.get("height")
        dims = ""
        if isinstance(logo_width, int) and isinstance(logo_height, int):
            dims = f' width={{{logo_width}}} height={{{logo_height}}}'
        # eslint-disable-next-line @next/next/no-img-element — vi använder
        # raw <img> för att slippa Next.js Image-loader inställningar i
        # alla starters; webp:erna är redan komprimerade av sharp.
        # VIKTIGT: `_jsx_safe_string("...")` returnerar `{"..."}` — det är
        # ett komplett JSX-uttryck för text/attribut, INTE en sträng som kan
        # smetas in mellan `"`-quotes. Tidigare kombinerade vi det med
        # `src="/uploads/{...}"`, vilket producerade `src="/uploads/{"x.webp"}"`
        # och bröt next build med "Expected '</', got '.'". Korrekt är att
        # låta hela attribut-värdet vara ett JS-uttryck (`src={...}`).
        header_logo_jsx = (
            f'              <img src={_jsx_safe_string("/uploads/" + logo_filename)}'
            f' alt={_js_string_literal(logo_alt)} className="h-9 w-auto object-contain"{dims} />'
        )
        footer_logo_jsx = (
            f'              <img src={_jsx_safe_string("/uploads/" + logo_filename)}'
            f' alt={_js_string_literal(logo_alt)} className="h-10 w-auto object-contain mb-1"{dims} />'
        )
    else:
        # Fas 2.5 — snyggare default-monogram. Två-tons gradient som
        # förgrund (primary → accent) och en mjuk shadow-ring så symbolen
        # står ut även mot ljusa bakgrunder. tracking-wider gör att två
        # bokstäver inte trycks ihop. samma gradient används i footer:n
        # för konsistens.
        monogram_text = _jsx_safe_string(company["name"][:2])
        header_logo_jsx = (
            '              <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--primary)] to-[color:var(--accent)] text-[color:var(--primary-foreground)] text-[11px] font-bold uppercase tracking-wider shadow-sm ring-1 ring-[color:var(--primary)]/20">'
            f"{monogram_text}</span>"
        )
        footer_logo_jsx = (
            '              <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-[color:var(--primary)] to-[color:var(--accent)] text-[color:var(--primary-foreground)] text-xs font-bold uppercase tracking-wider shadow-sm mb-2">'
            f"{monogram_text}</span>"
        )

    # Fas 1.6 — favicon + Open Graph + Apple touch-icon. Vi använder
    # Next.js Metadata API:s `icons` och `openGraph.images` så headern
    # genereras automatiskt utan att vi behöver injicera <link>/<meta>
    # i body:n. Saknas asset:n hoppas fältet — Next.js default-favicon
    # (eller den som ligger i ``public/favicon.ico``) tar över.
    favicon_asset = resolve_media_asset(dossier, "favicon")
    og_image_asset = resolve_media_asset(dossier, "ogImage")
    metadata_extras: list[str] = []
    if isinstance(favicon_asset, dict) and favicon_asset.get("filename"):
        favicon_url = "/uploads/" + str(favicon_asset["filename"])
        # ``apple-touch-icon`` ska helst vara 180×180 PNG. Vi använder
        # samma asset eftersom operatör-uppladdade favicons normalt har
        # högre upplösning än 32×32. Browsern resize:ar utan tappad kvalitet.
        metadata_extras.append(
            "  icons: {\n"
            f"    icon: {_js_string_literal(favicon_url)},\n"
            f"    apple: {_js_string_literal(favicon_url)},\n"
            "  },\n"
        )
    # Sprint 1.5 — använd operator-uppladdad og-image om den finns,
    # annars fallback till generated SVG-kort (skrivs av write_pages
    # till public/og-image-fallback.svg). På så sätt har VARJE genererad
    # sajt en delningsfärdig preview-bild från första bygget.
    if isinstance(og_image_asset, dict) and og_image_asset.get("filename"):
        og_url = "/uploads/" + str(og_image_asset["filename"])
        og_alt = og_image_asset.get("alt") or company["tagline"] or company["name"]
        og_image_type_block = ""
    else:
        og_url = "/og-image-fallback.svg"
        og_alt = company["tagline"] or company["name"]
        # SVG-fallback: explicit ``type`` så Next.js Metadata API
        # serialiserar det som image/svg+xml i meta-taggen. Vissa
        # äldre social-parsers använder type-hinten istället för att
        # sniffa MIME från Content-Type.
        og_image_type_block = '        type: "image/svg+xml",\n'
    metadata_extras.append(
        "  openGraph: {\n"
        f"    title: {_js_string_literal(company['name'])},\n"
        f"    description: {_js_string_literal(company['tagline'])},\n"
        "    images: [\n"
        "      {\n"
        f"        url: {_js_string_literal(og_url)},\n"
        f"        alt: {_js_string_literal(og_alt)},\n"
        "        width: 1200,\n"
        "        height: 630,\n"
        f"{og_image_type_block}"
        "      },\n"
        "    ],\n"
        "  },\n"
        "  twitter: {\n"
        '    card: "summary_large_image",\n'
        f"    title: {_js_string_literal(company['name'])},\n"
        f"    description: {_js_string_literal(company['tagline'])},\n"
        f"    images: [{_js_string_literal(og_url)}],\n"
        "  },\n"
    )
    metadata_extras_block = "".join(metadata_extras)

    # Fas 2.4 — themeColor + viewport. ``theme-color`` påverkar mobil
    # adress-fält och Android task-switcher; vi använder brand.primaryColorHex
    # när den finns och faller tillbaka till ett neutralt ljust värde
    # som matchar default --background. Detta gör att mobilen visuellt
    # ankrar mot sajtens identitet redan innan första paint.
    brand = dossier.get("brand") or {}
    primary_hex_raw = (
        brand.get("primaryColorHex") if isinstance(brand, dict) else None
    )
    theme_color_hex = _normalise_hex_color(primary_hex_raw) or "#ffffff"
    viewport_block = (
        "\n"
        "export const viewport: Viewport = {\n"
        f"  themeColor: {_js_string_literal(theme_color_hex)},\n"
        "};\n"
        "\n"
    )

    return (
        'import type { Metadata, Viewport } from "next";\n'
        'import { Geist, Geist_Mono } from "next/font/google";\n'
        'import { Mail, MapPin, Phone } from "lucide-react";\n'
        'import "./globals.css";\n'
        "\n"
        "const geistSans = Geist({\n"
        '  variable: "--font-geist-sans",\n'
        '  subsets: ["latin"],\n'
        "});\n"
        "\n"
        "const geistMono = Geist_Mono({\n"
        '  variable: "--font-geist-mono",\n'
        '  subsets: ["latin"],\n'
        "});\n"
        "\n"
        "export const metadata: Metadata = {\n"
        f"  title: {_js_string_literal(company['name'])},\n"
        f"  description: {_js_string_literal(company['tagline'])},\n"
        f"{metadata_extras_block}"
        "};\n"
        f"{viewport_block}"
        "export default function RootLayout({\n"
        "  children,\n"
        "}: Readonly<{\n"
        "  children: React.ReactNode;\n"
        "}>) {\n"
        "  return (\n"
        "    <html\n"
        '      lang="sv"\n'
        "      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}\n"
        "    >\n"
        # Sprint 1.1 — preconnect + dns-prefetch till Google Fonts.
        # ``variant_css`` skickar ett ``@import url(fonts.googleapis.com)``
        # in i globals.css; preconnect:en låter browsern öppna TCP +
        # TLS-handskakningar parallellt med HTML-parsningen, vilket
        # raderar 300-700 ms från LCP enligt webvitals.
        #
        # `crossOrigin="anonymous"` på `fonts.gstatic.com` är obligatoriskt
        # eftersom font-filerna serveras med CORS — utan attributet öppnar
        # browsern en ny anslutning för font-fetchen och preconnect-en gör
        # ingenting. Detta är samma mönster Google själv dokumenterar.
        #
        # Sprint 2.1 — JSON-LD LocalBusiness. Inline-script i <head>
        # så Google + Bing + DuckDuckGo plockar upp markeringen direkt
        # vid första crawl. dangerouslySetInnerHTML är säkert här
        # eftersom innehållet är förseraliserad JSON med ``</`` →
        # ``<\/``-escape (se _render_structured_data_jsonld).
        "      <head>\n"
        '        <link rel="preconnect" href="https://fonts.googleapis.com" />\n'
        '        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />\n'
        '        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />\n'
        '        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: '
        + _js_string_literal(_render_structured_data_jsonld(dossier))
        + " }} />\n"
        # Sprint 5 — runtime CSS-token-listener. Tar emot postMessage
        # från Sajtbyggarens Site Inspector (TokensTab) och uppdaterar
        # CSS custom properties direkt på <html>-elementet, vilket
        # låter operatören se färgändringar utan en ny build.
        #
        # Säkerhetsmodell:
        #   * Strikt event-type-filter (``"sajtbyggaren:set-token"``).
        #     Vi accepterar inte vilket meddelande som helst — bara
        #     vårt eget namespace, så random extensions och tredje
        #     parts iframes kan inte påverka sajten.
        #   * Värdet valideras med en exakt ``#RRGGBB`` regex
        #     (hex-färg). Övriga payloads ignoreras tyst.
        #   * Token-namnet whitelist:as (primary/accent/background/
        #     foreground) så ingen kan injicera arbiträra CSS-vars
        #     som ``--font-family-system`` eller liknande.
        #   * Värsta-fall vid missbruk: sajten ser tillfälligt ful
        #     ut i den browser där meddelandet skickades. Ingen
        #     XSS, ingen exfiltration, ingen persistence — page
        #     reload återställer canonical.
        #
        # Scriptet är hårdkodad konstant — innehåller ingen operator-
        # data — så ``dangerouslySetInnerHTML`` är säkert.
        "        <script dangerouslySetInnerHTML={{ __html: "
        + _js_string_literal(_RUNTIME_TOKEN_LISTENER_JS)
        + " }} />\n"
        "      </head>\n"
        '      <body className="min-h-full flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">\n'
        # Sprint 2.5 — skip-link. Visuellt dolda tills den får fokus
        # (tab från adressfältet) sen popup:ar den högst upp till
        # vänster med stark kontrast. Detta är WCAG 2.1 SC 2.4.1
        # ("Bypass Blocks") och en av de få a11y-features som även
        # tangentbordsanvändare utan screen-reader använder dagligen.
        # `focus:not-sr-only` är den standardiserade Tailwind-pattern
        # för exakt detta beteende.
        '        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[color:var(--primary)] focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-[color:var(--primary-foreground)] focus:shadow-lg focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-[color:var(--primary)]">Hoppa till innehållet</a>\n'
        '        <header className="sticky top-0 z-40 border-b border-[color:var(--border)] bg-[color:var(--background)]/80 backdrop-blur supports-[backdrop-filter]:bg-[color:var(--background)]/60">\n'
        '          <div className="mx-auto flex w-[var(--container-width)] items-center justify-between gap-6 py-4">\n'
        '            <a href="/" className="flex items-center gap-2 text-base font-semibold">\n'
        f"{header_logo_jsx}\n"
        f'              <span className="hidden sm:inline">{_jsx_safe_string(company["name"])}</span>\n'
        "            </a>\n"
        '            <nav className="flex items-center gap-5 text-sm font-medium">\n'
        f"{nav_links}\n"
        "            </nav>\n"
        f'            <a href={contact_href} className="hidden md:inline-flex items-center gap-1 rounded-md bg-[color:var(--primary)] px-4 py-2 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">Kontakta oss</a>\n'
        "          </div>\n"
        "        </header>\n"
        # Sprint 2.4/2.5 — skip-link-mål.
        # Varje page-renderer (render_home, render_services, …) har
        # redan en egen ``<main>``-tag. Dubbla ``<main>``-element är
        # ogiltig HTML och förvirrar screen-readers, så layout-
        # wrappern stannar som ``<div>``. ``id="main-content"`` matchar
        # skip-link:en ovan och ``tabIndex={-1}`` gör att fokus
        # verkligen flyttas dit när användaren aktiverar länken
        # (annars hoppar fokus tillbaka till body i Chromium-baserade
        # browsers eftersom <div> inte är fokuserbar by default).
        '        <div id="main-content" tabIndex={-1} className="flex-1 outline-none">{children}</div>\n'
        '        <footer className="border-t border-[color:var(--border)] bg-[color:var(--background)]">\n'
        '          <div className="mx-auto grid w-[var(--container-width)] gap-8 py-12 md:grid-cols-3">\n'
        '            <div className="flex flex-col gap-3">\n'
        + (f"{footer_logo_jsx}\n" if footer_logo_jsx else "")
        + f'              <p className="text-base font-semibold">{_jsx_safe_string(company["name"])}</p>\n'
        f'              <p className="text-sm text-[color:var(--muted)]">{_jsx_safe_string(company["tagline"])}</p>\n'
        "            </div>\n"
        '            <div className="flex flex-col gap-2 text-sm">\n'
        '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>\n'
        f'              <a href={_jsx_safe_string("tel:" + _phone_href(contact["phone"]))} className="inline-flex items-center gap-2 hover:underline"><Phone className="size-4" />{_jsx_safe_string(contact["phone"])}</a>\n'
        f'              <a href={_jsx_safe_string("mailto:" + contact["email"])} className="inline-flex items-center gap-2 hover:underline"><Mail className="size-4" />{_jsx_safe_string(contact["email"])}</a>\n'
        f'              <p className="inline-flex items-start gap-2 text-[color:var(--muted)]"><MapPin className="size-4 mt-0.5" />{_jsx_safe_string(address_line)}</p>\n'
        "            </div>\n"
        '            <div className="flex flex-col gap-2 text-sm text-[color:var(--muted)]">\n'
        '              <p className="text-xs uppercase tracking-widest">Sajt</p>\n'
        + "\n".join(
            f'              <a href={_route_href(href)} className="hover:underline">{_jsx_safe_string(label)}</a>'
            for href, label in nav_items
        )
        + "\n"
        "            </div>\n"
        "          </div>\n"
        '          <div className="border-t border-[color:var(--border)] py-4">\n'
        f'            <p className="mx-auto w-[var(--container-width)] text-xs text-[color:var(--muted)]">© {{new Date().getFullYear()}} {_jsx_safe_string(company["name"])}. Alla rättigheter förbehållna.</p>\n'
        "          </div>\n"
        "        </footer>\n"
        "      </body>\n"
        "    </html>\n"
        "  );\n"
        "}\n"
    )


def render_home(
    dossier: dict,
    dossier_routes: list[str],
    *,
    listing_route: dict | None = None,
    contact_path: str = "/kontakt",
    variant_id: str | None = None,
) -> str:
    """Home page renderer.

    ``listing_route`` is the scaffold's primary listing surface
    (``{"id": "services", "path": "/tjanster"}`` for
    local-service-business, ``{"id": "products", "path": "/produkter"}``
    for ecommerce-lite). When ``None`` the renderer keeps the listing
    section content but omits the cross-link rather than inventing a
    route that may not exist.

    The pre-B13 B30 unit tests in
    ``tests/test_builder_audit_post_3b_next.py`` call
    ``render_home(dossier, dossier_routes=...)`` directly to exercise
    JSX escaping and depend on the service/product grid being rendered.
    Keeping the section but dropping the CTA preserves those tests
    without creating a ghost route.
    """
    company = dossier["company"]
    location = dossier["location"]
    services = dossier["services"]
    trust = dossier["trustSignals"]
    contact = dossier["contact"]
    icons_used = _collect_icons_for_pages(services, dossier_routes)
    # USPs propagate either from dossier.uniqueSellingPoints (when the
    # backend has been updated to pass it through) or from
    # dossier.directives.uniqueSellingPoints (when the v2 directives
    # block lives on dossier). Empty list = no chips rendered.
    usp_list = _extract_usps(dossier)
    if usp_list and "Check" not in icons_used:
        icons_used = sorted({*icons_used, "Check"})
    # Story + testimonials home-sections both use the ``Quote`` glyph.
    # We whitelist it whenever either section is going to render, so
    # the icon-import line stays in sync with the JSX below. The
    # corresponding short-circuit helpers (_render_home_story_section,
    # _render_home_testimonials_section) themselves return "" when
    # their inputs are empty, so this whitelist is harmless if the
    # dossier ends up with no story and no testimonials.
    story_text = (dossier.get("company") or {}).get("story") or ""
    trust_count = sum(
        1
        for item in (dossier.get("trustSignals") or [])
        if isinstance(item, str) and item.strip()
    )
    needs_quote_icon = bool(str(story_text).strip()) or trust_count >= _HOME_TESTIMONIAL_MIN_ITEMS
    if needs_quote_icon and "Quote" not in icons_used:
        icons_used = sorted({*icons_used, "Quote"})
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    # Fas 2.3 — hover-effekt med translate-y och förbättrad shadow.
    # Ikonen lyfts samtidigt för en sammanhängande Apple-känsla.
    services_grid = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--card,var(--background))] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'              <span className="mb-4 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)] transition-transform group-hover:scale-105"><{_icon_for_service(svc["id"])} className="size-5" /></span>\n'
        f'              <h3 className="text-lg font-semibold">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    trust_items = "\n".join(
        f'            <li key="trust-{i}" className="flex items-start gap-3">\n'
        f'              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-[color:var(--primary)]" />\n'
        f'              <span className="text-base">{_jsx_safe_string(item)}</span>\n'
        "            </li>"
        for i, item in enumerate(trust)
    )
    trust_section = ""
    if trust:
        trust_section = (
            '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/20">\n'
            '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]">\n'
            '          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Varför oss</h2>\n'
            '          <ul className="grid gap-4 md:grid-cols-2">\n'
            f"{trust_items}\n"
            "          </ul>\n"
            "        </div>\n"
            "      </section>\n"
            "\n"
        )
    spel_cta = (
        '          <a href="/spel" className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Gamepad2 className="size-4" />Spela direkt</a>\n'
        if "/spel" in dossier_routes
        else ""
    )
    contact_href = _route_href(contact_path)
    # Branch-specifik listing-copy: när dossiern har en businessType som
    # finns i ``_BRANCH_LISTING_COPY`` använder vi den (t.ex. "Menyn" /
    # "Det vi serverar" för restaurang) istället för den generiska
    # route-id-baserade copy:n. Faller tillbaka till routebaserad copy
    # för okända branscher så befintliga tester och dossiers utan
    # businessType fortsätter funka.
    listing_copy = _LISTING_COPY_BY_ROUTE_ID["services"]
    branch_copy = _branch_listing_copy(dossier)
    if listing_route is not None:
        listing_copy = _LISTING_COPY_BY_ROUTE_ID.get(
            listing_route["id"], _LISTING_COPY_BY_ROUTE_ID["services"]
        )
    if branch_copy:
        # Branch-copy vinner över route-baserad copy — branschen är
        # närmare operatörens verklighet än scaffold-typen.
        listing_copy = {**listing_copy, **branch_copy}
    listing_link = ""
    if listing_route is not None:
        listing_href = _route_href(listing_route["path"])
        listing_link = f'          <a href={listing_href} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">{listing_copy["cta"]}<ArrowRight className="size-4" /></a>\n'
    # Demo-baseline-fix 1C (B95): suppress the hero ortstag when the
    # location is country-only (no real city, see _placeholder_location).
    location_tag = ""
    if not _location_is_country_only(location):
        location_tag = (
            '          <div className="flex items-center gap-2 text-sm uppercase tracking-widest text-[color:var(--muted)]">\n'
            '            <MapPin className="size-4" />\n'
            f"            <span>{_jsx_safe_string(location['city'])}</span>\n"
            "          </div>\n"
        )
    # Demo-baseline-fix 1C (B96): hero CTA label is scaffold-aware
    # (shop / booking / quote) so e-commerce projects do not get a
    # service-business "Begär offert" verb in the hero.
    hero_cta_label = _hero_cta_label(dossier)
    # B101 (re-Verifierings-Scout 3 2026-05-18): when CTA is shop the
    # primary hero button must link to the products listing, not the
    # contact route. Booking and quote variants keep contact as target.
    hero_cta_href = _route_href(
        _hero_cta_target_path(dossier, listing_route, contact_path)
    )

    # Operator-uploaded hero image (if present) renders as a banner
    # above the gradient section. The asset is placed in public/uploads/
    # by copy_operator_uploads. We render a raw <img> (not next/image)
    # because the webp files are pre-compressed by sharp and the
    # starters ship without a Next.js Image loader config.
    #
    # Sprint 1.3 — LCP boost: hero-bilden är typiskt Largest Contentful
    # Paint. Tre attribut tillsammans ger ~700ms LCP-vinst utan att
    # introducera next/image-import:
    #   * fetchPriority="high" — säger åt browsern att prioritera nedladdning
    #     före andra subresources (CSS-bakgrunder, lazy-bilder)
    #   * loading="eager" — explicit (default är eager, men explicit är
    #     defensivt mot framtida change i browser-defaults)
    #   * decoding="async" — paint sker utan att blockera main thread
    #     på image-decode (annars kan en stor JPEG blocka 80-200ms)
    brand_block = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    hero_asset = brand_block.get("heroImage") if isinstance(brand_block, dict) else None
    hero_section_jsx = ""
    if isinstance(hero_asset, dict) and hero_asset.get("filename"):
        hero_filename = hero_asset["filename"]
        hero_alt = hero_asset.get("alt") or company["tagline"]
        hero_section_jsx = (
            '      <section className="relative w-full overflow-hidden bg-[color:var(--background)]">\n'
            '        <div className="mx-auto w-[var(--container-width)] pt-[var(--section-spacing)]">\n'
            f'          <img src={_jsx_safe_string("/uploads/" + hero_filename)} alt={_js_string_literal(hero_alt)} fetchPriority="high" loading="eager" decoding="async" className="aspect-[16/9] w-full rounded-2xl object-cover shadow-sm" />\n'
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    # Visual proof block placed between services and trust: shows the
    # operator's uploaded gallery images so the home page does not lean
    # only on textual trust signals. Returns "" when no gallery items
    # exist so the section never leaks placeholder copy.
    gallery_section = _render_home_gallery_section(dossier)

    # A1 — Story-sektion: enkel quote-card med ``company.story``.
    # Returnerar "" när story saknas, vilket är det normala för dossiers
    # där mockBrief inte fyllt i något.
    story_section = _render_home_story_section(dossier)

    # A2 — Testimonials-sektion: render trustSignals som riktiga kort
    # när det finns ≥ ``_HOME_TESTIMONIAL_MIN_ITEMS`` items. Annars ""
    # och vi behåller den klassiska ``trust_section`` (bullet-listan
    # ovan) som fallback.
    testimonials_section = _render_home_testimonials_section(dossier)
    # När testimonials har renderats, dropp:a den klassiska
    # ``trust_section`` för att inte visa samma info två gånger.
    if testimonials_section:
        trust_section = ""

    # A3 — FAQ-sektion: deterministisk render från ``_faq_pairs``.
    # När /faq-routen är aktiverad i ``dossier_routes`` renderar vi en
    # "Se alla frågor"-CTA, annars bara griden.
    has_faq_route = "/faq" in dossier_routes
    faq_section = _render_home_faq_section(dossier, has_faq_route=has_faq_route)

    # Variant-aware hero layout. Resolves to one of three layouts
    # (gradient/centered/split) based on directives.layoutHint or
    # variant_id; falls back to gradient when neither is set, which
    # matches the pre-#2 baseline so legacy callers (tests without a
    # variant_id) keep their expected JSX shape.
    # C1 — Unsplash-fallback för split-layouten. Pre-resolved här så
    # ``_render_hero_block`` slipper röra dossiern. Returnerar ``None``
    # när business-typ saknar en kuraterad photo-ID i mappningen, vilket
    # behåller den befintliga accent-tinted-fallbacken.
    unsplash_fallback_url = _unsplash_hero_url(dossier)
    # Fas 1.6 — background_video är optional. Operatören laddar upp en
    # mp4/webm i wizardens MediaStep; build_site.py renderar den som
    # absolut-positionerat ``<video>`` bakom hero-texten med poster
    # fallback mot hero-bilden. Saknas videon renderas hero som vanligt.
    hero_video_asset = resolve_media_asset(dossier, "backgroundVideo")
    hero_block_jsx = _render_hero_block(
        _hero_style_for(dossier, variant_id),
        company=company,
        location_tag=location_tag,
        hero_cta_label=hero_cta_label,
        hero_cta_href=hero_cta_href,
        contact_phone=contact["phone"],
        spel_cta=spel_cta,
        hero_asset=hero_asset,
        usps=usp_list,
        unsplash_fallback_url=unsplash_fallback_url,
        background_video=hero_video_asset,
    )

    return (
        icon_import + "\n"
        "export default function Home() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        f"{hero_section_jsx}"
        f"{hero_block_jsx}"
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{listing_copy["eyebrow"]}</p>\n'
        f'            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">{listing_copy["heading"]}</h2>\n'
        "          </div>\n"
        '          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{services_grid}\n"
        "          </ul>\n"
        f"{listing_link}"
        "        </div>\n"
        "      </section>\n"
        "\n"
        f"{story_section}"
        f"{gallery_section}"
        f"{testimonials_section}"
        f"{trust_section}"
        f"{faq_section}"
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--primary)] text-[color:var(--primary-foreground)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Hör av dig idag</h2>\n'
        '          <p className="max-w-2xl text-base opacity-90 md:text-lg">Beskriv kort vad du behöver så återkommer vi inom en arbetsdag.</p>\n'
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary-foreground)] px-5 py-3 text-sm font-medium text-[color:var(--primary)] hover:opacity-90 transition-opacity">Kontakta oss<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_services(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
) -> str:
    services = dossier["services"]
    contact_href = _route_href(contact_path)
    icons_used = sorted({_icon_for_service(svc["id"]) for svc in services} | {"ArrowRight"})
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    items = "\n".join(
        f'          <article key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(svc["id"])} className="size-6" /></span>\n'
        f'            <h2 className="text-xl font-semibold">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "          </article>"
        for svc in services
    )
    # Demo-baseline-fix 1C (B96): keep the bottom-of-page CTA on
    # render_services aligned with the hero CTA verb so a booking-driven
    # service business (e.g. frisör) reads "Boka tid" everywhere.
    cta_label = _hero_cta_label(dossier)
    return (
        icon_import + "\n"
        "export default function ServicesPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Tjänster</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vad vi gör</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Allt vi erbjuder, samlat på ett ställe. Klicka på en tjänst eller hör av dig direkt.</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_about(dossier: dict) -> str:
    company = dossier["company"]
    team = company.get("team", [])
    location = dossier["location"]
    areas_html = ", ".join(location["serviceAreas"])
    location_section = ""
    if not _location_is_country_only(location):
        location_section = (
            '          <div className="flex flex-col gap-2">\n'
            '            <h2 className="inline-flex items-center gap-2 text-2xl font-semibold tracking-tight"><MapPin className="size-5" />Områden vi arbetar i</h2>\n'
            f'            <p className="text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(areas_html)}</p>\n'
            "          </div>\n"
        )
    # Demo-baseline-fix 1C (B94): skip the entire team section when no
    # team members are declared, mirroring B66's trustSignals fix.
    # Previously the renderer emitted "Teamet" + an empty <ul>, which
    # surfaced on every generated /om-oss page in the re-Verifierings-
    # Scout 2026-05-15 run because prompt_to_project_input.py never
    # populates team.
    team_section = ""
    if team:
        team_items = "\n".join(
            f'            <li key={_jsx_safe_string(member["name"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-foreground)] text-sm font-semibold uppercase">{_jsx_safe_string(_member_initials(member["name"]))}</span>\n'
            f'              <p className="text-base font-semibold">{_jsx_safe_string(member["name"])}</p>\n'
            f'              <p className="mt-1 text-sm text-[color:var(--muted)]">{_jsx_safe_string(member["role"])}</p>\n'
            "            </li>"
            for member in team
        )
        team_section = (
            '          <div className="flex flex-col gap-4">\n'
            '            <h2 className="text-2xl font-semibold tracking-tight">Teamet</h2>\n'
            '            <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            f"{team_items}\n"
            "            </ul>\n"
            "          </div>\n"
        )

    # Gallery images with placement="about" (or no placement, but we
    # restrict ourselves to about so we do not overload /om-oss).
    # The images come from operator upload via copy_operator_uploads.
    gallery_items = dossier.get("gallery") or []
    about_images = [
        item
        for item in gallery_items
        if isinstance(item, dict)
        and item.get("filename")
        and (item.get("placement") in (None, "about"))
    ]
    gallery_section_jsx = ""
    if about_images:
        gallery_cards = "\n".join(
            f'            <figure key={_jsx_safe_string(item["assetId"])} className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[color:var(--background)]">\n'
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company["name"])} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover" />\n'
            "            </figure>"
            for item in about_images
        )
        gallery_section_jsx = (
            '          <div className="flex flex-col gap-4">\n'
            '            <h2 className="text-2xl font-semibold tracking-tight">Galleri</h2>\n'
            '            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            f"{gallery_cards}\n"
            "            </div>\n"
            "          </div>\n"
        )
    return (
        'import { MapPin, Quote } from "lucide-react";\n'
        "\n"
        "export default function AboutPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Om oss</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(company["name"])}</h1>\n'
        "          </header>\n"
        '          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
        '            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/20" />\n'
        f'            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{_jsx_safe_string(company["story"])}</p>\n'
        "          </div>\n"
        f"{team_section}"
        f"{gallery_section_jsx}"
        f"{location_section}"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_contact(dossier: dict) -> str:
    contact = dossier["contact"]
    address_lines = "\n".join(
        f'                <span className="block">{_jsx_safe_string(line)}</span>'
        for line in contact["addressLines"]
    )
    return (
        'import { Clock, Mail, MapPin, Phone } from "lucide-react";\n'
        "\n"
        "export default function ContactPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Hör av dig</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Beskriv jobbet kort så återkommer vi inom en arbetsdag med tider och offert.</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2">\n'
        '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Phone className="size-5" /></span>\n'
        '              <h2 className="text-base font-semibold">Telefon</h2>\n'
        f'              <a href={_jsx_safe_string("tel:" + _phone_href(contact["phone"]))} className="mt-2 block text-lg font-medium hover:underline">{_jsx_safe_string(contact["phone"])}</a>\n'
        '              <p className="mt-2 inline-flex items-center gap-2 text-sm text-[color:var(--muted)]">\n'
        '                <Clock className="size-4" />\n'
        f"                <span>{_jsx_safe_string(contact['openingHours'])}</span>\n"
        "              </p>\n"
        "            </article>\n"
        '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Mail className="size-5" /></span>\n'
        '              <h2 className="text-base font-semibold">E-post</h2>\n'
        f'              <a href={_jsx_safe_string("mailto:" + contact["email"])} className="mt-2 block text-lg font-medium hover:underline">{_jsx_safe_string(contact["email"])}</a>\n'
        "            </article>\n"
        '            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">\n'
        '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
        '              <h2 className="text-base font-semibold">Adress</h2>\n'
        '              <address className="mt-2 not-italic">\n'
        f"{address_lines}\n"
        "              </address>\n"
        "            </article>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_products(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
) -> str:
    """Products-page renderer for ecommerce-lite (B13 route-emission).

    Reads the ``services`` array from the Project Input. The schema
    keeps the field named ``services`` because the renderer reads
    the same id/label/summary tuple regardless of scaffold; the
    rename to a dedicated ``products`` field is deliberately left
    for the next sprint that flips ``SCAFFOLD_TO_STARTER`` to
    ``commerce-base`` (current focus: B13 is route-emission only).

    ``contact_path`` defaults to ``/kontakt`` so direct unit tests
    still produce a valid href. write_pages threads the scaffold's
    actual contact route in so a scaffold that moves contact to
    ``/kontakta-oss`` keeps the CTA aligned with the nav (Bugbot PR
    #19 follow-up).
    """
    products = dossier["services"]
    contact_href = _route_href(contact_path)
    icons_used = sorted(
        {_icon_for_service(item["id"]) for item in products} | {"ArrowRight", "ShoppingBag"}
    )
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    items = "\n".join(
        f'          <article key={_jsx_safe_string(item["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(item["id"])} className="size-6" /></span>\n'
        f'            <h2 className="text-xl font-semibold">{_jsx_safe_string(item["label"])}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(item["summary"])}</p>\n'
        "          </article>"
        for item in products
    )
    # B102 (re-Verifierings-Scout 3 2026-05-18): shop-flavoured bottom-CTA.
    # Länken mot kontakt-routen behålls eftersom builder MVP inte har
    # checkout, men verbet ("Hör av dig för att beställa") matchar
    # shop-tonen från hero ("Shoppa nu") i stället för offert-känslan
    # i den gamla copyn "Fråga om en beställning".
    bottom_cta_label = _commerce_bottom_cta_label(dossier)
    return (
        icon_import + "\n"
        "export default function ProductsPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Produkter</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vårt sortiment</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Här är våra produkter. Hör av dig om du undrar något så hjälper vi dig hela vägen till beställning.</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><ShoppingBag className="size-4" />{bottom_cta_label}<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


# ---------------------------------------------------------------------------
# Wizard-driven extra routes (B132 follow-up sprint 2026-05-21)
#
# The new routes share a few small helpers: every renderer ends in a
# contact CTA that uses the scaffold's threaded contact_path, a section
# heading uses the same eyebrow/h1 idiom as the existing service/about
# pages, and every customer-supplied string goes through
# _jsx_safe_string so JSX-special characters cannot break the build.
#
# The renderers stay deterministic and integration-free: no booking
# layer, no payments, no editorial CMS. They read what is already in
# the Project Input dossier (services, contact, location, gallery,
# team, trustSignals) and rely on Swedish "vi har inget att visa här
# ännu, hör av dig"-fallbacks when the dossier does not have data.
# That keeps the operator promise honest: a route exists, the visitor
# does not hit a 404, and the page never invents customer-specific
# content the operator did not authorise.
# ---------------------------------------------------------------------------


def _wizard_section_heading(
    eyebrow: str,
    heading: str,
    intro: str | None = None,
) -> str:
    """Reusable hero-style header for the wizard-route renderers.

    Matches the eyebrow + h1 idiom of the existing about/services
    pages so the new routes feel consistent with the rest of the
    generated site. ``intro`` renders as a muted lead paragraph and
    is dropped when empty.
    """
    intro_jsx = ""
    if intro:
        intro_jsx = (
            '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">'
            f"{_jsx_safe_string(intro)}</p>\n"
        )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(eyebrow)}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(heading)}</h1>\n'
        f"{intro_jsx}"
        "          </header>\n"
    )


def _wizard_contact_cta(dossier: dict, contact_path: str) -> str:
    """Trailing contact CTA used by every wizard-route renderer.

    Re-uses ``_hero_cta_label`` so booking-driven businesses say
    "Boka tid" instead of "Begär offert" on /priser and /portfolio,
    matching the home/services pages. Mirrors the route-href guard
    discipline from B50 (path goes through ``_route_href``).
    """
    cta_href = _route_href(contact_path)
    cta_label = _hero_cta_label(dossier)
    return (
        '          <div>\n'
        f'            <a href={cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        "          </div>\n"
    )


def _wizard_page_footer() -> str:
    """Closing tags shared by every wizard-route renderer."""
    return (
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


_FAQ_DEFAULT_SV: list[tuple[str, str]] = [
    (
        "Hur snabbt får jag svar?",
        "Vi återkommer normalt inom en arbetsdag på telefon och e-post.",
    ),
    (
        "Kostar det något att höra av sig?",
        "Nej, vi tar inte betalt för en första kontakt eller en kostnadsfri offert.",
    ),
    (
        "Vilka områden täcker ni?",
        "Vi jobbar i {areas}. Kontakta oss om du är osäker på om vi täcker just din adress.",
    ),
]


def _faq_pairs(dossier: dict) -> list[tuple[str, str]]:
    """Compose FAQ items from the dossier without inventing facts."""
    location = dossier.get("location") or {}
    area_values = location.get("serviceAreas") if isinstance(location, dict) else None
    if isinstance(area_values, list) and area_values:
        areas = ", ".join(str(area) for area in area_values if isinstance(area, str))
    else:
        city = location.get("city") if isinstance(location, dict) else None
        country = location.get("country") if isinstance(location, dict) else None
        areas = str(city or country or "ditt närområde")
    pairs: list[tuple[str, str]] = []
    for question, answer_template in _FAQ_DEFAULT_SV:
        pairs.append((question, answer_template.format(areas=areas)))
    contact = dossier.get("contact") or {}
    opening = contact.get("openingHours") if isinstance(contact, dict) else None
    if isinstance(opening, str) and opening.strip():
        pairs.append(
            (
                "När har ni öppet?",
                f"Vi har öppet {opening.strip()}.",
            )
        )
    return pairs


def render_faq(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /faq route.

    Deterministic FAQ built from the dossier: three default questions
    plus an opening-hours question when ``contact.openingHours`` is
    set. No invented service prices or warranties — operator-specific
    answers belong on the operator's wishlist, not in v1 codegen.
    """
    pairs = _faq_pairs(dossier)
    items = "\n".join(
        f'            <article key={_jsx_safe_string(f"faq-{i}")} className="rounded-xl border border-[color:var(--border)] p-6">\n'
        f'              <h2 className="text-lg font-semibold">{_jsx_safe_string(question)}</h2>\n'
        f'              <p className="mt-2 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(answer)}</p>\n'
        "            </article>"
        for i, (question, answer) in enumerate(pairs)
    )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function FaqPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Vanliga frågor",
            "Det vi får höra ofta",
            "Korta svar på de frågor våra kunder ställer oftast. "
            "Saknas något du undrar över? Hör av dig så svarar vi.",
        )
        + '          <div className="grid gap-3 md:grid-cols-2">\n'
        + items
        + "\n          </div>\n"
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def _gallery_images(dossier: dict) -> list[dict]:
    items = dossier.get("gallery") or []
    selected: list[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("filename"):
                selected.append(item)
    return selected


_HOME_GALLERY_MAX_ITEMS = 6

# Antal FAQ-frågor som visas i den kompakta home-sektionen. Tre matchar
# 2/3-kolumns-griden och håller sektionen visuellt snäv; resterande
# frågor (när /faq-routen aktiveras) lever på dedikerade sidan så
# operatören inte tappar information.
_HOME_FAQ_MAX_ITEMS = 4

# Minsta antal trustSignals för att rendra dem som riktiga testimonial-
# kort istället för bullet-list. Under detta tröskelvärde faller vi
# tillbaka på den befintliga ``trust_section`` i ``render_home`` (en
# enkel checkbox-lista) eftersom 1–2 punkter inte fyller ett 3-kolumns-
# grid och kort skulle se underbefolkat ut.
_HOME_TESTIMONIAL_MIN_ITEMS = 3


# Branch/business-type-specifik listing-copy. När operatören har en
# typisk restaurant/retail/service/medical-typ vill vi att rubriken
# på home-sidans listing-sektion (services-grid) känns relevant för
# branschen istället för den generiska "Vad vi tar oss an". Mappningen
# läses i ``_branch_listing_copy``; om business-typ saknas eller inte
# matchar någon nyckel faller vi tillbaka på ``_LISTING_COPY_BY_ROUTE_ID``
# (route-id-baserade copy). Värdena är medvetet mjuka och beskrivande,
# inte säljiga, för att inte krocka med variant-tonen.
_BRANCH_LISTING_COPY: dict[str, dict[str, str]] = {
    "restaurant": {
        "eyebrow": "Menyn",
        "heading": "Det vi serverar",
        "cta": "Se hela menyn",
    },
    "cafe": {
        "eyebrow": "Menyn",
        "heading": "Smaker från oss",
        "cta": "Se hela menyn",
    },
    "bakery": {
        "eyebrow": "Sortimentet",
        "heading": "Det vi bakar",
        "cta": "Se hela sortimentet",
    },
    "retail": {
        "eyebrow": "Sortimentet",
        "heading": "Det vi säljer",
        "cta": "Se hela sortimentet",
    },
    "e-commerce": {
        "eyebrow": "Sortimentet",
        "heading": "Vårt sortiment",
        "cta": "Se alla produkter",
    },
    "salon": {
        "eyebrow": "Behandlingar",
        "heading": "Det vi gör",
        "cta": "Se alla behandlingar",
    },
    "barbershop": {
        "eyebrow": "Behandlingar",
        "heading": "Det vi gör",
        "cta": "Se alla behandlingar",
    },
    "medical": {
        "eyebrow": "Vården",
        "heading": "Det vi hjälper med",
        "cta": "Se hela vårdutbudet",
    },
    "clinic": {
        "eyebrow": "Vården",
        "heading": "Det vi hjälper med",
        "cta": "Se hela vårdutbudet",
    },
    "consulting": {
        "eyebrow": "Erbjudandet",
        "heading": "Det vi hjälper med",
        "cta": "Se hela erbjudandet",
    },
    "agency": {
        "eyebrow": "Erbjudandet",
        "heading": "Det vi gör",
        "cta": "Se hela erbjudandet",
    },
    "fitness": {
        "eyebrow": "Träningen",
        "heading": "Det vi erbjuder",
        "cta": "Se hela utbudet",
    },
    "gym": {
        "eyebrow": "Träningen",
        "heading": "Det vi erbjuder",
        "cta": "Se hela utbudet",
    },
    "education": {
        "eyebrow": "Utbildningarna",
        "heading": "Det vi lär ut",
        "cta": "Se hela utbudet",
    },
    "hotel": {
        "eyebrow": "Boende",
        "heading": "Det vi erbjuder",
        "cta": "Se alla rum",
    },
    "real-estate": {
        "eyebrow": "Tjänster",
        "heading": "Det vi förmedlar",
        "cta": "Se hela utbudet",
    },
}


# Unsplash-fallback per business-type när operatören inte laddat upp
# en egen hero-bild i split-layouten. Vi väljer kuraterade query-strings
# (inte slumpmässiga Unsplash-bilder) så generated sites får en bild
# som åtminstone matchar branschen. Värdena är Unsplash-photo-IDn så
# vi får deterministisk rendering — random query skulle annars
# producera olika bilder mellan builds och sabotera test-snapshots.
#
# Photo-ID:n är hämtade från Unsplash Editorial collection och har
# fria-användning-licens. När operatören har laddat upp en hero-bild
# används den istället; denna fallback aktiveras bara när hero_asset
# saknas OCH variant-style är ``split`` (där en bild krävs för att
# layouten ska läsa rätt).
_UNSPLASH_HERO_BY_BRANCH: dict[str, str] = {
    "restaurant": "1414235077428-338989a2e8c0",
    "cafe": "1554118811-1e0d58224f24",
    "bakery": "1517433670267-08bbd4be890f",
    "retail": "1441986300917-64674bd600d8",
    "e-commerce": "1556909114-f6e7ad7d3136",
    "salon": "1560066984-138dadb4c035",
    "barbershop": "1503951914875-452162b0f3f1",
    "medical": "1576091160399-112ba8d25d1d",
    "clinic": "1581595220892-b0739db3ba8c",
    "consulting": "1497366216548-37526070297c",
    "agency": "1497366754035-f200968a6e72",
    "fitness": "1517836357463-d25dfeac3438",
    "gym": "1534438327276-14e5300c3a48",
    "education": "1503676260728-1c00da094a0b",
    "hotel": "1566073771259-6a8506099945",
    "real-estate": "1564013799919-ab600027ffc6",
    "construction": "1503387762-cbe48e8fc7d3",
    "automotive": "1502877338535-766e1452684a",
}


def _branch_listing_copy(dossier: dict) -> dict[str, str]:
    """Resolve branch-specific listing copy (eyebrow + heading + CTA)
    from the dossier's ``businessType``. Returns the matching
    ``_BRANCH_LISTING_COPY`` entry when business-type maps cleanly,
    otherwise ``None`` so the caller falls back on the existing
    route-id-based ``_LISTING_COPY_BY_ROUTE_ID`` lookup.

    Branch matching is case-insensitive and tolerates the
    ``"local-service-business"`` placeholder by treating it as
    "no specific branch" (returning ``None``) so the generic copy
    keeps applying.
    """
    company = dossier.get("company") or {}
    business_type = _normalize_business_type(company.get("businessType"))
    if not business_type:
        return {}
    return _BRANCH_LISTING_COPY.get(business_type, {})


def _unsplash_hero_url(dossier: dict, *, width: int = 1200, height: int = 1500) -> str | None:
    """Return a deterministic Unsplash CDN URL for the dossier's
    business-type, or ``None`` when no matching photo-ID exists. Used
    by ``_render_hero_block`` (split-layout) as a fallback when the
    operator has not uploaded their own hero image.

    The URL is built with explicit ``w=``/``h=``/``fit=crop`` params
    so Next.js can serve the right size without an Image-loader
    config, matching how operator-uploaded ``/uploads/*.webp`` files
    are rendered. ``auto=format`` lets Unsplash pick WebP/AVIF based
    on the visitor's browser headers.
    """
    company = dossier.get("company") or {}
    business_type = _normalize_business_type(company.get("businessType"))
    photo_id = _UNSPLASH_HERO_BY_BRANCH.get(business_type)
    if not photo_id:
        return None
    return (
        f"https://images.unsplash.com/photo-{photo_id}"
        f"?w={width}&h={height}&fit=crop&auto=format&q=80"
    )


_HERO_STYLE_BY_VARIANT: dict[str, str] = {
    # local-service-business
    "nordic-trust": "gradient",
    "warm-craft": "centered",
    "clinical-calm": "centered",
    "midnight-counsel": "split",
    "pulse-fit": "gradient",
    # ecommerce-lite
    "clean-store": "split",
    "earth-wellness": "centered",
    "mono-tech": "split",
    "noir-editorial": "split",
    "street-vivid": "gradient",
}

# Tone-driven fallback för hero-stil när layoutHint saknas OCH varianten
# inte har en mapping i ``_HERO_STYLE_BY_VARIANT`` (sannolikt en framtida
# experimentell variant). Mappar mot semantiska tone-keys (post-
# normalisering via ``_normalize_tone_key``), så svenska wizard-tags
# som "Lekfull" / "Exklusiv / lyxig" automatiskt får rätt stil utan
# explicit konfiguration.
#
# Sprint B/3 (2026-05-22): säkerhetsnät så ingen tone-väljare blir
# helt utan effekt på above-the-fold-upplevelsen ens om operatören
# hoppar över vibe-steget eller en framtida variant inte registrerats.
_HERO_STYLE_BY_TONE: dict[str, str] = {
    "calm": "split",
    "playful": "centered",
    "warm": "centered",
    "premium": "split",
    "luxury": "split",
    "editorial": "split",
    "bold": "gradient",
    "modern": "split",
    "tech": "split",
}

_VALID_HERO_STYLES: frozenset[str] = frozenset({"gradient", "centered", "split"})


_HERO_USP_MAX = 4


def _extract_usps(dossier: dict) -> list[str]:
    """Return up to ``_HERO_USP_MAX`` unique selling points for the hero
    chip row. Reads from two locations in priority order:

    1. ``dossier["uniqueSellingPoints"]`` — once the operator's USPs are
       propagated into Project Input by ``prompt_to_project_input.py``
       (currently blocked by ``project-input.schema.json``
       ``additionalProperties: false``; tracked as backend gap).
    2. ``dossier["directives"]["uniqueSellingPoints"]`` — the structured
       v2 directives block that lives on ``dossier`` when the brief
       persister chooses to pass it through.

    Returns ``[]`` when neither source has a non-empty list. Each item
    is trimmed and falsy values are dropped so the renderer can rely on
    every item being a printable string. The cap of four keeps the
    chip row visually balanced regardless of variant.
    """
    candidates: list[str] | None = None
    raw = dossier.get("uniqueSellingPoints")
    if isinstance(raw, list):
        candidates = [str(item).strip() for item in raw if isinstance(item, str)]
    if not candidates:
        directives = dossier.get("directives")
        if isinstance(directives, dict):
            raw = directives.get("uniqueSellingPoints")
            if isinstance(raw, list):
                candidates = [
                    str(item).strip() for item in raw if isinstance(item, str)
                ]
    if not candidates:
        return []
    return [item for item in candidates if item][:_HERO_USP_MAX]


def _render_hero_usp_chips(usps: list[str], *, centered: bool = False) -> str:
    """Render a ``<ul>`` of USP chips. Empty list collapses to ``""`` so
    the chip row is not emitted at all when the operator has no USPs.

    Each chip uses the variant's ``--accent`` background with a
    ``Check`` glyph from lucide-react so the visual weight matches the
    surrounding hero buttons without competing for attention.
    """
    if not usps:
        return ""
    align_class = "justify-center" if centered else ""
    items = "\n".join(
        f'            <li key={_jsx_safe_string("usp-" + str(i))} className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--accent)]/40 px-3 py-1 text-xs font-medium text-[color:var(--accent-foreground)]"><Check className="size-3" />{_jsx_safe_string(item)}</li>'
        for i, item in enumerate(usps)
    )
    return (
        f'          <ul className="flex flex-wrap gap-2 {align_class}">\n'
        f"{items}\n"
        "          </ul>\n"
    )


def _hero_style_for(dossier: dict, variant_id: str | None) -> str:
    """Resolve which hero layout to render for the home page.

    Precedence:

    1. ``dossier["directives"]["layoutHint"]`` — operator override
       coming from the wizard's visual step. Frontend may set
       ``"gradient" | "centered" | "split"``; anything else is ignored
       so we never trust unknown strings.
    2. ``_HERO_STYLE_BY_VARIANT[variant_id]`` — vibe-aware default. A
       warm-craft variant gets a centered hero by default, a noir-
       editorial gets a split hero, etc.
    3. ``_HERO_STYLE_BY_TONE[normalized_tone]`` — tone-aware fallback
       (Sprint B/3). Triggas när varianten saknar mapping (framtida
       experimentella variants) ELLER när variantId helt saknas men
       tone är satt. Svenska wizard-tags ("Lekfull", "Lugn och
       förtroendeingivande") normaliseras via ``_normalize_tone_key``
       så samma mapping fungerar oavsett om operatören valde tone
       via chips eller skrev en engelsk semantisk key.
    4. ``"gradient"`` — universal fallback. Matches the pre-#2 behavior
       so tests that call ``render_home`` with no variant_id keep the
       same JSX shape they used to.
    """
    directives = dossier.get("directives")
    if isinstance(directives, dict):
        hint = directives.get("layoutHint")
        if isinstance(hint, str) and hint in _VALID_HERO_STYLES:
            return hint
    if variant_id and variant_id in _HERO_STYLE_BY_VARIANT:
        return _HERO_STYLE_BY_VARIANT[variant_id]
    tone = dossier.get("tone")
    if isinstance(tone, dict):
        primary = tone.get("primary")
        if isinstance(primary, str) and primary.strip():
            normalized = _normalize_tone_key(primary)
            if normalized in _HERO_STYLE_BY_TONE:
                return _HERO_STYLE_BY_TONE[normalized]
    return "gradient"


def _render_hero_background_video(
    background_video: dict | None, hero_asset: dict | None
) -> str:
    """Render a tyst loopande bakgrundsvideo bakom hero-textinnehållet.

    Avgör layout: <video> ligger som ``absolute inset-0`` i en wrapper
    så texten kan staplas ovanpå. ``poster`` pekar mot hero-bilden om
    den finns — då ser första frame snyggt ut även om autoplay blockas
    (Safari low-power mode, prefers-reduced-motion-användare).

    En semi-transparent overlay (``bg-background/40``) lägger sig över
    videon så texten håller WCAG AA-kontrast oavsett vad operatorn
    laddade upp. Marknadsledande mönster (Apple, Stripe, Linear).

    Returnerar tom sträng om ingen video — då renderas hero som vanligt
    utan video-wrapper.
    """
    if not isinstance(background_video, dict):
        return ""
    filename = background_video.get("filename")
    if not isinstance(filename, str) or not filename:
        return ""
    mime = background_video.get("mimeType")
    if mime not in ("video/mp4", "video/webm"):
        return ""
    poster_attr = ""
    if isinstance(hero_asset, dict) and hero_asset.get("filename"):
        poster_path = "/uploads/" + str(hero_asset["filename"])
        poster_attr = f" poster={_jsx_safe_string(poster_path)}"
    video_src = "/uploads/" + filename
    return (
        '        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">\n'
        f'          <video src={_jsx_safe_string(video_src)}{poster_attr} autoPlay loop muted playsInline aria-hidden className="h-full w-full object-cover" />\n'
        '          <div className="absolute inset-0 bg-[color:var(--background)]/60 backdrop-blur-[2px]"></div>\n'
        "        </div>\n"
    )


def _render_hero_block(
    style: str,
    *,
    company: dict,
    location_tag: str,
    hero_cta_label: str,
    hero_cta_href: str,
    contact_phone: str,
    spel_cta: str,
    hero_asset: dict | None,
    usps: list[str] | None = None,
    unsplash_fallback_url: str | None = None,
    background_video: dict | None = None,
) -> str:
    """Render the hero <section> for the home page in one of three
    layouts. Customer-text (company.name, company.tagline) is always
    wrapped via ``_jsx_safe_string`` so the JSX-escape tests (B30)
    pass for every variant.

    Layouts:

    - ``gradient``: full-width gradient panel, location tag + h1 +
       tagline stacked left-aligned. The pre-#2 baseline.
    - ``centered``: text-aligned center, no gradient, generous vertical
       rhythm. Suits calm/serif/editorial vibes (warm-craft, clinical-
       calm, earth-wellness).
    - ``split``: two-column on md+: text left, hero image right. When
       the operator has uploaded a hero image we render it; otherwise
       a soft accent-tinted block sits in the right column so the
       layout reads correctly even with no asset. Suits editorial and
       commerce vibes (midnight-counsel, noir-editorial, clean-store).
    """
    safe_name = _jsx_safe_string(company["name"])
    safe_tagline = _jsx_safe_string(company["tagline"])
    usp_list = usps or []
    usp_chips_left = _render_hero_usp_chips(usp_list, centered=False)
    usp_chips_centered = _render_hero_usp_chips(usp_list, centered=True)
    video_layer = _render_hero_background_video(background_video, hero_asset)
    has_video = bool(video_layer)
    cta_buttons = (
        '          <div className="flex flex-wrap gap-3">\n'
        f'            <a href={hero_cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
        f'            <a href={_jsx_safe_string("tel:" + _phone_href(contact_phone))} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {_jsx_safe_string(contact_phone)}</a>\n'
        f"{spel_cta}"
        "          </div>\n"
    )

    if style == "centered":
        # location_tag in the centered layout sits as an eyebrow above
        # the title and is text-centered alongside it. We translate the
        # left-aligned default to a centered one inline rather than
        # branching upstream.
        centered_location = (
            location_tag.replace("flex items-center gap-2", "flex items-center gap-2 justify-center")
            if location_tag
            else ""
        )
        section_classes = (
            "relative overflow-hidden bg-[color:var(--background)]"
            if has_video
            else "bg-[color:var(--background)]"
        )
        return (
            f'      <section className="{section_classes}">\n'
            f"{video_layer}"
            '        <div className="relative mx-auto flex w-[var(--container-width)] flex-col items-center gap-8 py-[calc(var(--section-spacing)*1.25)] text-center">\n'
            f"{centered_location}"
            f'          <h1 className="max-w-3xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl lg:text-7xl">{safe_name}</h1>\n'
            f'          <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{safe_tagline}</p>\n'
            f"{usp_chips_centered}"
            '          <div className="flex flex-wrap items-center justify-center gap-3">\n'
            f'            <a href={hero_cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
            f'            <a href={_jsx_safe_string("tel:" + _phone_href(contact_phone))} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {_jsx_safe_string(contact_phone)}</a>\n'
            f"{spel_cta}"
            "          </div>\n"
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    if style == "split":
        if isinstance(hero_asset, dict) and hero_asset.get("filename"):
            hero_filename = hero_asset["filename"]
            hero_alt = hero_asset.get("alt") or company["tagline"]
            # Fas 3.3 — CSS-only parallax via scroll-driven animations.
            # ``parallax-hero``-klassen definieras i variant_css och
            # zoomar bilden 1.0 → 1.08 över hela hero-exit-fönstret när
            # browsern stödjer animation-timeline (Chrome/Edge 115+).
            # Safari + Firefox ignorerar utility:n och visar bilden statiskt.
            right_column = (
                '          <div className="relative aspect-square w-full overflow-hidden rounded-2xl ring-1 ring-[color:var(--border)] shadow-sm md:aspect-[4/5]">\n'
                # Sprint 1.3 — split-layout hero är också above-the-fold
                # på desktop. Samma LCP-attribut som banner-hero.
                f'            <img src={_jsx_safe_string("/uploads/" + hero_filename)} alt={_js_string_literal(hero_alt)} fetchPriority="high" loading="eager" decoding="async" className="parallax-hero h-full w-full object-cover" />\n'
                "          </div>\n"
            )
        elif unsplash_fallback_url:
            # C1 — branch-baserad Unsplash-fallback. Operatören har inte
            # laddat upp en hero-bild men vi har en branschmatchande
            # bild från Unsplash editorial collection. Vi använder en
            # raw ``<img>`` med ``loading="lazy"`` och en explicit alt
            # som refererar till företagets tagline, så bilden får
            # samma a11y-och-prestanda-behandling som operatör-uppladdade
            # filer under ``/uploads/``.
            fallback_alt = company.get("tagline") or company.get("name") or "Hero-bild"
            right_column = (
                '          <div className="relative aspect-square w-full overflow-hidden rounded-2xl ring-1 ring-[color:var(--border)] shadow-sm md:aspect-[4/5]">\n'
                f'            <img src={_jsx_safe_string(unsplash_fallback_url)} alt={_js_string_literal(fallback_alt)} loading="lazy" decoding="async" className="parallax-hero h-full w-full object-cover" />\n'
                "          </div>\n"
            )
        else:
            # No hero image and no branch-fallback: render a soft
            # accent-tinted shape so the split layout still reads
            # correctly. Pure CSS, no asset.
            right_column = (
                '          <div className="relative aspect-square w-full overflow-hidden rounded-2xl bg-gradient-to-br from-[color:var(--accent)] to-[color:var(--primary)]/40 md:aspect-[4/5]">\n'
                '            <div className="absolute inset-12 rounded-full bg-[color:var(--background)]/30 blur-3xl"></div>\n'
                "          </div>\n"
            )
        split_section_classes = (
            "relative overflow-hidden bg-[color:var(--background)]"
            if has_video
            else "bg-[color:var(--background)]"
        )
        return (
            f'      <section className="{split_section_classes}">\n'
            f"{video_layer}"
            '        <div className="relative mx-auto grid w-[var(--container-width)] gap-10 py-[var(--section-spacing)] md:grid-cols-2 md:items-center md:gap-16">\n'
            '          <div className="flex flex-col gap-8">\n'
            f"{location_tag}"
            f'            <h1 className="max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">{safe_name}</h1>\n'
            f'            <p className="max-w-xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{safe_tagline}</p>\n'
            "            "
            + cta_buttons.lstrip()
            + f"{usp_chips_left}"
            + "          </div>\n"
            + right_column
            + "        </div>\n"
            "      </section>\n"
            "\n"
        )

    # Default — gradient (pre-#2 baseline). Gradient sektionen har
    # redan ``relative overflow-hidden`` så video-lagret blandar sig
    # snyggt med den befintliga gradient-bakgrunden.
    return (
        '      <section className="relative overflow-hidden bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/30">\n'
        f"{video_layer}"
        '        <div className="relative mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        f"{location_tag}"
        f'          <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">{safe_name}</h1>\n'
        f'          <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed md:text-xl">{safe_tagline}</p>\n'
        f"{usp_chips_left}"
        + cta_buttons
        + "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_gallery_section(dossier: dict) -> str:
    """Render an optional gallery section on the home page.

    Re-uses ``dossier["gallery"]`` (the same source as ``render_gallery``
    for the dedicated ``/galleri`` route). Renders up to
    ``_HOME_GALLERY_MAX_ITEMS`` figures in a responsive 1/2/3-column
    grid; a full /galleri route still exists for the long tail.

    Returns ``""`` when the operator has not uploaded any gallery
    images, so the section never leaks empty placeholder copy onto the
    home page. The empty string short-circuits the whole `<section>`
    block in ``render_home`` so other sections rendered after it
    (trust, contact CTA) keep their `border-t` divider.

    Fas 2.1 — om story-sektionen körs (``company.story`` finns) så
    konsumerar den första gallery-bilden i en two-column layout. Vi
    hoppar över första bilden här så samma foto inte syns dubbelt på
    startsidan. Bilden finns kvar i /galleri-routen via ``render_gallery``
    så den fortfarande är synlig på sajten.
    """
    images = _gallery_images(dossier)
    if not images:
        return ""
    company = dossier.get("company") or {}
    story_text = company.get("story")
    story_consumed = isinstance(story_text, str) and bool(story_text.strip())
    if story_consumed and len(images) >= 2:
        images = images[1:]
    elif story_consumed and len(images) == 1:
        # Single image was already lifted into the story-section.
        # Suppress the gallery to avoid rendering an empty section.
        return ""
    selected = images[:_HOME_GALLERY_MAX_ITEMS]
    # Fas 3.2 — smarta bildramar. ``ring-1`` ger en hairline-kant som
    # tar över när hover-state lyfter shadow:n. ``shadow-sm`` på vila
    # och ``shadow-md`` på hover ger en mjuk floating-känsla.
    figures = "\n".join(
        f'            <figure key={_jsx_safe_string(item.get("assetId") or item["filename"])} className="group overflow-hidden rounded-xl ring-1 ring-[color:var(--border)] bg-[color:var(--background)] shadow-sm transition-all duration-300 hover:shadow-md">\n'
        f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company.get("name") or "Bild")} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.03]" />\n'
        "            </figure>"
        for item in selected
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vårt arbete</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Ett urval från projekten</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">\n'
        f"{figures}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_story_section(dossier: dict) -> str:
    """Render a compact story section on the home page when the
    operator has a non-empty ``company.story``. The section reuses
    the ``Quote``-flanked card pattern from ``render_about`` so the
    visual language is consistent between home and the dedicated
    /om-oss route.

    Returns ``""`` when ``company.story`` is missing or blank so the
    section never leaks generic filler onto the home page. Tests in
    ``test_builder_audit_post_3b_next.py`` exercise ``render_home``
    directly with various dossier shapes; the empty-story short-
    circuit is what keeps those tests passing without forcing every
    operator to supply a story.

    Icon dependency: this helper consumes ``Quote`` from lucide-react.
    The caller (``render_home``) is responsible for including
    ``Quote`` in its icon-import line; ``_collect_icons_for_pages``
    cannot detect this dependency from ``services`` alone, so
    ``render_home`` whitelists ``Quote`` whenever this section is
    emitted (mirrors the ``Check`` whitelist for USP chips).
    """
    company = dossier.get("company") or {}
    story = company.get("story")
    if not isinstance(story, str) or not story.strip():
        return ""
    safe_story = _jsx_safe_string(story.strip())

    # Fas 2.1 — om gallery har minst en bild lyfter vi den första
    # bredvid story-kortet i en two-column layout. Detta ger startsidan
    # ett ankrat foto bredvid berättelsen istället för att alla bilder
    # försvinner ner i gallery-sektionen. Story-bilden konsumeras
    # fortfarande av render_gallery (/galleri-routen renderar hela
    # listan), och _render_home_gallery_section slipper visa den första
    # bilden igen via en offset (se motsvarande fix där).
    images = _gallery_images(dossier)
    story_image: dict | None = images[0] if images else None

    if story_image is None:
        return (
            '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/10">\n'
            '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[var(--section-spacing)]">\n'
            '          <div className="flex flex-col gap-3">\n'
            '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vår historia</p>\n'
            '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det här är vi</h2>\n'
            "          </div>\n"
            '          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
            '            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/25" />\n'
            f'            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{safe_story}</p>\n'
            "          </div>\n"
            "        </div>\n"
            "      </section>\n"
            "\n"
        )

    story_alt = story_image.get("alt") or company.get("name") or "Story-bild"
    story_filename = story_image["filename"]
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/10">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vår historia</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det här är vi</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-center md:gap-12">\n'
        '            <div className="relative rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
        '              <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/25" />\n'
        f'              <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{safe_story}</p>\n'
        "            </div>\n"
        '            <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl ring-1 ring-[color:var(--border)] shadow-sm">\n'
        f'              <img src={_jsx_safe_string("/uploads/" + story_filename)} alt={_js_string_literal(story_alt)} loading="lazy" decoding="async" className="h-full w-full object-cover" />\n'
        "            </div>\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_testimonials_section(dossier: dict) -> str:
    """Render a testimonials-style section on the home page when the
    dossier has at least ``_HOME_TESTIMONIAL_MIN_ITEMS`` trustSignals.

    The threshold is intentional: with only 1–2 trustSignals, a
    3-column card grid looks underpopulated. The caller falls back to
    the existing ``trust_section`` (bullet list with ``ShieldCheck``
    icons) below this threshold. With 3+ items we render each
    trustSignal as a card with a ``Quote``-glyph and bold attribution
    ("Sagt om oss") so the visual feel matches real customer
    testimonials, even though the source is operator-authored copy.

    Returns ``""`` when fewer than the minimum number of items exist,
    so the caller can decide whether to render its bullet-list
    fallback or skip the section entirely.

    Icon dependency: ``Quote`` (caller whitelists this when the
    section is emitted; ``_collect_icons_for_pages`` doesn't see
    trustSignals).
    """
    trust = dossier.get("trustSignals") or []
    if not isinstance(trust, list):
        return ""
    items: list[str] = [
        str(item).strip()
        for item in trust
        if isinstance(item, str) and item.strip()
    ]
    if len(items) < _HOME_TESTIMONIAL_MIN_ITEMS:
        return ""
    # Fas 2.3 — hover-effekter på testimonial-cards. Identisk timing
    # och easing som services-cards så hover-känslan är konsistent
    # över startsidan. ``-translate-y-0.5`` ger en lätt lyft-effekt
    # som Apple/Stripe använder för dwell-tid på cards.
    cards = "\n".join(
        f'            <figure key={_jsx_safe_string(f"trust-card-{i}")} className="group relative flex h-full flex-col gap-4 rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'              <Quote className="size-6 text-[color:var(--primary)]/30 transition-colors group-hover:text-[color:var(--primary)]/60" />\n'
        f'              <blockquote className="text-base text-[color:var(--foreground)] leading-relaxed">{_jsx_safe_string(item)}</blockquote>\n'
        f'              <figcaption className="mt-auto text-xs uppercase tracking-widest text-[color:var(--muted)]">Sagt om oss</figcaption>\n'
        "            </figure>"
        for i, item in enumerate(items)
    )
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Förtroende</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det här uppskattar våra kunder</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_home_faq_section(dossier: dict, *, has_faq_route: bool) -> str:
    """Render a compact FAQ section on the home page using the
    deterministic ``_faq_pairs`` helper that ``render_faq`` already
    uses for the dedicated /faq route. Shows up to
    ``_HOME_FAQ_MAX_ITEMS`` pairs in a 2-column grid; when the dossier
    has a /faq route the section ends with a "Se alla frågor"-CTA
    that links to it, otherwise the CTA is omitted to avoid ghost
    routes.

    ``_faq_pairs`` returns 3–4 deterministic pairs (three defaults
    plus an opening-hours pair when ``contact.openingHours`` is set),
    so this section always renders when called — there's no
    operator-data dependency that could short-circuit it to ``""``.
    Callers that want to suppress FAQs entirely should skip calling
    this helper.

    Icon dependency: ``ArrowRight`` (already in render_home's icon-
    set whenever ``listing_link`` is rendered, so the caller doesn't
    need additional whitelisting; we still soft-import via the icon
    collector to be explicit).
    """
    pairs = _faq_pairs(dossier)
    if not pairs:
        return ""
    items = "\n".join(
        f'            <article key={_jsx_safe_string(f"home-faq-{i}")} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6">\n'
        f'              <h3 className="text-base font-semibold leading-snug">{_jsx_safe_string(question)}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(answer)}</p>\n'
        "            </article>"
        for i, (question, answer) in enumerate(pairs[:_HOME_FAQ_MAX_ITEMS])
    )
    faq_link = ""
    if has_faq_route:
        faq_link = (
            '          <a href="/faq" className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se alla frågor<ArrowRight className="size-4" /></a>\n'
        )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vanliga frågor</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Det vi får höra ofta</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-3 md:grid-cols-2">\n'
        f"{items}\n"
        "          </div>\n"
        f"{faq_link}"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_gallery(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /galleri route.

    Uses ``dossier["gallery"]`` images that ``copy_operator_uploads``
    already placed under ``public/uploads/``. An empty gallery falls
    back to honest copy ("Vi laddar upp bilder snart...") rather than
    rendering generic stock placeholders.
    """
    company = dossier.get("company") or {}
    images = _gallery_images(dossier)
    body: str
    if images:
        figures = "\n".join(
            f'            <figure key={_jsx_safe_string(item.get("assetId") or item["filename"])} className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[color:var(--background)]">\n'
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or company.get("name") or "Bild")} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover" />\n'
            "            </figure>"
            for item in images
        )
        body = (
            '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            + figures
            + "\n          </div>\n"
        )
    else:
        body = (
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Bilder från våra senaste uppdrag publiceras här löpande. Vill du se exempel direkt? Hör av dig så delar vi referensbilder via mejl.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function GalleryPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Galleri",
            "Bilder från våra uppdrag",
            "Ett urval av jobb vi har gjort. Bilderna laddas upp av "
            "oss i takt med att nya projekt blir klara.",
        )
        + body
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def _team_members(dossier: dict) -> list[dict]:
    company = dossier.get("company") or {}
    team = company.get("team") if isinstance(company, dict) else None
    if not isinstance(team, list):
        return []
    return [member for member in team if isinstance(member, dict) and member.get("name")]


def render_team(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /team route.

    Reads ``company.team`` (same source as render_about) and renders
    one card per member. Empty teams fall back to honest copy instead
    of inventing roles or photos.
    """
    members = _team_members(dossier)
    if members:
        cards = "\n".join(
            f'            <li key={_jsx_safe_string(member["name"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-foreground)] text-sm font-semibold uppercase">{_jsx_safe_string(_member_initials(member["name"]))}</span>\n'
            f'              <p className="text-base font-semibold">{_jsx_safe_string(member["name"])}</p>\n'
            f'              <p className="mt-1 text-sm text-[color:var(--muted)]">{_jsx_safe_string(member.get("role") or "")}</p>\n'
            "            </li>"
            for member in members
        )
        body = (
            '          <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            + cards
            + "\n          </ul>\n"
        )
    else:
        body = (
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Vi presenterar teamet här när vi hunnit fylla på med bilder och roller. Vill du veta vem du kommer prata med? Hör av dig så berättar vi gärna.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function TeamPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Team",
            "Människorna bakom",
            "Här ser du vilka du kommer i kontakt med när du anlitar oss.",
        )
        + body
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_pricing(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /priser route.

    Lists the dossier's ``services`` array as price-quote cards with
    honest "Pris efter offert"-copy. No invented price points: a
    fake hourly rate or fixed price could mislead customers and is
    out of scope for the deterministic Builder.
    """
    services = dossier.get("services") or []
    if isinstance(services, list) and services:
        cards = "\n".join(
            f'            <article key={_jsx_safe_string(svc["id"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <h2 className="text-xl font-semibold">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc.get("summary") or "")}</p>\n'
            '              <p className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-[color:var(--primary)]">Pris efter offert</p>\n'
            "            </article>"
            for svc in services
            if isinstance(svc, dict) and svc.get("id") and svc.get("label")
        )
        body = (
            '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
            + cards
            + "\n          </div>\n"
        )
    else:
        body = (
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Vi lägger upp en aktuell prislista här inom kort. Vill du ha pris på ett specifikt uppdrag direkt? Hör av dig så återkommer vi med offert.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function PricingPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Priser",
            "Vad kostar det?",
            "Priserna beror på uppdragets omfattning. Begär en "
            "kostnadsfri offert så får du ett tydligt pris innan vi "
            "startar.",
        )
        + body
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_portfolio(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /portfolio route.

    Combines uploaded gallery images with the services list as
    case-style cards. Empty input falls back to a friendly "vi
    bygger på portföljen"-message.
    """
    images = _gallery_images(dossier)
    services = dossier.get("services") or []
    blocks: list[str] = []
    if images:
        figures = "\n".join(
            f'            <figure key={_jsx_safe_string(item.get("assetId") or item["filename"])} className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-[color:var(--background)]">\n'
            f'              <img src={_jsx_safe_string("/uploads/" + item["filename"])} alt={_js_string_literal(item.get("alt") or "Case-bild")} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover" />\n'
            f'              <figcaption className="px-4 py-3 text-sm text-[color:var(--muted)]">{_jsx_safe_string(item.get("alt") or "Genomfört uppdrag")}</figcaption>\n'
            "            </figure>"
            for item in images
        )
        blocks.append(
            '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
            + figures
            + "\n          </div>\n"
        )
    if isinstance(services, list) and services:
        cards = "\n".join(
            f'            <article key={_jsx_safe_string(svc["id"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
            f'              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Exempel på uppdrag</p>\n'
            f'              <h2 className="mt-2 text-xl font-semibold">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc.get("summary") or "")}</p>\n'
            "            </article>"
            for svc in services
            if isinstance(svc, dict) and svc.get("id") and svc.get("label")
        )
        blocks.append(
            '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
            + cards
            + "\n          </div>\n"
        )
    if not blocks:
        blocks.append(
            '          <div className="rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--background)] p-6 text-[color:var(--muted)]">\n'
            '            <p className="text-base leading-relaxed">Vi bygger på portföljen löpande. Vill du höra om liknande uppdrag vi har gjort? Hör av dig så delar vi referenser.</p>\n'
            "          </div>\n"
        )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function PortfolioPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Portfolio",
            "Tidigare uppdrag",
            "Ett urval av jobb och case som visar hur vi arbetar.",
        )
        + "".join(blocks)
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_map(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the wizard-driven /karta route.

    Shows the contact address, service areas and a Google Maps query
    link based on the dossier address. Avoids embedded map iframes
    because they require an API key and would shift the runtime
    contract. The link is opt-in for the visitor and clearly labelled.
    """
    location = dossier.get("location") or {}
    contact = dossier.get("contact") or {}
    address_lines: list[str] = []
    if isinstance(contact, dict):
        raw_lines = contact.get("addressLines")
        if isinstance(raw_lines, list):
            for line in raw_lines:
                if isinstance(line, str) and line.strip():
                    address_lines.append(line.strip())
    if not address_lines:
        city = location.get("city") if isinstance(location, dict) else None
        if isinstance(city, str) and city.strip():
            address_lines.append(city.strip())
    address_jsx = "\n".join(
        f'                <span className="block">{_jsx_safe_string(line)}</span>'
        for line in address_lines
    )
    address_block: str
    if address_lines:
        address_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Adress</h2>\n'
            '              <address className="mt-2 not-italic">\n'
            f"{address_jsx}\n"
            "              </address>\n"
            "            </article>\n"
        )
    else:
        address_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6 text-[color:var(--muted)]">\n'
            '              <p className="text-base leading-relaxed">Vi lägger upp adressen så fort den är bekräftad. Ring eller mejla oss om du vill ha vägbeskrivning direkt.</p>\n'
            "            </article>\n"
        )
    service_areas: list[str] = []
    if isinstance(location, dict):
        raw_areas = location.get("serviceAreas")
        if isinstance(raw_areas, list):
            for area in raw_areas:
                if isinstance(area, str) and area.strip():
                    service_areas.append(area.strip())
    if service_areas:
        areas_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Områden vi arbetar i</h2>\n'
            f'              <p className="mt-2 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(", ".join(service_areas))}</p>\n'
            "            </article>\n"
        )
    else:
        areas_block = ""
    query_source = ", ".join(address_lines) if address_lines else (
        (location.get("city") if isinstance(location, dict) else None) or ""
    )
    map_block: str
    if isinstance(query_source, str) and query_source.strip():
        maps_url = (
            "https://www.google.com/maps/search/?api=1&query="
            + _url_quote(query_source.strip())
        )
        map_block = (
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Hitta hit</h2>\n'
            '              <p className="mt-2 text-sm text-[color:var(--muted)]">Öppna platsen i Google Maps för vägbeskrivning.</p>\n'
            f'              <a href={_js_string_literal(maps_url)} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] px-4 py-2 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors">Visa på karta<ArrowRight className="size-4" /></a>\n'
            "            </article>\n"
        )
    else:
        map_block = ""
    return (
        'import { ArrowRight, MapPin } from "lucide-react";\n'
        "\n"
        "export default function MapPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Hitta hit",
            "Vägbeskrivning och områden",
            "Här hittar du adressen och vilka områden vi arbetar i. "
            "Vill du ha hjälp med vägbeskrivning är det bara att ringa.",
        )
        + '          <div className="grid gap-4 md:grid-cols-2">\n'
        + address_block
        + areas_block
        + map_block
        + "          </div>\n"
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


# ---------------------------------------------------------------------------
# Restaurant-hospitality default-route renderers (Issue #90).
#
# These two functions wire the ``menu`` and ``booking`` route ids declared
# by ``packages/generation/orchestration/scaffolds/restaurant-hospitality/
# routes.json`` so a full build of a restaurant Project Input no longer
# exits with a SystemExit from ``write_pages``. They are scaffold-default
# renderers (registered as ``elif`` arms below), not wizard-extras, so
# they do NOT live in ``_WIZARD_ROUTE_RENDERERS``.
#
# Scope per Issue #90: static markup only. No third-party booking
# integration, no payment flow, no real-time availability — the
# scaffold's compatible-dossiers.json declares ``menu-display`` and
# ``booking-cta`` as required dossiers and the dossier-mounting layer
# adds any dynamic UI on top during a separate compositional pass.
#
# Path B (section-driven renderer registry from
# docs/scaffold-runtime-extension-needed.md) is deliberately deferred
# to a future sprint; for Issue #90 we follow Path A (per-route
# functions in the existing if/elif chain) to keep the change small
# and reviewable.
# ---------------------------------------------------------------------------


def _menu_items(dossier: dict) -> list[dict]:
    """Return menu items for a restaurant project input.

    The project-input schema's ``services[]`` is structurally identical
    to a menu item (``id`` + ``label`` + ``summary``), and the schema's
    top-level ``additionalProperties: false`` forbids adding a separate
    ``menu`` field. Restaurant operators therefore put menu items in
    the ``services`` array; ``render_menu`` reads them back here.

    The fallback returns a short sample so the page still has visible
    content for projects that pin restaurant-hospitality without
    supplying any items — that is rare in production but useful when
    the planner picks the scaffold from a thin prompt.
    """
    items = dossier.get("services") or []
    cleaned: list[dict] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("id") and item.get("label"):
                cleaned.append(item)
    if cleaned:
        return cleaned
    return [
        {
            "id": "house-special",
            "label": "Dagens rätt",
            "summary": (
                "Vår kock väljer en huvudrätt utifrån säsongens råvaror. "
                "Fråga personalen vad som serveras idag."
            ),
        },
    ]


def render_menu(dossier: dict, *, contact_path: str = "/hitta-hit") -> str:
    """Render the restaurant /meny route.

    Composes ``services``-as-menu-items into a card grid with the
    wizard-route eyebrow + heading idiom, followed by a trailing CTA
    to the contact route so a hungry visitor lands on opening hours
    and phone instead of dead-ending on the menu. The booking page
    is intentionally not the CTA target here: the scaffold's
    ``booking-cta`` dossier is mounted separately by the
    dossier-mounting layer and handles the visible book-a-table
    affordance in compliance with sections.json's order rule that
    the booking CTA must appear at least twice on the home page.

    ``contact_path`` defaults to ``/hitta-hit`` to match the
    scaffold's ``contact`` route slug; callers that pass a different
    contact route will see the CTA point there instead.
    """
    items = _menu_items(dossier)
    card_fragments: list[str] = []
    for item in items:
        key_attr = _jsx_safe_string("menu-" + str(item["id"]))
        label_attr = _jsx_safe_string(str(item["label"]))
        summary_value = item.get("summary")
        summary_fragment = ""
        if isinstance(summary_value, str) and summary_value.strip():
            summary_attr = _jsx_safe_string(summary_value)
            summary_fragment = (
                '              <p className="mt-2 text-sm '
                'text-[color:var(--muted)] leading-relaxed">'
                f"{summary_attr}</p>\n"
            )
        card_fragments.append(
            f"            <article key={key_attr} "
            'className="rounded-xl border border-[color:var(--border)] '
            "bg-[color:var(--card,var(--background))] p-6 transition-all "
            "duration-300 hover:-translate-y-0.5 "
            'hover:border-[color:var(--primary)] hover:shadow-md">\n'
            f'              <h2 className="text-lg font-semibold">{label_attr}</h2>\n'
            f"{summary_fragment}"
            "            </article>"
        )
    cards = "\n".join(card_fragments)
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function MenuPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Meny",
            "Vad vi serverar just nu",
            "Menyn växlar med säsongen och tillgången på råvaror. "
            "Be gärna personalen om dagens rekommendation eller hör av dig "
            "i förväg om du har önskemål eller allergier.",
        )
        + '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        + cards
        + "\n          </div>\n"
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


def render_booking(dossier: dict, *, contact_path: str = "/hitta-hit") -> str:
    """Render the restaurant /bokning route.

    Static reservation page: opening hours summary plus a fallback
    phone (tel:) link and email (mailto:) link so the visitor can
    book even when no third-party widget is wired. Per Issue #90 we
    do NOT embed a booking provider here — the operator's preferred
    provider lands via the ``booking-cta`` dossier in a separate
    compositional pass.

    Mirrors render_menu's signature so the dispatcher in write_pages
    can call both with the same contact_path argument.
    """
    contact = dossier.get("contact") or {}
    phone = contact.get("phone") if isinstance(contact, dict) else None
    email = contact.get("email") if isinstance(contact, dict) else None
    opening = contact.get("openingHours") if isinstance(contact, dict) else None

    rows: list[str] = []
    if isinstance(opening, str) and opening.strip():
        rows.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Öppettider</p>\n'
            f'              <p className="mt-2 text-base">{_jsx_safe_string(opening.strip())}</p>\n'
            "            </div>"
        )
    if isinstance(phone, str) and phone.strip():
        rows.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via telefon</p>\n'
            f'              <a href={_jsx_safe_string("tel:" + _phone_href(phone))} '
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(phone)}</a>\n'
            "            </div>"
        )
    if isinstance(email, str) and email.strip():
        rows.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via e-post</p>\n'
            f'              <a href={_jsx_safe_string("mailto:" + email.strip())} '
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(email.strip())}</a>\n'
            "            </div>"
        )
    rows_block = "\n".join(rows) if rows else (
        '            <p className="text-base text-[color:var(--muted)]">'
        "Boka bord genom att kontakta oss — kontaktuppgifter finns på "
        "sidan Hitta hit.</p>"
    )

    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        "export default function BookingPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + _wizard_section_heading(
            "Boka bord",
            "Boka en plats hos oss",
            "Just nu tar vi bokningar via telefon och e-post. Ring eller "
            "skriv så bekräftar vi tid och antal personer. För större "
            "sällskap, hör av dig minst två dagar i förväg.",
        )
        + '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        + rows_block
        + "\n          </div>\n"
        + _wizard_contact_cta(dossier, contact_path)
        + _wizard_page_footer()
    )


_WIZARD_ROUTE_RENDERERS: dict[str, Any] = {
    "faq": render_faq,
    "gallery": render_gallery,
    "team": render_team,
    "pricing": render_pricing,
    "portfolio": render_portfolio,
    "map": render_map,
}


def _url_quote(value: str) -> str:
    """Small wrapper around urllib's quoting for Maps query strings.

    Local import keeps the module-level imports clean; the helper only
    runs on the wizard-driven /karta path.
    """
    from urllib.parse import quote

    return quote(value, safe="")



def write_pages(
    target: Path,
    dossier: dict,
    scaffold_routes: dict,
    dossier_routes: list[str],
    extra_routes: list[dict] | None = None,
    variant_id: str | None = None,
) -> list[str]:
    """Write every page declared in ``scaffold_routes["defaultRoutes"]``.

    The renderer for each route is selected by route id, not by
    path, so a future scaffold can keep the id ``"contact"`` while
    moving the path from ``/kontakt`` to ``/kontakta-oss`` without
    duplicating the renderer.

    Returns the list of paths written (one per default route) so
    the caller can mention them in the trace event without
    rebuilding the list.

    Raises ``SystemExit`` for scaffold route ids that have no
    registered renderer: silently skipping such routes would later
    surface as Quality Gate route-scan failures with no obvious
    owner. The error message names the route id so the operator
    can add a renderer or remove the route from the scaffold.
    """
    default_routes = scaffold_routes["defaultRoutes"]
    listing_route = _pick_listing_route(default_routes)
    contact_route = _pick_contact_route(default_routes)
    written: list[str] = []
    for route in default_routes:
        route_id = route["id"]
        path = route["path"]
        if route_id == "home":
            content = _renderer("render_home")(
                dossier,
                dossier_routes,
                listing_route=listing_route,
                contact_path=contact_route["path"],
                variant_id=variant_id,
            )
        elif route_id == "services":
            content = _renderer("render_services")(dossier, contact_path=contact_route["path"])
        elif route_id == "products":
            content = _renderer("render_products")(dossier, contact_path=contact_route["path"])
        elif route_id == "menu":
            content = _renderer("render_menu")(dossier, contact_path=contact_route["path"])
        elif route_id == "booking":
            content = _renderer("render_booking")(dossier, contact_path=contact_route["path"])
        elif route_id == "about":
            content = _renderer("render_about")(dossier)
        elif route_id == "contact":
            content = _renderer("render_contact")(dossier)
        else:
            raise SystemExit(
                "Builder failed: scaffold route id "
                f"{route_id!r} (path={path!r}) has no registered "
                "renderer in scripts/build_site.py. Add a "
                "render_<id>() function and register it in "
                "write_pages, or remove the route from the "
                "scaffold's routes.json."
            )
        write(route_to_page_path(target, path), content)
        written.append(path)
    sanitized_extras: list[dict] = []
    if extra_routes:
        default_paths = {route["path"] for route in default_routes}
        seen_extra_paths: set[str] = set()
        for route in extra_routes:
            if not isinstance(route, dict):
                continue
            route_id = route.get("id")
            path = route.get("path")
            if not isinstance(route_id, str) or not isinstance(path, str):
                continue
            if path in default_paths or path in seen_extra_paths:
                continue
            renderer = _WIZARD_ROUTE_RENDERERS.get(route_id)
            if renderer is None:
                raise SystemExit(
                    "Builder failed: wizard extra route id "
                    f"{route_id!r} (path={path!r}) has no registered "
                    "renderer in scripts/build_site.py. Register it in "
                    "_WIZARD_ROUTE_RENDERERS or remove it from the "
                    "wizard extra route list in "
                    "packages/generation/planning/plan.py."
                )
            content = renderer(dossier, contact_path=contact_route["path"])
            write(route_to_page_path(target, path), content)
            written.append(path)
            seen_extra_paths.add(path)
            sanitized_extras.append({"id": route_id, "path": path})
    write(
        target / "app" / "layout.tsx",
        render_layout(
            dossier,
            dossier_routes,
            scaffold_default_routes=default_routes,
            contact_path=contact_route["path"],
            extra_routes=sanitized_extras or None,
        ),
    )
    # Sprint 1.2 — branded 404 + error pages. Skrivs alltid (de har
    # inga ``id``-baserade renderers och behöver inte registreras i
    # scaffold:s defaultRoutes). Next.js plockar upp filerna automatiskt
    # via filsystem-routing: ``not-found.tsx`` används för 404 och
    # ``error.tsx`` för uncaught exceptions i alla under-routes.
    write(target / "app" / "not-found.tsx", render_not_found(dossier))
    write(target / "app" / "error.tsx", render_global_error(dossier))
    # Sprint 1.5 — auto-OG-fallback. SVG:n skrivs alltid till
    # ``public/og-image-fallback.svg`` så Next.js Metadata API kan
    # länka dit oberoende av om operatorn laddat upp en egen.
    # ``render_layout`` använder den som default när
    # ``project_input.media.ogImage`` saknas; om operatorn HAR laddat
    # upp en egen vinner den, men fallback-filen ligger ändå kvar för
    # framtida sociala delningar utan extra build-steg.
    write(
        target / "public" / "og-image-fallback.svg",
        render_og_fallback_svg(dossier),
    )
    # Sprint 2.2/2.3 — robots.txt + sitemap.xml. Skrivs alltid så att
    # genererade sajter är Google-indexerbara från första bygget.
    # ``written`` innehåller alla scaffold-default routes plus wizard
    # extra routes (galleri, team, pricing, portfolio osv.) — sitemapen
    # speglar exakt det som faktiskt finns på disk.
    write(target / "public" / "robots.txt", render_robots_txt())
    write(target / "public" / "sitemap.xml", render_sitemap_xml(written))
    return written
