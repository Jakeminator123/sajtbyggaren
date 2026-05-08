"""Tests for packages/generation/brief/extract.py.

Covers mock fallback (default in CI), error fallback (exception inside LLM call),
language detection, artifact serialisation including the briefSource truth field,
and a gated end-to-end test that only runs when SAJTBYGGAREN_E2E=1.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from packages.generation.brief import (
    BriefResult,
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
        target_audience=["lokala kunder"],
        page_count=5,
        tone=["trustworthy", "local"],
        requested_capabilities=["contact-form"],
        location_hint="Malmö",
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
    assert result.brief.location_hint == "Malmö"
    assert result.brief.conversion_goals == ["call", "quote-request"]


@pytest.mark.tooling
def test_site_brief_to_artifact_real_run():
    brief = SiteBrief(
        language="sv",
        business_type="electrician",
        target_audience=["husägare"],
        page_count=5,
        tone=["trustworthy"],
        requested_capabilities=["contact-form"],
        location_hint="Malmö",
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
    assert artifact["sourceModelRole"] == "briefModel"
    assert artifact["modelUsed"] == "gpt-5.4"
    assert artifact["_status"] == "real"
    assert artifact["briefSource"] == "real"
    assert artifact["briefError"] is None
    assert artifact["locationHint"] == "Malmö"
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
    assert artifact["_status"] == "mock-no-key"
    assert artifact["briefSource"] == "mock-no-key"
    assert artifact["businessTypeGuess"] is None


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
    assert artifact["_status"] == "mock-llm-error"
    assert artifact["briefSource"] == "mock-llm-error"
    assert artifact["briefError"] == "RuntimeError: boom"


@pytest.mark.tooling
def test_site_brief_pydantic_validates_required_fields():
    """language and raw_prompt are required."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SiteBrief(business_type="electrician")  # type: ignore[call-arg]


# E2E test gated on SAJTBYGGAREN_E2E=1 to avoid spending money in CI.
@pytest.mark.tooling
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
