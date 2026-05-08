"""Cached loaders for governance JSON.

Streamlit re-runs the script on every interaction; @st.cache_data avoids
re-reading the same files repeatedly. Cache is invalidated on file mtime
so policy edits are picked up.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from .paths import DECISIONS_DIR, POLICIES_DIR, RULES_DIR, SCHEMAS_DIR


def _file_signature(path: Path) -> tuple[str, float]:
    if not path.exists():
        return (str(path), 0.0)
    return (str(path), path.stat().st_mtime)


@st.cache_data(show_spinner=False)
def load_json(path_str: str, _signature: tuple[str, float]) -> dict[str, Any]:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def load_policy(name: str) -> dict[str, Any]:
    path = POLICIES_DIR / name
    return load_json(str(path), _file_signature(path))


def load_schema(name: str) -> dict[str, Any]:
    path = SCHEMAS_DIR / name
    return load_json(str(path), _file_signature(path))


def list_policies() -> list[Path]:
    return sorted(POLICIES_DIR.glob("*.json"))


def list_schemas() -> list[Path]:
    return sorted(SCHEMAS_DIR.glob("*.json"))


def list_rules() -> list[Path]:
    return sorted(RULES_DIR.glob("*.md"))


def list_decisions() -> list[Path]:
    return sorted(DECISIONS_DIR.glob("*.md"))


@st.cache_data(show_spinner=False)
def read_text(path_str: str, _signature: tuple[str, float]) -> str:
    return Path(path_str).read_text(encoding="utf-8")


def text_of(path: Path) -> str:
    return read_text(str(path), _file_signature(path))


def safe_load_policy(name: str) -> tuple[dict[str, Any] | None, str | None]:
    """Load a policy without raising. Returns (data, error_message)."""
    path = POLICIES_DIR / name
    if not path.exists():
        return None, f"Policy {name} saknas"
    try:
        return load_policy(name), None
    except Exception as exc:
        return None, f"Kunde inte ladda {name}: {exc}"


def list_run_ids() -> list[str]:
    """List runIds present under data/runs/, newest first."""
    from .paths import RUNS_DIR

    if not RUNS_DIR.exists():
        return []
    return sorted(
        [p.name for p in RUNS_DIR.iterdir() if p.is_dir()],
        reverse=True,
    )
