"""Maintenance views for cleanup and generation-asset toggles."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import streamlit as st

from backoffice.maintenance import (
    CleanupItem,
    apply_safe_cleanup,
    apply_warning_cleanup,
    format_megabytes,
    plan_safe_cleanup,
    plan_warning_cleanup,
)
from packages.generation.maintenance import (
    MAX_GENERATED_ENV_VAR,
    MAX_PROMPT_INPUTS_ENV_VAR,
    MAX_RUNS_ENV_VAR,
)

from ..paths import REPO_ROOT
from ._helpers import safe_render


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _render_item_preview(items: list[CleanupItem]) -> None:
    rows = [
        {
            "Typ": item.kind,
            "Path": _relative(item.path),
            "Storlek": format_megabytes(item.size_bytes),
            "Varning": item.warning or "",
        }
        for item in items[:20]
    ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    if len(items) > 20:
        st.caption(f"...resten ({len(items) - 20} till)")


def _protected_run_ids() -> set[str]:
    protected: set[str] = set()
    for key in ("playground_run_id", "engine_run_select", "current_run_id"):
        value = st.session_state.get(key)
        if isinstance(value, str) and value.strip():
            protected.add(value.strip())
    return protected


def _env_caption(names: Iterable[str]) -> str:
    parts = []
    for name in names:
        value = os.environ.get(name)
        parts.append(f"`{name}`={value.strip() if value and value.strip() else 'unset'}")
    return " · ".join(parts)


def view_safe_cleanup() -> None:
    st.title("Cleanup - Säker rensning")
    st.caption(
        "Dry-run som standard. Rensar bara bygg-/cache-artefakter och använder "
        "befintlig auto-prune-logik för runs och genererade previews."
    )
    st.caption(_env_caption([MAX_RUNS_ENV_VAR, MAX_GENERATED_ENV_VAR]))

    protected = _protected_run_ids()
    if protected:
        st.info("Skyddade aktiva runId: " + ", ".join(sorted(protected)))

    plan = plan_safe_cleanup(protected_run_ids=protected)
    st.metric(
        "Dry-run",
        f"{plan.total_count} mappar/filer",
        help="Inget raderas innan du trycker Bekräfta radering.",
    )
    st.write(f"Detta skulle rensa {plan.total_count} mappar/filer ({format_megabytes(plan.total_bytes)}).")
    _render_item_preview(plan.items)

    if not plan.items:
        st.success("Inget säkert cleanup-target hittades.")
        return

    if st.button("Bekräfta radering", type="primary", key="safe-cleanup-apply"):
        result = apply_safe_cleanup(protected_run_ids=protected)
        if result.errors:
            for error in result.errors:
                st.error(error)
        st.success(
            f"Rensade {result.deleted_count} mappar/filer, "
            f"frigjorde {format_megabytes(result.freed_bytes)}."
        )
        if result.skipped_paths:
            with st.expander("Skippade paths"):
                for path in result.skipped_paths:
                    st.write(f"- `{_relative(path)}`")


def view_warning_cleanup() -> None:
    st.title("Cleanup - Med varning")
    st.warning(
        "Detta kan ta bort state som gör att operatören kan fortsätta på en "
        "befintlig sajt, eller kräva ny npm install efteråt."
    )
    st.caption(_env_caption([MAX_PROMPT_INPUTS_ENV_VAR]))

    plan = plan_warning_cleanup()
    st.write(f"Detta skulle rensa {plan.total_count} mappar/filer ({format_megabytes(plan.total_bytes)}).")
    _render_item_preview(plan.items)

    prompt_items = [item for item in plan.items if item.kind == "prompt-input"]
    node_modules_items = [item for item in plan.items if item.kind == "node-modules"]

    include_prompt_inputs = False
    include_node_modules = False
    if prompt_items:
        st.error(
            "`data/prompt-inputs/`-rensning kan ta bort fortsätt-på-sajt-underlag "
            "för gamla siteId:n."
        )
        typed = st.text_input(
            "Skriv RADERA PROMPT INPUTS för att bekräfta prompt-input-rensning",
            key="confirm-prompt-inputs",
        )
        include_prompt_inputs = typed == "RADERA PROMPT INPUTS"
    if node_modules_items:
        st.error("`apps/viewser/node_modules/` kräver npm install efter radering.")
        typed = st.text_input(
            "Skriv RADERA NODE MODULES för att bekräfta node_modules-rensning",
            key="confirm-node-modules",
        )
        include_node_modules = typed == "RADERA NODE MODULES"

    disabled = not (include_prompt_inputs or include_node_modules)
    if st.button(
        "Bekräfta varningsradering",
        type="primary",
        key="warning-cleanup-apply",
        disabled=disabled,
    ):
        result = apply_warning_cleanup(
            include_prompt_inputs=include_prompt_inputs,
            include_node_modules=include_node_modules,
        )
        if result.errors:
            for error in result.errors:
                st.error(error)
        st.success(
            f"Rensade {result.deleted_count} mappar/filer, "
            f"frigjorde {format_megabytes(result.freed_bytes)}."
        )


def view_toggle() -> None:
    st.title("Toggle - Aktivera/inaktivera")
    st.info(
        "Toggle-vyn landar med governance-fälten i ADR 0023. Den kommer visa "
        "Scaffolds, Variants, Dossiers och Starters i separata tabeller."
    )


VIEWS = {
    "Cleanup - Säker rensning": lambda: safe_render(view_safe_cleanup),
    "Cleanup - Med varning": lambda: safe_render(view_warning_cleanup),
    "Toggle - Aktivera/inaktivera": lambda: safe_render(view_toggle),
}
