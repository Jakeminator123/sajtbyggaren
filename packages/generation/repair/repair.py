"""Repair Pipeline orchestrator.

Sprint 3A v1 is intentionally narrow: it inspects QualityResult and
emits a structured RepairResult. It does NOT yet apply mechanical or
LLM fixes - those land in Sprint 3B+ (mechanical via Fix Registry from
governance/policies/fix-registry.v1.json) and Sprint 5+ (LLM-fix when
mechanical autofix is insufficient).

The contract (RepairResult) is locked now so the orchestrator and
build-result.json consumers do not have to change when the body is
filled in.
"""

from __future__ import annotations

from pathlib import Path

from packages.generation.quality_gate import QualityResult

from .models import RepairResult


def _collect_remaining_errors(quality_result: QualityResult) -> list[str]:
    """Flatten failed-check findings into a single list of strings.

    Format: ``<check name>: <finding>``. Used by Sprint 3A v1 to surface
    what Repair Pipeline could not fix; later sprints filter this list
    against the Fix Registry to decide which fixes to attempt.
    """
    remaining: list[str] = []
    for check in quality_result.checks:
        if check.status != "failed":
            continue
        if check.findings:
            for finding in check.findings:
                remaining.append(f"{check.name}: {finding}")
        else:
            remaining.append(f"{check.name}: {check.detail or 'failed'}")
    return remaining


def run_repair_pipeline(
    quality_result: QualityResult,
    *,
    target_dir: Path,
    do_repair: bool = True,
) -> RepairResult:
    """Inspect QualityResult and produce a RepairResult.

    Sprint 3A v1 behaviour:

    - If ``quality_result.status == "ok"`` -> ``status="not-needed"``.
      No work to do, no fixes to attempt.
    - If ``do_repair`` is False -> ``status="no-fix-applied"`` with a
      reason explaining the caller skipped repair (used by --skip-build
      paths and tests).
    - Otherwise -> ``status="no-fix-applied"`` with ``remainingErrors``
      flattened from the failed checks. Sprint 3A v1 has no mechanical
      or LLM fixes to attempt, so the pipeline is honest about that.

    ``target_dir`` is reserved for Sprint 3B+ mechanical fixes that
    write to disk (e.g. add ``export default`` to a page that the
    route-scan flagged). Currently unused but locked into the signature
    so callers do not need to change.
    """
    if quality_result.status == "ok":
        return RepairResult(
            status="not-needed",
            reason="Quality Gate reported status=ok; no failures to repair.",
        )

    if not do_repair:
        return RepairResult(
            status="no-fix-applied",
            reason=(
                "Repair Pipeline skipped (do_repair=False). "
                "Quality Gate failures were not addressed."
            ),
            remainingErrors=_collect_remaining_errors(quality_result),
        )

    return RepairResult(
        status="no-fix-applied",
        reason=(
            "Sprint 3A v1: mechanical fix registry is empty and LLM-fix "
            "is not yet wired. Quality Gate failures are surfaced as "
            "remainingErrors for operator review. Mechanical fixes land "
            "in Sprint 3B per ADR 0015."
        ),
        remainingErrors=_collect_remaining_errors(quality_result),
    )
