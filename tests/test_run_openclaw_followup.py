"""Smoke tests for the skiva 1b OpenClaw follow-up decision CLI.

scripts/run_openclaw_followup.py is the read-only decision seam apps/viewser
shells to. These tests lock the two contract guarantees that matter for the UI:

1. a pure question is answer_only (no build), and
2. an edit instruction is an HONEST patch_plan_request flagged
   action_bridge_missing - never a faked applied change - until the action
   bridge (next slice) lands.
"""

from __future__ import annotations

import json

import pytest

from scripts.run_openclaw_followup import apply_followup_to_json, decide_to_json


@pytest.mark.tooling
def test_followup_question_is_answer_only_no_build():
    payload = json.loads(decide_to_json("vad ar klockan?"))
    assert payload["action"] == "answer_only"
    # A read-only question must not produce a patch request.
    assert payload.get("patchPlanRequest") is None


@pytest.mark.tooling
def test_followup_edit_is_honest_action_bridge_missing():
    payload = json.loads(
        decide_to_json(
            "byt rubriken till Bryggans Surdegsbageri",
            site_id="painter-palma",
        )
    )
    assert payload["action"] == "patch_plan_request"
    ppr = payload["patchPlanRequest"]
    assert ppr["status"] == "action_bridge_missing"
    assert ppr["blockedBy"] == "openclaw-action-bridge"


@pytest.mark.tooling
def test_followup_decision_is_schema_stable_json():
    payload = json.loads(decide_to_json("vad ar klockan?"))
    # The UI branches on action + the nested router decision; both must be present.
    assert isinstance(payload.get("action"), str)
    assert isinstance(payload.get("router"), dict)
    assert isinstance(payload["router"].get("messageKind"), str)


# ---------------------------------------------------------------------------
# Action-bridge (--apply): the gate runs the chain only for edits.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_apply_non_edit_never_builds():
    """A read-only kind (answer_only) must NOT run the follow-up chain; the
    bridge reports no_build_needed without ever touching the build path."""
    payload = json.loads(
        apply_followup_to_json("vad ar klockan?", site_id="painter-palma")
    )
    assert payload["decision"]["action"] == "answer_only"
    bridge = payload["bridge"]
    assert bridge["status"] == "no_build_needed"
    assert bridge["applied"] is False
    assert bridge["previewShouldRefresh"] is False
    assert bridge["chain"] is None


@pytest.mark.tooling
def test_apply_edit_runs_chain_and_surfaces_result(monkeypatch):
    """An edit_instruction is delegated to run_followup_chain; the bridge
    surfaces the chain's authoritative outcome (stage/applied/previewRefresh)."""
    calls: dict[str, object] = {}

    def _fake_chain(site_id, follow_up_prompt, **kwargs):
        calls["site_id"] = site_id
        calls["prompt"] = follow_up_prompt
        calls["base_run_id"] = kwargs.get("base_run_id")
        return {
            "siteId": site_id,
            "stage": "built",
            "applied": True,
            "appliedVisibleEffect": True,
            "previewShouldRefresh": True,
            "version": 2,
            "runId": "run-2",
            "changedRoutes": ["/"],
        }

    monkeypatch.setattr("scripts.build_site.run_followup_chain", _fake_chain)
    payload = json.loads(
        apply_followup_to_json(
            "byt rubriken till Bryggans Surdegsbageri",
            site_id="painter-palma",
            base_run_id="run-1",
        )
    )
    assert payload["decision"]["action"] == "patch_plan_request"
    bridge = payload["bridge"]
    assert bridge["status"] == "built"
    assert bridge["applied"] is True
    assert bridge["previewShouldRefresh"] is True
    assert bridge["chain"]["runId"] == "run-2"
    # The bridge forwarded the message + base run to the chain.
    assert calls == {
        "site_id": "painter-palma",
        "prompt": "byt rubriken till Bryggans Surdegsbageri",
        "base_run_id": "run-1",
    }


@pytest.mark.tooling
def test_apply_edit_honest_no_op_when_chain_does_not_apply(monkeypatch):
    """When the chain makes no patchable change the bridge reports the honest
    no-op stage and never sets previewShouldRefresh."""

    def _fake_chain(site_id, follow_up_prompt, **kwargs):
        return {
            "siteId": site_id,
            "stage": "plan_empty",
            "applied": False,
            "appliedVisibleEffect": False,
            "previewShouldRefresh": False,
        }

    monkeypatch.setattr("scripts.build_site.run_followup_chain", _fake_chain)
    payload = json.loads(
        apply_followup_to_json("gör hero mer premium", site_id="painter-palma")
    )
    bridge = payload["bridge"]
    assert bridge["applied"] is False
    assert bridge["previewShouldRefresh"] is False
    assert bridge["status"] == "plan_empty"


@pytest.mark.tooling
def test_apply_edit_no_base_run_degrades_to_honest_error(monkeypatch):
    """If the chain raises SystemExit (no prior run to build on) the bridge
    degrades to an honest error instead of crashing."""

    def _fake_chain(site_id, follow_up_prompt, **kwargs):
        raise SystemExit("no previous run for site")

    monkeypatch.setattr("scripts.build_site.run_followup_chain", _fake_chain)
    payload = json.loads(
        apply_followup_to_json("byt rubriken till X", site_id="painter-palma")
    )
    bridge = payload["bridge"]
    assert bridge["status"] == "error"
    assert bridge["applied"] is False


# ---------------------------------------------------------------------------
# F1 slice 2: conversation gate (answer-only, no build) + role metadata.
# ---------------------------------------------------------------------------


def _forbid_chain(monkeypatch):
    """Make any chain invocation an immediate test failure (no build allowed)."""

    def _explode(*args, **kwargs):  # pragma: no cover - reaching this IS the bug
        raise AssertionError("run_followup_chain must NOT run for a conversation")

    monkeypatch.setattr("scripts.build_site.run_followup_chain", _explode)


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("message", "expected_kind"),
    [
        ("dra ett skämt", "small_talk"),
        ("vad tycker du om sajten?", "site_opinion"),
        ("vad kostar en hemsida?", "question"),
    ],
)
def test_apply_conversation_is_answer_only_and_never_builds(
    monkeypatch, message: str, expected_kind: str
):
    """A conversation kind stops BEFORE the chain with an honest answer-only
    decision: no version written, no render, previewShouldRefresh False."""
    _forbid_chain(monkeypatch)
    payload = json.loads(apply_followup_to_json(message, site_id="painter-palma"))
    decision = payload["decision"]
    assert decision["action"] == "answer_only"
    assert decision["appliedVisibleEffect"] is False
    assert decision["patchPlanRequest"] is None
    assert isinstance(decision["answer"], str) and decision["answer"]
    conversation = decision["conversation"]
    assert conversation["conversationKind"] == expected_kind
    assert conversation["role"] == "router"
    bridge = payload["bridge"]
    assert bridge["status"] == "no_build_needed"
    assert bridge["applied"] is False
    assert bridge["previewShouldRefresh"] is False
    assert bridge["chain"] is None


@pytest.mark.tooling
def test_apply_edit_keeps_chain_flow_and_carries_role_metadata(monkeypatch):
    """An edit ("gör sajten mörkblå") keeps the EXACT same chain flow as
    before; the owning role (stylist) is attached as metadata only."""
    calls: dict[str, object] = {}

    def _fake_chain(site_id, follow_up_prompt, **kwargs):
        calls["site_id"] = site_id
        calls["prompt"] = follow_up_prompt
        return {
            "siteId": site_id,
            "stage": "built",
            "applied": True,
            "appliedVisibleEffect": True,
            "previewShouldRefresh": True,
            "version": 3,
            "runId": "run-3",
        }

    monkeypatch.setattr("scripts.build_site.run_followup_chain", _fake_chain)
    payload = json.loads(
        apply_followup_to_json("gör sajten mörkblå", site_id="painter-palma")
    )
    # The chain ran exactly as before (unchanged behaviour).
    assert calls["site_id"] == "painter-palma"
    assert calls["prompt"] == "gör sajten mörkblå"
    assert payload["decision"]["action"] == "patch_plan_request"
    assert payload["bridge"]["applied"] is True
    assert payload["bridge"]["chain"]["runId"] == "run-3"
    # The role is pure metadata in the decision payload.
    conversation = payload["decision"]["conversation"]
    assert conversation["conversationKind"] == "edit"
    assert conversation["role"] == "stylist"


@pytest.mark.tooling
def test_decide_conversation_is_answer_only_with_metadata():
    """The read-only mode carries the same honest answer-only reframe."""
    payload = json.loads(decide_to_json("dra ett skämt"))
    assert payload["action"] == "answer_only"
    assert payload["patchPlanRequest"] is None
    assert payload["conversation"]["conversationKind"] == "small_talk"


@pytest.mark.tooling
def test_decide_edit_decision_is_unchanged_with_role_metadata():
    """An edit's decision is byte-identical to before apart from the additive
    ``conversation`` metadata block (role as metadata, no behaviour change)."""
    payload = json.loads(
        decide_to_json("gör sajten mörkblå", site_id="painter-palma")
    )
    conversation = payload.pop("conversation")
    assert conversation == {
        "conversationKind": "edit",
        "role": "stylist",
        "source": conversation["source"],
        "rationale": conversation["rationale"],
    }
    assert payload["action"] == "patch_plan_request"
    ppr = payload["patchPlanRequest"]
    assert ppr["status"] == "action_bridge_missing"


@pytest.mark.tooling
def test_conversation_gate_no_key_parity(monkeypatch):
    """Without OPENAI_API_KEY the gate still answers honestly (exit 0 path):
    deterministic answer-only decision, source mock-no-key, never a build."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _forbid_chain(monkeypatch)
    payload = json.loads(
        apply_followup_to_json("dra ett skämt", site_id="painter-palma")
    )
    decision = payload["decision"]
    assert decision["action"] == "answer_only"
    assert decision["conversation"]["conversationKind"] == "small_talk"
    assert decision["conversation"]["source"] == "mock-no-key"
    assert payload["bridge"]["applied"] is False
