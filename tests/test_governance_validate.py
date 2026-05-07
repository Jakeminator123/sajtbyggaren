"""Run governance_validate.py as a subprocess and assert exit code 0.

This guarantees that every policy under governance/policies/ matches its
JSON Schema and that no globally-forbidden term is used outside its
allowed anti-pattern fields.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR


@pytest.mark.governance
@pytest.mark.tooling
def test_governance_validate_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "governance_validate.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "governance_validate.py failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
