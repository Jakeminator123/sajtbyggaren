"""Tests for scripts/eval_gate.py (the eval-baseline regression gate)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytestmark = pytest.mark.tooling


def _baseline(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "embeddingsReadiness": "go",
        "totalScore": 7.75,
        "cases": {
            "ceramics-shop": 8.12,
            "electrician-malmo": 7.47,
            "naprapat-stockholm": 7.96,
            "salon-goteborg": 7.47,
        },
    }
    base.update(overrides)
    return base


def test_compare_equal_to_baseline_passes() -> None:
    from scripts.eval_gate import baseline_scores, compare_to_baseline

    baseline = _baseline()
    result = compare_to_baseline(dict(baseline), baseline_scores(baseline))

    assert result.passed is True
    assert result.regressions == []
    assert result.improvements == []


def test_compare_regression_within_tolerance_passes() -> None:
    from scripts.eval_gate import compare_to_baseline

    baseline = _baseline()
    # One case drops 0.4 (<= 0.5 per-case tolerance) and the aggregate drops
    # 0.1 (<= 0.2 aggregate tolerance): a soft dip that must not trip the gate.
    current = _baseline(
        totalScore=7.65,
        cases={
            "ceramics-shop": 8.12,
            "electrician-malmo": 7.07,
            "naprapat-stockholm": 7.96,
            "salon-goteborg": 7.47,
        },
    )

    result = compare_to_baseline(current, baseline)

    assert result.passed is True
    assert result.regressions == []


def test_compare_per_case_regression_beyond_tolerance_fails() -> None:
    from scripts.eval_gate import compare_to_baseline

    baseline = _baseline()
    current = _baseline(
        totalScore=7.6,
        cases={
            "ceramics-shop": 8.12,
            "electrician-malmo": 6.8,  # drop 0.67 > 0.5 per-case tolerance
            "naprapat-stockholm": 7.96,
            "salon-goteborg": 7.47,
        },
    )

    result = compare_to_baseline(current, baseline)

    assert result.passed is False
    assert any("electrician-malmo" in reason for reason in result.regressions)


def test_compare_aggregate_regression_beyond_tolerance_fails() -> None:
    from scripts.eval_gate import compare_to_baseline

    baseline = _baseline()
    # Every case dips 0.3 (within per-case tolerance) but the aggregate falls
    # 0.3 > 0.2 aggregate tolerance, so the broad drift must fail the gate.
    current = _baseline(
        totalScore=7.45,
        cases={
            "ceramics-shop": 7.82,
            "electrician-malmo": 7.17,
            "naprapat-stockholm": 7.66,
            "salon-goteborg": 7.17,
        },
    )

    result = compare_to_baseline(current, baseline)

    assert result.passed is False
    assert any("aggregate" in reason for reason in result.regressions)


def test_compare_improvement_passes() -> None:
    from scripts.eval_gate import compare_to_baseline

    baseline = _baseline()
    current = _baseline(
        totalScore=8.5,
        cases={
            "ceramics-shop": 9.0,
            "electrician-malmo": 8.0,
            "naprapat-stockholm": 8.5,
            "salon-goteborg": 8.5,
        },
    )

    result = compare_to_baseline(current, baseline)

    assert result.passed is True
    assert result.regressions == []
    assert any("electrician-malmo" in note for note in result.improvements)


def test_compare_missing_case_fails() -> None:
    from scripts.eval_gate import compare_to_baseline

    baseline = _baseline()
    current = _baseline(
        cases={
            "ceramics-shop": 8.12,
            "electrician-malmo": 7.47,
            "naprapat-stockholm": 7.96,
        },
    )

    result = compare_to_baseline(current, baseline)

    assert result.passed is False
    assert any("salon-goteborg" in reason for reason in result.regressions)


def test_compare_readiness_go_to_no_go_fails() -> None:
    from scripts.eval_gate import compare_to_baseline

    baseline = _baseline()
    current = _baseline(embeddingsReadiness="no-go")

    result = compare_to_baseline(current, baseline)

    assert result.passed is False
    assert any("embeddingsReadiness" in reason for reason in result.regressions)


def test_distill_scores_strips_volatile_fields() -> None:
    from scripts.eval_gate import distill_scores

    summary = {
        "evalId": "golden-path-20260611T000000Z",
        "createdAt": "2026-06-11T00:00:00+00:00",
        "embeddingsReadiness": "go",
        "totalScore": 7.75,
        "cases": [
            {"caseId": "salon-goteborg", "totalScore": 7.47, "runId": "x", "runDir": "/tmp/x"},
            {"caseId": "electrician-malmo", "totalScore": 7.47, "elapsedMs": 123},
        ],
    }

    distilled = distill_scores(summary)

    assert distilled == {
        "embeddingsReadiness": "go",
        "totalScore": 7.75,
        "cases": {"electrician-malmo": 7.47, "salon-goteborg": 7.47},
    }
    assert list(distilled["cases"]) == ["electrician-malmo", "salon-goteborg"]


def test_build_baseline_document_round_trips(tmp_path: Path) -> None:
    from scripts.eval_gate import (
        GateTolerance,
        baseline_scores,
        build_baseline_document,
        load_baseline,
        write_baseline,
    )

    distilled = {
        "embeddingsReadiness": "go",
        "totalScore": 7.75,
        "cases": {"electrician-malmo": 7.47, "salon-goteborg": 7.47},
    }
    document = build_baseline_document(distilled, tolerance=GateTolerance())

    assert document["_meta"]["tolerance"]["aggregateAverageMaxDrop"] == 0.2
    assert document["_meta"]["tolerance"]["perCaseMaxDrop"] == 0.5

    path = tmp_path / "golden-path-baseline.json"
    write_baseline(path, document)
    reloaded = load_baseline(path)

    assert baseline_scores(reloaded) == distilled


def test_committed_baseline_matches_gate_defaults() -> None:
    """The committed baseline must be readable with the shipped tolerance."""

    from scripts.eval_gate import (
        AGGREGATE_MAX_DROP,
        CASE_MAX_DROP,
        DEFAULT_BASELINE_PATH,
        baseline_scores,
        load_baseline,
    )

    document = load_baseline(DEFAULT_BASELINE_PATH)
    scores = baseline_scores(document)

    assert document["_meta"]["tolerance"] == {
        "aggregateAverageMaxDrop": AGGREGATE_MAX_DROP,
        "perCaseMaxDrop": CASE_MAX_DROP,
    }
    assert scores["embeddingsReadiness"] == "go"
    assert set(scores["cases"]) == {
        "ceramics-shop",
        "electrician-malmo",
        "naprapat-stockholm",
        "salon-goteborg",
    }
    assert all(0.0 <= score <= 10.0 for score in scores["cases"].values())


def test_run_gate_wires_eval_to_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """run_gate distils the eval summary and compares it to the baseline."""

    import scripts.eval_gate as eval_gate

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "_meta": {"schemaVersion": 1},
                "embeddingsReadiness": "go",
                "totalScore": 7.75,
                "cases": {"electrician-malmo": 7.47, "salon-goteborg": 7.47},
            }
        ),
        encoding="utf-8",
    )

    def fake_eval(*, work_dir: Path | None = None) -> dict[str, object]:
        return {
            "embeddingsReadiness": "go",
            "totalScore": 7.75,
            "cases": [
                {"caseId": "electrician-malmo", "totalScore": 7.47},
                {"caseId": "salon-goteborg", "totalScore": 7.47},
            ],
        }

    monkeypatch.setattr(eval_gate, "run_deterministic_eval", fake_eval)

    result, current = eval_gate.run_gate(baseline_path=baseline_path)

    assert result.passed is True
    assert current["cases"] == {"electrician-malmo": 7.47, "salon-goteborg": 7.47}


@pytest.mark.slow
def test_deterministic_eval_runs_even_with_key_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Honest fallback: a present OPENAI_API_KEY still runs deterministic mode.

    This guards against a silent no-op ("no key -> green"): the gate must run
    a real deterministic eval and produce four scored cases regardless of the
    key, and must not consume the operator's key.
    """

    from scripts.eval_gate import compare_to_baseline, distill_scores, run_deterministic_eval

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-must-not-be-used")

    summary = run_deterministic_eval(work_dir=tmp_path / "eval")

    assert summary["deterministicOffline"] is True
    assert summary["llmKeyRequired"] is False
    assert summary["caseCount"] == 4
    assert os.environ["OPENAI_API_KEY"] == "sk-test-must-not-be-used"

    distilled = distill_scores(summary)
    assert len(distilled["cases"]) == 4
    assert all(0.0 <= score <= 10.0 for score in distilled["cases"].values())

    # Validating the fresh deterministic run against itself must pass — proof
    # the gate evaluates real scores rather than skipping when a key exists.
    result = compare_to_baseline(distilled, distilled)
    assert result.passed is True
