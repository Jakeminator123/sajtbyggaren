"""Sajtbyggaren backoffice (Streamlit entry point).

Operator-facing admin tool for editing governance, viewing scaffolds and
dossiers, browsing the LLM flow, and running consistency checks.

This file stays thin. View logic lives in the `backoffice/` package.
ADR 0002 keeps backoffice strictly out of the user runtime.

Run:
    pip install -r requirements.txt
    streamlit run backend.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from backoffice import health, loaders
from backoffice.paths import (
    DECISIONS_DIR,
    POLICIES_DIR,
    REFERENS_DIR,
    REPO_ROOT,
    RULES_DIR,
    SCHEMAS_DIR,
    TESTS_DIR,
)


st.set_page_config(
    page_title="Sajtbyggaren Backoffice",
    page_icon=":wrench:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----- helpers ---------------------------------------------------------------


def _check_badge(ok: bool) -> str:
    return "OK" if ok else "FEL"


def _render_check(result: health.CheckResult) -> None:
    if result.ok:
        st.success(f"{result.name}: OK")
    else:
        st.error(f"{result.name}: FEL (exit {result.exit_code})")
    if result.output:
        with st.expander("Visa output"):
            st.code(result.output, language="text")


def _hard_reset_caches() -> None:
    loaders.load_json.clear()
    loaders.read_text.clear()


# ----- views -----------------------------------------------------------------


def view_overview() -> None:
    st.title("Översikt")
    st.caption(
        "Sajtbyggaren styrs av JSON-policies under `governance/policies/`. "
        "Detta är operatörens redigeringsyta. Användarens runtime ligger inte här."
    )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Policies", len(loaders.list_policies()))
    col2.metric("Schemas", len(loaders.list_schemas()))
    col3.metric("Regler", len(loaders.list_rules()))
    col4.metric("ADR", len(loaders.list_decisions()))
    col5.metric("Cursor-speglar", len(list((REPO_ROOT / ".cursor" / "rules").glob("*.mdc"))))

    st.divider()
    st.subheader("Kvalitetsmål och gates")
    pq = loaders.load_policy("page-quality-traits.v1.json")
    qt = pq["qualityTarget"]
    a, b, c, d = st.columns(4)
    a.metric("Target", qt["targetScore"])
    b.metric("Gate", qt["gateScore"])
    c.metric("Block under", qt["blockBelow"])
    d.metric("Skala", qt["scoreScale"])
    st.caption(qt.get("meaning", ""))

    st.divider()
    st.subheader("Snabbåtgärder")
    a1, a2, a3 = st.columns(3)
    if a1.button("Kör governance-validering", use_container_width=True):
        _render_check(health.run_governance_validate())
    if a2.button("Verifiera rules-sync", use_container_width=True):
        _render_check(health.run_rules_sync_check())
    if a3.button("Term-coverage (strict)", use_container_width=True):
        _render_check(health.run_term_coverage(strict=True))


def view_system_health() -> None:
    st.title("System Health")
    st.caption(
        "Live status från de tre kontrollskripten plus pytest-svit för "
        "governance. Klicka 'Kör allt' för en helkörning."
    )

    if st.button("Kör allt", type="primary"):
        _hard_reset_caches()
        with st.spinner("Kör skript..."):
            r1 = health.run_governance_validate()
            r2 = health.run_rules_sync_check()
            r3 = health.run_term_coverage(strict=True)
            r4 = health.run_pytest_governance()
        st.session_state["health_results"] = [r1, r2, r3, r4]

    results: list[health.CheckResult] = st.session_state.get("health_results", [])
    if not results:
        st.info("Inga körningar än. Tryck 'Kör allt' för att börja.")
        return

    cols = st.columns(len(results))
    for col, result in zip(cols, results):
        col.metric(result.name, _check_badge(result.ok))

    st.divider()
    for result in results:
        _render_check(result)

    st.divider()
    if any(not r.ok for r in results):
        if st.button("Försök fixa rules-sync (kör spegel-skript)"):
            res = health.run_rules_sync_apply()
            _render_check(res)


def view_policies() -> None:
    st.title("Policies")
    policies = loaders.list_policies()
    if not policies:
        st.info("Inga policies hittades.")
        return

    names = [p.name for p in policies]
    selected = st.selectbox("Välj policy", names)
    selected_path = POLICIES_DIR / selected

    try:
        data = loaders.load_policy(selected)
    except json.JSONDecodeError as exc:
        st.error(f"Ogiltig JSON: {exc}")
        return

    a, b, c, d = st.columns(4)
    a.metric("policyId", data.get("policyId", "okänd"))
    b.metric("version", data.get("version", "okänd"))
    c.metric("status", data.get("status", "okänd"))
    if "$schema" in data:
        schema_name = Path(data["$schema"]).name
        d.metric("schema", schema_name)

    if data.get("purpose"):
        st.info(data["purpose"])

    tab_view, tab_edit = st.tabs(["Läs", "Redigera"])

    with tab_view:
        st.json(data, expanded=False)

    with tab_edit:
        st.warning(
            "Att redigera en policy kan bryta cross-policy-tester. "
            "Kör System Health efter spara."
        )
        text = selected_path.read_text(encoding="utf-8")
        new_text = st.text_area("JSON", value=text, height=600, key=f"edit-{selected}")
        if st.button("Spara", key=f"save-{selected}"):
            try:
                json.loads(new_text)
            except json.JSONDecodeError as exc:
                st.error(f"Ogiltig JSON, sparar inte: {exc}")
                return
            selected_path.write_text(new_text, encoding="utf-8")
            _hard_reset_caches()
            st.success("Sparat. Kör validering i System Health.")


def view_naming_dictionary() -> None:
    st.title("Naming Dictionary")
    nd = loaders.load_policy("naming-dictionary.v1.json")
    st.caption(nd.get("purpose", ""))

    terms = nd.get("terms", [])
    a, b = st.columns(2)
    a.metric("Termer", len(terms))
    b.metric("Globally forbidden", len(nd.get("globallyForbidden", [])))

    query = st.text_input("Sök på term, definition eller ägar-paket", "").strip().lower()

    def _matches(term: dict) -> bool:
        if not query:
            return True
        haystack = " ".join(
            [
                term.get("id", ""),
                term.get("canonical", ""),
                term.get("definition", ""),
                term.get("ownerPackage", ""),
                " ".join(term.get("aliasesAllowed") or []),
                " ".join(term.get("aliasesForbidden") or []),
            ]
        ).lower()
        return query in haystack

    filtered = [t for t in terms if _matches(t)]
    st.write(f"Visar {len(filtered)} av {len(terms)} termer.")

    rows = [
        {
            "Kanonisk": t.get("canonical"),
            "id": t.get("id"),
            "Ägar-paket": t.get("ownerPackage"),
            "Tillåtna alias": ", ".join(t.get("aliasesAllowed") or []),
            "Förbjudna alias": ", ".join(t.get("aliasesForbidden") or []),
        }
        for t in filtered
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Visa fullständiga definitioner"):
        for term in filtered:
            st.markdown(
                f"**{term['canonical']}** (`{term['id']}`)  "
                f"\n*{term['ownerPackage']}*  "
                f"\n{term['definition']}"
            )

    with st.expander("Globally forbidden"):
        st.write(", ".join(nd.get("globallyForbidden", [])) or "(inga)")


def view_cross_policy() -> None:
    st.title("Cross-Policy Status")
    st.caption(
        "Realtidsstatus över konsistens mellan policies. Det här är vad "
        "pytest -m governance kontrollerar; samma logik visas här direkt."
    )

    nd = loaders.load_policy("naming-dictionary.v1.json")
    rb = loaders.load_policy("repo-boundaries.v1.json")
    sc = loaders.load_policy("scaffold-contract.v1.json")
    ss = loaders.load_policy("scaffold-selection.v1.json")
    pq = loaders.load_policy("page-quality-traits.v1.json")
    pr = loaders.load_policy("preview-runtime-policy.v1.json")
    flow = loaders.load_policy("llm-flow-concepts.v1.json")

    findings: list[tuple[bool, str]] = []

    # Default scaffold valid
    default_scaffold = ss["fallback"]["defaultScaffold"]
    registry_ids = {s["id"] for s in sc["primaryScaffoldRegistry"]}
    findings.append(
        (default_scaffold in registry_ids, f"defaultScaffold '{default_scaffold}' finns i registry")
    )

    # Quality target ordering
    qt = pq["qualityTarget"]
    findings.append(
        (
            qt["blockBelow"] <= qt["gateScore"] <= qt["targetScore"],
            f"qualityTarget thresholds: {qt['blockBelow']} <= {qt['gateScore']} <= {qt['targetScore']}",
        )
    )

    # Weights total
    total_weight = sum(t["weight"] for t in pq["traits"])
    findings.append(
        (
            total_weight == pq["scoring"]["weightsTotal"],
            f"trait-vikter summerar till {total_weight} (förväntat {pq['scoring']['weightsTotal']})",
        )
    )

    # canonicalFlow vs phase ids
    phase_ids = [p["id"] for p in flow["phases"]]
    findings.append(
        (
            set(phase_ids) == set(flow["canonicalFlow"]),
            "canonicalFlow matchar phase ids",
        )
    )

    # Default preview runtime exists
    pr_kinds = {r["kind"] for r in pr["runtimes"]}
    findings.append(
        (
            pr["default"] in pr_kinds,
            f"default Preview Runtime '{pr['default']}' finns i runtimes",
        )
    )

    # Canonicals unique
    canonicals = [t["canonical"] for t in nd["terms"]]
    findings.append(
        (
            len(canonicals) == len(set(canonicals)),
            f"alla {len(canonicals)} kanoniska termer är unika",
        )
    )

    # ownerPackages mappar mot repo-boundaries
    boundary_paths = {o["path"].rstrip("/") for o in rb["ownership"]} | {"backend.py"}
    unknown_owners = [
        t["canonical"]
        for t in nd["terms"]
        if not any(t["ownerPackage"].startswith(p) for p in boundary_paths)
    ]
    findings.append(
        (
            not unknown_owners,
            f"alla termer har ownerPackage i repo-boundaries"
            + (f" (avvikande: {unknown_owners})" if unknown_owners else ""),
        )
    )

    ok_count = sum(1 for ok, _ in findings if ok)
    st.metric("Status", f"{ok_count}/{len(findings)}")

    for ok, msg in findings:
        if ok:
            st.success(msg)
        else:
            st.error(msg)


def view_llm_flow() -> None:
    st.title("LLM-flöde")
    flow = loaders.load_policy("llm-flow-concepts.v1.json")

    st.caption(f"northStar: {flow.get('northStar', '')}")
    st.subheader("Kanonisk ordning")
    st.write(" -> ".join(flow.get("canonicalFlow", [])))

    phase_groups = {
        "Fas 1 - Brief & Policy Resolution": [
            "raw_prompt",
            "site_brief",
            "intent_resolution",
            "policy_resolution",
        ],
        "Fas 2 - Orchestration": ["scaffold_resolution", "generation_package"],
        "Fas 3 - Codegen, Finalize, Quality Gate": [
            "codegen",
            "mechanical_autofix",
            "llm_repair",
            "preview_runtime",
            "quality_evaluation",
            "promotion",
        ],
    }

    phases = sorted(flow.get("phases", []), key=lambda p: p.get("order", 0))

    tab_phases, tab_diagrams = st.tabs(["Faser", "Diagram"])

    with tab_phases:
        for label, ids in phase_groups.items():
            st.markdown(f"### {label}")
            for phase in [p for p in phases if p["id"] in ids]:
                with st.expander(
                    f"{phase['order']:>3} - {phase['canonicalName']} ({phase['id']})"
                ):
                    st.write(phase.get("purpose", ""))
                    cols = st.columns(2)
                    cols[0].markdown("**Input**")
                    for art in phase.get("inputArtifacts", []):
                        cols[0].write(f"- {art}")
                    cols[1].markdown("**Output**")
                    for art in phase.get("outputArtifacts", []):
                        cols[1].write(f"- {art}")
                    st.markdown(f"**Owner package:** `{phase.get('ownerPackage')}`")
                    st.markdown(
                        f"**LLM-anrop tillåtna:** `{phase.get('allowedToCallLLM', False)}`"
                    )
                    if phase.get("mustNotDo"):
                        st.markdown("**Must not do:**")
                        for item in phase["mustNotDo"]:
                            st.write(f"- {item}")

    with tab_diagrams:
        st.caption(
            "Bilderna kommer från `referens/llm-flode/`. Mermaid-källan finns i "
            "`docs/architecture/llm-flow.md` och `docs/architecture/scaffold-dossier-model.md`."
        )
        diagrams = [
            ("Init - end to end", REFERENS_DIR / "llm-flode" / "diagram-init-end-to-end.png"),
            ("Init - Fas 1 - översikt", REFERENS_DIR / "llm-flode" / "init" / "fas1-overview.png"),
            (
                "Init - Fas 2 - orchestration",
                REFERENS_DIR / "llm-flode" / "init" / "fas2-orchestration.png",
            ),
            (
                "Init - Fas 3 - codegen + quality",
                REFERENS_DIR / "llm-flode" / "init" / "fas3-codegen-quality.png",
            ),
            (
                "Init - Fas 3 - detaljerat codegen",
                REFERENS_DIR / "llm-flode" / "init" / "fas3-detaljerat-codegen.png",
            ),
            (
                "Init med shadcn-budget",
                REFERENS_DIR / "llm-flode" / "init" / "init-med-shadcn-budget.png",
            ),
            (
                "Dossier Selection",
                REFERENS_DIR / "llm-flode" / "diagram-dossier-selection.png",
            ),
            (
                "Follow-up flow (kommande fas)",
                REFERENS_DIR / "llm-flode" / "follow-up" / "follow-up-flow.png",
            ),
        ]
        for title, path in diagrams:
            if path.exists():
                with st.expander(title):
                    st.image(str(path), use_container_width=True)


def view_quality_traits() -> None:
    st.title("Page Quality Traits")
    pq = loaders.load_policy("page-quality-traits.v1.json")

    qt = pq["qualityTarget"]
    cols = st.columns(4)
    cols[0].metric("Target", qt["targetScore"])
    cols[1].metric("Gate", qt["gateScore"])
    cols[2].metric("Block under", qt["blockBelow"])
    cols[3].metric("Skala", qt["scoreScale"])
    st.caption(qt.get("meaning", ""))

    total_weight = sum(t["weight"] for t in pq["traits"])
    st.write(
        f"Vikter summerar till {total_weight} av {pq['scoring']['weightsTotal']} förväntade."
    )

    for trait in pq.get("traits", []):
        with st.expander(f"{trait['name']} (vikt {trait['weight']})"):
            st.write(trait["definition"])
            cols = st.columns(2)
            cols[0].markdown("**Positiva signaler**")
            for s in trait.get("positiveSignals", []):
                cols[0].write(f"- {s}")
            cols[1].markdown("**Negativa signaler**")
            for s in trait.get("negativeSignals", []):
                cols[1].write(f"- {s}")
            st.markdown("**Check methods:** " + ", ".join(trait.get("checkMethods", [])))
            st.markdown(f"**Owner package:** `{trait.get('ownerPackage')}`")


def view_decisions() -> None:
    st.title("Architecture Decisions (ADR)")
    decisions = loaders.list_decisions()
    if not decisions:
        st.info("Inga ADR:er hittades.")
        return
    names = [p.name for p in decisions]
    selected = st.selectbox("Välj ADR", names)
    text = loaders.text_of(DECISIONS_DIR / selected)
    st.markdown(text)


def view_rules() -> None:
    st.title("Rules")
    st.caption(
        "Källfiler i `governance/rules/`. Spegeln i `.cursor/rules/` "
        "uppdateras med `python scripts/rules_sync.py`."
    )
    rules = loaders.list_rules()
    names = [p.name for p in rules]
    selected = st.selectbox("Välj regel", names)
    text = loaders.text_of(RULES_DIR / selected)
    st.markdown(text)


def view_scaffolds_placeholder() -> None:
    st.title("Scaffolds")
    sc = loaders.load_policy("scaffold-contract.v1.json")
    st.info(
        "Scaffold-runtime är inte implementerad än. När fas 2 byggs läggs "
        "CRUD-yta här. Tills dess visar denna sida endast registret från "
        "`scaffold-contract.v1.json`."
    )
    st.subheader("Primary Scaffold Registry")
    rows = [
        {"id": s["id"], "label": s["label"], "rationale": s["rationale"]}
        for s in sc["primaryScaffoldRegistry"]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("Scaffold-filer per Scaffold (kontrakt)")
    layout = sc["scaffoldDirectoryLayout"]
    st.write(f"**Owner package:** `{layout['ownerPackage']}`")
    st.write(f"**Per scaffold path:** `{layout['perScaffoldPath']}`")
    cols = st.columns(2)
    cols[0].markdown("**Required files**")
    for f in layout["requiredFiles"]:
        cols[0].write(f"- `{f}`")
    cols[1].markdown("**Optional files**")
    for f in layout.get("optionalFiles", []):
        cols[1].write(f"- `{f}`")


def view_dossiers_placeholder() -> None:
    st.title("Dossiers")
    dc = loaders.load_policy("dossier-contract.v1.json")
    st.info(
        "Dossier-runtime är inte implementerad än. När fas 2 byggs läggs "
        "CRUD-yta här. Tills dess visar denna sida endast kontraktet från "
        "`dossier-contract.v1.json`."
    )
    st.subheader("Dossier-klasser")
    for cls in dc["dossierClasses"]:
        with st.expander(cls["class"].upper()):
            st.write(cls["definition"])
            st.write("**Exempel:** " + ", ".join(cls["examples"]))

    st.subheader("Filer per Dossier")
    layout = dc["dossierDirectoryLayout"]
    st.write(f"**Owner package:** `{layout['ownerPackage']}`")
    st.write(f"**Per dossier path:** `{layout['perDossierPath']}`")
    st.markdown("**Required files (alla klasser):**")
    for f in layout["requiredFilesAllClasses"]:
        st.write(f"- `{f}`")
    st.markdown("**Extra filer per klass:**")
    for cls, files in layout["additionalRequiredFilesByClass"].items():
        st.write(f"- `{cls}`: " + ", ".join(f"`{f}`" for f in files))


def view_evals_placeholder() -> None:
    st.title("Evals och telemetri")
    st.info(
        "Evals byggs i `tests/evals/`. Backoffice får körnings- och "
        "historikyta här när första prompt-batchen finns."
    )
    eval_files = list((TESTS_DIR / "evals").rglob("*"))
    eval_files = [f for f in eval_files if f.is_file() and f.name != ".gitkeep"]
    st.metric("Eval-filer", len(eval_files))
    st.caption(
        "Första evals är inte sajtmaskin-baseline-jämförelser (ADR 0004 är "
        "öppet) utan regression-tester på governance-konsistens. Se "
        "`tests/test_cross_policy_consistency.py`."
    )


# ----- navigation ------------------------------------------------------------


SECTIONS = {
    "Status": {
        "Översikt": view_overview,
        "System Health": view_system_health,
        "Cross-Policy Status": view_cross_policy,
    },
    "Governance": {
        "Policies": view_policies,
        "Naming Dictionary": view_naming_dictionary,
        "Page Quality Traits": view_quality_traits,
        "Rules": view_rules,
        "ADR": view_decisions,
    },
    "LLM-flöde": {
        "LLM-flöde och fasansvar": view_llm_flow,
    },
    "Runtime (kommer)": {
        "Scaffolds": view_scaffolds_placeholder,
        "Dossiers": view_dossiers_placeholder,
        "Evals och telemetri": view_evals_placeholder,
    },
}


def main() -> None:
    st.sidebar.title("Sajtbyggaren")
    st.sidebar.caption("Backoffice - operatörens redigeringsyta")

    for section, pages in SECTIONS.items():
        st.sidebar.markdown(f"**{section}**")
        for page_name in pages:
            if st.sidebar.button(page_name, key=f"nav-{page_name}", use_container_width=True):
                st.session_state["current_view"] = page_name
        st.sidebar.markdown("")

    st.sidebar.divider()
    st.sidebar.caption(
        "**Källa:** `governance/`\n\n"
        "**Inte runtime.** Slutanvändarens flöde ligger i `apps/` + `packages/`."
    )

    if st.sidebar.button("Rensa cache", use_container_width=True):
        _hard_reset_caches()
        st.sidebar.success("Cache rensad.")

    current = st.session_state.get("current_view", "Översikt")

    for pages in SECTIONS.values():
        if current in pages:
            pages[current]()
            return

    view_overview()


if __name__ == "__main__":
    main()
