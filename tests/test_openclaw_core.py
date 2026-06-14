"""Tests for OpenClaw Core V0 (KÖR-o2).

These lock the kor-o1 capability plan as regression tests: each
``messageKind`` the deterministic router (KÖR-6a) can emit maps to exactly
one of the four V0 actions

    answer_only | clarification | plan_only | patch_plan_request

and V0 is provably read-only - it writes nothing, builds nothing, starts no
preview, and always reports ``appliedVisibleEffect == False`` (kor-o1 "Mål"
+ 04 §9). Classification is delegated to the real ``classify_message`` so
there is a single router truth and no divergent classifier here.

Everything runs without ``OPENAI_API_KEY`` and is fully deterministic over
(router, context): no LLM is involved at any point.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.context import assemble_context  # noqa: E402
from packages.generation.orchestration.context.models import (  # noqa: E402
    AssembledContext,
)
from packages.generation.orchestration.openclaw import (  # noqa: E402
    OpenClawDecision,
    PatchPlanRequest,
    ToolCall,
    decide,
    orchestrate,
)
from packages.generation.orchestration.router import classify_message  # noqa: E402
from packages.generation.orchestration.router.models import (  # noqa: E402
    RouterDecision,
    RouterReference,
    RouterSubtask,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

# ---------------------------------------------------------------------------
# Capability-plan rows (kor-o1): messageKind -> V0 action
# ---------------------------------------------------------------------------


def _decide_for(message: str, *, context: AssembledContext | None = None) -> OpenClawDecision:
    """Classify with the real router, then run V0 ``decide`` on the result."""
    router = classify_message(message)
    ctx = context if context is not None else AssembledContext(contextLevel=router.contextLevel)
    return decide(router, ctx)


def test_answer_only_pure_question_is_answer_only():
    """answer_only -> answer_only, with an answer and no other result field."""
    d = _decide_for("vad är klockan?")
    assert d.router.messageKind == "answer_only"
    assert d.action == "answer_only"
    assert d.answer
    assert d.clarifyingQuestion is None
    assert d.plan == []
    assert d.patchPlanRequest is None


def test_unclear_is_clarification():
    """unclear -> clarification, with a clarifying question."""
    router = classify_message("öö")
    # Force the ambiguous path deterministically if the heuristic disagrees.
    if router.messageKind != "unclear" and not router.requiresClarification:
        router = RouterDecision(messageKind="unclear", requiresClarification=True)
    d = decide(router, AssembledContext(contextLevel="none"))
    assert d.action == "clarification"
    assert d.clarifyingQuestion
    assert d.answer is None
    assert d.plan == []
    assert d.patchPlanRequest is None


def test_reference_analysis_is_plan_only_never_copy():
    """reference_analysis -> plan_only proposing an own variant (no copy)."""
    d = _decide_for("samma klocka som på aftonbladet.se")
    assert d.router.messageKind == "reference_analysis"
    assert d.action == "plan_only"
    assert d.plan
    # Honest: the plan must say it does not copy exactly.
    assert any("kopiera" in step.lower() for step in d.plan)
    assert d.patchPlanRequest is None


def test_bug_report_is_plan_only():
    """bug_report -> plan_only (V0 proposes; it does not fix/build)."""
    d = _decide_for("knappen funkar inte")
    assert d.router.messageKind == "bug_report"
    assert d.action == "plan_only"
    assert d.plan


def test_site_review_is_answer_only_when_no_change_wanted():
    """site_review with buildRequirement none -> answer_only."""
    d = _decide_for("vad tycker du om sidan?")
    assert d.router.messageKind == "site_review"
    assert d.router.buildRequirement == "none"
    assert d.action == "answer_only"
    assert d.answer


def test_edit_instruction_is_honest_patch_plan_request():
    """edit_instruction -> patch_plan_request{action_bridge_missing}.

    The single most important honesty test: an edit order in V0 must NOT fake a
    success - it returns the missing-bridge flag. The patch -> apply -> targeted
    render chain exists (kor-7b/7c/7d), but the OpenClaw action-bridge that drives
    it from a decision does not.
    """
    d = _decide_for("lägg en klocka i andra sektionen till vänster")
    assert d.router.messageKind == "edit_instruction"
    assert d.action == "patch_plan_request"
    assert d.patchPlanRequest is not None
    assert d.patchPlanRequest.status == "action_bridge_missing"
    assert d.patchPlanRequest.blockedBy == "openclaw-action-bridge"
    assert d.patchPlanRequest.targetSummary.startswith("contentBlocks.")
    # Never an applied effect.
    assert d.appliedVisibleEffect is False


def test_edit_instruction_carries_grounded_plan_without_false_success():
    """Novel-intent planeringssvar (coach-beslut 2026-06-15, ADR 0059-anda): a
    clear edit V0 cannot auto-apply yet now gets a grounded "så här skulle det
    kunna byggas" plan instead of a bare missing-bridge dead-end - WHILE staying
    honest: still patch_plan_request{action_bridge_missing}, no applied effect,
    and an explicit "no automatic change yet" line (#313 no false success).
    """
    d = _decide_for("lägg en klocka i andra sektionen till vänster")
    assert d.action == "patch_plan_request"
    # The dead-end is gone: a grounded, non-empty plan that names what it read.
    assert len(d.plan) >= 2
    assert any("uppfattar" in step.lower() for step in d.plan)
    # ...but #313 honesty is intact - the bridge flag, no fake success.
    assert d.patchPlanRequest is not None
    assert d.patchPlanRequest.status == "action_bridge_missing"
    assert d.appliedVisibleEffect is False
    assert any("ingen automatisk ändring" in step.lower() for step in d.plan)


def test_visual_style_target_summary_describes_style_not_contentblocks():
    """ÄNDRING 2: a visual_style restyle changes the site's STYLE/THEME (colour,
    tone), NOT a content field - so the patch_plan_request summary must describe
    stil/tema instead of a contentBlocks.<route>.<section>.<field> path (which
    mislabelled a restyle in the operator-facing chat row). The action/status
    stay the honest action_bridge_missing flag - only the summary string is
    fixed, so #313's no-false-success contract is untouched."""
    d = _decide_for("gör om designen")
    assert d.router.messageKind == "edit_instruction"
    assert d.router.editKind == "visual_style"
    assert d.action == "patch_plan_request"
    assert d.patchPlanRequest is not None
    summary = d.patchPlanRequest.targetSummary
    assert not summary.startswith("contentBlocks."), summary
    assert "stil" in summary or "tema" in summary, summary
    # The honesty flag is unchanged (no faked success).
    assert d.patchPlanRequest.status == "action_bridge_missing"
    assert d.appliedVisibleEffect is False


def test_content_edit_target_summary_keeps_contentblocks():
    """Counterpart to the visual_style honesty fix: copy_change / component_add
    edits still get the contentBlocks path, where it correctly names the targeted
    content field (the fix is scoped to visual_style only)."""
    component_add = _decide_for("lägg en klocka i andra sektionen till vänster")
    assert component_add.router.editKind == "component_add"
    assert component_add.patchPlanRequest is not None
    assert component_add.patchPlanRequest.targetSummary.startswith("contentBlocks.")

    copy_change = _decide_for("ändra rubriken till Välkommen hem")
    assert copy_change.router.editKind == "copy_change"
    assert copy_change.patchPlanRequest is not None
    assert copy_change.patchPlanRequest.targetSummary.startswith("contentBlocks.")


def test_multi_intent_with_edit_aggregates_to_patch_plan_request():
    """multi_intent containing an edit -> aggregated patch_plan_request."""
    d = _decide_for(
        "gör sidan mer premium, lägg en klocka i andra sektionen, "
        "ändra inte texterna"
    )
    assert d.router.messageKind == "multi_intent"
    assert d.action == "patch_plan_request"
    assert d.patchPlanRequest is not None
    assert d.patchPlanRequest.status == "action_bridge_missing"
    # One plan line per subtask, for transparency.
    assert len(d.plan) == len(d.router.subtasks)


def test_component_discovery_lists_available_options():
    """component_discovery -> answer_only that lists options from context."""
    router = classify_message("vilka klockor finns att tillgå?")
    assert router.messageKind == "component_discovery"
    ctx = AssembledContext(
        contextLevel="component_registry",
        payload={
            "dossiers": [
                {"id": "clock-basic", "label": "Klocka (enkel)"},
                {"id": "clock-analog", "label": "Klocka (analog)"},
            ],
            "capabilities": [{"capability": "clock_widget"}],
        },
    )
    d = decide(router, ctx)
    assert d.action == "answer_only"
    assert "Klocka (enkel)" in d.answer
    assert "Klocka (analog)" in d.answer


def test_component_discovery_is_honest_when_registry_empty():
    """No options in context -> an honest 'inga val' answer, not invented."""
    router = classify_message("vilka komponenter finns att välja på?")
    d = decide(router, AssembledContext(contextLevel="component_registry"))
    assert d.action == "answer_only"
    assert "Inga" in d.answer or "inga" in d.answer


# ---------------------------------------------------------------------------
# Full contract shape + V0 invariants
# ---------------------------------------------------------------------------

ALL_MESSAGES = [
    "vad är klockan?",
    "vilka klockor finns att tillgå?",
    "samma klocka som på aftonbladet.se",
    "vad tycker du om sidan?",
    "lägg en klocka i andra sektionen till vänster",
    "knappen funkar inte",
    "gör sidan mer premium, lägg en klocka, ändra inte texterna",
]


@pytest.mark.parametrize("message", ALL_MESSAGES)
def test_decision_carries_full_contract_shape(message: str):
    """OpenClawDecision embeds the unchanged router + context and the full
    contract fields (toolCalls/capability default empty/None in V0)."""
    router = classify_message(message)
    ctx = AssembledContext(contextLevel=router.contextLevel)
    d = decide(router, ctx)

    # Composes the existing types unchanged (no new enums).
    assert isinstance(d.router, RouterDecision)
    assert d.router == router
    assert isinstance(d.context, AssembledContext)
    assert d.context is ctx
    # Action is one of the four closed V0 actions.
    assert d.action in {"answer_only", "clarification", "plan_only", "patch_plan_request"}
    # V0 defaults: empty tool list, no capability, no applied effect.
    assert d.toolCalls == []
    assert d.capability is None
    assert d.appliedVisibleEffect is False
    assert d.rationale
    # Round-trips through the contract shape.
    dumped = d.model_dump()
    assert set(
        [
            "router",
            "context",
            "action",
            "answer",
            "clarifyingQuestion",
            "plan",
            "patchPlanRequest",
            "toolCalls",
            "capability",
            "appliedVisibleEffect",
            "rationale",
        ]
    ).issubset(dumped.keys())


def test_applied_visible_effect_cannot_be_set_true():
    """The validator forces appliedVisibleEffect False even if a caller tries
    to set it True - V0 can never fabricate a visible change (04 §9)."""
    d = OpenClawDecision(
        router=classify_message("vad är klockan?"),
        context=AssembledContext(contextLevel="none"),
        action="answer_only",
        appliedVisibleEffect=True,
    )
    assert d.appliedVisibleEffect is False


def test_toolcall_always_requires_approval():
    """A proposed ToolCall can never be marked auto-runnable in V0."""
    tc = ToolCall(name="propose_patch_plan", requiresApproval=False)
    assert tc.requiresApproval is True


def test_patch_plan_request_defaults_are_honest():
    """PatchPlanRequest defaults to the honest action-bridge-missing marker."""
    p = PatchPlanRequest(targetSummary="contentBlocks.home.hero.<field>")
    assert p.status == "action_bridge_missing"
    assert p.blockedBy == "openclaw-action-bridge"


def test_applied_visible_effect_cannot_be_mutated_true():
    """validate_assignment re-runs the validator on assignment too, so a caller
    cannot mute appliedVisibleEffect to True after construction (KÖR-o2 §6)."""
    d = OpenClawDecision(
        router=classify_message("vad är klockan?"),
        context=AssembledContext(contextLevel="none"),
        action="answer_only",
    )
    d.appliedVisibleEffect = True
    assert d.appliedVisibleEffect is False


def test_toolcall_requires_approval_cannot_be_mutated_false():
    """A ToolCall's requiresApproval cannot be muted to False post-construction."""
    tc = ToolCall(name="propose_patch_plan")
    tc.requiresApproval = False
    assert tc.requiresApproval is True


# ---------------------------------------------------------------------------
# Reference gating + reference-url forwarding (KÖR-o2 §3/§4)
# ---------------------------------------------------------------------------


def test_multi_intent_with_reference_is_plan_only_not_patch():
    """A multi_intent carrying an external reference goes to plan_only
    (referensanalys först), never patch_plan_request, even with an edit subtask."""
    router = RouterDecision(
        messageKind="multi_intent",
        buildRequirement="plan_only",
        contextLevel="external_reference",
        reference=RouterReference(url="https://aftonbladet.se"),
        risk="do_not_copy_exact",
        subtasks=[
            RouterSubtask(
                editKind="component_add",
                instruction="lägg en klocka som på aftonbladet.se",
            ),
            RouterSubtask(editKind="copy_change", instruction="ändra rubriken"),
        ],
    )
    d = decide(router, AssembledContext(contextLevel="external_reference"))
    assert d.action == "plan_only"
    assert d.patchPlanRequest is None
    assert len(d.plan) == len(router.subtasks)


def test_orchestrate_forwards_reference_url_to_assembler(monkeypatch):
    """orchestrate passes router.reference.url to assemble_context so an external
    reference is not assembled on empty context (KÖR-o2 §3)."""
    import packages.generation.orchestration.openclaw.core as core

    router = classify_message("samma klocka som på aftonbladet.se")
    assert router.reference is not None and router.reference.url

    captured: dict = {}

    def _spy(level, **kwargs):
        captured["level"] = level
        captured["kwargs"] = kwargs
        return AssembledContext(contextLevel=level)

    monkeypatch.setattr(core, "assemble_context", _spy)
    core.orchestrate("samma klocka som på aftonbladet.se")
    assert captured["kwargs"].get("url") == router.reference.url


# ---------------------------------------------------------------------------
# Read-only / mock-safe guarantees
# ---------------------------------------------------------------------------


def test_decide_is_deterministic():
    """Same (router, context) pair -> identical decision (no LLM, no clock)."""
    router = classify_message("lägg en klocka i andra sektionen till vänster")
    ctx = AssembledContext(contextLevel=router.contextLevel)
    first = decide(router, ctx)
    second = decide(router, ctx)
    assert first.model_dump() == second.model_dump()


def test_decide_needs_no_openai_key(monkeypatch: pytest.MonkeyPatch):
    """V0 is mock-safe: it works with OPENAI_API_KEY absent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    d = _decide_for("vad är klockan?")
    assert d.action == "answer_only"
    assert os.environ.get("OPENAI_API_KEY") is None


def test_decide_writes_no_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Running decide for every kind creates no files and no run dirs.

    decide is a pure function, so this is belt-and-braces: it proves V0
    materialises nothing on disk (no build, no current.json, no run).
    """
    monkeypatch.chdir(tmp_path)
    for message in ALL_MESSAGES:
        d = _decide_for(message)
        assert d.appliedVisibleEffect is False
    # The working directory is untouched - nothing was written.
    assert list(tmp_path.iterdir()) == []


def test_orchestrate_wires_three_tools_read_only():
    """orchestrate(message) runs classify -> assemble -> decide read-only.

    For a pure question the context level is ``none`` (assembler returns an
    empty, budgeted envelope) and the action is answer_only - no run, no
    build, no preview.
    """
    d = orchestrate("vad är klockan?")
    assert d.router.messageKind == "answer_only"
    assert d.context.contextLevel == "none"
    assert d.action == "answer_only"
    assert d.appliedVisibleEffect is False


def test_orchestrate_matches_manual_composition():
    """orchestrate is exactly classify + assemble + decide (no extra logic)."""
    message = "vilka klockor finns att tillgå?"
    router = classify_message(message)
    ctx = assemble_context(router.contextLevel)
    expected = decide(router, ctx)
    got = orchestrate(message)
    assert got.action == expected.action
    assert got.router == router


def test_orchestrate_uses_injected_router_without_reclassifying(
    monkeypatch: pytest.MonkeyPatch,
):
    """KÖR-6b bridge wiring: an injected RouterDecision is used verbatim and
    the message is never classified a second time (one router truth, at most
    one model call per invocation upstream)."""
    import packages.generation.orchestration.openclaw.core as core

    injected = classify_message("byt rubriken till Bryggans Surdegsbageri")

    def _explode(*args, **kwargs):  # pragma: no cover - reaching this IS the bug
        raise AssertionError("orchestrate must not re-classify an injected router")

    monkeypatch.setattr(core, "classify_message", _explode)
    decision = core.orchestrate(
        "byt rubriken till Bryggans Surdegsbageri", router=injected
    )
    assert decision.router == injected
    assert decision.action == "patch_plan_request"
