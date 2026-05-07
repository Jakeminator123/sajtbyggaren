"""Defensive helpers shared across view modules."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from .. import health


def render_check(result: health.CheckResult) -> None:
    if result.ok:
        st.success(f"{result.name}: OK")
    else:
        st.error(f"{result.name}: FEL (exit {result.exit_code})")
    if result.output:
        with st.expander("Visa output"):
            st.code(result.output, language="text")


def safe_render(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Wrap a render call so a single broken policy doesn't kill the page."""
    try:
        fn(*args, **kwargs)
    except KeyError as exc:
        st.error(f"Saknat fält i policy: {exc}")
    except Exception as exc:
        st.error(f"Oväntat fel i vyn: {exc}")
