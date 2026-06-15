"""Building Blocks: Reference Templates-vyn."""

from __future__ import annotations

import streamlit as st

from . import REFERENCE_TEMPLATES_DIR


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
