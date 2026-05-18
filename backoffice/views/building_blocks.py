"""Building Blocks-block: Scaffolds, Variants, Dossiers, Reference Templates."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from scripts.generate_variant_candidate import (
    VariantGenerationError,
    generate_variant_candidates,
)

from .. import asset_graph, impact, loaders, selection_profiles
from ..paths import REPO_ROOT
from ._helpers import safe_render

SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"
REFERENCE_TEMPLATES_DIR = REPO_ROOT / "data" / "reference-templates"
VARIANT_CANDIDATES_DIR = REPO_ROOT / "data" / "variant-candidates"
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


def view_control_plane() -> None:
    st.title("Kontrollplan")
    st.caption(
        "Read-only översikt över Starters, Scaffolds, Variants, Dossiers, "
        "modellroller och kandidatfiler. Inga destruktiva åtgärder finns här."
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
    "Reference Templates": lambda: safe_render(view_reference_templates),
}
