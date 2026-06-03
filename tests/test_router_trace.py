"""Trace-rule tests for the router (KÖR-6a).

The kor-6a trace rule is strict:
- A decision that belongs to an existing run is appended to that run's
  trace.ndjson (append-only, never overwrites).
- A decision without a run (the typical answer_only case) creates NO run -
  the logger returns False and writes nothing.

Tests use ``tmp_path`` so they never touch the canonical data/runs/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.router import (  # noqa: E402
    classify_message,
    log_router_decision_to_existing_run,
)


def test_logs_into_existing_run_appends_engine_event(tmp_path: Path):
    run_dir = tmp_path / "run-abc123"
    run_dir.mkdir()
    trace = run_dir / "trace.ndjson"
    # Pre-existing run trace with one event.
    trace.write_text(
        json.dumps({"runId": "run-abc123", "phase": "build", "event": "x", "status": "done"})
        + "\n",
        encoding="utf-8",
    )

    decision = classify_message("lägg en klocka i andra sektionen till vänster")
    appended = log_router_decision_to_existing_run(run_dir, decision)

    assert appended is True
    lines = trace.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "must append, not overwrite the existing trace"
    record = json.loads(lines[-1])
    assert record["runId"] == "run-abc123"
    assert record["phase"] == "route"
    assert record["event"] == "router-decision"
    assert record["status"] == "done"
    # Engine Event shape parity with build_site.py / dev_generate.py.
    for field in ("runId", "phase", "event", "status", "message", "timestamp", "payloadPath"):
        assert field in record
    # The structured decision rides along for later inspection.
    assert record["decision"]["messageKind"] == "edit_instruction"
    assert record["decision"]["componentIntent"] == "clock_widget"


def test_answer_only_without_run_creates_no_run(tmp_path: Path):
    """The core kor-6a guarantee: a pure question without a run must not
    cause a run directory to be created just for logging."""
    ghost = tmp_path / "does-not-exist"
    decision = classify_message("vad är klockan?")
    assert decision.messageKind == "answer_only"

    appended = log_router_decision_to_existing_run(ghost, decision)

    assert appended is False
    assert not ghost.exists(), "no run directory may be created for logging"
    # And nothing was written anywhere under tmp_path.
    assert list(tmp_path.iterdir()) == []


def test_run_id_defaults_to_dir_name_but_can_be_overridden(tmp_path: Path):
    run_dir = tmp_path / "run-default-id"
    run_dir.mkdir()

    decision = classify_message("vilka klockor finns?")
    assert log_router_decision_to_existing_run(run_dir, decision) is True
    record = json.loads((run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()[-1])
    assert record["runId"] == "run-default-id"

    assert (
        log_router_decision_to_existing_run(run_dir, decision, run_id="explicit-run") is True
    )
    record2 = json.loads(
        (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert record2["runId"] == "explicit-run"


def test_logging_a_file_path_instead_of_dir_is_a_no_op(tmp_path: Path):
    """Defensive: if a file path is passed (not a run directory), the logger
    treats it as 'no existing run' and writes nothing."""
    not_a_dir = tmp_path / "some-file.txt"
    not_a_dir.write_text("x", encoding="utf-8")
    decision = classify_message("vad är klockan?")
    assert log_router_decision_to_existing_run(not_a_dir, decision) is False
    assert not_a_dir.read_text(encoding="utf-8") == "x"
