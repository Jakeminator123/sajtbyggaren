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
