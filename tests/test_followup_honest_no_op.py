"""Regression coverage for B155 follow-up no-op honesty.

The tests exercise the builder-side contract only: follow-up builds get an
``appliedVisibleEffect`` boolean in build-result.json, and no-op follow-ups
also emit a structured trace event. UI presentation is intentionally out of
scope for this backend slice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_site import (
    _detect_followup_applied_visible_effect,
    _find_previous_page_snapshot,
    build,
)
from scripts.prompt_to_project_input import generate, generate_followup

INIT_PROMPT = "Skapa en hemsida för Surdegsbagaren i Malmö."
NO_OP_FOLLOWUP_PROMPT = "Lägg till mycket mer info om surdegsbröd"
SITE_ID = "surdegsbagaren-malmo"
PROJECT_ID = "b155-honest-no-op"
NO_OP_REASONS = {"intent_no_semantic_change", "visible_files_unchanged"}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_trace_events(run_dir: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


@pytest.mark.tooling
def test_init_build_omits_applied_visible_effect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )

    _, run_dir = build(
        init_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    build_result = _read_json(run_dir / "build-result.json")
    assert build_result["engineMode"] == "init"
    assert "appliedVisibleEffect" not in build_result
    assert "appliedVisibleEffectReason" not in build_result


@pytest.mark.tooling
def test_sourdough_followup_no_op_writes_build_result_and_trace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Jakob's "more info about sourdough bread" case must be honest.

    The reason assertion deliberately accepts both supported no-op paths:
    if the classifier stays conservative we expect intent-based detection;
    if it later learns a semantic intent, the unchanged page snapshot still
    proves that no visible home-page effect was applied.
    """

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    build(init_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir)

    _, followup_meta, followup_path, _ = generate_followup(
        NO_OP_FOLLOWUP_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
    )
    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    build_result = _read_json(run_dir_v2 / "build-result.json")
    assert build_result["engineMode"] == "followup"
    assert build_result["appliedVisibleEffect"] is False
    assert build_result["appliedVisibleEffectReason"] in NO_OP_REASONS

    actual_intent = followup_meta["projectDna"]["followUpIntent"]["id"]
    assert isinstance(actual_intent, str)

    events = _read_trace_events(run_dir_v2)
    event_names = [event["event"] for event in events]
    no_op_index = event_names.index("followup.no_op_detected")
    build_result_index = event_names.index("build.result.written")
    assert no_op_index < build_result_index
    no_op_event = events[no_op_index]
    assert no_op_event["status"] == "warning"
    assert no_op_event["reason"] in NO_OP_REASONS


@pytest.mark.tooling
def test_snapshot_diff_marks_semantic_followup_false_when_visible_files_are_unchanged(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    current_run = runs_root / "current-run"
    previous_page = previous_run / "generated-files" / "app" / "page.tsx"
    current_page = current_run / "generated-files" / "app" / "page.tsx"
    previous_page.parent.mkdir(parents=True)
    current_page.parent.mkdir(parents=True)
    previous_page.write_bytes(b"export default function Page() { return null }\n")
    current_page.write_bytes(b"export default function Page() { return null }\n")
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
        "previousVersion": 1,
        "projectDna": {"followUpIntent": {"id": "tone-shift"}},
    }

    effect = _detect_followup_applied_visible_effect(
        runs_root,
        current_run,
        prompt_meta,
        {},
    )

    assert effect == {"applied": False, "reason": "visible_files_unchanged"}


@pytest.mark.tooling
def test_snapshot_diff_marks_semantic_followup_true_when_visible_files_changed(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    current_run = runs_root / "current-run"
    previous_page = previous_run / "generated-files" / "app" / "page.tsx"
    current_page = current_run / "generated-files" / "app" / "page.tsx"
    previous_page.parent.mkdir(parents=True)
    current_page.parent.mkdir(parents=True)
    previous_page.write_bytes(b"previous page\n")
    current_page.write_bytes(b"changed page\n")
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
        "previousVersion": 1,
        "projectDna": {"followUpIntent": {"id": "tone-shift"}},
    }

    effect = _detect_followup_applied_visible_effect(
        runs_root,
        current_run,
        prompt_meta,
        {},
    )

    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_snapshot_diff_marks_tone_shift_true_when_only_css_changed(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    current_run = runs_root / "current-run"
    for run_dir, css in (
        (previous_run, b":root { --primary: #111111; }\n"),
        (current_run, b":root { --primary: #eeeeee; }\n"),
    ):
        page = run_dir / "generated-files" / "app" / "page.tsx"
        globals_css = run_dir / "generated-files" / "app" / "globals.css"
        page.parent.mkdir(parents=True)
        page.write_bytes(b"export default function Page() { return null }\n")
        globals_css.write_bytes(css)
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
        "previousVersion": 1,
        "projectDna": {"followUpIntent": {"id": "tone-shift"}},
    }

    effect = _detect_followup_applied_visible_effect(
        runs_root,
        current_run,
        prompt_meta,
        {},
    )

    assert effect == {"applied": True, "reason": "visible_files_changed"}


@pytest.mark.tooling
def test_previous_snapshot_lookup_derives_previous_version_from_current_version(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    previous_run = runs_root / "previous-run"
    previous_page = previous_run / "generated-files" / "app" / "page.tsx"
    previous_page.parent.mkdir(parents=True)
    previous_page.write_text("previous\n", encoding="utf-8")
    (previous_run / "input.json").write_text(
        json.dumps({"projectId": PROJECT_ID, "version": 1}),
        encoding="utf-8",
    )
    prompt_meta_without_previous_version = {
        "mode": "followup",
        "projectId": PROJECT_ID,
        "version": 2,
    }

    assert (
        _find_previous_page_snapshot(
            runs_root,
            runs_root / "current-run",
            prompt_meta_without_previous_version,
        )
        == previous_page
    )
