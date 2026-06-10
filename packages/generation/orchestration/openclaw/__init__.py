"""OpenClaw Core V0 for the orchestration layer (KÖR-o2).

The "brain" on top of the two existing orchestration halves: it composes the
deterministic router (KÖR-6a, ``packages/generation/orchestration/router/``)
and the read-only Context Assembler (KÖR-7a, ``.../context/``) into a single
transient ``OpenClawDecision`` and picks exactly one of four V0 actions:
``answer_only`` / ``clarification`` / ``plan_only`` / ``patch_plan_request``
(docs/heavy-llm-flow/kor-o1-openclaw-core-contract.md).

V0 is as read-only as the two halves it binds: it never builds, never writes
a file, never starts a preview, never runs shell, and never touches
``current.json``. It proposes; it does not act. ``OpenClawDecision`` is a
transient object (like ``RouterDecision`` / ``AssembledContext``) and is
never persisted as a canonical artefakt.

Public API:
    decide(router, context) -> OpenClawDecision          # the V0 core
    orchestrate(message, ...) -> OpenClawDecision         # classify+assemble+decide
    OpenClawDecision, OpenClawAction, PatchPlanRequest, ToolCall

F1 slice 1 (conductor role contracts + conversation classification):
    ROLE_CONTRACTS, RoleContract, Role, RoleDirectiveKind
    contract_for_role(role) / role_for_edit_kind(edit_kind)
    classify_conversation(message, ...) -> ConversationDecision
    ConversationDecision, ConversationKind
"""

from .core import decide, orchestrate
from .models import OpenClawAction, OpenClawDecision, PatchPlanRequest, ToolCall
from .roles import (
    ROLE_CONTRACTS,
    ConversationDecision,
    ConversationKind,
    Role,
    RoleContract,
    RoleDirectiveKind,
    classify_conversation,
    contract_for_role,
    role_for_edit_kind,
)

__all__ = [
    "ROLE_CONTRACTS",
    "ConversationDecision",
    "ConversationKind",
    "OpenClawAction",
    "OpenClawDecision",
    "PatchPlanRequest",
    "Role",
    "RoleContract",
    "RoleDirectiveKind",
    "ToolCall",
    "classify_conversation",
    "contract_for_role",
    "decide",
    "orchestrate",
    "role_for_edit_kind",
]
