"""Building Blocks: Kontrollplan-vyn (read-only control plane).

Sammanhållen kontrollyta som väver ihop asset graph, Discovery mapping,
wizard->generation-diagnostik, SNI->kategori-mappning, branschtäckning och
konsekvensvyn. Utbruten ur den tidigare building_blocks-god-modulen utan
beteendeändring; samma vy-labels och samma render-ordning.
"""
from __future__ import annotations

import streamlit as st

from scripts.generate_dossier_candidate import DossierGenerationError
from scripts.generate_variant_candidate import VariantGenerationError

from ... import (
    asset_graph,
    discovery_control,
    discovery_wizard_diagnostics,
    impact,
    industry_coverage,
    loaders,
    sni_diagnostics,
)
from ...paths import REPO_ROOT
from . import create_dossier_candidate_from_ui, create_variant_candidate_from_ui


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
        st.dataframe(relation_rows, width="stretch", hide_index=True)
    else:
        st.caption("Inga direkta relationer hittades.")

    if result["affectedNodes"]:
        with st.expander("Påverkade noder"):
            st.dataframe(result["affectedNodes"], width="stretch", hide_index=True)
    if result["affectedPaths"]:
        with st.expander("Berörda filer"):
            for path in result["affectedPaths"]:
                st.write(f"- `{path}`")


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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

    st.dataframe(mapping_rows, width="stretch", hide_index=True)

    with st.expander("Discovery relationer i asset graph"):
        st.dataframe(discovery_graph["nodes"], width="stretch", hide_index=True)
        st.dataframe(discovery_graph["edges"], width="stretch", hide_index=True)

    with st.expander("Discovery gap/orphan"):
        gap_rows = discovery_control.discovery_gap_rows(policy)
        if gap_rows:
            st.dataframe(gap_rows, width="stretch", hide_index=True)
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
            st.dataframe(findings, width="stretch", hide_index=True)


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
        st.dataframe(filtered_rows, width="stretch", hide_index=True)
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
        st.dataframe(filtered_rows, width="stretch", hide_index=True)
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
        st.dataframe(filtered_rows, width="stretch", hide_index=True)
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
        st.dataframe(filtered_rows, width="stretch", hide_index=True)
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

    st.dataframe(filtered_rows, width="stretch", hide_index=True)

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
            st.dataframe(coverage_gaps, width="stretch", hide_index=True)
        else:
            st.success("Alla Discovery Taxonomy-kategorier har minst en SNI-mappning.")

    category_options = ["Alla"] + sorted({str(row["wizardCategoryId"]) for row in rows})
    selected_category = st.selectbox(
        "wizardCategoryId",
        category_options,
        key="sni_mapping_category_filter",
    )
    filtered_rows = sni_diagnostics.filter_rows_by_category(rows, selected_category)
    st.dataframe(filtered_rows, width="stretch", hide_index=True)

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
                st.dataframe(parent_chain, width="stretch", hide_index=True)
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
        st.dataframe(filtered_summary, width="stretch", hide_index=True)

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
        st.dataframe(filtered_rows, width="stretch", hide_index=True)

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
        st.dataframe(sni_rows, width="stretch", hide_index=True)
        missing_sni = [row for row in sni_rows if int(row["sniMappingCount"]) == 0]
        with st.expander(f"Kategorier utan SNI-mappning ({len(missing_sni)})"):
            if missing_sni:
                st.dataframe(missing_sni, width="stretch", hide_index=True)
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
        st.dataframe(filtered_actions, width="stretch", hide_index=True)
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
        st.dataframe(findings, width="stretch", hide_index=True)

    st.subheader("Nodes")
    st.dataframe(graph["nodes"], width="stretch", hide_index=True)

    st.subheader("Relationer")
    st.dataframe(graph["edges"], width="stretch", hide_index=True)

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
