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

F1 slice 3 (role-driven dispatch + answer-only signal):
    skill_for_edit_kind(edit_kind) -> the SKILL.md path the owning role runs
    SECTION_ADD_SKILL                # the section_builder role's skill (dispatch key)
    ANSWER_ONLY_CONVERSATION_KINDS   # kinds the dispatcher answers (expectsAnswer)
    ConversationDecision.expectsAnswer

B155 follow-up (honest compound follow-ups):
    compute_unapplied_followup_chain_intents(decision, ...) -> bounded
    {target, reason} posts for compound subtasks no executor applied, surfaced
    through the existing unappliedFollowupIntents channel (no new mechanism).

Honest follow-up report (operator finding 2026-06-16):
    build_followup_report(decision, bridge) -> a short, grounded Swedish line
    that reflects how a follow-up was interpreted and what was done or why it
    was not. DETERMINISTIC (no LLM): the floor the seam carries on EVERY turn
    so an applied edit / honest no-op is never stum without OPENAI_API_KEY.
"""

from .core import decide, orchestrate
from .models import OpenClawAction, OpenClawDecision, PatchPlanRequest, ToolCall
from .report import build_followup_report
from .roles import (
    ANSWER_ONLY_CONVERSATION_KINDS,
    ROLE_CONTRACTS,
    SECTION_ADD_SKILL,
    ConversationDecision,
    ConversationKind,
    Role,
    RoleContract,
    RoleDirectiveKind,
    classify_conversation,
    contract_for_role,
    role_for_edit_kind,
    skill_for_edit_kind,
)
from .unapplied import compute_unapplied_followup_chain_intents

__all__ = [
    "ANSWER_ONLY_CONVERSATION_KINDS",
    "ROLE_CONTRACTS",
    "SECTION_ADD_SKILL",
    "ConversationDecision",
    "ConversationKind",
    "OpenClawAction",
    "OpenClawDecision",
    "PatchPlanRequest",
    "Role",
    "RoleContract",
    "RoleDirectiveKind",
    "ToolCall",
    "build_followup_report",
    "classify_conversation",
    "compute_unapplied_followup_chain_intents",
    "contract_for_role",
    "decide",
    "orchestrate",
    "role_for_edit_kind",
    "skill_for_edit_kind",
]
