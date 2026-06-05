"""Pydantic types for OpenClaw Core V0 (KÖR-o2).

OpenClaw Core is the "brain" that binds the two existing halves of the
orchestration layer together: the deterministic router (KÖR-6a, what a
message *is*) and the read-only Context Assembler (KÖR-7a, what was *read*
to understand it). It composes them into a single transient
``OpenClawDecision`` and picks exactly one of four V0 actions
(docs/heavy-llm-flow/kor-o1-openclaw-core-contract.md).

Nothing here is a new canonical artefakt: ``OpenClawDecision`` is a
transient object exactly like ``RouterDecision`` and ``AssembledContext`` -
it is returned to the caller and never persisted as its own file. The
field names are camelCase on purpose so they mirror the contract shape in
kor-o1; the embedded ``router`` / ``context`` keep their own contracts.

V0 honesty contract (kor-o1 "Mål" + 04 §9):
- V0 never builds, never writes a file, never starts a preview, never runs
  shell, never touches ``current.json``. It proposes; it does not act.
- ``appliedVisibleEffect`` is therefore *always* ``False`` and is forced so
  by a validator below - V0 cannot fabricate a visible change.
- ``toolCalls`` and ``capability`` carry the full contract shape so the
  later patch-flow (kor-o3) needs no schema change, but in V0 they default
  to an empty list / ``None`` and V0 never acts on them.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..context.models import AssembledContext
from ..router.models import RouterDecision

__all__ = [
    "OpenClawAction",
    "OpenClawDecision",
    "PatchPlanRequest",
    "ToolCall",
]

# Closed enum: the only actions OpenClaw Core V0 can take. Each turn is
# exactly one of these (kor-o1 "Ingen suddig gräns"). Build / patch-apply
# are deliberately absent - they belong to Nivå 2 (kor-7c onwards).
OpenClawAction = Literal[
    "answer_only",
    "clarification",
    "plan_only",
    "patch_plan_request",
]


class ToolCall(BaseModel):
    """A *proposed* tool call - never auto-run by V0.

    Distilled from the coach ``openclaw-mvp`` spike: every tool call always
    requires approval and V0 never executes it itself (kor-o1 "Tool-ytan").
    In V0 this list stays empty; it is here so the patch-flow slice can fill
    it without a schema change.
    """

    # validate_assignment re-runs the validators on post-construction assignment
    # so requiresApproval can never be muted to False after the fact (KÖR-o2 §6).
    model_config = ConfigDict(validate_assignment=True)

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    requiresApproval: bool = True
    reason: str = ""

    @field_validator("requiresApproval")
    @classmethod
    def _approval_is_mandatory(cls, value: bool) -> bool:  # noqa: FBT001
        # A proposed tool call can never be marked auto-runnable in V0.
        return True


class PatchPlanRequest(BaseModel):
    """An honest "a patch is needed but the OpenClaw action-bridge is missing" marker.

    Set only for an ``edit_instruction`` in V0: the patch planner -> apply ->
    targeted render chain exists (kor-7b/7c/7d, all merged), but the OpenClaw
    action-bridge that would drive it *from an OpenClaw decision* does not, so V0
    returns this instead of faking a success (kor-o1 "Tool-ytan" + 04 §9).
    ``status`` and ``blockedBy`` are plain strings so a later slice can report a
    different status (e.g. once the action-bridge lands) without a schema change.
    """

    targetSummary: str = ""
    status: str = "action_bridge_missing"
    blockedBy: str | None = "openclaw-action-bridge"


class OpenClawDecision(BaseModel):
    """The transient decision OpenClaw Core returns for one user message.

    It *composes* the existing types - it invents no new enums (kor-o1
    "Kontraktet"): ``router`` is the unchanged KÖR-6a ``RouterDecision`` and
    ``context`` is the unchanged KÖR-7a ``AssembledContext``. ``action`` is
    the only genuinely new thing, and it is transient.

    Exactly one of the result fields is meaningful per ``action``:
    ``answer`` for ``answer_only``, ``clarifyingQuestion`` for
    ``clarification``, ``plan`` for ``plan_only``, and ``patchPlanRequest``
    for     ``patch_plan_request``. ``rationale`` is a short trace/observability
    line, never customer copy.
    """

    # validate_assignment re-runs the validators on post-construction assignment
    # so appliedVisibleEffect can never be muted to True after the fact (KÖR-o2 §6).
    model_config = ConfigDict(validate_assignment=True)

    router: RouterDecision
    context: AssembledContext
    action: OpenClawAction
    answer: str | None = None
    clarifyingQuestion: str | None = None
    plan: list[str] = Field(default_factory=list)
    patchPlanRequest: PatchPlanRequest | None = None
    toolCalls: list[ToolCall] = Field(default_factory=list)
    capability: str | None = None
    appliedVisibleEffect: bool = False
    rationale: str = ""

    @field_validator("appliedVisibleEffect")
    @classmethod
    def _v0_never_applies(cls, value: bool) -> bool:  # noqa: FBT001
        # V0 changes nothing, so a visible effect can never be claimed. This
        # is forced here (not just defaulted) so no caller can fabricate one.
        return False
