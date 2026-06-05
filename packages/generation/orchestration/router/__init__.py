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

An optional LLM fallback (KÖR-6b, ``routerModel``) sits on top of the
heuristic via ``classify_message_with_llm_fallback``: it only escalates
``unclear`` / long / complex ``multi_intent`` messages to the model, returns the
same ``RouterDecision`` contract, and is identical to KÖR-6a without an
``OPENAI_API_KEY`` (no regression). ``shouldStartPreview`` is always recomputed
deterministically so the model can never start a build/preview it should not.

Public API:
    classify_message(message, *, context=None) -> RouterDecision
    classify_message_with_llm_fallback(message, *, context=None, ...) -> RouterDecision
    log_router_decision_to_existing_run(run_dir, decision, *, run_id=None) -> bool
    RouterDecision, RouterContext, RouterTarget, RouterReference, RouterSubtask
    MessageKind, EditKind, BuildRequirement, ContextLevel
"""

from .classify import classify_message
from .llm_fallback import (
    RouterModelResolutionError,
    classify_message_with_llm_fallback,
    has_openai_api_key,
    needs_llm_fallback,
    resolve_router_model,
)
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
    "RouterModelResolutionError",
    "RouterReference",
    "RouterSubtask",
    "RouterTarget",
    "classify_message",
    "classify_message_with_llm_fallback",
    "has_openai_api_key",
    "log_router_decision_to_existing_run",
    "needs_llm_fallback",
    "resolve_router_model",
]
