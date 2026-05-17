"""Regression tests for the Streamlit backoffice entrypoint rename."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_backoffice_py_exists() -> None:
    assert (REPO_ROOT / "backoffice.py").is_file()


def test_backend_py_not_present() -> None:
    assert not (REPO_ROOT / "backend.py").exists()


def test_backoffice_entrypoint_registers_maintenance_section() -> None:
    source = (REPO_ROOT / "backoffice.py").read_text(encoding="utf-8")
    assert "from backoffice.views import" in source
    assert "maintenance" in source
    assert '"Underhåll": maintenance.VIEWS' in source
