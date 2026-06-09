"""Tests for packages/generation/brief/extract.py.

Covers mock fallback (default in CI), error fallback (exception inside LLM call),
language detection, artifact serialisation including the briefSource truth field,
and a gated end-to-end test that only runs when SAJTBYGGAREN_E2E=1.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from packages.generation.artifacts import validate_site_brief
from packages.generation.brief import (
    BriefResult,
    BusinessFacts,
    ContentStrategy,
    Conversion,
    Positioning,
    SiteBrief,
    detect_language,
    extract_site_brief,
    site_brief_to_artifact,
)


@pytest.mark.tooling
def test_detect_language_swedish():
    assert detect_language("Skapa en hemsida för en elektriker i Malmö") == "sv"


@pytest.mark.tooling
def test_detect_language_english():
    assert detect_language("Build a website for a clinic in Boston") == "en"


# ---------------------------------------------------------------------------
# Demo-baseline-fix 1A-hotfix (B62): short Swedish prompts with no
# stop-word match used to fall through to the "en" default and generate
# fully English customer copy. The cascading heuristic now leans Swedish
# whenever (a) any token contains å/ä/ö, or (b) the prompt has no
# English stop-word match either (operator population is ~95% Swedish).
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "frisör Göteborg",
        "naprapatklinik Stockholm",
        "Skapa en hemsida för Volt & Co",
        "elektriker Malmö",
        "tandläkarpraktik",
        "yoga",
    ],
)
def test_detect_language_short_swedish_prompts_default_to_sv(prompt: str):
    """B62: short prompts without SWEDISH_HINTS stop-words must still
    resolve to "sv" so the rendered site stays in the prompt language.
    """
    assert detect_language(prompt) == "sv", (
        f"B62 regression: prompt {prompt!r} resolved to non-Swedish; "
        "the 1A-hotfix cascading heuristic must default to sv when no "
        "English stop-word matches."
    )


@pytest.mark.tooling
@pytest.mark.parametrize(
    "prompt",
    [
        "electrician website in Malmö",
        "build a small site for a clinic",
        "create a shop with checkout",
        "make a portfolio page for a photographer",
    ],
)
def test_detect_language_english_prompts_with_swedish_chars_stay_en(
    prompt: str,
):
    """B62: English prompts that mention Swedish characters in a city
    name must NOT be misclassified as Swedish. The cascade puts
    ENGLISH_HINTS BEFORE the å/ä/ö check so this prompt stays "en".
    """
    assert detect_language(prompt) == "en", (
        f"B62 regression: English prompt {prompt!r} resolved to sv; "
        "the cascading heuristic must check ENGLISH_HINTS before falling "
        "back to the å/ä/ö signal."
    )


@pytest.mark.tooling
def test_extract_site_brief_returns_mock_when_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = extract_site_brief("Skapa en hemsida för en elektriker i Malmö")
    assert isinstance(result, BriefResult)
    assert result.source == "mock-no-key"
    assert result.error is None
    brief = result.brief
    assert isinstance(brief, SiteBrief)
    assert brief.language == "sv"
    assert brief.raw_prompt.startswith("Skapa")
    # Default fields should be the empty-list / None defaults defined on the model.
    assert brief.conversion_goals == []
    assert brief.services_mentioned == []
    assert brief.content_depth is None


@pytest.mark.tooling
def test_extract_site_brief_falls_back_when_llm_raises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    with patch(
        "packages.generation.brief.extract._real_brief",
        side_effect=RuntimeError("boom"),
    ):
        result = extract_site_brief("Build a clinic site")
    assert result.source == "mock-llm-error"
    assert result.error is not None
    assert "RuntimeError" in result.error
    assert "boom" in result.error
    brief = result.brief
    assert isinstance(brief, SiteBrief)
    assert brief.language == "en"
    assert brief.notes_for_planner is not None
    assert "boom" in brief.notes_for_planner or "RuntimeError" in brief.notes_for_planner


@pytest.mark.tooling
def test_extract_site_brief_uses_real_path_when_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")

    fake_brief = SiteBrief(
        language="sv",
        business_type="electrician",
        company_name="Volt & Co",
        target_audience=["lokala kunder"],
        page_count=5,
        tone=["trustworthy", "local"],
        requested_capabilities=["contact-form"],
        location_hint="Malmö",
        contact_phone="0701234567",
        contact_email="hej@voltco.se",
        contact_address="Storgatan 1, 211 22 Malmö",
        conversion_goals=["call", "quote-request"],
        services_mentioned=["paneldragning", "laddbox-installation"],
        content_depth="rich",
        raw_prompt="Skapa en hemsida för en elektriker i Malmö",
        notes_for_planner="Test brief from mock",
    )

    with patch(
        "packages.generation.brief.extract._real_brief",
        return_value=fake_brief,
    ) as call:
        result = extract_site_brief(
            "Skapa en hemsida för en elektriker i Malmö",
            model="gpt-5.4",
        )

    call.assert_called_once()
    assert result.source == "real"
    assert result.error is None
    assert result.brief.business_type == "electrician"
    assert result.brief.company_name == "Volt & Co"
    assert result.brief.location_hint == "Malmö"
    assert result.brief.contact_phone == "0701234567"
    assert result.brief.conversion_goals == ["call", "quote-request"]


# ---------------------------------------------------------------------------
# ADR 0022-style opening-hours extraction (S3 Fas 1). A free prompt that
# states opening hours ("öppet tisdag–söndag 07–16") must carry them through
# the brief into the artefakt; a prompt without them must keep the field null
# (Fas 1 never invents hours). The real LLM extraction itself is not exercised
# here - the briefModel call is mocked via _real_brief, mirroring
# test_extract_site_brief_uses_real_path_when_key_set above so the test stays
# offline (no live OPENAI call).
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_extract_site_brief_carries_opening_hours_when_prompt_states_them(
    monkeypatch,
):
    """Med-öppettid-fallet: when the (mocked) briefModel extracts opening
    hours, they survive into the brief and the serialised artefakt.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    prompt = "Skapa en hemsida för ett bageri, öppet tisdag–söndag 07–16"
    fake_brief = SiteBrief(
        language="sv",
        business_type="bakery",
        raw_prompt=prompt,
        contact_opening_hours="tisdag–söndag 07–16",
    )

    with patch(
        "packages.generation.brief.extract._real_brief",
        return_value=fake_brief,
    ):
        result = extract_site_brief(prompt)

    assert result.source == "real"
    assert result.brief.contact_opening_hours == "tisdag–söndag 07–16"
    artifact = site_brief_to_artifact(result, run_id="run-oh", model="gpt-5.4")
    assert artifact["contactOpeningHours"] == "tisdag–söndag 07–16"


@pytest.mark.tooling
def test_extract_site_brief_opening_hours_null_when_prompt_omits_them(
    monkeypatch,
):
    """Utan-öppettid-fallet: a prompt that never mentions hours leaves
    contact_opening_hours None - the field is never invented.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = extract_site_brief("Skapa en hemsida för ett bageri")
    assert result.source == "mock-no-key"
    assert result.brief.contact_opening_hours is None
    artifact = site_brief_to_artifact(result, run_id="run-noh", model="gpt-5.4")
    assert artifact["contactOpeningHours"] is None


@pytest.mark.tooling
def test_site_brief_to_artifact_real_run():
    brief = SiteBrief(
        language="sv",
        business_type="electrician",
        company_name="Volt & Co",
        target_audience=["husägare"],
        page_count=5,
        tone=["trustworthy"],
        requested_capabilities=["contact-form"],
        location_hint="Malmö",
        contact_phone="0701234567",
        contact_email="hej@voltco.se",
        contact_address="Storgatan 1, 211 22 Malmö",
        contact_opening_hours="mån-fre 08-17",
        conversion_goals=["call"],
        services_mentioned=["akut-elservice"],
        content_depth="medium",
        raw_prompt="Skapa en hemsida för en elektriker i Malmö",
        notes_for_planner="ok",
    )
    result = BriefResult(brief=brief, source="real")
    artifact = site_brief_to_artifact(result, run_id="2026-05-07T00-00-00Z-aaaaaa", model="gpt-5.4")
    assert artifact["runId"].startswith("2026-")
    assert artifact["language"] == "sv"
    assert artifact["businessTypeGuess"] == "electrician"
    assert artifact["companyName"] == "Volt & Co"
    assert artifact["sourceModelRole"] == "briefModel"
    assert artifact["modelUsed"] == "gpt-5.4"
    assert artifact["briefSource"] == "real"
    assert artifact["briefError"] is None
    assert artifact["locationHint"] == "Malmö"
    assert artifact["contactPhone"] == "0701234567"
    assert artifact["contactEmail"] == "hej@voltco.se"
    assert artifact["contactAddress"] == "Storgatan 1, 211 22 Malmö"
    assert artifact["contactOpeningHours"] == "mån-fre 08-17"
    assert artifact["requestedCapabilities"] == ["contact-form"]
    assert artifact["conversionGoals"] == ["call"]
    assert artifact["servicesMentioned"] == ["akut-elservice"]
    assert artifact["contentDepth"] == "medium"


@pytest.mark.tooling
def test_site_brief_to_artifact_mock_no_key():
    brief = SiteBrief(language="en", business_type=None, raw_prompt="Build a website")
    result = BriefResult(brief=brief, source="mock-no-key")
    artifact = site_brief_to_artifact(result, run_id="run-x", model="gpt-5.4")
    assert artifact["modelUsed"] == "mock"
    assert artifact["briefSource"] == "mock-no-key"
    assert artifact["businessTypeGuess"] is None
    assert artifact["companyName"] is None
    assert artifact["contactPhone"] is None
    assert artifact["contactEmail"] is None
    assert artifact["contactAddress"] is None
    assert artifact["contactOpeningHours"] is None


@pytest.mark.tooling
def test_site_brief_to_artifact_mock_llm_error():
    """Artifact must NOT claim 'real' when LLM raised and we fell back to mock."""
    brief = SiteBrief(language="sv", raw_prompt="Skapa hemsida")
    result = BriefResult(
        brief=brief,
        source="mock-llm-error",
        error="RuntimeError: boom",
    )
    artifact = site_brief_to_artifact(result, run_id="run-y", model="gpt-5.4")
    assert artifact["modelUsed"] == "mock"
    assert artifact["briefSource"] == "mock-llm-error"
    assert artifact["briefError"] == "RuntimeError: boom"


@pytest.mark.tooling
def test_site_brief_pydantic_validates_required_fields():
    """language and raw_prompt are required."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SiteBrief(business_type="electrician")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# KÖR-1b: briefModel fills the blueprint fields (businessFacts, positioning,
# contentStrategy, conversion) with an honest mock fallback. DoD:
#  - the four baseline prompts yield clearly different positioning;
#  - missing contact/cert lands in businessFacts.unknowns, never invented copy;
#  - without a key the mock-no-key contract is unchanged AND the serialised
#    artefakt (now carrying the blueprint) still validates;
#  - blueprint serialises to camelCase, additive to the existing conversionGoals.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "blueprints"
BASELINE_BRANCHES = [
    "elektriker-malmo",
    "frisor-goteborg",
    "naprapat-stockholm",
    "keramik-ehandel",
]


def _baseline_prompt(branch: str) -> str:
    """The canonical rawPrompt for a baseline branch (kor-1a fixture)."""
    fixture = json.loads(
        (BLUEPRINT_FIXTURES / f"{branch}.blueprint.json").read_text(encoding="utf-8")
    )
    return fixture["siteBrief"]["rawPrompt"]


@pytest.mark.tooling
def test_mock_blueprint_four_baselines_have_distinct_positioning(monkeypatch):
    """DoD: the four baseline prompts give clearly different
    positioning.oneLiner / differentiator (offline, via the mock)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    one_liners: list[str] = []
    differentiators: list[str] = []
    for branch in BASELINE_BRANCHES:
        result = extract_site_brief(_baseline_prompt(branch))
        assert result.source == "mock-no-key"
        positioning = result.brief.positioning
        assert positioning is not None
        assert positioning.one_liner and positioning.one_liner.strip()
        assert positioning.differentiator and positioning.differentiator.strip()
        one_liners.append(positioning.one_liner)
        differentiators.append(positioning.differentiator)
    assert len(set(one_liners)) == len(BASELINE_BRANCHES), one_liners
    assert len(set(differentiators)) == len(BASELINE_BRANCHES), differentiators


@pytest.mark.tooling
def test_mock_blueprint_puts_missing_contact_and_cert_in_unknowns(monkeypatch):
    """DoD: a prompt that states no phone/certifications puts them in
    businessFacts.unknowns and never fabricates them as copy."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    brief = extract_site_brief(_baseline_prompt("elektriker-malmo")).brief

    # The mock never invents contact details.
    assert brief.contact_phone is None
    assert brief.contact_email is None
    assert brief.contact_address is None

    unknowns = brief.business_facts.unknowns
    assert "telefonnummer" in unknowns
    assert "certifieringar" in unknowns

    # Honesty guard: no blueprint copy carries a phone-shaped digit run or a
    # placeholder contact - an unknown must never surface as invented copy.
    copy_blob = " ".join(
        filter(
            None,
            [
                brief.positioning.one_liner,
                brief.positioning.differentiator,
                brief.positioning.local_angle,
                brief.content_strategy.hero_angle,
                brief.conversion.primary_cta,
                brief.conversion.secondary_cta,
            ],
        )
    )
    assert not re.search(r"\d{3,}", copy_blob), copy_blob
    assert "example" not in copy_blob.lower()


@pytest.mark.tooling
def test_mock_no_key_contract_includes_valid_blueprint(monkeypatch):
    """DoD: without a key the source contract is identical (mock-no-key) AND
    the serialised artefakt - now carrying the blueprint - still validates
    against site-brief.schema.json (the dev_generate.py write path)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = extract_site_brief(_baseline_prompt("frisor-goteborg"))
    assert result.source == "mock-no-key"
    assert result.error is None

    brief = result.brief
    assert isinstance(brief.business_facts, BusinessFacts)
    assert isinstance(brief.positioning, Positioning)
    assert isinstance(brief.content_strategy, ContentStrategy)
    assert isinstance(brief.conversion, Conversion)

    artifact = site_brief_to_artifact(result, run_id="run-bp", model="gpt-5.4")
    assert artifact["briefSource"] == "mock-no-key"
    assert artifact["modelUsed"] == "mock"
    # Blueprint emitted in camelCase, additive to the legacy conversionGoals.
    assert artifact["businessFacts"]["unknowns"]
    assert artifact["positioning"]["oneLiner"]
    assert artifact["contentStrategy"]["avoidGenericClaims"] is True
    assert artifact["conversion"]["primaryCta"]
    assert artifact["conversionGoals"] == []
    validate_site_brief(artifact)


@pytest.mark.tooling
def test_mock_blueprint_is_byte_deterministic(monkeypatch):
    """The mock blueprint is a pure function of the prompt, so the
    deterministic-fallback contract holds (everything but createdAt is stable)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt = _baseline_prompt("naprapat-stockholm")
    first = site_brief_to_artifact(
        extract_site_brief(prompt), run_id="r", model="gpt-5.4"
    )
    second = site_brief_to_artifact(
        extract_site_brief(prompt), run_id="r", model="gpt-5.4"
    )
    volatile = {"createdAt"}
    assert {k: v for k, v in first.items() if k not in volatile} == {
        k: v for k, v in second.items() if k not in volatile
    }


@pytest.mark.tooling
def test_site_brief_to_artifact_serialises_blueprint_camelcase():
    """A real-path brief carrying blueprint models serialises to the camelCase
    schema shape, additive to conversionGoals, and validates."""
    brief = SiteBrief(
        language="sv",
        raw_prompt="Skapa en hemsida för en elektriker i Malmö",
        conversion_goals=["call"],
        business_facts=BusinessFacts(
            facts=["verksam i Malmö"], unknowns=["telefonnummer"]
        ),
        positioning=Positioning(
            one_liner="Elektriker i Malmö.",
            differentiator="lokal och trygg",
            avoid=["påhittade certifieringar"],
        ),
        content_strategy=ContentStrategy(
            hero_angle="trygg elektriker", avoid_generic_claims=True
        ),
        conversion=Conversion(
            primary_action="request_quote",
            primary_cta="Be om offert",
            contact_priority=["phone_if_real", "form"],
            cta_rules=["visa inte telefon om telefon saknas"],
        ),
    )
    artifact = site_brief_to_artifact(
        BriefResult(brief=brief, source="real"), run_id="run-z", model="gpt-5.4"
    )
    assert artifact["businessFacts"] == {
        "facts": ["verksam i Malmö"],
        "unknowns": ["telefonnummer"],
    }
    assert artifact["positioning"]["oneLiner"] == "Elektriker i Malmö."
    assert artifact["positioning"]["avoid"] == ["påhittade certifieringar"]
    assert artifact["contentStrategy"]["avoidGenericClaims"] is True
    assert artifact["conversion"]["primaryAction"] == "request_quote"
    assert artifact["conversion"]["contactPriority"] == ["phone_if_real", "form"]
    # Additive: blueprint conversion lives alongside the legacy conversionGoals.
    assert artifact["conversionGoals"] == ["call"]
    validate_site_brief(artifact)


@pytest.mark.tooling
def test_site_brief_to_artifact_omits_blueprint_when_absent():
    """Backward-compat: a brief without blueprint models emits no blueprint
    keys (never null) and still validates - the additive kor-1a contract."""
    brief = SiteBrief(language="sv", raw_prompt="Skapa hemsida")
    artifact = site_brief_to_artifact(
        BriefResult(brief=brief, source="mock-no-key"),
        run_id="run-q",
        model="gpt-5.4",
    )
    for key in ("businessFacts", "positioning", "contentStrategy", "conversion"):
        assert key not in artifact
    validate_site_brief(artifact)


# E2E test gated on SAJTBYGGAREN_E2E=1 to avoid spending money in CI.
@pytest.mark.tooling
@pytest.mark.e2e
@pytest.mark.skipif(
    os.environ.get("SAJTBYGGAREN_E2E") != "1" or not os.environ.get("OPENAI_API_KEY"),
    reason="SAJTBYGGAREN_E2E=1 and OPENAI_API_KEY required for real LLM call",
)
def test_extract_site_brief_e2e_real_call():
    result = extract_site_brief(
        "Skapa en hemsida för en elektriker i Malmö",
        model="gpt-5.4",
    )
    assert result.source == "real"
    assert isinstance(result.brief, SiteBrief)
    assert result.brief.language == "sv"
    assert result.brief.raw_prompt
