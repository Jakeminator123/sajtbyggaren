"""Phase 3 orchestration: run Quality Gate -> Repair Pipeline -> capture
final QualityResult.

This is the single entrypoint that ``scripts/build_site.py`` uses to
run fas 3 quality + repair so the wiring helper there stays thin
(B13 discipline + ADR 0015 + ADR 0016). The fix-registry policy says
the sandwich pattern (mechanical -> validate -> mechanical -> ...)
runs on EXACTLY ONE place, and that place is this package.

Why the helper exists alongside ``run_repair_pipeline``
-------------------------------------------------------
``run_repair_pipeline`` returns a ``RepairResult``. But the canonical
``data/runs/<runId>/quality-result.json`` artefact wants the FINAL
``QualityResult`` (post-repair, including the full
``checks: [CheckResult, ...]`` structure), not just the post-repair
status that ``RepairResult.qualityStatusAfter`` carries. Rather than
fattening ``RepairResult`` with an embedded QualityResult, this helper
re-runs the gate one more time (cheap; route-scan + policy-compliance
are pure file walks, build/typecheck were already skipped by the
sandwich loop) when the loop reports a status change. Tests assert the
re-run is *only* triggered when ``qualityStatusAfter`` actually
differs from the pre-repair status, so happy-path runs still incur a
single Quality Gate call.
"""

from __future__ import annotations

from pathlib import Path

from packages.generation.quality_gate import QualityResult, run_quality_gate

from .models import RepairResult
from .repair import run_repair_pipeline


def execute_phase3_quality_and_repair(
    *,
    target_dir: Path,
    required_routes: list[str],
    npm_steps: list[dict],
    build_status: str,
    do_typecheck: bool,
) -> tuple[QualityResult, RepairResult]:
    """Run Quality Gate, run Repair Pipeline, return (final QG, repair).

    Sequence:
        1. Initial Quality Gate. Always runs; emits ``QualityResult``.
        2. Repair Pipeline:
           - When ``build_status == "skipped"`` (caller used
             ``--skip-build``) repair is skipped because mechanical
             fixes need a real codegen target. Mirrors Sprint 3A.
           - Otherwise the pipeline applies fixes and may re-run the
             gate inside its sandwich loop.
        3. If the loop changed the gate's aggregate status, re-run the
           gate one more time so we have the full ``QualityResult``
           (not just the status field) for ``quality-result.json``.

    Returns
    -------
    (final_quality, repair_result)
        ``final_quality`` is what ``quality-result.json`` should record;
        ``repair_result`` is what ``repair-result.json`` should record.
        Callers serialise both to disk; this helper does NOT touch the
        filesystem itself (B13 boundary - I/O is the wiring's job).
    """
    initial_quality = run_quality_gate(
        target_dir=target_dir,
        required_routes=required_routes,
        npm_steps=npm_steps,
        build_status=build_status,
        do_typecheck=do_typecheck,
    )

    do_repair = build_status != "skipped"

    repair_result = run_repair_pipeline(
        initial_quality,
        target_dir=target_dir,
        required_routes=required_routes,
        npm_steps=npm_steps,
        build_status=build_status,
        do_typecheck=do_typecheck,
        do_repair=do_repair,
    )

    if (
        repair_result.iterations > 0
        and repair_result.qualityStatusAfter is not None
        and repair_result.qualityStatusAfter != initial_quality.status
    ):
        final_quality = run_quality_gate(
            target_dir=target_dir,
            required_routes=required_routes,
            npm_steps=npm_steps,
            build_status=build_status,
            do_typecheck=do_typecheck,
        )
    else:
        final_quality = initial_quality

    return final_quality, repair_result
