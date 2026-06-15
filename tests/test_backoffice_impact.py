"""Tests for Backoffice read-only impact helpers."""

from __future__ import annotations

import pytest

from backoffice import asset_graph, impact

pytestmark = pytest.mark.tooling


def test_impact_for_starter_lists_mapped_scaffold() -> None:
    graph = asset_graph.build_graph()

    result = impact.impact_for_node("starter", "marketing-base", graph=graph)

    assert result["found"] is True
    assert result["riskLevel"] == "high"
    assert result["runtimeEffect"].startswith("Planning fails loud")
    assert any(
        edge["to"] == "scaffold:local-service-business"
        and edge["relation"] == "maps-to"
        for edge in result["outgoing"]
    )
    assert any(
        node["type"] == "scaffold" and node["id"] == "local-service-business"
        for node in result["affectedNodes"]
    )


def test_impact_for_variant_candidate_has_no_runtime_effect() -> None:
    graph = {
        "nodes": [
            {
                "type": "variant-candidate",
                "id": "local-service-business/warm",
                "path": "data/variant-candidates/local-service-business/warm.json",
                "status": "candidate",
                "canonical": False,
                "enabled": False,
                "details": "Warm",
            }
        ],
        "edges": [],
    }

    result = impact.impact_for_node(
        "variant-candidate",
        "local-service-business/warm",
        graph=graph,
    )

    assert result["found"] is True
    assert result["riskLevel"] == "low"
    assert "not part of runtime selection" in result["runtimeEffect"]


def test_impact_table_rows_keeps_edge_details() -> None:
    result = {
        "incoming": [],
        "outgoing": [
            {
                "from": "scaffold:demo",
                "to": "dossier:faq",
                "relation": "conditional",
                "details": "when asked",
            }
        ],
    }

    assert impact.impact_table_rows(result) == [
        {
            "direction": "out",
            "from": "scaffold:demo",
            "to": "dossier:faq",
            "relation": "conditional",
            "details": "when asked",
        }
    ]
