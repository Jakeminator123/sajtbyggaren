"""Governance-block: Policies, Naming Dictionary, Page Quality Traits, Rules, ADR."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from .. import loaders
from ..paths import DECISIONS_DIR, POLICIES_DIR, RULES_DIR
from ._helpers import safe_render


def _hard_reset_caches() -> None:
    loaders.load_json.clear()
    loaders.read_text.clear()


def view_policies() -> None:
    st.title("Policies")
    policies = loaders.list_policies()
    if not policies:
        st.info("Inga policies hittades.")
        return

    names = [p.name for p in policies]
    selected = st.selectbox("Välj policy", names, key="policies_select")
    selected_path = POLICIES_DIR / selected

    data, err = loaders.safe_load_policy(selected)
    if err or data is None:
        st.error(err)
        return

    a, b, c, d = st.columns(4)
    a.metric("policyId", data.get("policyId", "okänd"))
    b.metric("version", data.get("version", "okänd"))
    c.metric("status", data.get("status", "okänd"))
    if "$schema" in data:
        d.metric("schema", Path(data["$schema"]).name)

    if data.get("purpose"):
        st.info(data["purpose"])

    tab_view, tab_edit = st.tabs(["Läs", "Redigera"])
    with tab_view:
        st.json(data, expanded=False)
    with tab_edit:
        st.warning(
            "Edit-läget skriver till disk + kör governance_validate direkt. "
            "Vid validation-fail rullas ändringen tillbaka automatiskt."
        )
        text = selected_path.read_text(encoding="utf-8")
        new_text = st.text_area("JSON", value=text, height=600, key=f"edit-{selected}")
        if st.button("Spara", key=f"save-{selected}"):
            # 1. JSON-validera
            try:
                json.loads(new_text)
            except json.JSONDecodeError as exc:
                st.error(f"Ogiltig JSON, sparar inte: {exc}")
                return

            # 2. Skriv backup, applicera, kör governance_validate, rollback om fel.
            backup = text
            selected_path.write_text(new_text, encoding="utf-8")
            _hard_reset_caches()

            from .. import health

            result = health.run_governance_validate()
            if not result.ok:
                selected_path.write_text(backup, encoding="utf-8")
                _hard_reset_caches()
                st.error(
                    f"governance_validate failade efter spara - automatisk rollback genomfört.\n\n"
                    f"Output:\n{result.output}"
                )
                return

            st.success(
                f"Sparat och validerat. {selected} är fortfarande policy-konsistent."
            )


def view_naming_dictionary() -> None:
    st.title("Naming Dictionary")
    nd, err = loaders.safe_load_policy("naming-dictionary.v1.json")
    if err or nd is None:
        st.error(err)
        return

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
                f"**{term.get('canonical', '?')}** (`{term.get('id', '?')}`)  "
                f"\n*{term.get('ownerPackage', '?')}*  "
                f"\n{term.get('definition', '')}"
            )

    with st.expander("Globally forbidden"):
        st.write(", ".join(nd.get("globallyForbidden", [])) or "(inga)")


def view_quality_traits() -> None:
    st.title("Page Quality Traits")
    pq, err = loaders.safe_load_policy("page-quality-traits.v1.json")
    if err or pq is None:
        st.error(err)
        return

    qt = pq.get("qualityTarget", {})
    cols = st.columns(4)
    cols[0].metric("Target", qt.get("targetScore"))
    cols[1].metric("Gate", qt.get("gateScore"))
    cols[2].metric("Block under", qt.get("blockBelow"))
    cols[3].metric("Skala", qt.get("scoreScale"))
    st.caption(qt.get("meaning", ""))

    total_weight = sum(t["weight"] for t in pq.get("traits", []))
    st.write(
        f"Vikter summerar till {total_weight} av "
        f"{pq.get('scoring', {}).get('weightsTotal', '?')} förväntade."
    )

    for trait in pq.get("traits", []):
        with st.expander(f"{trait.get('name', '?')} (vikt {trait.get('weight', '?')})"):
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


def view_rules() -> None:
    st.title("Rules")
    st.caption(
        "Källfiler i `governance/rules/`. Spegeln i `.cursor/rules/` "
        "uppdateras med `python scripts/rules_sync.py`."
    )
    rules = loaders.list_rules()
    if not rules:
        st.info("Inga regler hittades.")
        return
    names = [p.name for p in rules]
    selected = st.selectbox("Välj regel", names, key="rules_select")
    text = loaders.text_of(RULES_DIR / selected)
    st.markdown(text)


def view_decisions() -> None:
    st.title("Architecture Decisions (ADR)")
    decisions = loaders.list_decisions()
    if not decisions:
        st.info("Inga ADR:er hittades.")
        return
    names = [p.name for p in decisions]
    selected = st.selectbox("Välj ADR", names, key="adr_select")
    text = loaders.text_of(DECISIONS_DIR / selected)
    st.markdown(text)


VIEWS = {
    "Policies": lambda: safe_render(view_policies),
    "Naming Dictionary": lambda: safe_render(view_naming_dictionary),
    "Page Quality Traits": lambda: safe_render(view_quality_traits),
    "Rules": lambda: safe_render(view_rules),
    "ADR": lambda: safe_render(view_decisions),
}
