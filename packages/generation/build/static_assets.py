"""Static asset renderers for generated Next.js sites.

Extracted from ``scripts/build_site.py`` for B13a Step C. Shared builder
utilities stay in ``scripts.build_site`` until the later full architecture
move, so this module resolves those helpers lazily to avoid circular imports.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from packages.generation.build.contact_placeholders import (
    real_address_lines,
    real_email,
    real_opening_hours,
    real_phone,
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


def _call_build_site(name: str, *args: Any, **kwargs: Any) -> Any:
    return getattr(_build_site_module(), name)(*args, **kwargs)


def _jsx_safe_string(text: str) -> str:
    return _call_build_site("_jsx_safe_string", text)


def _normalise_hex_color(value: Any) -> str | None:
    return _call_build_site("_normalise_hex_color", value)


def _phone_href(phone: str) -> str:
    return _call_build_site("_phone_href", phone)


def render_robots_txt() -> str:
    """Return a minimal ``robots.txt`` body. Sprint 2.2.

    Generated sites are intended to be publicly indexed by default —
    Sajtbyggaren's whole point is to ship a site that operators can
    point Google at. Therefore the policy is "allow all" plus a
    sitemap-pointer.

    We use a relative sitemap-URL (``/sitemap.xml``) instead of an
    absolute one because the deployment domain isn't known at build
    time. Google + Bing both honour relative URLs in robots.txt as
    long as they're served from the same origin as the robots file.
    Operatorer som vill blockera enskilda paths (t.ex. /admin) lägger
    till regler i builder:n senare; default-statet är index-allt.
    """
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        "Sitemap: /sitemap.xml\n"
    )


def render_sitemap_xml(written_paths: list[str]) -> str:
    """Return a ``sitemap.xml`` body listing every route the builder
    actually wrote. Sprint 2.3.

    We use the XML 0.9 Sitemap Protocol (the universal one Google,
    Bing, Yandex and DuckDuckGo all parse). Three notable choices:

      * URLs är relativa (``loc>/tjanster</loc``) av samma anledning
        som robots.txt — vi vet inte vilken domän operatorn
        deployar på. Google klarar relativa URLs så länge sitemapen
        serveras från samma host.
      * ``priority`` skala 1.0 (startsida) → 0.7 (sekundära sidor).
        Detta är heuristiskt — Google ignorerar det numera, men
        Bing och flera SEO-verktyg använder det fortfarande.
      * ``changefreq=weekly`` är en rimlig default för småföretags-
        sajter. Inga av våra renderers genererar dynamiskt innehåll
        som ändras dagligen.
    """
    import html as _html_module

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    # Avduplicera och normalisera så ``/`` och ``/`` inte räknas två
    # gånger om någon scaffold råkar lägga in den dubbelt.
    seen: set[str] = set()
    for raw in written_paths:
        if not isinstance(raw, str):
            continue
        path = raw if raw.startswith("/") else "/" + raw
        if path in seen:
            continue
        seen.add(path)
        priority = "1.0" if path == "/" else "0.7"
        # Bug-fix: XML-escape path (defensivt mot framtida scaffold-paths
        # som innehåller ``&`` eller ``<`` — t.ex. /artiklar?id=...).
        # ``quote=False`` håller ``"`` orörd eftersom vi inte är i ett
        # attribut-värde. Standard-paths som ``/tjanster`` är oförändrade.
        safe_path = _html_module.escape(path, quote=False)
        lines.append("  <url>")
        lines.append(f"    <loc>{safe_path}</loc>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def _render_structured_data_jsonld(dossier: dict) -> str:
    """Return a JSON-LD ``LocalBusiness`` blob (string) suitable for
    embedding in a ``<script type="application/ld+json">`` tag. Sprint 2.1.

    Why LocalBusiness specifically: Sajtbyggaren targets svenska små-
    företag (måleri, café, hantverk, restaurang, konsult etc.) — alla
    matchar Schema.org/LocalBusiness exakt. För dem som har en fysisk
    adress fungerar det dessutom direkt med Google Business Profile.
    Mer specialiserade typer (Restaurant, Dentist, Cafe, etc.) finns,
    men för MVP rendrar vi en generisk ``LocalBusiness`` så vi inte
    behöver mappning per bransch här — operatorn kan byta till en
    specifik subtyp senare via builder-prompts.

    Vi inkluderar bara fält där dossier:n verkligen har data, så
    Google Rich Results inte avvisar markeringen för ``null``-värden.
    Tom telephone, address eller adress utan locality skulle förstöra
    "Verified Business"-badge:n.

    Returns the raw JSON-LD content (without script-tag wrapper) so
    layout-byggaren kan bädda in det med korrekt JSX-escaping.
    """
    import json as _json_module

    company = dossier["company"]
    location = dossier.get("location") if isinstance(dossier.get("location"), dict) else {}
    contact = dossier.get("contact") if isinstance(dossier.get("contact"), dict) else {}

    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": company.get("name") or "",
    }
    if company.get("tagline"):
        payload["description"] = company["tagline"]
    # Only publish real contact data in structured metadata. Placeholder
    # fallbacks (B88 dummy phone/email/address) are omitted rather than
    # emitted as a fake "Verified Business" telephone/email/address.
    real_contact_phone = real_phone(contact)
    if real_contact_phone is not None:
        payload["telephone"] = real_contact_phone
    real_contact_email = real_email(contact)
    if real_contact_email is not None:
        payload["email"] = real_contact_email

    address_lines = real_address_lines(contact)
    address_part: dict[str, Any] = {}
    if address_lines:
        address_part["streetAddress"] = ", ".join(
            line.strip() for line in address_lines if isinstance(line, str) and line.strip()
        )
    if location.get("city"):
        address_part["addressLocality"] = location["city"]
    if location.get("country"):
        address_part["addressCountry"] = location["country"]
    if address_part:
        address_part["@type"] = "PostalAddress"
        payload["address"] = address_part

    service_areas = location.get("serviceAreas") if isinstance(location, dict) else None
    if isinstance(service_areas, list):
        clean_areas = [
            area.strip()
            for area in service_areas
            if isinstance(area, str) and area.strip()
        ]
        if clean_areas:
            payload["areaServed"] = clean_areas

    real_contact_hours = real_opening_hours(contact)
    if real_contact_hours is not None:
        # OpeningHours-fältet i Schema.org förväntar ett strukturerat
        # format (e.g. "Mo-Fr 09:00-17:00"). Dossier-värdet är fri
        # svensk text ("Mån-Fre 09:00-17:00"). Vi rendrar den som
        # ``openingHoursSpecification`` i ren string-form — Google
        # accepterar både den och den strukturerade varianten. Placeholder-
        # öppettider utelämnas så markeringen inte publicerar fejkdata.
        payload["openingHours"] = real_contact_hours

    # ``json.dumps`` skapar valid JSON; vi förlitar oss på Reacts
    # inbyggda JSX-escaping för att skydda script-innehållet via
    # ``dangerouslySetInnerHTML`` (det är godtagbart för JSON-LD —
    # innehållet är data, inte exekverbar kod, och vi har redan
    # serialiserat bort potentiella ``</script>``-strängar via
    # ensure_ascii=False och en explicit re-escape nedan).
    serialized = _json_module.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Skydd mot inbäddade ``</script>``-strängar i operator-input som
    # annars skulle bryta sig ut ur scriptet. ``\u003c`` är giltig
    # JSON och rendreras tillbaka som ``<`` i alla parsers.
    return serialized.replace("</", "<\\/")


def render_og_fallback_svg(dossier: dict) -> str:
    """Return an SVG (string) used as Open Graph fallback when the
    operator hasn't uploaded a custom og-image. Sprint 1.5.

    Why SVG and not PNG/JPG:

      * Server-side PNG-generation requires either Satori/Resvg-js
        (Node deps) or Pillow (Python; works but adds 30 MB to the
        Docker image and a long cold-start). SVG is built with string
        concatenation — zero deps, deterministic, ~2 KB on disk.
      * 95 % of social platforms (Twitter, Facebook, LinkedIn, Slack,
        Discord, iMessage, WhatsApp, Telegram) render SVG og:images
        without a problem. The 5 % that don't fall back to the page
        title which is still better than the "naked" no-preview state
        we have today.
      * The SVG is brand-tinted via primaryColorHex so it actually
        looks intentional, not like a default placeholder.

    Returns the raw SVG (XML declaration + <svg> + content). The
    caller writes it to ``public/og-image-fallback.svg`` so Next.js
    serves it under that URL.
    """
    company = dossier["company"]
    brand = dossier.get("brand") if isinstance(dossier.get("brand"), dict) else {}
    primary_hex_raw = brand.get("primaryColorHex") if isinstance(brand, dict) else None
    primary_hex = _normalise_hex_color(primary_hex_raw) or "#0f172a"
    # Tagline kan vara None/empty; visa då bara namnet centrerat.
    # Bug-fix: trim långa namn så de inte overflowar 1200px-canvasen.
    # ~52 tecken @ 56px font-size får plats med ~100px vänster-gutter
    # och 50px höger-marginal. Längre namn ellips:as.
    raw_name = (company.get("name") or "").strip() or "Sajten"
    if len(raw_name) > 52:
        raw_name = raw_name[:49].rstrip() + "…"
    raw_tagline = (company.get("tagline") or "").strip()
    # XML-escapa för att skydda mot " < > & ' i operator-input. SVG är
    # XML — vi får INTE skicka rå text in i <text>-noder.
    import html as _html_module

    safe_name = _html_module.escape(raw_name, quote=False)
    safe_tagline = _html_module.escape(raw_tagline, quote=False)
    monogram = _html_module.escape(raw_name[:2].upper(), quote=False)
    # Beräkna kontrast-säker text-färg mot bakgrund. Om brand-hex är
    # ljus (luma > 0.6) väljer vi mörk text; annars vit. Standard luma:
    # 0.2126·R + 0.7152·G + 0.0722·B (sRGB-perception).
    r = int(primary_hex[1:3], 16) / 255.0
    g = int(primary_hex[3:5], 16) / 255.0
    b = int(primary_hex[5:7], 16) / 255.0
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    text_color = "#0f172a" if luma > 0.6 else "#ffffff"
    muted_color = "rgba(15,23,42,0.65)" if luma > 0.6 else "rgba(255,255,255,0.75)"
    # Auto-skala texten om namnet är långt — annars stora namn flödar
    # ut ur 1200×630-ramen.
    name_font_size = 96 if len(raw_name) <= 18 else 72 if len(raw_name) <= 28 else 56
    tagline_block = ""
    if safe_tagline:
        tagline_block = (
            f'  <text x="100" y="450" font-family="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif" '
            f'font-size="36" font-weight="400" fill="{muted_color}">'
            f"{safe_tagline[:80]}"
            "</text>\n"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">\n'
        f'  <rect width="1200" height="630" fill="{primary_hex}" />\n'
        # Decorativ gradient overlay (subtilt ljus från övre högra hörnet)
        '  <defs>\n'
        '    <radialGradient id="glow" cx="80%" cy="20%" r="60%">\n'
        '      <stop offset="0%" stop-color="white" stop-opacity="0.25" />\n'
        '      <stop offset="100%" stop-color="white" stop-opacity="0" />\n'
        '    </radialGradient>\n'
        '  </defs>\n'
        '  <rect width="1200" height="630" fill="url(#glow)" />\n'
        # Monogram-cirkel i högra övre hörnet
        f'  <circle cx="1050" cy="150" r="80" fill="{text_color}" fill-opacity="0.12" />\n'
        f'  <text x="1050" y="172" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif" '
        f'font-size="56" font-weight="700" fill="{text_color}">{monogram}</text>\n'
        # Företagsnamn — stort, vänsterställt mot vänster gutter
        f'  <text x="100" y="350" font-family="-apple-system, BlinkMacSystemFont, Inter, system-ui, sans-serif" '
        f'font-size="{name_font_size}" font-weight="700" fill="{text_color}" letter-spacing="-2">'
        f"{safe_name}"
        "</text>\n"
        f"{tagline_block}"
        # Decorativ accent-stapel under tagline
        f'  <rect x="100" y="520" width="120" height="6" fill="{text_color}" fill-opacity="0.4" rx="3" />\n'
        "</svg>\n"
    )


def render_not_found(dossier: dict) -> str:
    """Render an ``app/not-found.tsx`` page used by Next.js when no route
    matches the URL. Sprint 1.2.

    We replace the default Next.js black-on-white text-only 404 with a
    branded experience that:

      * Reuses the company name + tagline so the page feels like the rest
        of the site (not an interruption).
      * Suggests the home page + the primary listing route (services or
        products depending on scaffold) so the operator gets back to
        useful content in one click.
      * Surfaces the contact phone number for high-intent visitors who
        clearly tried to find something specific.

    Customer-text is JSX-escaped via ``_jsx_safe_string`` so the same
    B30 safety net the rest of the renderers use protects this page too.
    """
    company = dossier["company"]
    contact = dossier["contact"]
    safe_name = _jsx_safe_string(company["name"])
    safe_tagline = _jsx_safe_string(company["tagline"])
    # Only surface the phone CTA when it is a real number. A placeholder
    # phone is suppressed (and the Phone icon dropped from the import) so
    # the 404 never offers ``+46 8 000 00 00`` as a callable affordance —
    # the "Tillbaka till startsidan" link remains the honest next step.
    real_contact_phone = real_phone(contact)
    if real_contact_phone is not None:
        icon_import = 'import { ArrowLeft, Phone } from "lucide-react";\n'
        phone_href = _jsx_safe_string("tel:" + _phone_href(real_contact_phone))
        phone_cta = (
            f'        <a href={phone_href} className="inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />{_jsx_safe_string(real_contact_phone)}</a>\n'
        )
    else:
        icon_import = 'import { ArrowLeft } from "lucide-react";\n'
        phone_cta = ""
    return (
        'import Link from "next/link";\n'
        + icon_import
        + "\n"
        "export default function NotFound() {\n"
        "  return (\n"
        '    <main className="mx-auto flex w-[var(--container-width)] flex-col items-center gap-8 py-[calc(var(--section-spacing)*1.5)] text-center">\n'
        '      <p className="font-mono text-xs uppercase tracking-[0.3em] text-[color:var(--muted)]">404 — sidan hittades inte</p>\n'
        f'      <h1 className="max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">Vi hittade inte det du letade efter</h1>\n'
        f'      <p className="max-w-xl text-lg text-[color:var(--muted)] leading-relaxed">Sidan kan ha flyttats eller tagits bort. Hör av dig till {safe_name} så hjälper vi dig vidare.</p>\n'
        '      <div className="flex flex-wrap items-center justify-center gap-3">\n'
        '        <Link href="/" className="inline-flex items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><ArrowLeft className="size-4" />Tillbaka till startsidan</Link>\n'
        + phone_cta
        + "      </div>\n"
        f'      <p className="text-xs text-[color:var(--muted)]">{safe_tagline}</p>\n'
        "    </main>\n"
        "  );\n"
        "}\n"
    )


def render_global_error(dossier: dict) -> str:
    """Render an ``app/error.tsx`` page shown by Next.js when a server
    component throws. Sprint 1.2.

    Next.js requires this file to be a Client Component (it needs the
    ``reset`` callback) so we emit ``"use client"`` at the top. The
    page mirrors not-found.tsx visually but with a recovery action:
    a ``Försök igen``-button bound to ``reset()`` which re-mounts the
    failing tree without a full page reload.
    """
    company = dossier["company"]
    contact = dossier["contact"]
    safe_name = _jsx_safe_string(company["name"])
    phone_href = _jsx_safe_string("tel:" + _phone_href(contact["phone"]))
    return (
        '"use client";\n'
        "\n"
        'import { useEffect } from "react";\n'
        'import { Phone, RefreshCw } from "lucide-react";\n'
        "\n"
        "export default function ErrorBoundary({\n"
        "  error,\n"
        "  reset,\n"
        "}: {\n"
        "  error: Error & { digest?: string };\n"
        "  reset: () => void;\n"
        "}) {\n"
        "  useEffect(() => {\n"
        "    // Surface the error to whatever telemetry the operator wires up\n"
        "    // (Sentry, Logflare, Vercel Analytics). For now a console.error\n"
        "    // keeps the digest discoverable in production logs without\n"
        "    // exposing the stack trace to end users.\n"
        '    console.error("[error.tsx]", error);\n'
        "  }, [error]);\n"
        "  return (\n"
        '    <main className="mx-auto flex w-[var(--container-width)] flex-col items-center gap-8 py-[calc(var(--section-spacing)*1.5)] text-center">\n'
        '      <p className="font-mono text-xs uppercase tracking-[0.3em] text-[color:var(--muted)]">500 — något gick fel</p>\n'
        '      <h1 className="max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight md:text-6xl">Ett tekniskt fel uppstod</h1>\n'
        f'      <p className="max-w-xl text-lg text-[color:var(--muted)] leading-relaxed">Vi ber om ursäkt — sidan kunde inte laddas just nu. Försök igen eller kontakta {safe_name} så hjälper vi dig.</p>\n'
        '      <div className="flex flex-wrap items-center justify-center gap-3">\n'
        '        <button type="button" onClick={() => reset()} className="inline-flex items-center gap-2 rounded-md bg-[color:var(--primary)] px-5 py-3 text-sm font-medium text-[color:var(--primary-foreground)] hover:opacity-90 transition-opacity"><RefreshCw className="size-4" />Försök igen</button>\n'
        f'        <a href={phone_href} className="inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] px-5 py-3 text-sm font-medium hover:bg-[color:var(--accent)] transition-colors"><Phone className="size-4" />{_jsx_safe_string(contact["phone"])}</a>\n'
        "      </div>\n"
        '      {error.digest ? (\n'
        '        <p className="font-mono text-[10px] text-[color:var(--muted)]/70">Fel-ID: {error.digest}</p>\n'
        "      ) : null}\n"
        "    </main>\n"
        "  );\n"
        "}\n"
    )

