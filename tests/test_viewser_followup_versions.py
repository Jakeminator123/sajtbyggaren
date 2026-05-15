"""Source guards for Viewser follow-up version metadata.

These tests intentionally avoid tests/test_viewser_files.py because the
follow-up sprint is scoped away from the StackBlitz file surface locked
there. They guard the Viewser-side contract only: RunHistory must prefer
immutable per-run metadata, and the Project Input picker must not list
version snapshot files as duplicate selectable sites.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"


@pytest.mark.tooling
def test_run_history_prefers_immutable_run_metadata_before_sidecar() -> None:
    runs_ts = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")

    build_result_project = runs_ts.index("stringOrUndefined(result.projectId)")
    input_meta_project = runs_ts.index("inputMeta.projectId")
    prompt_meta_project = runs_ts.index("promptMeta.projectId")
    assert build_result_project < input_meta_project < prompt_meta_project

    build_result_version = runs_ts.index("numberOrNull(result.version)")
    input_meta_version = runs_ts.index("inputMeta.version")
    prompt_meta_version = runs_ts.index("promptMeta.version")
    assert build_result_version < input_meta_version < prompt_meta_version


@pytest.mark.tooling
def test_project_input_picker_filters_version_snapshots() -> None:
    project_inputs_ts = (VIEWSER_DIR / "lib" / "project-inputs.ts").read_text(
        encoding="utf-8"
    )

    assert "VERSIONED_PROJECT_INPUT_PATTERN" in project_inputs_ts
    assert "!VERSIONED_PROJECT_INPUT_PATTERN.test(entry.name)" in project_inputs_ts
