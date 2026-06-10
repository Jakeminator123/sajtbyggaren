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
import sys

import pytest

from scripts.run_openclaw_followup import (
    BRIDGE_SENTINEL_PREFIX,
    apply_followup_to_json,
    decide_to_json,
    main,
)


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


# ---------------------------------------------------------------------------
# B174: the CLI's stdout contract — the payload is the FINAL line behind the
# OPENCLAW_BRIDGE_JSON: sentinel, even when the chain prints build progress to
# the same stream first. apps/viewser/lib/openclaw-runner.ts scans for this.
# ---------------------------------------------------------------------------


def _last_stdout_line(capsys) -> str:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert lines, "CLI printed nothing to stdout"
    return lines[-1]


def _payload_from_sentinel_line(line: str) -> dict:
    assert line.startswith(BRIDGE_SENTINEL_PREFIX), (
        f"sista stdout-raden måste börja med {BRIDGE_SENTINEL_PREFIX!r}, "
        f"fick: {line[:80]!r}"
    )
    return json.loads(line[len(BRIDGE_SENTINEL_PREFIX) :])


@pytest.mark.tooling
def test_cli_readonly_emits_sentinel_prefixed_payload_line(monkeypatch, capsys):
    """The read-only mode prints the decision behind the sentinel prefix so
    the TS runner has one explicit contract line for BOTH modes."""
    monkeypatch.setattr(
        sys, "argv", ["run_openclaw_followup.py", "--", "vad ar klockan?"]
    )
    assert main() == 0
    payload = _payload_from_sentinel_line(_last_stdout_line(capsys))
    assert payload["action"] == "answer_only"


@pytest.mark.tooling
def test_cli_apply_sentinel_survives_build_progress_noise(monkeypatch, capsys):
    """B174 regression shape: with --apply the chain (build_site.build) prints
    human progress ("runId: ...", "Copying starter ...", npm notices) to the
    SAME stdout BEFORE the payload. The sentinel line must still be the LAST
    stdout line and parse cleanly to the {decision, bridge} object — the blind
    JSON.parse(stdout) in the old TS runner threw on exactly this stream."""

    def _noisy_chain(site_id, follow_up_prompt, **kwargs):
        print(f"runId: 20260610-abcdef-{site_id}")
        print("Copying starter into builds/20260610/ ...")
        print("npm notice New minor version of npm available! 11.3.0 -> 11.4.1")
        return {
            "siteId": site_id,
            "stage": "built",
            "applied": True,
            "appliedVisibleEffect": True,
            "previewShouldRefresh": True,
            "version": 2,
            "runId": f"20260610-abcdef-{site_id}",
        }

    monkeypatch.setattr("scripts.build_site.run_followup_chain", _noisy_chain)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_openclaw_followup.py",
            "--apply",
            "--site-id",
            "painter-palma",
            "--",
            "byt rubriken till Bryggans Surdegsbageri",
        ],
    )
    assert main() == 0
    out_lines = [
        line for line in capsys.readouterr().out.splitlines() if line.strip()
    ]
    # The progress noise really was printed to stdout before the payload
    # (the regression shape), and the sentinel line is LAST.
    assert any(line.startswith("runId:") for line in out_lines[:-1])
    payload = _payload_from_sentinel_line(out_lines[-1])
    assert payload["decision"]["action"] == "patch_plan_request"
    assert payload["bridge"]["applied"] is True
    assert payload["bridge"]["chain"]["version"] == 2


@pytest.mark.tooling
def test_cli_apply_conversation_emits_sentinel_payload(monkeypatch, capsys):
    """--apply on a conversation kind never builds, and the no-build payload
    uses the same sentinel contract line."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_openclaw_followup.py",
            "--apply",
            "--site-id",
            "painter-palma",
            "--",
            "vad ar klockan?",
        ],
    )
    assert main() == 0
    payload = _payload_from_sentinel_line(_last_stdout_line(capsys))
    assert payload["decision"]["action"] == "answer_only"
    assert payload["bridge"]["status"] == "no_build_needed"


# ---------------------------------------------------------------------------
# B178: a site-scoped question WITHOUT an explicit baseRunId auto-resolves the
# site's latest completed run (read-only) so the context payload is populated.
# /api/prompt normally sends no baseRunId, so before the fix a site_opinion
# question got an empty context despite runs on disk.
# ---------------------------------------------------------------------------


def _seed_run(runs_dir, run_id: str, site_id: str):
    """Seed a minimal completed run: build-result.json + site-brief.json."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "build-result.json").write_text(
        json.dumps({"siteId": site_id, "runId": run_id}), encoding="utf-8"
    )
    (run_dir / "site-brief.json").write_text(
        json.dumps({"runId": run_id, "language": "sv", "rawPrompt": "seeded"}),
        encoding="utf-8",
    )
    return run_dir


def _file_snapshot(root) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*")}


@pytest.mark.tooling
def test_b178_site_opinion_without_base_run_gets_populated_context(
    monkeypatch, tmp_path
):
    """A site_opinion decision without baseRunId reads the site's latest run:
    non-empty context payload, runId resolved, and NOTHING written to disk."""
    runs_dir = tmp_path / "runs"
    _seed_run(runs_dir, "run-volt-1", "volt-watt")
    monkeypatch.setenv("VIEWSER_RUNS_DIR", str(runs_dir))

    before = _file_snapshot(tmp_path)
    payload = json.loads(
        decide_to_json("vad tycker du om sajten?", site_id="volt-watt")
    )
    after = _file_snapshot(tmp_path)

    context = payload["context"]
    assert context["runId"] == "run-volt-1"
    assert context["payload"], "context payload must not be empty (B178)"
    assert "siteBrief" in context["payload"]
    assert payload["conversation"]["conversationKind"] == "site_opinion"
    # Read-only guarantee: the decision created no files anywhere in the tree.
    assert before == after


@pytest.mark.tooling
def test_b178_resolution_filters_on_site_id(monkeypatch, tmp_path):
    """The newest run on disk belongs to ANOTHER site - the resolver must skip
    it and pick the newest run that actually belongs to the asked site."""
    import os
    import time

    runs_dir = tmp_path / "runs"
    mine = _seed_run(runs_dir, "run-volt-1", "volt-watt")
    other = _seed_run(runs_dir, "run-other-9", "other-site")
    now = time.time()
    os.utime(mine, (now - 100, now - 100))
    os.utime(other, (now, now))
    monkeypatch.setenv("VIEWSER_RUNS_DIR", str(runs_dir))

    payload = json.loads(
        decide_to_json("vad tycker du om sajten?", site_id="volt-watt")
    )
    assert payload["context"]["runId"] == "run-volt-1"


@pytest.mark.tooling
def test_b178_explicit_base_run_id_still_wins(monkeypatch, tmp_path):
    """An explicit baseRunId ('Iterera från denna') is forwarded verbatim and
    never overridden by the auto-resolver."""
    import os
    import time

    runs_dir = tmp_path / "runs"
    old = _seed_run(runs_dir, "run-volt-1", "volt-watt")
    new = _seed_run(runs_dir, "run-volt-2", "volt-watt")
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now, now))
    monkeypatch.setenv("VIEWSER_RUNS_DIR", str(runs_dir))

    payload = json.loads(
        decide_to_json(
            "vad tycker du om sajten?",
            site_id="volt-watt",
            base_run_id="run-volt-1",
        )
    )
    assert payload["context"]["runId"] == "run-volt-1"


@pytest.mark.tooling
def test_b178_no_runs_on_disk_keeps_honest_empty_context(monkeypatch, tmp_path):
    """Without any completed run the context stays honestly empty (the same
    missing-run_id note as before the fix) - nothing is invented."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    monkeypatch.setenv("VIEWSER_RUNS_DIR", str(runs_dir))

    payload = json.loads(
        decide_to_json("vad tycker du om sajten?", site_id="volt-watt")
    )
    context = payload["context"]
    assert context["payload"] == {}
    assert any("run_id" in note for note in context["notes"])


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
