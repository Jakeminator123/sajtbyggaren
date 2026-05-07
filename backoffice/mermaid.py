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
) -> str:
    """Build a mermaid diagram of the full engine: phase blocks, phases, model roles.

    The diagram is generated from the three policies above, so editing any of
    them updates the diagram automatically next time the cache is cleared.
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
        for phase_id in block["phaseIds"]:
            phase = phases_by_id.get(phase_id)
            if phase is None:
                continue
            label = phase["canonicalName"].replace('"', "'")
            lines.append(f'    {phase_id}["{label}"]')
            if previous_phase is not None:
                lines.append(f"    {previous_phase} --> {phase_id}")
            previous_phase = phase_id
        lines.append("  end")

    # Connect blocks in order.
    for prev_block, next_block in zip(phase_blocks, phase_blocks[1:]):
        prev_last = prev_block["phaseIds"][-1]
        next_first = next_block["phaseIds"][0]
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
    if "init" in modes:
        lines.append('  initMode(["Mode: init"])')
        if phase_blocks:
            lines.append(f'  initMode -.-> {phase_blocks[0]["phaseIds"][0]}')
    if "followup" in modes:
        lines.append('  followupMode(["Mode: followup"])')
        if phase_blocks:
            lines.append(f'  followupMode -.-> {phase_blocks[0]["phaseIds"][0]}')

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
