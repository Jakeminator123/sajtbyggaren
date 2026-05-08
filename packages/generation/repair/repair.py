"""Repair Pipeline orchestrator.

Sprint 3A v1 emitted ``no-fix-applied`` for every failure (the registry
was empty). Sprint 3B v1 ships the first mechanical fix
(``ensure-default-export`` for route-scan failures of the form
``"<route> -> <relpath> (saknar export default)"``) and the sandwich
loop that re-runs Quality Gate after a mutation:

    quality_before
        |
        v
    apply mechanical fixes  -- bounded per stage --+
        |                                          |
        v                                          |
    re-run run_quality_gate(target_dir=...) -------+
        |
        v
    quality_after  (-> RepairResult.qualityStatusAfter)

Loop bounds come from
``governance/policies/fix-registry.v1.json:loopLimits``:

- ``maxMechanicalIterationsPerStage=2`` -- this orchestrator currently
  ships a single stage (``post-codegen``); the cap means we run the
  fix list at most twice before giving up on a stuck file.
- ``maxTotalSandwichPasses=3`` -- absolute cap on
  apply-fix + re-run-gate iterations regardless of how many stages
  exist. Sprint 3B v1 has one stage so the practical cap is 2 (one
  initial apply, one rerun-and-retry).
- ``abortBehavior="mark-degraded-and-emit-engine-event"`` -- when the
  cap is hit we surface the run as ``partial-fix`` if any mechanical
  fix succeeded, else ``no-fix-applied``. The orchestrator caller
  (scripts/build_site.py) emits the engine event.

LLM-fix is intentionally not wired here. Sprint 5+ adds it via the
registry's ``llmFixes`` array; ``llmFixesApplied`` stays empty in
Sprint 3B.
"""

from __future__ import annotations

from pathlib import Path

from packages.generation.quality_gate import (
    QualityResult,
    QualityStatus,
    run_quality_gate,
)

from .fixes import MECHANICAL_FIXES
from .fixes.ensure_default_export import apply_ensure_default_export
from .models import RepairFix, RepairResult

# Mirrors governance/policies/fix-registry.v1.json:loopLimits. Tests in
# tests/test_repair_fixes.py assert that the constant matches the
# policy file so a registry bump cannot drift past this code.
_MAX_TOTAL_SANDWICH_PASSES = 3


def _collect_remaining_errors(quality_result: QualityResult) -> list[str]:
    """Flatten failed-check findings into a single list of strings.

    Format: ``<check name>: <finding>``. Used by the orchestrator to
    surface what Repair Pipeline could not fix; later sprints filter
    this list against the Fix Registry to decide which fixes to
    attempt.
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


def _can_rerun_quality_gate(
    *,
    required_routes: list[str] | None,
    npm_steps: list[dict] | None,
) -> bool:
    """Sprint 3B re-runs the gate only when the caller passed enough
    information to reproduce the original gate call. The Sprint 3A
    test signature ``run_repair_pipeline(quality_result, *, target_dir,
    do_repair=True)`` does not, so those tests fall back to a single
    apply-pass with no re-run (mechanical fixes still mutate disk; we
    just cannot independently confirm the gate now reports ``ok``).
    """
    return required_routes is not None and npm_steps is not None


def _dispatch_mechanical_fixes(
    target_dir: Path,
    quality_result: QualityResult,
) -> list[RepairFix]:
    """Run every registered mechanical fix in priority order and
    aggregate the RepairFix entries.

    Sprint 3B v1 only ships ``ensure-default-export`` so the dispatch
    table is one entry. The structure stays generic so Sprint 3B-next
    (more mechanical fixes) plugs in without rewriting the orchestrator.
    """
    fixes: list[RepairFix] = []
    for spec in sorted(MECHANICAL_FIXES, key=lambda s: s.priority):
        if spec.fix_id == "ensure-default-export":
            fixes.extend(
                apply_ensure_default_export(target_dir, quality_result)
            )
            continue
        # Future: add elif branches for newly registered fixes. Tests
        # in tests/test_repair_fixes.py assert that every registry
        # entry has a dispatch branch here.
    return fixes


def _decide_status(
    *,
    applied_fixes: list[RepairFix],
    quality_status_before: QualityStatus,
    quality_status_after: QualityStatus,
) -> tuple[str, str]:
    """Compute final RepairResult.status + reason from the collected
    telemetry. Pure function so the policy is easy to lock in tests.

    Rules:
      - At least one successful fix AND gate now reports ok ->
        ``fixed``.
      - At least one successful fix AND gate status improved (from
        failed to degraded, or from degraded to ok-but-still-not-ok-
        on-soft-checks) -> ``partial-fix``.
      - At least one successful fix BUT gate status unchanged ->
        ``partial-fix`` (we did mutate disk; the orchestrator should
        record that even when the gate cannot confirm an improvement,
        e.g. when re-run was not possible).
      - Fixes attempted but all failed -> ``no-fix-applied`` with a
        reason that lists the failure detail.
      - No fixes attempted at all -> ``no-fix-applied`` with a Sprint
        3B v1 reason (registry only ships ensure-default-export).
    """
    succeeded = [f for f in applied_fixes if f.success]
    failed = [f for f in applied_fixes if not f.success]

    if succeeded and quality_status_after == "ok":
        return (
            "fixed",
            (
                f"Mechanical fixes applied ({len(succeeded)}); "
                f"Quality Gate after re-run reports status=ok."
            ),
        )

    if succeeded:
        return (
            "partial-fix",
            (
                f"Mechanical fixes applied ({len(succeeded)}); "
                f"Quality Gate status before={quality_status_before} "
                f"after={quality_status_after}. Some findings remain; "
                f"see remainingErrors."
            ),
        )

    if failed:
        return (
            "no-fix-applied",
            (
                f"Mechanical fixes attempted ({len(failed)}) but none "
                f"succeeded. See mechanicalFixesApplied[].detail for "
                f"why each fix could not proceed."
            ),
        )

    return (
        "no-fix-applied",
        (
            "Sprint 3B v1: mechanical fix registry ships "
            "ensure-default-export only. Quality Gate findings outside "
            "that scope are surfaced as remainingErrors for operator "
            "review (LLM-fix lands in Sprint 5+ per ADR 0015 + 0016)."
        ),
    )


def run_repair_pipeline(
    quality_result: QualityResult,
    *,
    target_dir: Path,
    required_routes: list[str] | None = None,
    npm_steps: list[dict] | None = None,
    build_status: str = "ok",
    do_typecheck: bool = False,
    do_repair: bool = True,
) -> RepairResult:
    """Inspect QualityResult, apply mechanical fixes, optionally re-run
    Quality Gate, return a RepairResult.

    Behaviour:

    - ``quality_result.status == "ok"`` -> ``status="not-needed"``;
      no work to do, gate-status fields are populated for telemetry.
    - ``do_repair=False`` -> ``status="no-fix-applied"`` with a reason
      explaining the caller skipped repair (used by --skip-build paths
      and tests). Used by Sprint 3A consumers.
    - Otherwise the sandwich loop runs:
      1. dispatch mechanical fixes against the current quality result
      2. if any fix succeeded AND we have enough info to re-run, call
         ``run_quality_gate`` and update the cursor
      3. repeat until ``maxTotalSandwichPasses``, until no new fixes
         apply, or until quality status reaches ``ok``

    The Sprint 3A signature ``run_repair_pipeline(quality_result, *,
    target_dir, do_repair=True)`` keeps working unchanged: when the
    re-run params (``required_routes`` / ``npm_steps``) are not passed,
    the loop performs at most one apply-pass and skips the re-run. The
    new behaviour is additive.

    Parameters
    ----------
    quality_result
        The pre-repair Quality Gate output; ``status`` may be ``ok``,
        ``degraded`` or ``failed``.
    target_dir
        The generated Next.js project directory mechanical fixes
        write into.
    required_routes / npm_steps / build_status / do_typecheck
        What ``packages.generation.quality_gate.run_quality_gate``
        needs to re-run after a mutation. ``required_routes=None`` (or
        ``npm_steps=None``) disables the re-run.
    do_repair
        Set False to skip the loop entirely; matches Sprint 3A
        behaviour and the dev-generate mock pipeline.
    """
    quality_status_before = quality_result.status

    if quality_result.status == "ok":
        return RepairResult(
            status="not-needed",
            reason="Quality Gate reported status=ok; no failures to repair.",
            qualityStatusBefore=quality_status_before,
            qualityStatusAfter=quality_status_before,
            iterations=0,
        )

    if not do_repair:
        return RepairResult(
            status="no-fix-applied",
            reason=(
                "Repair Pipeline skipped (do_repair=False). "
                "Quality Gate failures were not addressed."
            ),
            remainingErrors=_collect_remaining_errors(quality_result),
            qualityStatusBefore=quality_status_before,
            qualityStatusAfter=quality_status_before,
            iterations=0,
        )

    can_rerun = _can_rerun_quality_gate(
        required_routes=required_routes, npm_steps=npm_steps
    )

    applied_fixes: list[RepairFix] = []
    current_quality = quality_result
    iterations = 0

    def _failed_finding_count(qr: QualityResult) -> int:
        return sum(
            len(check.findings)
            for check in qr.checks
            if check.status == "failed"
        )

    prev_finding_count = _failed_finding_count(current_quality)

    while iterations < _MAX_TOTAL_SANDWICH_PASSES:
        pass_fixes = _dispatch_mechanical_fixes(target_dir, current_quality)
        had_success = any(f.success for f in pass_fixes)
        if not had_success:
            # Either the dispatcher matched no findings (registry has
            # no fix for the failure type) or every attempted fix on
            # this pass was a duplicate of a previously-attempted-and-
            # failed target. In both cases extending applied_fixes
            # with these entries would log the same failures multiple
            # times, so break without extending.
            break

        applied_fixes.extend(pass_fixes)
        iterations += 1

        if not can_rerun:
            # Disk was mutated but the caller did not pass re-run
            # params (Sprint 3A signature). Trust the mutations; do
            # not loop further.
            break

        # required_routes / npm_steps are guaranteed non-None by
        # _can_rerun_quality_gate; the asserts keep type-checkers
        # quiet and codify the contract.
        assert required_routes is not None
        assert npm_steps is not None

        current_quality = run_quality_gate(
            target_dir=target_dir,
            required_routes=required_routes,
            npm_steps=npm_steps,
            build_status=build_status,
            do_typecheck=do_typecheck,
        )

        if current_quality.status == "ok":
            break

        new_finding_count = _failed_finding_count(current_quality)
        if new_finding_count >= prev_finding_count:
            # Sandwich-loop progress check: if the post-rerun gate has
            # at least as many failed findings as it did before this
            # pass, the loop is not making progress. Further passes
            # would re-attempt the same failed targets and dilute
            # mechanicalFixesApplied[] with duplicate failure entries.
            # Per fix-registry abortBehavior, mark and stop.
            break
        prev_finding_count = new_finding_count

    quality_status_after: QualityStatus
    if can_rerun and any(f.success for f in applied_fixes):
        quality_status_after = current_quality.status
    else:
        # We did not re-run the gate (or all fixes failed); the
        # post-repair gate status is unknown -> mirror the pre-repair
        # status so consumers do not see a misleading drop to ``ok``.
        quality_status_after = quality_status_before

    status, reason = _decide_status(
        applied_fixes=applied_fixes,
        quality_status_before=quality_status_before,
        quality_status_after=quality_status_after,
    )

    return RepairResult(
        status=status,  # type: ignore[arg-type]
        reason=reason,
        mechanicalFixesApplied=applied_fixes,
        remainingErrors=_collect_remaining_errors(current_quality),
        qualityStatusBefore=quality_status_before,
        qualityStatusAfter=quality_status_after,
        iterations=iterations,
    )
