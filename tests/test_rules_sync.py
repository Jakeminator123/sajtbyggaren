"""Verify that .cursor/rules/ is in sync with governance/rules/.

The mirror is the only acceptable state. Direct edits to .cursor/rules/
must be detected by this test.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from .conftest import CURSOR_RULES_DIR, REPO_ROOT, RULES_DIR, SCRIPTS_DIR


@pytest.mark.governance
@pytest.mark.tooling
def test_rules_sync_check_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "rules_sync.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "rules_sync.py --check failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.mark.governance
def test_every_rule_has_a_mirror():
    sources = {p.stem for p in RULES_DIR.glob("*.md")}
    mirrors = {p.stem for p in CURSOR_RULES_DIR.glob("*.mdc")}
    missing = sources - mirrors
    extra = mirrors - sources
    assert not missing, f"Sources missing mirror in .cursor/rules: {sorted(missing)}"
    assert not extra, (
        "Mirror files in .cursor/rules without source in governance/rules: "
        f"{sorted(extra)}"
    )
