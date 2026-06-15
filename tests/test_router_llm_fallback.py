"""Tests for the router LLM fallback (KÖR-6b).

The fallback sits on top of the deterministic KÖR-6a router. These tests lock
the hard guarantees of the slice:

- The LLM is only consulted for genuinely ambiguous input (unclear / long /
  complex multi_intent). The clock examples A-E stay with the heuristic.
- Without OPENAI_API_KEY the fallback is byte-identical to KÖR-6a (no
  regression) - even on the messages that *would* trigger the LLM.
- Whatever the model returns, shouldStartPreview is recomputed deterministically
  so an answer_only / plan_only decision can never start a preview, and a live
  user session always blocks it (builder coexistence).
- Any model/parse/network error falls back to the heuristic decision.
- routerModel resolves from the existing llm-models.v1.json policy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.router import (  # noqa: E402
    RouterContext,
    RouterDecision,
    RouterModelResolutionError,
    classify_message,
    classify_message_with_llm_fallback,
    llm_fallback,  # noqa: E402
    needs_llm_fallback,
    resolve_router_model,
)

# The five canonical clock examples (02 §3) - the heuristic owns these.
CLOCK_EXAMPLES = [
    "vad är klockan?",
    "lägg en klocka i andra sektionen till vänster",
    "vilka klockor finns att tillgå?",
    "samma klocka som på aftonbladet.se",
    "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna",
]

UNCLEAR_PROMPTS = ["fixa det där", "ändra", "hej"]

LONG_PROMPT = (
    "jag vill verkligen att du hjälper mig att fundera kring hur sidan skulle "
    "kunna kännas mer förtroendeingivande och samtidigt modern men jag är osäker "
    "på om det är färgerna eller texterna eller kanske helt enkelt strukturen "
    "som behöver ses över ordentligt innan vi går vidare"
)


# ---------------------------------------------------------------------------
# needs_llm_fallback - which messages reach the model
# ---------------------------------------------------------------------------


def test_empty_message_does_not_trigger_fallback():
    """An empty message is heuristic-unclear but there is nothing for the LLM
    to resolve, so it is never sent to the model."""
    assert needs_llm_fallback(classify_message(""), "") is False


@pytest.mark.parametrize("prompt", UNCLEAR_PROMPTS)
def test_unclear_messages_trigger_fallback(prompt):
    decision = classify_message(prompt)
    assert decision.messageKind == "unclear"
    assert needs_llm_fallback(decision, prompt) is True


def test_long_message_triggers_fallback():
    assert needs_llm_fallback(classify_message(LONG_PROMPT), LONG_PROMPT) is True


@pytest.mark.parametrize("prompt", CLOCK_EXAMPLES)
def test_clock_examples_never_trigger_fallback(prompt):
    """The heuristic owns the clock examples - the LLM rör dem inte i onödan."""
    assert needs_llm_fallback(classify_message(prompt), prompt) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "lägg till en kontaktknapp överst",
        "ta bort knappen",
        "gör sidan mer premium",
        "skriv om rubriken på startsidan",
        "lägg till en kontaktknapp och gör sidan mörkare",
    ],
)
def test_confident_short_edits_do_not_trigger_fallback(prompt):
    """Confidently-classified short edits (incl. a two-edit multi_intent) stay
    with the heuristic."""
    assert needs_llm_fallback(classify_message(prompt), prompt) is False


def test_complex_multi_intent_triggers_fallback():
    """A multi_intent with >= 3 actionable edits escalates to the LLM."""
    prompt = "lägg till en klocka, ta bort galleriet och lägg till en kontaktknapp"
    decision = classify_message(prompt)
    assert decision.messageKind == "multi_intent"
    actionable = [s for s in decision.subtasks if s.editKind != "none"]
    assert len(actionable) >= 3
    assert needs_llm_fallback(decision, prompt) is True


# ---------------------------------------------------------------------------
# Without a key: identical to KÖR-6a (no regression)
# ---------------------------------------------------------------------------


@pytest.fixture
def _no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.mark.parametrize("prompt", CLOCK_EXAMPLES + UNCLEAR_PROMPTS + [LONG_PROMPT, ""])
def test_without_key_is_identical_to_kor_6a(prompt, _no_api_key, monkeypatch):
    """Mock (no key) == KÖR-6a heuristic for every prompt, including the ones
    that would otherwise trigger the LLM. The model must never be called."""

    def _boom(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("routerModel must not be called without a key")

    monkeypatch.setattr(llm_fallback, "_real_router_decision", _boom)

    heuristic = classify_message(prompt)
    fallback = classify_message_with_llm_fallback(prompt)
    assert fallback.model_dump() == heuristic.model_dump()


def test_clock_examples_byte_identical_with_key_present(monkeypatch):
    """Even WITH a key, the confident clock examples never reach the model and
    stay byte-identical to KÖR-6a."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def _boom(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("confident clock examples must not call routerModel")

    monkeypatch.setattr(llm_fallback, "_real_router_decision", _boom)

    for prompt in CLOCK_EXAMPLES:
        assert (
            classify_message_with_llm_fallback(prompt).model_dump()
            == classify_message(prompt).model_dump()
        )


# ---------------------------------------------------------------------------
# With a key: the LLM decision is used, with deterministic preview gating
# ---------------------------------------------------------------------------


def test_with_key_uses_llm_decision_for_unclear(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    crafted = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        buildRequirement="targeted_rebuild",
        contextLevel="artifacts_plus_sections",
        rationale="LLM resolved the ambiguous request.",
    )
    monkeypatch.setattr(
        llm_fallback, "_real_router_decision", lambda *a, **k: crafted
    )

    decision = classify_message_with_llm_fallback("fixa det där", model="test-model")
    assert decision.messageKind == "edit_instruction"
    assert decision.editKind == "component_add"
    assert decision.buildRequirement == "targeted_rebuild"
    # targeted_rebuild + no active session -> the router actuates the preview.
    assert decision.shouldStartPreview is True


def test_llm_cannot_start_preview_for_answer_only(monkeypatch):
    """A model that wrongly sets shouldStartPreview=True on a none build must be
    overridden - the router recomputes the flag from buildRequirement."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    crafted = RouterDecision(
        messageKind="answer_only",
        buildRequirement="none",
        shouldStartPreview=True,  # the model lied
        rationale="pure question",
    )
    monkeypatch.setattr(
        llm_fallback, "_real_router_decision", lambda *a, **k: crafted
    )

    decision = classify_message_with_llm_fallback("fixa det där", model="test-model")
    assert decision.buildRequirement == "none"
    assert decision.shouldStartPreview is False


def test_llm_decision_respects_builder_coexistence(monkeypatch):
    """A live user session forces shouldStartPreview false even when the LLM
    returns a real rebuild (02 §8)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    crafted = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        buildRequirement="targeted_rebuild",
        shouldStartPreview=True,
        rationale="rebuild",
    )
    monkeypatch.setattr(
        llm_fallback, "_real_router_decision", lambda *a, **k: crafted
    )

    ctx = RouterContext(siteId="elektriker-malmo", hasActiveUserSession=True)
    decision = classify_message_with_llm_fallback(
        "fixa det där", context=ctx, model="test-model"
    )
    assert decision.buildRequirement == "targeted_rebuild"
    assert decision.shouldStartPreview is False


def test_llm_error_falls_back_to_heuristic(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(llm_fallback, "_real_router_decision", _raise)

    heuristic = classify_message("fixa det där")
    fallback = classify_message_with_llm_fallback("fixa det där", model="test-model")
    assert fallback.model_dump() == heuristic.model_dump()


def test_llm_none_output_falls_back_to_heuristic(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(llm_fallback, "_real_router_decision", lambda *a, **k: None)

    heuristic = classify_message("fixa det där")
    fallback = classify_message_with_llm_fallback("fixa det där", model="test-model")
    assert fallback.model_dump() == heuristic.model_dump()


# ---------------------------------------------------------------------------
# Cross-field clamp - a semantically inconsistent LLM pairing can never build
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,given,expected",
    [
        # Non-edit kinds can never escalate to a build -> clamped to least action.
        ("answer_only", "targeted_rebuild", "none"),
        ("component_discovery", "full_rebuild", "none"),
        ("site_review", "targeted_rebuild", "none"),
        ("reference_analysis", "targeted_rebuild", "plan_only"),
        ("bug_report", "full_rebuild", "plan_only"),
        ("unclear", "artifact_patch_only", "none"),
        ("multi_intent", "none", "plan_only"),
        ("edit_instruction", "none", "artifact_patch_only"),
        # Values already in the allowed set are left untouched.
        ("edit_instruction", "targeted_rebuild", "targeted_rebuild"),
        ("site_review", "plan_only", "plan_only"),
        ("multi_intent", "full_rebuild", "full_rebuild"),
    ],
)
def test_clamp_build_requirement(kind, given, expected):
    decision = RouterDecision(messageKind=kind, buildRequirement=given)
    llm_fallback._clamp_build_requirement(decision)
    assert decision.buildRequirement == expected


def test_llm_inconsistent_answer_only_cannot_build(monkeypatch):
    """routerModel returning answer_only + targeted_rebuild is clamped to none,
    so a pure question can never actuate a build/preview (kor-6a / 02 §2)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    crafted = RouterDecision(
        messageKind="answer_only",
        buildRequirement="targeted_rebuild",  # semantically inconsistent
        rationale="pure question wrongly marked as a rebuild",
    )
    monkeypatch.setattr(llm_fallback, "_real_router_decision", lambda *a, **k: crafted)

    decision = classify_message_with_llm_fallback("fixa det där", model="test-model")
    assert decision.buildRequirement == "none"
    assert decision.shouldStartPreview is False


def test_llm_valid_edit_is_not_clamped(monkeypatch):
    """A consistent edit_instruction + targeted_rebuild is preserved (no clamp)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    crafted = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        buildRequirement="targeted_rebuild",
        rationale="add a component",
    )
    monkeypatch.setattr(llm_fallback, "_real_router_decision", lambda *a, **k: crafted)

    decision = classify_message_with_llm_fallback("fixa det där", model="test-model")
    assert decision.buildRequirement == "targeted_rebuild"
    assert decision.shouldStartPreview is True


# ---------------------------------------------------------------------------
# routerModel resolution from the policy
# ---------------------------------------------------------------------------


def test_resolve_router_model_reads_policy():
    assert resolve_router_model() == "gpt-5.5"


def test_resolve_router_model_missing_role(tmp_path):
    policy = tmp_path / "llm-models.v1.json"
    policy.write_text(json.dumps({"roles": []}), encoding="utf-8")
    with pytest.raises(RouterModelResolutionError):
        resolve_router_model(policy)


def test_resolve_router_model_wrong_provider(tmp_path):
    policy = tmp_path / "llm-models.v1.json"
    policy.write_text(
        json.dumps(
            {"roles": [{"id": "routerModel", "provider": "anthropic", "model": "x"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(RouterModelResolutionError):
        resolve_router_model(policy)


def test_resolve_router_model_missing_file(tmp_path):
    with pytest.raises(RouterModelResolutionError):
        resolve_router_model(tmp_path / "does-not-exist.json")


# ---------------------------------------------------------------------------
# has_openai_api_key semantics
# ---------------------------------------------------------------------------


def test_has_openai_api_key_semantics(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_fallback.has_openai_api_key() is False
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    assert llm_fallback.has_openai_api_key() is False
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real")
    assert llm_fallback.has_openai_api_key() is True
