"""Tests for packages/generation/repair/ (Sprint 3A v1).

Locks the RepairResult contract and the no-fix-applied + not-needed
paths. Sprint 3A v1 has no mechanical or LLM fixes implemented; these
tests pin the v1 behaviour so Sprint 3B+ can plug in fixes without
breaking existing semantics.
"""

from __future__ import annotations

import pytest

from packages.generation.quality_gate import CheckResult, QualityResult
from packages.generation.repair import (
    RepairFix,
    RepairResult,
    run_repair_pipeline,
)


def _make_quality_result(
    status: str,
    checks: list[CheckResult] | None = None,
) -> QualityResult:
    return QualityResult(
        status=status,  # type: ignore[arg-type]
        checks=checks or [
            CheckResult(name="typecheck", status="ok"),
            CheckResult(name="route-scan", status="ok"),
            CheckResult(name="build-status", status="ok"),
            CheckResult(name="policy-compliance", status="ok"),
        ],
    )


@pytest.mark.tooling
def test_repair_returns_not_needed_when_quality_is_ok(tmp_path):
    """Quality Gate ok -> nothing to repair, status=not-needed."""
    result = run_repair_pipeline(
        _make_quality_result("ok"),
        target_dir=tmp_path,
    )
    assert result.status == "not-needed"
    assert result.mechanicalFixesApplied == []
    assert result.llmFixesApplied == []
    assert result.remainingErrors == []


@pytest.mark.tooling
def test_repair_returns_no_fix_applied_on_failed_quality(tmp_path):
    """Sprint 3A v1: failures are surfaced in remainingErrors but not
    fixed (no mechanical or LLM fixes implemented yet).
    """
    quality = _make_quality_result(
        "failed",
        checks=[
            CheckResult(
                name="route-scan",
                status="failed",
                detail="missing routes",
                findings=["/foo -> app/foo/page.tsx (saknas)"],
            ),
            CheckResult(name="typecheck", status="ok"),
            CheckResult(name="build-status", status="ok"),
            CheckResult(name="policy-compliance", status="ok"),
        ],
    )
    result = run_repair_pipeline(quality, target_dir=tmp_path)
    assert result.status == "no-fix-applied"
    assert result.mechanicalFixesApplied == []
    assert result.llmFixesApplied == []
    assert any("/foo" in err for err in result.remainingErrors)
    assert "Sprint 3A v1" in result.reason


@pytest.mark.tooling
def test_repair_skips_when_do_repair_false(tmp_path):
    """do_repair=False -> no-fix-applied with explicit skipped reason."""
    quality = _make_quality_result(
        "degraded",
        checks=[
            CheckResult(
                name="policy-compliance",
                status="failed",
                detail="forbidden file",
                findings=[".env"],
            ),
            CheckResult(name="route-scan", status="ok"),
            CheckResult(name="typecheck", status="ok"),
            CheckResult(name="build-status", status="ok"),
        ],
    )
    result = run_repair_pipeline(
        quality, target_dir=tmp_path, do_repair=False
    )
    assert result.status == "no-fix-applied"
    assert "skipped" in result.reason.lower() or "do_repair=False" in result.reason


@pytest.mark.tooling
def test_repair_aggregates_findings_with_check_name():
    """remainingErrors must qualify each finding with the check name so
    Sprint 3B fix routing can dispatch by check.
    """
    quality = _make_quality_result(
        "failed",
        checks=[
            CheckResult(
                name="route-scan",
                status="failed",
                findings=["a", "b"],
            ),
            CheckResult(
                name="policy-compliance",
                status="failed",
                findings=["c"],
            ),
            CheckResult(name="typecheck", status="ok"),
            CheckResult(name="build-status", status="ok"),
        ],
    )
    result = run_repair_pipeline(quality, target_dir=__import__("pathlib").Path("/tmp"))
    assert result.status == "no-fix-applied"
    assert any(err.startswith("route-scan: ") for err in result.remainingErrors)
    assert any(err.startswith("policy-compliance: ") for err in result.remainingErrors)
    assert len(result.remainingErrors) == 3


@pytest.mark.tooling
def test_repair_falls_back_to_check_detail_when_no_findings(tmp_path):
    """When a failed check has no findings, fall back to detail so the
    operator at least sees what failed.
    """
    quality = _make_quality_result(
        "failed",
        checks=[
            CheckResult(
                name="typecheck",
                status="failed",
                detail="tsc returncode 2",
                findings=[],
            ),
            CheckResult(name="route-scan", status="ok"),
            CheckResult(name="build-status", status="ok"),
            CheckResult(name="policy-compliance", status="ok"),
        ],
    )
    result = run_repair_pipeline(quality, target_dir=tmp_path)
    assert any("typecheck: tsc returncode 2" in err for err in result.remainingErrors)


@pytest.mark.tooling
def test_repair_result_round_trips_through_pydantic(tmp_path):
    """RepairResult is written to disk via model_dump - must be JSON-clean
    and reconstructable.
    """
    import json

    result = run_repair_pipeline(
        _make_quality_result("ok"),
        target_dir=tmp_path,
    )
    payload = result.model_dump()
    json.dumps(payload)
    restored = RepairResult.model_validate(payload)
    assert restored.status == result.status


@pytest.mark.tooling
def test_repair_fix_pydantic_validates_kind():
    """RepairFix.kind is Literal - bogus kinds must be rejected so the
    contract stays strict before mechanical fixes land in Sprint 3B.
    """
    from pydantic import ValidationError

    RepairFix(kind="mechanical", name="add-export-default", target="app/page.tsx")
    RepairFix(kind="llm", name="prompt-fix", target="app/page.tsx")
    with pytest.raises(ValidationError):
        RepairFix(kind="manual", name="x", target="y")  # type: ignore[arg-type]
