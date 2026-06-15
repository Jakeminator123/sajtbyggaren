"""Regression tests for the Streamlit backoffice entrypoint rename."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.tooling

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_backoffice_py_exists() -> None:
    assert (REPO_ROOT / "backoffice.py").is_file()


def test_backend_py_not_present() -> None:
    assert not (REPO_ROOT / "backend.py").exists()


def test_backoffice_entrypoint_uses_view_registry() -> None:
    """backoffice.py composes the sidebar from the single source of truth in
    backoffice/view_registry.py (extracted so it is importable without
    st.set_page_config). The section/VIEWS wiring is asserted against the
    registry below and locked bidirectionally in test_backoffice_registry.py."""
    source = (REPO_ROOT / "backoffice.py").read_text(encoding="utf-8")
    assert "from backoffice.view_registry import SECTIONS" in source


def test_view_registry_registers_maintenance_section() -> None:
    from backoffice.view_registry import SECTION_MODULES, SECTIONS
    from backoffice.views import maintenance

    assert "Underhåll" in SECTIONS
    assert SECTION_MODULES["Underhåll"] is maintenance
    assert SECTIONS["Underhåll"] is maintenance.VIEWS
