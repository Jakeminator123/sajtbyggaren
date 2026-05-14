"""End-to-end tests for the mock Engine Run driver (scripts/dev_generate.py).

We run the script as a subprocess with a temporary --data-runs-dir, then
assert that all eight artifacts plus the trace are written and that the
trace contains the expected Engine Events in order.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR


def _run_dev_generate(tmp_path: Path, prompt: str, *args: str) -> tuple[int, Path, str]:
    """Invoke dev_generate.py with a tmp data-runs dir; return (rc, runs_dir, output)."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "dev_generate.py"),
        prompt,
        "--data-runs-dir",
        str(runs_dir),
        *args,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))
    return result.returncode, runs_dir, (result.stdout or "") + (result.stderr or "")


def _only_run_dir(runs_dir: Path) -> Path:
    """Return the single subdirectory the run created."""
    children = [p for p in runs_dir.iterdir() if p.is_dir()]
    assert len(children) == 1, f"Expected exactly one run dir, got {children}"
    return children[0]


@pytest.mark.tooling
def test_dev_generate_all_phases_writes_all_artifacts(tmp_path: Path):
    rc, runs_dir, output = _run_dev_generate(
        tmp_path, "Skapa hemsida för elektriker i Malmö"
    )
    assert rc == 0, f"dev_generate failed: {output}"

    run_dir = _only_run_dir(runs_dir)

    expected_files = [
        "input.json",
        "site-brief.json",
        "site-plan.json",
        "generation-package.json",
        "repair-result.json",
        "quality-result.json",
        "build-result.json",
        "trace.ndjson",
    ]
    for name in expected_files:
        assert (run_dir / name).exists(), f"Missing artifact: {name}"

    files_dir = run_dir / "generated-files"
    assert files_dir.is_dir(), "generated-files/ missing"
    assert (files_dir / "app.tsx").exists()


@pytest.mark.tooling
def test_dev_generate_trace_has_expected_events(tmp_path: Path):
    rc, runs_dir, output = _run_dev_generate(
        tmp_path, "Skapa hemsida för elektriker i Malmö"
    )
    assert rc == 0, output

    run_dir = _only_run_dir(runs_dir)
    trace = (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in trace if line.strip()]

    phases_seen = [e["phase"] for e in events]
    assert "engine" in phases_seen
    assert "understand" in phases_seen
    assert "plan" in phases_seen
    assert "build" in phases_seen

    statuses = {e["event"] for e in events}
    assert "run.started" in statuses
    assert "run.done" in statuses
    assert "files.written" in statuses
    # Sprint 3A harmonised event names: dev_generate now emits the same
    # dotted phase events as scripts/build_site.py (was: quality.done /
    # repair.done / result.written, now: quality_result.written /
    # repair_result.written / build.result.written). A single Backoffice
    # consumer can render both runner outputs without per-driver casing.
    assert "quality_result.written" in statuses
    assert "repair_result.written" in statuses
    assert "build.result.written" in statuses


@pytest.mark.tooling
def test_dev_generate_brief_only_skips_later_phases(tmp_path: Path):
    rc, runs_dir, output = _run_dev_generate(
        tmp_path, "A small clinic in Stockholm", "--phase", "brief"
    )
    assert rc == 0, output

    run_dir = _only_run_dir(runs_dir)
    assert (run_dir / "site-brief.json").exists()
    assert not (run_dir / "site-plan.json").exists(), "plan phase should not have run"
    assert not (run_dir / "build-result.json").exists(), "build phase should not have run"


@pytest.mark.tooling
def test_dev_generate_plan_then_build_can_resume(tmp_path: Path):
    rc, runs_dir, output = _run_dev_generate(
        tmp_path, "Skapa restaurangsajt", "--phase", "brief"
    )
    assert rc == 0, output
    run_dir = _only_run_dir(runs_dir)
    run_id = run_dir.name

    rc2, _, output2 = _run_dev_generate(
        tmp_path, "Skapa restaurangsajt", "--phase", "plan", "--run-id", run_id
    )
    assert rc2 == 0, output2
    assert (run_dir / "generation-package.json").exists()

    rc3, _, output3 = _run_dev_generate(
        tmp_path, "Skapa restaurangsajt", "--phase", "build", "--run-id", run_id
    )
    assert rc3 == 0, output3
    assert (run_dir / "build-result.json").exists()


@pytest.mark.tooling
def test_dev_generate_followup_threads_mode_and_project_id_to_package(tmp_path: Path):
    """Follow-up mode must stay consistent across input.json and
    generation-package.json.

    Backoffice Playground and the CLI expose --mode followup + --project-id.
    The bug found by Scout was that Phase 1 wrote input.json as followup while
    Phase 2 still hardcoded engineMode=init and projectId=None. This locks the
    contract at the artifact boundary instead of only checking CLI output.
    """
    project_id = "stable-project-id"
    rc, runs_dir, output = _run_dev_generate(
        tmp_path,
        "Uppdatera startsidan med tydligare CTA",
        "--mode",
        "followup",
        "--project-id",
        project_id,
    )
    assert rc == 0, output

    run_dir = _only_run_dir(runs_dir)
    input_payload = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    package = json.loads(
        (run_dir / "generation-package.json").read_text(encoding="utf-8")
    )

    assert input_payload["mode"] == "followup"
    assert input_payload["projectId"] == project_id
    assert package["engineMode"] == "followup"
    assert package["projectId"] == project_id


@pytest.mark.tooling
def test_dev_generate_placeholder_uses_canonical_field_names(tmp_path: Path):
    """B17 regression: build placeholder must read scaffoldId/variantId/starterId
    from the Generation Package, not the legacy 'scaffold'/'scaffoldVariant' keys
    that used to live there before ADR 0013 schema-locked the artefact contract.
    """
    rc, runs_dir, output = _run_dev_generate(
        tmp_path, "Skapa hemsida för elektriker i Malmö"
    )
    assert rc == 0, output

    run_dir = _only_run_dir(runs_dir)
    placeholder = (run_dir / "generated-files" / "app.tsx").read_text(encoding="utf-8")

    assert "scaffold: None" not in placeholder, (
        "B17 regressed: placeholder is reading the legacy 'scaffold' key "
        "and rendering None instead of the canonical scaffoldId."
    )
    assert "variant:  None" not in placeholder, (
        "B17 regressed: placeholder is reading the legacy 'scaffoldVariant' key "
        "and rendering None instead of the canonical variantId."
    )
    pkg = json.loads((run_dir / "generation-package.json").read_text(encoding="utf-8"))
    assert pkg["scaffoldId"] in placeholder
    assert pkg["variantId"] in placeholder
    assert pkg["starterId"] in placeholder


@pytest.mark.tooling
def test_dev_generate_language_detection(tmp_path: Path):
    rc, runs_dir, _ = _run_dev_generate(
        tmp_path, "Skapa hemsida för en elektriker i Malmö", "--phase", "brief"
    )
    assert rc == 0
    run_dir = _only_run_dir(runs_dir)
    brief = json.loads((run_dir / "site-brief.json").read_text(encoding="utf-8"))
    assert brief["language"] == "sv"

    rc2, runs_dir2, _ = _run_dev_generate(
        tmp_path / "english", "Build a website for a clinic", "--phase", "brief"
    )
    assert rc2 == 0
    run_dir2 = _only_run_dir(runs_dir2)
    brief2 = json.loads((run_dir2 / "site-brief.json").read_text(encoding="utf-8"))
    assert brief2["language"] == "en"
