"""Pydantic types for Repair Pipeline output.

Locked by ADR 0015 so future sprints can plug in mechanical fixes and
LLM-fix calls without changing the consumer-facing shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RepairStatus = Literal[
    "not-needed",
    "no-fix-applied",
    "fixed",
    "partial-fix",
]


class RepairFix(BaseModel):
    """One repair attempt.

    Sprint 3A v1 never produces RepairFix entries - the repair pipeline
    is no-op for now. Future sprints emit one entry per mechanical fix
    (autoadd default export, autoinsert missing import, etc.) or one
    entry per LLM-fix call.
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
        v1 default).
      - ``fixed`` when all reported failures were fixed (future).
      - ``partial-fix`` when some failures were fixed but others
        remain (future).

    ``remainingErrors`` mirrors what could not be fixed so build-result.
    json can surface them to operators.
    """

    status: RepairStatus
    reason: str = ""
    mechanicalFixesApplied: list[RepairFix] = Field(default_factory=list)
    llmFixesApplied: list[RepairFix] = Field(default_factory=list)
    remainingErrors: list[str] = Field(default_factory=list)
