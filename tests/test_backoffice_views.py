"""Smoke tests for backoffice view modules.

We can't run Streamlit's render loop in pytest, but we can:
- Import each view module and verify it exposes a VIEWS dict.
- Verify each entry is callable.
- Verify mermaid builders produce valid-looking output from real policies.
- Verify safe_load_policy handles broken JSON without raising.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.tooling

VIEW_MODULES = [
    "backoffice.views.control_room",
    "backoffice.views.status",
    "backoffice.views.governance",
    "backoffice.views.identity",
    "backoffice.views.llm_engine",
    "backoffice.views.building_blocks",
    "backoffice.views.engine_runs",
    "backoffice.views.playground",
    "backoffice.views.evals",
    "backoffice.views.maintenance",
]


@pytest.mark.tooling
@pytest.mark.parametrize("module_name", VIEW_MODULES)
def test_view_module_exposes_views_dict(module_name: str):
    import importlib

    module = importlib.import_module(module_name)
    assert hasattr(module, "VIEWS"), f"{module_name} missing VIEWS dict"
    assert isinstance(module.VIEWS, dict), f"{module_name}.VIEWS is not a dict"
    assert module.VIEWS, f"{module_name}.VIEWS is empty"
    for name, fn in module.VIEWS.items():
        assert callable(fn), f"{module_name}.VIEWS[{name!r}] is not callable"


@pytest.mark.tooling
def test_safe_load_policy_returns_data_for_existing(repo_root: Path):
    from backoffice import loaders

    data, err = loaders.safe_load_policy("naming-dictionary.v1.json")
    assert err is None
    assert data is not None
    assert data["policyId"].startswith("naming-dictionary.")


@pytest.mark.tooling
def test_safe_load_policy_returns_error_for_missing():
    from backoffice import loaders

    data, err = loaders.safe_load_policy("does-not-exist.v1.json")
    assert data is None
    assert err is not None
    assert "saknas" in err.lower()


@pytest.mark.tooling
def test_safe_load_policy_handles_broken_json(tmp_path: Path, monkeypatch):
    from backoffice import loaders

    fake_dir = tmp_path / "policies"
    fake_dir.mkdir()
    bad = fake_dir / "broken.v1.json"
    bad.write_text("{ not valid json", encoding="utf-8")

    monkeypatch.setattr(loaders, "POLICIES_DIR", fake_dir)
    loaders.load_json.clear()
    loaders.read_text.clear()
    data, err = loaders.safe_load_policy("broken.v1.json")
    assert data is None
    assert err is not None


@pytest.mark.tooling
def test_build_engine_mindmap_produces_mermaid(policies):
    from backoffice.mermaid import build_engine_mindmap

    diagram = build_engine_mindmap(
        policies["llm-flow-concepts.v1.json"],
        policies["llm-models.v1.json"],
        policies["engine-run.v1.json"],
    )
    assert diagram.startswith("flowchart")
    assert "subgraph" in diagram
    assert "briefModel" in diagram
    assert "codegenModel" in diagram
    # Each phase block should be present.
    for block in policies["llm-flow-concepts.v1.json"]["phaseBlocks"]:
        assert block["id"] in diagram


@pytest.mark.tooling
def test_build_init_flow_diagram(policies):
    from backoffice.mermaid import build_init_flow_diagram

    diagram = build_init_flow_diagram(
        policies["llm-flow-concepts.v1.json"],
        policies["project-dna.v1.json"],
    )
    assert diagram.startswith("flowchart")
    assert "Project DNA" in diagram or "dna" in diagram.lower()
    assert "Raw Prompt" in diagram


@pytest.mark.tooling
def test_build_followup_flow_diagram(policies):
    from backoffice.mermaid import build_followup_flow_diagram

    diagram = build_followup_flow_diagram(policies["project-dna.v1.json"])
    assert diagram.startswith("flowchart")
    assert "Load Project DNA" in diagram
    assert "Classify FollowUp Intent" in diagram
    # All seven intents present (snake_case in node ids).
    for intent in policies["project-dna.v1.json"]["followUpIntents"]:
        assert intent["id"].replace("-", "_") in diagram


@pytest.mark.tooling
def test_paths_module_exposes_runs_and_data():
    from backoffice import paths

    assert paths.RUNS_DIR.parent == paths.DATA_DIR
    assert paths.DATA_DIR.parent == paths.REPO_ROOT


@pytest.mark.tooling
def test_status_views_include_golden_path():
    """ADR 0039: a read-only Golden Path status view lives in the Status block."""
    from backoffice.views import status

    assert "Golden Path" in status.VIEWS
    assert callable(status.VIEWS["Golden Path"])


@pytest.mark.tooling
def test_status_views_include_idag_landing():
    """PR2: a read-only Idag landing view is registered first in the Status block."""
    from backoffice.views import status

    assert "Idag" in status.VIEWS
    assert callable(status.VIEWS["Idag"])
    # Idag is the first (top) view in the section.
    assert next(iter(status.VIEWS)) == "Idag"


@pytest.mark.tooling
def test_latest_run_artifacts_none_when_no_runs(tmp_path: Path, monkeypatch):
    """No runs on disk -> (None, None, None) so Idag renders an info state."""
    from backoffice import loaders
    from backoffice.views import status

    monkeypatch.setattr(loaders, "RUNS_DIR", tmp_path / "runs", raising=False)
    # list_run_ids reads paths.RUNS_DIR lazily; point it at an empty dir.
    monkeypatch.setattr(status, "RUNS_DIR", tmp_path / "runs", raising=False)
    monkeypatch.setattr(loaders, "list_run_ids", lambda: [])
    run_id, build_result, quality_result = status.latest_run_artifacts()
    assert run_id is None
    assert build_result is None
    assert quality_result is None


@pytest.mark.tooling
def test_latest_run_artifacts_reads_build_and_quality(tmp_path: Path, monkeypatch):
    import json as _json

    from backoffice import loaders
    from backoffice.views import status

    run_dir = tmp_path / "20260609T000000Z-abc-electrician"
    run_dir.mkdir()
    (run_dir / "build-result.json").write_text(
        _json.dumps({"status": "ok", "siteId": "electrician", "version": 1}),
        encoding="utf-8",
    )
    (run_dir / "quality-result.json").write_text(
        _json.dumps({"status": "ok", "checks": [{"name": "typecheck", "status": "ok"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(status, "RUNS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(loaders, "list_run_ids", lambda: [run_dir.name])

    run_id, build_result, quality_result = status.latest_run_artifacts()
    assert run_id == run_dir.name
    assert build_result["status"] == "ok"
    assert build_result["siteId"] == "electrician"
    assert quality_result["checks"][0]["name"] == "typecheck"


@pytest.mark.tooling
def test_latest_run_artifacts_handles_broken_json(tmp_path: Path, monkeypatch):
    from backoffice import loaders
    from backoffice.views import status

    run_dir = tmp_path / "20260609T000000Z-broken"
    run_dir.mkdir()
    (run_dir / "build-result.json").write_text("{ not valid", encoding="utf-8")
    monkeypatch.setattr(status, "RUNS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(loaders, "list_run_ids", lambda: [run_dir.name])

    run_id, build_result, quality_result = status.latest_run_artifacts()
    assert run_id == run_dir.name
    assert build_result is None  # broken JSON skipped, not raised
    assert quality_result is None


@pytest.mark.tooling
def test_latest_golden_path_summary_none_when_empty(tmp_path: Path):
    """No summary on disk -> (None, None), so the view renders an info state."""
    from backoffice.views.status import latest_golden_path_summary

    missing = tmp_path / "does-not-exist"
    data, path = latest_golden_path_summary(missing)
    assert data is None
    assert path is None

    empty = tmp_path / "summaries"
    empty.mkdir()
    data, path = latest_golden_path_summary(empty)
    assert data is None
    assert path is None


@pytest.mark.tooling
def test_latest_golden_path_summary_picks_newest(tmp_path: Path):
    import json
    import os

    from backoffice.views.status import latest_golden_path_summary

    summaries = tmp_path / "summaries"
    summaries.mkdir()
    old = summaries / "eval-old.json"
    new = summaries / "eval-new.json"
    old.write_text(json.dumps({"evalId": "old", "totalScore": 5}), encoding="utf-8")
    new.write_text(json.dumps({"evalId": "new", "totalScore": 8}), encoding="utf-8")
    # Force a deterministic mtime ordering (old older than new).
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))

    data, path = latest_golden_path_summary(summaries)
    assert data is not None
    assert data["evalId"] == "new"
    assert path == new


@pytest.mark.tooling
def test_latest_golden_path_summary_skips_broken_json(tmp_path: Path):
    import json
    import os

    from backoffice.views.status import latest_golden_path_summary

    summaries = tmp_path / "summaries"
    summaries.mkdir()
    broken = summaries / "eval-broken.json"
    good = summaries / "eval-good.json"
    broken.write_text("{ not valid json", encoding="utf-8")
    good.write_text(json.dumps({"evalId": "good"}), encoding="utf-8")
    # Make the broken file *newer* so the helper must skip it to find the good one.
    os.utime(good, (1_000_000, 1_000_000))
    os.utime(broken, (2_000_000, 2_000_000))

    data, path = latest_golden_path_summary(summaries)
    assert data is not None
    assert data["evalId"] == "good"
    assert path == good


@pytest.mark.tooling
def test_latest_golden_path_summary_reads_legacy_dir(tmp_path: Path):
    import json

    from backoffice.views.status import latest_golden_path_summary

    summaries = tmp_path / "summaries"
    legacy = tmp_path / "legacy"
    summaries.mkdir()
    legacy.mkdir()
    (legacy / "eval-legacy.json").write_text(
        json.dumps({"evalId": "legacy"}), encoding="utf-8"
    )

    data, path = latest_golden_path_summary(summaries, legacy)
    assert data is not None
    assert data["evalId"] == "legacy"


def _streamlit_floor_from_requirements(repo_root: Path) -> tuple[int, int]:
    """Parse the declared ``streamlit>=X.Y`` floor from requirements.txt."""
    import re

    text = (repo_root / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"^streamlit>=(\d+)\.(\d+)", text, flags=re.MULTILINE)
    assert match is not None, "requirements.txt must declare a streamlit floor"
    return int(match.group(1)), int(match.group(2))


@pytest.mark.tooling
def test_streamlit_floor_supports_width_stretch_api(repo_root: Path):
    """Backoffice uses width="stretch" (st.dataframe/st.button/form_submit_button).

    That API requires Streamlit >= 1.49 (dataframe width landed in 1.49,
    buttons in 1.48), and ``use_container_width`` was removed after
    2025-12-31, so the declared floor must guarantee the new API. This locks
    the Codex 2026-06-01 compatibility fix so a later downgrade of the floor
    re-introduces the deprecation/removal break.
    """
    assert _streamlit_floor_from_requirements(repo_root) >= (1, 49)


@pytest.mark.tooling
def test_installed_streamlit_matches_declared_floor(repo_root: Path):
    import streamlit

    parts = streamlit.__version__.split(".")
    installed = (int(parts[0]), int(parts[1]))
    assert installed >= _streamlit_floor_from_requirements(repo_root)


def _streamlit_floor_from_pyproject(repo_root: Path) -> tuple[int, int]:
    """Parse the declared ``streamlit>=X.Y`` floor from pyproject.toml."""
    import re

    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'"streamlit>=(\d+)\.(\d+)"', text)
    assert match is not None, "pyproject.toml must declare a streamlit floor"
    return int(match.group(1)), int(match.group(2))


@pytest.mark.tooling
def test_pyproject_streamlit_floor_matches_requirements(repo_root: Path):
    """`pip install .` reads the floor from pyproject.toml, while
    `pip install -r requirements.txt` reads requirements.txt. If they drift,
    a pyproject-based install can resolve Streamlit < 1.49 and crash on the
    width="stretch" API. Lock both to the same >= 1.49 floor (Codex
    2026-06-01 parity fix)."""
    pyproject_floor = _streamlit_floor_from_pyproject(repo_root)
    assert pyproject_floor >= (1, 49)
    assert pyproject_floor == _streamlit_floor_from_requirements(repo_root)
