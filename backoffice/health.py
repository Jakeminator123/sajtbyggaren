"""Wrappers for the three governance scripts so the backoffice can call them."""

from __future__ import annotations

import shutil
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


def run_focus_check() -> CheckResult:
    """Fast drift check: does the repo match docs/current-focus.md?

    ``focus_check.py`` cross-checks open PRs by shelling out to the GitHub CLI
    (``gh pr list``). On a normal local Python env ``gh`` may not be installed,
    which would make the subprocess crash with ``FileNotFoundError``. A quick
    sanity check must not require GitHub CLI, so soft-skip when ``gh`` is
    missing (ok=True, not a red crash). When ``gh`` is present, run the full
    check - non-zero exit only on hard errors (diverged branch, missing focus
    SHA); stale-doc/forgotten-push situations surface as warnings.
    """
    if shutil.which("gh") is None:
        return CheckResult(
            name="focus_check.py",
            ok=True,
            output=(
                "SKIPPED - GitHub CLI (gh) saknas; focus_check körs bara när gh "
                "finns (den shellar ut till `gh pr list`). Kör övriga checks som "
                "vanligt."
            ),
            exit_code=0,
        )
    return _run("focus_check.py")


def run_governance_validate() -> CheckResult:
    return _run("governance_validate.py")


def run_rules_sync_check() -> CheckResult:
    return _run("rules_sync.py", "--check")


def run_rules_sync_apply() -> CheckResult:
    return _run("rules_sync.py")


def run_term_coverage(strict: bool = True) -> CheckResult:
    args = ["--strict"] if strict else []
    return _run("check_term_coverage.py", *args)


def run_platform_baseline_check() -> CheckResult:
    """Drift check: do package.json files conform to platform-baseline.v1.json?"""
    return _run("check_platform_baseline.py", "--check")


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
