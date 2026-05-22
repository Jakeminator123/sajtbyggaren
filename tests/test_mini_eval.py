"""Tests for the isolated mini-eval runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.tooling
def test_mini_eval_runs_single_case_in_isolated_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts.mini_eval import MINI_EVAL_CASES, run_mini_eval

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = run_mini_eval(
        cases=[MINI_EVAL_CASES[0]],
        evals_dir=tmp_path,
        eval_id="single-case",
        run_build=False,
    )

    eval_dir = tmp_path / "single-case"
    assert report["summary"]["total"] == 1
    assert report["summary"]["failed"] == 0
    assert (eval_dir / "prompt-inputs").is_dir()
    assert (eval_dir / "runs").is_dir()
    assert (eval_dir / "generated").is_dir()
    assert (eval_dir / "mini-eval-report.json").is_file()
    assert (eval_dir / "mini-eval-report.md").is_file()
    assert not (REPO_ROOT / "data" / "runs" / report["results"][0]["v2"]["runId"]).exists()


@pytest.mark.tooling
def test_mini_eval_report_records_token_change_for_premium_followup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts.mini_eval import MINI_EVAL_CASES, run_mini_eval

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = run_mini_eval(
        cases=[MINI_EVAL_CASES[0]],
        evals_dir=tmp_path,
        eval_id="token-change",
        run_build=False,
    )
    result = report["results"][0]

    assert result["passed"] is True
    assert result["fieldChanges"]["tone"] is True
    assert result["tokenChanges"]["primary"] is True
    assert result["rawPromptLeaks"] == []
    written = json.loads((tmp_path / "token-change" / "mini-eval-report.json").read_text(encoding="utf-8"))
    assert written["summary"] == report["summary"]
