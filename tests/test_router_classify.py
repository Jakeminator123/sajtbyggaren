"""Tests for the deterministic message router (KÖR-6a).

These lock the acceptance criteria from
docs/heavy-llm-flow/02-orchestrator-och-intent.md §3 (the clock examples
A-E) as regression tests, plus a broad coverage table (~45 prompts across
all eight message kinds). The router is pure and deterministic, so every
assertion is exact.

The two hard invariants this slice exists to protect:
- A pure question / discovery / reference / review never starts a build or
  a preview (``answer_only`` / ``plan_only`` -> ``shouldStartPreview`` is
  False, ``buildRequirement`` is ``none``/``plan_only``).
- A live user session (builder coexistence) forces ``shouldStartPreview``
  False even for a real rebuild.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.router import (  # noqa: E402
    RouterContext,
    RouterDecision,
    classify_message,
)

# ---------------------------------------------------------------------------
# Clock examples A-E (02 §3) - the canonical acceptance criteria
# ---------------------------------------------------------------------------


def test_clock_a_pure_question_is_answer_only_no_build():
    """A: "vad är klockan?" -> answer_only, no build, no preview."""
    d = classify_message("vad är klockan?")
    assert d.messageKind == "answer_only"
    assert d.buildRequirement == "none"
    assert d.contextLevel == "none"
    assert d.shouldStartPreview is False
    assert d.editKind == "none"
    # The router can explain why it does not start a build.
    assert "answer" in d.rationale.lower()


def test_clock_b_component_add_resolves_target_and_rebuilds():
    """B: "lägg en klocka i andra sektionen till vänster" -> edit_instruction,
    component_add, targeted_rebuild, target resolved (ordinal 2, left)."""
    d = classify_message("lägg en klocka i andra sektionen till vänster")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "component_add"
    assert d.buildRequirement == "targeted_rebuild"
    assert d.contextLevel == "artifacts_plus_sections"
    assert d.componentIntent == "clock_widget"
    assert d.target is not None
    assert d.target.routeId == "home"
    assert d.target.sectionOrdinal == 2
    assert d.target.position == "left"
    assert d.shouldStartPreview is True


def test_clock_c_discovery_lists_options_no_build():
    """C: "vilka klockor finns att tillgå?" -> component_discovery, none,
    component_registry."""
    d = classify_message("vilka klockor finns att tillgå?")
    assert d.messageKind == "component_discovery"
    assert d.editKind == "none"
    assert d.buildRequirement == "none"
    assert d.contextLevel == "component_registry"
    assert d.shouldStartPreview is False


def test_clock_d_reference_is_plan_only_with_do_not_copy():
    """D: "samma klocka som på aftonbladet.se" -> reference_analysis,
    plan_only, external_reference, risk do_not_copy_exact."""
    d = classify_message("samma klocka som på aftonbladet.se")
    assert d.messageKind == "reference_analysis"
    assert d.buildRequirement == "plan_only"
    assert d.contextLevel == "external_reference"
    assert d.risk == "do_not_copy_exact"
    assert d.reference is not None
    assert d.reference.url == "aftonbladet.se"
    assert d.shouldStartPreview is False


def test_clock_e_multi_intent_preserves_copy_constraint():
    """E: "gör sidan mer premium, lägg en klocka i andra sektionen, ändra
    inte texterna" -> multi_intent with preserve_copy constraint."""
    d = classify_message(
        "gör sidan mer premium, lägg en klocka i andra sektionen, "
        "ändra inte texterna"
    )
    assert d.messageKind == "multi_intent"
    assert d.buildRequirement == "targeted_rebuild"
    assert "preserve_copy" in d.constraints
    # The three deluppgifter: a style change, a component add, a constraint.
    kinds = [s.editKind for s in d.subtasks]
    assert "visual_style" in kinds
    assert "component_add" in kinds
    assert any(s.constraint == "preserve_copy" for s in d.subtasks)


# ---------------------------------------------------------------------------
# Broad coverage table (~45 prompts across all eight message kinds)
# ---------------------------------------------------------------------------

COVERAGE: list[tuple[str, str, str]] = [
    # answer_only - pure questions unrelated to the site
    ("vad är klockan", "answer_only", "none"),
    ("vad är klockan?", "answer_only", "none"),
    ("hur mycket är klockan just nu?", "answer_only", "none"),
    ("vad är huvudstaden i Frankrike?", "answer_only", "none"),
    ("förklara hur fotosyntes fungerar", "answer_only", "none"),
    ("vem skrev Hamlet?", "answer_only", "none"),
    ("berätta en rolig fakta", "answer_only", "none"),
    ("vad är klockan och vad är datumet?", "answer_only", "none"),
    # component_discovery
    ("vilka klockor finns att tillgå?", "component_discovery", "none"),
    ("vilka klockor finns?", "component_discovery", "none"),
    ("vilka komponenter finns att välja på?", "component_discovery", "none"),
    ("vad finns det för widgets?", "component_discovery", "none"),
    ("finns det några kontaktformulär jag kan använda?", "component_discovery", "none"),
    ("vilka alternativ har jag för galleri?", "component_discovery", "none"),
    ("vilka typsnitt kan jag välja?", "component_discovery", "none"),
    # reference_analysis
    ("samma klocka som på aftonbladet.se", "reference_analysis", "plan_only"),
    ("gör en hero liknande stripe.com", "reference_analysis", "plan_only"),
    ("jag vill ha en meny som på mcdonalds.se", "reference_analysis", "plan_only"),
    ("kan du kolla in apple.com och göra något liknande?", "reference_analysis", "plan_only"),
    # edit_instruction - component add/remove
    ("lägg en klocka i andra sektionen till vänster", "edit_instruction", "targeted_rebuild"),
    ("lägg till en kontaktknapp överst", "edit_instruction", "targeted_rebuild"),
    ("ta bort knappen", "edit_instruction", "targeted_rebuild"),
    ("lägg till en faq-sektion", "edit_instruction", "targeted_rebuild"),
    # edit_instruction - visual_style
    ("gör sidan mer premium", "edit_instruction", "targeted_rebuild"),
    ("ändra färgen till blått", "edit_instruction", "targeted_rebuild"),
    ("gör om hela sidan från grunden", "edit_instruction", "full_rebuild"),
    # edit_instruction - copy_change
    ("skriv om rubriken på startsidan", "edit_instruction", "artifact_patch_only"),
    ("uppdatera texten i hero-sektionen", "edit_instruction", "artifact_patch_only"),
    # edit_instruction - layout_change
    ("flytta klockan till höger", "edit_instruction", "targeted_rebuild"),
    ("centrera rubriken", "edit_instruction", "targeted_rebuild"),
    # edit_instruction - route_add
    ("lägg till en kontaktsida", "edit_instruction", "targeted_rebuild"),
    # multi_intent
    (
        "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna",
        "multi_intent",
        "targeted_rebuild",
    ),
    ("lägg till en kontaktknapp och gör sidan mörkare", "multi_intent", "targeted_rebuild"),
    ("ta bort galleriet och lägg till ett kontaktformulär", "multi_intent", "targeted_rebuild"),
    ("byt färg på knappen och flytta den till höger", "multi_intent", "targeted_rebuild"),
    # bug_report
    ("knappen funkar inte", "bug_report", "plan_only"),
    ("sidan kraschar när jag klickar på menyn", "bug_report", "plan_only"),
    ("kontaktformuläret fungerar inte", "bug_report", "plan_only"),
    # site_review
    ("vad tycker du om sidan?", "site_review", "none"),
    ("kan du granska designen?", "site_review", "none"),
    ("vad tycker du om hemsidan?", "site_review", "none"),
    ("hur ser startsidan ut?", "site_review", "none"),
    # unclear
    ("", "unclear", "none"),
    ("hej", "unclear", "none"),
    ("ändra", "unclear", "none"),
    ("fixa det där", "unclear", "none"),
]


@pytest.mark.parametrize("prompt,message_kind,build_requirement", COVERAGE)
def test_coverage_table(prompt: str, message_kind: str, build_requirement: str):
    d = classify_message(prompt)
    assert d.messageKind == message_kind, f"{prompt!r} -> {d.messageKind} ({d.rationale})"
    assert d.buildRequirement == build_requirement, (
        f"{prompt!r} -> {d.buildRequirement} ({d.rationale})"
    )


@pytest.mark.parametrize("prompt,message_kind,build_requirement", COVERAGE)
def test_no_preview_without_a_real_rebuild(prompt, message_kind, build_requirement):
    """The hard rule: answer_only / plan_only (and anything that is not a
    real rebuild) must never set shouldStartPreview."""
    d = classify_message(prompt)
    if d.buildRequirement in ("none", "plan_only", "artifact_patch_only"):
        assert d.shouldStartPreview is False, (
            f"{prompt!r}: {d.buildRequirement} must not start preview"
        )


@pytest.mark.parametrize("prompt,message_kind,build_requirement", COVERAGE)
def test_every_decision_is_schema_shaped(prompt, message_kind, build_requirement):
    """Every classification returns a fully-formed RouterDecision."""
    d = classify_message(prompt)
    assert isinstance(d, RouterDecision)
    assert d.rationale  # non-empty explanation always present


# ---------------------------------------------------------------------------
# Builder coexistence + context-driven target resolution
# ---------------------------------------------------------------------------


def test_active_user_session_blocks_preview_even_for_rebuild():
    """Coexistence (02 §8): a live session on the same site must never get a
    router-started preview, even when a rebuild is otherwise required."""
    ctx = RouterContext(siteId="elektriker-malmo", hasActiveUserSession=True)
    d = classify_message("lägg en klocka i andra sektionen till vänster", context=ctx)
    assert d.messageKind == "edit_instruction"
    assert d.buildRequirement == "targeted_rebuild"
    assert d.shouldStartPreview is False


def test_context_route_sections_resolve_section_id():
    """When a caller supplies a route/section map, the ordinal resolves to a
    concrete sectionId - without the router reading disk itself."""
    ctx = RouterContext(routeSections={"home": ["hero", "services", "about"]})
    d = classify_message("lägg en klocka i andra sektionen", context=ctx)
    assert d.target is not None
    assert d.target.sectionOrdinal == 2
    assert d.target.sectionId == "services"


def test_without_context_section_id_stays_none():
    """No context -> the router parses the ordinal but does not invent a
    sectionId (that mapping is the context layer's job, kor-7a)."""
    d = classify_message("lägg en klocka i andra sektionen")
    assert d.target is not None
    assert d.target.sectionOrdinal == 2
    assert d.target.sectionId is None


def test_preserve_constraint_on_single_edit_is_not_multi_intent():
    """A single edit plus a preserve constraint stays edit_instruction (one
    actionable change) but carries the constraint."""
    d = classify_message("gör sidan mer premium men ändra inte texterna")
    assert d.messageKind == "edit_instruction"
    assert d.editKind == "visual_style"
    assert "preserve_copy" in d.constraints


def test_pure_questions_never_require_a_build():
    """Regression: the whole point of kor-6a is that pure questions stop the
    chat from rebuilding. Lock it for the canonical trio."""
    for prompt in ("vad är klockan", "vilka klockor finns?", "vad tycker du om sidan?"):
        d = classify_message(prompt)
        assert d.buildRequirement in ("none",)
        assert d.shouldStartPreview is False
