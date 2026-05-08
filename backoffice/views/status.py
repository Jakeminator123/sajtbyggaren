"""Status-block: Översikt, System Health, Cross-Policy Status."""

from __future__ import annotations

import os

import streamlit as st

from .. import health, loaders
from ..paths import REPO_ROOT
from ._helpers import render_check, safe_render


def _hard_reset_caches() -> None:
    loaders.load_json.clear()
    loaders.read_text.clear()


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
    pq, err = loaders.safe_load_policy("page-quality-traits.v1.json")
    if err or pq is None:
        st.warning(err or "page-quality-traits saknas")
    else:
        qt = pq.get("qualityTarget", {})
        a, b, c, d = st.columns(4)
        a.metric("Target", qt.get("targetScore"))
        b.metric("Gate", qt.get("gateScore"))
        c.metric("Block under", qt.get("blockBelow"))
        d.metric("Skala", qt.get("scoreScale"))
        st.caption(qt.get("meaning", ""))

    st.divider()
    st.subheader("Snabbåtgärder")
    a1, a2, a3 = st.columns(3)
    if a1.button("Kör governance-validering", use_container_width=True, key="ov_validate"):
        st.session_state["overview_check"] = health.run_governance_validate()
    if a2.button("Verifiera rules-sync", use_container_width=True, key="ov_sync"):
        st.session_state["overview_check"] = health.run_rules_sync_check()
    if a3.button("Term-coverage (strict)", use_container_width=True, key="ov_terms"):
        st.session_state["overview_check"] = health.run_term_coverage(strict=True)

    if "overview_check" in st.session_state:
        render_check(st.session_state["overview_check"])


def view_system_health() -> None:
    st.title("System Health")
    st.caption(
        "Live status från de tre kontrollskripten plus pytest-svit för "
        "governance. Plus en API-nyckel-kontroll för LLM-anrop."
    )

    if st.button("Kör allt", type="primary", key="sh_run_all"):
        _hard_reset_caches()
        with st.spinner("Kör skript..."):
            st.session_state["health_results"] = [
                health.run_governance_validate(),
                health.run_rules_sync_check(),
                health.run_term_coverage(strict=True),
                health.run_pytest_governance(),
            ]

    results: list[health.CheckResult] = st.session_state.get("health_results", [])
    if not results:
        st.info("Inga körningar än. Tryck 'Kör allt' för att börja.")
    else:
        cols = st.columns(len(results))
        for col, result in zip(cols, results, strict=True):
            col.metric(result.name, "OK" if result.ok else "FEL")
        st.divider()
        for result in results:
            render_check(result)
        st.divider()
        if any(not r.ok for r in results):
            if st.button("Försök fixa rules-sync (kör spegel-skript)", key="sh_apply_sync"):
                render_check(health.run_rules_sync_apply())

    st.divider()
    st.subheader("API-nycklar")
    openai_set = bool(os.environ.get("OPENAI_API_KEY"))
    anthropic_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    a, b = st.columns(2)
    a.metric("OPENAI_API_KEY", "satt" if openai_set else "saknas")
    b.metric("ANTHROPIC_API_KEY", "satt" if anthropic_set else "saknas")
    st.caption(
        "Ingen nyckel echo-as. Saknad nyckel innebär att Playground och dev_generate.py "
        "faller tillbaka på mock-svar."
    )


def view_cross_policy() -> None:
    st.title("Cross-Policy Status")
    st.caption(
        "Realtidsstatus över konsistens mellan policies. Det här är vad "
        "pytest -m governance kontrollerar; samma logik visas här direkt."
    )

    needed = [
        "naming-dictionary.v1.json",
        "repo-boundaries.v1.json",
        "scaffold-contract.v1.json",
        "scaffold-selection.v1.json",
        "page-quality-traits.v1.json",
        "preview-runtime-policy.v1.json",
        "llm-flow-concepts.v1.json",
    ]
    bundle = {}
    missing = []
    for name in needed:
        p, err = loaders.safe_load_policy(name)
        if err or p is None:
            missing.append(f"{name}: {err}")
        else:
            bundle[name] = p
    if missing:
        for m in missing:
            st.error(m)
        return

    findings: list[tuple[bool, str]] = []

    nd = bundle["naming-dictionary.v1.json"]
    rb = bundle["repo-boundaries.v1.json"]
    sc = bundle["scaffold-contract.v1.json"]
    ss = bundle["scaffold-selection.v1.json"]
    pq = bundle["page-quality-traits.v1.json"]
    pr = bundle["preview-runtime-policy.v1.json"]
    flow = bundle["llm-flow-concepts.v1.json"]

    default_scaffold = ss["fallback"]["defaultScaffold"]
    registry_ids = {s["id"] for s in sc["primaryScaffoldRegistry"]}
    findings.append(
        (default_scaffold in registry_ids, f"defaultScaffold '{default_scaffold}' finns i registry")
    )

    qt = pq["qualityTarget"]
    findings.append(
        (
            qt["blockBelow"] <= qt["gateScore"] <= qt["targetScore"],
            f"qualityTarget thresholds: {qt['blockBelow']} <= {qt['gateScore']} <= {qt['targetScore']}",
        )
    )

    total_weight = sum(t["weight"] for t in pq["traits"])
    findings.append(
        (
            total_weight == pq["scoring"]["weightsTotal"],
            f"trait-vikter summerar till {total_weight} (förväntat {pq['scoring']['weightsTotal']})",
        )
    )

    phase_ids = [p["id"] for p in flow["phases"]]
    findings.append(
        (set(phase_ids) == set(flow["canonicalFlow"]), "canonicalFlow matchar phase ids")
    )

    pr_kinds = {r["kind"] for r in pr["runtimes"]}
    findings.append(
        (pr["default"] in pr_kinds, f"default Preview Runtime '{pr['default']}' finns i runtimes")
    )

    canonicals = [t["canonical"] for t in nd["terms"]]
    findings.append(
        (len(canonicals) == len(set(canonicals)), f"alla {len(canonicals)} kanoniska termer är unika")
    )

    boundary_paths = {o["path"].rstrip("/") for o in rb["ownership"]} | {"backend.py"}
    unknown_owners = [
        t["canonical"]
        for t in nd["terms"]
        if not any(t["ownerPackage"].startswith(p) for p in boundary_paths if p)
    ]
    findings.append(
        (
            not unknown_owners,
            "alla termer har ownerPackage i repo-boundaries"
            + (f" (avvikande: {unknown_owners})" if unknown_owners else ""),
        )
    )

    block_phase_ids: list[str] = []
    for block in flow.get("phaseBlocks", []):
        block_phase_ids.extend(block["phaseIds"])
    findings.append(
        (
            set(block_phase_ids) == set(phase_ids),
            "phaseBlocks täcker exakt alla phase ids",
        )
    )

    ok_count = sum(1 for ok, _ in findings if ok)
    st.metric("Status", f"{ok_count}/{len(findings)}")

    for ok, msg in findings:
        if ok:
            st.success(msg)
        else:
            st.error(msg)


VIEWS = {
    "Översikt": lambda: safe_render(view_overview),
    "System Health": lambda: safe_render(view_system_health),
    "Cross-Policy Status": lambda: safe_render(view_cross_policy),
}
