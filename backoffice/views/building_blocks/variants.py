"""Building Blocks: Variants, Selection Profiles och Variant Candidates."""

from __future__ import annotations

import json

import streamlit as st

from scripts.generate_variant_candidate import VariantGenerationError

from ... import asset_graph, loaders, selection_profiles
from ...paths import REPO_ROOT
from . import (
    _list_scaffold_dirs,
    _render_candidate_source_help,
    _scaffold_options,
    _warn_non_real_sources,
    create_variant_candidate_from_ui,
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
    st.dataframe(rows, width="stretch", hide_index=True)


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
    st.dataframe(summaries, width="stretch", hide_index=True)

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
                width="stretch",
                hide_index=True,
            )
            st.subheader(f"Diff mot `{existing[0].get('id', 'canonical')}`")
            st.dataframe(
                asset_graph.variant_diff_rows(result.payload, existing[0]),
                width="stretch",
                hide_index=True,
            )

    st.divider()
    st.subheader("Befintliga kandidater")
    candidate_rows = asset_graph.list_variant_candidates()
    if not candidate_rows:
        st.info("Inga variantkandidater finns ännu.")
        return

    _warn_non_real_sources(candidate_rows)
    st.dataframe(candidate_rows, width="stretch", hide_index=True)
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
    st.dataframe(diff_rows, width="stretch", hide_index=True)
