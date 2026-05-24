"""Tests for Backoffice Discovery Control helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from backoffice import asset_graph, discovery_control, impact


def _policy() -> dict[str, Any]:
    return discovery_control.load_discovery_policy()


def _category(payload: dict[str, Any], category_id: str = "business") -> dict[str, Any]:
    for category in payload["categories"]:
        if category["id"] == category_id:
            return category
    raise AssertionError(f"Missing category {category_id!r}")


def test_asset_graph_shows_discovery_category_to_scaffold_edges() -> None:
    graph = asset_graph.build_graph()
    nodes = {(node["type"], node["id"]) for node in graph["nodes"]}
    edges = {(edge["from"], edge["to"], edge["relation"]) for edge in graph["edges"]}

    assert ("discovery-category", "business") in nodes
    assert (
        "discovery-category:business",
        "scaffold:local-service-business",
        "target-scaffold",
    ) in edges
    assert (
        "discovery-category:business",
        "capability:contact-form",
        "requests",
    ) in edges
    assert (
        "scaffold:local-service-business",
        "starter:marketing-base",
        "expected-starter",
    ) in edges


def test_discovery_impact_says_changes_affect_future_init_runs() -> None:
    graph = asset_graph.build_graph()

    result = impact.impact_for_node("discovery-category", "business", graph=graph)

    assert result["found"] is True
    assert result["riskLevel"] == "high"
    assert "future init-runs" in result["runtimeEffect"]
    assert "Existing Project Inputs" in result["runtimeEffect"]


def test_discovery_doctor_warns_on_invalid_scaffold() -> None:
    payload = copy.deepcopy(_policy())
    category = _category(payload)
    category["supportStatus"] = "active"
    category["targetScaffoldId"] = "not-a-scaffold"
    category["activeScaffoldId"] = "not-a-scaffold"

    findings = discovery_control.discovery_doctor_findings(payload)
    ids = {finding["id"] for finding in findings}

    assert "discovery-target-scaffold:business" in ids
    assert "discovery-selected-scaffold:business" in ids


def test_discovery_doctor_treats_fallback_target_without_runtime_as_warning() -> None:
    payload = copy.deepcopy(_policy())
    category = _category(payload)
    category["supportStatus"] = "fallback"
    # ``portfolio-creator`` is enabled in scaffold-contract.v1.json but has
    # not yet been wired into SCAFFOLD_TO_STARTER in plan.py; it is the
    # canonical example of a "registered but not runtime" target. The
    # previous example, ``restaurant-hospitality``, became runtime in PR #68
    # follow-up after the planner starter-mapping was wired alongside the
    # scaffold landing, so it no longer triggers this warning path.
    category["targetScaffoldId"] = "portfolio-creator"
    category.pop("activeScaffoldId", None)
    category["fallbackScaffoldId"] = "local-service-business"
    category["defaultVariantId"] = "nordic-trust"
    category["expectedStarterId"] = "marketing-base"

    findings = discovery_control.discovery_doctor_findings(payload)
    by_id = {finding["id"]: finding for finding in findings}

    assert by_id["discovery-target-runtime:business"]["level"] == "warning"
    assert "discovery-selected-runtime:business" not in by_id
    assert "discovery-starter-mapping:business" not in by_id


def test_discovery_doctor_warns_on_invalid_variant() -> None:
    payload = copy.deepcopy(_policy())
    category = _category(payload)
    category["defaultVariantId"] = "not-a-variant"

    findings = discovery_control.discovery_doctor_findings(payload)
    by_id = {finding["id"]: finding for finding in findings}

    assert by_id["discovery-default-variant:business"]["level"] == "error"
    assert "not-a-variant" in by_id["discovery-default-variant:business"]["details"]


def test_discovery_doctor_warns_on_starter_mismatch() -> None:
    payload = copy.deepcopy(_policy())
    category = _category(payload)
    category["expectedStarterId"] = "commerce-base"

    findings = discovery_control.discovery_doctor_findings(payload)
    by_id = {finding["id"]: finding for finding in findings}

    assert by_id["discovery-starter-mapping:business"]["level"] == "error"
    assert "marketing-base" in by_id["discovery-starter-mapping:business"]["details"]


def test_discovery_doctor_warns_on_missing_capability_and_candidate_dossier() -> None:
    payload = copy.deepcopy(_policy())
    category = _category(payload)
    category["requestedCapabilities"] = ["not-a-capability"]
    category["candidateDossiers"] = ["not-a-dossier"]

    findings = discovery_control.discovery_doctor_findings(payload)
    ids = {finding["id"] for finding in findings}

    assert "discovery-capability:business:not-a-capability" in ids
    assert "discovery-candidate-dossier:business:not-a-dossier" in ids


def test_valid_taxonomy_has_no_false_critical_discovery_warnings() -> None:
    findings = discovery_control.discovery_doctor_findings()
    critical = [finding for finding in findings if finding["level"] == "error"]

    assert critical == []


def test_discovery_dry_run_returns_decision_and_field_sources() -> None:
    result = discovery_control.run_discovery_dry_run("ecommerce")

    assert result["categoryId"] == "ecommerce"
    assert result["decision"]["selectedScaffoldId"] == "ecommerce-lite"
    assert result["decision"]["selectedVariantId"] == "clean-store"
    assert result["fieldSources"]["scaffoldId"] == "taxonomy"
    assert "fallbackWarnings" in result


def test_discovery_save_dry_run_does_not_write_without_operator_action(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "discovery-taxonomy.v1.json"
    original = _policy()
    policy_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    proposed, _findings = discovery_control.save_category_update(
        "business",
        {"labelSv": "Ny label"},
        policy_path=policy_path,
        write=False,
    )
    on_disk = json.loads(policy_path.read_text(encoding="utf-8"))

    assert _category(proposed)["labelSv"] == "Ny label"
    assert _category(on_disk)["labelSv"] == _category(original)["labelSv"]


def test_discovery_save_write_true_updates_tmp_policy(tmp_path: Path) -> None:
    policy_path = tmp_path / "discovery-taxonomy.v1.json"
    original = _policy()
    policy_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    discovery_control.save_category_update(
        "business",
        {"labelSv": "Ny sparad label"},
        policy_path=policy_path,
        write=True,
    )
    on_disk = json.loads(policy_path.read_text(encoding="utf-8"))

    assert _category(on_disk)["labelSv"] == "Ny sparad label"


def test_discovery_invalid_save_leaves_tmp_policy_unchanged(tmp_path: Path) -> None:
    policy_path = tmp_path / "discovery-taxonomy.v1.json"
    original = _policy()
    policy_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="not-a-scaffold"):
        discovery_control.save_category_update(
            "business",
            {"targetScaffoldId": "not-a-scaffold"},
            policy_path=policy_path,
            write=True,
        )
    on_disk = json.loads(policy_path.read_text(encoding="utf-8"))

    assert on_disk == original


def test_discovery_edit_validation_accepts_valid_change() -> None:
    payload = copy.deepcopy(_policy())

    proposed, findings = discovery_control.proposed_policy_update(
        "business",
        {"labelSv": "Företag / Tjänster test"},
        policy=payload,
    )

    assert _category(proposed)["labelSv"] == "Företag / Tjänster test"
    assert not [finding for finding in findings if finding["level"] == "error"]


def test_discovery_edit_validation_syncs_expected_starter_for_scaffold_change() -> None:
    payload = copy.deepcopy(_policy())

    proposed, findings = discovery_control.proposed_policy_update(
        "business",
        {
            "supportStatus": "active",
            "targetScaffoldId": "ecommerce-lite",
            "activeScaffoldId": "ecommerce-lite",
            "defaultVariantId": "clean-store",
            "requestedCapabilities": ["payments", "contact-form"],
        },
        policy=payload,
    )
    category = _category(proposed)

    assert category["expectedStarterId"] == "commerce-base"
    assert not [finding for finding in findings if finding["level"] == "error"]


def test_category_mapping_rows_surface_real_doctor_warnings() -> None:
    rows = discovery_control.category_mapping_rows()
    by_id = {row["categoryId"]: row for row in rows}

    # ``portfolio`` is the canonical "planned, target not runtime" category
    # since PR #68 follow-up wired ``restaurant-hospitality`` into
    # SCAFFOLD_TO_STARTER (planner mapping) — the restaurant category is
    # now runtime-resolved for the planner even though
    # ``write_pages`` still lacks ``menu``/``booking`` renderers (see
    # docs/scaffold-runtime-extension-needed.md). When a future PR wires
    # ``portfolio-creator`` into SCAFFOLD_TO_STARTER, swap to another
    # genuinely-planned category (``event``, ``nonprofit``, …) here.
    portfolio = by_id["portfolio"]
    assert portfolio["mappingState"] == "planned-fallback"
    assert portfolio["operatorReviewRequired"] == "ja"
    assert "discovery-target-runtime" in portfolio["fallbackWarnings"]


def test_discovery_edit_validation_rejects_required_dossier_promotion() -> None:
    with pytest.raises(ValueError, match="selectedDossiers"):
        discovery_control.proposed_policy_update(
            "business",
            {"selectedDossiers": {"required": ["interactive-game-loop"]}},
            policy=copy.deepcopy(_policy()),
        )
