"""Phase 3 Repair Pipeline: act on Quality Gate findings.

Public API:
    run_repair_pipeline(quality_result, *, target_dir, do_repair=True)
        -> RepairResult
        Sprint 3A v1 is honest about its scope: when QualityResult is
        ok the result is ``not-needed``; when something failed the
        result is ``no-fix-applied`` with a structured payload of what
        could not be fixed mechanically. ``mechanicalFixesApplied`` and
        ``llmFixesApplied`` are always empty in v1.

    RepairResult, RepairFix
        Pydantic types locked by ADR 0015 so Sprint 3B can plug
        mechanical fixes into ``mechanicalFixesApplied`` and Sprint 5+
        can plug LLM-fix calls into ``llmFixesApplied`` without
        breaking callers.

The pipeline never crashes on a soft Quality Gate failure - that is
the point of having a Repair phase. Hard failures (exceptions raised
during repair attempts) propagate to the orchestrator.
"""

from .models import RepairFix, RepairResult, RepairStatus
from .repair import run_repair_pipeline

__all__ = [
    "RepairFix",
    "RepairResult",
    "RepairStatus",
    "run_repair_pipeline",
]
