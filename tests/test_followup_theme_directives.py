"""Coverage for the visual_style follow-up slice (theme directives).

Before this slice, a follow-up like "gör färgen rosa och typsnittet snyggt" was
a silent no-op: the copyDirective path only touches text targets and the KÖR-7
patch planner only handles component_add/copy_change. These tests lock the
deterministic, schema-safe theme extractor + apply path:

- a colour word maps to ``brand.primaryColorHex`` (rendered as ``--primary``),
- a font/style vibe maps to ``tone.primary`` (rendered via ``_TONE_TYPOGRAPHY``),
- a bare "ändra typsnittet" gets a tasteful default vibe (not a no-op),
- non-theme follow-ups produce no directive (the honest no-op path still fires),
- the merged Project Input stays schema-valid.
"""

from __future__ import annotations

import copy

import pytest

from packages.generation.followup.theme_directives import (
    apply_theme_directive,
    extract_theme_directive,
)
from scripts.prompt_to_project_input import (
    _theme_directive_llm_eligible,
    _validate_against_schema,
    merge_followup_project_input,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core


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


def _merge(prompt: str, previous: dict[str, object] | None = None) -> dict[str, object]:
    previous = previous or _previous_project_input()
    return merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt=prompt,
    )


# --- extraction ------------------------------------------------------------


@pytest.mark.tooling
def test_extract_color_and_font_from_operator_case() -> None:
    directive = extract_theme_directive("gör typsnittet rosa och svinsnyggt")
    assert directive is not None
    assert directive.primaryColorHex == "#db2777"
    assert directive.colorWord == "rosa"
    assert directive.toneVibe == "editorial"
    assert directive.vibeWord == "svinsnyggt"


@pytest.mark.tooling
def test_extract_color_only() -> None:
    directive = extract_theme_directive("måla allt blått tack")
    assert directive is not None
    assert directive.primaryColorHex == "#2563eb"
    assert directive.toneVibe is None


@pytest.mark.tooling
def test_extract_font_trigger_without_vibe_uses_default() -> None:
    directive = extract_theme_directive("byt typsnitt på sidan")
    assert directive is not None
    assert directive.primaryColorHex is None
    assert directive.toneVibe == "editorial"


@pytest.mark.tooling
def test_extract_vibe_word_without_font_trigger() -> None:
    directive = extract_theme_directive("gör det lite mer lekfullt")
    assert directive is not None
    assert directive.toneVibe == "playful"
    assert directive.primaryColorHex is None


@pytest.mark.tooling
def test_specific_colour_word_wins_over_substring() -> None:
    # "marinblå" must not be reduced to "blå".
    directive = extract_theme_directive("gör den marinblå")
    assert directive is not None
    assert directive.primaryColorHex == "#1e3a8a"
    assert directive.colorWord == "marinblå"


@pytest.mark.tooling
def test_two_colours_set_primary_and_accent_in_order() -> None:
    directive = extract_theme_directive("gör den rosa och blå")
    assert directive is not None
    assert directive.primaryColorHex == "#db2777"
    assert directive.colorWord == "rosa"
    assert directive.accentColorHex == "#2563eb"
    assert directive.accentWord == "blå"


@pytest.mark.tooling
def test_duplicate_colour_synonyms_do_not_become_accent() -> None:
    # "rosa" and "pink" share a hex -> only one colour, no accent.
    directive = extract_theme_directive("gör den rosa, alltså pink")
    assert directive is not None
    assert directive.primaryColorHex == "#db2777"
    assert directive.accentColorHex is None


# --- literal hex extraction (colour-tools dialog, 2026-06-11) ---------------
# The viewser colour dialog emits "Ändra sajtens primärfärg till #rrggbb." —
# previously only understood via the styleDirectiveModel LLM fallback, so the
# dialog was a silent no-op without an OPENAI_API_KEY. These lock the
# deterministic hex path.


@pytest.mark.tooling
def test_extract_primary_hex_literal_deterministically() -> None:
    directive = extract_theme_directive(
        "Ändra sajtens primärfärg till #2D5F3F. Behåll övrig design intakt."
    )
    assert directive is not None
    assert directive.primaryColorHex == "#2d5f3f"
    assert directive.colorWord == "#2d5f3f"
    assert directive.accentColorHex is None


@pytest.mark.tooling
def test_extract_accent_hex_literal_stands_alone() -> None:
    directive = extract_theme_directive(
        "Ändra sajtens accentfärg till #B45309. Behåll övrig design intakt."
    )
    assert directive is not None
    assert directive.primaryColorHex is None
    assert directive.accentColorHex == "#b45309"
    assert directive.accentWord == "#b45309"


@pytest.mark.tooling
def test_extract_both_hex_literals_by_nearest_target_word() -> None:
    directive = extract_theme_directive(
        "Ändra primärfärgen till #112233 och accentfärgen till #aabbcc."
    )
    assert directive is not None
    assert directive.primaryColorHex == "#112233"
    assert directive.accentColorHex == "#aabbcc"


@pytest.mark.tooling
def test_extract_untargeted_hex_defaults_to_primary() -> None:
    directive = extract_theme_directive("byt färg till #abc")
    assert directive is not None
    # #rgb expands to #rrggbb.
    assert directive.primaryColorHex == "#aabbcc"
    assert directive.accentColorHex is None


@pytest.mark.tooling
def test_hex_literal_wins_over_colour_word_for_same_slot() -> None:
    directive = extract_theme_directive(
        "gör den blå, närmare bestämt primärfärg #2d5f3f"
    )
    assert directive is not None
    assert directive.primaryColorHex == "#2d5f3f"


@pytest.mark.tooling
def test_invalid_hex_lengths_are_ignored() -> None:
    # 4/5/8-siffriga "hex" är inte giltiga tokens — ingen träff, inget direktiv.
    assert extract_theme_directive("byt färg till #abcd") is None
    assert extract_theme_directive("byt färg till #aabbccdd") is None


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "byt namnet i headern till Getgården AB",
        "lägg till en kontaktknapp",
        "skriv om om-oss-texten",
        "lägg till en sida för priser",
    ],
)
def test_non_theme_followups_are_noop(prompt: str) -> None:
    assert extract_theme_directive(prompt) is None


@pytest.mark.tooling
def test_empty_prompt_is_noop() -> None:
    assert extract_theme_directive("") is None
    assert extract_theme_directive("   ") is None


# --- apply -----------------------------------------------------------------


@pytest.mark.tooling
def test_apply_sets_brand_and_tone_without_clobbering_other_brand_fields() -> None:
    project_input: dict[str, object] = {"brand": {"logoText": "GG"}, "tone": {"primary": "calm", "secondary": []}}
    directive = extract_theme_directive("gör färgen rosa och typsnittet snyggt")
    changed = apply_theme_directive(project_input, directive)
    assert changed is True
    brand = project_input["brand"]
    assert isinstance(brand, dict)
    assert brand["primaryColorHex"] == "#db2777"
    assert brand["logoText"] == "GG"  # preserved
    tone = project_input["tone"]
    assert isinstance(tone, dict)
    assert tone["primary"] == "editorial"
    assert tone["secondary"] == []  # preserved


@pytest.mark.tooling
def test_apply_creates_brand_when_absent() -> None:
    project_input: dict[str, object] = {}
    directive = extract_theme_directive("måla allt grönt")
    assert apply_theme_directive(project_input, directive) is True
    brand = project_input["brand"]
    assert isinstance(brand, dict)
    assert brand["primaryColorHex"] == "#16a34a"


@pytest.mark.tooling
def test_apply_sets_accent_color() -> None:
    project_input: dict[str, object] = {}
    directive = extract_theme_directive("rosa och mint")
    assert apply_theme_directive(project_input, directive) is True
    brand = project_input["brand"]
    assert isinstance(brand, dict)
    assert brand["primaryColorHex"] == "#db2777"
    assert brand["accentColorHex"] == "#10b981"


@pytest.mark.tooling
def test_apply_none_directive_is_noop() -> None:
    project_input: dict[str, object] = {"brand": {"logoText": "GG"}}
    assert apply_theme_directive(project_input, None) is False
    assert project_input == {"brand": {"logoText": "GG"}}


# --- integration via merge_followup_project_input --------------------------


@pytest.mark.tooling
def test_merge_applies_theme_and_stays_schema_valid() -> None:
    merged = _merge("gör färgen rosa och typsnittet svinsnyggt")
    brand = merged.get("brand")
    assert isinstance(brand, dict)
    assert brand["primaryColorHex"] == "#db2777"
    tone = merged.get("tone")
    assert isinstance(tone, dict)
    assert tone["primary"] == "editorial"
    # Must remain a valid Project Input after the restyle.
    _validate_against_schema(merged)


@pytest.mark.tooling
def test_merge_non_theme_followup_leaves_theme_untouched() -> None:
    previous = _previous_project_input()
    merged = _merge("lägg till en kontaktknapp", previous=previous)
    # No theme intent -> brand stays absent, tone.primary unchanged.
    assert "primaryColorHex" not in (merged.get("brand") or {})
    assert (merged.get("tone") or {}).get("primary") == "trustworthy"


# --- 2026-06-08 stylist slice: compound colours + accent (central lexicon) ---
#
# A free/compound colour expression ("grönvit"/"svartvit"/"blå och vit") must
# resolve to a primary + accent without exact single-word keywords, the white
# half landing as the accent (never a near-white primary). "korall" and the
# other lexicon colours resolve too. A model-driven fallback (the stylist role)
# interprets unknown free expressions into the SAME validated ThemeDirective.


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt,primary,accent",
    [
        ("gör sajten grönvit", "#16a34a", "#ffffff"),
        ("gör den svartvit", "#171717", "#ffffff"),
        ("jag vill ha det blåvitt", "#2563eb", "#ffffff"),
    ],
)
def test_extract_compound_colour_sets_primary_and_white_accent(
    prompt: str, primary: str, accent: str
) -> None:
    directive = extract_theme_directive(prompt)
    assert directive is not None
    assert directive.primaryColorHex == primary
    assert directive.accentColorHex == accent


@pytest.mark.tooling
def test_extract_two_word_colour_with_white_accent() -> None:
    """A light/neutral word (white) only fills the ACCENT slot, alongside a
    contrast-safe primary - it is never the primary on its own."""
    directive = extract_theme_directive("gör den blå och vit")
    assert directive is not None
    assert directive.primaryColorHex == "#2563eb"
    assert directive.accentColorHex == "#ffffff"


@pytest.mark.tooling
def test_extract_korall_colour() -> None:
    directive = extract_theme_directive("gör färgen korall")
    assert directive is not None
    assert directive.primaryColorHex == "#f43f5e"


@pytest.mark.tooling
def test_bare_white_alone_is_no_op() -> None:
    """A near-white primary breaks contrast, so a bare 'vit' yields no primary
    (honest no-op) rather than a near-white brand colour."""
    assert extract_theme_directive("gör den vit") is None


@pytest.mark.tooling
def test_compound_colour_is_schema_valid_after_merge() -> None:
    merged = _merge("gör sajten grönvit")
    brand = merged.get("brand")
    assert isinstance(brand, dict)
    assert brand["primaryColorHex"] == "#16a34a"
    assert brand["accentColorHex"] == "#ffffff"
    _validate_against_schema(merged)


# --- stylist role: model-driven fallback (parallel to the copyDirective A1) ---


def _merge_with_llm(prompt: str) -> dict[str, object]:
    previous = _previous_project_input()
    return merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt=prompt,
        enable_llm_fallback=True,
    )


@pytest.mark.tooling
def test_style_model_fallback_resolves_free_expression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A free style expression the deterministic lexicon misses is interpreted
    by styleDirectiveModel into a validated theme mutation (hex + known vibe)."""
    prompt = "gör sajten i varma höstfärger"
    assert extract_theme_directive(prompt) is None  # deterministic miss
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_style_directive_llm",
        lambda *a, **k: {"primaryColorHex": "#b45309", "toneVibe": "calm"},
    )
    merged = _merge_with_llm(prompt)
    assert merged["brand"]["primaryColorHex"] == "#b45309"
    assert merged["tone"]["primary"] == "calm"


@pytest.mark.tooling
def test_style_model_fallback_rejects_garbage_hex_and_vibe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation/honesty: a non-hex colour or unknown vibe from the model is
    dropped, leaving an honest no-op (no fabricated restyle)."""
    prompt = "gör om hela färgkänslan"
    assert extract_theme_directive(prompt) is None
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_style_directive_llm",
        lambda *a, **k: {"primaryColorHex": "skyblue", "toneVibe": "not-a-vibe"},
    )
    merged = _merge_with_llm(prompt)
    assert "primaryColorHex" not in (merged.get("brand") or {})
    assert (merged.get("tone") or {}).get("primary") == "trustworthy"


@pytest.mark.tooling
def test_style_model_fallback_lone_accent_without_primary_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model that returns only a light accent (no primary, no vibe) is a
    no-op - a lone near-white accent could break contrast."""
    prompt = "gör om temat lite"
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_style_directive_llm",
        lambda *a, **k: {"accentColorHex": "#ffffff"},
    )
    merged = _merge_with_llm(prompt)
    assert "primaryColorHex" not in (merged.get("brand") or {})
    assert "accentColorHex" not in (merged.get("brand") or {})


@pytest.mark.tooling
def test_style_model_fallback_only_runs_when_llm_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the opt-in flag the model is never consulted (offline parity)."""
    called = {"n": 0}

    def _spy(*a: object, **k: object) -> dict[str, str]:
        called["n"] += 1
        return {"primaryColorHex": "#db2777"}

    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_style_directive_llm", _spy
    )
    previous = _previous_project_input()
    merged = merge_followup_project_input(
        previous,
        copy.deepcopy(previous),
        follow_up_prompt="gör sajten i höstfärger",
    )
    assert called["n"] == 0
    assert "primaryColorHex" not in (merged.get("brand") or {})


# --- stylist eligibility gate (fix-1 honesty mirrored into the prompt path) ---


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt,expected",
    [
        # free style expressions carry a visual cue -> eligible
        ("gör sajten i höstfärger", True),
        ("ändra färgkänslan", True),
        ("gör om hela stilen", True),
        ("snygga till paletten", True),
        # fix-1: a bare colour / question with no style cue -> never asks
        ("vad betyder rosa", False),
        ("rosa", False),
        # add-only requests never restyle, even with a colour cue word
        ("lägg till en blå knapp", False),
        ("lägg till en sektion om färger", False),
    ],
)
def test_theme_directive_llm_eligible_gate(prompt: str, expected: bool) -> None:
    assert _theme_directive_llm_eligible(prompt) is expected
