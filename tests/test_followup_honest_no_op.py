"""B155 / ADR 0034 path (b): honest no-op detection for free-text follow-ups.

The unit tests exercise the pure ``determine_applied_visible_effect`` decision
table; the integration test reproduces the operator case "Lägg till mycket mer
info om surdegsbröd" end-to-end through the prompt helper + builder with
``tmp_path`` storage (no OpenAI key, no real ``data/runs`` writes, ``do_build``
disabled so no npm install/build is required).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_site import (
    _dossier_has_copy_directives,
    _prompt_meta_followup_intent,
    determine_applied_visible_effect,
)
from scripts.prompt_to_project_input import generate, generate_followup

INITIAL_PROMPT = "Skapa en hemsida för ett surdegsbageri i Malmö."
NO_OP_FOLLOWUP_PROMPT = "Lägg till mycket mer info om surdegsbröd"
SITE_ID = "surdegsbageri-malmo"
PROJECT_ID = "stable-surdeg-project-id"


# ---------------------------------------------------------------------------
# Unit tests — pure decision table (AC1, AC3, AC4)
# ---------------------------------------------------------------------------


def test_init_build_has_no_applied_effect_field() -> None:
    # AC3: the concept only applies to follow-ups.
    applied, reason = determine_applied_visible_effect(
        mode="init",
        follow_up_intent="no-semantic-change",
        has_copy_directives=False,
    )
    assert applied is None
    assert reason is None


def test_no_semantic_change_intent_without_directives_is_no_op() -> None:
    # AC1(a): intent no-semantic-change AND no copyDirectives -> False.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent="no-semantic-change",
        has_copy_directives=False,
    )
    assert applied is False
    assert reason == "intent_no_semantic_change"


def test_no_op_intent_short_circuits_even_when_page_changed() -> None:
    # AC1 OR-semantics: condition (a) is sufficient on its own, so a
    # no-semantic-change follow-up stays honest even if some byte happened to
    # differ in page.tsx.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent="no-semantic-change",
        has_copy_directives=False,
        previous_page_source="<old/>",
        current_page_source="<new/>",
    )
    assert applied is False
    assert reason == "intent_no_semantic_change"


def test_byte_identical_page_is_no_op() -> None:
    # AC1(b): byte-identical page.tsx -> False even for a supported intent.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent="tone-shift",
        has_copy_directives=False,
        previous_page_source="export default function Page() {}",
        current_page_source="export default function Page() {}",
    )
    assert applied is False
    assert reason == "page_identical"


def test_tone_shift_with_changed_page_is_applied() -> None:
    # AC4: supported intent AND page.tsx differs -> True.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent="tone-shift",
        has_copy_directives=False,
        previous_page_source="<dark/>",
        current_page_source="<light/>",
    )
    assert applied is True
    assert reason == "page_changed"


def test_supported_intent_without_snapshot_predicts_applied() -> None:
    # No snapshot available -> fall back to the intent-based prediction.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent="tagline-update",
        has_copy_directives=False,
    )
    assert applied is True
    assert reason == "intent_tagline_update"


def test_copy_directives_override_no_op_intent() -> None:
    # An explicit copyDirective means a change was requested even if the
    # keyword classifier returned no-semantic-change.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent="no-semantic-change",
        has_copy_directives=True,
    )
    assert applied is True
    assert reason == "intent_no_semantic_change"


def test_missing_intent_defaults_to_no_op() -> None:
    # A pre-Project-DNA sidecar (intent None) is treated conservatively as a
    # no-op rather than claiming a phantom effect.
    applied, reason = determine_applied_visible_effect(
        mode="followup",
        follow_up_intent=None,
        has_copy_directives=False,
    )
    assert applied is False
    assert reason == "intent_no_semantic_change"


# ---------------------------------------------------------------------------
# Unit tests — helpers
# ---------------------------------------------------------------------------


def test_prompt_meta_followup_intent_reads_project_dna() -> None:
    meta = {"projectDna": {"followUpIntent": {"id": "tone-shift"}}}
    assert _prompt_meta_followup_intent(meta) == "tone-shift"


def test_prompt_meta_followup_intent_degrades_gracefully() -> None:
    assert _prompt_meta_followup_intent(None) is None
    assert _prompt_meta_followup_intent({}) is None
    assert _prompt_meta_followup_intent({"projectDna": {}}) is None
    assert _prompt_meta_followup_intent({"projectDna": {"followUpIntent": {}}}) is None


def test_dossier_copy_directives_detection() -> None:
    assert _dossier_has_copy_directives(None) is False
    assert _dossier_has_copy_directives({}) is False
    assert _dossier_has_copy_directives({"copyDirectives": []}) is False
    assert _dossier_has_copy_directives({"copyDirectives": [{"target": "hero"}]}) is True
    assert (
        _dossier_has_copy_directives(
            {"directives": {"copyDirectives": [{"target": "all-copy"}]}}
        )
        is True
    )


# ---------------------------------------------------------------------------
# Integration test — reproduce the operator case end-to-end (AC2, AC3, AC5)
# ---------------------------------------------------------------------------


def _bakery_discovery_payload() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "rawPrompt": INITIAL_PROMPT,
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {
            "siteType": ["business"],
            "companyName": "Surdegshörnan",
            "mustHave": ["Kontaktformulär"],
        },
    }


def _read_trace_events(run_dir: Path) -> list[dict[str, object]]:
    raw = (run_dir / "trace.ndjson").read_text(encoding="utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


@pytest.mark.tooling
def test_followup_free_text_content_prompt_reports_honest_no_op(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, initial_path, _ = generate(
        INITIAL_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
        discovery=_bakery_discovery_payload(),
    )
    _, followup_meta, followup_path, _ = generate_followup(
        NO_OP_FOLLOWUP_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
    )

    # The classifier must keep this free-text content prompt conservative.
    assert followup_meta["projectDna"]["followUpIntent"]["id"] == "no-semantic-change"

    _, run_dir_v1 = build(
        initial_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )
    _, run_dir_v2 = build(
        followup_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    result_v1 = json.loads((run_dir_v1 / "build-result.json").read_text(encoding="utf-8"))
    result_v2 = json.loads((run_dir_v2 / "build-result.json").read_text(encoding="utf-8"))

    # AC3: init build omits the field entirely.
    assert result_v1["engineMode"] == "init"
    assert "appliedVisibleEffect" not in result_v1

    # AC5: the follow-up created a new version but honestly reports no effect.
    assert result_v2["engineMode"] == "followup"
    assert result_v2["appliedVisibleEffect"] is False
    assert result_v2["appliedEffectReason"] == "intent_no_semantic_change"

    # AC2: a structured trace event is emitted, and it lands BEFORE the
    # build-result is written so Live Build Sync can react from the stream.
    events_v2 = _read_trace_events(run_dir_v2)
    event_names = [event["event"] for event in events_v2]
    assert "followup.no_op_detected" in event_names
    no_op_index = event_names.index("followup.no_op_detected")
    result_index = event_names.index("build.result.written")
    assert no_op_index < result_index
    no_op_event = events_v2[no_op_index]
    assert "intent_no_semantic_change" in str(no_op_event["message"])

    # Init builds never emit the honest-no-op event.
    assert "followup.no_op_detected" not in [
        event["event"] for event in _read_trace_events(run_dir_v1)
    ]
