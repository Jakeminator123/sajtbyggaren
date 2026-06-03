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
from typing import Any

from packages.generation.quality_gate import (
    QualityResult,
    append_critic_trace_event,
    run_quality_gate,
)

from .models import RepairResult
from .repair import run_repair_pipeline


def execute_phase3_quality_and_repair(
    *,
    target_dir: Path,
    required_routes: list[str],
    npm_steps: list[dict],
    build_status: str,
    do_typecheck: bool,
    generation_package: dict[str, Any] | None = None,
    site_brief: dict[str, Any] | None = None,
    run_dir: Path | None = None,
    run_id: str | None = None,
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

    kor-4a critic wiring (integration-gap fix): when ``generation_package``
    is supplied the deterministic critic runs over the blueprint (+ the
    optional ``site_brief`` honesty fields + ``target_dir`` output) and is
    attached to the FINAL ``QualityResult.critic`` that reaches
    ``quality-result.json`` in a real build. Without a blueprint (the legacy/
    Repair-Pipeline callers) ``critic`` stays ``None`` exactly as before.
    The internal repair sandwich-loop gate calls deliberately stay
    blueprint-free: the critic is a warning lane that never affects
    ``status``, so re-running it inside the loop would add nothing but a
    duplicate ``critic.evaluated`` trace event. ``run_dir``/``run_id`` let the
    final gate log exactly one non-blocking ``critic.evaluated`` event.

    Returns
    -------
    (final_quality, repair_result)
        ``final_quality`` is what ``quality-result.json`` should record;
        ``repair_result`` is what ``repair-result.json`` should record.
        Callers serialise both to disk; this helper does NOT touch the
        filesystem itself (B13 boundary - I/O is the wiring's job).
    """
    # Initial gate: compute the critic but defer its trace event until we know
    # which QualityResult is final, so a single ``critic.evaluated`` event is
    # written regardless of whether the repair loop forced a re-run.
    initial_quality = run_quality_gate(
        target_dir=target_dir,
        required_routes=required_routes,
        npm_steps=npm_steps,
        build_status=build_status,
        do_typecheck=do_typecheck,
        generation_package=generation_package,
        site_brief=site_brief,
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

    # Sprint 3B v1.1 fix: any successful sandwich pass mutates target/
    # so the initial QualityResult.checks list is stale even if the
    # AGGREGATE status (ok/degraded/failed) is unchanged. A run that
    # fixed one of two route-scan findings is still ``degraded`` after
    # repair, but the post-repair gate has fewer findings - the
    # operator-facing artefact must reflect that. Re-run when
    # ``iterations > 0`` regardless of the status delta. The cost is
    # one extra route-scan + policy-compliance walk (ms-cheap;
    # typecheck and build-status are already either skipped or
    # impossible to re-validate without re-running npm).
    if repair_result.iterations > 0:
        # A sandwich pass mutated target/, so re-run the gate (and the critic)
        # over the post-repair tree; this final gate owns the single trace
        # event when a run dir is available.
        final_quality = run_quality_gate(
            target_dir=target_dir,
            required_routes=required_routes,
            npm_steps=npm_steps,
            build_status=build_status,
            do_typecheck=do_typecheck,
            generation_package=generation_package,
            site_brief=site_brief,
            run_dir=run_dir,
            run_id=run_id,
        )
    else:
        final_quality = initial_quality
        # No re-run happened, so the initial critic is final: emit its single
        # non-blocking trace event here (the initial gate was called without a
        # run_dir to keep the event count at exactly one).
        if run_dir is not None and final_quality.critic is not None:
            append_critic_trace_event(run_dir, run_id or "unknown", final_quality.critic)

    return final_quality, repair_result
