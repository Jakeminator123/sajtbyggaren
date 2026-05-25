"""Tests for scripts/run_golden_path_eval.py."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.tooling
def test_golden_path_eval_writes_all_four_cases_without_llm_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default mode writes JSON/Markdown and does not use OPENAI_API_KEY."""

    from scripts.run_golden_path_eval import (
        BASELINE_CASES,
        OPENAI_API_KEY_ENV,
        TRAIT_DEFINITIONS,
        run_golden_path_eval,
    )

    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-not-used")

    summary = run_golden_path_eval(
        mode="deterministic",
        evals_dir=tmp_path,
        eval_id="golden-contract",
    )

    assert summary["caseCount"] == 4
    assert summary["deterministicOffline"] is True
    assert summary["llmKeyRequired"] is False
    assert summary["thresholds"] == {
        "averageScoreGo": 7.0,
        "minimumCaseScoreGo": 6.5,
    }
    assert {item["prompt"] for item in summary["baselinePrompts"]} == {
        case.prompt for case in BASELINE_CASES
    }
    assert Path(summary["jsonPath"]).is_file()
    assert Path(summary["markdownPath"]).is_file()
    assert (tmp_path / "golden-contract" / "runs").is_dir()
    assert (tmp_path / "golden-contract" / "generated").is_dir()
    assert (tmp_path / "golden-contract" / "prompt-inputs").is_dir()

    on_disk = json.loads((tmp_path / "golden-contract.json").read_text(encoding="utf-8"))
    assert on_disk["caseCount"] == 4
    assert len(on_disk["cases"]) == 4

    expected_traits = set(TRAIT_DEFINITIONS)
    for case in on_disk["cases"]:
        assert isinstance(case["totalScore"], int | float)
        assert 0 <= case["totalScore"] <= 10
        assert set(case["traitScores"]) == expected_traits
        assert case["passThreshold"] == 6.5
        assert case["briefSource"] == "mock-no-key"
        assert case["planSource"] in {"pinned", "mock-no-key"}
        assert case["routeSanity"]["plannedRoutes"]
        assert case["contactCtaSanity"]["status"] in {"pass", "warn", "fail"}
        assert "selectedScaffoldId" in case["signalPropagation"]
        assert "expectedStarterId" in case["signalPropagation"]

    assert os.environ[OPENAI_API_KEY_ENV] == "sk-test-not-used"
    assert summary["embeddingsReadiness"] in {"go", "no-go"}
    assert summary["nextGate"] == summary["embeddingsReadiness"]


@pytest.mark.tooling
def test_golden_path_eval_gate_is_no_go_below_thresholds() -> None:
    from scripts.run_golden_path_eval import compute_gate

    gate = compute_gate(
        [
            {"caseId": "a", "totalScore": 8.0},
            {"caseId": "b", "totalScore": 7.0},
            {"caseId": "c", "totalScore": 6.4},
            {"caseId": "d", "totalScore": 7.0},
        ]
    )

    assert gate["embeddingsReadiness"] == "no-go"
    assert gate["nextGate"] == "no-go"
    assert gate["averagePassThreshold"] == 7.0
    assert gate["casePassThreshold"] == 6.5
    assert gate["casesBelowThreshold"] == ["c"]
    assert any("cases below 6.5" in reason for reason in gate["reasons"])


@pytest.mark.tooling
def test_golden_path_eval_gate_is_no_go_on_low_average() -> None:
    from scripts.run_golden_path_eval import compute_gate

    gate = compute_gate(
        [
            {"caseId": "a", "totalScore": 6.6},
            {"caseId": "b", "totalScore": 6.8},
            {"caseId": "c", "totalScore": 6.9},
            {"caseId": "d", "totalScore": 6.7},
        ]
    )

    assert gate["embeddingsReadiness"] == "no-go"
    assert gate["casesBelowThreshold"] == []
    assert any("average score" in reason for reason in gate["reasons"])


@pytest.mark.tooling
def test_golden_path_eval_gate_is_go_when_all_thresholds_pass() -> None:
    from scripts.run_golden_path_eval import compute_gate

    gate = compute_gate(
        [
            {"caseId": "a", "totalScore": 7.0},
            {"caseId": "b", "totalScore": 7.2},
            {"caseId": "c", "totalScore": 6.5},
            {"caseId": "d", "totalScore": 7.3},
        ]
    )

    assert gate["embeddingsReadiness"] == "go"
    assert gate["nextGate"] == "go"
    assert gate["casesBelowThreshold"] == []
