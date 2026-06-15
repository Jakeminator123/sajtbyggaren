"""Building Blocks: Dossiers och Dossier Candidates."""

from __future__ import annotations

import streamlit as st

from scripts.dossier_candidate_intake import DossierIntakeError
from scripts.generate_dossier_candidate import DossierGenerationError

from ... import asset_graph, loaders
from ...paths import REPO_ROOT
from . import (
    _list_dossier_dirs,
    _render_candidate_source_help,
    _warn_non_real_sources,
    analyze_dossier_source_from_ui,
    create_dossier_candidate_from_ui,
    review_dossier_intake_from_ui,
)


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
    st.dataframe(rows, width="stretch", hide_index=True)

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
            st.session_state["dossier_candidate_intake_source_path"] = source_path.strip()
            st.session_state.pop("dossier_candidate_intake_review", None)
            st.success("Intake-rapport skapad. Inget har skrivits till disk.")

    intake_report = st.session_state.get("dossier_candidate_intake_report")
    if isinstance(intake_report, dict):
        st.markdown("**senaste intake report**")
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

        st.markdown("**LLM-review**")
        st.caption(
            "Kör separat review med säker evidens. Utan OPENAI_API_KEY används deterministic fallback."
        )
        with st.form("dossier_intake_review_form"):
            review_use_llm = st.checkbox(
                "Använd dossierModel om OPENAI_API_KEY finns",
                value=False,
                key="dossier_intake_review_use_llm",
            )
            review_submitted = st.form_submit_button("Resonera med dossierModel")
        if review_submitted:
            try:
                review = review_dossier_intake_from_ui(
                    operator_brief=str(
                        st.session_state.get("dossier_candidate_intake_brief") or ""
                    ),
                    intake_report=intake_report,
                    source_path=str(
                        st.session_state.get("dossier_candidate_intake_source_path")
                        or intake_report.get("sourcePath")
                        or ""
                    ),
                    use_llm=review_use_llm,
                )
            except (DossierIntakeError, ValueError, RuntimeError) as exc:
                st.error(f"Kunde inte resonera med dossierModel: {exc}")
            else:
                st.session_state["dossier_candidate_intake_review"] = review
                st.success(
                    "Review klar. "
                    f"Source: `{review.get('source')}`, model: `{review.get('modelUsed')}`."
                )

        intake_review = st.session_state.get("dossier_candidate_intake_review")
        if isinstance(intake_review, dict):
            review_cols = st.columns(4)
            review_cols[0].metric("Decision", str(intake_review.get("decision") or ""))
            review_cols[1].metric(
                "Rekommendation",
                str(intake_review.get("recommendedClass") or ""),
            )
            review_cols[2].metric(
                "Dossier id",
                str(intake_review.get("suggestedDossierId") or ""),
            )
            review_cols[3].metric(
                "Capability",
                str(intake_review.get("suggestedCapability") or ""),
            )
            if intake_review.get("summary"):
                st.write(str(intake_review["summary"]))
            for title, key in (
                ("Föreslaget innehåll", "proposedContents"),
                ("Risker", "risks"),
                ("Operatorfrågor", "operatorQuestions"),
                ("Testplan", "testPlan"),
            ):
                values = list(intake_review.get(key) or [])
                if values:
                    with st.expander(title):
                        for value in values:
                            st.write(f"- {value}")
            if intake_review.get("promotionBlockedReason"):
                st.warning(str(intake_review["promotionBlockedReason"]))
            with st.expander("Review JSON"):
                st.json(intake_review, expanded=False)

        if intake_report.get("recommendedClass") == "not-a-dossier":
            st.warning(
                "Rapporten rekommenderar `not-a-dossier`. Skapa ingen kandidat från "
                "denna källa utan att flytta materialet till Project Input/assets."
            )
        else:
            review_defaults = (
                st.session_state.get("dossier_candidate_intake_review")
                if isinstance(st.session_state.get("dossier_candidate_intake_review"), dict)
                else {}
            )
            with st.form("dossier_intake_create_form"):
                intake_candidate_id = st.text_input(
                    "Dossier id från analys",
                    value=str(
                        review_defaults.get("suggestedDossierId")
                        or intake_report.get("suggestedDossierId")
                        or ""
                    ),
                )
                intake_capability = st.text_input(
                    "Capability från analys",
                    value=str(
                        review_defaults.get("suggestedCapability")
                        or intake_report.get("suggestedCapability")
                        or ""
                    ),
                )
                intake_create_brief = st.text_area(
                    "Capability-brief från analys",
                    value=str(
                        review_defaults.get("summary")
                        or st.session_state.get("dossier_candidate_intake_brief")
                        or ""
                    ),
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
                        intake_report={
                            **intake_report,
                            **(
                                {
                                    "recommendedClass": review_defaults.get("recommendedClass"),
                                    "suggestedDossierId": review_defaults.get("suggestedDossierId"),
                                    "suggestedCapability": review_defaults.get("suggestedCapability"),
                                }
                                if review_defaults
                                else {}
                            ),
                        },
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
    st.dataframe(candidate_nodes, width="stretch", hide_index=True)
