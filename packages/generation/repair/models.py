"""Pydantic types for Repair Pipeline output.

Locked by ADR 0015 (Sprint 3A) and extended in ADR 0016 (Sprint 3B):
``qualityStatusBefore`` / ``qualityStatusAfter`` / ``iterations`` carry
the sandwich-loop telemetry (mechanical fix -> re-run Quality Gate ->
mechanical fix -> ...). Fields default to ``None`` / ``0`` so Sprint 3A
consumers and the dev-generate mock pipeline that never re-runs the
gate keep round-tripping unchanged.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from packages.generation.quality_gate import QualityStatus

RepairStatus = Literal[
    "not-needed",
    "no-fix-applied",
    "fixed",
    "partial-fix",
]


class RepairFix(BaseModel):
    """One repair attempt.

    Sprint 3A v1 never produced RepairFix entries (no-op pipeline).
    Sprint 3B emits one entry per mechanical fix attempt; Sprint 5+
    will emit one entry per LLM-fix call.

    ``success=False`` records that a fix was attempted but could not be
    applied (e.g. ``ensure-default-export`` could not find an exportable
    symbol to default-export). ``detail`` carries the operator-facing
    explanation; the registry id of the fix is in ``name`` (see
    ``governance/policies/fix-registry.v1.json:mechanicalFixes[].id``).
    """

    kind: Literal["mechanical", "llm"]
    name: str
    target: str
    detail: str = ""
    success: bool = True


class RepairResult(BaseModel):
    """Aggregated Repair Pipeline output.

    ``status`` rules:
      - ``not-needed`` when QualityResult.status was ``ok``.
      - ``no-fix-applied`` when QualityResult had failures but Repair
        Pipeline had no applicable mechanical or LLM fixes (Sprint 3A
        v1 default; Sprint 3B keeps using this when a finding does not
        match any registered fix).
      - ``fixed`` when the sandwich loop drove QualityResult to ``ok``
        after applying mechanical fixes.
      - ``partial-fix`` when at least one mechanical fix succeeded but
        the gate still reports ``degraded`` or ``failed`` after re-run
        (Sprint 3B+ - some findings repaired, some remain).

    ``remainingErrors`` mirrors what could not be fixed so build-result.
    json can surface them to operators. After a sandwich pass, this
    list reflects the *post-repair* gate findings, not the pre-repair
    ones.

    ``qualityStatusBefore`` / ``qualityStatusAfter`` capture the gate
    status at the start of repair and after the final re-run. They are
    optional so Sprint 3A callers (and the dev-generate mock pipeline,
    which never re-runs the gate) keep working without changes.

    ``iterations`` records how many sandwich passes the loop executed.
    Bounded by the fix-registry policy
    (``loopLimits.maxTotalSandwichPasses``); when the cap is reached
    the run is marked ``partial-fix`` (or ``no-fix-applied`` if the
    last pass produced no fixes), per the registry's
    ``mark-degraded-and-emit-engine-event`` abortBehavior.
    """

    status: RepairStatus
    reason: str = ""
    mechanicalFixesApplied: list[RepairFix] = Field(default_factory=list)
    llmFixesApplied: list[RepairFix] = Field(default_factory=list)
    remainingErrors: list[str] = Field(default_factory=list)
    qualityStatusBefore: QualityStatus | None = None
    qualityStatusAfter: QualityStatus | None = None
    iterations: int = 0
