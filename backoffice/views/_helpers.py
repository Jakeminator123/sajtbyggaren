"""Defensive helpers shared across view modules."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

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
    """Wrap a render call so a single broken policy doesn't kill the page.

    Shows the full traceback in an expander so developers can debug rather than
    silently swallowing every error.
    """
    try:
        fn(*args, **kwargs)
    except KeyError as exc:
        st.error(f"Saknat fält i policy: {exc}")
        with st.expander("Visa traceback"):
            st.code(traceback.format_exc(), language="text")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Oväntat fel ({type(exc).__name__}): {exc}")
        with st.expander("Visa traceback"):
            st.code(traceback.format_exc(), language="text")
