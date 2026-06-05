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

from scripts.run_openclaw_followup import decide_to_json


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
