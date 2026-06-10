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
    ANSWER_ONLY_CONVERSATION_KINDS,
    ROLE_CONTRACTS,
    SECTION_ADD_SKILL,
    ConversationDecision,
    Role,
    RoleContract,
    classify_conversation,
    contract_for_role,
    role_for_edit_kind,
    skill_for_edit_kind,
)
from packages.generation.orchestration.router import (  # noqa: E402
    classify_message,
)
from packages.generation.orchestration.router.models import (  # noqa: E402
    MessageKind,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

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
# 1b. F1 slice 3: role-driven dispatch reads RoleContract.skill
# ---------------------------------------------------------------------------


def test_section_add_skill_constant_matches_contract():
    """SECTION_ADD_SKILL is read from the section_builder contract (not
    hardcoded) and is the section-add SKILL.md path the chain dispatches on."""
    assert SECTION_ADD_SKILL == contract_for_role("section_builder").skill
    assert SECTION_ADD_SKILL == "skills/section-add/SKILL.md"
    assert SECTION_ADD_SKILL  # non-empty


@pytest.mark.parametrize(
    ("edit_kind", "expected_skill"),
    [
        ("section_add", "skills/section-add/SKILL.md"),
        ("visual_style", "skills/restyle/SKILL.md"),
        ("copy_change", "skills/copy-change/SKILL.md"),
        # Edit kinds no role owns in this slice -> None (honest surface).
        ("component_add", None),
        ("component_remove", None),
        ("layout_change", None),
        ("route_add", None),
    ],
)
def test_skill_for_edit_kind_maps_role_skill(
    edit_kind: str, expected_skill: str | None
):
    """skill_for_edit_kind resolves the owning role and returns its
    RoleContract.skill (the conductor bridge editKind -> skill)."""
    assert skill_for_edit_kind(edit_kind) == expected_skill


def test_skill_for_edit_kind_agrees_with_role_contracts():
    """For every editing role, skill_for_edit_kind(directive) equals the role's
    own contract skill (no drift between the helper and the contracts)."""
    for _role, contract in ROLE_CONTRACTS.items():
        for directive in contract.producesDirectives:
            assert skill_for_edit_kind(directive) == contract.skill


def test_router_role_has_no_skill():
    """The router dispatcher owns no editing directive and declares no skill."""
    assert contract_for_role("router").skill == ""


@pytest.mark.parametrize("edit_kind", [None, "", "none"])
def test_skill_for_edit_kind_is_defensive(edit_kind):
    """decision.editKind can be 'none'/missing: skill_for_edit_kind must return
    None and never raise (adjustment 3b)."""
    assert skill_for_edit_kind(edit_kind) is None


def test_section_add_dispatch_is_equivalent_to_old_edit_kind_gate():
    """The role-driven gate (skill == SECTION_ADD_SKILL) is byte-for-byte
    equivalent to the old `editKind == "section_add"` gate: ONLY section_add
    maps to the section-add skill, every other kind does not."""
    all_edit_kinds = [
        "section_add", "visual_style", "copy_change", "component_add",
        "component_remove", "layout_change", "route_add", "none",
    ]
    for edit_kind in all_edit_kinds:
        role_driven = skill_for_edit_kind(edit_kind) == SECTION_ADD_SKILL
        old_gate = edit_kind == "section_add"
        assert role_driven == old_gate, edit_kind


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
# 2b. F1 slice 3 (Scout #262): expectsAnswer signal
# ---------------------------------------------------------------------------


def test_answer_only_conversation_kinds_constant_is_locked():
    """The expectsAnswer source-of-truth set is exactly the three chat kinds."""
    assert ANSWER_ONLY_CONVERSATION_KINDS == (
        "small_talk", "site_opinion", "question",
    )


@pytest.mark.parametrize(("message", "expected"), _CONVERSATION_EXAMPLES)
def test_conversation_kinds_expect_an_answer(message: str, expected: str):
    """small_talk / site_opinion / question expect a chat answer (no build)."""
    decision = classify_conversation(message)
    assert decision.expectsAnswer is True
    assert decision.conversationKind in ANSWER_ONLY_CONVERSATION_KINDS


def test_other_kinds_do_not_expect_an_answer():
    """`other` (reference/bug/unclear) has its own downstream handling: it is
    not a chat answer, so expectsAnswer is False."""
    reference = classify_conversation("samma klocka som på aftonbladet.se")
    assert reference.conversationKind == "other"
    assert reference.expectsAnswer is False
    bug = classify_conversation("hallå, sidan funkar inte")
    assert bug.conversationKind == "other"
    assert bug.expectsAnswer is False


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


@pytest.mark.parametrize(("message", "_expected_role"), _EDIT_EXAMPLES)
def test_edit_prompts_do_not_expect_an_answer(message: str, _expected_role):
    """An edit is built/no-op'd by the chain, never a chat answer (F1 slice 3)."""
    decision = classify_conversation(message)
    assert decision.conversationKind == "edit"
    assert decision.expectsAnswer is False


def test_expects_answer_matches_conversation_kind_membership():
    """expectsAnswer is exactly membership of ANSWER_ONLY_CONVERSATION_KINDS
    across both conversation and edit examples (F1 slice 3)."""
    for message, _ in _CONVERSATION_EXAMPLES + _EDIT_EXAMPLES:
        decision = classify_conversation(message)
        assert decision.expectsAnswer == (
            decision.conversationKind in ANSWER_ONLY_CONVERSATION_KINDS
        )


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
# 3b. B181: greeting/question-mark must never hijack the classification
# ---------------------------------------------------------------------------


def test_B181_greeting_plus_opinion_is_site_opinion():
    """A polite opinion ("hej, vad tycker du om sajten?") keeps its site
    context: site_opinion, never small_talk (the greeting cue must not win)."""
    decision = classify_conversation("hej, vad tycker du om sajten?")
    assert decision.conversationKind == "site_opinion"
    assert decision.role == "router"


def test_B181_greeting_plus_bug_report_is_other():
    """A greeted bug report ("hallå, sidan funkar inte") is never answered as
    chit-chat: bug_report has its own downstream handling -> other."""
    decision = classify_conversation("hallå, sidan funkar inte")
    assert decision.messageKind == "bug_report"
    assert decision.conversationKind == "other"


def test_B181_bug_report_label_is_greeting_invariant():
    """The same bug report classifies identically with and without a greeting
    (the B181 repro: only the greeting flipped the label)."""
    plain = classify_conversation("sidan funkar inte")
    greeted = classify_conversation("hallå, sidan funkar inte")
    assert plain.messageKind == greeted.messageKind == "bug_report"
    assert plain.conversationKind == greeted.conversationKind == "other"


def test_B181_question_mark_does_not_relabel_bug_report():
    """A '?'-terminated bug report stays 'other' (never the question branch)."""
    decision = classify_conversation("varför funkar inte sidan?")
    assert decision.messageKind == "bug_report"
    assert decision.conversationKind == "other"


def test_B181_question_mark_does_not_relabel_reference():
    """A '?'-terminated reference stays 'other' (never the question branch)."""
    decision = classify_conversation("samma klocka som på aftonbladet.se?")
    assert decision.messageKind == "reference_analysis"
    assert decision.conversationKind == "other"


def test_B181_pure_greeting_is_still_small_talk():
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


# --- 2026-06-10 (extern granskning, GPT-fynd 2): frågeformade edits ----------
#
# En artigt frågeformad edit ("kan du lägga till en FAQ-sektion?") klassades
# som answer-only question i stället för edit, eftersom routerns _ADD_VERBS
# bara bar imperativformerna ("lägg till") - infinitivets "lägga till"
# (ordgräns: "lägg" matchar inte "lägga") föll igenom till ?-grenen. En
# användare som BAD om en sektion fick ett chat-svar och inget bygge.


@pytest.mark.parametrize(
    ("message", "expected_edit_kind"),
    [
        ("kan du lägga till en FAQ-sektion?", "section_add"),
        ("skulle du kunna lägga till en team-sektion?", "section_add"),
        ("kan du göra sajten mörkblå?", "visual_style"),
        ("kan du ändra rubriken till Ny rubrik?", "copy_change"),
    ],
)
def test_question_formed_edits_classify_as_edit(
    message: str, expected_edit_kind: str
):
    """Edit vinner över frågetecknet: en frågeformad edit bygger, svaras inte."""
    decision = classify_conversation(message)
    assert decision.conversationKind == "edit", message
    assert decision.editKind == expected_edit_kind, message
    assert decision.expectsAnswer is False, message


@pytest.mark.parametrize(
    ("message", "expected_kind"),
    [
        # Genuina frågor/småprat får INTE bli edits av infinitiv-tillägget.
        ("vad är en FAQ-sektion?", "question"),
        ("hej, hur är läget?", "small_talk"),
        ("vad tycker du om sajten?", "site_opinion"),
    ],
)
def test_genuine_conversation_stays_answer_only_after_infinitive_verbs(
    message: str, expected_kind: str
):
    decision = classify_conversation(message)
    assert decision.conversationKind == expected_kind, message
    assert decision.expectsAnswer is True, message
