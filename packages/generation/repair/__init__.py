"""Phase 3 Repair Pipeline: act on Quality Gate findings.

Public API:
    run_repair_pipeline(quality_result, *, target_dir, ...) -> RepairResult
        Sprint 3A v1 was honest about its scope (no fixes wired);
        Sprint 3B v1 ships ``ensure-default-export`` and the sandwich
        loop that re-runs Quality Gate after a mutation. The signature
        is backward compatible: callers that pass only ``quality_result``
        and ``target_dir`` keep the Sprint 3A behaviour (one apply-pass,
        no re-run). Pass ``required_routes`` / ``npm_steps`` /
        ``build_status`` / ``do_typecheck`` to enable the re-run.

    RepairResult, RepairFix, RepairStatus
        Pydantic types locked by ADR 0015 and extended in ADR 0016
        with ``qualityStatusBefore`` / ``qualityStatusAfter`` /
        ``iterations`` (sandwich-loop telemetry).

    MECHANICAL_FIXES, MechanicalFixSpec
        Static descriptors of the fixes ``run_repair_pipeline``
        dispatches over. Mirrors
        ``governance/policies/fix-registry.v1.json:mechanicalFixes``;
        tests assert the two stay in sync.

The pipeline never crashes on a soft Quality Gate failure - that is
the point of having a Repair phase. Hard failures (exceptions raised
during fix application) are caught inside the fix bodies and surfaced
as ``RepairFix(success=False, ...)`` so the orchestrator continues
producing a well-formed RepairResult.
"""

from .fixes import MECHANICAL_FIXES, MechanicalFixSpec
from .models import RepairFix, RepairResult, RepairStatus
from .orchestration import execute_phase3_quality_and_repair
from .repair import run_repair_pipeline

__all__ = [
    "MECHANICAL_FIXES",
    "MechanicalFixSpec",
    "RepairFix",
    "RepairResult",
    "RepairStatus",
    "execute_phase3_quality_and_repair",
    "run_repair_pipeline",
]
