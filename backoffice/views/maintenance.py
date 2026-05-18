"""Maintenance views for cleanup and generation-asset toggles."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import streamlit as st

from backoffice import asset_graph, impact
from backoffice.maintenance import (
    CleanupItem,
    apply_safe_cleanup,
    apply_warning_cleanup,
    format_megabytes,
    list_dossier_toggles,
    list_scaffold_toggles,
    list_starter_toggles,
    list_variant_toggles,
    plan_safe_cleanup,
    plan_warning_cleanup,
    set_collection_entry_enabled,
    set_top_level_enabled,
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
        st.info(
            "Skyddade aktiva runId: "
            + ", ".join(sorted(protected))
            + ". Skyddet är sessionsberoende - en runId hamnar här när "
            "Engine runs- eller Playground-vyn har valt den i nuvarande session."
        )
    else:
        st.caption(
            "Inga aktiva runId i sessionen - rensningen styrs ensam av "
            "auto-prune-reglerna nedan. Öppna en run i Engine runs eller "
            "Playground om du vill skydda just den från denna körning."
        )

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
    st.caption(
        "Skriver `enabled: bool` enligt ADR 0023. Saknat fält behandlas som "
        "aktivt av runtime, men Backoffice skriver alltid explicit värde."
    )
    tabs = st.tabs(["Scaffolds", "Variants", "Dossiers", "Starters"])

    def _render_impact(row_id: str, node_type: str, graph: dict) -> dict:
        result = impact.impact_for_node(node_type, row_id, graph=graph)
        with st.expander("Konsekvens", expanded=False):
            st.caption(result["runtimeEffect"])
            relation_rows = impact.impact_table_rows(result)
            if relation_rows:
                st.dataframe(relation_rows, use_container_width=True, hide_index=True)
            else:
                st.write("Inga direkta relationer hittades.")
        return result

    def _node_type(row, configured_type: str) -> str:
        if configured_type == "dossier":
            return f"{row.group}-dossier"
        return configured_type

    def _render_rows(
        rows,
        *,
        node_type: str,
        collection_key: str | None = None,
    ) -> None:
        if not rows:
            st.info("Inga entries hittades.")
            return
        graph = asset_graph.build_graph()
        for row in rows:
            cols = st.columns([2, 1, 4])
            cols[0].markdown(f"**{row.label}**  \n`{row.id}`")
            cols[2].caption(f"`{_relative(row.path)}`")
            if row.note:
                cols[2].write(row.note[:240] + ("..." if len(row.note) > 240 else ""))
            actual_node_type = _node_type(row, node_type)
            impact_result = _render_impact(row.id, actual_node_type, graph)
            value = cols[1].toggle(
                "Aktiv",
                value=row.enabled,
                key=f"toggle-{row.path}-{row.id}",
            )
            if value != row.enabled:
                if actual_node_type in impact.HIGH_IMPACT_TYPES:
                    st.warning(
                        "Detta är en högpåverkande ändring. Granska konsekvensen "
                        "och bekräfta innan Backoffice skriver enabled-värdet."
                    )
                    if not st.button(
                        f"Bekräfta ändring för {row.id}",
                        key=f"confirm-toggle-{row.path}-{row.id}",
                    ):
                        continue
                backup = row.path.read_text(encoding="utf-8")
                try:
                    if collection_key is None:
                        set_top_level_enabled(row.path, value)
                    else:
                        set_collection_entry_enabled(
                            row.path,
                            collection_key=collection_key,
                            item_id=row.id,
                            enabled=value,
                        )
                    from .. import health, loaders

                    result = health.run_governance_validate()
                    if not result.ok:
                        row.path.write_text(backup, encoding="utf-8")
                        st.error(f"Validation failade; rollback genomfört.\n\n{result.output}")
                    else:
                        loaders.load_json.clear()
                        loaders.read_text.clear()
                        st.success(
                            f"{row.id}: enabled={value} "
                            f"(risk: {impact_result['riskLevel']})"
                        )
                except Exception as exc:  # noqa: BLE001
                    row.path.write_text(backup, encoding="utf-8")
                    st.error(f"Kunde inte spara toggle för {row.id}: {exc}")

    with tabs[0]:
        _render_rows(
            list_scaffold_toggles(),
            node_type="scaffold",
            collection_key="primaryScaffoldRegistry",
        )
    with tabs[1]:
        _render_rows(list_variant_toggles(), node_type="variant")
    with tabs[2]:
        _render_rows(list_dossier_toggles(), node_type="dossier")
    with tabs[3]:
        _render_rows(
            list_starter_toggles(),
            node_type="starter",
            collection_key="starters",
        )


VIEWS = {
    "Cleanup - Säker rensning": lambda: safe_render(view_safe_cleanup),
    "Cleanup - Med varning": lambda: safe_render(view_warning_cleanup),
    "Toggle - Aktivera/inaktivera": lambda: safe_render(view_toggle),
}
