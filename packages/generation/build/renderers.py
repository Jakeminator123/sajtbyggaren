"""Page renderers + section renderers for the deterministic Builder MVP.

Originally extracted from ``scripts/build_site.py`` for B13a Step C
(PR #107). Re-expanded during the B146 port (2026-05-25) to absorb
Christopher's section-dispatcher pattern + Phase 3 operator-pin tier
from ``origin/main`` (PR #105 + PR #108) without re-inflating
``build_site.py`` past 7k rader.

The split is now three-tier:

* ``packages.generation.build.dispatcher``: section-id registry,
  scaffold sections cache, treatment-resolution helpers, generic route
  composer (``render_route_generic``).
* ``packages.generation.build.renderers`` (this module): every page
  renderer (``render_home`` etc.) and every section renderer
  (``render_section_*``). Registers section renderers into
  ``dispatcher._SECTION_RENDERERS`` at import time via
  ``.update(...)`` blocks so the dispatcher's registry is fully
  populated before any caller invokes it.
* ``packages.generation.build.static_assets``: deterministic static
  artefacts (robots.txt, sitemap.xml, OG fallback SVG, error pages,
  structured-data JSON-LD).

Shared utility helpers (variant_css, ``_hero_cta_label``,
``_nav_items_from_scaffold``, etc.) still live in ``scripts.build_site``
and are reached via the lazy ``_call_build_site`` shim block below.
A future sprint will finish moving them too; today's port keeps the
helper territory untouched on purpose so PR-diff stays bounded to
renderer + dispatcher movement.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from packages.generation.build.blueprint_render import (
    RenderBlueprint,
    apply_blueprint_to_dossier,
    resolve_section_content_override,
)
from packages.generation.build.contact_placeholders import (
    is_placeholder_address_lines,
    is_placeholder_email,
    is_placeholder_opening_hours,
    is_placeholder_phone,
    real_address_lines,
    real_email,
    real_opening_hours,
    real_phone,
)
from packages.generation.build.dispatcher import (
    _SECTION_RENDERERS,
    _call_section_renderer,
    _load_scaffold_sections,
    _operator_pin_for_section,
    _treatment_for_section,
    annotate_section_marker,
    render_route_generic,
)
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


def _hero_cta_variant(dossier: dict) -> str:
    """Shim for ``scripts.build_site._hero_cta_variant``.

    Returns ``"shop"`` / ``"booking"`` / ``"quote"`` based on the
    dossier's conversionGoals + business type + scaffoldId. B97 uses
    this to pick per-variant contact-page hero body copy so e-commerce
    and booking businesses do not show the quote-flavoured
    "Beskriv jobbet kort så återkommer vi … med tider och offert."
    paragraph.
    """
    return _call_build_site("_hero_cta_variant", dossier)


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


def _hard_dossier_runtime(dossier: dict, dossier_id: str) -> dict[str, Any] | None:
    runtime = dossier.get("dossierRuntime")
    if not isinstance(runtime, dict):
        return None
    hard = runtime.get("hardDossiers")
    if not isinstance(hard, dict):
        return None
    entry = hard.get(dossier_id)
    return entry if isinstance(entry, dict) else None


def resolve_media_asset(dossier: dict, kind: str) -> dict | None:
    return _call_build_site("resolve_media_asset", dossier, kind)


def route_to_page_path(target: Path, route: str) -> Path:
    return _call_build_site("route_to_page_path", target, route)


def write(path: Path, contents: str) -> None:
    _call_build_site("write", path, contents)


REPO_ROOT = Path(__file__).resolve().parents[3]


def render_layout(
    dossier: dict,
    dossier_routes: list[str],
    *,
    scaffold_default_routes: list[dict] | None = None,
    contact_path: str | None = None,
    extra_routes: list[dict] | None = None,
    font_stylesheet_href: str | None = None,
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
    # Honest footer contact column: only render channels the operator
    # actually supplied. Placeholder phone/email/address (the B88
    # fallbacks scripts/prompt_to_project_input.py writes to satisfy the
    # schema) are suppressed so every page footer never publishes
    # ``+46 8 000 00 00`` / ``kontakt@example.se`` as if they were real.
    # When no channel is real the column degrades to an honest "Kontakta
    # oss" link pointing at the scaffold contact route. The lucide import
    # is derived from the lines actually emitted so a suppressed channel
    # does not leave an unused icon import in the generated layout.tsx.
    footer_real_phone = real_phone(contact)
    footer_real_email = real_email(contact)
    footer_real_address = real_address_lines(contact)
    footer_contact_lines: list[str] = []
    footer_icons: list[str] = []
    if footer_real_phone is not None:
        footer_contact_lines.append(
            f'              <a href={_jsx_safe_string("tel:" + _phone_href(footer_real_phone))} className="inline-flex items-center gap-2 hover:underline"><Phone className="size-4" />{_jsx_safe_string(footer_real_phone)}</a>'
        )
        footer_icons.append("Phone")
    if footer_real_email is not None:
        footer_contact_lines.append(
            f'              <a href={_jsx_safe_string("mailto:" + footer_real_email)} className="inline-flex items-center gap-2 hover:underline"><Mail className="size-4" />{_jsx_safe_string(footer_real_email)}</a>'
        )
        footer_icons.append("Mail")
    if footer_real_address:
        footer_contact_lines.append(
            f'              <p className="inline-flex items-start gap-2 text-[color:var(--muted)]"><MapPin className="size-4 mt-0.5" />{_jsx_safe_string(", ".join(footer_real_address))}</p>'
        )
        footer_icons.append("MapPin")
    if not footer_contact_lines:
        footer_contact_lines.append(
            f'              <a href={contact_href} className="inline-flex items-center gap-2 font-medium hover:underline">Kontakta oss</a>'
        )
    footer_contact_block = "\n".join(footer_contact_lines)
    footer_icon_import = (
        ("import { " + ", ".join(sorted(footer_icons)) + ' } from "lucide-react";\n')
        if footer_icons
        else ""
    )

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
        og_image_entries = (
            "      {\n"
            f"        url: {_js_string_literal('/og-image.png')},\n"
            f"        alt: {_js_string_literal(og_alt)},\n"
            "        width: 1200,\n"
            "        height: 630,\n"
            '        type: "image/png",\n'
            "      },\n"
            "      {\n"
            f"        url: {_js_string_literal(og_url)},\n"
            f"        alt: {_js_string_literal(og_alt)},\n"
            "        width: 1200,\n"
            "        height: 630,\n"
            "      },\n"
        )
    else:
        og_url = "/og-image-fallback.svg"
        og_alt = company["tagline"] or company["name"]
        # SVG-fallback: explicit ``type`` så Next.js Metadata API
        # serialiserar det som image/svg+xml i meta-taggen. Vissa
        # äldre social-parsers använder type-hinten istället för att
        # sniffa MIME från Content-Type.
        og_image_entries = (
            "      {\n"
            f"        url: {_js_string_literal(og_url)},\n"
            f"        alt: {_js_string_literal(og_alt)},\n"
            "        width: 1200,\n"
            "        height: 630,\n"
            '        type: "image/svg+xml",\n'
            "      },\n"
        )
    metadata_extras.append(
        "  openGraph: {\n"
        f"    title: {_js_string_literal(company['name'])},\n"
        f"    description: {_js_string_literal(company['tagline'])},\n"
        "    images: [\n"
        f"{og_image_entries}"
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
    # B177: load the variant webfont via a <link rel="stylesheet"> in <head>
    # (order-independent of the bundle) instead of a CSS @import that Next would
    # bundle mid-file and the browser would ignore. The href is builder-derived
    # from the variant registry (no customer input); the double-quote guard keeps
    # the JSX attribute well-formed even if a future query carried one.
    font_stylesheet_link = ""
    if font_stylesheet_href and '"' not in font_stylesheet_href:
        font_stylesheet_link = (
            f'        <link rel="stylesheet" href="{font_stylesheet_href}" />\n'
        )

    return (
        'import type { Metadata, Viewport } from "next";\n'
        'import { Geist, Geist_Mono } from "next/font/google";\n'
        f"{footer_icon_import}"
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
        # metadataBase gör relativa OG-/Twitter-bild-URL:er absoluta så att
        # social-delning fungerar i preview/produktion. Utan den varnar
        # Next.js vid varje render och faller tillbaka på localhost. Värdet
        # tas från NEXT_PUBLIC_SITE_URL, annars Vercel-deployens URL, annars
        # localhost. Split-join på localhost-strängen speglar
        # commerce-base/lib/utils.ts och undviker url-literal-lint.
        "const metadataBaseUrl = process.env.NEXT_PUBLIC_SITE_URL\n"
        "  ? process.env.NEXT_PUBLIC_SITE_URL\n"
        "  : process.env.VERCEL_PROJECT_PRODUCTION_URL\n"
        "    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`\n"
        '    : ["http", "://", "localhost", ":", "3000"].join("");\n'
        "\n"
        "export const metadata: Metadata = {\n"
        "  metadataBase: new URL(metadataBaseUrl),\n"
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
        # B177: variantens webfont laddas nu via ``<link rel="stylesheet">``
        # nedan (inte längre via ett ``@import`` i globals.css som Next
        # bundlade mitt i filen och browsern ignorerade). Preconnect:en låter
        # browsern öppna TCP + TLS-handskakningar parallellt med HTML-
        # parsningen, vilket raderar 300-700 ms från LCP enligt webvitals.
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
        f"{font_stylesheet_link}"
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
        f"{footer_contact_block}\n"
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


def render_section_hero(
    dossier: dict,
    *,
    dossier_routes: list[str],
    listing_route: dict | None,
    contact_path: str,
    variant_id: str | None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the hero section for the home route.

    Combines two visual elements that always appear at the top of the
    home page:

      1. Optional operator-uploaded hero image banner (rendered when
         ``dossier.brand.heroImage.filename`` is set).
      2. Variant-aware hero block with CTA, location tag, USPs and
         optional background video, dispatched through
         ``_render_hero_block`` based on ``_hero_style_for`` (which
         consults ``directives.layoutHint`` first, then
         ``_HERO_STYLE_BY_VARIANT`` and finally
         ``_HERO_STYLE_BY_TONE``).

    Path B step 1 (GAP-backend-path-b-section-renderer): this function
    is the first per-section renderer extracted from ``render_home``.
    It must produce byte-identical output to the inline implementation
    it replaces — verified against the LSB / commerce / restaurant
    snapshots taken before the extraction. ``render_home`` still owns
    icon-collection (``_collect_icons_for_pages`` + ``Check`` /
    ``Quote`` cross-section additions) and the page-shell wrapper;
    those move into a shared ``render_route_generic`` dispatcher in
    commit 6.
    """
    company = dossier["company"]
    location = dossier["location"]
    contact = dossier["contact"]
    usp_list = _extract_usps(dossier)
    # kor-2: prefer grounded blueprint hero copy (contentBlocks.home.hero) over
    # the template's company name/tagline. Each override falls back to the
    # template value when the blueprint is absent or the field is empty, so a
    # no-blueprint build renders byte-identically. The raw prompt never reaches
    # here — these strings are produced upstream by briefModel/planning.
    hero_bp = blueprint.hero("home") if blueprint is not None else {}
    hero_headline: str | None = None
    hero_subheadline: str | None = None
    hero_proof_line: str | None = None
    if blueprint is not None:
        hero_headline = blueprint.note_changed(
            "home.hero.headline", hero_bp.get("headline"), company["name"]
        )
        hero_subheadline = blueprint.note_changed(
            "home.hero.subheadline", hero_bp.get("subheadline"), company["tagline"]
        )
        proof = hero_bp.get("proofLine")
        if isinstance(proof, str) and proof.strip():
            proof = proof.strip()
            # B155 honesty: the proof line is an additive element (no template
            # default). Render it + count it as a visible effect only when it
            # adds NEW copy — not when it merely restates the rendered headline
            # or subheadline (that would render a duplicate line and over-report
            # appliedVisibleEffect).
            effective_subheadline = hero_subheadline or company["tagline"]
            effective_headline = hero_headline or company["name"]
            if proof not in (effective_subheadline, effective_headline):
                hero_proof_line = proof
                blueprint.note_applied("home.hero.proofLine")
    # Hero-copy decoupling fix (2026-06-08): an explicit operator hero override
    # (``company.heroHeadline``, set by a follow-up tagline copyDirective) wins
    # over the regenerated blueprint headline so "ändra hero-texten till X" is
    # actually visible in the H1 and survives a rebuild. The blueprint headline
    # is re-derived from briefModel positioning every build and would otherwise
    # overwrite the operator's edit. Absent on init/most builds, so the
    # no-override path stays byte-identical (the field is optional in the schema).
    hero_override = company.get("heroHeadline")
    if isinstance(hero_override, str) and hero_override.strip():
        hero_headline = hero_override.strip()
    # ADR 0043: an explicit operator section-content override
    # (directives.sectionContentOverrides["home.hero.headline"/.subheadline])
    # wins over BOTH the regenerated blueprint copy and the heroHeadline pin so
    # "ändra texten i hero-sektionen till X" is visible in the H1 and survives a
    # rebuild. Absent on init/most builds, so the no-override path is unchanged.
    hero_headline_override = resolve_section_content_override(
        dossier, "hero", "headline"
    )
    if hero_headline_override is not None:
        hero_headline = hero_headline_override
    hero_subheadline_override = resolve_section_content_override(
        dossier, "hero", "subheadline"
    )
    if hero_subheadline_override is not None:
        hero_subheadline = hero_subheadline_override
    spel_cta = (
        '          <a href="/spel" className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Gamepad2 className="size-4" />Spela direkt</a>\n'
        if "/spel" in dossier_routes
        else ""
    )
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
    # kor-2: the CTA follows conversion.primaryCta from the blueprint when set
    # (hard requirement #3). honesty: a phone-promising blueprint label
    # ("Ring oss") is dropped when the phone is a placeholder/missing and the
    # blueprint forbids showing it — the same rule that suppresses the secondary
    # "Ring <nummer>" button (B158). We pass phone availability to the accessor
    # so the gate lives next to the other CTA-honesty logic.
    if blueprint is not None:
        phone_available = real_phone(contact) is not None
        cta_override = blueprint.note_changed(
            "home.hero.primaryCta",
            blueprint.hero_cta("home", phone_available=phone_available),
            hero_cta_label,
        )
        if cta_override is not None:
            hero_cta_label = cta_override
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
    # kor-2: only let the blueprint nudge the hero layout when there is a real
    # hero content block (the rich path). The live kor-1c mock pipeline emits no
    # hero block, so this never fires there — zero regression. The full
    # visual-direction mapping is kor-3b; this is the deliberately light touch.
    style_blueprint = blueprint if (blueprint is not None and hero_bp) else None
    hero_style = _hero_style_for(dossier, variant_id, style_blueprint)
    if style_blueprint is not None and hero_style != _hero_style_for(dossier, variant_id):
        blueprint.note_applied("home.hero.visualTreatment")
    hero_block_jsx = _render_hero_block(
        hero_style,
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
        headline=hero_headline,
        subheadline=hero_subheadline,
        proof_line=hero_proof_line,
    )
    return hero_section_jsx + hero_block_jsx


def render_section_products_intro(dossier: dict) -> str:
    """Render the /produkter route header block (eyebrow + h1 + lead).

    Static Swedish copy today ("Produkter" / "Vårt sortiment" /
    "Här är våra produkter…") — ``dossier`` is reserved for a future
    branch-aware copy switch (e.g. "Smyckessortimentet" / "Klädkollektionen")
    when ecommerce niches get their own copy table.

    Path B step 5 (GAP-backend-path-b-section-renderer): extracted
    from ``render_products`` as a block fragment (no ``<section>``
    wrapper) so it can sit alongside ``render_section_product_grid``
    and the bottom shop-CTA inside the same gradient page section.
    """
    del dossier  # reserved for branch-aware copy
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Produkter</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vårt sortiment</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Här är våra produkter. Hör av dig om du undrar något så hjälper vi dig hela vägen till beställning.</p>\n'
        "          </header>\n"
    )


def _product_grid_items(dossier: dict) -> list[dict]:
    products = dossier.get("products")
    if isinstance(products, list) and products:
        return [item for item in products if isinstance(item, dict)]
    return dossier["services"]


def _product_grid_text(item: dict, key: str, fallback: str) -> str:
    value = item.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _render_product_grid_image(item: dict, label: str, escape) -> str:
    image_url = item.get("imageUrl")
    if not isinstance(image_url, str) or not image_url.strip():
        service_id = _product_grid_text(item, "id", "product")
        return (
            f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(service_id)} className="size-6" /></span>\n'
        )

    product_image = item.get("productImage")
    alt = label
    if isinstance(product_image, dict):
        raw_alt = product_image.get("alt")
        if isinstance(raw_alt, str) and raw_alt.strip():
            alt = raw_alt.strip()
    return (
        '            <div className="mb-5 overflow-hidden rounded-lg border border-[color:var(--border)] bg-[color:var(--accent)]">\n'
        f'              <img src={escape(image_url.strip())} alt={escape(alt)} width={{640}} height={{480}} loading="lazy" className="h-44 w-full object-cover transition duration-300 group-hover:scale-[1.03]" />\n'
        "            </div>\n"
    )


def _render_product_grid_card(item: dict, index: int, escape) -> str:
    item_id = _product_grid_text(item, "id", f"product-{index + 1}")
    label = _product_grid_text(item, "label", _product_grid_text(item, "name", "Produkt"))
    summary = _product_grid_text(item, "summary", "")
    price = _product_grid_text(item, "price", "")
    price_markup = (
        f'            <p className="mt-4 text-sm font-semibold text-[color:var(--primary)]">{escape(price)}</p>\n'
        if price
        else ""
    )
    return (
        f'          <article key={escape(item_id)} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f"{_render_product_grid_image(item, label, escape)}"
        f'            <h2 className="text-xl font-semibold">{escape(label)}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{escape(summary)}</p>\n'
        f"{price_markup}"
        "          </article>"
    )


def render_section_product_grid(dossier: dict) -> str:
    """Render the /produkter product-grid block.

    Iterates ``dossier.products`` when present, otherwise falls back to
    ``dossier.services`` for legacy Project Inputs. Produces a 3-column
    responsive grid of article cards with product image + label + summary
    or an icon fallback when no imageUrl is available.

    Path B step 5: extracted from ``render_products``. Returned as a
    block fragment (no ``<section>`` wrapper) so the route-renderer
    can compose it with the products-intro header and shop-CTA inside
    a single gradient page section.
    """
    products = _product_grid_items(dossier)

    def escape(value: str) -> str:
        return _jsx_safe_string(value)

    items = "\n".join(
        _render_product_grid_card(item, index, escape)
        for index, item in enumerate(products)
    )
    return (
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
    )


def render_section_contact_cta(
    dossier: dict,
    *,
    contact_path: str,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the home-page closing contact-CTA section.

    Produces the primary-coloured full-bleed "Hör av dig idag" banner
    with a single ArrowRight CTA pointing at ``contact_path``. Always
    rendered (no suppression branch) because the home shell has
    historically always closed with a contact prompt; future scaffolds
    that want a different closing section should compose a different
    section list in their sections.json instead.

    kor-2: the button label follows the blueprint's
    ``conversion.primaryCta`` when set (so a booking-driven clinic reads
    "Boka behandling" rather than the generic "Kontakta oss" — exactly
    the clinic scaffold's contact-cta section rule). The CTA only ever
    links to the deterministic ``contact_path``; no phone/email is
    published here, so the honesty rules are unaffected. Falls back to
    "Kontakta oss" with no blueprint, keeping the output byte-identical.

    Path B step 4 (GAP-backend-path-b-section-renderer): extracted
    from ``render_home``.
    """
    contact_href = _route_href(contact_path)
    cta_label = "Kontakta oss"
    if blueprint is not None:
        # honesty: gate a phone-promising blueprint CTA ("Ring oss") when the
        # dossier has no real phone and the blueprint forbids showing it. The
        # banner only ever links to ``contact_path`` (never a tel:), but a label
        # that says "call us" with no phone is still misleading.
        phone_available = real_phone(dossier.get("contact") or {}) is not None
        override = blueprint.note_changed(
            "home.contact-cta.primaryCta",
            blueprint.primary_cta(phone_available=phone_available),
            cta_label,
        )
        if override is not None:
            cta_label = override
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--primary)] text-[color:var(--primary-foreground)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Hör av dig idag</h2>\n'
        '          <p className="max-w-2xl text-base opacity-90 md:text-lg">Beskriv kort vad du behöver så återkommer vi inom en arbetsdag.</p>\n'
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary-foreground)] px-5 py-3 text-sm font-medium text-[color:var(--primary)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
    )


_CONTACT_PAGE_HERO_BODY_BY_VARIANT: dict[tuple[str, str], str] = {
    # B97: kontakt-page hero body copy per CTA-variant + language. The
    # original "Beskriv jobbet kort … med tider och offert." assumed a
    # quote-driven service business and read awkwardly for e-handel
    # (orders/returns/delivery) and booking-flow businesses (book a time).
    # ``_hero_cta_variant`` already encodes the right bucket from
    # conversionGoals + business type + scaffoldId, so we reuse it here
    # for consistency with the hero CTA label/target.
    ("quote", "sv"): "Beskriv jobbet kort så återkommer vi inom en arbetsdag med tider och offert.",
    ("quote", "en"): "Tell us briefly about the job and we'll get back within one business day with times and a quote.",
    ("shop", "sv"): "Frågor om beställning, leverans eller retur? Vi återkommer inom en arbetsdag.",
    ("shop", "en"): "Questions about your order, delivery or return? We get back to you within one business day.",
    ("booking", "sv"): "Berätta kort vad du söker — vi återkommer inom en arbetsdag med en tid som passar.",
    ("booking", "en"): "Tell us briefly what you need — we'll come back within one business day with a time that suits you.",
}


def _contact_page_hero_body(dossier: dict) -> str:
    """Pick the contact-page hero body paragraph for this Project Input.

    B97 fix: branches on ``_hero_cta_variant`` so e-handel and booking
    scaffolds no longer show the quote-driven
    "Beskriv jobbet kort … med tider och offert."-paragraph. Falls back
    to the quote-variant copy when the variant or language is unknown,
    which keeps the existing local-service-business byte-output intact.
    Language is normalised the same way ``_hero_cta_label`` does it so
    non-(sv|en) values fall through to Swedish.
    """
    language = (dossier.get("language") or "sv").strip().lower()
    if language not in ("sv", "en"):
        language = "sv"
    variant = _hero_cta_variant(dossier)
    return _CONTACT_PAGE_HERO_BODY_BY_VARIANT.get(
        (variant, language),
        _CONTACT_PAGE_HERO_BODY_BY_VARIANT[("quote", language)],
    )


def render_section_contact_info(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    """Render the contact-page Phone / Mail / Address card section.

    Produces the gradient-headed /kontakt section with three articles
    (telephone with opening hours, email, multi-line address). The
    address is rendered as ``<address>`` with one ``<span>`` per line
    so the markup degrades gracefully when ``addressLines`` only has
    one entry.

    Path B step 4: extracted from ``render_contact``. Output is
    byte-identical to the inline implementation it replaces.

    B97 (2026-05-26): the hero body paragraph now varies by CTA-variant
    via ``_contact_page_hero_body``. The hero headline ("Hör av dig")
    stays generic across variants — it works for shop, booking and
    quote alike.
    """
    contact = dossier["contact"]
    resend_runtime = _hard_dossier_runtime(dossier, "resend-contact-form")
    hero_body = _contact_page_hero_body(dossier)
    header = (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kontakt</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Hör av dig</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(hero_body)}</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2">\n'
    )
    footer = "          </div>\n        </div>\n      </section>\n"

    # Byte-identical fast path: when no contact field is a placeholder the
    # historical three-article layout is returned verbatim so every
    # existing real-data snapshot/byte-exact test stays unchanged.
    no_placeholders = not (
        is_placeholder_phone(contact.get("phone"))
        or is_placeholder_email(contact.get("email"))
        or is_placeholder_opening_hours(contact.get("openingHours"))
        or is_placeholder_address_lines(contact.get("addressLines"))
    )
    if no_placeholders and resend_runtime is None:
        # Filter individual placeholder lines even on the fast path: a mixed
        # address (real line + fallback line) takes this branch because
        # is_placeholder_address_lines() is True only when EVERY line is a
        # placeholder. real_address_lines() drops the fallback lines; for a
        # fully-real address it returns every line unchanged, so real-data
        # snapshots stay byte-identical.
        address_lines = "\n".join(
            f'                <span className="block">{_jsx_safe_string(line)}</span>'
            for line in real_address_lines(contact)
        )
        return (
            header
            + '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
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
            + footer
        )

    # Honest path: at least one field is a placeholder. Render only the
    # channels the operator actually supplied; never publish dummy
    # phone/email/address. When nothing is real the section degrades to a
    # neutral invitation card so the contact page still reads honestly
    # (the contact route + page hero remain the visitor's call to action).
    phone = real_phone(contact)
    email = real_email(contact)
    hours = real_opening_hours(contact)
    address = real_address_lines(contact)
    language = (dossier.get("language") or "sv").strip().lower()
    cards: list[str] = []
    if phone is not None:
        hours_line = (
            (
                '              <p className="mt-2 inline-flex items-center gap-2 text-sm text-[color:var(--muted)]">\n'
                '                <Clock className="size-4" />\n'
                f"                <span>{_jsx_safe_string(hours)}</span>\n"
                "              </p>\n"
            )
            if hours is not None
            else ""
        )
        cards.append(
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Phone className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Telefon</h2>\n'
            f'              <a href={_jsx_safe_string("tel:" + _phone_href(phone))} className="mt-2 block text-lg font-medium hover:underline">{_jsx_safe_string(phone)}</a>\n'
            + hours_line
            + "            </article>\n"
        )
    if email is not None:
        cards.append(
            '            <article className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><Mail className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">E-post</h2>\n'
            f'              <a href={_jsx_safe_string("mailto:" + email)} className="mt-2 block text-lg font-medium hover:underline">{_jsx_safe_string(email)}</a>\n'
            "            </article>\n"
        )
    if address:
        address_lines = "\n".join(
            f'                <span className="block">{_jsx_safe_string(line)}</span>'
            for line in address
        )
        cards.append(
            '            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">\n'
            '              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><MapPin className="size-5" /></span>\n'
            '              <h2 className="text-base font-semibold">Adress</h2>\n'
            '              <address className="mt-2 not-italic">\n'
            f"{address_lines}\n"
            "              </address>\n"
            "            </article>\n"
        )
    # B159: when no real phone/email is available there is no tel:/mailto:
    # CTA on the page, so the contact route would render with no way to reach
    # the business (and the contact-cta-presence quality-gate check fails on
    # e.g. restaurant /hitta-hit). Add an honest CTA that links to the contact
    # route with CTA text instead of publishing a dummy channel. No tel:/
    # mailto: and no lucide icon (so a fully-placeholder page stays icon-free).
    contact_cta_label = "Get in touch" if language == "en" else "Hör av dig"
    contact_cta_anchor = (
        f'              <a href={_route_href(contact_path)} className="mt-4 inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{_jsx_safe_string(contact_cta_label)}</a>\n'
    )
    if not cards:
        invite_heading = "How to reach us" if language == "en" else "Så når du oss"
        invite_body = (
            "Tell us briefly what you need and we'll get back to you as soon as we can."
            if language == "en"
            else "Beskriv kort vad du söker så återkommer vi så snart vi kan."
        )
        cards.append(
            '            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">\n'
            f'              <h2 className="text-base font-semibold">{_jsx_safe_string(invite_heading)}</h2>\n'
            f'              <p className="mt-2 text-[color:var(--muted)]">{_jsx_safe_string(invite_body)}</p>\n'
            + contact_cta_anchor
            + "            </article>\n"
        )
    elif phone is None and email is None:
        # A real address (or hours) but no phone/email: keep the rendered
        # cards and append a standalone contact CTA so the page still offers
        # an explicit route back to the business.
        cards.append(
            '            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">\n'
            + contact_cta_anchor
            + "            </article>\n"
        )

    if resend_runtime is not None:
        submit_path = str(
            resend_runtime.get("submitTarget") or "/api/contact/resend"
        )
        mode = "integration" if resend_runtime.get("mode") == "integration" else "design"
        heading = (
            "Send us a message"
            if language == "en"
            else "Skicka ett meddelande"
        )
        intro = (
            "Use the form below and we reply by email."
            if language == "en"
            else "Fyll i formuläret nedan så svarar vi via e-post."
        )
        if mode == "design":
            mode_note = (
                "Design mode is active until runtime env is configured."
                if language == "en"
                else "Designläge är aktivt tills runtime-env är konfigurerad."
            )
        else:
            mode_note = (
                "Integration mode is active for this build."
                if language == "en"
                else "Integrationsläge är aktivt för denna build."
            )
        behavior = (
            str(resend_runtime.get("designModeBehavior", "")).strip()
            if mode == "design"
            else str(resend_runtime.get("integrationModeBehavior", "")).strip()
        )
        behavior_line = (
            f'              <p className="mt-2 text-sm text-[color:var(--muted)]">{_jsx_safe_string(behavior)}</p>\n'
            if behavior
            else ""
        )
        design_mode_message = str(
            resend_runtime.get("designModeBehavior", "")
        ).strip()
        if not design_mode_message:
            design_mode_message = (
                "Design mode active: submission is a no-op until RESEND_API_KEY is configured."
            )
        cards.append(
            '            <article className="rounded-xl border border-[color:var(--border)] p-6 md:col-span-2">\n'
            f'              <h2 className="text-base font-semibold">{_jsx_safe_string(heading)}</h2>\n'
            f'              <p className="mt-2 text-[color:var(--muted)]">{_jsx_safe_string(intro)}</p>\n'
            f'              <p className="mt-2 text-sm font-medium text-[color:var(--muted)]">{_jsx_safe_string(mode_note)}</p>\n'
            + behavior_line
            + "              <div className=\"mt-4\">\n"
            + f'                <ResendContactForm submitPath={_jsx_safe_string(submit_path)} designModeAtBuild={"{true}" if mode == "design" else "{false}"} designModeMessage={_jsx_safe_string(design_mode_message)} />\n'
            + "              </div>\n"
            + "            </article>\n"
        )
    return header + "".join(cards) + footer


def render_section_trust_proof(
    dossier: dict,
    *,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the home-page "Varför oss" trust-proof bullet section.

    Pulls ``dossier.trustSignals`` and produces a 2-column ShieldCheck-
    iconed bullet list. Returns "" when the list is empty so the
    section is suppressed entirely (mirrors the pre-existing
    ``trust = []`` handling in ``render_home``).

    kor-2: when the dossier carries no trust signals the section is
    seeded from the blueprint's confirmed ``businessFacts.facts``
    (filtered against ``unknowns`` / ``qualityRisks`` so no ungrounded
    claim — fake cert, invented review — is ever rendered). This only
    fires when the dossier list is empty, so it never changes the
    testimonials-vs-trust-proof coordination in ``render_home`` (that
    branch keys off the dossier's own trustSignals count).

    Path B step 3 (GAP-backend-path-b-section-renderer): extracted
    from ``render_home``. Note that ``render_home`` is also responsible
    for suppressing this section when the richer testimonials section
    has rendered (it sets the local string to "" in that case) — that
    cross-section coordination stays in ``render_home`` until the
    section-driven dispatcher lands in commit 6.
    """
    trust = dossier.get("trustSignals") or []
    if not trust:
        # Gap 1 (trust-honesty): before falling back to the auto-extracted
        # businessFacts narration (which reads like raw metadata, e.g.
        # "Verksamhetstyp: elektriker"), prefer the operator's own
        # uniqueSellingPoints. They are grounded operator claims stated in
        # the wizard, so showing them under "Varför oss" is honest and far
        # stronger than the metadata fallback. USPs are deliberately used
        # ONLY by this neutral strengths section - never by the testimonials
        # ("Sagt om oss"), clinic credentials or agency client-roster
        # sections, which would misframe a self-claim as a quote/cert/client.
        usps = [
            item.strip()
            for item in (dossier.get("uniqueSellingPoints") or [])
            if isinstance(item, str) and item.strip()
        ]
        if usps:
            trust = usps
            # NB: do NOT call blueprint.note_applied here. USPs are dossier
            # (operator) data, not blueprint (LLM Generation Package / Site
            # Brief) data, so crediting the blueprint would inflate
            # appliedVisibleEffect with an effect the blueprint never produced.
            # note_applied below is reserved for the businessFacts fallback,
            # which IS blueprint-derived.
    if not trust and blueprint is not None:
        facts = blueprint.honest_trust_signals()
        if facts:
            trust = facts
            blueprint.note_applied("home.trust-proof")
    if not trust:
        return ""
    trust_items = "\n".join(
        f'            <li key="trust-{i}" className="flex items-start gap-3">\n'
        f'              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-[color:var(--primary)]" />\n'
        f'              <span className="text-base">{_jsx_safe_string(item)}</span>\n'
        "            </li>"
        for i, item in enumerate(trust)
    )
    return (
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


def render_section_about_story(dossier: dict) -> str:
    """Render the about-page header + story-card block.

    Produces the page header (the about-page eyebrow + company name
    h1) and the quote-iconed story card (``company.story``). Used as
    the leading block inside the AboutPage shell.

    Path B step 3: extracted from ``render_about``. Together with
    ``render_section_team`` and the inline gallery/location sub-blocks
    these form the LSB ``about`` route's section list. Output is
    byte-identical to the inline implementation.
    """
    company = dossier["company"]
    # ADR 0043: an operator section-content override wins over the template copy
    # (the about-page H1 + story card). Absent on init/most builds, so the
    # no-override path renders byte-identically.
    about_headline = resolve_section_content_override(dossier, "about-story", "headline")
    about_body = resolve_section_content_override(dossier, "about-story", "body")
    headline = about_headline if about_headline is not None else company["name"]
    body = about_body if about_body is not None else company["story"]
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Om oss</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(headline)}</h1>\n'
        "          </header>\n"
        '          <div className="relative max-w-3xl rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:p-8">\n'
        '            <Quote className="absolute -top-3 -left-3 size-8 text-[color:var(--primary)]/20" />\n'
        f'            <p className="text-lg text-[color:var(--foreground)] leading-relaxed">{_jsx_safe_string(body)}</p>\n'
        "          </div>\n"
    )


def render_section_team(dossier: dict) -> str:
    """Render the about-page team-grid block.

    Iterates ``dossier.company.team`` (array of ``{name, role}``) into
    a 3-column responsive grid of monogram cards. Returns "" when the
    team is empty (B94 fix: no empty "Teamet" + ``<ul>`` shell).

    Path B step 3: extracted from ``render_about``. Output is
    byte-identical to the inline implementation.
    """
    company = dossier["company"]
    team = company.get("team", [])
    if not team:
        return ""
    team_items = "\n".join(
        f'            <li key={_jsx_safe_string(member["name"])} className="rounded-xl border border-[color:var(--border)] p-6">\n'
        f'              <span className="mb-3 inline-flex size-10 items-center justify-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-foreground)] text-sm font-semibold uppercase">{_jsx_safe_string(_member_initials(member["name"]))}</span>\n'
        f'              <p className="text-base font-semibold">{_jsx_safe_string(member["name"])}</p>\n'
        f'              <p className="mt-1 text-sm text-[color:var(--muted)]">{_jsx_safe_string(member["role"])}</p>\n'
        "            </li>"
        for member in team
    )
    return (
        '          <div className="flex flex-col gap-4">\n'
        '            <h2 className="text-2xl font-semibold tracking-tight">Teamet</h2>\n'
        '            <ul className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{team_items}\n"
        "            </ul>\n"
        "          </div>\n"
    )


def render_section_services_summary(
    dossier: dict,
    *,
    listing_route: dict | None,
) -> str:
    """Render the home-page services-summary section.

    Produces the service-grid block (3-column on lg, 2-column on md)
    with branch-aware listing copy (e.g. "Menyn" for restaurants,
    "Sortimentet" for ecommerce) and an optional listing-link CTA
    that points at ``listing_route`` when set.

    Path B step 2 (GAP-backend-path-b-section-renderer): second
    per-section renderer extracted from ``render_home``. Output is
    byte-identical to the pre-extraction inline implementation,
    verified against LSB / commerce / restaurant snapshots.
    """
    services = dossier["services"]
    services_grid = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--card,var(--background))] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'              <span className="mb-4 inline-flex size-10 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)] transition-transform group-hover:scale-105"><{_icon_for_service(svc["id"])} className="size-5" /></span>\n'
        f'              <h3 className="text-lg font-semibold">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
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
    return (
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
    )


def _collect_home_icons(dossier: dict, dossier_routes: list[str]) -> list[str]:
    """Compose the icon-import set for the LSB home page.

    Mirrors the pre-shim render_home logic: starts with
    ``_collect_icons_for_pages``, adds ``Check`` when any USP chips
    will render, and adds ``Quote`` when either the story-section or
    a testimonials-cards section will render. Lifted into its own
    helper so the render_home shim can reuse it.
    """
    services = dossier["services"]
    icons_used = _collect_icons_for_pages(services, dossier_routes)
    if _extract_usps(dossier) and "Check" not in icons_used:
        icons_used = sorted({*icons_used, "Check"})
    story_text = (dossier.get("company") or {}).get("story") or ""
    trust_count = sum(
        1
        for item in (dossier.get("trustSignals") or [])
        if isinstance(item, str) and item.strip()
    )
    needs_quote_icon = (
        bool(str(story_text).strip()) or trust_count >= _HOME_TESTIMONIAL_MIN_ITEMS
    )
    if needs_quote_icon and "Quote" not in icons_used:
        icons_used = sorted({*icons_used, "Quote"})
    return icons_used


# Render-time allowlist for inline section injection (ADR 0038, defense in
# depth): ``(scaffoldId, routeId) -> allowed section ids``. The schema permits
# any string in ``directives.mountedSections[].sectionId``, and apply enforces
# the canonical allowlist when IT writes the directive - but a hand-edited or
# stale Project Input must not be able to inject an arbitrary registered
# section (e.g. ``service-list``) onto a page the ADR never sanctioned. This
# table MIRRORS ``INLINE_SECTION_PLACEMENTS`` + ``INLINE_SECTION_SCAFFOLDS`` +
# ``INLINE_SECTION_ROUTES`` in ``packages/generation/followup/
# section_directives.py``; it is duplicated here (same pattern as
# ``_FORBIDDEN_ENV_PATTERN`` in quality_gate/checks.py) because the build layer
# must not import the followup layer. Parity is locked by
# ``tests/test_section_directives.py`` so the two cannot silently drift.
_INLINE_SECTION_ALLOWLIST: dict[tuple[str, str], frozenset[str]] = {
    ("local-service-business", "home"): frozenset({"hours-summary", "gallery"}),
    ("ecommerce-lite", "home"): frozenset({"hours-summary", "gallery"}),
}

# Positions that may MOVE a section that is already part of the route's default
# order (ADR 0042). Without an explicit position an already-present section
# stays an honest no-op (the ADR 0038 duplicate gate), so old directives keep
# byte-identical output.
_MOVABLE_POSITIONS: frozenset[str] = frozenset({"top", "bottom", "before-contact"})


def _mounted_section_ids_for_route(
    dossier: dict,
    route_id: str,
    *,
    existing_section_ids: list[str],
    render_kwargs: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Resolve gated inline section injections for a route (ADR 0038).

    Reads ``dossier.directives.mountedSections`` and returns
    ``(top_ids, bottom_ids)`` - the section ids to inject at the top (right after
    the leading section) and at the bottom (before the closing CTA) of the
    route's section order. The ``before-contact`` position and the default
    (no position) both land in ``bottom_ids``.

    Render-time honesty gates - an entry is dropped (never raised on) unless ALL
    hold, so a mounted section can never appear as an empty or phantom block:

    - the entry targets THIS ``route_id``;
    - ``(scaffoldId, routeId, sectionId)`` is in ``_INLINE_SECTION_ALLOWLIST``
      (the ADR 0038 canonical set - a hand-edited/stale Project Input cannot
      inject an arbitrary registered section);
    - ``sectionId`` has a registered renderer in ``_SECTION_RENDERERS``
      (``render_route_generic`` would SystemExit on an unknown id);
    - the section is not already in ``existing_section_ids`` (no duplicate) —
      UNLESS the entry carries an explicit position in ``_MOVABLE_POSITIONS``,
      in which case it is a MOVE (ADR 0042): the id is returned so the caller
      relocates the section to the requested slot instead of dropping the
      operator's placement intent. The caller MUST remove a returned id from
      its default order before inserting (``render_home`` does), so the
      section still renders exactly once;
    - the section renders non-empty grounded content for this dossier (the
      renderer returns "" when the operator supplied no content).

    Deterministic, offline. Order-preserving; a section id is injected at most
    once even if requested twice.
    """
    directives = dossier.get("directives")
    if not isinstance(directives, dict):
        return [], []
    entries = directives.get("mountedSections")
    if not isinstance(entries, list):
        return [], []
    scaffold_id = dossier.get("scaffoldId")
    allowed = (
        _INLINE_SECTION_ALLOWLIST.get((scaffold_id, route_id))
        if isinstance(scaffold_id, str)
        else None
    )
    if not allowed:
        return [], []
    existing = set(existing_section_ids)
    top_ids: list[str] = []
    bottom_ids: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("routeId") != route_id:
            continue
        section_id = entry.get("sectionId")
        if not isinstance(section_id, str) or not section_id:
            continue
        if section_id not in allowed:
            continue
        if section_id in seen:
            continue
        position = entry.get("position")
        if section_id in existing and position not in _MOVABLE_POSITIONS:
            # Already in the default order and no explicit position: honest
            # no-op (ADR 0038 duplicate gate). With an explicit position the
            # entry is a MOVE (ADR 0042) and falls through; the caller removes
            # the default occurrence before inserting.
            continue
        renderer = _SECTION_RENDERERS.get(section_id)
        if renderer is None:
            continue
        # Grounded-content gate: only inject when the section actually renders.
        if not _call_section_renderer(renderer, dossier, render_kwargs).strip():
            continue
        seen.add(section_id)
        if position == "top":
            top_ids.append(section_id)
        else:
            # default / "before-contact" / "bottom" all land before the CTA.
            bottom_ids.append(section_id)
    return top_ids, bottom_ids


def render_home(
    dossier: dict,
    dossier_routes: list[str],
    *,
    listing_route: dict | None = None,
    contact_path: str = "/kontakt",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Home page renderer — Path B step 11 dispatcher shim.

    The actual section composition lives in ``render_section_*``
    helpers and is dispatched through ``render_route_generic`` from
    the section list declared in
    ``local-service-business/sections.json``. The shim still owns
    two cross-section concerns that the dispatcher cannot infer
    from the scaffold contract alone:

    1. Icon-import line — composed deterministically from the
       services list, USP chips and story/testimonials presence
       (see ``_collect_home_icons``).
    2. Testimonials suppress trust-proof — when the dossier carries
       enough ``trustSignals`` for the testimonials cards section
       to render, the classic trust-proof bullet list is removed
       from the effective section list so the same proof never
       renders twice.

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
    icons_used = _collect_home_icons(dossier, dossier_routes)
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'

    # Cross-section coordination: testimonials cards (when they
    # render at all) suppress the classic trust-proof bullet list
    # so the same proof is not shown twice. We pre-compute the
    # testimonials body so the home-page section order can drop
    # trust-proof before render_route_generic walks the list.
    testimonials_will_render = bool(_render_home_testimonials_section(dossier))

    # The home-page section order is owned by the renderer (not
    # the scaffold contract) because LSB interleaves required and
    # optional sections — story / gallery / testimonials sit
    # between services-summary and trust-proof, and faq sits
    # between trust-proof and the closing contact-cta. sections.
    # json declares which sections exist; the shim arranges them.
    section_order: list[str] = [
        "hero",
        "service-summary",
        "story",
        "gallery",
        "testimonials",
    ]
    if not testimonials_will_render:
        section_order.append("trust-proof")
    section_order.append("faq")

    # ADR 0038: inject section_add inline placements from
    # ``directives.mountedSections`` before the closing contact-cta. The gate
    # uses the SAME render kwargs the dispatcher passes each section so the
    # grounded-content check renders the candidate exactly as it will appear.
    # Default / before-contact / bottom land before the CTA; top lands right
    # after the hero. ``contact-cta`` is appended LAST so an injected block can
    # never displace the closing call-to-action.
    render_kwargs: dict[str, Any] = {
        "dossier_routes": dossier_routes,
        "listing_route": listing_route,
        "contact_path": contact_path,
        "variant_id": variant_id,
        "blueprint": blueprint,
    }
    top_ids, bottom_ids = _mounted_section_ids_for_route(
        dossier,
        "home",
        existing_section_ids=[*section_order, "contact-cta"],
        render_kwargs=render_kwargs,
    )
    # ADR 0042 move semantics: an id returned for a section that is already in
    # the default order is a MOVE (explicit position), so the default
    # occurrence is removed first — the section renders exactly once, at the
    # operator's slot. Ids not in the default order pass through unchanged.
    moved = {sid for sid in (*top_ids, *bottom_ids) if sid in section_order}
    if moved:
        section_order = [sid for sid in section_order if sid not in moved]
    if top_ids:
        # After hero (index 0), before the rest of the body.
        section_order[1:1] = top_ids
    section_order.extend(bottom_ids)
    section_order.append("contact-cta")

    effective_sections = {
        "home": {"requiredSections": section_order, "optionalSections": []}
    }

    body = render_route_generic(
        dossier,
        route_id="home",
        scaffold_sections=effective_sections,
        dossier_routes=dossier_routes,
        listing_route=listing_route,
        contact_path=contact_path,
        variant_id=variant_id,
        blueprint=blueprint,
    )

    return (
        icon_import + "\n"
        "export default function Home() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + body
        + "    </main>\n"
        "  );\n"
        "}\n"
    )


_SERVICE_LIST_TREATMENT_DEFAULT = "card-grid"


def render_section_service_list(
    dossier: dict,
    *,
    contact_path: str,
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the service-list section for the /tjanster route.

    Path B step 2 (GAP-backend-path-b-section-renderer): second
    per-section renderer extracted from ``render_services``.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of four private renderers:

    * ``card-grid`` — the byte-identical default. 3-col gradient-
      headered grid with icon-bubble + label + summary. Mapped
      implicitly to ``midnight-counsel`` and ``pulse-fit``
      (default-keep) so the LSB look most operators expect stays
      stable.
    * ``alternating-rows`` — vertical sequence where odd rows put
      the icon on the left and the copy on the right, even rows
      flip the layout. Reads as a "we and you, together" rhythm.
      Mapped to ``warm-craft``.
    * ``icon-strip`` — compact horizontal strip with small icon-
      label pills, summaries underneath the strip. Reads as a
      minimalist contents bar. Mapped to ``clinical-calm``.
    * ``tabular`` — formal row listing without card chrome, thin
      ``border-b`` separators and a column header. Reads as a
      service catalogue. Mapped to ``nordic-trust``.

    Returns "" through every treatment when no services are
    declared so the dispatcher does not emit an empty list scaffold.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "service-list",
        default=_SERVICE_LIST_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "service-list"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("service-list")
            if blueprint is not None
            else None
        ),
    )
    if treatment == "alternating-rows":
        return _render_service_list_alternating_rows(dossier, contact_path)
    if treatment == "icon-strip":
        return _render_service_list_icon_strip(dossier, contact_path)
    if treatment == "tabular":
        return _render_service_list_tabular(dossier, contact_path)
    return _render_service_list_card_grid(dossier, contact_path)


def _service_list_header() -> str:
    """Shared eyebrow + h1 + lede markup for every service-list treatment."""
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Tjänster</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Vad vi gör</h1>\n'
        '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">Allt vi erbjuder, samlat på ett ställe. Klicka på en tjänst eller hör av dig direkt.</p>\n'
        "          </header>\n"
    )


def _render_service_list_card_grid(dossier: dict, contact_path: str) -> str:
    """3-col gradient-headered card grid (the default treatment).

    Kept byte-identical to the pre-Phase-2 output of
    ``render_section_service_list`` so existing snapshots are not
    invalidated by introducing treatment dispatch.
    """
    services = dossier["services"]
    contact_href = _route_href(contact_path)
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
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        + _service_list_header()
        + '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        + f"{items}\n"
        + "          </div>\n"
        + f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
    )


def _render_service_list_alternating_rows(
    dossier: dict, contact_path: str
) -> str:
    """Vertical sequence of left-/right-flipped icon+copy rows.

    Each service is its own row spanning the full container width;
    odd rows put the icon-tile on the left and copy on the right,
    even rows flip the layout via ``md:flex-row-reverse``. Reads
    as a back-and-forth conversation rather than a uniform card
    grid. Mapped to ``warm-craft``.
    """
    services = dossier["services"]
    contact_href = _route_href(contact_path)
    items = "\n".join(
        (
            f'          <li key={_jsx_safe_string(svc["id"])} className="flex flex-col items-start gap-6 rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 md:flex-row md:items-center md:gap-10 md:p-10'
            + (' md:flex-row-reverse' if idx % 2 == 0 else '')
            + '">\n'
            f'            <span className="inline-flex size-16 shrink-0 items-center justify-center rounded-2xl bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(svc["id"])} className="size-7" /></span>\n'
            f'            <div className="flex flex-col gap-2">\n'
            f'              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            "            </div>\n"
            "          </li>"
        )
        for idx, svc in enumerate(services, start=1)
    )
    cta_label = _hero_cta_label(dossier)
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _service_list_header()
        + '          <ul className="flex flex-col gap-6">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
    )


def _render_service_list_icon_strip(
    dossier: dict, contact_path: str
) -> str:
    """Compact horizontal icon-label strip with summaries underneath.

    The strip is a single row of small icon-label pills (each
    service rendered as a short pill); the summaries follow on a
    quieter grid beneath. Reads as a minimalist "what we do at a
    glance" bar. Mapped to ``clinical-calm``.
    """
    services = dossier["services"]
    contact_href = _route_href(contact_path)
    pills = "\n".join(
        (
            f'              <li key={_jsx_safe_string(svc["id"])} className="inline-flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[color:var(--background)] px-4 py-2 text-sm font-medium tracking-tight">\n'
            f'                <{_icon_for_service(svc["id"])} className="size-4 text-[color:var(--accent)]" />\n'
            f'                <span>{_jsx_safe_string(svc["label"])}</span>\n'
            "              </li>"
        )
        for svc in services
    )
    cards = "\n".join(
        (
            f'              <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-2 border-t border-[color:var(--border)] pt-6">\n'
            f'                <h2 className="text-lg font-semibold tracking-tight">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'                <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            "              </article>"
        )
        for svc in services
    )
    cta_label = _hero_cta_label(dossier)
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _service_list_header()
        + '          <ul className="flex flex-wrap gap-2">\n'
        + f"{pills}\n"
        + "          </ul>\n"
        + '          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
    )


def _render_service_list_tabular(dossier: dict, contact_path: str) -> str:
    """Formal row listing with thin separators and a column header.

    No card chrome — each service is a row spanning the full
    container width with icon / label / summary columns and a
    thin ``border-b``. Reads as a service catalogue rather than
    a marketing grid. Mapped to ``nordic-trust``.
    """
    services = dossier["services"]
    contact_href = _route_href(contact_path)
    rows = "\n".join(
        (
            f'              <li key={_jsx_safe_string(svc["id"])} className="grid items-center gap-4 border-b border-[color:var(--border)] py-6 md:grid-cols-[3rem_14rem_1fr] md:gap-8">\n'
            f'                <span className="inline-flex size-10 items-center justify-center rounded-md bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(svc["id"])} className="size-5" /></span>\n'
            f'                <h2 className="text-base font-semibold tracking-tight md:text-lg">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'                <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            "              </li>"
        )
        for svc in services
    )
    cta_label = _hero_cta_label(dossier)
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _service_list_header()
        + '          <div className="flex flex-col">\n'
        + '            <div className="grid gap-4 border-b border-[color:var(--border)] pb-3 text-xs font-mono uppercase tracking-widest text-[color:var(--muted)] md:grid-cols-[3rem_14rem_1fr] md:gap-8">\n'
        + '              <span aria-hidden />\n'
        + "              <span>Tjänst</span>\n"
        + "              <span>Beskrivning</span>\n"
        + "            </div>\n"
        + '            <ul className="flex flex-col">\n'
        + f"{rows}\n"
        + "            </ul>\n"
        + "          </div>\n"
        + f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{cta_label}<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
    )


def render_services(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
    blueprint: RenderBlueprint | None = None,
) -> str:
    services = dossier["services"]
    icons_used = sorted({_icon_for_service(svc["id"]) for svc in services} | {"ArrowRight"})
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    # Path B step 2 — service-list section now produced by
    # ``render_section_service_list``. Section design-treatments
    # Phase 2: forward the dossier's variantId so the section can
    # pick a treatment (card-grid / alternating-rows / icon-strip /
    # tabular). Path B native scaffolds get variant_id threaded
    # through render_route_generic; LSB still goes through this
    # shim so the variant lookup happens here instead.
    # kor-3b: also forward the blueprint so the service-list section can
    # honour the Generation Package's visualDirection pick. LSB does not go
    # through render_route_generic, so without this thread the headline
    # service-list example (tabular vs alternating-rows) could never see the
    # blueprint.
    service_list_section = annotate_section_marker(
        render_section_service_list(
            dossier,
            contact_path=contact_path,
            variant_id=dossier.get("variantId"),
            blueprint=blueprint,
        ),
        "service-list",
    )
    return (
        icon_import + "\n"
        "export default function ServicesPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        f"{service_list_section}"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def _render_collection_page(
    dossier: dict,
    *,
    contact_path: str,
    component_name: str,
    eyebrow: str,
    heading: str,
    intro: str,
    cta_label: str | None = None,
) -> str:
    items_source = dossier["services"]
    contact_href = _route_href(contact_path)
    icons_used = sorted(
        {_icon_for_service(item["id"]) for item in items_source} | {"ArrowRight"}
    )
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    items = "\n".join(
        f'          <article key={_jsx_safe_string(item["id"])} className="group rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-[color:var(--primary)] hover:shadow-md">\n'
        f'            <span className="mb-4 inline-flex size-12 items-center justify-center rounded-lg bg-[color:var(--accent)] text-[color:var(--accent-foreground)]"><{_icon_for_service(item["id"])} className="size-6" /></span>\n'
        f'            <h2 className="text-xl font-semibold">{_jsx_safe_string(item["label"])}</h2>\n'
        f'            <p className="mt-3 text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(item["summary"])}</p>\n'
        "          </article>"
        for item in items_source
    )
    label = cta_label or _hero_cta_label(dossier)
    return (
        icon_import + "\n"
        f"export default function {component_name}() {{\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        # Sidnivå-grov markering: collection-sidorna (treatments/expertise/
        # work) är en service-list-presentation i en enda <section>.
        '      <section data-section-id="service-list" className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        '          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{items}\n"
        "          </div>\n"
        f'          <a href={contact_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{label}<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_treatments(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    return _render_collection_page(
        dossier,
        contact_path=contact_path,
        component_name="TreatmentsPage",
        eyebrow="Behandlingar",
        heading="Behandlingar och vård",
        intro=(
            "Här är behandlingarna samlade med tydliga beskrivningar så "
            "besökaren snabbt hittar rätt nästa steg."
        ),
        cta_label="Kontakta kliniken",
    )


def render_expertise(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    return _render_collection_page(
        dossier,
        contact_path=contact_path,
        component_name="ExpertisePage",
        eyebrow="Expertis",
        heading="Våra expertisområden",
        intro=(
            "En strukturerad överblick över de områden där teamet hjälper "
            "kunder från första fråga till genomförande."
        ),
        cta_label="Boka ett samtal",
    )


def render_work(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    return _render_collection_page(
        dossier,
        contact_path=contact_path,
        component_name="WorkPage",
        eyebrow="Arbeten",
        heading="Utvalda arbeten",
        intro=(
            "Projekt, case och uppdrag presenteras som konkreta bevis på "
            "studions riktning och hantverk."
        ),
        cta_label="Prata om ett projekt",
    )


def render_about(dossier: dict) -> str:
    company = dossier["company"]
    location = dossier["location"]
    areas_html = ", ".join(location["serviceAreas"])
    location_section = ""
    # B98: "Områden vi arbetar i" är meaningless för e-handel (kunden får
    # produkter levererade, det finns inga lokala serviceområden i samma
    # bemärkelse). Suppressas för ecommerce-lite. För övriga scaffolds
    # gäller fortsatt bara B104-checken (country-only suppression).
    scaffold_id = (dossier.get("scaffoldId") or "").strip().lower()
    if (
        not _location_is_country_only(location)
        and scaffold_id != "ecommerce-lite"
    ):
        location_section = (
            '          <div className="flex flex-col gap-2">\n'
            '            <h2 className="inline-flex items-center gap-2 text-2xl font-semibold tracking-tight"><MapPin className="size-5" />Områden vi arbetar i</h2>\n'
            f'            <p className="text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(areas_html)}</p>\n'
            "          </div>\n"
        )
    # Path B step 3 — about-story (header + quote-iconed story card)
    # and team-grid blocks are now produced by ``render_section_about_story``
    # and ``render_section_team``. Output is byte-identical.
    about_story_block = render_section_about_story(dossier)
    team_section = render_section_team(dossier)

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
        # Sidnivå-grov markering: om-oss-sidan är en enda <section> med
        # flera logiska block; about-story är det dominerande innehållet.
        '      <section data-section-id="about-story" className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        f"{about_story_block}"
        f"{team_section}"
        f"{gallery_section_jsx}"
        f"{location_section}"
        "        </div>\n"
        "      </section>\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_contact(dossier: dict, *, contact_path: str = "/kontakt") -> str:
    # Path B step 4 — contact-info card grid (Phone / Mail / Address)
    # is produced by ``render_section_contact_info``. The lucide import is
    # derived from the icons the section actually emits (the same approach
    # the dispatched scaffolds use) so a suppressed placeholder channel
    # does not leave an unused icon import. For fully-real contact data the
    # section emits Phone/Clock/Mail/MapPin and the import is byte-identical
    # to the previous static ``Clock, Mail, MapPin, Phone`` line.
    #
    # ``contact_path`` is threaded through so the B159 honest-CTA fallback
    # (no real phone/email) links back to the scaffold's contact route
    # (``/hitta-hit`` for restaurant-hospitality, ``/kontakt`` elsewhere).
    contact_info_section = annotate_section_marker(
        render_section_contact_info(dossier, contact_path=contact_path),
        "contact-info",
    )
    icons = sorted(set(_DISPATCHED_ICON_PATTERN.findall(contact_info_section)))
    icon_import = (
        ("import { " + ", ".join(icons) + ' } from "lucide-react";\n' + "\n")
        if icons
        else ""
    )
    form_import = (
        'import { ResendContactForm } from "@/components/resend-contact-form";\n\n'
        if _hard_dossier_runtime(dossier, "resend-contact-form") is not None
        else ""
    )
    return (
        form_import
        + icon_import
        + "export default function ContactPage() {\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        f"{contact_info_section}"
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
    products = _product_grid_items(dossier)
    contact_href = _route_href(contact_path)
    icons_used = sorted(
        {
            _icon_for_service(_product_grid_text(item, "id", f"product-{index + 1}"))
            for index, item in enumerate(products)
        }
        | {"ArrowRight", "ShoppingBag"}
    )
    icon_import = "import { " + ", ".join(icons_used) + ' } from "lucide-react";\n'
    # Path B step 5 — products-intro header and product-grid blocks
    # are now produced by ``render_section_products_intro`` and
    # ``render_section_product_grid``. Output is byte-identical.
    products_intro_block = render_section_products_intro(dossier)
    product_grid_block = render_section_product_grid(dossier)
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
        # Sidnivå-grov markering: produktsidan är en enda <section> där
        # product-grid är det dominerande innehållet.
        '      <section data-section-id="product-grid" className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        f"{products_intro_block}"
        f"{product_grid_block}"
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
    *,
    section_id: str | None = None,
) -> str:
    """Reusable hero-style header for the wizard-route renderers.

    Matches the eyebrow + h1 idiom of the existing about/services
    pages so the new routes feel consistent with the rest of the
    generated site. ``intro`` renders as a muted lead paragraph and
    is dropped when empty. ``section_id`` stamps the opening
    ``<section>`` with ``data-section-id`` (preview-markeringskontraktet)
    — wizard-sidorna är en enda <section>, så sidans dominerande
    innehåll ger id:t.
    """
    intro_jsx = ""
    if intro:
        intro_jsx = (
            '            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">'
            f"{_jsx_safe_string(intro)}</p>\n"
        )
    marker_attr = f' data-section-id="{section_id}"' if section_id else ""
    return (
        f'      <section{marker_attr} className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
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


def _faq_pairs(
    dossier: dict,
    blueprint: RenderBlueprint | None = None,
) -> list[tuple[str, str]]:
    """Compose FAQ items from the dossier without inventing facts.

    kor-2: when the blueprint carries a grounded FAQ list
    (``contentBlocks.<route>.faq``) it replaces the three generic
    template questions, so the four baseline branches can read with
    industry-specific answers instead of the same mall. The real
    opening-hours pair is still appended in both paths, so honest
    contact data is never dropped. With no blueprint FAQ block the
    template defaults render byte-identically.
    """
    pairs: list[tuple[str, str]] = []
    bp_pairs = blueprint.faq(("home", "faq")) if blueprint is not None else []
    if bp_pairs:
        pairs.extend(bp_pairs)
        if blueprint is not None:
            blueprint.note_applied("home.faq")
    else:
        location = dossier.get("location") or {}
        area_values = location.get("serviceAreas") if isinstance(location, dict) else None
        if isinstance(area_values, list) and area_values:
            areas = ", ".join(str(area) for area in area_values if isinstance(area, str))
        else:
            city = location.get("city") if isinstance(location, dict) else None
            country = location.get("country") if isinstance(location, dict) else None
            areas = str(city or country or "ditt närområde")
        for question, answer_template in _FAQ_DEFAULT_SV:
            pairs.append((question, answer_template.format(areas=areas)))
    contact = dossier.get("contact") or {}
    # Only add the opening-hours FAQ for real hours - a placeholder
    # ("Mån-Fre 09:00-17:00") must not be presented as a fact (contact-honesty
    # slice 2026-06-02).
    opening = real_opening_hours(contact)
    if opening is not None:
        pairs.append(
            (
                "När har ni öppet?",
                f"Vi har öppet {opening}.",
            )
        )
    return pairs


def render_faq(
    dossier: dict,
    *,
    contact_path: str = "/kontakt",
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the wizard-driven /faq route.

    Deterministic FAQ built from the dossier: three default questions
    plus an opening-hours question only when ``contact.openingHours`` is a
    real (non-placeholder) value. No invented service prices or warranties —
    operator-specific answers belong on the operator's wishlist, not in v1
    codegen. kor-2 lets a grounded blueprint FAQ replace the generic
    template questions (see ``_faq_pairs``).
    """
    pairs = _faq_pairs(dossier, blueprint)
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
            section_id="faq",
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
    # restaurant-hospitality (Path A — render_menu + render_booking)
    "warm-bistro": "centered",
    "nordic-fine-dining": "split",
    "casual-cafe": "gradient",
    "midnight-bar": "split",
    # clinic-healthcare (Path B native — _DISPATCHED_SCAFFOLDS)
    "clinic-calm": "split",
    "warm-care": "centered",
    "modern-precision": "split",
    # professional-services (Path B native — _DISPATCHED_SCAFFOLDS)
    "legal-classic": "split",
    "consulting-modern": "split",
    "accounting-trust": "centered",
    # agency-studio (Path B native — _DISPATCHED_SCAFFOLDS)
    "studio-monochrome": "split",
    "editorial-warm": "centered",
    "bold-electric": "split",
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


def _hero_style_for(
    dossier: dict,
    variant_id: str | None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Resolve which hero layout to render for the home page.

    Precedence:

    1. ``dossier["directives"]["layoutHint"]`` — operator override
       coming from the wizard's visual step. Frontend may set
       ``"gradient" | "centered" | "split"``; anything else is ignored
       so we never trust unknown strings.
    2. ``blueprint.hero_layout()`` — kor-2 light touch: the Generation
       Package ``visualDirection.heroStyle`` mapped onto a renderer
       layout. Sits below the operator hint (the operator always wins)
       and above the variant default. ``None`` (no blueprint or an
       unmapped style) leaves the variant/tone defaults untouched. The
       full visual-direction mapping is kor-3b.
    3. ``_HERO_STYLE_BY_VARIANT[variant_id]`` — vibe-aware default. A
       warm-craft variant gets a centered hero by default, a noir-
       editorial gets a split hero, etc.
    4. ``_HERO_STYLE_BY_TONE[normalized_tone]`` — tone-aware fallback
       (Sprint B/3). Triggas när varianten saknar mapping (framtida
       experimentella variants) ELLER när variantId helt saknas men
       tone är satt. Svenska wizard-tags ("Lekfull", "Lugn och
       förtroendeingivande") normaliseras via ``_normalize_tone_key``
       så samma mapping fungerar oavsett om operatören valde tone
       via chips eller skrev en engelsk semantisk key.
    5. ``"gradient"`` — universal fallback. Matches the pre-#2 behavior
       so tests that call ``render_home`` with no variant_id keep the
       same JSX shape they used to.
    """
    directives = dossier.get("directives")
    if isinstance(directives, dict):
        hint = directives.get("layoutHint")
        if isinstance(hint, str) and hint in _VALID_HERO_STYLES:
            return hint
    if blueprint is not None:
        bp_layout = blueprint.hero_layout()
        if bp_layout in _VALID_HERO_STYLES:
            return bp_layout
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
    headline: str | None = None,
    subheadline: str | None = None,
    proof_line: str | None = None,
) -> str:
    """Render the hero <section> for the home page in one of three
    layouts. Customer-text (company.name, company.tagline) is always
    wrapped via ``_jsx_safe_string`` so the JSX-escape tests (B30)
    pass for every variant.

    kor-2: ``headline`` / ``subheadline`` override the company name /
    tagline when the Generation Package carries grounded hero copy, and
    ``proof_line`` adds an optional supporting line beneath the
    subheadline. All three default to ``None`` so a no-blueprint call
    renders byte-identically to the pre-kor-2 hero.

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
    safe_name = _jsx_safe_string(headline or company["name"])
    safe_tagline = _jsx_safe_string(subheadline or company["tagline"])
    # kor-2: optional grounded proof line beneath the subheadline. Emitted only
    # when the blueprint supplies one, so the no-blueprint hero is unchanged.
    # Two indentation variants match the centered/gradient (10 spaces) and
    # split (12 spaces) column layouts.
    proof_p_10 = (
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)]/80 leading-relaxed">{_jsx_safe_string(proof_line)}</p>\n'
        if proof_line
        else ""
    )
    proof_p_12 = (
        f'            <p className="max-w-xl text-base text-[color:var(--foreground)]/80 leading-relaxed">{_jsx_safe_string(proof_line)}</p>\n'
        if proof_line
        else ""
    )
    usp_list = usps or []
    usp_chips_left = _render_hero_usp_chips(usp_list, centered=False)
    usp_chips_centered = _render_hero_usp_chips(usp_list, centered=True)
    video_layer = _render_hero_background_video(background_video, hero_asset)
    has_video = bool(video_layer)
    # B158: never render the secondary "Ring <nummer>"-CTA when the phone is
    # the B88 placeholder. A ``tel:+4680000000``-button looks broken and
    # publishes a dummy number; the primary CTA (``hero_cta_href`` → contact/
    # booking route) still gives the visitor a path, so dropping the dummy-
    # phone button is the honest degrade. Computed once and reused across all
    # three hero layouts so real-phone output stays byte-identical.
    phone_cta_button = ""
    if not is_placeholder_phone(contact_phone):
        phone_cta_button = (
            f'            <a href={_jsx_safe_string("tel:" + _phone_href(contact_phone))} className="inline-flex w-fit items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />Ring {_jsx_safe_string(contact_phone)}</a>\n'
        )
    cta_buttons = (
        '          <div className="flex flex-wrap gap-3">\n'
        f'            <a href={hero_cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
        f"{phone_cta_button}"
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
            f"{proof_p_10}"
            f"{usp_chips_centered}"
            '          <div className="flex flex-wrap items-center justify-center gap-3">\n'
            f'            <a href={hero_cta_href} className="inline-flex w-fit items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity">{hero_cta_label}<ArrowRight className="size-4" /></a>\n'
            f"{phone_cta_button}"
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
            f"{proof_p_12}"
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
        f"{proof_p_10}"
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
    # ADR 0043: an operator section-content override for the home story body
    # wins over (and can force-render) the company.story copy. Absent on init/
    # most builds, so the no-override path renders byte-identically.
    story_override = resolve_section_content_override(dossier, "story", "body")
    if story_override is not None:
        story = story_override
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


def _render_home_faq_section(
    dossier: dict,
    *,
    has_faq_route: bool,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render a compact FAQ section on the home page using the
    deterministic ``_faq_pairs`` helper that ``render_faq`` already
    uses for the dedicated /faq route. Shows up to
    ``_HOME_FAQ_MAX_ITEMS`` pairs in a 2-column grid; when the dossier
    has a /faq route the section ends with a "Se alla frågor"-CTA
    that links to it, otherwise the CTA is omitted to avoid ghost
    routes.

    ``_faq_pairs`` returns 3–4 deterministic pairs (three defaults
    plus an opening-hours pair when ``contact.openingHours`` is a real
    non-placeholder value), so this section always renders when called —
    there's no
    operator-data dependency that could short-circuit it to ``""``.
    Callers that want to suppress FAQs entirely should skip calling
    this helper.

    Icon dependency: ``ArrowRight`` (already in render_home's icon-
    set whenever ``listing_link`` is rendered, so the caller doesn't
    need additional whitelisting; we still soft-import via the icon
    collector to be explicit).
    """
    pairs = _faq_pairs(dossier, blueprint)
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
            section_id="gallery",
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
            section_id="team",
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
            section_id="pricing",
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
            section_id="portfolio",
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
    # Drop placeholder address lines so /karta never shows "Adress lämnas på
    # förfrågan" or builds a Google Maps query from a dummy address; the empty
    # fallback below stays honest for the all-placeholder case (contact-honesty
    # slice 2026-06-02).
    address_lines: list[str] = real_address_lines(contact)
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
            section_id="map",
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


# ---------------------------------------------------------------------------
# Path B step 7 — restaurant-hospitality section renderers.
#
# Each helper renders a single section from the restaurant scaffold's
# sections.json. They are deliberately self-contained ``<section>``
# blocks so render_route_generic can compose them in any order (for
# example: hero + menu-preview + book-table-cta on home, then
# menu-intro + menu-list + dietary-key on /menu). All customer text is
# routed through ``_jsx_safe_string`` so JSX-special characters in
# operator-supplied copy never break ``next build``.
#
# Optional sections (large-party-note, cancellation-policy) return an
# empty string when the dossier has no content for them so a scaffold
# can list them in optionalSections without forcing every site to
# render an empty card.
# ---------------------------------------------------------------------------


def render_section_menu_intro(dossier: dict) -> str:
    """Header section for the restaurant /meny route.

    Eyebrow + heading + lead paragraph using the wizard idiom so the
    section visually matches the existing about/services pages.
    Customer text from the dossier is not interpolated here yet — the
    copy is deterministic and operator-safe per the restaurant
    scaffold contract.
    """
    eyebrow = _jsx_safe_string("Meny")
    heading = _jsx_safe_string("Vad vi serverar just nu")
    intro = _jsx_safe_string(
        "Menyn växlar med säsongen och tillgången på råvaror. "
        "Be gärna personalen om dagens rekommendation eller hör av dig "
        "i förväg om du har önskemål eller allergier."
    )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_menu_list(dossier: dict) -> str:
    """Card grid of menu items for the restaurant /meny route.

    Reads ``services`` from the dossier via ``_menu_items`` (project
    input schema reuses the services array for menu items). Each card
    shows the item label and an optional summary. Empty dossiers fall
    back to a "Dagens rätt" placeholder via ``_menu_items`` so the
    page never renders an empty grid.
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
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_dietary_key(dossier: dict) -> str:
    """Optional dietary-marker key for the /meny route.

    Renders a small panel listing common Swedish dietary markers
    (vegetariskt, veganskt, glutenfritt, laktosfritt) so visitors can
    scan the menu legend at a glance. Empty when no menu item refers
    to a marker; the dispatcher includes the section because the
    restaurant scaffold's sections.json marks it as required, but the
    panel itself stays minimal so it does not dominate the page.
    """
    markers: list[tuple[str, str]] = [
        ("V", "Vegetariskt"),
        ("VG", "Veganskt"),
        ("GF", "Glutenfritt"),
        ("LF", "Laktosfritt"),
    ]
    rows = "\n".join(
        '            <li className="inline-flex items-center gap-2 rounded-full '
        'border border-[color:var(--border)] px-3 py-1 text-xs '
        'text-[color:var(--muted)]">'
        f'<span className="font-semibold text-[color:var(--foreground)]">{_jsx_safe_string(short)}</span>'
        f'<span>{_jsx_safe_string(label)}</span>'
        "</li>"
        for short, label in markers
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Kostmarkeringar</p>\n'
        '          <ul className="flex flex-wrap gap-2">\n'
        f"{rows}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_booking_intro(dossier: dict) -> str:
    """Header section for the restaurant /bokning route.

    Mirrors render_section_menu_intro's structure with reservation-
    flavoured copy. Per Issue #90 we do NOT embed a third-party
    booking provider — the operator's preferred provider lands via the
    ``booking-cta`` dossier in a separate compositional pass — so this
    intro frames the contact-driven booking flow.
    """
    eyebrow = _jsx_safe_string("Boka bord")
    heading = _jsx_safe_string("Boka en plats hos oss")
    intro = _jsx_safe_string(
        "Just nu tar vi bokningar via telefon och e-post. Ring eller "
        "skriv så bekräftar vi tid och antal personer. För större "
        "sällskap, hör av dig minst två dagar i förväg."
    )
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/20">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3">\n'
        f'            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">{eyebrow}</p>\n'
        f'            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">{heading}</h1>\n'
        f'            <p className="max-w-2xl text-lg text-[color:var(--muted)] leading-relaxed">{intro}</p>\n'
        "          </header>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_booking_form_or_embed(dossier: dict) -> str:
    """Booking-form placeholder card for the /bokning route.

    The MVP intentionally has no embedded reservation widget so the
    section renders a copy block explaining that the operator handles
    bookings via phone or email. A future scaffold variant can swap
    this renderer for a Resoo / Tablefy / Quandoo embed without
    touching the dispatcher.
    """
    body = _jsx_safe_string(
        "Vi tar bokningar manuellt så att vi kan stämma av specialönskemål, "
        "allergier och större sällskap. Använd kontaktuppgifterna nedan "
        "eller hör av dig på sociala medier."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-[var(--section-spacing)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Bokningsförfrågan</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_hours_summary(dossier: dict) -> str:
    """Opening-hours summary card for /bokning and /hitta-hit.

    Reads ``contact.openingHours`` from the dossier and renders a
    single card. Returns an empty string when no hours are set so the
    section is invisible rather than rendering an empty placeholder.
    """
    contact = dossier.get("contact") or {}
    # Suppress the dummy "Mån-Fre 09:00-17:00" fallback so the card never
    # presents placeholder hours as if they were the real schedule.
    opening = real_opening_hours(contact)
    if opening is None:
        return ""
    safe_hours = _jsx_safe_string(opening.strip())
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-8">\n'
        '          <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Öppettider</p>\n'
        f'            <p className="mt-2 text-base">{safe_hours}</p>\n'
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_fallback_phone(dossier: dict) -> str:
    """Phone + email fallback cards for /bokning.

    Reads ``contact.phone`` and ``contact.email``. Renders cards only
    for the channels the operator actually staffs so the visitor does
    not see "Boka via e-post" links pointing nowhere. Returns empty
    when neither channel is configured.
    """
    contact = dossier.get("contact") or {}
    # Only surface channels the operator actually staffs — placeholder
    # phone/email are suppressed so /bokning never shows a dummy number
    # or address as a bookable channel.
    phone = real_phone(contact)
    email = real_email(contact)
    cards: list[str] = []
    if isinstance(phone, str) and phone.strip():
        cards.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via telefon</p>\n'
            f'              <a href={_jsx_safe_string("tel:" + _phone_href(phone))} '
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(phone)}</a>\n'
            "            </div>"
        )
    if isinstance(email, str) and email.strip():
        cards.append(
            '            <div className="rounded-xl border border-[color:var(--border)] p-6">\n'
            '              <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Boka via e-post</p>\n'
            f'              <a href={_jsx_safe_string("mailto:" + email.strip())} '
            f'className="mt-2 inline-flex items-center gap-2 text-base hover:underline">{_jsx_safe_string(email.strip())}</a>\n'
            "            </div>"
        )
    if not cards:
        return ""
    grid = "\n".join(cards)
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-4 py-8">\n'
        '          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{grid}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
    )


def render_section_large_party_note(dossier: dict) -> str:
    """Optional 'larger party' guidance for /bokning.

    Static text encouraging visitors with bigger groups to call ahead.
    The MVP keeps the copy generic; a future scaffold variant can
    wire this to a per-restaurant max-party-size from the dossier.
    """
    body = _jsx_safe_string(
        "För sällskap över sex personer ber vi dig kontakta oss direkt så "
        "vi kan reservera plats och förbereda menyn. Boka helst minst "
        "två dagar i förväg."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Större sällskap</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def render_section_cancellation_policy(dossier: dict) -> str:
    """Optional cancellation-policy block for /bokning.

    Static placeholder text matching the MVP's manual-booking flow.
    A scaffold variant or operator override can replace this with the
    operator's actual policy via a future dossier field.
    """
    body = _jsx_safe_string(
        "Behöver du avboka eller ändra antalet personer? Hör av dig så "
        "snart du kan, så hjälper vi nästa gäst som står på väntelistan."
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-3 py-8">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Avbokning</p>\n'
        f'          <p className="max-w-2xl text-base text-[color:var(--foreground)] leading-relaxed">{body}</p>\n'
        "        </div>\n"
        "      </section>\n"
    )


def _restaurant_optional_section_stub(dossier: dict) -> str:
    """No-op renderer for optional restaurant sections without bespoke copy.

    Returned by ``render_section_wine_pairings``,
    ``render_section_lunch_rotation_note`` and
    ``render_section_menu_download_cta`` so a future operator-driven
    fix can add real copy by simply replacing the renderer with a
    section-shaped function. Until then these slots stay empty so
    the page does not render placeholder marketing copy that the
    operator did not approve.
    """
    return ""


def render_section_wine_pairings(dossier: dict) -> str:
    """Optional wine-pairing recommendations panel for /meny.

    Empty MVP stub: a future scaffold variant or operator override
    will populate this section with a curated list pulled from a
    new dossier field. Returning empty keeps the page slim until
    real content is wired.
    """
    return _restaurant_optional_section_stub(dossier)


def render_section_lunch_rotation_note(dossier: dict) -> str:
    """Optional lunch-rotation note for /meny.

    Empty MVP stub: weekday lunch rotations require a structured
    schedule the project-input schema does not yet model. The
    section is still registered so a scaffold listing it in
    optionalSections does not raise SystemExit at build time.
    """
    return _restaurant_optional_section_stub(dossier)


def render_section_menu_download_cta(dossier: dict) -> str:
    """Optional menu-PDF download CTA for /meny.

    Empty MVP stub: file uploads are routed through
    ``public/uploads`` only for hero/gallery/logo today. A future
    scaffold can wire a menu PDF upload through the same path and
    swap this stub for a real download button.
    """
    return _restaurant_optional_section_stub(dossier)


# Restaurant section renderers register here so render_route_generic
# can dispatch on the section ids declared in
# packages/generation/orchestration/scaffolds/restaurant-hospitality/sections.json.
# Optional sections without bespoke copy register a no-op stub so the
# dispatcher can include them without raising SystemExit; operators or
# scaffold variants can replace each stub with a real renderer when
# the corresponding dossier fields land.
_SECTION_RENDERERS.update(
    {
        "menu-intro": render_section_menu_intro,
        "menu-list": render_section_menu_list,
        "dietary-key": render_section_dietary_key,
        "wine-pairings": render_section_wine_pairings,
        "lunch-rotation-note": render_section_lunch_rotation_note,
        "menu-download-cta": render_section_menu_download_cta,
        "booking-intro": render_section_booking_intro,
        "booking-form-or-embed": render_section_booking_form_or_embed,
        "hours-summary": render_section_hours_summary,
        "fallback-phone": render_section_fallback_phone,
        "large-party-note": render_section_large_party_note,
        "cancellation-policy": render_section_cancellation_policy,
    }
)


# ---------------------------------------------------------------------------
# Path B step 9 — LSB home-page alias renderers.
#
# render_home today emits four extra sections beyond the four declared
# in local-service-business/sections.json: story, gallery, testimonials
# and faq. The implementations live in private ``_render_home_*``
# helpers because they were extracted before the section dispatcher
# existed. To complete Path B for LSB we expose them under stable
# ``render_section_*`` names and register them in the dispatcher so a
# scaffold's sections.json can reference them by id. The aliases are
# 1-1 wrappers — output stays byte-identical with the inline calls in
# render_home.
#
# render_section_faq accepts a ``dossier_routes`` kwarg so the
# dispatcher can pass the same list render_home computes today; when
# the list contains "/faq" the section appends a "Se alla frågor"-CTA
# pointing at the dedicated /faq route, otherwise the CTA is dropped
# so the section never emits a ghost link.
# ---------------------------------------------------------------------------


def render_section_story(dossier: dict) -> str:
    """LSB home-page story section.

    Thin alias for ``_render_home_story_section``. Returns "" when
    the dossier has no ``company.story`` content so a scaffold can
    list ``story`` in optionalSections without forcing an empty
    section onto every site.
    """
    return _render_home_story_section(dossier)


def render_section_gallery(dossier: dict) -> str:
    """LSB home-page gallery section.

    Thin alias for ``_render_home_gallery_section``. Renders up to
    ``_HOME_GALLERY_MAX_ITEMS`` operator-uploaded gallery images;
    returns "" when no gallery is set or the story section already
    consumed the only available image.
    """
    return _render_home_gallery_section(dossier)


def render_section_testimonials(dossier: dict) -> str:
    """LSB home-page testimonials section.

    Thin alias for ``_render_home_testimonials_section``. Renders
    real cards when ``trustSignals`` has at least
    ``_HOME_TESTIMONIAL_MIN_ITEMS`` entries, otherwise returns "" so
    the classic ``trust-proof`` bullet section stays as fallback.
    Cross-section coordination (suppressing trust-proof when
    testimonials are visible) is the caller's responsibility.
    """
    return _render_home_testimonials_section(dossier)


def render_section_faq(
    dossier: dict,
    *,
    dossier_routes: list[str] | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """LSB home-page FAQ section.

    Thin alias for ``_render_home_faq_section`` that derives the
    ``has_faq_route`` flag from ``dossier_routes`` so the dispatcher
    can pass the same list ``render_home`` already computes. When
    /faq is in the route list the section ends with a "Se alla
    frågor"-CTA pointing at the dedicated route, otherwise the CTA
    is omitted to avoid a ghost link. kor-2: forwards the blueprint so
    a grounded FAQ replaces the generic template questions.
    """
    has_faq_route = "/faq" in (dossier_routes or [])
    return _render_home_faq_section(
        dossier, has_faq_route=has_faq_route, blueprint=blueprint
    )


def render_section_service_area(dossier: dict) -> str:
    """LSB optional service-area section — MVP stub.

    LSB's sections.json lists ``service-area`` as an optional home
    section so a future renderer can surface a "vi täcker dessa
    områden"-block without a structural change. The MVP stub returns
    "" so the page stays slim until that renderer lands; the
    location-aware copy already lives on /om-oss via render_about's
    inline location-section.
    """
    return ""


def render_section_reviews(dossier: dict) -> str:
    """LSB optional reviews section — MVP stub.

    Reserved slot for an external-review widget (Google reviews,
    Reco, etc.) once the operator-side integration lands. Returns
    "" so the dispatcher can include the section without forcing
    every site to render an empty placeholder.
    """
    return ""


def render_section_certifications(dossier: dict) -> str:
    """LSB optional certifications section — MVP stub.

    Reserved slot for a row of certification logos / badges once
    the project-input schema models them. Today the dossier carries
    free-form trust signals only, which the trust-proof section
    already surfaces. Returns "" until structured certifications
    are wired.
    """
    return ""


_SECTION_RENDERERS.update(
    {
        "story": render_section_story,
        "gallery": render_section_gallery,
        "testimonials": render_section_testimonials,
        "faq": render_section_faq,
        "service-area": render_section_service_area,
        "reviews": render_section_reviews,
        "certifications": render_section_certifications,
    }
)


_LSB_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "local-service-business"
)


_RESTAURANT_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "restaurant-hospitality"
)


def _render_restaurant_route(
    dossier: dict,
    *,
    route_id: str,
    page_function_name: str,
    contact_path: str,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Compose a restaurant route via the section dispatcher.

    Loads ``restaurant-hospitality/sections.json`` for the section
    list, dispatches each id through ``render_route_generic``, then
    appends the standard contact-CTA section so the visitor always
    has a path back to opening hours and phone. The page shell
    (icon import + ``<main>`` wrapper + closing tags) is added
    here so the renderer remains a drop-in replacement for the
    previous specialised implementation.

    ``page_function_name`` controls the name of the exported React
    component (``MenuPage`` / ``BookingPage``) so a future scaffold
    can reuse this helper for any new route.
    """
    sections = _load_scaffold_sections(_RESTAURANT_SCAFFOLD_DIR)
    body = render_route_generic(
        dossier,
        route_id=route_id,
        scaffold_sections=sections,
        contact_path=contact_path,
        blueprint=blueprint,
    )
    # kor-2: thread the blueprint so the trailing contact CTA follows
    # conversion.primaryCta (e.g. "Boka bord") instead of the generic
    # "Kontakta oss", consistent with the rest of the default-route set.
    cta_section = annotate_section_marker(
        render_section_contact_cta(
            dossier, contact_path=contact_path, blueprint=blueprint
        ),
        "contact-cta",
    )
    return (
        'import { ArrowRight } from "lucide-react";\n'
        "\n"
        f"export default function {page_function_name}() {{\n"
        "  return (\n"
        '    <main className="flex flex-1 flex-col">\n'
        + body
        + cta_section
        + "    </main>\n"
        + "  );\n"
        + "}\n"
    )


def render_menu(
    dossier: dict,
    *,
    contact_path: str = "/hitta-hit",
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the restaurant /meny route via the section dispatcher.

    Path B step 8 thin shim. The actual section composition lives
    in ``render_section_menu_intro`` / ``render_section_menu_list``
    / ``render_section_dietary_key`` and is dispatched through
    ``render_route_generic`` based on the section list declared in
    ``restaurant-hospitality/sections.json``. A future scaffold can
    extend the route by appending an optional section (for example
    ``wine-pairings``) to its sections.json without editing this
    file.

    The trailing contact CTA is added here as a deliberate page-
    level affordance — the scaffold's sections.json keeps the
    /menu route lean (intro + list + dietary key) and the CTA is
    surfaced by the page wrapper so a hungry visitor always has a
    path back to opening hours and phone.

    ``contact_path`` defaults to ``/hitta-hit`` to match the
    scaffold's ``contact`` route slug.
    """
    return _render_restaurant_route(
        dossier,
        route_id="menu",
        page_function_name="MenuPage",
        contact_path=contact_path,
        blueprint=blueprint,
    )


def render_booking(
    dossier: dict,
    *,
    contact_path: str = "/hitta-hit",
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the restaurant /bokning route via the section dispatcher.

    Path B step 8 thin shim. The actual section composition lives
    in ``render_section_booking_intro`` /
    ``render_section_booking_form_or_embed`` /
    ``render_section_hours_summary`` /
    ``render_section_fallback_phone`` and is dispatched through
    ``render_route_generic`` based on the section list declared in
    ``restaurant-hospitality/sections.json``.

    Per Issue #90 we still do NOT embed a third-party booking
    provider — the dispatcher composes a static reservation page
    where the operator handles bookings via phone and email. A
    scaffold variant can swap
    ``render_section_booking_form_or_embed`` for an embedded
    widget without touching the dispatcher.
    """
    return _render_restaurant_route(
        dossier,
        route_id="booking",
        page_function_name="BookingPage",
        contact_path=contact_path,
        blueprint=blueprint,
    )


# ---------------------------------------------------------------------------
# Path B step 12 — clinic-healthcare runtime activation
# (and generic Path B native dispatch infrastructure for future scaffolds)
#
# Restaurant-hospitality (above) keeps render_menu / render_booking as
# specialised entry points so write_pages can call them directly while
# the home / about / contact routes flow through the LSB shims. A new
# scaffold whose routes do NOT line up with the existing if/elif arms
# (for example clinic-healthcare's ``treatments`` route) needs another
# path: the scaffold registers itself in ``_DISPATCHED_SCAFFOLDS`` and
# write_pages routes every one of its routes through the section
# dispatcher. Future scaffolds (professional-services, agency-studio,
# portfolio-creator, ...) can join the table without touching
# write_pages.
# ---------------------------------------------------------------------------


def render_section_about_story_block(dossier: dict) -> str:
    """Render about-story as a self-contained <section> block.

    The base ``render_section_about_story`` returns a fragment that
    is meant to be embedded inside ``render_about``'s page-level
    <main> wrapper (header + story-card with no surrounding
    section). Path B native scaffolds compose at the section level
    via the dispatcher, so this wrapper exposes the same content
    as a standalone block they can list in their sections.json
    under the id ``about-story-block``.
    """
    fragment = render_section_about_story(dossier)
    return (
        '      <section className="bg-[color:var(--background)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        + fragment
        + "        </div>\n"
        "      </section>\n"
    )


def render_section_team_block(dossier: dict) -> str:
    """Render the team grid as a self-contained <section> block.

    Wraps ``render_section_team`` in a standalone section so non-LSB
    scaffolds can list ``team-block`` in their sections.json. Returns
    "" when the underlying team is empty so the dispatcher never
    emits a hollow heading + empty grid.
    """
    fragment = render_section_team(dossier)
    if not fragment.strip():
        return ""
    return (
        '      <section className="bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/15">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        + fragment
        + "        </div>\n"
        "      </section>\n"
    )


def render_section_treatment_summary(
    dossier: dict,
    *,
    contact_path: str = "/kontakta-oss",
) -> str:
    """Render a compact home-page treatments preview for clinic-healthcare.

    Picks the first three services from the dossier (clinics use
    the services array as their treatment catalogue), renders each
    as a plain card with the treatment name and a short
    plain-language summary, and ends with a "Boka tid"-CTA pointing
    at the contact route. Visually calmer than the LSB
    services-summary block (no hover-lift, softer borders) so it
    sits well next to the credentials section a clinic home depends
    on for trust.

    Returns "" when the dossier carries no services so a generic
    landing page does not emit an empty grid.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    cards = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--background)] p-6">\n'
        f'              <h3 className="text-lg font-semibold">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="mt-2 text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services[:3]
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-8 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Vård vi erbjuder</p>\n'
        '            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight md:text-4xl">Våra behandlingar</h2>\n'
        "          </div>\n"
        '          <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </ul>\n"
        f'          <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Boka tid<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


_TREATMENT_LIST_TREATMENT_DEFAULT = "minimal-rows"


def render_section_treatment_list(
    dossier: dict,
    *,
    contact_path: str = "/kontakta-oss",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the full treatment list for the clinic /behandlingar route.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of three private renderers:

    * ``minimal-rows`` — the byte-identical default. Vertical list
      of rounded-2xl border-cards with a quiet typographic header.
      Mapped to ``clinic-calm`` so the calm clinic keeps the
      pre-Phase-2 menu feel.
    * ``split-cards`` — two-column grid of warmer cards where each
      treatment card carries a soft accent-tinted left rail and
      slightly bigger label typography. Mapped to ``warm-care``.
    * ``numbered-stack`` — sequence with large monospaced
      "01 / 02 / 03"-numerals and thin horizontal separators
      between rows. Reads as a clinical sequence rather than a
      menu of options. Mapped to ``modern-precision``.

    Returns "" when no services are declared so the dispatcher
    does not emit an empty list scaffold regardless of treatment.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "treatment-list",
        default=_TREATMENT_LIST_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "treatment-list"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("treatment-list")
            if blueprint is not None
            else None
        ),
    )
    if treatment == "split-cards":
        return _render_treatment_list_split_cards(services, contact_path)
    if treatment == "numbered-stack":
        return _render_treatment_list_numbered_stack(services, contact_path)
    return _render_treatment_list_minimal_rows(services, contact_path)


def _treatment_list_header() -> str:
    """Shared header markup for every treatment-list treatment.

    Kept as a single source so the eyebrow + h1 + supporting copy
    stay in lockstep across all three treatments. The Phase 3
    operator-pin tier (ADR 0032) only changes which treatment
    renderer dispatches; it does not (yet) override the header copy.
    """
    return (
        '          <header className="flex flex-col gap-3">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Behandlingar</p>\n'
        '            <h1 className="max-w-2xl text-4xl font-semibold tracking-tight md:text-5xl">Det här hjälper vi dig med</h1>\n'
        '            <p className="max-w-2xl text-base text-[color:var(--muted)] leading-relaxed">Beskrivningarna är skrivna i klarspråk. Är du osäker på vilken behandling som passar — ring eller skicka ett mejl så hjälper vi dig.</p>\n'
        "          </header>\n"
    )


def _render_treatment_list_minimal_rows(
    services: list[dict],
    contact_path: str,
) -> str:
    """Vertical list of rounded border-cards (the default treatment).

    Kept byte-identical to the pre-Phase-2 output so existing
    snapshots and any clinic build that did not pin a variant in
    Phase 1 are not invalidated by introducing treatment dispatch.
    """
    items = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--background)] p-8">\n'
        f'              <h2 className="text-xl font-semibold tracking-tight md:text-2xl">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="mt-3 text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _treatment_list_header()
        + '          <ul className="flex flex-col gap-4">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + f'          <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Boka tid<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_treatment_list_split_cards(
    services: list[dict],
    contact_path: str,
) -> str:
    """Two-column grid of warm cards with an accent-tinted left rail.

    Reads as a warmer brochure than ``minimal-rows`` — slightly
    larger label typography, a soft accent-coloured left rail
    (``border-l-4 border-[color:var(--accent)]``) and card-surface
    background instead of a flat panel. Mapped to ``warm-care``.
    """
    items = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-3 rounded-2xl border border-[color:var(--border)] border-l-4 border-l-[color:var(--accent)] bg-[color:var(--card)] p-8">\n'
        f'              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </li>"
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _treatment_list_header()
        + '          <ul className="grid gap-6 md:grid-cols-2">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + f'          <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Boka tid<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_treatment_list_numbered_stack(
    services: list[dict],
    contact_path: str,
) -> str:
    """Sequence with monospaced numerals and thin horizontal separators.

    Reads as a clinical sequence: a large mono "01 / 02 / 03"
    numeral on the left, the treatment name and description on the
    right, and a thin ``border-b`` separator between rows. No card
    chrome — the eye runs straight down the numeral column. Mapped
    to ``modern-precision``.
    """
    items = "\n".join(
        (
            f'            <li key={_jsx_safe_string(svc["id"])} className="grid gap-6 border-b border-[color:var(--border)] py-8 md:grid-cols-[6rem_1fr]">\n'
            f'              <p className="font-mono text-3xl tracking-tight text-[color:var(--muted)] md:text-4xl">{_jsx_safe_string(f"{idx:02d}")}</p>\n'
            "              <div className=\"flex flex-col gap-3\">\n"
            f'                <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'                <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            "              </div>\n"
            "            </li>"
        )
        for idx, svc in enumerate(services, start=1)
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _treatment_list_header()
        + '          <ul className="flex flex-col border-t border-[color:var(--border)]">\n'
        + f"{items}\n"
        + "          </ul>\n"
        + f'          <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Boka tid<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def render_section_credentials(dossier: dict) -> str:
    """Render a credentials / certifications row for clinic-healthcare.

    Reads ``dossier.trustSignals`` (the same array LSB uses for
    trust bullets) and renders it as a compact inline row of badge-
    cards under a "Legitimerade och certifierade"-eyebrow. This is
    what surfaces a clinic's regulated status (Sveriges Tand-
    läkarförbund, Vårdgivarregistret, etc.) on the home and
    treatments pages where a patient is deciding whether the
    practitioner is real.

    Returns "" when the dossier has no trust signals so the
    dispatcher does not emit a hollow section.
    """
    trust_raw = dossier.get("trustSignals") or []
    trust: list[str] = []
    for item in trust_raw:
        if isinstance(item, str) and item.strip():
            trust.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label")
            if isinstance(label, str) and label.strip():
                trust.append(label.strip())
    if not trust:
        return ""
    badges = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="flex items-center gap-3 rounded-full border border-[color:var(--border)] bg-[color:var(--background)] px-5 py-2 text-sm font-medium">\n'
        '              <Check className="size-4 text-[color:var(--primary)]" />\n'
        f'              <span>{_jsx_safe_string(label)}</span>\n'
        "            </li>"
        for label in trust
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.7)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Legitimerade och certifierade</p>\n'
        '          <ul className="flex flex-wrap gap-3">\n'
        f"{badges}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


_SECTION_RENDERERS.update(
    {
        "about-story-block": render_section_about_story_block,
        "team-block": render_section_team_block,
        "treatment-summary": render_section_treatment_summary,
        "treatment-list": render_section_treatment_list,
        "credentials": render_section_credentials,
    }
)


_EXPERTISE_AREAS_TREATMENT_DEFAULT = "numbered-2col"


def render_section_expertise_areas(
    dossier: dict,
    *,
    contact_path: str = "/kontakta-oss",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render a structured expertise-area grid for professional-services home.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of two private renderers:

    * ``numbered-2col`` — the byte-identical default. 2-col grid with
      numeric eyebrows (``01``..``06``) and a left-rail border on
      each card. Calm, court-filing-style restraint. Mapped to
      ``legal-classic`` and ``accounting-trust`` (default-keep).
    * ``tag-cluster`` — pill cloud where each practice area is a
      compact rounded pill with the label inside and the scope
      revealed on the row directly below. Reads as an associative
      "what we do"-cloud rather than a numbered index. Mapped to
      ``consulting-modern``.

    Returns "" when the dossier carries no services so the
    dispatcher does not emit an empty grid. Caps at six entries
    on the home; the full list belongs on the practice-grid
    section that runs the /expertis route.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "expertise-areas",
        default=_EXPERTISE_AREAS_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "expertise-areas"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("expertise-areas")
            if blueprint is not None
            else None
        ),
    )
    if treatment == "tag-cluster":
        return _render_expertise_areas_tag_cluster(services, contact_path)
    return _render_expertise_areas_numbered_2col(services, contact_path)


def _expertise_areas_header() -> str:
    """Shared header markup for every expertise-areas treatment."""
    return (
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Verksamhetsområden</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Vår expertis</h2>\n'
        "          </div>\n"
    )


def _render_expertise_areas_numbered_2col(
    services: list[dict],
    contact_path: str,
) -> str:
    """2-col grid with numbered eyebrows and left-rail borders.

    Kept byte-identical to the pre-Phase-2 output so existing
    snapshots and any PS build that did not pin a variant in Phase 1
    are not invalidated by introducing treatment dispatch.
    """
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-3 border-l border-[color:var(--border)] pl-6">\n'
        f'              <span className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"{idx:02d}")}</span>\n'
        f'              <h3 className="text-xl font-semibold tracking-tight">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        "            </article>"
        for idx, svc in enumerate(services[:6], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _expertise_areas_header()
        + '          <div className="grid gap-10 md:grid-cols-2">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + f'          <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Boka introduktionssamtal<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_expertise_areas_tag_cluster(
    services: list[dict],
    contact_path: str,
) -> str:
    """Pill cloud where practice areas read as an associative tag cluster.

    Each practice area renders as a compact rounded pill carrying
    its label; the scope follows on a separate row beneath the
    cluster as a single line of running text joined by middots.
    The shape — pills + summary line — reads as "what we do" rather
    than a numbered index, which suits the modern consulting tone.
    Mapped to ``consulting-modern``.
    """
    pills = "\n".join(
        f'              <li key={_jsx_safe_string(svc["id"])} className="rounded-full border border-[color:var(--border)] bg-[color:var(--card)] px-5 py-2 text-sm font-medium tracking-tight">{_jsx_safe_string(svc["label"])}</li>'
        for svc in services[:6]
    )
    summary_line = " · ".join(
        str(svc.get("summary", "")).strip()
        for svc in services[:6]
        if isinstance(svc.get("summary"), str) and svc.get("summary", "").strip()
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _expertise_areas_header()
        + '          <ul className="flex flex-wrap gap-3">\n'
        + f"{pills}\n"
        + "          </ul>\n"
        + f'          <p className="max-w-3xl text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(summary_line)}</p>\n'
        + f'          <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Boka introduktionssamtal<ArrowRight className="size-4" /></a>\n'
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


_PRACTICE_GRID_TREATMENT_DEFAULT = "dense-grid"


def render_section_practice_grid(
    dossier: dict,
    *,
    contact_path: str = "/kontakta-oss",
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the full practice-area catalogue for professional-services /expertis.

    Section design-treatments (Phase 2): the section now resolves a
    treatment id via ``_treatment_for_section`` and routes the same
    services array through one of three private renderers:

    * ``dense-grid`` — the byte-identical default. 3-col compact
      grid of small cards with formal restraint. Mapped to
      ``consulting-modern`` so the modern consulting variant keeps
      the pre-Phase-2 expertise menu.
    * ``tabular`` — formal row listing (no card chrome) with thin
      ``border-b`` separators between rows and a column header.
      Reads as a court-filing index. Mapped to ``legal-classic``.
    * ``grouped`` — 2-col feature columns with large numbered
      eyebrows (``Område 01`` / ``Område 02``…) and richer
      typography. Mapped to ``accounting-trust``.

    Returns "" when no services are declared so the dispatcher
    does not emit an empty grid scaffold regardless of treatment.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "practice-grid",
        default=_PRACTICE_GRID_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(dossier, "practice-grid"),
        visual_direction_pick=(
            blueprint.section_treatment_pick("practice-grid")
            if blueprint is not None
            else None
        ),
    )
    if treatment == "tabular":
        return _render_practice_grid_tabular(services, contact_path)
    if treatment == "grouped":
        return _render_practice_grid_grouped(services, contact_path)
    return _render_practice_grid_dense_grid(services, contact_path)


def _practice_grid_header() -> str:
    """Shared header markup for every practice-grid treatment.

    Locks the eyebrow + h1 + supporting copy across all three
    treatments. The Phase 3 operator-pin tier (ADR 0032) only
    swaps the treatment renderer; copy overrides via dossier
    directives are out of scope and left for a future iteration.
    """
    return (
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Verksamhetsområden</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">Praktikgrupper</h1>\n'
        '            <p className="text-base text-[color:var(--muted)] leading-relaxed">Vår verksamhet är organiserad i specialiserade praktikgrupper. Välj det område som ligger närmast ert ärende — vi kopplar in den partner som har relevant precedent.</p>\n'
        "          </header>\n"
    )


def _render_practice_grid_dense_grid(
    services: list[dict],
    contact_path: str,
) -> str:
    """3-col compact card grid (the default treatment).

    Kept byte-identical to the pre-Phase-2 output so existing
    snapshots and any PS build that did not pin a variant in Phase 1
    are not invalidated by introducing treatment dispatch.
    """
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-4 rounded-lg border border-[color:var(--border)] bg-[color:var(--background)] p-7">\n'
        f'              <h2 className="text-lg font-semibold tracking-tight">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        f'              <a href={_jsx_safe_string(contact_path)} className="mt-auto inline-flex items-center gap-2 text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline">Diskutera ärende<ArrowRight className="size-3" /></a>\n'
        "            </article>"
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _practice_grid_header()
        + '          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_practice_grid_tabular(
    services: list[dict],
    contact_path: str,
) -> str:
    """Formal row listing with thin separators (no card chrome).

    Reads as a court-filing index: a header row labels the columns,
    each practice area is a single row with a label / scope / link
    layout and a thin ``border-b`` separator. No surface chrome —
    the eye runs straight down the column. Mapped to
    ``legal-classic`` so the classic law firm reads as a structured
    filing index rather than a marketing brochure.
    """
    rows = "\n".join(
        (
            f'              <li key={_jsx_safe_string(svc["id"])} className="grid items-baseline gap-4 border-b border-[color:var(--border)] py-6 md:grid-cols-[14rem_1fr_auto] md:gap-8">\n'
            f'                <h2 className="text-base font-semibold tracking-tight md:text-lg">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'                <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            f'                <a href={_jsx_safe_string(contact_path)} className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline">Diskutera ärende<ArrowRight className="size-3" /></a>\n'
            "              </li>"
        )
        for svc in services
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _practice_grid_header()
        + '          <div className="flex flex-col">\n'
        + '            <div className="grid gap-4 border-b border-[color:var(--border)] pb-3 text-xs font-mono uppercase tracking-widest text-[color:var(--muted)] md:grid-cols-[14rem_1fr_auto] md:gap-8">\n'
        + "              <span>Praktikområde</span>\n"
        + "              <span>Omfång</span>\n"
        + '              <span className="hidden md:inline">Kontakt</span>\n'
        + "            </div>\n"
        + '            <ul className="flex flex-col">\n'
        + f"{rows}\n"
        + "            </ul>\n"
        + "          </div>\n"
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def _render_practice_grid_grouped(
    services: list[dict],
    contact_path: str,
) -> str:
    """2-col feature columns with numbered eyebrows.

    Each practice area becomes a richer feature card with a large
    monospace ``Område NN`` eyebrow, slightly bigger heading
    typography and more vertical breathing room. Mapped to
    ``accounting-trust`` so the audit / advisory variant reads as a
    structured "this is how we organise our practice" rather than a
    dense menu.
    """
    cards = "\n".join(
        (
            f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--card)] p-8">\n'
            f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--accent)]">{_jsx_safe_string(f"Område {idx:02d}")}</p>\n'
            f'              <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h2>\n'
            f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            f'              <a href={_jsx_safe_string(contact_path)} className="mt-auto inline-flex items-center gap-2 text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline">Diskutera ärende<ArrowRight className="size-3" /></a>\n'
            "            </article>"
        )
        for idx, svc in enumerate(services, start=1)
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        + _practice_grid_header()
        + '          <div className="grid gap-6 md:grid-cols-2">\n'
        + f"{cards}\n"
        + "          </div>\n"
        + "        </div>\n"
        + "      </section>\n"
        + "\n"
    )


def render_section_industries_served(dossier: dict) -> str:
    """Render an industries-served row for professional-services scaffolds.

    Reads ``location.serviceAreas`` (which for a professional-
    services firm is the natural place to declare served markets
    or industries — a multi-office advokatbyrå already uses this
    field for its office cities or covered regions, an audit firm
    might list industries served) and emits a compact pill row
    under a "Branscher och marknader vi arbetar inom" eyebrow.
    Visually identifiable as PS — uppercase eyebrow, monospace
    pill labels, no icons — and structurally separate from the
    LSB service-area block which renders the same field as a
    travel-distance trust message.

    Returns "" when the field is empty so the dispatcher does
    not emit an empty pill row.
    """
    location = dossier.get("location") or {}
    areas = location.get("serviceAreas") or []
    cleaned: list[str] = [item.strip() for item in areas if isinstance(item, str) and item.strip()]
    if not cleaned:
        return ""
    pills = "\n".join(
        f'            <li key={_jsx_safe_string(area)} className="rounded-sm border border-[color:var(--border)] bg-[color:var(--background)] px-4 py-2 text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(area)}</li>'
        for area in cleaned
    )
    return (
        '      <section className="border-t border-[color:var(--border)] bg-gradient-to-b from-[color:var(--background)] to-[color:var(--accent)]/10">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.7)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Branscher och marknader vi arbetar inom</p>\n'
        '          <ul className="flex flex-wrap gap-2">\n'
        f"{pills}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_partners_grid(dossier: dict) -> str:
    """Render a formal partners grid for professional-services scaffolds.

    Reads ``company.team`` and presents each named member as a
    formal partner card with their role on a separate eyebrow
    line — the visual convention of an advokatbyrå or
    revisionsbyrå roster. Bigger cards than the clinic
    ``team-block``, more typographic restraint than the LSB
    team renderer; the layout is designed so that bar
    admissions, audit registrations or "delägare sedan ÅÅÅÅ"
    dates read as the primary attribute.

    Returns "" when no team is declared so the dispatcher does
    not emit a hollow grid.
    """
    company = dossier.get("company") or {}
    team = company.get("team") or []
    members: list[dict] = [m for m in team if isinstance(m, dict) and m.get("name") and m.get("role")]
    if not members:
        return ""
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(member["name"])} className="flex flex-col gap-2 border-t border-[color:var(--border)] pt-6">\n'
        f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(member["role"])}</p>\n'
        f'              <h3 className="text-2xl font-semibold tracking-tight">{_jsx_safe_string(member["name"])}</h3>\n'
        "            </article>"
        for member in members
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Partners och rådgivare</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Vårt team</h2>\n'
        "          </header>\n"
        '          <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{cards}\n"
        "          </div>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_insights_list(dossier: dict) -> str:  # noqa: ARG001 — dossier reserved for future insights schema
    """Render an insights / publications row for professional-services.

    The current project-input schema does not carry a structured
    ``insights`` collection, so this renderer is intentionally a
    no-op — it returns ``""`` until a future schema extension lets
    a dossier declare publications. Registering it now means PS
    sections.json can list ``insights-list`` as an optional
    section without crashing the dispatcher; once the schema
    grows the renderer can be filled in without touching the
    contract.
    """
    return ""


_SECTION_RENDERERS.update(
    {
        "expertise-areas": render_section_expertise_areas,
        "practice-grid": render_section_practice_grid,
        "industries-served": render_section_industries_served,
        "partners-grid": render_section_partners_grid,
        "insights-list": render_section_insights_list,
    }
)


_SELECTED_WORK_PREVIEW_TREATMENT_DEFAULT = "editorial-stack"


def render_section_selected_work_preview(
    dossier: dict,
    *,
    contact_path: str = "/kontakta-oss",  # noqa: ARG001 — included for kwarg-call symmetry; preview uses /arbeten as the explicit follow link
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Render the home-page Selected Work preview for agency-studio.

    Section design-treatments (Phase 1 pilot + Phase 2 expansion):
    the section resolves a treatment id via
    ``_treatment_for_section`` and routes the same dossier data
    through one of three private renderers:

    * ``editorial-stack`` — the byte-identical default that preserves
      pre-pilot snapshots. Vertical 2-col grid, every card sits on
      the same baseline with a thin top border and a "Case 01"
      eyebrow.
    * ``asymmetric-grid`` — offset 2-col grid where every other card
      is vertically translated by ``md:translate-y-12`` and rendered
      as an enclosed surface card with a "Studio nº 01" eyebrow.
      Same services, deliberately broken rhythm.
    * ``marquee-row`` — horizontal scroll-snap rail with six tight
      cards, "Studio reel"-eyebrow and a gradient fade hint on the
      right edge. No auto-animation in Phase 2; reduced-motion users
      get the same browseable rail. Mapped to ``bold-electric``.

    The variant-to-treatment mapping lives in
    ``_SECTION_TREATMENTS_BY_VARIANT`` so the section renderer itself
    does not have to know about variants — only about treatments.

    Returns "" when no work is declared so the dispatcher does not
    emit an empty grid regardless of treatment.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    treatment = _treatment_for_section(
        variant_id,
        "selected-work-preview",
        default=_SELECTED_WORK_PREVIEW_TREATMENT_DEFAULT,
        operator_pin=_operator_pin_for_section(
            dossier, "selected-work-preview"
        ),
        visual_direction_pick=(
            blueprint.section_treatment_pick("selected-work-preview")
            if blueprint is not None
            else None
        ),
    )
    if treatment == "asymmetric-grid":
        return _render_selected_work_preview_asymmetric_grid(services)
    if treatment == "marquee-row":
        return _render_selected_work_preview_marquee_row(services)
    return _render_selected_work_preview_editorial_stack(services)


def _render_selected_work_preview_editorial_stack(services: list[dict]) -> str:
    """Vertical 2-col grid where every card sits on a shared baseline.

    The default treatment for ``selected-work-preview``. Kept
    byte-identical to the pre-pilot output of the section renderer
    so existing snapshots (editorial-warm, bold-electric) are not
    invalidated by the introduction of treatment dispatch.
    """
    cards = "\n".join(
        f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-4 border-t border-[color:var(--border)] pt-8">\n'
        f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Case {idx:02d}")}</p>\n'
        f'              <h3 className="text-2xl font-semibold tracking-tight md:text-3xl">{_jsx_safe_string(svc["label"])}</h3>\n'
        f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
        '              <a href={"/arbeten"} className="mt-2 inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se case<ArrowRight className="size-4" /></a>\n'
        "            </article>"
        for idx, svc in enumerate(services[:4], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-12 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Selected work</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Senaste arbeten</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-12 md:grid-cols-2">\n'
        f"{cards}\n"
        "          </div>\n"
        '          <a href={"/arbeten"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Hela arbets-arkivet<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_selected_work_preview_asymmetric_grid(services: list[dict]) -> str:
    """Offset 2-col grid where every other card is vertically translated.

    Visually breaks the editorial baseline by pushing every odd-
    indexed card down with ``md:translate-y-12`` and rendering each
    card as a self-contained surface (``bg-[color:var(--card)]`` +
    ``rounded-[var(--radius-lg)]`` + generous padding) instead of
    the flat top-border card used in ``editorial-stack``. The
    eyebrow is reframed as "Studio nº NN" so the visual identity
    reads as a curated studio index rather than a project log.

    Same data as ``editorial-stack``; only the spatial rhythm and
    surface treatment differ.
    """
    cards = "\n".join(
        (
            f'            <article key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[color:var(--border)] bg-[color:var(--card)] p-8 md:p-10'
            + (' md:translate-y-12' if idx % 2 == 0 else '')
            + '">\n'
            f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Studio nº {idx:02d}")}</p>\n'
            f'              <h3 className="text-2xl font-semibold tracking-tight md:text-4xl">{_jsx_safe_string(svc["label"])}</h3>\n'
            f'              <p className="text-base text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(svc["summary"])}</p>\n'
            '              <a href={"/arbeten"} className="mt-auto inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se case<ArrowRight className="size-4" /></a>\n'
            "            </article>"
        )
        for idx, svc in enumerate(services[:4], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-16 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Selected work</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Senaste arbeten</h2>\n'
        "          </div>\n"
        '          <div className="grid gap-x-10 gap-y-12 md:grid-cols-2 md:gap-x-16 md:pb-16">\n'
        f"{cards}\n"
        "          </div>\n"
        '          <a href={"/arbeten"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Hela arbets-arkivet<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def _render_selected_work_preview_marquee_row(services: list[dict]) -> str:
    """Horizontal scroll-snap rail with up to six tight cards.

    Reads as a "studio reel" — six cards (vs four in editorial-stack
    and asymmetric-grid) packed into a horizontal scroll container
    with ``snap-x snap-mandatory`` so each card snaps into view.
    Cards have a fixed minimum width so they do not collapse on
    narrow viewports, and the right edge has a gradient mask
    suggesting "more to scroll". The eyebrow becomes "Studio reel"
    to telegraph the motion-led identity bold-electric leans into.

    Phase 2 deliberately does NOT auto-animate the rail. Reduced-
    motion users get the same browseable scroll-snap experience as
    everyone else; only the user's own scroll input drives the row.
    Phase 3 may add a ``prefers-reduced-motion: no-preference``-
    gated CSS animation if operator feedback wants it.
    """
    cards = "\n".join(
        (
            f'              <article key={_jsx_safe_string(svc["id"])} className="flex w-[18rem] shrink-0 snap-start flex-col gap-3 rounded-[var(--radius-lg)] border border-[color:var(--border)] bg-[color:var(--card)] p-6 md:w-[22rem] md:p-8">\n'
            f'                <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Studio reel · {idx:02d}")}</p>\n'
            f'                <h3 className="text-xl font-semibold tracking-tight md:text-2xl">{_jsx_safe_string(svc["label"])}</h3>\n'
            f'                <p className="text-sm text-[color:var(--muted)] leading-relaxed line-clamp-4">{_jsx_safe_string(svc["summary"])}</p>\n'
            '                <a href={"/arbeten"} className="mt-auto inline-flex items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Se case<ArrowRight className="size-4" /></a>\n'
            "              </article>"
        )
        for idx, svc in enumerate(services[:6], start=1)
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-12 py-[var(--section-spacing)]">\n'
        '          <div className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Studio reel</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">Senaste arbeten</h2>\n'
        "          </div>\n"
        '          <div className="relative -mr-[max(0px,calc((100vw-var(--container-width))/2))]">\n'
        '            <div className="flex snap-x snap-mandatory gap-6 overflow-x-auto pb-6 pr-[max(2rem,calc((100vw-var(--container-width))/2))] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">\n'
        f"{cards}\n"
        "            </div>\n"
        '            <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-[color:var(--background)] to-transparent" />\n'
        "          </div>\n"
        '          <a href={"/arbeten"} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Hela arbets-arkivet<ArrowRight className="size-4" /></a>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_selected_work_grid(
    dossier: dict,
    *,
    contact_path: str = "/kontakta-oss",
) -> str:
    """Render the full Selected Work catalogue for agency-studio /arbeten.

    Iterates the entire ``dossier.services`` array as case studies
    and emits a single-column editorial layout — large project
    label, generous reading width on the summary, and a quiet
    "Diskutera projekt"-link at the bottom of each entry pointing
    at the contact route. Distinct from the LSB ``service-list``
    (vertical, icon-led, USP bullets), the clinic ``treatment-list``
    (clinical menu) and the PS ``practice-grid`` (3-col counsel
    cards) — agency work pages read as a magazine spread, not a
    services catalogue.

    Returns "" when no work is declared so the dispatcher does
    not emit an empty list scaffold.
    """
    services = dossier.get("services") or []
    if not services:
        return ""
    items = "\n".join(
        f'            <li key={_jsx_safe_string(svc["id"])} className="flex flex-col gap-5 border-t border-[color:var(--border)] py-12 first:border-t-0 first:pt-0 last:pb-0">\n'
        f'              <p className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(f"Case {idx:02d}")}</p>\n'
        f'              <h2 className="max-w-3xl text-3xl font-semibold tracking-tight md:text-5xl">{_jsx_safe_string(svc["label"])}</h2>\n'
        f'              <p className="max-w-3xl text-base text-[color:var(--muted)] leading-relaxed md:text-lg">{_jsx_safe_string(svc["summary"])}</p>\n'
        f'              <a href={_jsx_safe_string(contact_path)} className="inline-flex w-fit items-center gap-2 text-sm font-medium underline-offset-4 hover:underline">Diskutera projekt<ArrowRight className="size-4" /></a>\n'
        "            </li>"
        for idx, svc in enumerate(services, start=1)
    )
    return (
        '      <section className="border-b border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-12 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Arkivet</p>\n'
        '            <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">Selected work</h1>\n'
        "          </header>\n"
        '          <ul className="flex flex-col">\n'
        f"{items}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_capabilities_row(dossier: dict) -> str:
    """Render a horizontal capabilities row for agency-studio.

    Reads ``dossier.tone.secondary`` (the studio's secondary tone
    descriptors are the most natural place to lift discipline
    keywords like 'Brand identity', 'Motion', 'Web' until the
    project-input schema grows a structured capabilities array)
    and renders them as a single horizontal row of monospace
    pills under a "What we make"-eyebrow. Distinct from the LSB
    services-summary block (cards) and the PS industries-served
    block (uppercase pills under a different framing) — agency
    capabilities read as a one-liner taxonomy, not a card grid.

    Returns "" when no tone descriptors are declared so the
    dispatcher does not emit a hollow row.
    """
    tone = dossier.get("tone") or {}
    secondary = tone.get("secondary") or []
    cleaned: list[str] = [item.strip() for item in secondary if isinstance(item, str) and item.strip()]
    if not cleaned:
        return ""
    pills = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="text-sm font-mono uppercase tracking-widest">{_jsx_safe_string(label)}</li>'
        for label in cleaned
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.6)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">What we make</p>\n'
        '          <ul className="flex flex-wrap gap-x-10 gap-y-3">\n'
        f"{pills}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_manifesto_block(dossier: dict) -> str:
    """Render a manifesto statement for agency-studio.

    Lifts ``dossier.company.tagline`` and reads it as the studio's
    point of view, presented as a single full-width oversized
    typographic statement. No icons, no decoration — the section
    is the studio's voice. Distinct from the LSB hero (CTA-led)
    and the PS about story (multi-paragraph) — a manifesto is
    one sentence done loud.

    Returns "" when the dossier carries no tagline so the
    dispatcher does not emit a hollow section.
    """
    company = dossier.get("company") or {}
    tagline = company.get("tagline")
    if not isinstance(tagline, str) or not tagline.strip():
        return ""
    return (
        '      <section className="border-t border-[color:var(--border)] bg-[color:var(--background)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*1.2)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Manifest</p>\n'
        f'          <p className="max-w-4xl text-3xl font-semibold leading-tight tracking-tight md:text-5xl lg:text-6xl">{_jsx_safe_string(tagline.strip())}</p>\n'
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_process_steps(dossier: dict) -> str:  # noqa: ARG001 — dossier reserved for studio-supplied process descriptions
    """Render a four-step studio-process block for agency-studio.

    Renders a fixed four-step process (Discovery → Concept →
    Production → Launch) as a numbered horizontal flow. Each step
    has a Roman-style numeric label, a step name and a short
    descriptor pulled from the studio's voice manual rather than
    the dossier — the names are the actual stages a producer
    would recognise from any well-run studio engagement, so the
    section can render even when the dossier carries no
    structured process data.

    Once project-input.schema.json grows a structured
    ``process[]`` array the renderer can be extended to read it;
    until then the fixed step names are a deliberate, non-mock
    studio convention.
    """
    steps = (
        ("01", "Discovery", "Vi lyssnar, läser och kartlägger så att vi vet vad arbetet faktiskt ska göra."),
        ("02", "Concept", "Skriver, skissar och visar riktning. Vi visar val, inte färdiga lösningar."),
        ("03", "Production", "Designar, kodar, animerar — det praktiska arbetet där studion bygger sakerna."),
        ("04", "Launch", "Vi sjösätter med er och stannar kvar för att se hur arbetet beter sig i världen."),
    )
    cells = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="flex flex-col gap-3 border-l border-[color:var(--border)] pl-6">\n'
        f'              <span className="text-xs font-mono uppercase tracking-widest text-[color:var(--muted)]">{_jsx_safe_string(idx)}</span>\n'
        f'              <h3 className="text-xl font-semibold tracking-tight">{_jsx_safe_string(label)}</h3>\n'
        f'              <p className="text-sm text-[color:var(--muted)] leading-relaxed">{_jsx_safe_string(blurb)}</p>\n'
        "            </li>"
        for idx, label, blurb in steps
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-10 py-[var(--section-spacing)]">\n'
        '          <header className="flex flex-col gap-3 max-w-2xl">\n'
        '            <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Process</p>\n'
        '            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Så jobbar vi</h2>\n'
        "          </header>\n"
        '          <ol className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">\n'
        f"{cells}\n"
        "          </ol>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


def render_section_client_roster(dossier: dict) -> str:
    """Render a text-only client roster for agency-studio.

    Reads ``dossier.trustSignals`` (the same field LSB uses for
    trust bullets) and renders each entry as a discreet pill —
    no logos, just names — under a "Selected clients"-eyebrow.
    Studios usually decline to publish actual logos for
    procurement reasons; a text roster captures the recognition
    signal without the image-rights complication. Visually
    distinct from the clinic credentials block (badges) and the
    PS credentials block (registrations) — agency rosters read as
    a casually arranged list, not a regulated certification panel.

    Returns "" when no entries are declared so the dispatcher
    does not emit a hollow section.
    """
    trust_raw = dossier.get("trustSignals") or []
    entries: list[str] = []
    for item in trust_raw:
        if isinstance(item, str) and item.strip():
            entries.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label")
            if isinstance(label, str) and label.strip():
                entries.append(label.strip())
    if not entries:
        return ""
    pills = "\n".join(
        f'            <li key={_jsx_safe_string(label)} className="text-sm text-[color:var(--muted)]">{_jsx_safe_string(label)}</li>'
        for label in entries
    )
    return (
        '      <section className="border-t border-[color:var(--border)]">\n'
        '        <div className="mx-auto flex w-[var(--container-width)] flex-col gap-6 py-[calc(var(--section-spacing)*0.7)]">\n'
        '          <p className="text-xs uppercase tracking-widest text-[color:var(--muted)]">Selected clients</p>\n'
        '          <ul className="grid gap-x-10 gap-y-2 md:grid-cols-2 lg:grid-cols-3">\n'
        f"{pills}\n"
        "          </ul>\n"
        "        </div>\n"
        "      </section>\n"
        "\n"
    )


_SECTION_RENDERERS.update(
    {
        "selected-work-preview": render_section_selected_work_preview,
        "selected-work-grid": render_section_selected_work_grid,
        "capabilities-row": render_section_capabilities_row,
        "manifesto-block": render_section_manifesto_block,
        "process-steps": render_section_process_steps,
        "client-roster": render_section_client_roster,
    }
)


_CLINIC_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "clinic-healthcare"
)

_PROFESSIONAL_SERVICES_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "professional-services"
)

_AGENCY_STUDIO_SCAFFOLD_DIR = (
    REPO_ROOT
    / "packages"
    / "generation"
    / "orchestration"
    / "scaffolds"
    / "agency-studio"
)


_DISPATCHED_SCAFFOLDS: dict[str, Path] = {
    "clinic-healthcare": _CLINIC_SCAFFOLD_DIR,
    "professional-services": _PROFESSIONAL_SERVICES_SCAFFOLD_DIR,
    "agency-studio": _AGENCY_STUDIO_SCAFFOLD_DIR,
}


_DISPATCHED_PAGE_FUNCTION_NAMES: dict[str, str] = {
    "home": "HomePage",
    "about": "AboutPage",
    "contact": "ContactPage",
    "treatments": "TreatmentsPage",
    "team": "TeamPage",
    "faq": "FaqPage",
    "pricing": "PricingPage",
    "expertise": "ExpertisePage",
    "industries": "IndustriesPage",
    "insights": "InsightsPage",
    "work": "WorkPage",
    "process": "ProcessPage",
    "journal": "JournalPage",
}


def _dispatched_page_function_name(route_id: str) -> str:
    """Return the React component name for a Path B native route.

    Uses ``_DISPATCHED_PAGE_FUNCTION_NAMES`` when an explicit name
    is registered, otherwise derives a CamelCase-then-Page name
    from the route id. A scaffold can introduce a new route id
    without first updating the table; the derived name keeps the
    builder green while a more semantic mapping is added.
    """
    explicit = _DISPATCHED_PAGE_FUNCTION_NAMES.get(route_id)
    if explicit is not None:
        return explicit
    parts = [piece for piece in route_id.split("-") if piece]
    return "".join(piece.capitalize() for piece in parts) + "Page"


_DISPATCHED_ICON_PATTERN = re.compile(r"<([A-Z][a-zA-Z0-9]*)\s")


def _collect_dispatched_icons(body: str) -> list[str]:
    """Extract lucide-react icon names from a dispatched route body.

    Path B native page bodies are concatenated section fragments;
    each fragment may reference a different subset of lucide icons
    (Check on credentials, ArrowRight on the treatments CTA,
    Sparkles + Quote on the hero, ...). Rather than pre-declaring
    every icon a section might emit, we scan the assembled body
    for ``<PascalCase ...`` patterns and collect the names — our
    JSX uses PascalCase exclusively for lucide icons in section
    bodies, never for custom React components, so the regex is a
    safe proxy.

    Returns a sorted unique list. Always includes ``ArrowRight``
    so the page-shell's trailing contact CTA stays compilable
    even if a route happens not to emit any icon-bearing section.
    """
    matches = set(_DISPATCHED_ICON_PATTERN.findall(body))
    matches.add("ArrowRight")
    return sorted(matches)


def _render_dispatched_route(
    *,
    scaffold_id: str,
    route_id: str,
    dossier: dict,
    dossier_routes: list[str] | None = None,
    listing_route: dict | None = None,
    contact_path: str,
    variant_id: str | None = None,
    blueprint: RenderBlueprint | None = None,
) -> str:
    """Compose a route end-to-end via the section dispatcher.

    Path B native scaffolds (those listed in
    ``_DISPATCHED_SCAFFOLDS``) use this helper for every route in
    their routes.json instead of bespoke ``render_home`` /
    ``render_services`` shims. The helper:

    * loads the scaffold's sections.json,
    * dispatches each section id through ``render_route_generic``,
    * collects the lucide icons referenced in the resulting JSX,
    * wraps the body in the standard page shell.

    Future scaffolds register themselves in
    ``_DISPATCHED_SCAFFOLDS`` and immediately get a complete
    builder route — no new ``elif`` branch in ``write_pages`` is
    required as long as every section id used in the scaffold's
    sections.json is registered in ``_SECTION_RENDERERS``.
    """
    scaffold_dir = _DISPATCHED_SCAFFOLDS[scaffold_id]
    sections = _load_scaffold_sections(scaffold_dir)
    page_function_name = _dispatched_page_function_name(route_id)
    body = render_route_generic(
        dossier,
        route_id=route_id,
        scaffold_sections=sections,
        contact_path=contact_path,
        dossier_routes=dossier_routes,
        listing_route=listing_route,
        variant_id=variant_id,
        blueprint=blueprint,
    )
    icons = _collect_dispatched_icons(body)
    icon_import = "import { " + ", ".join(icons) + ' } from "lucide-react";\n'
    return (
        icon_import
        + "\n"
        + f"export default function {page_function_name}() {{\n"
        + "  return (\n"
        + '    <main className="flex flex-1 flex-col">\n'
        + body
        + "    </main>\n"
        + "  );\n"
        + "}\n"
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
    blueprint: RenderBlueprint | None = None,
    font_stylesheet_href: str | None = None,
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
    scaffold_id = (dossier.get("scaffoldId") or "").strip()
    # kor-2: build the render dossier whose offer list + company story prefer
    # grounded blueprint copy (when present). Everything downstream — section
    # renderers, icon collectors, layout — reads this one dossier so the offer
    # copy and the icon imports stay byte-consistent. With no blueprint this is
    # the original dossier object, so non-blueprint builds are unchanged.
    render_dossier = apply_blueprint_to_dossier(dossier, blueprint)[0]
    written: list[str] = []
    for route in default_routes:
        route_id = route["id"]
        path = route["path"]
        if scaffold_id in _DISPATCHED_SCAFFOLDS:
            content = _render_dispatched_route(
                scaffold_id=scaffold_id,
                route_id=route_id,
                dossier=render_dossier,
                dossier_routes=dossier_routes,
                listing_route=listing_route,
                contact_path=contact_route["path"],
                variant_id=variant_id,
                blueprint=blueprint,
            )
        elif route_id == "home":
            content = render_home(
                render_dossier,
                dossier_routes,
                listing_route=listing_route,
                contact_path=contact_route["path"],
                variant_id=variant_id,
                blueprint=blueprint,
            )
        elif route_id == "services":
            content = render_services(
                render_dossier,
                contact_path=contact_route["path"],
                blueprint=blueprint,
            )
        elif route_id == "products":
            content = render_products(render_dossier, contact_path=contact_route["path"])
        elif route_id == "menu":
            content = render_menu(
                render_dossier, contact_path=contact_route["path"], blueprint=blueprint
            )
        elif route_id == "booking":
            content = render_booking(
                render_dossier, contact_path=contact_route["path"], blueprint=blueprint
            )
        elif route_id == "about":
            content = render_about(render_dossier)
        elif route_id == "contact":
            content = render_contact(render_dossier, contact_path=contact_route["path"])
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
            if renderer is render_faq:
                content = renderer(
                    render_dossier,
                    contact_path=contact_route["path"],
                    blueprint=blueprint,
                )
            else:
                content = renderer(render_dossier, contact_path=contact_route["path"])
            write(route_to_page_path(target, path), content)
            written.append(path)
            seen_extra_paths.add(path)
            sanitized_extras.append({"id": route_id, "path": path})
    write(
        target / "app" / "layout.tsx",
        render_layout(
            render_dossier,
            dossier_routes,
            scaffold_default_routes=default_routes,
            contact_path=contact_route["path"],
            extra_routes=sanitized_extras or None,
            font_stylesheet_href=font_stylesheet_href,
        ),
    )
    # Sprint 1.2 — branded 404 + error pages. Skrivs alltid (de har
    # inga ``id``-baserade renderers och behöver inte registreras i
    # scaffold:s defaultRoutes). Next.js plockar upp filerna automatiskt
    # via filsystem-routing: ``not-found.tsx`` används för 404 och
    # ``error.tsx`` för uncaught exceptions i alla under-routes.
    write(target / "app" / "not-found.tsx", render_not_found(render_dossier))
    write(target / "app" / "error.tsx", render_global_error(render_dossier))
    # Sprint 1.5 — auto-OG-fallback. SVG:n skrivs alltid till
    # ``public/og-image-fallback.svg`` så Next.js Metadata API kan
    # länka dit oberoende av om operatorn laddat upp en egen.
    # ``render_layout`` använder den som default när
    # ``project_input.media.ogImage`` saknas; om operatorn HAR laddat
    # upp en egen vinner den, men fallback-filen ligger ändå kvar för
    # framtida sociala delningar utan extra build-steg.
    write(
        target / "public" / "og-image-fallback.svg",
        render_og_fallback_svg(render_dossier),
    )
    # Sprint 2.2/2.3 — robots.txt + sitemap.xml. Skrivs alltid så att
    # genererade sajter är Google-indexerbara från första bygget.
    # ``written`` innehåller alla scaffold-default routes plus wizard
    # extra routes (galleri, team, pricing, portfolio osv.) — sitemapen
    # speglar exakt det som faktiskt finns på disk.
    write(target / "public" / "robots.txt", render_robots_txt())
    write(target / "public" / "sitemap.xml", render_sitemap_xml(written))
    return written


# ---------------------------------------------------------------------------
# Initial section registration (basic shared sections).
#
# On ``origin/main`` these were declared as the initial dict literal
# at ``scripts/build_site.py`` line 3509 (immediately after the
# section-renderer functions were defined and before
# ``render_route_generic`` was declared). In the B146-split layout,
# ``dispatcher._SECTION_RENDERERS`` starts empty and renderers.py is
# the only module that registers entries. Scaffold-specific
# registrations happen inline above (see ``_SECTION_RENDERERS.update({...})``
# blocks under restaurant, LSB-extra, clinic, professional-services
# and agency-studio sections); this final block covers the basic
# sections that on main were registered upfront.
# ---------------------------------------------------------------------------


_SECTION_RENDERERS.update(
    {
        "hero": render_section_hero,
        "service-summary": render_section_services_summary,
        "services-summary": render_section_services_summary,
        "service-list": render_section_service_list,
        "trust-proof": render_section_trust_proof,
        "about-story": render_section_about_story,
        "team": render_section_team,
        "contact-cta": render_section_contact_cta,
        "contact-info": render_section_contact_info,
        "products-intro": render_section_products_intro,
        "product-grid": render_section_product_grid,
    }
)
