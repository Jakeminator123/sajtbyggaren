"""Tests for packages/generation/brief/extract.py.

Covers mock fallback (default in CI), error fallback (exception inside LLM call),
language detection, artifact serialization, and a gated end-to-end test that only
runs when SAJTBYGGAREN_E2E=1 (used by operators with a real OPENAI_API_KEY).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from packages.generation.brief import (
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
    brief = extract_site_brief("Skapa en hemsida för en elektriker i Malmö")
    assert isinstance(brief, SiteBrief)
    assert brief.language == "sv"
    assert brief.raw_prompt.startswith("Skapa")
    assert brief.notes_for_planner is not None
    assert "mock" in brief.notes_for_planner.lower() or "OPENAI" in brief.notes_for_planner


@pytest.mark.tooling
def test_extract_site_brief_falls_back_when_llm_raises(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    with patch("packages.generation.brief.extract._real_brief", side_effect=RuntimeError("boom")):
        brief = extract_site_brief("Build a clinic site")
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
        raw_prompt="Skapa en hemsida för en elektriker i Malmö",
        notes_for_planner="Test brief from mock",
    )

    with patch(
        "packages.generation.brief.extract._real_brief",
        return_value=fake_brief,
    ) as call:
        brief = extract_site_brief(
            "Skapa en hemsida för en elektriker i Malmö",
            model="gpt-5.4",
        )

    call.assert_called_once()
    assert brief.business_type == "electrician"
    assert brief.location_hint == "Malmö"


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
        raw_prompt="Skapa en hemsida för en elektriker i Malmö",
        notes_for_planner="ok",
    )
    artifact = site_brief_to_artifact(
        brief, run_id="2026-05-07T00-00-00Z-aaaaaa", model="gpt-5.4", used_real_llm=True
    )
    assert artifact["runId"].startswith("2026-")
    assert artifact["language"] == "sv"
    assert artifact["businessTypeGuess"] == "electrician"
    assert artifact["sourceModelRole"] == "briefModel"
    assert artifact["modelUsed"] == "gpt-5.4"
    assert artifact["_status"] == "real"
    assert artifact["locationHint"] == "Malmö"
    assert artifact["requestedCapabilities"] == ["contact-form"]


@pytest.mark.tooling
def test_site_brief_to_artifact_mock_run():
    brief = SiteBrief(
        language="en",
        business_type=None,
        raw_prompt="Build a website",
    )
    artifact = site_brief_to_artifact(
        brief, run_id="run-x", model="gpt-5.4", used_real_llm=False
    )
    assert artifact["modelUsed"] == "mock"
    assert artifact["_status"].startswith("mock")
    assert artifact["businessTypeGuess"] is None


@pytest.mark.tooling
def test_site_brief_pydantic_validates_required_fields():
    """language and raw_prompt are required."""
    with pytest.raises(Exception):
        SiteBrief(business_type="electrician")  # type: ignore[call-arg]


# E2E test gated on SAJTBYGGAREN_E2E=1 to avoid spending money in CI.
@pytest.mark.tooling
@pytest.mark.skipif(
    os.environ.get("SAJTBYGGAREN_E2E") != "1" or not os.environ.get("OPENAI_API_KEY"),
    reason="SAJTBYGGAREN_E2E=1 and OPENAI_API_KEY required for real LLM call",
)
def test_extract_site_brief_e2e_real_call():
    brief = extract_site_brief(
        "Skapa en hemsida för en elektriker i Malmö",
        model="gpt-5.4",
    )
    assert isinstance(brief, SiteBrief)
    assert brief.language == "sv"
    assert brief.raw_prompt
    # We don't assert on business_type because the LLM may legitimately leave it null.
