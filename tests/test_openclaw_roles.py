"""Tests for OpenClaw F1 slice 1: conductor role contracts + conversation kind.

Two things are locked here:

1. The four conductor role contracts (router / section_builder / stylist /
   copy) - their input (acceptsEditKinds) / output (producesDirectives)
   contracts and the EditKind -> role mapping (section_add -> section_builder,
   visual_style -> stylist, copy_change -> copy). The contracts are frozen
   dataclasses, so a caller can read but never mutate them.

2. The additive conversation classification on top of the deterministic
   router: at least eight Swedish conversation examples (jokes, opinions,
   questions) classify into the conductor conversation kinds, while edit
   prompts ("gör sajten mörkblå", "lägg till öppettider överst", ...) STILL
   classify as edit. It composes the router; it never mutates the router's
   locked eight-kind messageKind enum.

Everything runs without OPENAI_API_KEY and is fully deterministic; no LLM is
involved (no-key parity is asserted explicitly, mirroring briefModel).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.openclaw import (  # noqa: E402
    ROLE_CONTRACTS,
    ConversationDecision,
    Role,
    RoleContract,
    classify_conversation,
    contract_for_role,
    role_for_edit_kind,
)
from packages.generation.orchestration.router import (  # noqa: E402
    classify_message,
)
from packages.generation.orchestration.router.models import (  # noqa: E402
    MessageKind,
)

# The router's locked eight messageKind values (kept in sync with
# tests/test_router_schema.py::test_message_kind_enum_is_locked). The
# conversation layer must never emit a router kind outside this set - it
# composes the router, it does not extend the enum.
_LOCKED_ROUTER_KINDS = {
    "answer_only",
    "site_review",
    "edit_instruction",
    "component_discovery",
    "reference_analysis",
    "bug_report",
    "multi_intent",
    "unclear",
}

_CONVERSATION_KINDS = {"small_talk", "site_opinion", "question", "edit", "other"}


# ---------------------------------------------------------------------------
# 1. Role contract locks
# ---------------------------------------------------------------------------


def test_exactly_the_four_named_roles_exist():
    """The registry holds exactly the four conductor roles the plan names."""
    assert set(ROLE_CONTRACTS) == {"router", "section_builder", "stylist", "copy"}


@pytest.mark.parametrize(
    ("role", "accepts", "produces"),
    [
        ("section_builder", ("section_add",), ("section_add",)),
        ("stylist", ("visual_style",), ("visual_style",)),
        ("copy", ("copy_change",), ("copy_change",)),
    ],
)
def test_editing_role_input_output_contract(
    role: Role, accepts: tuple[str, ...], produces: tuple[str, ...]
):
    """Each editing role locks its input (acceptsEditKinds) + output directive."""
    contract = contract_for_role(role)
    assert contract.acceptsEditKinds == accepts
    assert contract.producesDirectives == produces
    assert contract.accepts(accepts[0]) is True
    assert contract.produces(produces[0]) is True
    # A role never claims a directive it does not own.
    assert contract.produces("layout_change") is False


def test_router_role_dispatches_and_produces_no_directive():
    """The router role is the dispatcher: it accepts/produces no directive."""
    contract = contract_for_role("router")
    assert contract.acceptsEditKinds == ()
    assert contract.producesDirectives == ()


@pytest.mark.parametrize(
    ("edit_kind", "expected_role"),
    [
        ("section_add", "section_builder"),
        ("visual_style", "stylist"),
        ("copy_change", "copy"),
        # Edit kinds no role owns in this slice -> None (honest surface).
        ("component_add", None),
        ("component_remove", None),
        ("layout_change", None),
        ("route_add", None),
        ("none", None),
    ],
)
def test_role_for_edit_kind_mapping(edit_kind: str, expected_role: str | None):
    assert role_for_edit_kind(edit_kind) == expected_role


def test_role_contracts_are_frozen():
    """Contracts are immutable - a caller can read but not mutate them."""
    contract = contract_for_role("stylist")
    assert isinstance(contract, RoleContract)
    with pytest.raises(dataclasses.FrozenInstanceError):
        contract.status = "planned"  # type: ignore[misc]


def test_each_produced_directive_maps_back_to_its_role():
    """producesDirectives and role_for_edit_kind agree (no contradiction)."""
    for role, contract in ROLE_CONTRACTS.items():
        for directive in contract.producesDirectives:
            assert role_for_edit_kind(directive) == role


# ---------------------------------------------------------------------------
# 2. Conversation classification - at least 8 Swedish examples
# ---------------------------------------------------------------------------

_CONVERSATION_EXAMPLES: list[tuple[str, str]] = [
    # small talk / jokes / greetings
    ("dra ett skämt", "small_talk"),
    ("berätta ett skämt om hantverkare", "small_talk"),
    ("hej, hur är läget?", "small_talk"),
    ("tjena, vad heter du?", "small_talk"),
    # opinion / omdöme about the site
    ("vad tycker du om sajten?", "site_opinion"),
    ("är min hemsida snygg?", "site_opinion"),
    ("ge mig feedback på designen", "site_opinion"),
    # plain questions
    ("är det här bra för tandläkare?", "question"),
    ("vad kostar en hemsida?", "question"),
    ("vilka typer av sektioner finns?", "question"),
]


@pytest.mark.parametrize(("message", "expected"), _CONVERSATION_EXAMPLES)
def test_conversation_kind_classification(message: str, expected: str):
    decision = classify_conversation(message)
    assert isinstance(decision, ConversationDecision)
    assert decision.conversationKind == expected
    # A conversation (not an edit) is answered by the dispatcher, no role edit.
    assert decision.role == "router"


def test_at_least_eight_swedish_conversation_examples_covered():
    """Guard the slice acceptance: >= 8 non-edit conversation examples."""
    non_edit = [m for m, kind in _CONVERSATION_EXAMPLES if kind != "edit"]
    assert len(non_edit) >= 8
    # And all three conversation intents are represented.
    covered = {kind for _, kind in _CONVERSATION_EXAMPLES}
    assert {"small_talk", "site_opinion", "question"}.issubset(covered)


# ---------------------------------------------------------------------------
# 3. Edit prompts STILL classify as edit (the non-negotiable guarantee)
# ---------------------------------------------------------------------------

_EDIT_EXAMPLES: list[tuple[str, str | None]] = [
    # message -> expected owning role (None when no role owns the edit kind yet)
    ("gör sajten mörkblå", "stylist"),
    ("gör sidan mörkare och mer premium", "stylist"),
    ("lägg till en faq-sektion", "section_builder"),
    ("lägg till en sektion om garantier", "section_builder"),
    ("skriv om rubriken till något kortare", "copy"),
    ("ändra texten i hero-sektionen", "copy"),
    # component_add / layout etc. are still edits, just not owned by a role here
    ("lägg till öppettider överst", None),
    ("lägg en klocka i andra sektionen till vänster", None),
]


@pytest.mark.parametrize(("message", "expected_role"), _EDIT_EXAMPLES)
def test_edit_prompts_still_classify_as_edit(message: str, expected_role: str | None):
    decision = classify_conversation(message)
    assert decision.conversationKind == "edit", (
        f"{message!r} must stay an edit, got {decision.conversationKind}"
    )
    assert decision.role == expected_role
    assert decision.editKind != "none"


def test_multi_intent_edit_is_still_edit():
    """A multi-intent that contains an edit stays an edit (first edit's role)."""
    decision = classify_conversation(
        "gör sidan mer premium, lägg en klocka i andra sektionen, "
        "ändra inte texterna"
    )
    assert decision.messageKind == "multi_intent"
    assert decision.conversationKind == "edit"
    # First actionable subtask is the style change -> stylist.
    assert decision.role == "stylist"


def test_reference_is_not_misread_as_edit_or_conversation():
    """A do-not-copy reference is 'other', not a faked edit or chit-chat."""
    decision = classify_conversation("samma klocka som på aftonbladet.se")
    assert decision.messageKind == "reference_analysis"
    assert decision.conversationKind == "other"


# ---------------------------------------------------------------------------
# 3b. B177: greeting/question-mark must never hijack the classification
# ---------------------------------------------------------------------------


def test_b177_greeting_plus_opinion_is_site_opinion():
    """A polite opinion ("hej, vad tycker du om sajten?") keeps its site
    context: site_opinion, never small_talk (the greeting cue must not win)."""
    decision = classify_conversation("hej, vad tycker du om sajten?")
    assert decision.conversationKind == "site_opinion"
    assert decision.role == "router"


def test_b177_greeting_plus_bug_report_is_other():
    """A greeted bug report ("hallå, sidan funkar inte") is never answered as
    chit-chat: bug_report has its own downstream handling -> other."""
    decision = classify_conversation("hallå, sidan funkar inte")
    assert decision.messageKind == "bug_report"
    assert decision.conversationKind == "other"


def test_b177_bug_report_label_is_greeting_invariant():
    """The same bug report classifies identically with and without a greeting
    (the B177 repro: only the greeting flipped the label)."""
    plain = classify_conversation("sidan funkar inte")
    greeted = classify_conversation("hallå, sidan funkar inte")
    assert plain.messageKind == greeted.messageKind == "bug_report"
    assert plain.conversationKind == greeted.conversationKind == "other"


def test_b177_question_mark_does_not_relabel_bug_report():
    """A '?'-terminated bug report stays 'other' (never the question branch)."""
    decision = classify_conversation("varför funkar inte sidan?")
    assert decision.messageKind == "bug_report"
    assert decision.conversationKind == "other"


def test_b177_question_mark_does_not_relabel_reference():
    """A '?'-terminated reference stays 'other' (never the question branch)."""
    decision = classify_conversation("samma klocka som på aftonbladet.se?")
    assert decision.messageKind == "reference_analysis"
    assert decision.conversationKind == "other"


def test_b177_pure_greeting_is_still_small_talk():
    """A greeting without site/opinion content keeps its small-talk label."""
    decision = classify_conversation("hallå, hur mår du?")
    assert decision.conversationKind == "small_talk"


# ---------------------------------------------------------------------------
# 4. No-key parity + determinism (mirrors briefModel)
# ---------------------------------------------------------------------------


def test_no_key_parity_source_is_mock_no_key(monkeypatch: pytest.MonkeyPatch):
    """Without OPENAI_API_KEY the source mirrors briefModel's mock-no-key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    decision = classify_conversation("dra ett skämt")
    assert decision.source == "mock-no-key"
    assert decision.conversationKind == "small_talk"


def test_source_is_heuristic_when_key_present(monkeypatch: pytest.MonkeyPatch):
    """With a key but no model_fallback, the deterministic path is used.

    model_fallback defaults to False, so no network/LLM call is made; the
    source is 'heuristic' (not the routerModel fallback).
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    decision = classify_conversation("vad tycker du om sajten?")
    assert decision.source == "heuristic"
    assert decision.conversationKind == "site_opinion"


def test_classification_is_deterministic():
    first = classify_conversation("dra ett skämt")
    second = classify_conversation("dra ett skämt")
    assert first == second


# ---------------------------------------------------------------------------
# 5. Additivity: composes the router, never extends its locked enum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [m for m, _ in _CONVERSATION_EXAMPLES] + [m for m, _ in _EDIT_EXAMPLES],
)
def test_messagekind_stays_inside_locked_router_enum(message: str):
    """conversationKind is additive: messageKind never leaves the locked 8."""
    decision = classify_conversation(message)
    assert decision.messageKind in _LOCKED_ROUTER_KINDS
    assert decision.conversationKind in _CONVERSATION_KINDS
    # The conductor carries the router's own messageKind verbatim.
    assert decision.messageKind == classify_message(message).messageKind


def test_message_kind_type_still_has_exactly_eight_values():
    """The router MessageKind Literal is untouched (8 values, no new ones)."""
    import typing

    assert set(typing.get_args(MessageKind)) == _LOCKED_ROUTER_KINDS
