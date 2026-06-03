"""Deterministic message router for the orchestration layer (KÖR-6a).

Working name "OpenClaw Router" (docs/heavy-llm-flow/02). It sits on top of
init/follow-up and turns a single user message into a structured decision:
what kind of message it is (``messageKind``) and how much the system must
do (``buildRequirement``), plus context level, target, constraints and a
single ``shouldStartPreview`` actuation flag.

Hard guarantees of this slice:
- No LLM, no model role, no OpenAI call - pure Unicode-aware heuristics.
- No file changes to the generated site, no build, no PreviewRuntime for
  ``answer_only`` / ``plan_only``.
- Read-only: classification never touches disk. The only disk write is
  ``log_router_decision_to_existing_run``, which appends to an *existing*
  run's trace.ndjson and never creates a run.

Public API:
    classify_message(message, *, context=None) -> RouterDecision
    log_router_decision_to_existing_run(run_dir, decision, *, run_id=None) -> bool
    RouterDecision, RouterContext, RouterTarget, RouterReference, RouterSubtask
    MessageKind, EditKind, BuildRequirement, ContextLevel
"""

from .classify import classify_message
from .models import (
    BuildRequirement,
    ContextLevel,
    EditKind,
    MessageKind,
    RouterContext,
    RouterDecision,
    RouterReference,
    RouterSubtask,
    RouterTarget,
)
from .trace import log_router_decision_to_existing_run

__all__ = [
    "BuildRequirement",
    "ContextLevel",
    "EditKind",
    "MessageKind",
    "RouterContext",
    "RouterDecision",
    "RouterReference",
    "RouterSubtask",
    "RouterTarget",
    "classify_message",
    "log_router_decision_to_existing_run",
]
