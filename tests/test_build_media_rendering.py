"""End-to-end tests for media-asset rendering in build_site.py.

Locks the contract between the discovery-resolver (which persists
``directives.media`` into ``project_input.media``) and the build-site
renderers (which read ``project_input.media`` to inject favicon, OG-
image and background video into the generated Next.js source).

Without these tests a future refactor of either side could break the
media-chain silently — the wizard upload would still work but the
generated site would not reflect it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_site import (  # noqa: E402
    _is_valid_asset_ref,
    iter_asset_refs,
    render_global_error,
    render_home,
    render_layout,
    render_not_found,
    render_og_fallback_svg,
    resolve_media_asset,
)


def _favicon_ref() -> dict[str, Any]:
    return {
        "assetId": "01JXXX1234567890ABCDEFGHIJK",
        "filename": "logo-test.webp",
        "mimeType": "image/webp",
        "sizeBytes": 4096,
        "width": 256,
        "height": 256,
        "alt": "Företagslogotyp",
        "role": "favicon",
        "sourceUrl": "https://blob.example/logo-test.webp",
    }


def _og_image_ref() -> dict[str, Any]:
    return {
        "assetId": "01JZZZ1234567890OPENGRAPH00",
        "filename": "social-card.webp",
        "mimeType": "image/webp",
        "sizeBytes": 88_000,
        "width": 1200,
        "height": 630,
        "alt": "Social preview",
        "role": "ogImage",
    }


def _background_video_ref() -> dict[str, Any]:
    return {
        "assetId": "01JYYY9876543210ZYXWVUTSRQP",
        "filename": "hero-loop.mp4",
        "mimeType": "video/mp4",
        "sizeBytes": 2_400_000,
        "width": None,
        "height": None,
        "alt": "Bakgrundsvideo",
        "role": "backgroundVideo",
        "placement": "home",
    }


def _minimal_dossier(media: dict[str, Any] | None = None) -> dict[str, Any]:
    """Minimal dossier that satisfies render_layout + render_home.

    Mirrors the shape used in tests/test_builder_audit_post_3b_next.py so
    failures here are isolated to media-rendering, not dossier-validation.
    """
    dossier: dict[str, Any] = {
        "siteId": "media-rendering-test",
        "company": {
            "name": "Brief Company AB",
            "businessType": "painter",
            "tagline": "Hantverk på vita väggar",
            "story": "",
        },
        "location": {
            "city": "Stockholm",
            "country": "Sverige",
            "serviceAreas": ["Stockholm"],
        },
        "services": [
            {"id": "maleri", "label": "Måleri", "summary": "Måleri inomhus."},
        ],
        "tone": {"primary": "warm", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "hej@example.se",
            "addressLines": ["Exempelgatan 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "gallery": [],
        "brand": {"primaryColorHex": "#1d4ed8"},
    }
    if media:
        dossier["media"] = media
    return dossier


# ── resolve_media_asset ──────────────────────────────────────────────


@pytest.mark.tooling
def test_resolve_reads_canonical_media_block() -> None:
    """Primary path: ``project_input.media`` set by discovery-resolver."""
    dossier = _minimal_dossier({"favicon": _favicon_ref()})
    resolved = resolve_media_asset(dossier, "favicon")
    assert resolved is not None
    assert resolved["filename"] == "logo-test.webp"


@pytest.mark.tooling
def test_resolve_falls_back_to_directives_media() -> None:
    """Defensive fallback for callers that bypass the discovery-resolver
    (e.g. JIT-rendering of a raw wizard payload). Verifies the path-of-
    last-resort still produces the AssetRef."""
    dossier = _minimal_dossier()
    dossier["directives"] = {"media": {"favicon": _favicon_ref()}}
    resolved = resolve_media_asset(dossier, "favicon")
    assert resolved is not None
    assert resolved["assetId"] == "01JXXX1234567890ABCDEFGHIJK"


@pytest.mark.tooling
def test_resolve_returns_none_for_missing_role() -> None:
    assert resolve_media_asset(_minimal_dossier(), "favicon") is None


@pytest.mark.tooling
def test_resolve_rejects_invalid_ref_shape() -> None:
    dossier = _minimal_dossier({"favicon": {"assetId": "missing-filename"}})
    assert resolve_media_asset(dossier, "favicon") is None


@pytest.mark.tooling
def test_resolve_prefers_canonical_over_directives_fallback() -> None:
    """When both paths exist the canonical block wins. This catches a
    regression where the resolver order was accidentally inverted."""
    canonical = _favicon_ref()
    fallback = {**_favicon_ref(), "filename": "older-version.webp"}
    dossier = _minimal_dossier({"favicon": canonical})
    dossier["directives"] = {"media": {"favicon": fallback}}
    resolved = resolve_media_asset(dossier, "favicon")
    assert resolved is not None
    assert resolved["filename"] == "logo-test.webp"


# ── iter_asset_refs ──────────────────────────────────────────────────


@pytest.mark.tooling
def test_iter_includes_all_media_roles() -> None:
    """``copy_operator_uploads`` calls ``iter_asset_refs`` to find every
    asset that needs disk → public/uploads copy. All three new media
    roles must be enumerated or the file copy step will silently skip
    them and the generated site will reference missing paths."""
    dossier = _minimal_dossier(
        {
            "favicon": _favicon_ref(),
            "ogImage": _og_image_ref(),
            "backgroundVideo": _background_video_ref(),
        }
    )
    refs = iter_asset_refs(dossier)
    roles = sorted(ref["role"] for ref in refs)
    assert roles == ["backgroundVideo", "favicon", "ogImage"]


# ── render_layout (favicon + og-image + viewport) ────────────────────


@pytest.mark.tooling
def test_layout_emits_icons_when_favicon_present() -> None:
    dossier = _minimal_dossier({"favicon": _favicon_ref()})
    layout = render_layout(dossier, dossier_routes=["/"])
    assert "icons: {" in layout
    assert '"/uploads/logo-test.webp"' in layout
    assert "apple:" in layout, "Apple touch-icon must use same asset"


@pytest.mark.tooling
def test_layout_emits_open_graph_when_og_image_present() -> None:
    dossier = _minimal_dossier({"ogImage": _og_image_ref()})
    layout = render_layout(dossier, dossier_routes=["/"])
    assert "openGraph:" in layout
    assert '"/uploads/social-card.webp"' in layout
    assert "twitter:" in layout
    assert '"summary_large_image"' in layout


@pytest.mark.tooling
def test_layout_omits_icons_block_when_no_favicon() -> None:
    """Empty media must not emit an empty ``icons: {}`` literal — Next.js
    would treat it as 'opt-in, none defined' and serve no favicon at all."""
    layout = render_layout(_minimal_dossier(), dossier_routes=["/"])
    assert "icons: {" not in layout


@pytest.mark.tooling
def test_layout_uses_og_fallback_when_no_upload() -> None:
    """Sprint 1.5: every site must have a sharable og:image even if the
    operator skipped the upload. Layout must point at the generated
    SVG fallback served from ``public/og-image-fallback.svg``."""
    layout = render_layout(_minimal_dossier(), dossier_routes=["/"])
    assert "openGraph:" in layout
    assert '"/og-image-fallback.svg"' in layout
    assert '"image/svg+xml"' in layout, "Fallback must declare SVG type for older parsers"


@pytest.mark.tooling
def test_layout_emits_preconnect_to_google_fonts() -> None:
    """Sprint 1.1: preconnect-hints är obligatoriska för LCP — utan dem
    kan första paint blockeras 300-700ms av font-loading."""
    layout = render_layout(_minimal_dossier(), dossier_routes=["/"])
    assert "<head>" in layout
    assert 'rel="preconnect"' in layout
    assert "fonts.googleapis.com" in layout
    assert "fonts.gstatic.com" in layout
    assert 'crossOrigin="anonymous"' in layout


@pytest.mark.tooling
def test_layout_emits_theme_color_from_brand() -> None:
    """Viewport.themeColor mirrors brand.primaryColorHex so mobile address
    bars match site identity."""
    dossier = _minimal_dossier()
    layout = render_layout(dossier, dossier_routes=["/"])
    assert "export const viewport: Viewport = {" in layout
    assert '"#1d4ed8"' in layout


# ── render_home (background video in hero) ───────────────────────────


@pytest.mark.tooling
def test_home_injects_background_video_into_hero() -> None:
    dossier = _minimal_dossier({"backgroundVideo": _background_video_ref()})
    home = render_home(dossier, dossier_routes=["/"])
    assert '"/uploads/hero-loop.mp4"' in home
    assert "autoPlay" in home
    assert "loop" in home
    assert "muted" in home
    assert "playsInline" in home


@pytest.mark.tooling
def test_home_omits_video_block_when_no_background_video() -> None:
    home = render_home(_minimal_dossier(), dossier_routes=["/"])
    assert "/uploads/hero-loop.mp4" not in home
    # No raw <video> tag anywhere when operator skipped the upload.
    assert "<video" not in home


@pytest.mark.tooling
def test_home_video_uses_hero_image_as_poster_when_available() -> None:
    """Operator-uploaded hero image becomes the ``poster`` so the first
    frame looks intentional even before autoplay starts (or on browsers
    that block autoplay)."""
    dossier = _minimal_dossier({"backgroundVideo": _background_video_ref()})
    dossier["brand"]["heroImage"] = {
        "assetId": "01JHHH0000000000000000HEROHERO",
        "filename": "hero-shot.webp",
        "mimeType": "image/webp",
        "sizeBytes": 50_000,
        "width": 1600,
        "height": 1200,
        "alt": "Hero",
        "role": "hero",
    }
    home = render_home(dossier, dossier_routes=["/"])
    assert "poster=" in home
    assert "/uploads/hero-shot.webp" in home


# ── _is_valid_asset_ref guard ────────────────────────────────────────


# ── Sprint 1.2 — not-found + error pages ─────────────────────────────


@pytest.mark.tooling
def test_not_found_includes_company_name_and_back_link() -> None:
    page = render_not_found(_minimal_dossier())
    assert '"use client"' not in page, "not-found.tsx must render server-side"
    assert "Brief Company AB" in page
    assert 'href="/"' in page
    assert "Tillbaka till startsidan" in page
    assert "+46 8 000 00 00" in page, "Contact phone should be reachable from 404"


@pytest.mark.tooling
def test_error_page_is_client_component_with_reset() -> None:
    page = render_global_error(_minimal_dossier())
    assert page.startswith('"use client"'), "error.tsx must be a Client Component"
    assert "reset: () => void" in page
    assert "onClick={() => reset()}" in page
    assert "error.digest" in page, "digest is what links the page to server logs"


# ── Sprint 1.5 — OG fallback SVG ─────────────────────────────────────


@pytest.mark.tooling
def test_og_fallback_uses_brand_color_when_set() -> None:
    dossier = _minimal_dossier()
    svg = render_og_fallback_svg(dossier)
    assert svg.startswith('<?xml version="1.0"')
    assert 'width="1200" height="630"' in svg
    assert '#1d4ed8' in svg, "Brand primary color must be background"
    assert "Brief Company AB" in svg


@pytest.mark.tooling
def test_og_fallback_falls_back_to_neutral_when_no_brand_color() -> None:
    dossier = _minimal_dossier()
    dossier["brand"].pop("primaryColorHex")
    svg = render_og_fallback_svg(dossier)
    # Default-fallback ska vara slate-900 (#0f172a) — neutral, professionell
    assert "#0f172a" in svg


@pytest.mark.tooling
def test_og_fallback_escapes_html_in_company_name() -> None:
    """Operator-provided name måste XML-escapas eller SVG:n bryts. Detta
    var en B30-klassad sårbarhet i tidigare templates."""
    dossier = _minimal_dossier()
    dossier["company"]["name"] = "<script>alert(1)</script>"
    svg = render_og_fallback_svg(dossier)
    assert "<script>" not in svg, "Raw HTML must not survive into SVG"
    assert "&lt;script&gt;" in svg


@pytest.mark.tooling
def test_og_fallback_picks_dark_text_on_light_background() -> None:
    """Sprint 1.5: luma-baserad text-färgsval. Vitt på vitt skulle ge
    en helt blank social-preview vilket är värre än ingen preview alls."""
    dossier = _minimal_dossier()
    dossier["brand"]["primaryColorHex"] = "#fef3c7"
    svg = render_og_fallback_svg(dossier)
    assert 'fill="#0f172a"' in svg
    assert 'fill="#ffffff"' not in svg


@pytest.mark.tooling
def test_og_fallback_picks_light_text_on_dark_background() -> None:
    dossier = _minimal_dossier()
    dossier["brand"]["primaryColorHex"] = "#0c0a09"
    svg = render_og_fallback_svg(dossier)
    assert 'fill="#ffffff"' in svg


@pytest.mark.tooling
def test_validator_rejects_partial_refs() -> None:
    assert _is_valid_asset_ref({}) is False
    assert _is_valid_asset_ref({"assetId": "x"}) is False
    assert _is_valid_asset_ref({"filename": "x.png"}) is False
    assert _is_valid_asset_ref({"assetId": "x", "filename": "x.png"}) is True
    assert _is_valid_asset_ref("not a dict") is False
    assert _is_valid_asset_ref(None) is False
