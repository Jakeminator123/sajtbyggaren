"""Tests for Backoffice control-plane helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backoffice import asset_graph
from backoffice.views import building_blocks


def test_scaffold_is_real_uses_all_required_files(tmp_path: Path) -> None:
    scaffold_dir = tmp_path / "demo"
    scaffold_dir.mkdir()
    for filename in ("scaffold.json", "routes.json", "sections.json"):
        (scaffold_dir / filename).write_text("{}", encoding="utf-8")

    required = [
        "scaffold.json",
        "routes.json",
        "sections.json",
        "quality-contract.json",
    ]

    assert asset_graph.scaffold_is_real(scaffold_dir, required) is False
    state = asset_graph.scaffold_file_state(scaffold_dir, required)
    assert state["status"] == "incomplete"
    assert state["missing"] == ["quality-contract.json"]


def test_dossier_listing_ignores_unregistered_hybrid_class(tmp_path: Path) -> None:
    dossiers_dir = tmp_path / "dossiers"
    (dossiers_dir / "soft" / "one").mkdir(parents=True)
    (dossiers_dir / "hybrid" / "legacy").mkdir(parents=True)
    (dossiers_dir / "hard" / "two").mkdir(parents=True)

    listed = asset_graph.list_dossier_dirs(
        dossiers_dir,
        classes=["soft", "hard"],
    )

    assert [(cls, path.name) for cls, path in listed] == [
        ("soft", "one"),
        ("hard", "two"),
    ]
    stale = asset_graph.list_unregistered_dossier_class_dirs(
        dossiers_dir,
        classes=["soft", "hard"],
    )
    assert [path.name for path in stale] == ["hybrid"]


def test_real_asset_graph_contains_core_edges() -> None:
    graph = asset_graph.build_graph()
    nodes = {(node["type"], node["id"]) for node in graph["nodes"]}
    edges = {(edge["from"], edge["to"], edge["relation"]) for edge in graph["edges"]}

    assert ("scaffold", "local-service-business") in nodes
    assert ("variant", "nordic-trust") in nodes
    assert ("model-role", "variantModel") in nodes
    assert ("starter:marketing-base", "scaffold:local-service-business", "maps-to") in edges
    assert ("scaffold:local-service-business", "variant:nordic-trust", "owns") in edges
    assert (
        "scaffold:local-service-business",
        "dossier:interactive-game-loop",
        "conditional",
    ) in edges
    assert (
        "scaffold:ecommerce-lite",
        "dossier:interactive-game-loop",
        "conditional",
    ) in edges
    assert not any("{'id':" in edge["to"] for edge in graph["edges"])


def test_health_checks_report_malformed_compatible_dossier_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scaffolds_dir = tmp_path / "scaffolds"
    dossiers_dir = tmp_path / "dossiers"
    scaffold_dir = scaffolds_dir / "demo"
    scaffold_dir.mkdir(parents=True)
    for filename in asset_graph.scaffold_required_files():
        payload: dict[str, Any] = {}
        if filename == "scaffold.json":
            payload = {"id": "demo"}
        if filename == "compatible-dossiers.json":
            payload = {
                "required": [{"when": "missing id"}],
                "recommended": ["missing-dossier"],
                "conditional": [{"id": "known-dossier", "when": "explicit ask"}],
            }
        (scaffold_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    manifest = dossiers_dir / "soft" / "known-dossier" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"id": "known-dossier", "class": "soft"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(asset_graph, "SCAFFOLDS_DIR", scaffolds_dir)
    monkeypatch.setattr(asset_graph, "DOSSIERS_DIR", dossiers_dir)

    findings = asset_graph.run_health_checks()
    ids = {finding["id"] for finding in findings}

    assert "compatible-dossier:demo:required:0" in ids
    assert "compatible-dossier:demo:recommended:missing-dossier" in ids
    assert "compatible-dossier:demo:conditional:known-dossier" not in ids


def test_health_checks_report_embedding_index_as_not_implemented() -> None:
    findings = asset_graph.run_health_checks()
    ids = {finding["id"] for finding in findings}

    assert "embedding-index:not-implemented" in ids


def test_compare_variant_to_existing_counts_overlap() -> None:
    candidate = {
        "tokens": {"color": {"background": "#ffffff", "primary": "#111111"}},
        "tone": {"vibe": ["calm", "warm"]},
    }
    existing = [
        {
            "id": "base",
            "tokens": {"color": {"background": "#ffffff", "primary": "#222222"}},
            "tone": {"vibe": ["calm", "premium"]},
        }
    ]

    rows = asset_graph.compare_variant_to_existing(candidate, existing)

    assert rows == [
        {"variant": "base", "sameColorTokens": 1, "sharedVibes": "calm"}
    ]


def test_variant_candidate_ui_helper_writes_only_candidate_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_generate_variant_candidates(**kwargs: Any) -> list[SimpleNamespace]:
        captured.update(kwargs)
        return [
            SimpleNamespace(
                path=Path("data/variant-candidates/local-service-business/warm.json"),
                payload={"id": "warm", "enabled": False},
                source="deterministic-v1",
                model_used="deterministic",
            )
        ]

    monkeypatch.setattr(
        building_blocks,
        "generate_variant_candidates",
        fake_generate_variant_candidates,
    )

    result = building_blocks.create_variant_candidate_from_ui(
        scaffold_id="local-service-business",
        brief="Warm local trust",
        variant_id="warm",
        use_llm=False,
        force=False,
    )

    assert result[0].payload["enabled"] is False
    assert captured["output_dir"] == building_blocks.VARIANT_CANDIDATES_DIR
    assert "packages/generation/orchestration/scaffolds" not in str(captured["output_dir"])
    assert captured["enabled"] is False


def test_pyrightconfig_adds_scripts_extra_path(repo_root: Path) -> None:
    payload = json.loads((repo_root / "pyrightconfig.json").read_text(encoding="utf-8"))
    environments = payload["executionEnvironments"]

    assert any("scripts" in env.get("extraPaths", []) for env in environments)
