"""Strict term coverage: zero unknown candidate terms allowed.

If this test fails, either the user introduced a new domain term that
must be registered in naming-dictionary.v1.json, or the script's
COMMON_WORDS list needs a small update for a real false positive.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR


@pytest.mark.governance
@pytest.mark.tooling
def test_term_coverage_strict_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "check_term_coverage.py"), "--strict"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "check_term_coverage.py --strict found unknown terms:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
