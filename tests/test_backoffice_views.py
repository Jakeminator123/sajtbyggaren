"""Smoke tests for backoffice view modules.

We can't run Streamlit's render loop in pytest, but we can:
- Import each view module and verify it exposes a VIEWS dict.
- Verify each entry is callable.
- Verify mermaid builders produce valid-looking output from real policies.
- Verify safe_load_policy handles broken JSON without raising.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


VIEW_MODULES = [
    "backoffice.views.status",
    "backoffice.views.governance",
    "backoffice.views.llm_engine",
    "backoffice.views.building_blocks",
    "backoffice.views.engine_runs",
    "backoffice.views.playground",
    "backoffice.views.evals",
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
