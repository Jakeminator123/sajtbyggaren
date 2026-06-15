"""Backoffice health wrappers: the quick sanity path must not require GitHub CLI.

``focus_check.py`` shells out to ``gh pr list``; on a normal local Python env
``gh`` may be absent, which would make the subprocess crash with
``FileNotFoundError``. The Backoffice "Snabb sanity" quick path uses
``run_focus_check()``, so it must soft-skip when ``gh`` is missing instead of
turning into a red crash.
"""

from __future__ import annotations

import pytest

import backoffice.health as health

pytestmark = pytest.mark.tooling


def test_run_focus_check_soft_skips_without_gh(monkeypatch) -> None:
    monkeypatch.setattr(health.shutil, "which", lambda _name: None)

    def _must_not_run(*_args, **_kwargs):
        raise AssertionError(
            "focus_check.py must not be spawned when gh is missing"
        )

    monkeypatch.setattr(health, "_run", _must_not_run)

    result = health.run_focus_check()
    assert result.ok is True
    assert result.exit_code == 0
    assert "SKIP" in result.output.upper()


def test_run_focus_check_runs_when_gh_present(monkeypatch) -> None:
    monkeypatch.setattr(health.shutil, "which", lambda _name: "/usr/bin/gh")

    sentinel = health.CheckResult(
        name="focus_check.py", ok=True, output="ran", exit_code=0
    )
    monkeypatch.setattr(health, "_run", lambda _script, *_a: sentinel)

    assert health.run_focus_check() is sentinel
