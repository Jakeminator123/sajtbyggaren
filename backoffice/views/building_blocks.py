"""Building Blocks-block: Scaffolds, Variants, Dossiers, Reference Templates."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from scripts.dossier_candidate_intake import (
    DossierIntakeError,
    analyze_dossier_source,
)
from scripts.generate_dossier_candidate import (
    DossierGenerationError,
    generate_dossier_candidate,
)
from scripts.generate_variant_candidate import (
    VariantGenerationError,
    generate_variant_candidates,
)

from .. import (
    asset_graph,
    discovery_control,
    discovery_wizard_diagnostics,
    impact,
    industry_coverage,
    loaders,
    selection_profiles,
    sni_diagnostics,
)
from ..paths import REPO_ROOT
from ._helpers import safe_render

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
REFERENCE_TEMPLATES_DIR = REPO_ROOT / "data" / "reference-templates"
VARIANT_CANDIDATES_DIR = REPO_ROOT / "data" / "variant-candidates"
DOSSIER_CANDIDATES_DIR = REPO_ROOT / "data" / "dossier-candidates"
PLACEHOLDER_MARKER = asset_graph.PLACEHOLDER_MARKER


def is_placeholder_file(path: Path) -> bool:
    """Return True if file looks like a placeholder created by the builder."""
    return asset_graph.is_placeholder_file(path)


def scaffold_is_real(scaffold_dir: Path) -> bool:
    """Scaffold is real iff every required contract file exists."""
    return asset_graph.scaffold_is_real(scaffold_dir)


def _list_scaffold_dirs() -> list:
    return asset_graph.list_scaffold_dirs(SCAFFOLDS_DIR)


def _list_dossier_dirs(classes: list[str] | None = None) -> list:
    return asset_graph.list_dossier_dirs(classes=classes)


def _scaffold_options() -> list[str]:
    return [path.name for path in _list_scaffold_dirs()]


def create_variant_candidate_from_ui(
    *,
    scaffold_id: str,
    brief: str,
    variant_id: str | None,
    use_llm: bool,
    force: bool,
):
    """Generate a Variant candidate from Backoffice without touching canonical files."""
    return generate_variant_candidates(
        scaffold_id=scaffold_id,
        brief=brief,
        variant_id=variant_id,
        output_dir=VARIANT_CANDIDATES_DIR,
        enabled=False,
        force=force,
        use_llm=use_llm,
    )


def create_dossier_candidate_from_ui(
    *,
    brief: str,
    candidate_id: str | None,
    capability: str | None,
    use_llm: bool,
    force: bool,
    intake_report: dict | None = None,
):
    """Generate a Dossier candidate from Backoffice without touching canonical files."""
    return generate_dossier_candidate(
        brief=brief,
        candidate_id=candidate_id,
        capability=capability,
        output_dir=DOSSIER_CANDIDATES_DIR,
        force=force,
        use_llm=use_llm,
        intake_report=intake_report,
    )


def analyze_dossier_source_from_ui(
    *,
    source_path: str,
    operator_brief: str,
) -> dict:
    """Analyse a local source path from Backoffice without writing files."""
    return analyze_dossier_source(
        source_path,
        operator_brief=operator_brief,
    )


def _render_impact_summary(result: dict) -> None:
    node = result["node"]
    cols = st.columns(4)
    cols[0].metric("Risk", result["riskLevel"])
    cols[1].metric("Inkommande", len(result["incoming"]))
    cols[2].metric("Utgående", len(result["outgoing"]))
    cols[3].metric("Runtime", "ja" if node.get("canonical") else "nej")
    st.info(result["runtimeEffect"])

    relation_rows = impact.impact_table_rows(result)
    if relation_rows:
        st.dataframe(relation_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Inga direkta relationer hittades.")

    if result["affectedNodes"]:
        with st.expander("Påverkade noder"):
            st.dataframe(result["affectedNodes"], use_container_width=True, hide_index=True)
    if result["affectedPaths"]:
        with st.expander("Berörda filer"):
            for path in result["affectedPaths"]:
                st.write(f"- `{path}`")


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _render_candidate_source_help() -> None:
    st.info(
        "`real` = skapad via policyregistrerad modellroll. "
        "`deterministic-v1` = lokal deterministisk fallback. "
        "`mock-no-key` = ingen API-nyckel fanns. "
        "`mock-llm-error` = modellfel, fallback användes. "
        "Candidates är inte canonical och promoteras aldrig automatiskt."
    )


def _warn_non_real_sources(rows: list[dict]) -> None:
    sources = sorted(
        {
            str(row.get("source") or "")
            for row in rows
            if str(row.get("source") or "") not in {"", "real"}
        }
    )
    if sources:
        st.warning(
            "Minst en kandidat är inte verifierat skapad av en riktig modellcall: "
            + ", ".join(f"`{source}`" for source in sources)
        )


def _render_discovery_mapping() -> None:
    st.subheader("Discovery Mapping")
    st.caption(
        "Discovery category-ändringar påverkar framtida init-runs via "
        "Discovery Resolver. Redan skapade Project Inputs skrivs inte om."
    )

    policy = discovery_control.load_discovery_policy()
    mapping_rows = discovery_control.category_mapping_rows(policy)
    discovery_graph = discovery_control.build_discovery_graph(policy)

    status_counts: dict[str, int] = {}
    for row in mapping_rows:
        status = str(row["supportStatus"])
        status_counts[status] = status_counts.get(status, 0) + 1
    cols = st.columns(4)
    for index, status in enumerate(("active", "fallback", "planned", "disabled")):
        cols[index].metric(status, status_counts.get(status, 0))

    st.dataframe(mapping_rows, use_container_width=True, hide_index=True)

    with st.expander("Discovery relationer i asset graph"):
        st.dataframe(discovery_graph["nodes"], use_container_width=True, hide_index=True)
        st.dataframe(discovery_graph["edges"], use_container_width=True, hide_index=True)

    with st.expander("Discovery gap/orphan"):
        gap_rows = discovery_control.discovery_gap_rows(policy)
        if gap_rows:
            st.dataframe(gap_rows, use_container_width=True, hide_index=True)
        else:
            st.success("Inga Discovery mapping-fynd.")

    category_ids = [str(row["categoryId"]) for row in mapping_rows]
    if not category_ids:
        return

    st.divider()
    st.subheader("Discovery Dry Run")
    dry_category = st.selectbox("Kategori", category_ids, key="discovery_dry_category")
    if st.button("Kör dry-run", key="discovery_dry_run"):
        st.session_state["discovery_dry_run_result"] = discovery_control.run_discovery_dry_run(
            dry_category
        )
    if "discovery_dry_run_result" in st.session_state:
        result = st.session_state["discovery_dry_run_result"]
        if result.get("categoryId") != dry_category:
            st.info("Dry-run-resultatet gäller en annan kategori. Kör dry-run igen.")
        else:
            st.markdown("**DiscoveryDecision**")
            st.json(result["decision"], expanded=False)
            st.markdown("**Field Source**")
            st.json(result["fieldSources"], expanded=False)
            st.markdown("**fallbackWarnings**")
            st.json(result["fallbackWarnings"], expanded=False)

    st.divider()
    st.subheader("Begränsad edit-mode")
    st.warning(
        "Edit-läget skriver endast `discovery-taxonomy.v1.json`, via atomic JSON write, "
        "efter scaffold/variant/starter/capability/Dossier-validering. Candidate Dossiers "
        "promoteras aldrig till `selectedDossiers.required`."
    )
    edit_enabled = st.toggle("Aktivera Discovery policy edit", key="discovery_edit_toggle")
    if not edit_enabled:
        st.caption("Read-only tills edit-toggle aktiveras.")
        return

    selected_category = st.selectbox(
        "Välj kategori att editera",
        category_ids,
        key="discovery_edit_category",
    )
    category = next(
        item for item in policy["categories"] if item.get("id") == selected_category
    )
    support_options = ["active", "fallback", "planned", "disabled"]
    current_support = str(category.get("supportStatus") or "planned")
    support_index = (
        support_options.index(current_support)
        if current_support in support_options
        else support_options.index("planned")
    )
    with st.form("discovery_edit_form"):
        support_status = st.selectbox(
            "supportStatus",
            support_options,
            index=support_index,
        )
        label_sv = st.text_input("labelSv", value=str(category.get("labelSv", "")))
        operator_notes = st.text_area(
            "operatorNotes",
            value=str(category.get("operatorNotes", "")),
            height=80,
        )
        target_scaffold = st.text_input(
            "targetScaffoldId",
            value=str(category.get("targetScaffoldId", "")),
        )
        active_scaffold = st.text_input(
            "activeScaffoldId",
            value=str(category.get("activeScaffoldId", "")),
        )
        fallback_scaffold = st.text_input(
            "fallbackScaffoldId",
            value=str(category.get("fallbackScaffoldId", "")),
        )
        default_variant = st.text_input(
            "defaultVariantId",
            value=str(category.get("defaultVariantId", "")),
        )
        requested_capabilities = st.text_input(
            "requestedCapabilities (comma-separated)",
            value=", ".join(category.get("requestedCapabilities") or []),
        )
        candidate_dossiers = st.text_input(
            "candidateDossiers (comma-separated)",
            value=", ".join(category.get("candidateDossiers") or []),
        )
        dry_validate = st.form_submit_button("Dry-run validation")
        save = st.form_submit_button("Spara policy")

    if dry_validate or save:
        updates = {
            "supportStatus": support_status,
            "labelSv": label_sv,
            "operatorNotes": operator_notes.strip(),
            "targetScaffoldId": target_scaffold,
            "activeScaffoldId": active_scaffold.strip(),
            "fallbackScaffoldId": fallback_scaffold.strip(),
            "defaultVariantId": default_variant,
            "requestedCapabilities": _csv_to_list(requested_capabilities),
            "candidateDossiers": _csv_to_list(candidate_dossiers),
        }
        try:
            _proposed, findings = discovery_control.save_category_update(
                selected_category,
                updates,
                write=save,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        if save:
            loaders.load_json.clear()
            loaders.read_text.clear()
            st.success("Discovery-taxonomy sparad atomiskt.")
        else:
            st.success("Dry-run validation OK. Inget skrevs till disk.")
        if findings:
            st.dataframe(findings, use_container_width=True, hide_index=True)


def _filter_options(rows: list[dict], key: str) -> list[str]:
    values = sorted({str(row.get(key) or "") for row in rows if row.get(key)})
    return ["Alla"] + values


def _split_cell_values(value: object) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _multi_filter_options(rows: list[dict], keys: list[str]) -> list[str]:
    values: set[str] = set()
    for row in rows:
        for key in keys:
            values.update(_split_cell_values(row.get(key)))
    return ["Alla"] + sorted(values)


def _filter_asset_graph_rows(
    rows: list[dict],
    *,
    exact_filters: dict[str, str],
    multi_filters: dict[str, tuple[str, list[str]]],
    attention_filter: str,
) -> list[dict]:
    filtered = rows
    for key, selected in exact_filters.items():
        if selected != "Alla":
            filtered = [row for row in filtered if str(row.get(key) or "") == selected]
    for selected, keys in multi_filters.values():
        if selected == "Alla":
            continue
        filtered = [
            row
            for row in filtered
            if any(selected in _split_cell_values(row.get(key)) for key in keys)
        ]
    if attention_filter == "Endast gap/orphan/missing":
        filtered = [row for row in filtered if row.get("gapOrOrphan") is True]
    elif attention_filter == "Utan gap/orphan/missing":
        filtered = [row for row in filtered if row.get("gapOrOrphan") is not True]
    return filtered


def _render_asset_graph() -> None:
    st.subheader("Asset Graph: category → scaffold → starter → variant → dossier")
    st.caption(
        "Denna vy är read-only och visar befintliga källor. Den aktiverar inte "
        "starters, ändrar inte mappings och är inte runtime-sanning."
    )

    try:
        summary = asset_graph.asset_graph_summary()
        category_rows = asset_graph.asset_graph_category_rows()
        scaffold_rows = asset_graph.asset_graph_scaffold_rows()
        starter_rows = asset_graph.asset_graph_starter_rows()
        capability_rows = asset_graph.asset_graph_capability_rows()
    except ImportError as exc:
        st.error(
            "Asset Graph kan inte läsa runtime-mappningen från planning. "
            f"Diagnostiken stoppas så den inte visar fel status: {exc}"
        )
        return

    metric_cols = st.columns(6)
    metric_cols[0].metric("categories", summary["categories"])
    metric_cols[1].metric("scaffolds", summary["scaffolds"])
    metric_cols[2].metric("starters", summary["starters"])
    metric_cols[3].metric(
        "runtime-mapped starters",
        summary["runtimeMappedStarters"],
    )
    metric_cols[4].metric(
        "available-not-mapped starters",
        summary["availableNotMappedStarters"],
    )
    metric_cols[5].metric("gaps/orphans/missing", summary["gapsOrphansMissing"])

    category_tab, scaffold_tab, starter_tab, capability_tab = st.tabs(
        ["Categories", "Scaffolds", "Starters", "Capabilities"]
    )
    attention_options = [
        "Alla",
        "Endast gap/orphan/missing",
        "Utan gap/orphan/missing",
    ]

    with category_tab:
        filter_cols = st.columns(4)
        selected_category = filter_cols[0].selectbox(
            "Category",
            _filter_options(category_rows, "categoryId"),
            key="asset_graph_category_filter",
        )
        selected_status = filter_cols[1].selectbox(
            "Status",
            _filter_options(category_rows, "status"),
            key="asset_graph_category_status_filter",
        )
        selected_scaffold = filter_cols[2].selectbox(
            "Scaffold",
            _multi_filter_options(
                category_rows,
                ["targetScaffoldId", "activeScaffoldId", "fallbackScaffoldId"],
            ),
            key="asset_graph_category_scaffold_filter",
        )
        selected_attention = filter_cols[3].selectbox(
            "Gap/orphan",
            attention_options,
            key="asset_graph_category_attention_filter",
        )
        filtered_rows = _filter_asset_graph_rows(
            category_rows,
            exact_filters={
                "categoryId": selected_category,
                "status": selected_status,
            },
            multi_filters={
                "scaffold": (
                    selected_scaffold,
                    ["targetScaffoldId", "activeScaffoldId", "fallbackScaffoldId"],
                )
            },
            attention_filter=selected_attention,
        )
        st.dataframe(filtered_rows, use_container_width=True, hide_index=True)
        with st.expander("Category-detaljer"):
            st.write(
                "Category-raderna delegerar supportStatus/mappingState till "
                "`category_mapping_rows()` och visar capability-gaps från "
                "Capability Map."
            )

    with scaffold_tab:
        filter_cols = st.columns(4)
        selected_scaffold = filter_cols[0].selectbox(
            "Scaffold",
            _filter_options(scaffold_rows, "scaffoldId"),
            key="asset_graph_scaffold_filter",
        )
        selected_status = filter_cols[1].selectbox(
            "Status",
            _filter_options(scaffold_rows, "status"),
            key="asset_graph_scaffold_status_filter",
        )
        selected_starter = filter_cols[2].selectbox(
            "Starter",
            _filter_options(scaffold_rows, "runtimeStarterId"),
            key="asset_graph_scaffold_starter_filter",
        )
        selected_attention = filter_cols[3].selectbox(
            "Gap/orphan",
            attention_options,
            key="asset_graph_scaffold_attention_filter",
        )
        filtered_rows = _filter_asset_graph_rows(
            scaffold_rows,
            exact_filters={
                "scaffoldId": selected_scaffold,
                "status": selected_status,
                "runtimeStarterId": selected_starter,
            },
            multi_filters={},
            attention_filter=selected_attention,
        )
        st.dataframe(filtered_rows, use_container_width=True, hide_index=True)
        with st.expander("Scaffold-detaljer"):
            st.write(
                "Scaffold-status kombinerar scaffold-contract registry, filer "
                "på disk och runtime-mappningen från planning."
            )

    with starter_tab:
        filter_cols = st.columns(4)
        selected_starter = filter_cols[0].selectbox(
            "Starter",
            _filter_options(starter_rows, "starterId"),
            key="asset_graph_starter_filter",
        )
        selected_status = filter_cols[1].selectbox(
            "Status",
            _filter_options(starter_rows, "status"),
            key="asset_graph_starter_status_filter",
        )
        selected_scaffold = filter_cols[2].selectbox(
            "Scaffold",
            _multi_filter_options(starter_rows, ["runtimeMappedScaffolds"]),
            key="asset_graph_starter_scaffold_filter",
        )
        selected_attention = filter_cols[3].selectbox(
            "Gap/orphan",
            attention_options,
            key="asset_graph_starter_attention_filter",
        )
        filtered_rows = _filter_asset_graph_rows(
            starter_rows,
            exact_filters={
                "starterId": selected_starter,
                "status": selected_status,
            },
            multi_filters={
                "scaffold": (selected_scaffold, ["runtimeMappedScaffolds"])
            },
            attention_filter=selected_attention,
        )
        st.dataframe(filtered_rows, use_container_width=True, hide_index=True)
        with st.expander("Starter-detaljer"):
            st.write(
                "Runtime-mappade starters kommer från `SCAFFOLD_TO_STARTER`; "
                "available-not-mapped och placeholder kommer från Starter Registry."
            )

    with capability_tab:
        filter_cols = st.columns(4)
        selected_capability = filter_cols[0].selectbox(
            "Capability",
            _filter_options(capability_rows, "capabilityId"),
            key="asset_graph_capability_filter",
        )
        selected_status = filter_cols[1].selectbox(
            "Status",
            _filter_options(capability_rows, "status"),
            key="asset_graph_capability_status_filter",
        )
        selected_category = filter_cols[2].selectbox(
            "Category",
            _multi_filter_options(capability_rows, ["referencedByCategories"]),
            key="asset_graph_capability_category_filter",
        )
        selected_attention = filter_cols[3].selectbox(
            "Gap/orphan",
            attention_options,
            key="asset_graph_capability_attention_filter",
        )
        filtered_rows = _filter_asset_graph_rows(
            capability_rows,
            exact_filters={
                "capabilityId": selected_capability,
                "status": selected_status,
            },
            multi_filters={
                "category": (selected_category, ["referencedByCategories"])
            },
            attention_filter=selected_attention,
        )
        st.dataframe(filtered_rows, use_container_width=True, hide_index=True)
        with st.expander("Capability-detaljer"):
            st.write(
                "Capabilities med tom `dossiers`-lista markeras som gap; "
                "referenser som saknas i Capability Map markeras som unknown."
            )


def _render_wizard_generation_mapping() -> None:
    st.subheader("Wizardfält → generation")
    st.caption(
        "Read-only diagnostik över kända wizardfält. Backoffice visar bara "
        "befintliga källor och är inte en ny runtime-sanning."
    )
    st.info(
        "Denna vy visar kända och dokumenterade wizardfält. Den är diagnostisk "
        "och kan vara ofullständig om frontendtypen ändras utan att "
        "diagnostikhelpern uppdateras."
    )

    rows = discovery_wizard_diagnostics.wizard_generation_rows()
    summary = discovery_wizard_diagnostics.wizard_generation_summary(rows)

    cols = st.columns(4)
    cols[0].metric("Wizardfält", summary["total"])
    cols[1].metric("Aktiva", summary["active"])
    cols[2].metric("Fallback/planned", summary["fallback_or_planned"])
    cols[3].metric(
        "Gap/unknown/saknar destination",
        summary["needs_attention"],
    )
    detail_cols = st.columns(3)
    detail_cols[0].metric("Deterministiska", summary["deterministic"])
    detail_cols[1].metric("Prompt-signaler", summary["prompt_signal"])
    detail_cols[2].metric("Downstream-gap", summary["downstream_gap"])

    filter_cols = st.columns(4)
    selected_step = filter_cols[0].selectbox(
        "Steg",
        _filter_options(rows, "stepLabel"),
        key="wizard_generation_step_filter",
    )
    selected_status = filter_cols[1].selectbox(
        "Status",
        _filter_options(rows, "status"),
        key="wizard_generation_status_filter",
    )
    selected_propagation = filter_cols[2].selectbox(
        "Signalnivå",
        _filter_options(rows, "propagationLevel"),
        key="wizard_generation_propagation_filter",
    )
    destination_query = filter_cols[3].text_input(
        "Destination/källa",
        key="wizard_generation_destination_filter",
        placeholder="t.ex. brand, capability, taxonomy",
    )

    filtered_rows = rows
    if selected_step != "Alla":
        filtered_rows = [
            row for row in filtered_rows if row["stepLabel"] == selected_step
        ]
    if selected_status != "Alla":
        filtered_rows = [
            row for row in filtered_rows if row["status"] == selected_status
        ]
    if selected_propagation != "Alla":
        filtered_rows = [
            row
            for row in filtered_rows
            if row["propagationLevel"] == selected_propagation
        ]
    if destination_query.strip():
        needle = destination_query.strip().lower()
        filtered_rows = [
            row
            for row in filtered_rows
            if needle
            in " ".join(
                [
                    row["answerPath"],
                    row["destination"],
                    row["sourceChain"],
                    row["sourcePath"],
                    row["explanation"],
                ]
            ).lower()
        ]

    st.dataframe(filtered_rows, use_container_width=True, hide_index=True)

    with st.expander("Källa och avgränsning"):
        st.markdown(
            "- `status` visar om känd mapping är aktiv, planned/fallback, gap, "
            "unknown eller saknar känd destination.\n"
            "- `propagationLevel` visar hur långt signalen kan styrkas: "
            "deterministisk destination, prompt-signal, Project Input-only, "
            "downstream-gap eller diagnostic-only.\n"
            "- Wizarden får inte sätta `starterId` direkt.\n"
            "- Dossiers väljs inte direkt av wizardknappar; wizardens svar blir "
            "capability-/taxonomisignaler och går vidare via Capability Map, "
            "Dossier Selection och planning."
        )


def _render_sni_discovery_mapping() -> None:
    st.subheader("SNI → Discovery category")
    st.caption(
        "Read-only diagnostik: SNI 2025-prefix (huvudgrupp/grupp) → "
        "kandidat wizardCategoryId. Inget i runtime konsumerar SNI än."
    )
    for line in sni_diagnostics.WARNING_LINES_SV:
        st.markdown(f"- {line}")

    reference = sni_diagnostics.load_sni_reference()
    ref_summary = sni_diagnostics.reference_summary(reference)
    rows = sni_diagnostics.mapping_rows(reference=reference)
    summary = sni_diagnostics.mapping_summary(rows)

    metric_cols = st.columns(4)
    metric_cols[0].metric("SNI-poster", ref_summary["total"])
    metric_cols[1].metric("Huvudgrupp-mappningar", summary["divisionMappings"])
    metric_cols[2].metric("Grupp-overrides", summary["groupOverrides"])
    metric_cols[3].metric("Unika kategorier", summary["uniqueCategories"])

    detail_cols = st.columns(5)
    detail_cols[0].metric("Avdelningar", ref_summary["section"])
    detail_cols[1].metric("Huvudgrupper", ref_summary["division"])
    detail_cols[2].metric("Grupper", ref_summary["group"])
    detail_cols[3].metric("Undergrupper", ref_summary["class"])
    detail_cols[4].metric("Detaljgrupper", ref_summary["subclass"])

    confidence = sni_diagnostics.confidence_breakdown(rows)
    conf_cols = st.columns(4)
    conf_cols[0].metric("Confidence high", confidence["high"])
    conf_cols[1].metric("Confidence medium", confidence["medium"])
    conf_cols[2].metric("Confidence low", confidence["low"])
    conf_cols[3].metric("Confidence övrigt", confidence["other"])

    if summary["unknownCategories"]:
        st.warning(
            f"{summary['unknownCategories']} policyrad(er) pekar mot en "
            "wizardCategoryId som inte finns i Discovery Taxonomy. Justera "
            "policy eller taxonomy innan SNI används som signal."
        )

    coverage_gaps = sni_diagnostics.taxonomy_coverage_gaps(rows=rows)
    with st.expander(
        f"Discovery Taxonomy-kategorier utan SNI-mappning ({len(coverage_gaps)})"
    ):
        if coverage_gaps:
            st.caption(
                "Kategorier som finns i Discovery Taxonomy men inte har en "
                "enda policyrad i SNI Discovery Map. Inte ett fel — bara en "
                "indikator på var policyn kan breddas i en framtida sprint."
            )
            st.dataframe(coverage_gaps, use_container_width=True, hide_index=True)
        else:
            st.success("Alla Discovery Taxonomy-kategorier har minst en SNI-mappning.")

    category_options = ["Alla"] + sorted({str(row["wizardCategoryId"]) for row in rows})
    selected_category = st.selectbox(
        "wizardCategoryId",
        category_options,
        key="sni_mapping_category_filter",
    )
    filtered_rows = sni_diagnostics.filter_rows_by_category(rows, selected_category)
    st.dataframe(filtered_rows, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("**Testa en SNI-kod**")
    st.caption(
        "Ange en 2- till 5-siffrig SNI-kod (med eller utan punkt). Diagnostiken "
        "visar matchad prefix, kandidat-kategori, parent-chain från avdelning "
        "ner till själva koden och hur Discovery Taxonomy skulle välja "
        "scaffold/variant/starter när kategorin når resolvern."
    )
    sni_input = st.text_input(
        "SNI-kod",
        key="sni_lookup_input",
        placeholder="t.ex. 56, 56.10, 56100 eller 691",
    )
    if sni_input.strip():
        lookup = sni_diagnostics.lookup_row(sni_input)
        parent_chain = sni_diagnostics.lookup_parent_chain(sni_input, reference=reference)
        if lookup["matchedLevel"] == "unknown" and not parent_chain:
            st.info(
                "Ingen policymappning matchade och koden finns inte i SNI-"
                "referensen. SNI är branschsignal — okänd kod är ett tyst "
                "no-op, inte ett fel."
            )
        else:
            if parent_chain:
                st.markdown("**Parent-chain i SNI 2025-referensen**")
                st.dataframe(parent_chain, use_container_width=True, hide_index=True)
            if lookup["matchedLevel"] == "unknown":
                st.info(
                    "Koden finns i SNI-referensen men ingen policymappning "
                    "täcker prefixet. Inte ett fel — bara en täckningslucka."
                )
            else:
                st.json(lookup, expanded=False)
                if not lookup["categoryKnown"]:
                    st.warning(
                        "Mappningen pekar mot en wizardCategoryId som saknas "
                        "i Discovery Taxonomy. Inga scaffold/variant/starter "
                        "visas."
                    )


def _industry_filter_options(rows: list[dict], key: str) -> list[str]:
    values = sorted({str(row.get(key) or "") for row in rows if row.get(key)})
    return ["Alla"] + values


def _industry_scaffold_options(rows: list[dict]) -> list[str]:
    values: set[str] = set()
    for row in rows:
        for key in ("targetScaffoldId", "selectedRuntimeScaffoldId", "fallbackScaffoldId"):
            value = row.get(key)
            if value:
                values.add(str(value))
    return ["Alla"] + sorted(values)


def _filter_industry_rows(
    rows: list[dict],
    *,
    content_branch: str,
    support_status: str,
    coverage_status: str,
    scaffold: str,
    only_attention: bool,
) -> list[dict]:
    filtered = rows
    if content_branch != "Alla":
        filtered = [row for row in filtered if row.get("contentBranch") == content_branch]
    if support_status != "Alla":
        filtered = [row for row in filtered if row.get("supportStatus") == support_status]
    if coverage_status != "Alla":
        filtered = [row for row in filtered if row.get("coverageStatus") == coverage_status]
    if scaffold != "Alla":
        filtered = [
            row
            for row in filtered
            if scaffold
            in {
                str(row.get("targetScaffoldId") or ""),
                str(row.get("selectedRuntimeScaffoldId") or ""),
                str(row.get("fallbackScaffoldId") or ""),
            }
        ]
    if only_attention:
        filtered = [row for row in filtered if row.get("needsAttention") is True]
    return filtered


def _render_industry_candidate_panel(rows: list[dict]) -> None:
    with st.expander("Candidate-actions för vald kategori"):
        st.caption(
            "Åtgärderna kräver operatortryck och skriver bara till candidate-mappar. "
            "Scaffold-actions är read-only i denna version."
        )
        category_options = sorted(str(row["wizardCategoryId"]) for row in rows)
        if not category_options:
            st.info("Inga kategorier finns att välja.")
            return
        selected_category = st.selectbox(
            "Kategori",
            category_options,
            key="industry_coverage_candidate_category",
        )
        row = next(item for item in rows if item["wizardCategoryId"] == selected_category)
        actions = list(row.get("recommendedActions") or [])
        if not actions:
            st.success("Den valda kategorin har inga recommended actions just nu.")
            return
        selected_action = st.selectbox(
            "Åtgärd",
            actions,
            key="industry_coverage_candidate_action",
        )
        st.write(f"**coverageStatus:** `{row['coverageStatus']}`")
        st.write(
            "**attentionReasons:** "
            + (", ".join(row.get("attentionReasons") or []) or "inga")
        )

        if selected_action == "create_variant_candidate":
            scaffold_id = row.get("selectedRuntimeScaffoldId")
            if not scaffold_id:
                st.info(
                    "Ingen runtimebar selectedRuntimeScaffoldId finns. Variant-kandidat "
                    "kan inte skapas säkert för denna kategori."
                )
                return
            default_brief = industry_coverage.build_variant_candidate_brief(row)
            with st.form("industry_variant_candidate_form"):
                variant_id = st.text_input(
                    "Variant id (valfritt)",
                    value=f"{row['wizardCategoryId']}-coverage",
                )
                brief = st.text_area("Variant-brief", value=default_brief, height=260)
                use_llm = st.checkbox(
                    "Använd variantModel om OPENAI_API_KEY finns",
                    value=False,
                )
                force = st.checkbox("Skriv över befintlig kandidat med samma id", value=False)
                submitted = st.form_submit_button("Skapa Variant-kandidat")
            if submitted:
                try:
                    [result] = create_variant_candidate_from_ui(
                        scaffold_id=str(scaffold_id),
                        brief=brief,
                        variant_id=variant_id.strip() or None,
                        use_llm=use_llm,
                        force=force,
                    )
                except (VariantGenerationError, ValueError, RuntimeError) as exc:
                    st.error(f"Kunde inte skapa Variant-kandidat: {exc}")
                    return
                st.success(f"Skapade `{result.path.relative_to(REPO_ROOT)}`")
                st.write(f"**Source:** `{result.source}`")
                st.write(f"**Model:** `{result.model_used}`")
                st.json(result.payload, expanded=False)
            return

        if selected_action == "create_soft_dossier_candidate":
            capabilities = list(row.get("safeSoftCapabilityGaps") or [])
            if not capabilities:
                st.info(
                    "Den valda kategorin har ingen safe soft capability-gap. "
                    "Visa recommended action som review i stället."
                )
                return
            capability = st.selectbox(
                "Capability",
                capabilities,
                key="industry_dossier_candidate_capability",
            )
            default_brief = industry_coverage.build_dossier_candidate_brief(
                row,
                capability_id=capability,
            )
            with st.form("industry_dossier_candidate_form"):
                candidate_id = st.text_input(
                    "Dossier id (valfritt)",
                    value=f"{capability}-{row['wizardCategoryId']}",
                )
                brief = st.text_area("Capability-brief", value=default_brief, height=260)
                use_llm = st.checkbox(
                    "Använd dossierModel om OPENAI_API_KEY finns",
                    value=False,
                )
                force = st.checkbox("Skriv över befintlig kandidat med samma id", value=False)
                submitted = st.form_submit_button("Skapa Soft Dossier-kandidat")
            if submitted:
                try:
                    result = create_dossier_candidate_from_ui(
                        brief=brief,
                        candidate_id=candidate_id.strip() or None,
                        capability=capability,
                        use_llm=use_llm,
                        force=force,
                    )
                except (DossierGenerationError, ValueError, RuntimeError) as exc:
                    st.error(f"Kunde inte skapa Dossier-kandidat: {exc}")
                    return
                st.success(f"Skapade `{result.candidate_dir.relative_to(REPO_ROOT)}`")
                st.write(f"**Source:** `{result.source}`")
                st.write(f"**Model:** `{result.model_used}`")
                st.subheader("manifest.json")
                st.json(result.manifest, expanded=False)
                st.subheader("instructions.md")
                st.code(result.instructions, language="markdown")
            return

        if selected_action == "create_scaffold_candidate":
            st.info(
                "Scaffold-candidate skrivs inte i denna version. Åtgärden är en "
                "read-only gap-signal tills repo:t har en explicit scaffold-"
                "candidate-konvention."
            )
            return

        st.info(
            "Den här åtgärden är en review-signal. Ändra inte policy eller runtime "
            "härifrån; använd ansvarig governance-/mapping-yta."
        )


def _render_industry_coverage() -> None:
    st.subheader("Branschtäckning")
    st.caption(
        "Read-only översikt över SNI → Discovery category → contentBranch → "
        "scaffold/variant/starter → capability/Dossier. Candidate-actions "
        "kräver operatortryck och skriver bara till candidate-mappar."
    )
    st.markdown("- SNI är branschsignal, inte runtime-sanning.")
    st.markdown("- Discovery Taxonomy styr downstream-valen.")
    st.markdown("- Inga candidates promoteras automatiskt.")

    rows = industry_coverage.industry_coverage_rows()
    table_rows = industry_coverage.table_rows(rows)
    summary_rows = industry_coverage.content_branch_summary(rows)
    action_rows = industry_coverage.recommended_action_rows(rows)

    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("coverageStatus") or "")
        status_counts[status] = status_counts.get(status, 0) + 1

    metric_cols = st.columns(7)
    metric_cols[0].metric("contentBranches", len({row["contentBranch"] for row in rows}))
    metric_cols[1].metric("categories", len(rows))
    metric_cols[2].metric("active_native", status_counts.get("active_native", 0))
    metric_cols[3].metric(
        "planned/fallback",
        status_counts.get("planned", 0) + status_counts.get("fallback_only", 0),
    )
    metric_cols[4].metric(
        "med SNI",
        sum(1 for row in rows if int(row.get("sniMappingCount") or 0) > 0),
    )
    metric_cols[5].metric(
        "utan SNI",
        sum(1 for row in rows if int(row.get("sniMappingCount") or 0) == 0),
    )
    metric_cols[6].metric(
        "needsAttention",
        sum(1 for row in rows if row.get("needsAttention") is True),
    )

    branch_tab, category_tab, sni_tab, action_tab = st.tabs(
        [
            "Per contentBranch",
            "Per kategori",
            "SNI-täckning",
            "Rekommenderade åtgärder",
        ]
    )

    with branch_tab:
        selected_branch = st.selectbox(
            "contentBranch",
            _industry_filter_options(summary_rows, "contentBranch"),
            key="industry_branch_summary_filter",
        )
        filtered_summary = (
            summary_rows
            if selected_branch == "Alla"
            else [row for row in summary_rows if row["contentBranch"] == selected_branch]
        )
        st.dataframe(filtered_summary, use_container_width=True, hide_index=True)

    with category_tab:
        filter_cols = st.columns(5)
        selected_branch = filter_cols[0].selectbox(
            "contentBranch",
            _industry_filter_options(rows, "contentBranch"),
            key="industry_category_branch_filter",
        )
        selected_support = filter_cols[1].selectbox(
            "supportStatus",
            _industry_filter_options(rows, "supportStatus"),
            key="industry_category_support_filter",
        )
        selected_coverage = filter_cols[2].selectbox(
            "coverageStatus",
            _industry_filter_options(rows, "coverageStatus"),
            key="industry_category_coverage_filter",
        )
        selected_scaffold = filter_cols[3].selectbox(
            "Scaffold",
            _industry_scaffold_options(rows),
            key="industry_category_scaffold_filter",
        )
        only_attention = filter_cols[4].checkbox(
            "Endast needsAttention",
            value=False,
            key="industry_category_attention_filter",
        )
        filtered_rows = _filter_industry_rows(
            table_rows,
            content_branch=selected_branch,
            support_status=selected_support,
            coverage_status=selected_coverage,
            scaffold=selected_scaffold,
            only_attention=only_attention,
        )
        st.dataframe(filtered_rows, use_container_width=True, hide_index=True)

    with sni_tab:
        sni_rows = [
            {
                "wizardCategoryId": row["wizardCategoryId"],
                "labelSv": row["labelSv"],
                "contentBranch": row["contentBranch"],
                "mappedSniDivisions": row["mappedSniDivisions"],
                "mappedSniGroups": row["mappedSniGroups"],
                "sniMappingCount": row["sniMappingCount"],
                "sniConfidenceHigh": row["sniConfidenceHigh"],
                "sniConfidenceMedium": row["sniConfidenceMedium"],
                "sniConfidenceLow": row["sniConfidenceLow"],
                "coverageStatus": row["coverageStatus"],
            }
            for row in table_rows
        ]
        st.dataframe(sni_rows, use_container_width=True, hide_index=True)
        missing_sni = [row for row in sni_rows if int(row["sniMappingCount"]) == 0]
        with st.expander(f"Kategorier utan SNI-mappning ({len(missing_sni)})"):
            if missing_sni:
                st.dataframe(missing_sni, use_container_width=True, hide_index=True)
            else:
                st.success("Alla kategorier har minst en SNI-mappning.")

    with action_tab:
        selected_action = st.selectbox(
            "Action type",
            ["Alla"] + sorted({str(row["action"]) for row in action_rows}),
            key="industry_action_filter",
        )
        filtered_actions = (
            action_rows
            if selected_action == "Alla"
            else [row for row in action_rows if row["action"] == selected_action]
        )
        st.dataframe(filtered_actions, use_container_width=True, hide_index=True)
        if filtered_actions:
            selected_category = st.selectbox(
                "Visa category-kontext",
                sorted({str(row["wizardCategoryId"]) for row in filtered_actions}),
                key="industry_action_context_category",
            )
            selected_row = next(row for row in rows if row["wizardCategoryId"] == selected_category)
            st.write(f"**Rationale:** {selected_row['rationale']}")
            if selected_row.get("operatorNotes"):
                st.write(f"**operatorNotes:** {selected_row['operatorNotes']}")
            st.write(
                "**recommendedPages:** "
                + (", ".join(selected_row.get("recommendedPages") or []) or "inga")
            )
        _render_industry_candidate_panel(rows)


def view_control_plane() -> None:
    st.title("Kontrollplan")
    st.caption(
        "Read-only översikt över Starters, Scaffolds, Variants, Dossiers, "
        "modellroller, Discovery mapping och kandidatfiler."
    )

    graph = asset_graph.build_graph()
    findings = asset_graph.run_health_checks()

    st.subheader("Doctor")
    if not findings:
        st.success("Inga kända driftfynd.")
    else:
        st.dataframe(findings, use_container_width=True, hide_index=True)

    st.subheader("Nodes")
    st.dataframe(graph["nodes"], use_container_width=True, hide_index=True)

    st.subheader("Relationer")
    st.dataframe(graph["edges"], use_container_width=True, hide_index=True)

    st.divider()
    _render_discovery_mapping()

    st.divider()
    _render_wizard_generation_mapping()

    st.divider()
    _render_sni_discovery_mapping()

    st.divider()
    _render_industry_coverage()

    st.divider()
    _render_asset_graph()

    st.divider()
    st.subheader("Konsekvensvy")
    st.caption(
        "Välj en nod för att se direkta relationer och runtime-effekt innan du "
        "inaktiverar eller ändrar något i en annan vy."
    )
    node_options = sorted(
        f"{node['type']}:{node['id']}"
        for node in graph["nodes"]
        if node.get("type") and node.get("id")
    )
    if not node_options:
        st.info("Inga noder finns i grafen.")
        return
    selected_node = st.selectbox("Nod", node_options, key="control_plane_impact_node")
    selected_type, selected_id = selected_node.split(":", 1)
    _render_impact_summary(
        impact.impact_for_node(selected_type, selected_id, graph=graph)
    )


def view_scaffolds() -> None:
    st.title("Scaffolds")
    contract, err = loaders.safe_load_policy("scaffold-contract.v1.json")
    if err or contract is None:
        st.error(err)
        return

    st.caption(contract.get("purpose", ""))

    registry = contract.get("primaryScaffoldRegistry", [])
    required_files = asset_graph.scaffold_required_files(contract)
    real_scaffolds = {
        d.name for d in _list_scaffold_dirs() if asset_graph.scaffold_is_real(d, required_files)
    }
    placeholder_scaffolds = {
        d.name for d in _list_scaffold_dirs()
        if d.exists() and not asset_graph.scaffold_is_real(d, required_files)
    }

    def _status(scaffold_id: str) -> str:
        if scaffold_id in real_scaffolds:
            return "ja"
        if scaffold_id in placeholder_scaffolds:
            return "platshållare"
        return "nej"

    rows = [
        {
            "id": s["id"],
            "label": s["label"],
            "Implementerad": _status(s["id"]),
            "requiredFiles": len(required_files),
            "rationale": s["rationale"],
        }
        for s in registry
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if placeholder_scaffolds:
        st.warning(
            "Följande scaffolds har bara platshållarfiler och bör fyllas eller tas "
            f"bort: {', '.join(sorted(placeholder_scaffolds))}"
        )

    st.divider()
    st.subheader("Filer per Scaffold (kontrakt)")
    layout = contract["scaffoldDirectoryLayout"]
    st.write(f"**Owner package:** `{layout['ownerPackage']}`")
    st.write(f"**Per scaffold path:** `{layout['perScaffoldPath']}`")
    cols = st.columns(2)
    cols[0].markdown("**Required files**")
    for f in layout["requiredFiles"]:
        cols[0].write(f"- `{f}`")
    cols[1].markdown("**Optional files**")
    for f in layout.get("optionalFiles", []):
        cols[1].write(f"- `{f}`")

    st.divider()
    st.subheader("Lägg till första filuppsättning för en Scaffold")
    st.caption(
        "Skapar mappen `packages/generation/orchestration/scaffolds/<id>/` med minimala "
        "obligatoriska filer enligt scaffold-contract. Innehållet är platshållare; "
        "redigera per fil efter creation."
    )

    edit_mode = st.toggle("Aktivera filsystemskrivning", key="scaffold_edit_toggle")
    if not edit_mode:
        return

    candidate_ids = [
        s["id"] for s in registry if s["id"] not in real_scaffolds
    ]
    if not candidate_ids:
        st.info("Alla 14 Scaffolds är redan implementerade.")
        return
    selected = st.selectbox("Välj Scaffold att skapa", candidate_ids, key="scaffold_create_select")
    if not isinstance(selected, str) or not selected:
        st.info("Välj en Scaffold innan du skapar filer.")
        return
    pick = selected
    if st.button(f"Skapa mapp för {pick}", key="scaffold_create"):
        target = SCAFFOLDS_DIR / pick
        target.mkdir(parents=True, exist_ok=True)
        for required in layout["requiredFiles"]:
            path = target / required
            if not path.exists():
                if path.suffix == ".json":
                    path.write_text(
                        json.dumps({"_status": PLACEHOLDER_MARKER}, indent=2) + "\n",
                        encoding="utf-8",
                    )
                else:
                    path.write_text("# placeholder\n", encoding="utf-8")
        st.success(
            f"Skapade {target.relative_to(REPO_ROOT)} med platshållare. "
            "Tabellen ovan visar den nu som 'platshållare', inte 'ja' - "
            "fyll filerna enligt scaffold-contract innan den räknas som implementerad."
        )


def view_variants() -> None:
    st.title("Variants")
    st.caption(
        "Variants ligger under `packages/generation/orchestration/scaffolds/<id>/variants/`. "
        "Canonical ändringar görs i respektive variantfil. Draftar skapas i "
        "`data/variant-candidates/` via Variant Candidates-vyn."
    )
    scaffolds = _list_scaffold_dirs()
    if not scaffolds:
        st.info("Inga Scaffolds finns att äga Variants än. Skapa en Scaffold först.")
        return

    rows = []
    for s in scaffolds:
        variants_dir = s / "variants"
        if not variants_dir.exists():
            continue
        for v in variants_dir.glob("*.json"):
            rows.append({"Scaffold": s.name, "Variant": v.stem})
    if not rows:
        st.info("Inga variants finns än under befintliga Scaffolds.")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)


def view_selection_profiles() -> None:
    st.title("Selection Profiles")
    st.caption(
        "Här styrs semantiska signaler för Scaffold-val. Embedding-policy är "
        "definierad, men index byggs inte ännu."
    )
    if not asset_graph.EMBEDDING_DIR.exists():
        st.info(
            "Embedding-index saknas fortfarande. Ändringar här påverkar curated "
            "selection-profile-data och framtida index, inte ett byggt index idag."
        )

    summaries = selection_profiles.list_profile_summaries()
    if not summaries:
        st.info("Inga selection-profile-filer hittades.")
        return
    st.dataframe(summaries, use_container_width=True, hide_index=True)

    scaffold_ids = [row["scaffold"] for row in summaries]
    selected = st.selectbox("Scaffold", scaffold_ids, key="selection_profile_scaffold")
    try:
        payload = selection_profiles.load_profile(selected)
    except (OSError, ValueError) as exc:
        st.error(f"Kunde inte läsa selection-profile: {exc}")
        return

    findings = selection_profiles.signal_findings(payload)
    if findings:
        st.warning("Signal-fynd: " + "; ".join(findings))
    else:
        st.success("Signal-listorna har inga enkla coverage-fynd.")

    tab_view, tab_edit = st.tabs(["Läs", "Redigera"])
    with tab_view:
        st.json(payload, expanded=False)

    with tab_edit:
        edit_mode = st.toggle("Aktivera redigering", key="selection_profile_edit_toggle")
        if not edit_mode:
            return
        embedding_text = st.text_area(
            "embeddingText",
            value=str(payload.get("embeddingText", "")),
            height=140,
        )
        semantic = st.text_area(
            "semanticSignals (en per rad)",
            value="\n".join(payload.get("semanticSignals", []) or []),
            height=140,
        )
        negative = st.text_area(
            "negativeSignals (en per rad)",
            value="\n".join(payload.get("negativeSignals", []) or []),
            height=140,
        )
        hints = st.text_area(
            "llmClassificationHints (en per rad)",
            value="\n".join(payload.get("llmClassificationHints", []) or []),
            height=140,
        )
        cols = st.columns(2)
        min_confidence = cols[0].number_input(
            "minConfidence",
            min_value=0.0,
            max_value=1.0,
            value=float(payload.get("minConfidence", 0.7)),
            step=0.01,
        )
        tie_break = cols[1].number_input(
            "requiresTieBreakWhenWithin",
            min_value=0.0,
            max_value=1.0,
            value=float(payload.get("requiresTieBreakWhenWithin", 0.08)),
            step=0.01,
        )

        next_payload = {
            "id": payload.get("id", selected),
            "embeddingText": embedding_text.strip(),
            "semanticSignals": selection_profiles.lines_to_list(semantic),
            "negativeSignals": selection_profiles.lines_to_list(negative),
            "llmClassificationHints": selection_profiles.lines_to_list(hints),
            "minConfidence": min_confidence,
            "requiresTieBreakWhenWithin": tie_break,
        }
        errors = selection_profiles.validate_profile(next_payload)
        if errors:
            for error in errors:
                st.error(error)
        st.subheader("Preview")
        st.json(next_payload, expanded=False)
        if st.button("Spara selection-profile", disabled=bool(errors)):
            try:
                selection_profiles.write_profile(selected, next_payload)
            except ValueError as exc:
                st.error(f"Kunde inte spara: {exc}")
                return
            loaders.load_json.clear()
            loaders.read_text.clear()
            st.success("Selection Profile sparad.")


def view_variant_candidates() -> None:
    st.title("Variant Candidates")
    st.caption(
        "Skapar draftade Variant JSON-filer under `data/variant-candidates/`. "
        "Det här promoterar aldrig till canonical `variants/`."
    )
    _render_candidate_source_help()

    scaffold_ids = _scaffold_options()
    if not scaffold_ids:
        st.info("Inga Scaffolds finns att skapa kandidater för.")
        return

    with st.form("variant_candidate_form"):
        scaffold_id = st.selectbox("Scaffold", scaffold_ids)
        variant_id = st.text_input("Variant id (valfritt)")
        brief = st.text_area("Variant-brief", height=120)
        use_llm = st.checkbox("Använd variantModel om OPENAI_API_KEY finns", value=False)
        force = st.checkbox("Skriv över befintlig kandidat med samma id", value=False)
        submitted = st.form_submit_button("Skapa kandidat")

    if submitted:
        try:
            [result] = create_variant_candidate_from_ui(
                scaffold_id=scaffold_id,
                brief=brief,
                variant_id=variant_id.strip() or None,
                use_llm=use_llm,
                force=force,
            )
        except (VariantGenerationError, ValueError, RuntimeError) as exc:
            st.error(f"Kunde inte skapa kandidat: {exc}")
            return

        st.success(f"Skapade `{result.path.relative_to(REPO_ROOT)}`")
        st.write(f"**Source:** `{result.source}`")
        st.write(f"**Model:** `{result.model_used}`")
        if result.source != "real":
            st.warning(
                "Kandidaten kommer från fallback eller okänd källa. "
                "Granska den manuellt före promotion."
            )
        st.json(result.payload)

        existing = asset_graph.load_existing_variants(scaffold_id)
        if existing:
            st.subheader("Likhet mot canonical variants")
            st.dataframe(
                asset_graph.compare_variant_to_existing(result.payload, existing),
                use_container_width=True,
                hide_index=True,
            )
            st.subheader(f"Diff mot `{existing[0].get('id', 'canonical')}`")
            st.dataframe(
                asset_graph.variant_diff_rows(result.payload, existing[0]),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    st.subheader("Befintliga kandidater")
    candidate_rows = asset_graph.list_variant_candidates()
    if not candidate_rows:
        st.info("Inga variantkandidater finns ännu.")
        return

    _warn_non_real_sources(candidate_rows)
    st.dataframe(candidate_rows, use_container_width=True, hide_index=True)
    candidate_options = [
        f"{row['scaffold']}:{row['candidate']}" for row in candidate_rows
    ]
    selected_candidate = st.selectbox(
        "Granska kandidat",
        candidate_options,
        key="variant_candidate_review_select",
    )
    selected_row = next(
        row for row in candidate_rows if f"{row['scaffold']}:{row['candidate']}" == selected_candidate
    )
    candidate_path = REPO_ROOT / selected_row["path"]
    try:
        candidate_payload = asset_graph.read_json(candidate_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.error(f"Kunde inte läsa kandidat: {exc}")
        return

    st.json(candidate_payload, expanded=False)
    existing = asset_graph.load_existing_variants(str(selected_row["scaffold"]))
    if not existing:
        st.info("Det finns ingen canonical Variant att jämföra mot för denna Scaffold.")
        return
    canonical_by_id = {str(variant["id"]): variant for variant in existing if variant.get("id")}
    canonical_id = st.selectbox(
        "Jämför mot canonical Variant",
        sorted(canonical_by_id),
        key="variant_candidate_diff_target",
    )
    diff_rows = asset_graph.variant_diff_rows(
        candidate_payload,
        canonical_by_id[canonical_id],
    )
    st.dataframe(diff_rows, use_container_width=True, hide_index=True)


def view_dossiers() -> None:
    st.title("Dossiers")
    contract, err = loaders.safe_load_policy("dossier-contract.v1.json")
    if err or contract is None:
        st.error(err)
        return

    st.caption(contract.get("purpose", ""))

    st.subheader("Klasser")
    for cls in contract["dossierClasses"]:
        with st.expander(cls["class"].upper()):
            st.write(cls["definition"])
            st.write("**Exempel:** " + ", ".join(cls["examples"]))

    st.subheader("Implementerade Dossiers")
    allowed_classes = asset_graph.dossier_classes(contract)
    items = _list_dossier_dirs(allowed_classes)
    if not items:
        st.info("Inga Dossiers implementerade än.")
        return
    rows = [{"Klass": cls, "id": d.name} for cls, d in items]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.divider()
    layout = contract["dossierDirectoryLayout"]
    st.write(f"**Owner package:** `{layout['ownerPackage']}`")
    st.write(f"**Per dossier path:** `{layout['perDossierPath']}`")
    st.markdown("**Required files (alla klasser):**")
    for f in layout["requiredFilesAllClasses"]:
        st.write(f"- `{f}`")
    st.markdown("**Extra filer per klass:**")
    for cls, files in layout["additionalRequiredFilesByClass"].items():
        st.write(f"- `{cls}`: " + ", ".join(f"`{f}`" for f in files))


def view_dossier_candidates() -> None:
    st.title("Dossier Candidates")
    st.caption(
        "Skapar candidate-only Dossier-mappar under `data/dossier-candidates/`. "
        "Det här promoterar aldrig till canonical Dossier-mappar."
    )
    _render_candidate_source_help()

    st.subheader("Intake från lokal källa")
    st.caption(
        "V1 analyserar bara lokala filer och mappar. URL/web-input är planerat för "
        "V1.5 och fetchas inte här."
    )
    with st.form("dossier_intake_analyze_form"):
        source_path = st.text_input(
            "Lokal source path",
            placeholder="t.ex. data/legacy-dossiers/old-carousel",
        )
        intake_brief = st.text_area(
            "Operator brief för analysen",
            height=120,
            placeholder="Beskriv vilken återanvändbar capability du hoppas hitta.",
        )
        intake_submitted = st.form_submit_button("Analysera källa")

    if intake_submitted:
        try:
            report = analyze_dossier_source_from_ui(
                source_path=source_path.strip(),
                operator_brief=intake_brief,
            )
        except (DossierIntakeError, ValueError, RuntimeError) as exc:
            st.error(f"Kunde inte analysera källa: {exc}")
        else:
            st.session_state["dossier_candidate_intake_report"] = report
            st.session_state["dossier_candidate_intake_brief"] = intake_brief
            st.success("Intake-rapport skapad. Inget har skrivits till disk.")

    intake_report = st.session_state.get("dossier_candidate_intake_report")
    if isinstance(intake_report, dict):
        st.markdown("**Senaste intake report**")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Rekommendation", str(intake_report["recommendedClass"]))
        metric_cols[1].metric("Filer", int(intake_report.get("fileCount") or 0))
        metric_cols[2].metric(
            "Inkluderade",
            len(intake_report.get("includedFiles") or []),
        )
        metric_cols[3].metric(
            "Exkluderade",
            len(intake_report.get("excludedFiles") or []),
        )
        st.write(f"**Suggested id:** `{intake_report.get('suggestedDossierId', '')}`")
        st.write(f"**Capability:** `{intake_report.get('suggestedCapability', '')}`")
        risk_flags = intake_report.get("riskFlags") or []
        if risk_flags:
            st.warning("Riskflaggor: " + ", ".join(f"`{flag}`" for flag in risk_flags))
        operator_questions = intake_report.get("operatorQuestions") or []
        if operator_questions:
            with st.expander("Operatorfrågor"):
                for question in operator_questions:
                    st.write(f"- {question}")
        with st.expander("Intake report JSON"):
            st.json(intake_report, expanded=False)

        if intake_report.get("recommendedClass") == "not-a-dossier":
            st.warning(
                "Rapporten rekommenderar `not-a-dossier`. Skapa ingen kandidat från "
                "denna källa utan att flytta materialet till Project Input/assets."
            )
        else:
            with st.form("dossier_intake_create_form"):
                intake_candidate_id = st.text_input(
                    "Dossier id från analys",
                    value=str(intake_report.get("suggestedDossierId") or ""),
                )
                intake_capability = st.text_input(
                    "Capability från analys",
                    value=str(intake_report.get("suggestedCapability") or ""),
                )
                intake_create_brief = st.text_area(
                    "Capability-brief från analys",
                    value=str(st.session_state.get("dossier_candidate_intake_brief") or ""),
                    height=160,
                )
                intake_use_llm = st.checkbox(
                    "Använd dossierModel om OPENAI_API_KEY finns",
                    value=False,
                    key="dossier_intake_use_llm",
                )
                intake_force = st.checkbox(
                    "Skriv över befintlig kandidat med samma id",
                    value=False,
                    key="dossier_intake_force",
                )
                intake_create = st.form_submit_button("Skapa kandidat från analys")
            if intake_create:
                try:
                    result = create_dossier_candidate_from_ui(
                        brief=intake_create_brief,
                        candidate_id=intake_candidate_id.strip() or None,
                        capability=intake_capability.strip() or None,
                        use_llm=intake_use_llm,
                        force=intake_force,
                        intake_report=intake_report,
                    )
                except (DossierGenerationError, ValueError, RuntimeError) as exc:
                    st.error(f"Kunde inte skapa kandidat från analys: {exc}")
                    return
                st.success(f"Skapade `{result.candidate_dir.relative_to(REPO_ROOT)}`")
                st.write(f"**Source:** `{result.source}`")
                st.write(f"**Model:** `{result.model_used}`")
                st.subheader("manifest.json")
                st.json(result.manifest, expanded=False)
                st.subheader("instructions.md")
                st.code(result.instructions, language="markdown")

    st.divider()
    st.subheader("Brief-only kandidat")
    with st.form("dossier_candidate_form"):
        candidate_id = st.text_input("Dossier id (valfritt)")
        capability = st.text_input("Capability (valfritt)")
        brief = st.text_area("Capability-brief", height=120)
        use_llm = st.checkbox("Använd dossierModel om OPENAI_API_KEY finns", value=False)
        force = st.checkbox("Skriv över befintlig kandidat med samma id", value=False)
        submitted = st.form_submit_button("Skapa Soft Dossier-kandidat")

    if submitted:
        try:
            result = create_dossier_candidate_from_ui(
                brief=brief,
                candidate_id=candidate_id.strip() or None,
                capability=capability.strip() or None,
                use_llm=use_llm,
                force=force,
            )
        except (DossierGenerationError, ValueError, RuntimeError) as exc:
            st.error(f"Kunde inte skapa kandidat: {exc}")
            return

        st.success(f"Skapade `{result.candidate_dir.relative_to(REPO_ROOT)}`")
        st.write(f"**Source:** `{result.source}`")
        st.write(f"**Model:** `{result.model_used}`")
        if result.source != "real":
            st.warning(
                "Kandidaten kommer från fallback eller okänd källa. "
                "Granska den manuellt före promotion."
            )
        st.subheader("manifest.json")
        st.json(result.manifest, expanded=False)
        st.subheader("instructions.md")
        st.code(result.instructions, language="markdown")

    st.divider()
    st.subheader("Befintliga kandidater")
    candidate_nodes = [
        node
        for node in asset_graph.build_graph()["nodes"]
        if node["type"] == "dossier-candidate"
    ]
    if not candidate_nodes:
        st.info("Inga Dossier-kandidater finns ännu.")
        return
    _warn_non_real_sources(candidate_nodes)
    st.dataframe(candidate_nodes, use_container_width=True, hide_index=True)


def view_reference_templates() -> None:
    st.title("Reference Templates")
    st.caption(
        "Externa templates som används som inspirations- och struktur-corpus, inte som "
        "produktens skelett. Sanningskälla: [`embedding-policy.v1.json`]."
    )
    if not REFERENCE_TEMPLATES_DIR.exists():
        st.info(
            "Ingen `data/reference-templates/`-mapp ännu. När du laddar ner Vercel-/egna "
            "templates till den mappen dyker de upp här."
        )
        return
    children = sorted([p.name for p in REFERENCE_TEMPLATES_DIR.iterdir() if p.is_dir()])
    if not children:
        st.info("`data/reference-templates/` är tom.")
        return
    st.write("Kataloger under `data/reference-templates/`:")
    for child in children:
        st.write(f"- `{child}`")


VIEWS = {
    "Kontrollplan": lambda: safe_render(view_control_plane),
    "Scaffolds": lambda: safe_render(view_scaffolds),
    "Selection Profiles": lambda: safe_render(view_selection_profiles),
    "Variants": lambda: safe_render(view_variants),
    "Variant Candidates": lambda: safe_render(view_variant_candidates),
    "Dossiers": lambda: safe_render(view_dossiers),
    "Dossier Candidates": lambda: safe_render(view_dossier_candidates),
    "Reference Templates": lambda: safe_render(view_reference_templates),
}
