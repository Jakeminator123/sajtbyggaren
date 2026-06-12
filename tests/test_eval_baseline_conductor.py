"""Deterministic conductor-classification regression baseline (no LLM, 0 kr).

Why this file exists
--------------------
The committed *golden-path* regression gate (``scripts/eval_gate.py`` +
``tests/test_eval_gate.py`` + ``tests/evals/golden-path-baseline.json``, landed in
PR #293) protects the deterministic *build* quality from silently regressing.
This file is its conductor-side companion: a single, consolidated regression
baseline for the deterministic *conductor classification* surface so a change to
the router / conversation heuristics that quietly reclassifies prompts trips a
red check instead of slipping through.

It composes the existing public OpenClaw orchestration API only - it adds no new
runtime code, no new canonical artefakt and no LLM call:

* ``classify_conversation`` / ``classify_message`` - the deterministic router +
  the additive conductor conversation label (``roles.py`` / ``router``).
* ``role_for_edit_kind`` - the EditKind -> conductor role map.
* ``compute_unapplied_followup_chain_intents`` - the honest "no executor owned
  this compound part" observer (``unapplied.py``).

No-key parity is a repo requirement (mirrors briefModel): every assertion holds
with ``OPENAI_API_KEY`` absent and the classification is deterministic. The
fixtures pin **today's public-API behaviour** and deliberately only assert on
owned edit kinds (section_add / visual_style / copy_change) and the clearly
*unowned* router edit kinds (component_remove / layout_change / route_add) whose
"no executor owns this" contract is stable - they never assert exact behaviour
for unknown/unregistered capability slugs.
"""

from __future__ import annotations

import sys
import typing
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.openclaw import (  # noqa: E402
    ANSWER_ONLY_CONVERSATION_KINDS,
    ConversationDecision,
    classify_conversation,
    compute_unapplied_followup_chain_intents,
    role_for_edit_kind,
)
from packages.generation.orchestration.router import (  # noqa: E402
    classify_message,
)
from packages.generation.orchestration.router.models import (  # noqa: E402
    MessageKind,
    RouterDecision,
    RouterSubtask,
    RouterTarget,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

# The router's locked eight messageKind values (kept in sync with
# tests/test_router_schema.py + tests/test_openclaw_roles.py). The conductor
# layer composes the router; it must never emit a kind outside this set.
_LOCKED_ROUTER_KINDS: frozenset[str] = frozenset(
    {
        "answer_only",
        "site_review",
        "edit_instruction",
        "component_discovery",
        "reference_analysis",
        "bug_report",
        "multi_intent",
        "unclear",
    }
)

_CONVERSATION_KINDS: frozenset[str] = frozenset(
    {"small_talk", "site_opinion", "question", "edit", "other"}
)


# ---------------------------------------------------------------------------
# 1. The conductor classification baseline: prompt -> (messageKind,
#    conversationKind, role). >= 15 fixtures covering small_talk / site_opinion
#    / question / edit-variants + the B181 greeting/?-invariant 'other' cases.
# ---------------------------------------------------------------------------

# Each row: (prompt, messageKind, conversationKind, role). These are the pinned
# deterministic outputs of the public API today; a heuristic change that moves
# any of them flips this baseline red.
_CONDUCTOR_BASELINE: tuple[tuple[str, str, str, str | None], ...] = (
    # -- small_talk (greetings / jokes / chit-chat) --
    ("dra ett skämt", "unclear", "small_talk", "router"),
    ("hej, hur är läget?", "answer_only", "small_talk", "router"),
    ("tjena, vad heter du?", "answer_only", "small_talk", "router"),
    ("berätta något roligt", "answer_only", "small_talk", "router"),
    # -- site_opinion (omdöme about the current site) --
    ("vad tycker du om sajten?", "site_review", "site_opinion", "router"),
    ("är min hemsida snygg?", "answer_only", "site_opinion", "router"),
    ("ge mig feedback på designen", "site_review", "site_opinion", "router"),
    # -- question (plain questions / discovery) --
    ("vad kostar en hemsida?", "answer_only", "question", "router"),
    ("vilka typer av sektioner finns?", "component_discovery", "question", "router"),
    ("är det här bra för tandläkare?", "answer_only", "question", "router"),
    # -- edit variants (owned + unowned-but-still-edit) --
    ("gör sajten mörkblå", "edit_instruction", "edit", "stylist"),
    ("lägg till en faq-sektion", "edit_instruction", "edit", "section_builder"),
    ("kan du lägga till en team-sektion?", "edit_instruction", "edit", "section_builder"),
    ("skriv om rubriken till något kortare", "edit_instruction", "edit", "copy"),
    # ADR 0057: component_add is now owned by component_builder (partial role).
    ("lägg till öppettider överst", "edit_instruction", "edit", "component_builder"),
    ("lägg en klocka i andra sektionen till vänster", "edit_instruction", "edit", "component_builder"),
    # A genuinely unowned edit kind still maps to role None (honest surface):
    # component_remove has no owning role in this slice.
    ("ta bort kontaktformuläret", "edit_instruction", "edit", None),
    # -- 'other' (own downstream handling) + B181 greeting/?-invariance --
    ("hej, vad tycker du om sajten?", "site_review", "site_opinion", "router"),
    ("hallå, sidan funkar inte", "bug_report", "other", "router"),
    ("varför funkar inte sidan?", "bug_report", "other", "router"),
    ("samma klocka som på aftonbladet.se", "reference_analysis", "other", "router"),
)


def test_baseline_has_at_least_fifteen_fixtures_and_full_coverage() -> None:
    """Lock the suite size + intent coverage so it can't silently shrink."""
    assert len(_CONDUCTOR_BASELINE) >= 15
    conversation_kinds = {ck for _p, _mk, ck, _role in _CONDUCTOR_BASELINE}
    # All four conversational intents + the edit passthrough are represented.
    assert {"small_talk", "site_opinion", "question", "edit", "other"}.issubset(
        conversation_kinds
    )
    # Every owned editing role appears at least once (ADR 0057 adds
    # component_builder); the unowned-edit honest surface (None) is also covered.
    roles = {role for _p, _mk, _ck, role in _CONDUCTOR_BASELINE}
    assert {
        "section_builder", "stylist", "copy", "component_builder", "router", None
    }.issubset(roles)


@pytest.mark.parametrize(
    ("prompt", "message_kind", "conversation_kind", "role"),
    _CONDUCTOR_BASELINE,
)
def test_conductor_classification_matches_baseline(
    prompt: str,
    message_kind: str,
    conversation_kind: str,
    role: str | None,
) -> None:
    """The full (messageKind, conversationKind, role) triple is pinned per prompt."""
    decision = classify_conversation(prompt)
    assert isinstance(decision, ConversationDecision)
    assert decision.messageKind == message_kind, prompt
    assert decision.conversationKind == conversation_kind, prompt
    assert decision.role == role, prompt
    # Membership invariants: the labels never leave their locked sets.
    assert decision.messageKind in _LOCKED_ROUTER_KINDS, prompt
    assert decision.conversationKind in _CONVERSATION_KINDS, prompt


@pytest.mark.parametrize("prompt", [row[0] for row in _CONDUCTOR_BASELINE])
def test_conversation_label_is_additive_over_the_router(prompt: str) -> None:
    """conversationKind is additive: messageKind is carried from the router
    verbatim, never an extension of the locked enum."""
    decision = classify_conversation(prompt)
    assert decision.messageKind == classify_message(prompt).messageKind, prompt


@pytest.mark.parametrize("prompt", [row[0] for row in _CONDUCTOR_BASELINE])
def test_expects_answer_tracks_conversation_kind_membership(prompt: str) -> None:
    """expectsAnswer is exactly membership of ANSWER_ONLY_CONVERSATION_KINDS."""
    decision = classify_conversation(prompt)
    assert decision.expectsAnswer == (
        decision.conversationKind in ANSWER_ONLY_CONVERSATION_KINDS
    ), prompt


def test_router_messagekind_enum_still_has_exactly_eight_values() -> None:
    """Guard against the conductor layer accidentally widening the locked enum."""
    assert set(typing.get_args(MessageKind)) == set(_LOCKED_ROUTER_KINDS)


# ---------------------------------------------------------------------------
# 2. EditKind -> role map (the conductor's ownership table), pinned.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("edit_kind", "expected_role"),
    [
        ("section_add", "section_builder"),
        ("visual_style", "stylist"),
        ("copy_change", "copy"),
        # ADR 0057: component_add is now owned by component_builder.
        ("component_add", "component_builder"),
        # Unowned-in-this-slice edit kinds map to None (honest surface).
        ("component_remove", None),
        ("layout_change", None),
        ("route_add", None),
        ("none", None),
    ],
)
def test_role_for_edit_kind_is_pinned(edit_kind: str, expected_role: str | None) -> None:
    assert role_for_edit_kind(edit_kind) == expected_role


# ---------------------------------------------------------------------------
# 3. Compound follow-ups: classification + honest unappliedFollowupIntents.
#    Only owned kinds (covered) and the clearly-unowned router edit kinds
#    (component_remove / layout_change / route_add) are asserted - never an
#    unknown/unregistered capability slug.
# ---------------------------------------------------------------------------


def _multi(*subtasks: RouterSubtask) -> RouterDecision:
    return RouterDecision(messageKind="multi_intent", subtasks=list(subtasks))


def test_compound_multi_intent_classifies_as_edit_with_first_actionable_role() -> None:
    """A compound follow-up that contains an edit stays an edit and reports the
    first actionable subtask's role (here: the style change -> stylist)."""
    decision = classify_conversation(
        "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna"
    )
    assert decision.messageKind == "multi_intent"
    assert decision.conversationKind == "edit"
    assert decision.role == "stylist"
    assert decision.expectsAnswer is False


def test_compound_unowned_part_is_reported_when_owned_part_applied() -> None:
    """Style applied + an unowned component_remove -> exactly one honest post."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör färgen mörkblå"),
        RouterSubtask(editKind="component_remove", instruction="ta bort kontaktformuläret"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=True,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert [p["target"] for p in posts] == ["borttagning"]
    assert "ta bort kontaktformuläret" in posts[0]["reason"]


def test_compound_each_unowned_kind_reported_once() -> None:
    """component_remove + layout_change + route_add are all unowned -> grouped,
    one post per kind (stable 'no executor owns this' contract)."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör färgen mörkblå"),
        RouterSubtask(editKind="component_remove", instruction="ta bort formuläret"),
        RouterSubtask(editKind="layout_change", instruction="centrera hero"),
        RouterSubtask(editKind="route_add", instruction="lägg till en blogg-sida"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=True,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert {p["target"] for p in posts} == {"borttagning", "layout", "ny sida"}


def test_compound_unparseable_style_is_reported() -> None:
    """A visual_style whose directive produced nothing (theme_applied=False) is
    an honest no-op and is reported (the stylist materialised nothing)."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör den coolare"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=False,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert [p["target"] for p in posts] == ["stil"]


def test_compound_owned_section_add_covered_is_not_reported() -> None:
    """An owned section_add whose registered capability was mounted is covered
    and produces no post (no false positive)."""
    decision = _multi(
        RouterSubtask(
            editKind="section_add", componentIntent="faq", instruction="en FAQ-sektion"
        ),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=False,
        applied_section_capabilities=["faq-section"],
        section_capability_for_intent={"faq": "faq-section"},
    )
    assert posts == []


def test_compound_clean_single_intent_has_no_posts() -> None:
    """A clean single applied intent yields no posts at all."""
    decision = RouterDecision(messageKind="edit_instruction", editKind="visual_style")
    assert (
        compute_unapplied_followup_chain_intents(
            decision,
            theme_applied=True,
            applied_section_capabilities=[],
            section_capability_for_intent={},
        )
        == []
    )


def test_compound_targeted_component_add_is_covered() -> None:
    """A component_add that carries a target section is collected by the patch
    planner -> covered (not reported); a targetless one is reported."""
    targeted = _multi(
        RouterSubtask(
            editKind="component_add",
            componentIntent="contact_form",
            instruction="lägg till kontaktformulär i sista sektionen",
            target=RouterTarget(routeId="home", sectionOrdinal=-1),
        ),
    )
    assert (
        compute_unapplied_followup_chain_intents(
            targeted,
            theme_applied=False,
            applied_section_capabilities=[],
            section_capability_for_intent={},
        )
        == []
    )
    targetless = _multi(
        RouterSubtask(
            editKind="component_add",
            componentIntent="contact_form",
            instruction="lägg till kontaktformulär",
        ),
    )
    posts = compute_unapplied_followup_chain_intents(
        targetless,
        theme_applied=False,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert [p["target"] for p in posts] == ["komponent"]


# ---------------------------------------------------------------------------
# 4. No-key parity + determinism (repo requirement, mirrors briefModel).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prompt", [row[0] for row in _CONDUCTOR_BASELINE])
def test_no_key_parity_classification_is_unchanged(
    prompt: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With OPENAI_API_KEY absent the classification is identical and the source
    mirrors briefModel's mock-no-key marker."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    decision = classify_conversation(prompt)
    assert decision.source == "mock-no-key", prompt
    # The triple still matches the committed baseline without a key.
    expected = next(row for row in _CONDUCTOR_BASELINE if row[0] == prompt)
    assert (decision.messageKind, decision.conversationKind, decision.role) == (
        expected[1],
        expected[2],
        expected[3],
    ), prompt


@pytest.mark.parametrize("prompt", [row[0] for row in _CONDUCTOR_BASELINE])
def test_classification_is_deterministic(prompt: str) -> None:
    """The same prompt classifies identically on repeat calls (no hidden state)."""
    assert classify_conversation(prompt) == classify_conversation(prompt)
