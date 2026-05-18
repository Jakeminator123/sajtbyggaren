"""Read-only impact helpers for Backoffice asset operations."""

from __future__ import annotations

from typing import Any

from . import asset_graph

HIGH_IMPACT_TYPES = {"starter", "scaffold"}
MEDIUM_IMPACT_TYPES = {"variant", "soft-dossier", "hard-dossier"}
NO_RUNTIME_TYPES = {"variant-candidate"}


def node_key(node_type: str, node_id: str) -> str:
    """Return the graph key format used by asset graph edges."""
    return f"{node_type}:{node_id}"


def _runtime_effect(node_type: str) -> str:
    if node_type == "starter":
        return (
            "Planning fails loud for mapped Scaffolds if this Starter is disabled. "
            "Generated historical runs are not modified."
        )
    if node_type == "scaffold":
        return (
            "Planning filters this Scaffold out before selection. Pinned Project Inputs "
            "that reference it fail loud."
        )
    if node_type == "variant":
        return (
            "Planning filters this Variant out before selection. Pinned Project Inputs "
            "that reference it fail loud when no enabled matching Variant remains."
        )
    if node_type.endswith("-dossier"):
        return (
            "Capability filtering rejects this Dossier when disabled. Runs that already "
            "selected it are not rewritten."
        )
    if node_type == "variant-candidate":
        return (
            "Candidate files are not part of runtime selection and are safe to review "
            "without affecting generation."
        )
    return "No runtime effect is known for this node type."


def _risk_level(node_type: str, incoming_count: int, outgoing_count: int) -> str:
    if node_type in HIGH_IMPACT_TYPES:
        return "high"
    if incoming_count or outgoing_count or node_type in MEDIUM_IMPACT_TYPES:
        return "medium"
    return "low"


def impact_for_node(
    node_type: str,
    node_id: str,
    *,
    graph: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Return incoming/outgoing relationships and runtime effect for a graph node."""
    actual_graph = graph if graph is not None else asset_graph.build_graph()
    key = node_key(node_type, node_id)
    nodes_by_key = {
        node_key(str(node["type"]), str(node["id"])): node
        for node in actual_graph.get("nodes", [])
    }
    node = nodes_by_key.get(key)
    incoming = [edge for edge in actual_graph.get("edges", []) if edge.get("to") == key]
    outgoing = [edge for edge in actual_graph.get("edges", []) if edge.get("from") == key]

    related_keys = {
        str(edge.get("from"))
        for edge in incoming
        if isinstance(edge.get("from"), str)
    } | {
        str(edge.get("to"))
        for edge in outgoing
        if isinstance(edge.get("to"), str)
    }
    affected_nodes = [
        nodes_by_key[related_key]
        for related_key in sorted(related_keys)
        if related_key in nodes_by_key
    ]
    affected_paths = sorted(
        {
            str(path)
            for path in [node.get("path") if node else None]
            + [related.get("path") for related in affected_nodes]
            if path
        }
    )

    return {
        "nodeKey": key,
        "found": node is not None,
        "node": node
        or {
            "type": node_type,
            "id": node_id,
            "path": "",
            "status": "missing",
            "canonical": None,
            "enabled": None,
            "details": "",
        },
        "incoming": incoming,
        "outgoing": outgoing,
        "affectedNodes": affected_nodes,
        "affectedPaths": affected_paths,
        "riskLevel": _risk_level(node_type, len(incoming), len(outgoing)),
        "runtimeEffect": _runtime_effect(node_type),
    }


def impact_table_rows(impact: dict[str, Any]) -> list[dict[str, str]]:
    """Return compact rows suitable for Streamlit tables."""
    rows: list[dict[str, str]] = []
    for direction, edges in (("in", impact["incoming"]), ("out", impact["outgoing"])):
        for edge in edges:
            rows.append(
                {
                    "direction": direction,
                    "from": str(edge.get("from", "")),
                    "to": str(edge.get("to", "")),
                    "relation": str(edge.get("relation", "")),
                    "details": str(edge.get("details", "")),
                }
            )
    return rows
