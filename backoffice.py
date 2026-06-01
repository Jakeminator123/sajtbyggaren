"""Sajtbyggaren backoffice (Streamlit entry point).

Operator-facing admin tool for editing governance, viewing scaffolds and
dossiers, browsing the LLM flow, and running consistency checks.

This file is thin - all view logic lives under `backoffice/views/`. ADR 0002
keeps backoffice strictly out of the user runtime.

Run:
    pip install -r requirements.txt
    streamlit run backoffice.py
"""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from backoffice import loaders
from backoffice.views import (
    building_blocks,
    engine_runs,
    evals,
    governance,
    llm_engine,
    maintenance,
    playground,
    status,
)

st.set_page_config(
    page_title="Sajtbyggaren Backoffice",
    page_icon=":wrench:",
    layout="wide",
    initial_sidebar_state="expanded",
)


SECTIONS: dict[str, dict[str, Callable[[], None]]] = {
    "Status": status.VIEWS,
    "Governance": governance.VIEWS,
    "LLM Engine": llm_engine.VIEWS,
    "Building Blocks": building_blocks.VIEWS,
    "Runs": engine_runs.VIEWS,
    "Playground": playground.VIEWS,
    "Evals": evals.VIEWS,
    "Underhåll": maintenance.VIEWS,
}


def _hard_reset_caches() -> None:
    loaders.load_json.clear()
    loaders.read_text.clear()


def main() -> None:
    st.sidebar.title("Sajtbyggaren")
    st.sidebar.caption("Backoffice - operatörens redigeringsyta")

    for section, pages in SECTIONS.items():
        st.sidebar.markdown(f"**{section}**")
        for page_name in pages:
            if st.sidebar.button(page_name, key=f"nav-{page_name}", width="stretch"):
                st.session_state["current_view"] = page_name
        st.sidebar.markdown("")

    st.sidebar.divider()
    st.sidebar.caption(
        "**Källa:** `governance/`\n\n"
        "**Inte runtime.** Slutanvändarens flöde ligger i `apps/` + `packages/`."
    )

    if st.sidebar.button("Rensa cache", width="stretch"):
        _hard_reset_caches()
        st.sidebar.success("Cache rensad.")

    current = st.session_state.get("current_view", "Översikt")

    for pages in SECTIONS.values():
        if current in pages:
            pages[current]()
            return

    # Fallback: render Översikt.
    status.VIEWS["Översikt"]()


if __name__ == "__main__":
    main()
