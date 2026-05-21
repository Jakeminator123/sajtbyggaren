"""Building Blocks-block: Scaffolds, Variants, Dossiers, Reference Templates."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

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
):
    """Generate a soft Dossier candidate from Backoffice without touching canonical files."""
    return generate_dossier_candidate(
        brief=brief,
        candidate_id=candidate_id,
        capability=capability,
        output_dir=DOSSIER_CANDIDATES_DIR,
        force=force,
        use_llm=use_llm,
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

    if summary["unknownCategories"]:
        st.warning(
            f"{summary['unknownCategories']} policyrad(er) pekar mot en "
            "wizardCategoryId som inte finns i Discovery Taxonomy. Justera "
            "policy eller taxonomy innan SNI används som signal."
        )

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
        "visar matchad prefix, kandidat-kategori och hur Discovery Taxonomy "
        "skulle välja scaffold/variant/starter när kategorin når resolvern."
    )
    sni_input = st.text_input(
        "SNI-kod",
        key="sni_lookup_input",
        placeholder="t.ex. 56, 56.10, 56100 eller 691",
    )
    if sni_input.strip():
        lookup = sni_diagnostics.lookup_row(sni_input)
        if lookup["matchedLevel"] == "unknown":
            st.info(
                "Ingen policymappning matchade. SNI är branschsignal — "
                "okänd kod är ett tyst no-op, inte ett fel."
            )
        else:
            st.json(lookup, expanded=False)
            if not lookup["categoryKnown"]:
                st.warning(
                    "Mappningen pekar mot en wizardCategoryId som saknas i "
                    "Discovery Taxonomy. Inga scaffold/variant/starter visas."
                )


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

    scaffold_ids = _scaffold_options()
    if not scaffold_ids:
        st.info("Inga Scaffolds finns att skapa kandidater för.")
        return

    with st.form("variant_candidate_form"):
        scaffold_id = st.selectbox("Scaffold", scaffold_ids)
        variant_id = st.text_input("Variant id (valfritt)")
        brief = st.text_area("Variant-brief", height=120)
        use_llm = st.checkbox("Använd variantModel om OPENAI_API_KEY finns", value=True)
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
        "Skapar candidate-only Soft Dossier-mappar under `data/dossier-candidates/`. "
        "Det här promoterar aldrig till canonical Dossier-mappar."
    )

    with st.form("dossier_candidate_form"):
        candidate_id = st.text_input("Dossier id (valfritt)")
        capability = st.text_input("Capability (valfritt)")
        brief = st.text_area("Capability-brief", height=120)
        use_llm = st.checkbox("Använd dossierModel om OPENAI_API_KEY finns", value=True)
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
