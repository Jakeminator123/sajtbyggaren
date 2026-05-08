"""Builder Phase 1 Site Brief wiring tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from packages.generation.brief import BriefResult, SiteBrief

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.tooling
def test_builder_uses_brief_extractor_when_api_key_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts.build_site import build

    calls: list[dict[str, Any]] = []

    def fake_extract_site_brief(
        prompt: str,
        *,
        model: str,
        language_hint: str | None = None,
    ) -> BriefResult:
        calls.append(
            {
                "prompt": prompt,
                "model": model,
                "language_hint": language_hint,
            }
        )
        return BriefResult(
            brief=SiteBrief(
                language="sv",
                business_type="photo-studio",
                target_audience=["Göteborgskunder"],
                page_count=5,
                tone=["warm", "craft"],
                requested_capabilities=["booking"],
                location_hint="Göteborg",
                conversion_goals=["booking_request"],
                services_mentioned=["porträtt", "ramar"],
                content_depth="rich",
                raw_prompt=prompt,
                notes_for_planner="Fake structured brief for builder test.",
            ),
            source="real",
        )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(
        "packages.generation.brief.extract_site_brief",
        fake_extract_site_brief,
    )

    project_input_path = REPO_ROOT / "examples" / "foto-ram.project-input.json"
    _, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)

    assert len(calls) == 1
    assert calls[0]["model"] == "gpt-5.4"
    assert calls[0]["language_hint"] == "sv"
    assert "Norrljus Studio" in calls[0]["prompt"]
    assert "framing-service" in calls[0]["prompt"]

    brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    assert brief["briefSource"] == "real"
    assert brief["sourceModelRole"] == "briefModel"
    assert brief["modelUsed"] == "gpt-5.4"
    assert brief["businessTypeGuess"] == "photo-studio"
    assert brief["locationHint"] == "Göteborg"
    assert brief["scaffoldHint"] == "local-service-business"

    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert result["briefSource"] == "real"
    assert result["modelUsed"] == "gpt-5.4"
    assert result["modelUsage"]["source"] == "real"


@pytest.mark.tooling
def test_builder_falls_back_to_mock_when_brief_extractor_fails(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from scripts.build_site import build

    def fail_extract_site_brief(
        prompt: str,
        *,
        model: str,
        language_hint: str | None = None,
    ) -> BriefResult:
        raise RuntimeError("synthetic extractor failure")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(
        "packages.generation.brief.extract_site_brief",
        fail_extract_site_brief,
    )

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)

    brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    assert brief["briefSource"] == "mock-llm-error"
    assert brief["modelUsed"] == "mock"
    assert brief["sourceModelRole"] == "briefModel"
    assert brief["attemptedModel"] == "gpt-5.4"
    assert "synthetic extractor failure" in brief["briefError"]
    assert brief["companyName"] == "Målare i Palma"
    assert brief["requestedCapabilities"] == ["interactive-game"]

    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert result["briefSource"] == "mock-llm-error"
    assert result["modelUsed"] == "mock"
    assert result["modelUsage"]["source"] == "mock-llm-error"

    captured = capsys.readouterr()
    assert "briefModel path failed" in captured.err
    assert "mock Site Brief fallback" in captured.err


@pytest.mark.tooling
@pytest.mark.parametrize(
    "example_name",
    [
        "painter-palma.project-input.json",
        "arcade-hall.project-input.json",
        "foto-ram.project-input.json",
    ],
)
def test_builder_fallback_is_deterministic_for_examples(
    tmp_path: Path,
    monkeypatch,
    example_name: str,
) -> None:
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = REPO_ROOT / "examples" / example_name
    assert project_input_path.exists()

    _, first_run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "first",
    )
    _, second_run_dir = build(
        project_input_path,
        do_build=False,
        runs_dir=tmp_path / "second",
    )

    assert (first_run_dir / "site-brief.json").exists()
    first_brief = json.loads((first_run_dir / "site-brief.json").read_text(encoding="utf-8"))
    second_brief = json.loads((second_run_dir / "site-brief.json").read_text(encoding="utf-8"))
    assert first_brief == second_brief
    assert first_brief["briefSource"] == "mock-no-key"

    snapshot_files = [
        "generated-files/app/page.tsx",
        "generated-files/app/layout.tsx",
    ]
    for relative_path in snapshot_files:
        first_text = (first_run_dir / relative_path).read_text(encoding="utf-8")
        second_text = (second_run_dir / relative_path).read_text(encoding="utf-8")
        assert first_text == second_text

    first_result = json.loads((first_run_dir / "build-result.json").read_text(encoding="utf-8"))
    second_result = json.loads((second_run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert first_result["status"] == "skipped"
    assert second_result["status"] == "skipped"
