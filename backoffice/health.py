"""Wrappers for the three governance scripts so the backoffice can call them."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from .paths import REPO_ROOT, SCRIPTS_DIR


@dataclass
class CheckResult:
    name: str
    ok: bool
    output: str
    exit_code: int


def _run(script: str, *args: str) -> CheckResult:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    output = (result.stdout or "") + (result.stderr or "")
    return CheckResult(
        name=script,
        ok=(result.returncode == 0),
        output=output.strip(),
        exit_code=result.returncode,
    )


def run_governance_validate() -> CheckResult:
    return _run("governance_validate.py")


def run_rules_sync_check() -> CheckResult:
    return _run("rules_sync.py", "--check")


def run_rules_sync_apply() -> CheckResult:
    return _run("rules_sync.py")


def run_term_coverage(strict: bool = True) -> CheckResult:
    args = ["--strict"] if strict else []
    return _run("check_term_coverage.py", *args)


def run_pytest_governance() -> CheckResult:
    """Run pytest with the governance marker for fast feedback."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-m", "governance", "-q"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    output = (result.stdout or "") + (result.stderr or "")
    return CheckResult(
        name="pytest -m governance",
        ok=(result.returncode == 0),
        output=output.strip(),
        exit_code=result.returncode,
    )
