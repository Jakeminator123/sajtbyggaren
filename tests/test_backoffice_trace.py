"""Regression tests for BO2/BO4 backoffice trace and playground helpers."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.tooling


@pytest.mark.tooling
def test_load_trace_events_tolerates_partial_ndjson(tmp_path: Path) -> None:
    from backoffice.views._trace import load_trace_events

    trace_path = tmp_path / "trace.ndjson"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "runId": "run-1",
                        "phase": "understand",
                        "event": "brief.written",
                        "status": "done",
                        "message": "site-brief.json written",
                        "timestamp": "2026-05-13T20:00:00+00:00",
                        "payloadPath": "site-brief.json",
                    }
                ),
                "{partial",
                json.dumps(["not", "an", "event"]),
                "",
            ]
        ),
        encoding="utf-8",
    )

    events, skipped_lines = load_trace_events(trace_path)

    assert len(events) == 1
    assert events[0]["phase"] == "understand"
    assert skipped_lines == 2


@pytest.mark.tooling
def test_trace_summary_and_severity_mark_important_events() -> None:
    from backoffice.views._trace import (
        event_badges,
        event_severity,
        summarize_trace_events,
    )

    events = [
        {
            "phase": "build",
            "event": "quality_result.written",
            "status": "done",
            "message": "Quality Gate status=ok",
            "timestamp": "2026-05-13T20:00:00+00:00",
        },
        {
            "phase": "build",
            "event": "repair_result.written",
            "status": "degraded",
            "message": "Repair Pipeline remainingErrors=1",
            "timestamp": "2026-05-13T20:00:01+00:00",
        },
        {
            "phase": "build",
            "event": "build.failed",
            "status": "failed",
            "message": "npm build failed",
            "timestamp": "2026-05-13T20:00:02+00:00",
        },
        {
            "phase": "plan",
            "event": "planning.mock",
            "status": "started",
            "message": "No OPENAI_API_KEY - mock plan",
            "timestamp": "2026-05-13T19:59:59+00:00",
        },
    ]

    summary = summarize_trace_events(events)

    assert summary["total"] == 4
    assert summary["phases"] == {"build": 3, "plan": 1}
    assert summary["severities"]["success"] == 1
    assert summary["severities"]["warning"] == 1
    assert summary["severities"]["error"] == 1
    assert summary["latestTimestamp"] == "2026-05-13T20:00:02+00:00"
    assert event_badges(events[0]) == ["quality"]
    assert event_badges(events[1]) == ["repair"]
    assert event_severity(events[2]) == "error"


@pytest.mark.tooling
@pytest.mark.parametrize("status", ["broken", "token", "revoked"])
def test_event_severity_does_not_match_ok_inside_status_words(status: str) -> None:
    from backoffice.views._trace import event_severity

    assert event_severity({"status": status, "event": "noop", "message": ""}) == "info"


@pytest.mark.tooling
def test_filter_events_empty_phase_or_status_selection_returns_empty() -> None:
    from backoffice.views._trace import _filter_events

    events = [
        {"phase": "engine", "status": "started", "event": "run.started"},
        {"phase": "build", "status": "done", "event": "phase.completed"},
    ]

    assert _filter_events(events, [], ["started", "done"], "") == []
    assert _filter_events(events, ["engine", "build"], [], "") == []
    assert _filter_events(events, ["engine"], ["started"], "") == [events[0]]


@pytest.mark.tooling
def test_playground_extracts_run_id_from_supported_outputs() -> None:
    from backoffice.views.playground import _extract_run_id

    assert (
        _extract_run_id("\nRun complete: /workspace/data/runs/2026-abc\n")
        == "2026-abc"
    )
    assert (
        _extract_run_id("\nRun complete: C:\\workspace\\data\\runs\\2026-win\n")
        == "2026-win"
    )
    assert (
        _extract_run_id("\nRun complete: /workspace/data/runs/2026-trailing/\n")
        == "2026-trailing"
    )
    assert (
        _extract_run_id("[engine.run.started] ok: runId=2026-def phase=all mode=init")
        == "2026-def"
    )


@pytest.mark.tooling
def test_playground_runner_uses_popen_not_subprocess_run() -> None:
    from backoffice.views import playground

    source = inspect.getsource(playground._run_dev_generate)
    assert "subprocess.Popen(" in source
    assert "subprocess.run(" not in source


@pytest.mark.tooling
def test_playground_runner_forwards_followup_project_id(monkeypatch) -> None:
    """Backoffice Playground must pass project_id through to dev_generate.

    This protects the follow-up semantics contract from regressing at the UI
    runner layer. The deeper dev_generate test locks that the package artifact
    receives the same mode/projectId.
    """
    from backoffice.views import playground

    captured: dict[str, list[str]] = {}

    class stdout_stub:
        def readline(self) -> str:
            return ""

        def close(self) -> None:
            return None

    class process_stub:
        stdout = stdout_stub()

        def __init__(self, args, **kwargs) -> None:
            captured["args"] = list(args)
            captured["kwargs"] = kwargs

        def poll(self) -> int:
            return 0

        def wait(self) -> int:
            return 0

    monkeypatch.setattr(playground.subprocess, "Popen", process_stub)

    result = playground._run_dev_generate(
        "Uppdatera hero",
        "followup",
        "plan",
        run_id="run-123",
        project_id="project-abc",
        timeout_seconds=1,
    )

    assert result["exit_code"] == 0
    assert "--mode" in captured["args"]
    assert "followup" in captured["args"]
    assert "--project-id" in captured["args"]
    assert "project-abc" in captured["args"]
    assert captured["kwargs"]["env"]["SAJTBYGGAREN_MODE"] == "followup"


@pytest.mark.tooling
def test_trace_views_use_structured_trace_viewer() -> None:
    from backoffice.views import engine_runs, playground

    engine_source = inspect.getsource(engine_runs.view_engine_runs)
    playground_source = inspect.getsource(playground.view_playground)

    assert "render_trace_viewer(" in engine_source
    assert "render_trace_viewer(" in playground_source
    assert "st.dataframe(events" not in engine_source
    assert "st.dataframe(events" not in playground_source
