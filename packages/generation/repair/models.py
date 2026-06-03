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


class BlueprintRepair(BaseModel):
    """One blueprint-repair attempt (kor-5).

    Records a single ``repairModel``-proposed edit to a NAMED, already-existing
    blueprint field (``contentBlocks`` on the Generation Package / ``conversion``
    on the Site Brief) in response to a deterministic critic issue. The LLM only
    ever proposes copy for fields that already exist; it never writes free files.

    ``success=False`` records a proposal that was received during a real repair
    run but rejected by the rails / grounding guard / schema check BEFORE apply
    (``detail`` carries why). A missing API key or an unavailable model is NOT a
    failed repair - that path produces zero ``BlueprintRepair`` entries and a
    ``repair.blueprint_skipped`` trace event (kor-5 no-key contract).

    ``before`` / ``after`` hold the field value before and after the patch so
    ``repair-result.json`` is an honest audit trail. ``before`` may be empty
    when the field did not exist yet (e.g. a missing hero CTA).
    """

    issueType: str
    target: str
    field: str
    before: str = ""
    after: str = ""
    source: Literal["repairModel"] = "repairModel"
    success: bool = True
    detail: str = ""


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

    ``blueprintRepairs`` / ``passes`` carry the kor-5 blueprint-repair
    telemetry: one ``BlueprintRepair`` per repairModel proposal that was
    received during a real run (success or rejected-before-apply), and the
    number of bounded blueprint-repair passes executed (bounded by
    ``fix-registry.v1.json:blueprintRepair.maxPasses``, default 1). Both
    default empty/0 so every existing mechanical-only caller round-trips
    unchanged; the fields populate only when a Generation Package + critic
    issues are threaded into ``execute_phase3_quality_and_repair``.
    """

    status: RepairStatus
    reason: str = ""
    mechanicalFixesApplied: list[RepairFix] = Field(default_factory=list)
    llmFixesApplied: list[RepairFix] = Field(default_factory=list)
    remainingErrors: list[str] = Field(default_factory=list)
    qualityStatusBefore: QualityStatus | None = None
    qualityStatusAfter: QualityStatus | None = None
    iterations: int = 0
    blueprintRepairs: list[BlueprintRepair] = Field(default_factory=list)
    passes: int = 0
