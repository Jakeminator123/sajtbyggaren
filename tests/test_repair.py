"""Tests for packages/generation/repair/ (Sprint 3A v1).

Locks the RepairResult contract and the no-fix-applied + not-needed
paths. Sprint 3A v1 has no mechanical or LLM fixes implemented; these
tests pin the v1 behaviour so Sprint 3B+ can plug in fixes without
breaking existing semantics.

Fixtures use ``_make_quality_result`` which derives ``status`` via the
real ``_aggregate_status`` helper from ``packages.generation.quality_gate
.gate``. That guarantees test fixtures are valid combinations the gate
itself could emit, preventing illusion of test coverage from impossible
states (e.g. ``status=failed`` with all blocking checks ok).
"""

from __future__ import annotations

import pytest

from packages.generation.quality_gate import CheckResult, QualityResult
from packages.generation.quality_gate.gate import _aggregate_status
from packages.generation.repair import (
    RepairFix,
    RepairResult,
    run_repair_pipeline,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core


def _make_quality_result(
    checks: list[CheckResult] | None = None,
) -> QualityResult:
    """Build a QualityResult with status derived from the same aggregator
    that ``run_quality_gate`` uses, so fixtures cannot encode states the
    gate itself would never emit.
    """
    if checks is None:
        checks = [
            CheckResult(name="typecheck", status="ok"),
            CheckResult(name="route-scan", status="ok"),
            CheckResult(name="build-status", status="ok"),
            CheckResult(name="policy-compliance", status="ok"),
        ]
    status = _aggregate_status(checks)
    return QualityResult(status=status, checks=checks)


@pytest.mark.tooling
def test_repair_returns_not_needed_when_quality_is_ok(tmp_path):
    """Quality Gate ok -> nothing to repair, status=not-needed."""
    result = run_repair_pipeline(
        _make_quality_result(),
        target_dir=tmp_path,
    )
    assert result.status == "not-needed"
    assert result.mechanicalFixesApplied == []
    assert result.llmFixesApplied == []
    assert result.remainingErrors == []


@pytest.mark.tooling
def test_repair_returns_no_fix_applied_on_failed_quality(tmp_path):
    """Sprint 3B v1: typecheck failures cannot be repaired by the
    current mechanical fix registry (which only ships
    ``ensure-default-export``), so they remain surfaced in
    remainingErrors with the Sprint 3B v1 reason that explains why no
    fix was applied. Sprint 5+ wires LLM-fix for typecheck failures.

    Uses typecheck=failed so _aggregate_status returns "failed" (a
    blocking check). route-scan-only failure aggregates to "degraded",
    not "failed", and is covered by the degraded test below.
    """
    quality = _make_quality_result(
        checks=[
            CheckResult(
                name="typecheck",
                status="failed",
                detail="tsc returncode 2",
                findings=["app/page.tsx(3,5): error TS2304: Cannot find name 'X'."],
            ),
            CheckResult(name="route-scan", status="ok"),
            CheckResult(name="build-status", status="ok"),
            CheckResult(name="policy-compliance", status="ok"),
        ],
    )
    assert quality.status == "failed"
    result = run_repair_pipeline(quality, target_dir=tmp_path)
    assert result.status == "no-fix-applied"
    assert result.mechanicalFixesApplied == []
    assert result.llmFixesApplied == []
    assert any("typecheck: " in err for err in result.remainingErrors)
    assert "Sprint 3B v1" in result.reason
    assert result.iterations == 0


@pytest.mark.tooling
def test_repair_no_fix_applied_on_degraded_quality(tmp_path):
    """Soft failure (route-scan failed but blocking checks ok) aggregates
    to ``degraded``; Repair Pipeline still surfaces the findings via
    no-fix-applied because Sprint 3A v1 has no fixes wired.
    """
    quality = _make_quality_result(
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
    assert quality.status == "degraded"
    result = run_repair_pipeline(quality, target_dir=tmp_path)
    assert result.status == "no-fix-applied"
    assert any("/foo" in err for err in result.remainingErrors)


@pytest.mark.tooling
def test_repair_skips_when_do_repair_false(tmp_path):
    """do_repair=False -> no-fix-applied with explicit skipped reason."""
    quality = _make_quality_result(
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
    assert quality.status == "degraded"
    result = run_repair_pipeline(
        quality, target_dir=tmp_path, do_repair=False
    )
    assert result.status == "no-fix-applied"
    assert "skipped" in result.reason.lower() or "do_repair=False" in result.reason


@pytest.mark.tooling
def test_repair_aggregates_findings_with_check_name(tmp_path):
    """remainingErrors must qualify each finding with the check name so
    Sprint 3B fix routing can dispatch by check.
    """
    quality = _make_quality_result(
        checks=[
            CheckResult(
                name="typecheck",
                status="failed",
                findings=["app/page.tsx(1,1): error TS2304"],
            ),
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
            CheckResult(name="build-status", status="ok"),
        ],
    )
    assert quality.status == "failed"
    result = run_repair_pipeline(quality, target_dir=tmp_path)
    assert result.status == "no-fix-applied"
    assert any(err.startswith("typecheck: ") for err in result.remainingErrors)
    assert any(err.startswith("route-scan: ") for err in result.remainingErrors)
    assert any(err.startswith("policy-compliance: ") for err in result.remainingErrors)
    assert len(result.remainingErrors) == 4


@pytest.mark.tooling
def test_repair_falls_back_to_check_detail_when_no_findings(tmp_path):
    """When a failed check has no findings, fall back to detail so the
    operator at least sees what failed.
    """
    quality = _make_quality_result(
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
    assert quality.status == "failed"
    result = run_repair_pipeline(quality, target_dir=tmp_path)
    assert any("typecheck: tsc returncode 2" in err for err in result.remainingErrors)


@pytest.mark.tooling
def test_repair_result_round_trips_through_pydantic(tmp_path):
    """RepairResult is written to disk via model_dump - must be JSON-clean
    and reconstructable.
    """
    import json

    result = run_repair_pipeline(
        _make_quality_result(),
        target_dir=tmp_path,
    )
    payload = result.model_dump()
    json.dumps(payload)
    restored = RepairResult.model_validate(payload)
    assert restored.status == result.status


@pytest.mark.tooling
def test_repair_fixture_helper_uses_real_aggregate_status():
    """Lock that _make_quality_result derives status via _aggregate_status.
    If a future test author bypasses the helper and constructs
    QualityResult with hand-picked status, fixtures may encode states
    the gate would never emit, hiding integration bugs.
    """
    import inspect

    import tests.test_repair as test_module

    source = inspect.getsource(test_module._make_quality_result)
    assert "_aggregate_status(checks)" in source, (
        "_make_quality_result must call _aggregate_status to keep "
        "fixtures consistent with what run_quality_gate would emit."
    )


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
