"""Regression coverage for prompt follow-up versioning.

The tests exercise the real prompt helper and builder metadata path with
``tmp_path`` storage only. No OpenAI key or repository ``data/runs`` writes are
required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.prompt_to_project_input import generate, generate_followup


INITIAL_PROMPT = "Skapa en hemsida för en elektriker i Malmö."
FOLLOWUP_PROMPT = "Gör tonen mer premium och lägg mer fokus på snabb offert."
SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"


def _business_discovery_payload() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "rawPrompt": INITIAL_PROMPT,
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {
            "siteType": ["business"],
            "companyName": "Volt & Co",
            "mustHave": ["Kontaktformulär"],
        },
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_followup_pair(
    monkeypatch: pytest.MonkeyPatch,
    output_dir: Path,
) -> tuple[dict[str, object], dict[str, object], Path, dict[str, object], dict[str, object], Path]:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    initial_project_input, initial_meta, initial_path, _ = generate(
        INITIAL_PROMPT,
        output_dir=output_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
        discovery=_business_discovery_payload(),
    )
    followup_project_input, followup_meta, followup_path, _ = generate_followup(
        FOLLOWUP_PROMPT,
        output_dir=output_dir,
        site_id=SITE_ID,
    )
    return (
        initial_project_input,
        initial_meta,
        initial_path,
        followup_project_input,
        followup_meta,
        followup_path,
    )


@pytest.mark.tooling
def test_followup_preserves_project_identity_context_and_versions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    (
        initial_project_input,
        initial_meta,
        initial_path,
        followup_project_input,
        followup_meta,
        followup_path,
    ) = _generate_followup_pair(monkeypatch, prompt_inputs_dir)

    initial_snapshot = initial_path.read_text(encoding="utf-8")
    current_project_input = json.loads(
        (prompt_inputs_dir / f"{SITE_ID}.project-input.json").read_text(
            encoding="utf-8"
        )
    )
    current_meta = json.loads(
        (prompt_inputs_dir / f"{SITE_ID}.meta.json").read_text(encoding="utf-8")
    )

    assert initial_path.name == f"{SITE_ID}.v1.project-input.json"
    assert followup_path.name == f"{SITE_ID}.v2.project-input.json"
    assert initial_path.read_text(encoding="utf-8") == initial_snapshot
    assert current_project_input == followup_project_input
    assert current_meta == followup_meta

    assert followup_meta["projectId"] == initial_meta["projectId"] == PROJECT_ID
    assert followup_meta["siteId"] == SITE_ID
    assert followup_meta["mode"] == "followup"
    assert followup_meta["version"] == 2
    assert followup_meta["previousVersion"] == 1
    assert followup_meta["originalPrompt"] == initial_meta["originalPrompt"]
    assert followup_meta["followUpPrompt"] == FOLLOWUP_PROMPT

    stable_project_fields = (
        "siteId",
        "scaffoldId",
        "variantId",
        "language",
        "location",
        "contact",
        "selectedDossiers",
    )
    for field in stable_project_fields:
        assert followup_project_input[field] == initial_project_input[field]
    assert (
        followup_project_input["company"]["businessType"]
        == initial_project_input["company"]["businessType"]
    )
    assert (
        followup_project_input["company"]["story"]
        == initial_project_input["company"]["story"]
    )
    assert (
        followup_project_input["company"]["tagline"]
        == initial_project_input["company"]["tagline"]
    )

    initial_decision = initial_meta["discoveryDecision"]
    followup_decision = followup_meta["discoveryDecision"]
    assert followup_decision["categoryIds"] == initial_decision["categoryIds"]
    assert followup_decision["contentBranch"] == initial_decision["contentBranch"]
    assert (
        followup_decision["selectedScaffoldId"]
        == initial_decision["selectedScaffoldId"]
        == "local-service-business"
    )
    assert followup_decision["inheritedFromVersion"] == 1

    project_dna = followup_meta["projectDna"]
    assert project_dna["followUpIntent"]["id"] == "tone-shift"
    assert project_dna["story"] == initial_meta["projectDna"]["story"]
    assert project_dna["tagline"] == initial_meta["projectDna"]["tagline"]
    assert project_dna["tone"]["primary"]["lastUpdatedVersion"] == 2
    assert project_dna["tone"]["primary"]["source"] == "followup"


@pytest.mark.tooling
def test_followup_build_links_new_run_to_same_project_version_track(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from scripts.build_site import build

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"
    _, _, initial_path, _, _, followup_path = _generate_followup_pair(
        monkeypatch,
        prompt_inputs_dir,
    )

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

    assert run_dir_v1 != run_dir_v2
    assert run_dir_v1.parent == run_dir_v2.parent == runs_dir

    input_v1 = json.loads((run_dir_v1 / "input.json").read_text(encoding="utf-8"))
    input_v2 = json.loads((run_dir_v2 / "input.json").read_text(encoding="utf-8"))
    result_v1 = json.loads(
        (run_dir_v1 / "build-result.json").read_text(encoding="utf-8")
    )
    result_v2 = json.loads(
        (run_dir_v2 / "build-result.json").read_text(encoding="utf-8")
    )
    package_v2 = json.loads(
        (run_dir_v2 / "generation-package.json").read_text(encoding="utf-8")
    )
    site_brief_v2 = json.loads(
        (run_dir_v2 / "site-brief.json").read_text(encoding="utf-8")
    )
    site_plan_v2 = json.loads(
        (run_dir_v2 / "site-plan.json").read_text(encoding="utf-8")
    )

    assert input_v1["projectId"] == input_v2["projectId"] == PROJECT_ID
    assert input_v1["version"] == 1
    assert input_v2["version"] == 2
    assert input_v2["previousVersion"] == 1
    assert input_v2["followUpPrompt"] == FOLLOWUP_PROMPT

    assert result_v1["engineMode"] == "init"
    assert result_v2["engineMode"] == "followup"
    assert result_v2["projectId"] == PROJECT_ID
    assert result_v2["version"] == 2
    assert result_v2["prompt"]["previousVersion"] == 1
    assert result_v2["prompt"]["followUpPrompt"] == FOLLOWUP_PROMPT
    assert package_v2["engineMode"] == "followup"
    assert package_v2["projectId"] == PROJECT_ID

    assert site_brief_v2["runId"] == run_dir_v2.name
    assert SITE_ID in site_brief_v2["notesForPlanner"]
    assert site_brief_v2["businessTypeGuess"]
    assert site_plan_v2["runId"] == run_dir_v2.name
    assert site_plan_v2["scaffoldId"] == "local-service-business"
    assert site_plan_v2["routePlan"]


@pytest.mark.tooling
def test_followup_rejects_missing_previous_meta_without_writing_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="meta sidecar saknas"):
        generate_followup(
            FOLLOWUP_PROMPT,
            output_dir=tmp_path,
            site_id=SITE_ID,
        )

    assert not list(tmp_path.glob(f"{SITE_ID}.v*.project-input.json"))
    assert not list(tmp_path.glob(f"{SITE_ID}.v*.meta.json"))


@pytest.mark.tooling
def test_followup_rejects_invalid_previous_version_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _write_json(
        tmp_path / f"{SITE_ID}.meta.json",
        {
            "projectId": PROJECT_ID,
            "version": 0,
            "mode": "followup",
            "siteId": SITE_ID,
        },
    )

    with pytest.raises(SystemExit, match="ogiltig version"):
        generate_followup(
            FOLLOWUP_PROMPT,
            output_dir=tmp_path,
            site_id=SITE_ID,
        )

    assert not (tmp_path / f"{SITE_ID}.v1.project-input.json").exists()
    assert not (tmp_path / f"{SITE_ID}.v1.meta.json").exists()
