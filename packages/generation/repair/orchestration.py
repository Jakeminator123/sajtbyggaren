"""Phase 3 orchestration: run Quality Gate -> Repair Pipeline -> capture
final QualityResult.

This is the single entrypoint that ``scripts/build_site.py`` uses to
run fas 3 quality + repair so the wiring helper there stays thin
(B13 discipline + ADR 0015 + ADR 0016). The fix-registry policy says
the sandwich pattern (mechanical -> validate -> mechanical -> ...)
runs on EXACTLY ONE place, and that place is this package.

kor-5 layers the blueprint-repair pass on top of the kor-4a critic wiring
(#186) WITHOUT a second call-site: after the deterministic Quality Critic
produces issues, ``repairModel`` patches named blueprint fields and the
critic is re-run. It activates ONLY when the caller injects a ``rerender``
callback (so a patched blueprint is actually materialised by the same
deterministic renderer); ``scripts/build_site.py`` passes the blueprint for
the critic (#186) but not yet a ``rerender``, so blueprint-repair stays
dormant in the build path until that wiring lands - it never claims an
improvement it cannot render.

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

import json
from functools import cache
from pathlib import Path
from typing import Any

from packages.generation.quality_gate import (
    QualityResult,
    append_critic_trace_event,
    run_quality_gate,
)

from .blueprint_repair import (
    BlueprintRepairOutcome,
    RerenderFn,
    append_blueprint_repair_trace_event,
    apply_blueprint_repairs,
)
from .models import RepairResult, RepairStatus
from .repair import run_repair_pipeline

_FIX_REGISTRY_PATH = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "policies"
    / "fix-registry.v1.json"
)


@cache
def _blueprint_repair_policy() -> tuple[int, frozenset[str]]:
    """Return ``(maxPasses, triggerIssueTypes)`` from fix-registry.v1.json.

    Single source of truth: the policy file. Cached because it is read on every
    phase-3 run. ``tests/test_repair_blueprint_pass.py`` locks the policy values
    so a drift surfaces at test time. Defensive defaults (1 pass, the kor-5
    trigger set) keep the pass working even if the optional block is absent.
    """
    default_types = frozenset({"generic_copy", "thin_offer", "missing_cta"})
    try:
        data = json.loads(_FIX_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1, default_types
    block = data.get("blueprintRepair")
    if not isinstance(block, dict):
        return 1, default_types
    max_passes = block.get("maxPasses")
    if not isinstance(max_passes, int) or max_passes < 1:
        max_passes = 1
    types = block.get("triggerIssueTypes")
    trigger = (
        frozenset(t for t in types if isinstance(t, str))
        if isinstance(types, list) and types
        else default_types
    )
    return max_passes, trigger


def _combine_status(mechanical: RepairStatus, blueprint: str) -> RepairStatus:
    """Combine the mechanical + blueprint repair verdicts into one status.

    ``blueprint == "not-needed"`` (no eligible critic issue / dormant) leaves
    the mechanical status untouched. Otherwise the two axes (build/route-scan vs
    copy-quality critic) are merged conservatively: any partial outcome, or a
    fixed-on-one-axis-but-not-the-other, surfaces as ``partial-fix`` so the
    artefakt never over-claims. Documented + locked by tests.
    """
    if blueprint == "not-needed":
        return mechanical
    if mechanical == "not-needed":
        return blueprint  # type: ignore[return-value]
    if mechanical == blueprint:
        return mechanical
    if "partial-fix" in (mechanical, blueprint):
        return "partial-fix"
    # Remaining mixed cases (fixed vs no-fix-applied either way) -> partial-fix.
    return "partial-fix"


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
    rerender: RerenderFn | None = None,
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
        4. kor-5 blueprint-repair (only when ``generation_package`` is passed
           AND ``build_status != "skipped"`` AND a ``rerender`` callback is
           injected AND the critic flagged an eligible issue): ``repairModel``
           patches named blueprint fields -> re-render (injected ``rerender``)
           -> re-run critic, bounded by ``fix-registry.blueprintRepair
           .maxPasses``. The blueprint verdict is merged into
           ``RepairResult.status`` and recorded in ``blueprintRepairs`` /
           ``blueprintPasses``; the post-repair critic is surfaced on the
           returned QualityResult. Requiring ``rerender`` keeps the pass
           dormant in any caller that cannot materialise the patch (so the
           artefakt never reports a copy improvement the rendered site lacks).

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
        filesystem itself (B13 boundary - I/O is the wiring's job), except the
        non-blocking ``trace.ndjson`` appends the critic + blueprint-repair
        emit when a ``run_dir`` exists.
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
    # AGGREGATE status (ok/degraded/failed) is unchanged. Re-run when
    # ``iterations > 0`` regardless of the status delta. The cost is
    # one extra route-scan + policy-compliance walk (ms-cheap).
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

    # ----- kor-5 blueprint-repair (central gate; additive + rerender-gated) ---
    if generation_package is not None and do_repair and rerender is not None:
        final_quality, repair_result = _run_blueprint_repair(
            final_quality=final_quality,
            repair_result=repair_result,
            generation_package=generation_package,
            site_brief=site_brief,
            target_dir=target_dir,
            run_dir=run_dir,
            run_id=run_id,
            rerender=rerender,
        )

    return final_quality, repair_result


def _run_blueprint_repair(
    *,
    final_quality: QualityResult,
    repair_result: RepairResult,
    generation_package: dict[str, Any],
    site_brief: dict[str, Any] | None,
    target_dir: Path,
    run_dir: Path | None,
    run_id: str | None,
    rerender: RerenderFn,
) -> tuple[QualityResult, RepairResult]:
    """Run the blueprint-repair pass and fold its result into the artefakts."""
    max_passes, trigger_types = _blueprint_repair_policy()
    outcome: BlueprintRepairOutcome = apply_blueprint_repairs(
        generation_package=generation_package,
        site_brief=site_brief,
        critic=final_quality.critic,
        trigger_types=trigger_types,
        max_passes=max_passes,
        target_dir=target_dir,
        rerender=rerender,
    )

    # not-needed -> no eligible critic issue; leave the mechanical result alone.
    if outcome.status == "not-needed" and not outcome.repairs and not outcome.skipped:
        return final_quality, repair_result

    combined = _combine_status(repair_result.status, outcome.status)
    reason = repair_result.reason
    if outcome.skipped:
        note = (
            f"Blueprint repair skipped ({outcome.skipped_reason}); "
            f"eligible critic issues were not addressed."
        )
    else:
        applied = sum(1 for r in outcome.repairs if r.success)
        note = (
            f"Blueprint repair status={outcome.status} "
            f"blueprintPasses={outcome.passes} applied={applied}."
        )
    reason = f"{reason} {note}".strip() if reason else note

    repair_result = repair_result.model_copy(
        update={
            "status": combined,
            "reason": reason,
            "blueprintRepairs": outcome.repairs,
            "blueprintPasses": outcome.passes,
        }
    )

    # Surface the post-repair critic on the FINAL quality-result.json so the
    # artefakt is honest about the improved copy (only when a patch landed).
    if outcome.final_critic is not None:
        final_quality = final_quality.model_copy(
            update={"critic": outcome.final_critic}
        )

    if run_dir is not None:
        append_blueprint_repair_trace_event(
            run_dir, run_id or "unknown", outcome
        )

    return final_quality, repair_result
