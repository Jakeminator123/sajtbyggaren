"""LLM Golden Path v1 smoke test.

Locks the narrow vertical slice that turns a free prompt into a built site
and a follow-up prompt into a new immutable version of the same project:

    prompt -> Project Input v1 -> build() -> run_v1
    follow-up prompt -> Project Input v2 -> build() -> run_v2

The test does not introduce new contracts. It exercises the real
``scripts.prompt_to_project_input.generate`` /
``scripts.prompt_to_project_input.generate_followup`` helpers and the real
``scripts.build_site.build`` entry-point with ``do_build=False`` so it never
shells out to ``npm install`` or ``npm run build``. ``OPENAI_API_KEY`` is
unset so both ``briefModel`` and ``planningModel`` fall back to the
deterministic mock paths, which keeps the smoke test runnable on any
agent (cloud or local) without network access or secrets.

The complementary test ``tests/test_followup_versioning_regression.py``
asserts the fine-grained semantic merge contract (tone shift, project DNA,
discovery decision inheritance). This smoke test asserts the coarse
artefakt contract: every run writes the eight canonical Engine Run files
plus a generated-files snapshot, and the v1 -> v2 chain preserves
``projectId`` / ``version`` / ``previousVersion`` / ``followUpPrompt``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_site import build
from scripts.prompt_to_project_input import generate, generate_followup

INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö."
FOLLOWUP_PROMPT = "Gör tonen mer premium."
SITE_ID = "electrician-malmo"
PROJECT_ID = "golden-path-smoke"

_REQUIRED_RUN_FILES = (
    "input.json",
    "site-brief.json",
    "site-plan.json",
    "generation-package.json",
    "quality-result.json",
    "repair-result.json",
    "build-result.json",
    "trace.ndjson",
)

_ACCEPTED_QUALITY_STATUSES = frozenset({"ok", "skipped"})


def _assert_run_artefakts_present(run_dir: Path) -> None:
    """Every run must produce the eight canonical files + a snapshot."""

    for name in _REQUIRED_RUN_FILES:
        artefakt = run_dir / name
        assert artefakt.is_file(), (
            f"Missing canonical run artefakt {name!r} under {run_dir}. "
            "The LLM Golden Path contract requires all eight files plus "
            "the generated-files snapshot per build."
        )

    home_page = run_dir / "generated-files" / "app" / "page.tsx"
    assert home_page.is_file(), (
        f"Missing generated home page at {home_page}. The build snapshot "
        "must contain app/page.tsx so the preview can render the site."
    )


@pytest.mark.tooling
def test_llm_golden_path_init_and_followup_smoke(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Init prompt + follow-up prompt run end-to-end through the pipeline.

    The test pins the public contract of the Golden Path:

    1. ``generate`` writes an immutable ``.v1.project-input.json`` snapshot
       with the operator-supplied ``projectId`` and version 1.
    2. ``build`` consumes that snapshot and emits a complete Engine Run
       directory (eight canonical artefakts + generated-files snapshot).
    3. ``generate_followup`` inherits ``projectId`` / discovery decision,
       bumps to version 2, and records ``previousVersion`` +
       ``followUpPrompt`` on the new snapshot.
    4. A second ``build`` produces a distinct run directory whose
       ``build-result.json`` declares ``engineMode == "followup"``.
    """

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_pi_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )

    assert init_pi_path.name == f"{SITE_ID}.v1.project-input.json"

    _, run_dir_v1 = build(
        init_pi_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    _, _, followup_pi_path, _ = generate_followup(
        FOLLOWUP_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
    )

    assert followup_pi_path.name == f"{SITE_ID}.v2.project-input.json"

    _, run_dir_v2 = build(
        followup_pi_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    _assert_run_artefakts_present(run_dir_v1)
    _assert_run_artefakts_present(run_dir_v2)

    assert run_dir_v1 != run_dir_v2, (
        "Follow-up build must write to a new run directory; reusing "
        "run_v1 would break version provenance and trace history."
    )
    assert run_dir_v1.parent == run_dir_v2.parent == runs_dir

    input_v1 = json.loads((run_dir_v1 / "input.json").read_text(encoding="utf-8"))
    input_v2 = json.loads((run_dir_v2 / "input.json").read_text(encoding="utf-8"))
    build_result_v1 = json.loads(
        (run_dir_v1 / "build-result.json").read_text(encoding="utf-8")
    )
    build_result_v2 = json.loads(
        (run_dir_v2 / "build-result.json").read_text(encoding="utf-8")
    )
    quality_v1 = json.loads(
        (run_dir_v1 / "quality-result.json").read_text(encoding="utf-8")
    )
    quality_v2 = json.loads(
        (run_dir_v2 / "quality-result.json").read_text(encoding="utf-8")
    )

    assert input_v1["projectId"] == PROJECT_ID
    assert input_v2["projectId"] == PROJECT_ID
    assert input_v1["version"] == 1
    assert input_v2["version"] == 2
    assert input_v2["previousVersion"] == 1
    assert input_v2["followUpPrompt"] == FOLLOWUP_PROMPT

    assert build_result_v1["engineMode"] == "init"
    assert build_result_v2["engineMode"] == "followup"

    for run_label, quality_payload in (("v1", quality_v1), ("v2", quality_v2)):
        assert quality_payload["status"] in _ACCEPTED_QUALITY_STATUSES, (
            f"quality-result.json status for {run_label} was "
            f"{quality_payload['status']!r}; expected one of "
            f"{sorted(_ACCEPTED_QUALITY_STATUSES)}. The smoke test runs "
            "with do_build=False, which keeps the blocking typecheck +/- "
            "build-status checks skipped so the aggregate must stay "
            "non-failing."
        )
