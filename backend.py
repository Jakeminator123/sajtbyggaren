"""Sajtbyggaren backoffice (Streamlit).

Detta är admin-verktyget för operatören. Det är INTE användarens runtime.
Backoffice läser och redigerar governance-policies, ger överblick över scaffolds
och dossiers, visar fas 1-3 i LLM-flödet, och kommer i kommande etapper styra
evals och telemetri.

Kör med:
    pip install -r requirements.txt
    streamlit run backend.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
POLICIES_DIR = GOVERNANCE_DIR / "policies"
SCHEMAS_DIR = GOVERNANCE_DIR / "schemas"
RULES_DIR = GOVERNANCE_DIR / "rules"
DECISIONS_DIR = GOVERNANCE_DIR / "decisions"
SCRIPTS_DIR = REPO_ROOT / "scripts"


st.set_page_config(
    page_title="Sajtbyggaren Backoffice",
    page_icon=":wrench:",
    layout="wide",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def list_policies() -> list[Path]:
    if not POLICIES_DIR.exists():
        return []
    return sorted(POLICIES_DIR.glob("*.json"))


def list_schemas() -> list[Path]:
    if not SCHEMAS_DIR.exists():
        return []
    return sorted(SCHEMAS_DIR.glob("*.json"))


def run_governance_validate() -> tuple[int, str]:
    script = SCRIPTS_DIR / "governance_validate.py"
    if not script.exists():
        return 1, f"Hittar inte {script}"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def run_rules_sync(check_only: bool) -> tuple[int, str]:
    script = SCRIPTS_DIR / "rules_sync.py"
    args = [sys.executable, str(script)]
    if check_only:
        args.append("--check")
    result = subprocess.run(args, capture_output=True, text=True, cwd=str(REPO_ROOT))
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def render_overview() -> None:
    st.header("Översikt")
    st.write(
        "Sajtbyggaren styrs av JSON-policies under `governance/policies/`. "
        "Detta är operatörens redigeringsyta. Användarens runtime ligger inte här."
    )

    policies = list_policies()
    schemas = list_schemas()
    rules = list(RULES_DIR.glob("*.md")) if RULES_DIR.exists() else []
    decisions = list(DECISIONS_DIR.glob("*.md")) if DECISIONS_DIR.exists() else []

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Policies", len(policies))
    col2.metric("Schemas", len(schemas))
    col3.metric("Rules", len(rules))
    col4.metric("Decisions", len(decisions))

    st.subheader("Snabbåtgärder")
    a1, a2 = st.columns(2)
    if a1.button("Kör governance-validering"):
        code, output = run_governance_validate()
        if code == 0:
            st.success(output or "OK")
        else:
            st.error(output or "Fel")
    if a2.button("Kontrollera rules-sync"):
        code, output = run_rules_sync(check_only=True)
        if code == 0:
            st.success(output or "OK")
        else:
            st.warning(output or "Out of sync")


def render_policies() -> None:
    st.header("Policies")
    policies = list_policies()
    if not policies:
        st.info("Inga policies hittades. Kontrollera att governance/policies/ existerar.")
        return

    names = [p.name for p in policies]
    selected = st.selectbox("Välj policy", names)
    selected_path = POLICIES_DIR / selected

    try:
        data = load_json(selected_path)
    except json.JSONDecodeError as exc:
        st.error(f"Ogiltig JSON: {exc}")
        return

    st.caption(
        f"policyId: `{data.get('policyId', 'okänd')}` "
        f"version: `{data.get('version', 'okänd')}` "
        f"status: `{data.get('status', 'okänd')}`"
    )

    edit_mode = st.toggle("Redigeringsläge", value=False, help="Visa textyta för att redigera JSON.")

    if edit_mode:
        text = selected_path.read_text(encoding="utf-8")
        new_text = st.text_area("JSON", value=text, height=500)
        if st.button("Spara"):
            try:
                json.loads(new_text)
            except json.JSONDecodeError as exc:
                st.error(f"Inte giltig JSON, sparar inte: {exc}")
                return
            selected_path.write_text(new_text, encoding="utf-8")
            st.success("Sparat. Kör 'Kör governance-validering' i översikten för att bekräfta.")
    else:
        st.json(data, expanded=False)


def render_llm_flow() -> None:
    st.header("LLM-flöde")
    flow_path = POLICIES_DIR / "llm-flow-concepts.v1.json"
    if not flow_path.exists():
        st.info("`llm-flow-concepts.v1.json` saknas.")
        return
    flow = load_json(flow_path)

    st.caption(f"northStar: {flow.get('northStar', '')}")
    st.subheader("Kanonisk ordning")
    st.write(" -> ".join(flow.get("canonicalFlow", [])))

    st.subheader("Faser")
    phases = sorted(flow.get("phases", []), key=lambda p: p.get("order", 0))

    phase_groups = {
        "Fas 1 - Brief & Policy Resolution": ["raw_prompt", "site_brief", "intent_resolution", "policy_resolution"],
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

    for group_label, ids in phase_groups.items():
        st.markdown(f"### {group_label}")
        group_phases = [p for p in phases if p.get("id") in ids]
        for phase in group_phases:
            with st.expander(
                f"{phase.get('order', 0):>3} - {phase.get('canonicalName')} "
                f"({phase.get('id')})"
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
                    for item in phase.get("mustNotDo", []):
                        st.write(f"- {item}")


def render_quality_traits() -> None:
    st.header("Page Quality Traits")
    traits_path = POLICIES_DIR / "page-quality-traits.v1.json"
    if not traits_path.exists():
        st.info("`page-quality-traits.v1.json` saknas.")
        return
    traits_doc = load_json(traits_path)

    qt = traits_doc.get("qualityTarget", {})
    cols = st.columns(4)
    cols[0].metric("Target", qt.get("targetScore"))
    cols[1].metric("Gate", qt.get("gateScore"))
    cols[2].metric("Block under", qt.get("blockBelow"))
    cols[3].metric("Skala", qt.get("scoreScale"))
    st.caption(qt.get("meaning", ""))

    st.subheader("Traits")
    for trait in traits_doc.get("traits", []):
        with st.expander(f"{trait.get('name')} (vikt {trait.get('weight')})"):
            st.write(trait.get("definition", ""))
            cols = st.columns(2)
            cols[0].markdown("**Positiva signaler**")
            for s in trait.get("positiveSignals", []):
                cols[0].write(f"- {s}")
            cols[1].markdown("**Negativa signaler**")
            for s in trait.get("negativeSignals", []):
                cols[1].write(f"- {s}")
            st.markdown("**Check methods:** " + ", ".join(trait.get("checkMethods", [])))
            st.markdown(f"**Owner package:** `{trait.get('ownerPackage')}`")


def render_naming() -> None:
    st.header("Naming Dictionary")
    path = POLICIES_DIR / "naming-dictionary.v1.json"
    if not path.exists():
        st.info("`naming-dictionary.v1.json` saknas.")
        return
    nd = load_json(path)

    st.caption(nd.get("purpose", ""))
    st.subheader("Globalt förbjudna termer")
    st.write(", ".join(nd.get("globallyForbidden", [])) or "(inga)")

    st.subheader("Termer")
    for term in nd.get("terms", []):
        with st.expander(f"{term.get('canonical')} - {term.get('id')}"):
            st.write(term.get("definition", ""))
            st.markdown(f"**Owner package:** `{term.get('ownerPackage')}`")
            allowed = term.get("aliasesAllowed", [])
            forbidden = term.get("aliasesForbidden", [])
            cols = st.columns(2)
            cols[0].markdown("**Tillåtna alias**")
            cols[0].write(", ".join(allowed) or "(inga)")
            cols[1].markdown("**Förbjudna alias**")
            cols[1].write(", ".join(forbidden) or "(inga)")


def render_scaffolds_placeholder() -> None:
    st.header("Scaffolds")
    st.info(
        "Scaffolds är inte implementerade än. När fas 2 byggs läggs en CRUD-yta här "
        "för att se, redigera och ta in/ut scaffolds, samt embedding-matchningar."
    )
    st.markdown(
        "**Planerad ägarmapp:** `packages/generation/orchestration/scaffolds/`\n\n"
        "**Planerade fält per scaffold:** id, namn, sajttyp, ägar-routes, "
        "default-variant, embedding, prompt-hints, capabilities."
    )


def render_dossiers_placeholder() -> None:
    st.header("Dossiers")
    st.info(
        "Dossiers är inte implementerade än. När fas 2 byggs läggs CRUD-yta här "
        "för att se, redigera och matcha dossiers (capability-moduler) mot scaffolds."
    )
    st.markdown(
        "**Planerad ägarmapp:** `packages/generation/orchestration/dossiers/`\n\n"
        "**Planerade fält per dossier:** id, capability-typ, klass (hard/soft), "
        "krav (env-vars, integrations), routes, prompt-guidance, code-expectations."
    )


def render_evals_placeholder() -> None:
    st.header("Evals och telemetri")
    st.info(
        "Evals byggs i `tests/evals/`. Backoffice får en körnings-/historikyta här "
        "när första prompt-batchen finns. Telemetri kopplas in i ett senare skede."
    )
    st.markdown(
        "**Första evals:** 5-10 företagshemside-prompts mot kandidat-baselines "
        "(`ba33b28`, `1f4e869`, `04b3215`) för att välja generation-bas. "
        "Se [governance/decisions/0004-migration-from-sajtmaskin-baseline.md](governance/decisions/0004-migration-from-sajtmaskin-baseline.md)."
    )


PAGES = {
    "Översikt": render_overview,
    "Policies": render_policies,
    "LLM-flöde": render_llm_flow,
    "Page Quality Traits": render_quality_traits,
    "Naming Dictionary": render_naming,
    "Scaffolds (kommer)": render_scaffolds_placeholder,
    "Dossiers (kommer)": render_dossiers_placeholder,
    "Evals och telemetri (kommer)": render_evals_placeholder,
}


def main() -> None:
    st.sidebar.title("Sajtbyggaren")
    st.sidebar.caption("Backoffice - operatörens redigeringsyta")
    page = st.sidebar.radio("Vy", list(PAGES.keys()))
    st.sidebar.divider()
    st.sidebar.markdown(
        "**Källa:** `governance/`\n\n"
        "**Inte runtime.** Slutanvändarens flöde ligger i `apps/` + `packages/`."
    )
    PAGES[page]()


if __name__ == "__main__":
    main()
