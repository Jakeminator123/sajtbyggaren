"""Regression tests for honest contact-fallback rendering (fix(contact)).

When a prompt gives no contact info, scripts/prompt_to_project_input.py
fills the schema-required contact block with B88 placeholder values
(``+46 8 000 00 00`` / ``kontakt@example.se`` / ``Adress lämnas på
förfrågan`` / ``Mån-Fre 09:00-17:00``). These tests lock that none of
those dummy values reach the generated site across the six surfaces that
render contact data (layout footer, contact page, hours-summary, booking
fallback phone, 404 page, JSON-LD), while real operator-supplied contact
data still renders.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.build import contact_placeholders as cp  # noqa: E402
from scripts.build_site import (  # noqa: E402
    _render_structured_data_jsonld,
    render_contact,
    render_home,
    render_layout,
    render_not_found,
    render_section_fallback_phone,
    render_section_hours_summary,
)

PLACEHOLDER_CONTACT: dict[str, Any] = {
    "phone": "+46 8 000 00 00",
    "email": "kontakt@example.se",
    "addressLines": ["Adress lämnas på förfrågan"],
    "openingHours": "Mån-Fre 09:00-17:00",
}
REAL_CONTACT: dict[str, Any] = {
    "phone": "+46 70 111 22 33",
    "email": "info@firma.se",
    "addressLines": ["Storgatan 5", "111 22 Stockholm"],
    "openingHours": "Mån-Fre 08-16",
}
PLACEHOLDER_STRINGS = (
    "+46 8 000 00 00",
    "kontakt@example.se",
    "Adress lämnas på förfrågan",
)


def _dossier(contact: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    dossier: dict[str, Any] = {
        "siteId": "fallback-test",
        "language": "sv",
        "scaffoldId": "local-service-business",
        "conversionGoals": [],
        "company": {
            "name": "Demo AB",
            "businessType": "service-provider",
            "tagline": "Vi hjälper dig vidare",
            "story": "En kort story.",
            "team": [],
        },
        "location": {"city": "Stockholm", "country": "Sverige", "serviceAreas": []},
        "services": [{"id": "a", "label": "Tjänst", "summary": "Sammanfattning."}],
        "trustSignals": [],
        "brand": {"primaryColorHex": "#1d4ed8"},
        "contact": dict(contact),
    }
    dossier.update(overrides)
    return dossier


# ── single source of truth ───────────────────────────────────────────


@pytest.mark.tooling
def test_placeholder_constants_match_producer() -> None:
    """contact_placeholders mirrors prompt_to_project_input's B88 values.

    renderers/static_assets live in packages/ and cannot import from
    scripts/, so the placeholder values are duplicated. This test locks
    the duplication so the two cannot drift apart.
    """
    from scripts import prompt_to_project_input as producer

    assert cp.PLACEHOLDER_PHONE == producer._PLACEHOLDER_CONTACT_PHONE
    assert producer._PLACEHOLDER_CONTACT_EMAIL_SV in cp.PLACEHOLDER_EMAILS
    assert producer._PLACEHOLDER_CONTACT_EMAIL_EN in cp.PLACEHOLDER_EMAILS
    assert producer._PLACEHOLDER_CONTACT_ADDRESS_SV in cp.PLACEHOLDER_ADDRESS_LINES
    assert producer._PLACEHOLDER_CONTACT_ADDRESS_EN in cp.PLACEHOLDER_ADDRESS_LINES
    assert producer._PLACEHOLDER_CONTACT_OPENING_HOURS_SV in cp.PLACEHOLDER_OPENING_HOURS
    assert producer._PLACEHOLDER_CONTACT_OPENING_HOURS_EN in cp.PLACEHOLDER_OPENING_HOURS


# ── layout footer (every page) ───────────────────────────────────────


@pytest.mark.tooling
def test_layout_footer_suppresses_placeholder_contact() -> None:
    layout = render_layout(_dossier(PLACEHOLDER_CONTACT), ["/"])
    for needle in PLACEHOLDER_STRINGS:
        assert needle not in layout
    assert 'href="tel:+4680000000"' not in layout
    assert "mailto:kontakt@example.se" not in layout
    # Honest CTA: footer still links to the contact route (JSX-expression
    # href form produced by _route_href).
    assert 'href={"/kontakt"}' in layout


@pytest.mark.tooling
def test_layout_footer_renders_real_contact() -> None:
    layout = render_layout(_dossier(REAL_CONTACT), ["/"])
    assert "+46 70 111 22 33" in layout
    assert "info@firma.se" in layout
    assert "Storgatan 5, 111 22 Stockholm" in layout


# ── contact page ─────────────────────────────────────────────────────


@pytest.mark.tooling
def test_contact_page_suppresses_placeholder_contact() -> None:
    page = render_contact(_dossier(PLACEHOLDER_CONTACT))
    for needle in PLACEHOLDER_STRINGS:
        assert needle not in page
    # All channels were placeholders -> honest invitation card, no unused
    # lucide import (no icons emitted).
    assert "Så når du oss" in page
    assert 'from "lucide-react"' not in page
    # B159: even with nothing real, the page keeps an honest contact CTA
    # (links to the contact route with CTA text; no dummy tel:/mailto:).
    assert "Hör av dig" in page
    assert 'href={"/kontakt"}' in page


@pytest.mark.tooling
def test_contact_page_renders_real_contact() -> None:
    page = render_contact(_dossier(REAL_CONTACT))
    assert "+46 70 111 22 33" in page
    assert "info@firma.se" in page
    assert "Storgatan 5" in page
    assert 'import { Clock, Mail, MapPin, Phone } from "lucide-react";' in page


@pytest.mark.tooling
def test_contact_page_real_phone_placeholder_address_keeps_phone_only() -> None:
    """A partially-filled contact renders only the real channel(s)."""
    contact = {
        "phone": "+46 70 111 22 33",
        "email": "kontakt@example.se",
        "addressLines": ["Adress lämnas på förfrågan"],
        "openingHours": "Mån-Fre 09:00-17:00",
    }
    page = render_contact(_dossier(contact))
    assert "+46 70 111 22 33" in page
    assert "kontakt@example.se" not in page
    assert "Adress lämnas på förfrågan" not in page
    # Phone is real but its hours are placeholder -> hours line dropped.
    assert "Mån-Fre 09:00-17:00" not in page


# ── 404 page ─────────────────────────────────────────────────────────


@pytest.mark.tooling
def test_not_found_suppresses_placeholder_phone() -> None:
    page = render_not_found(_dossier(PLACEHOLDER_CONTACT))
    assert "+46 8 000 00 00" not in page
    assert "Tillbaka till startsidan" in page
    assert 'import { ArrowLeft } from "lucide-react";' in page


@pytest.mark.tooling
def test_not_found_renders_real_phone() -> None:
    page = render_not_found(_dossier(REAL_CONTACT))
    assert "+46 70 111 22 33" in page
    assert 'import { ArrowLeft, Phone } from "lucide-react";' in page


# ── JSON-LD structured data ──────────────────────────────────────────


@pytest.mark.tooling
def test_jsonld_omits_placeholder_contact() -> None:
    payload = json.loads(
        _render_structured_data_jsonld(_dossier(PLACEHOLDER_CONTACT)).replace("<\\/", "</")
    )
    assert "telephone" not in payload
    assert "email" not in payload
    assert "openingHours" not in payload
    # The placeholder street address is omitted, but real location-derived
    # locality/country (from ``location``, not the dummy contact block) are
    # still valid structured data, so the address block keeps those.
    assert "streetAddress" not in payload.get("address", {})
    assert payload["address"]["addressLocality"] == "Stockholm"
    assert payload["address"]["addressCountry"] == "Sverige"


@pytest.mark.tooling
def test_jsonld_emits_real_contact() -> None:
    payload = json.loads(
        _render_structured_data_jsonld(_dossier(REAL_CONTACT)).replace("<\\/", "</")
    )
    assert payload["telephone"] == "+46 70 111 22 33"
    assert payload["email"] == "info@firma.se"
    assert payload["openingHours"] == "Mån-Fre 08-16"
    assert payload["address"]["streetAddress"] == "Storgatan 5, 111 22 Stockholm"


# ── hours-summary + booking fallback sections ────────────────────────


@pytest.mark.tooling
def test_hours_summary_suppresses_placeholder_hours() -> None:
    assert render_section_hours_summary(_dossier(PLACEHOLDER_CONTACT)) == ""
    real = render_section_hours_summary(_dossier(REAL_CONTACT))
    assert "Mån-Fre 08-16" in real


@pytest.mark.tooling
def test_fallback_phone_suppresses_placeholder_channels() -> None:
    assert render_section_fallback_phone(_dossier(PLACEHOLDER_CONTACT)) == ""
    real = render_section_fallback_phone(_dossier(REAL_CONTACT))
    assert "+46 70 111 22 33" in real
    assert "info@firma.se" in real


# ── commerce unaffected + eval guard intact ──────────────────────────


@pytest.mark.tooling
def test_products_renderer_unaffected_by_contact_fallback() -> None:
    from scripts.build_site import render_products

    output = render_products(_dossier(PLACEHOLDER_CONTACT), contact_path="/kontakt")
    assert 'href={"/kontakt"}' in output


@pytest.mark.tooling
def test_eval_still_flags_dummy_contact_copy_if_it_reappears() -> None:
    """The golden-path eval must still catch placeholder copy regressions."""
    from scripts.run_golden_path_eval import generic_copy_hits

    leaked = '<a href={"mailto:kontakt@example.se"}>kontakt@example.se</a>'
    assert generic_copy_hits(leaked)


# ── mixed address: drop only the placeholder line (Codex 2026-06-01) ──


@pytest.mark.tooling
def test_real_address_lines_drops_placeholder_line_in_mixed_list() -> None:
    contact = {"addressLines": ["Storgatan 5", "Adress lämnas på förfrågan"]}
    assert cp.real_address_lines(contact) == ["Storgatan 5"]


@pytest.mark.tooling
def test_contact_page_mixed_address_renders_only_real_line() -> None:
    contact = {
        "phone": "+46 8 000 00 00",
        "email": "kontakt@example.se",
        "addressLines": ["Storgatan 5", "Adress lämnas på förfrågan"],
        "openingHours": "Mån-Fre 09:00-17:00",
    }
    page = render_contact(_dossier(contact))
    assert "Storgatan 5" in page
    assert "Adress lämnas på förfrågan" not in page


# ── B158: hero secondary phone CTA suppresses the placeholder number ──


@pytest.mark.tooling
def test_home_hero_suppresses_placeholder_phone_cta() -> None:
    home = render_home(_dossier(PLACEHOLDER_CONTACT), ["/"])
    assert "+46 8 000 00 00" not in home
    assert "tel:+4680000000" not in home


@pytest.mark.tooling
def test_home_hero_keeps_real_phone_cta() -> None:
    home = render_home(_dossier(REAL_CONTACT), ["/"])
    # _jsx_safe_string wraps the number as {"..."} and _phone_href strips
    # spaces for the tel: target, so assert both forms rather than the raw
    # "Ring +46 ..." concatenation.
    assert "Ring {" in home
    assert "+46 70 111 22 33" in home
    assert "tel:+46701112233" in home


# ── B159: restaurant /hitta-hit keeps a contact CTA ───────────────────


@pytest.mark.tooling
def test_contact_page_has_cta_when_all_channels_placeholder() -> None:
    """Mirrors the contact-cta-presence quality gate: a contact-route link
    with CTA text, even when every channel is a placeholder (restaurant
    /hitta-hit is rendered by render_contact with that route path)."""
    page = render_contact(_dossier(PLACEHOLDER_CONTACT), contact_path="/hitta-hit")
    assert 'href={"/hitta-hit"}' in page
    assert "Hör av dig" in page
    assert "tel:+4680000000" not in page
    assert "mailto:kontakt@example.se" not in page


@pytest.mark.tooling
def test_contact_page_address_only_still_has_cta() -> None:
    """Real address but no phone/email still appends an explicit contact CTA."""
    contact = {
        "phone": "+46 8 000 00 00",
        "email": "kontakt@example.se",
        "addressLines": ["Storgatan 5", "111 22 Stockholm"],
        "openingHours": "Mån-Fre 09:00-17:00",
    }
    page = render_contact(_dossier(contact), contact_path="/hitta-hit")
    assert "Storgatan 5" in page
    assert 'href={"/hitta-hit"}' in page
    assert "Hör av dig" in page
