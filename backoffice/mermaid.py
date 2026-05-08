"""Mermaid diagram helpers for the backoffice.

Renders mermaid via CDN inside an iframe so we don't need a new pip dep.
Builders generate diagrams dynamically from governance policies so visualisations
never drift from the source of truth.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs"


def render_mermaid(diagram: str, height: int = 600) -> None:
    """Render a mermaid diagram via CDN in a sandboxed iframe."""
    if not diagram or not diagram.strip():
        st.warning("Tomt mermaid-diagram - inget att rendera.")
        return

    safe_diagram = diagram.replace("</", "<\\/")
    html = (
        '<div style="font-family: system-ui, -apple-system, sans-serif;">'
        '<script type="module">'
        f'import mermaid from "{_MERMAID_CDN}";'
        'mermaid.initialize({startOnLoad: true, theme: "neutral", securityLevel: "strict"});'
        '</script>'
        f'<pre class="mermaid">{safe_diagram}</pre>'
        '</div>'
    )
    st.components.v1.html(html, height=height, scrolling=True)


def build_engine_mindmap(
    llm_flow: dict[str, Any],
    llm_models: dict[str, Any],
    engine_run: dict[str, Any],
    project_dna: dict[str, Any] | None = None,
    embedding_policy: dict[str, Any] | None = None,
    fix_registry: dict[str, Any] | None = None,
    preview_runtime: dict[str, Any] | None = None,
) -> str:
    """Build a mermaid diagram of the full engine.

    Includes phase blocks, phases, model roles, Engine Run modes, Project DNA,
    Embedding Domains, Fix Registry and Preview Runtime. Generated from policies
    so editing any of them updates the diagram automatically.
    """
    lines: list[str] = ["flowchart LR"]

    phase_blocks = llm_flow.get("phaseBlocks", [])
    phases_by_id = {p["id"]: p for p in llm_flow.get("phases", [])}

    # Subgraphs per phase block.
    for block in phase_blocks:
        block_id = block["id"]
        block_label = block["label"].replace('"', "'")
        lines.append(f'  subgraph {block_id} ["{block_label}"]')
        previous_phase: str | None = None
        for phase_id in block.get("phaseIds", []):
            phase = phases_by_id.get(phase_id)
            if phase is None:
                continue
            label = phase["canonicalName"].replace('"', "'")
            lines.append(f'    {phase_id}["{label}"]')
            if previous_phase is not None:
                lines.append(f"    {previous_phase} --> {phase_id}")
            previous_phase = phase_id
        if previous_phase is None:
            lines.append(f'    {block_id}_empty["(no phases yet)"]')
        lines.append("  end")

    # Connect blocks in order. Skip blocks with no phaseIds.
    def _last_phase(block: dict) -> str | None:
        ids = block.get("phaseIds") or []
        return ids[-1] if ids else None

    def _first_phase(block: dict) -> str | None:
        ids = block.get("phaseIds") or []
        return ids[0] if ids else None

    from itertools import pairwise

    for prev_block, next_block in pairwise(phase_blocks):
        prev_last = _last_phase(prev_block)
        next_first = _first_phase(next_block)
        if prev_last and next_first:
            lines.append(f"  {prev_last} --> {next_first}")

    # Model role nodes (one per role) with the model name.
    for role in llm_models.get("roles", []):
        role_id = role["id"]
        model_name = role.get("model", "?")
        node_label = f"{role_id}<br/>{model_name}".replace('"', "'")
        lines.append(f'  {role_id}(["{node_label}"])')

    # Heuristic: connect roles to phases that allowToCallLLM=true and match by name.
    role_to_phase = {
        "briefModel": "site_brief",
        "planningModel": "scaffold_resolution",
        "rerankModel": "scaffold_resolution",
        "codegenModel": "codegen",
        "repairModel": "llm_repair",
        "verifierModel": "quality_evaluation",
        "embeddingModel": "scaffold_resolution",
    }
    for role in llm_models.get("roles", []):
        rid = role["id"]
        phase_target = role_to_phase.get(rid)
        if phase_target and phase_target in phases_by_id:
            lines.append(f"  {rid} -.-> {phase_target}")

    # Engine Run mode markers.
    modes = engine_run.get("modes", {})
    first_phase = _first_phase(phase_blocks[0]) if phase_blocks else None
    if "init" in modes and first_phase:
        lines.append('  initMode(["Mode: init<br/>writes Project DNA"])')
        lines.append(f"  initMode -.-> {first_phase}")
    if "followup" in modes and first_phase:
        lines.append('  followupMode(["Mode: followup<br/>reads Project DNA"])')
        lines.append(f"  followupMode -.-> {first_phase}")

    # Project DNA node, connected from init and followup modes.
    if project_dna:
        lines.append('  projectDna(["Project DNA<br/>scaffold/variant/dossiers/themeTokens"])')
        if "init" in modes:
            lines.append("  initMode --> projectDna")
        if "followup" in modes:
            lines.append("  projectDna --> followupMode")

    # Embedding Domains as a cluster pointing into scaffold_resolution.
    if embedding_policy:
        lines.append("  subgraph embeddings [Embedding Domains]")
        for domain in embedding_policy.get("domains", []):
            did = domain["id"].replace("-", "_")
            label = domain["id"].replace('"', "'")
            lines.append(f'    {did}["{label}"]')
        lines.append("  end")
        if "scaffold_resolution" in phases_by_id:
            lines.append("  embeddings -.-> scaffold_resolution")
        if "embeddingModel" in {r["id"] for r in llm_models.get("roles", [])}:
            lines.append("  embeddingModel -.-> embeddings")

    # Fix Registry as a cluster connected to llm_repair / mechanical_autofix.
    if fix_registry:
        lines.append("  subgraph fixes [Fix Registry]")
        lines.append('    mechanicalFixes["Mechanical Fixes"]')
        lines.append('    llmFixes["LLM Fixes"]')
        lines.append("  end")
        if "mechanical_autofix" in phases_by_id:
            lines.append("  mechanicalFixes -.-> mechanical_autofix")
        if "llm_repair" in phases_by_id:
            lines.append("  llmFixes -.-> llm_repair")

    # Preview Runtime + Quality Gate visibility.
    if preview_runtime:
        lines.append('  previewRuntimePolicy(["Preview Runtime<br/>Local/StackBlitz/Fly"])')
        if "preview_runtime" in phases_by_id:
            lines.append("  previewRuntimePolicy -.-> preview_runtime")
        lines.append('  qualityGate(["Quality Gate<br/>typecheck/build/route/preview-smoke"])')
        if "quality_evaluation" in phases_by_id:
            lines.append("  quality_evaluation -.-> qualityGate")

    return "\n".join(lines)


def build_init_flow_diagram(
    llm_flow: dict[str, Any],
    project_dna: dict[str, Any],
) -> str:
    """Init mode diagram: prompt -> phases -> Project DNA created."""
    lines = ["flowchart TD"]
    lines.append("  raw[Raw Prompt]")

    phases_by_id = {p["id"]: p for p in llm_flow.get("phases", [])}
    canonical = llm_flow.get("canonicalFlow", [])
    previous = "raw"
    for phase_id in canonical:
        phase = phases_by_id.get(phase_id)
        if phase is None:
            continue
        label = phase["canonicalName"].replace('"', "'")
        lines.append(f'  {phase_id}["{label}"]')
        lines.append(f"  {previous} --> {phase_id}")
        previous = phase_id

    lines.append('  dna(["Project DNA created"])')
    lines.append(f"  {previous} --> dna")
    return "\n".join(lines)


def build_followup_flow_diagram(project_dna: dict[str, Any]) -> str:
    """Follow-up mode diagram: load DNA -> classify intent -> branch by intent."""
    lines = ["flowchart TD"]
    lines.append("  prompt[Follow-up Prompt]")
    lines.append("  loadDna[Load Project DNA]")
    lines.append("  classify[Classify FollowUp Intent]")
    lines.append("  prompt --> loadDna --> classify")

    intents = project_dna.get("followUpIntents", [])
    for intent in intents:
        intent_id = intent["id"].replace("-", "_")
        label = intent["id"].replace('"', "'")
        lines.append(f'  classify --> {intent_id}["{label}"]')
        if intent["id"] == "redesign":
            lines.append(f"  {intent_id} --> fork[Project Fork]")
        elif intent["id"] == "clarify":
            lines.append(f"  {intent_id} --> ask[Ask user]")
        else:
            lines.append(f"  {intent_id} --> patch[Patch within DNA]")

    return "\n".join(lines)
