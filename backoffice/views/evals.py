"""Evals och telemetri-block (placeholder)."""

from __future__ import annotations

import streamlit as st

from ..paths import TESTS_DIR
from ._helpers import safe_render


def view_evals_placeholder() -> None:
    st.title("Evals och telemetri")
    st.info(
        "Evals byggs i `tests/evals/`. Backoffice får körnings- och historikyta "
        "här när första prompt-batchen finns."
    )
    eval_files = list((TESTS_DIR / "evals").rglob("*"))
    eval_files = [f for f in eval_files if f.is_file() and f.name != ".gitkeep"]
    st.metric("Eval-filer", len(eval_files))
    st.caption(
        "Första evals är inte sajtmaskin-baseline-jämförelser (ADR 0008) utan "
        "regression-tester på governance-konsistens. Se `tests/test_cross_policy_consistency.py`."
    )


VIEWS = {
    "Evals och telemetri": lambda: safe_render(view_evals_placeholder),
}
