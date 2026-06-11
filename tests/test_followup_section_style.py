"""Coverage for section-scoped colour overrides ("Färglägg sektionen", fas 3).

The preview section menu emits a deterministic prompt ("Ändra
bakgrundsfärgen i den markerade sektionen till #aabbcc.") together with
the validated ``markedSections`` signal (ADR 0046). These tests lock:

- the deterministic extractor (section reference + explicit target +
  hex/colour word, otherwise ``None``),
- the apply/upsert into ``directives.sectionStyleOverrides``,
- the merge integration (override applied, theme path short-circuited so
  the same hex never ALSO repaints the brand primary; honest fallthrough
  to the theme path without markings),
- the CSS emission in build_site.py (selector + ``!important`` +
  idempotent region), and schema validity of the merged Project Input.
"""

from __future__ import annotations

import copy

import pytest

from packages.generation.followup.section_style import (
    MAX_SECTION_STYLE_OVERRIDES,
    SectionStyleDirective,
    apply_section_style_directive,
    extract_section_style_directive,
)
from scripts.build_site import _section_style_overrides_css
from scripts.prompt_to_project_input import (
    _validate_against_schema,
    merge_followup_project_input,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

# The exact prompt shapes the ColorizeSectionDialog emits.
_DIALOG_BACKGROUND_PROMPT = (
    'Ändra bakgrundsfärgen i den markerade sektionen "Vad vi tar oss an" '
    "till #aabbcc. Behåll övrig design, copy och struktur intakt."
)
_DIALOG_TEXT_PROMPT = (
    'Ändra textfärgen i den markerade sektionen "Vad vi tar oss an" '
    "till #112233. Behåll övrig design, copy och struktur intakt."
)


def _previous_project_input() -> dict[str, object]:
    """A schema-valid Project Input standing in for a previous version."""
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "getgard-abc123",
        "scaffoldId": "local-service-business",
        "variantId": "family-warmth",
        "language": "sv",
        "company": {
            "name": "Getgården",
            "businessType": "farm",
            "tagline": "Getter som äter gräs i Småland",
            "story": "En liten gård med betande getter.",
        },
        "location": {
            "city": "Växjö",
            "country": "Sverige",
            "serviceAreas": ["Småland"],
        },
        "services": [
            {"id": "bete", "label": "Naturbete", "summary": "Getter som betar."}
        ],
        "tone": {"primary": "trustworthy", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "kontakt@example.se",
            "addressLines": ["Adress lämnas på förfrågan"],
            "openingHours": "Mån-Fre 9-17",
        },
        "selectedDossiers": {"required": [], "recommended": []},
    }


def _merge(
    prompt: str,
    marked_sections: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    previous = _previous_project_input()
    return merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt=prompt,
        marked_sections=marked_sections,
    )


# --- extraction ------------------------------------------------------------


@pytest.mark.tooling
def test_extract_background_hex_from_dialog_prompt() -> None:
    directive = extract_section_style_directive(_DIALOG_BACKGROUND_PROMPT)
    assert directive == SectionStyleDirective(
        target="background", color_hex="#aabbcc"
    )


@pytest.mark.tooling
def test_extract_text_target_and_short_hex_expansion() -> None:
    directive = extract_section_style_directive(
        "Ändra textfärgen i den markerade sektionen till #123."
    )
    assert directive == SectionStyleDirective(target="text", color_hex="#112233")


@pytest.mark.tooling
def test_extract_background_colour_word_via_lexicon() -> None:
    directive = extract_section_style_directive(
        "Gör bakgrunden i sektionen grön"
    )
    assert directive is not None
    assert directive.target == "background"
    assert directive.color_hex == "#16a34a"


@pytest.mark.tooling
def test_no_directive_without_section_reference() -> None:
    # Theme-level prompt — must keep flowing through the theme extractor.
    assert extract_section_style_directive("Byt bakgrundsfärg till #aabbcc") is None


@pytest.mark.tooling
def test_no_directive_without_explicit_colour_target() -> None:
    # "texten" alone is a copy edit, never a recolour target.
    assert (
        extract_section_style_directive(
            "Ändra texten i den markerade sektionen till grön energi"
        )
        is None
    )


@pytest.mark.tooling
def test_no_directive_without_colour() -> None:
    assert (
        extract_section_style_directive(
            "Gör bakgrunden i den markerade sektionen snyggare"
        )
        is None
    )


# --- apply -----------------------------------------------------------------


@pytest.mark.tooling
def test_apply_upserts_both_fields_on_same_key() -> None:
    project_input: dict[str, object] = {}
    apply_section_style_directive(
        project_input,
        SectionStyleDirective(target="background", color_hex="#aabbcc"),
        [{"routeId": "home", "sectionId": "hero"}],
    )
    apply_section_style_directive(
        project_input,
        SectionStyleDirective(target="text", color_hex="#112233"),
        [{"routeId": "home", "sectionId": "hero"}],
    )
    overrides = project_input["directives"]["sectionStyleOverrides"]
    assert overrides == [
        {
            "routeId": "home",
            "sectionId": "hero",
            "backgroundColorHex": "#aabbcc",
            "textColorHex": "#112233",
        }
    ]


@pytest.mark.tooling
def test_apply_without_markings_is_honest_no_op() -> None:
    project_input: dict[str, object] = {}
    applied = apply_section_style_directive(
        project_input,
        SectionStyleDirective(target="background", color_hex="#aabbcc"),
        [],
    )
    assert applied == []
    assert "directives" not in project_input


@pytest.mark.tooling
def test_apply_evicts_oldest_entry_at_cap() -> None:
    project_input: dict[str, object] = {
        "directives": {
            "sectionStyleOverrides": [
                {
                    "routeId": "home",
                    "sectionId": f"section-{index}",
                    "backgroundColorHex": "#000000",
                }
                for index in range(MAX_SECTION_STYLE_OVERRIDES)
            ]
        }
    }
    apply_section_style_directive(
        project_input,
        SectionStyleDirective(target="background", color_hex="#aabbcc"),
        [{"routeId": "home", "sectionId": "hero"}],
    )
    overrides = project_input["directives"]["sectionStyleOverrides"]
    assert len(overrides) == MAX_SECTION_STYLE_OVERRIDES
    assert overrides[0]["sectionId"] == "section-1"
    assert overrides[-1] == {
        "routeId": "home",
        "sectionId": "hero",
        "backgroundColorHex": "#aabbcc",
    }


# --- merge integration -----------------------------------------------------


@pytest.mark.tooling
def test_merge_applies_override_and_skips_theme_path() -> None:
    merged = _merge(
        _DIALOG_BACKGROUND_PROMPT,
        marked_sections=[{"routeId": "services", "sectionId": "service-list"}],
    )
    overrides = merged["directives"]["sectionStyleOverrides"]
    assert overrides == [
        {
            "routeId": "services",
            "sectionId": "service-list",
            "backgroundColorHex": "#aabbcc",
        }
    ]
    # Fas 2's untargeted-hex-defaults-to-primary rule must NOT also fire:
    # the section recolour short-circuits the theme path.
    assert "brand" not in merged or not (merged.get("brand") or {}).get(
        "primaryColorHex"
    )
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_merge_without_markings_is_honest_no_op_not_theme_change() -> None:
    # A prompt that explicitly says "sektionen" but arrives without a
    # validated marking (dropped by the facit check, or none sent) must
    # NOT fall through to the theme path — fas 2's untargeted-hex rule
    # would repaint the whole brand primary, which is the opposite of
    # what the operator asked for.
    merged = _merge(_DIALOG_BACKGROUND_PROMPT, marked_sections=None)
    assert "sectionStyleOverrides" not in (merged.get("directives") or {})
    assert not (merged.get("brand") or {}).get("primaryColorHex")
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_merge_preserves_overrides_across_versions() -> None:
    first = _merge(
        _DIALOG_BACKGROUND_PROMPT,
        marked_sections=[{"routeId": "home", "sectionId": "hero"}],
    )
    second = merge_followup_project_input(
        first,
        copy.deepcopy(first),
        follow_up_prompt="Lägg till en tjänst för stängselbygge.",
    )
    assert second["directives"]["sectionStyleOverrides"] == [
        {"routeId": "home", "sectionId": "hero", "backgroundColorHex": "#aabbcc"}
    ]
    _validate_against_schema(second)


@pytest.mark.tooling
def test_merge_text_prompt_sets_text_colour_field() -> None:
    merged = _merge(
        _DIALOG_TEXT_PROMPT,
        marked_sections=[{"routeId": "home", "sectionId": "hero"}],
    )
    assert merged["directives"]["sectionStyleOverrides"] == [
        {"routeId": "home", "sectionId": "hero", "textColorHex": "#112233"}
    ]
    _validate_against_schema(merged)


# --- CSS emission ----------------------------------------------------------


@pytest.mark.tooling
def test_css_emits_background_and_text_rules() -> None:
    css = _section_style_overrides_css(
        {
            "directives": {
                "sectionStyleOverrides": [
                    {
                        "routeId": "home",
                        "sectionId": "hero",
                        "backgroundColorHex": "#aabbcc",
                        "textColorHex": "#112233",
                    }
                ]
            }
        }
    )
    assert '[data-section-id="hero"] {' in css
    assert "background-color: #aabbcc !important;" in css
    assert "color: #112233 !important;" in css
    # Text rule scopes to headings/copy, never links/buttons.
    assert ":is(h1, h2, h3, h4, h5, h6, p, li, blockquote)" in css


@pytest.mark.tooling
def test_css_skips_invalid_entries() -> None:
    css = _section_style_overrides_css(
        {
            "directives": {
                "sectionStyleOverrides": [
                    {"routeId": "home", "sectionId": "Hero!", "backgroundColorHex": "#aabbcc"},
                    {"routeId": "home", "sectionId": "hero", "backgroundColorHex": "red"},
                    "not-a-dict",
                ]
            }
        }
    )
    assert css == ""
    assert _section_style_overrides_css(None) == ""
    assert _section_style_overrides_css({}) == ""
