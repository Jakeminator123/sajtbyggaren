"""Tests for Backoffice control-plane helpers."""

from __future__ import annotations

import inspect
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
    # Scaffold→Dossier edges must target the same {class}-dossier:{id} key that
    # the Dossier node is registered with — otherwise the Backoffice impact
    # view cannot follow the relation. interactive-game-loop is a soft Dossier.
    assert ("soft-dossier", "interactive-game-loop") in nodes
    assert (
        "scaffold:local-service-business",
        "soft-dossier:interactive-game-loop",
        "conditional",
    ) in edges
    assert (
        "scaffold:ecommerce-lite",
        "soft-dossier:interactive-game-loop",
        "conditional",
    ) in edges
    assert not any("{'id':" in edge["to"] for edge in graph["edges"])


def test_compatible_dossier_edges_match_dossier_node_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every Scaffold→Dossier edge must point at an existing graph node key.

    Regression lock for the post-PR-#32 review finding where edges were built
    as ``dossier:{id}`` while nodes were registered as
    ``{class}-dossier:{id}``, leaving the impact view blind to the relation.
    """
    scaffolds_dir = tmp_path / "scaffolds"
    dossiers_dir = tmp_path / "dossiers"
    scaffold_dir = scaffolds_dir / "demo"
    scaffold_dir.mkdir(parents=True)
    for filename in asset_graph.scaffold_required_files():
        payload: dict[str, Any] = {}
        if filename == "scaffold.json":
            payload = {"id": "demo", "label": "Demo Scaffold"}
        if filename == "compatible-dossiers.json":
            payload = {
                "required": [{"id": "soft-known"}],
                "recommended": ["hard-known"],
                "conditional": [{"id": "missing-from-registry"}],
            }
        (scaffold_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    for dossier_class, dossier_id in (("soft", "soft-known"), ("hard", "hard-known")):
        manifest = dossiers_dir / dossier_class / dossier_id / "manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"id": dossier_id, "class": dossier_class}),
            encoding="utf-8",
        )

    monkeypatch.setattr(asset_graph, "SCAFFOLDS_DIR", scaffolds_dir)
    monkeypatch.setattr(asset_graph, "DOSSIERS_DIR", dossiers_dir)

    graph = asset_graph.build_graph()
    node_keys = {f"{node['type']}:{node['id']}" for node in graph["nodes"]}
    relevant = [
        edge
        for edge in graph["edges"]
        if edge["from"] == "scaffold:demo"
        and (
            edge["to"].endswith(":soft-known")
            or edge["to"].endswith(":hard-known")
            or edge["to"].endswith(":missing-from-registry")
        )
    ]
    by_target = {edge["to"]: edge for edge in relevant}

    # Registered dossiers resolve to the {class}-dossier:{id} node key so the
    # impact view can connect Scaffold to Dossier.
    assert "soft-dossier:soft-known" in by_target
    assert "soft-dossier:soft-known" in node_keys
    assert "hard-dossier:hard-known" in by_target
    assert "hard-dossier:hard-known" in node_keys

    # Unregistered dossier ids fall back to the unqualified "dossier:" prefix
    # so run_health_checks can flag them as an "okänd Dossier" finding instead
    # of silently dropping the relation.
    assert "dossier:missing-from-registry" in by_target
    assert "dossier:missing-from-registry" not in node_keys


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


def test_doctor_warns_on_incomplete_and_placeholder_scaffolds_not_implemented(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Doctor must warn on Scaffolds that are NOT fully implemented.

    Regression lock for the post-PR-#32 review finding where the warning fired
    on ``status == "implemented"`` (i.e. the happy path) and never on
    ``"incomplete"``/``"placeholder"`` — guaranteeing empty-details false
    positives on healthy scaffolds and silently missing real coverage gaps.
    """
    scaffolds_dir = tmp_path / "scaffolds"
    required_files = asset_graph.scaffold_required_files()

    # Implemented Scaffold: every required file present, none a placeholder.
    healthy = scaffolds_dir / "healthy"
    healthy.mkdir(parents=True)
    for filename in required_files:
        (healthy / filename).write_text(
            json.dumps({"id": "healthy"}) if filename.endswith(".json") else "ok",
            encoding="utf-8",
        )

    # Incomplete Scaffold: required file missing.
    incomplete = scaffolds_dir / "incomplete"
    incomplete.mkdir()
    for filename in required_files[:-1]:
        (incomplete / filename).write_text(
            json.dumps({"id": "incomplete"}), encoding="utf-8"
        )

    # Placeholder Scaffold: every file present but at least one is a builder
    # placeholder (carries the _status sentinel).
    placeholder = scaffolds_dir / "placeholder"
    placeholder.mkdir()
    for filename in required_files:
        (placeholder / filename).write_text(
            json.dumps({"_status": asset_graph.PLACEHOLDER_MARKER}),
            encoding="utf-8",
        )

    monkeypatch.setattr(asset_graph, "SCAFFOLDS_DIR", scaffolds_dir)
    monkeypatch.setattr(asset_graph, "DOSSIERS_DIR", tmp_path / "no-dossiers")

    findings = asset_graph.run_health_checks()
    warning_ids = {
        finding["id"] for finding in findings if finding.get("level") == "warning"
    }

    # The two unhealthy Scaffolds must surface a warning.
    assert "scaffold-files:incomplete" in warning_ids
    assert "scaffold-files:placeholder" in warning_ids
    # The healthy Scaffold must NOT trigger a Doctor warning.
    assert "scaffold-files:healthy" not in warning_ids

    # And the details string must explain why for the unhealthy ones, so the
    # operator can read the finding without cross-referencing source.
    by_id = {finding["id"]: finding for finding in findings}
    assert "saknar" in by_id["scaffold-files:incomplete"]["details"]
    assert "platshållare" in by_id["scaffold-files:placeholder"]["details"]


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


def _variant_payload(variant_id: str) -> dict[str, Any]:
    return {
        "id": variant_id,
        "enabled": False,
        "label": "Test Variant",
        "description": "A focused test Variant.",
        "tokens": {
            "color": {
                "background": "#ffffff",
                "foreground": "#111111",
                "muted": "#666666",
                "border": "#dddddd",
                "primary": "#123456",
                "primaryForeground": "#ffffff",
                "accent": "#abcdef",
                "accentForeground": "#111111",
            },
            "typography": {
                "fontFamilyDisplay": "var(--font-geist-sans)",
                "fontFamilyBody": "var(--font-geist-sans)",
                "fontFamilyMono": "var(--font-geist-mono)",
                "scaleRatio": 1.2,
            },
            "radius": {"sm": "0.25rem", "md": "0.5rem", "lg": "0.75rem"},
            "spacing": {"section": "5rem", "container": "min(72rem, 92vw)"},
            "motion": {"level": "subtle"},
        },
        "tone": {"vibe": ["calm", "credible"]},
    }


def test_variant_diff_rows_marks_changed_fields() -> None:
    canonical = _variant_payload("base")
    candidate = _variant_payload("warm")
    candidate["tokens"]["color"]["primary"] = "#654321"

    rows = asset_graph.variant_diff_rows(candidate, canonical)
    by_field = {row["field"]: row for row in rows}

    assert by_field["id"]["changed"] is True
    assert by_field["tokens.color.primary"]["changed"] is True
    assert by_field["tokens.color.background"]["changed"] is False


def test_list_variant_candidates_reports_validation_and_collision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scaffolds_dir = tmp_path / "scaffolds"
    candidates_dir = tmp_path / "variant-candidates"
    variant_dir = scaffolds_dir / "demo" / "variants"
    variant_dir.mkdir(parents=True)
    (variant_dir / "base.json").write_text(
        json.dumps(_variant_payload("base")),
        encoding="utf-8",
    )
    candidate_dir = candidates_dir / "demo"
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "base.json").write_text(
        json.dumps(_variant_payload("base")),
        encoding="utf-8",
    )
    (candidate_dir / "broken.json").write_text("{", encoding="utf-8")

    monkeypatch.setattr(asset_graph, "SCAFFOLDS_DIR", scaffolds_dir)
    monkeypatch.setattr(asset_graph, "VARIANT_CANDIDATES_DIR", candidates_dir)

    rows = asset_graph.list_variant_candidates()
    by_candidate = {row["candidate"]: row for row in rows}

    assert by_candidate["base"]["status"] == "valid"
    assert by_candidate["base"]["collidesWithCanonical"] is True
    assert by_candidate["broken"]["status"] == "invalid"


def test_asset_graph_lists_dossier_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    candidates_dir = tmp_path / "dossier-candidates"
    manifest = candidates_dir / "soft" / "faq-accordion" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"id": "faq-accordion", "enabled": False, "capability": "faq-section"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(asset_graph, "DOSSIER_CANDIDATES_DIR", candidates_dir)

    graph = asset_graph.build_graph()

    assert ("dossier-candidate", "soft/faq-accordion") in {
        (node["type"], node["id"]) for node in graph["nodes"]
    }


def test_asset_graph_starter_rows_match_runtime_mapping() -> None:
    from packages.generation.planning.plan import SCAFFOLD_TO_STARTER

    starter_rows = asset_graph.asset_graph_starter_rows()
    scaffold_rows = asset_graph.asset_graph_scaffold_rows()
    by_starter = {row["starterId"]: row for row in starter_rows}
    by_scaffold = {row["scaffoldId"]: row for row in scaffold_rows}

    expected_by_starter: dict[str, set[str]] = {}
    for scaffold_id, starter_id in SCAFFOLD_TO_STARTER.items():
        expected_by_starter.setdefault(starter_id, set()).add(scaffold_id)
        assert by_scaffold[scaffold_id]["runtimeStarterId"] == starter_id

    for starter_id, scaffold_ids in expected_by_starter.items():
        actual = {
            item.strip()
            for item in by_starter[starter_id]["runtimeMappedScaffolds"].split(",")
            if item.strip()
        }
        assert actual == scaffold_ids
        assert by_starter[starter_id]["runtimeMappedScaffoldCount"] == len(scaffold_ids)


def test_asset_graph_runtime_and_available_starter_statuses() -> None:
    rows = asset_graph.asset_graph_starter_rows()
    by_id = {row["starterId"]: row for row in rows}

    for starter_id in ("marketing-base", "commerce-base"):
        assert by_id[starter_id]["status"] == "active-runtime"
        assert by_id[starter_id]["runtimeMappedScaffoldCount"] > 0

    for starter_id in ("portfolio-base", "docs-base"):
        assert by_id[starter_id]["status"] == "available-not-mapped"
        assert by_id[starter_id]["runtimeMappedScaffoldCount"] == 0


def test_asset_graph_category_rows_include_support_and_expected_starter() -> None:
    rows = asset_graph.asset_graph_category_rows()
    by_id = {row["categoryId"]: row for row in rows}

    assert {"supportStatus", "expectedStarterId"} <= set(by_id["business"])
    assert by_id["business"]["supportStatus"] == "active"
    assert by_id["business"]["expectedStarterId"] == "marketing-base"
    assert by_id["ecommerce"]["supportStatus"] == "active"
    assert by_id["ecommerce"]["expectedStarterId"] == "commerce-base"


def test_asset_graph_capability_empty_dossiers_are_gap() -> None:
    rows = asset_graph.asset_graph_capability_rows()
    by_id = {row["capabilityId"]: row for row in rows}

    assert by_id["contact-form"]["status"] == "gap"
    assert by_id["contact-form"]["dossierCount"] == 0
    assert by_id["contact-form"]["gapOrOrphan"] is True


def test_asset_graph_capability_unknown_when_referenced_but_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_load_policy = asset_graph.load_policy
    taxonomy = json.loads(
        json.dumps(original_load_policy("discovery-taxonomy.v1.json"))
    )
    taxonomy["categories"][0]["requestedCapabilities"] = [
        "contact-form",
        "not-a-capability",
    ]

    def fake_load_policy(filename: str) -> dict[str, Any]:
        if filename == "discovery-taxonomy.v1.json":
            return taxonomy
        return original_load_policy(filename)

    monkeypatch.setattr(asset_graph, "load_policy", fake_load_policy)

    rows = asset_graph.asset_graph_capability_rows()
    by_id = {row["capabilityId"]: row for row in rows}

    assert by_id["not-a-capability"]["status"] == "unknown"
    assert by_id["not-a-capability"]["referencedByCategories"] == "business"


def test_asset_graph_scaffold_missing_on_disk_can_be_flagged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scaffolds_dir = tmp_path / "empty-scaffolds"
    scaffolds_dir.mkdir()
    monkeypatch.setattr(asset_graph, "SCAFFOLDS_DIR", scaffolds_dir)

    rows = asset_graph.asset_graph_scaffold_rows()
    by_id = {row["scaffoldId"]: row for row in rows}

    assert by_id["local-service-business"]["status"] == "missing-on-disk"
    assert by_id["local-service-business"]["onDisk"] is False


def test_asset_graph_summary_counts_match_rows() -> None:
    category_rows = asset_graph.asset_graph_category_rows()
    scaffold_rows = asset_graph.asset_graph_scaffold_rows()
    starter_rows = asset_graph.asset_graph_starter_rows()
    capability_rows = asset_graph.asset_graph_capability_rows()
    summary = asset_graph.asset_graph_summary()
    attention_statuses = {"gap", "orphan", "missing-on-disk", "unknown"}

    assert summary["categories"] == len(category_rows)
    assert summary["scaffolds"] == len(scaffold_rows)
    assert summary["starters"] == len(starter_rows)
    assert summary["runtimeMappedStarters"] == sum(
        1 for row in starter_rows if row["runtimeMappedScaffoldCount"] > 0
    )
    assert summary["availableNotMappedStarters"] == sum(
        1 for row in starter_rows if row["status"] == "available-not-mapped"
    )
    assert summary["gapsOrphansMissing"] == sum(
        1
        for row in [*category_rows, *scaffold_rows, *starter_rows, *capability_rows]
        if row["gapOrOrphan"] is True or row["status"] in attention_statuses
    )


def test_asset_graph_summary_counts_category_attention() -> None:
    category_rows = asset_graph.asset_graph_category_rows()
    category_attention = sum(1 for row in category_rows if row["gapOrOrphan"] is True)
    assert category_attention > 0

    summary = asset_graph.asset_graph_summary()

    assert summary["gapsOrphansMissing"] >= category_attention


def test_asset_graph_runtime_mapping_import_error_is_not_silent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import() -> None:
        raise ImportError("planning import failed")

    monkeypatch.setattr(asset_graph, "_runtime_mapping", fail_import)

    with pytest.raises(ImportError, match="planning import failed"):
        asset_graph.asset_graph_scaffold_rows()


def test_asset_graph_view_reports_runtime_mapping_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[str] = []

    monkeypatch.setattr(
        building_blocks.asset_graph,
        "asset_graph_summary",
        lambda: (_ for _ in ()).throw(ImportError("planning import failed")),
    )
    monkeypatch.setattr(building_blocks.st, "error", errors.append)

    building_blocks._render_asset_graph()

    assert errors
    assert "runtime-mappningen" in errors[0]
    assert "planning import failed" in errors[0]


def test_asset_graph_helpers_are_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_write(*_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("Asset Graph helpers must not write files")

    def fail_mkdir(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("Asset Graph helpers must not create directories")

    monkeypatch.setattr(Path, "write_text", fail_write)
    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    assert asset_graph.asset_graph_category_rows()
    assert asset_graph.asset_graph_scaffold_rows()
    assert asset_graph.asset_graph_starter_rows()
    assert asset_graph.asset_graph_capability_rows()
    assert asset_graph.asset_graph_summary()["categories"] > 0


def test_asset_graph_view_is_rendered_before_impact_view() -> None:
    source = inspect.getsource(building_blocks.view_control_plane)

    assert hasattr(building_blocks, "_render_asset_graph")
    assert "Asset Graph: category → scaffold → starter → variant → dossier" in inspect.getsource(
        building_blocks._render_asset_graph
    )
    assert (
        "Denna vy är read-only och visar befintliga källor. Den aktiverar inte"
        in inspect.getsource(building_blocks._render_asset_graph)
    )
    assert source.index("_render_sni_discovery_mapping()") < source.index(
        "_render_asset_graph()"
    )
    assert source.index("_render_asset_graph()") < source.index(
        'st.subheader("Konsekvensvy")'
    )


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


def test_dossier_candidate_ui_helper_writes_only_candidate_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_generate_dossier_candidate(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            candidate_dir=Path("data/dossier-candidates/soft/faq-accordion"),
            manifest={"id": "faq-accordion", "enabled": False},
            instructions="# When to use\n",
            source="deterministic-v1",
            model_used="deterministic",
        )

    monkeypatch.setattr(
        building_blocks,
        "generate_dossier_candidate",
        fake_generate_dossier_candidate,
    )

    result = building_blocks.create_dossier_candidate_from_ui(
        brief="FAQ accordion",
        candidate_id="faq-accordion",
        capability="faq-section",
        use_llm=False,
        force=False,
    )

    assert result.manifest["enabled"] is False
    assert captured["output_dir"] == building_blocks.DOSSIER_CANDIDATES_DIR
    assert "packages/generation/orchestration/dossiers" not in str(captured["output_dir"])


def test_pyrightconfig_adds_scripts_extra_path(repo_root: Path) -> None:
    payload = json.loads((repo_root / "pyrightconfig.json").read_text(encoding="utf-8"))
    environments = payload["executionEnvironments"]

    assert any("scripts" in env.get("extraPaths", []) for env in environments)
