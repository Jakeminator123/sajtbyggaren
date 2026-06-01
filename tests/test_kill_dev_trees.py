"""Tests for kill-dev-trees.py process matching (reviewer-fynd 2026-05-31).

The Windows orphan-cleanup helper used to whitelist any process whose
CommandLine contained ``next start``/``next dev`` - which matches ANY Next.js
project on the machine, so running the helper could tree-kill unrelated
projects. ``matches_sajtbyggaren`` now requires a Sajtbyggaren scope signal:
a repo/output path token, or ``next start``/``next dev`` on Viewser's preview
port range 4100-4199. These tests lock that the over-broad bare-``next``
behaviour stays gone.

``kill-dev-trees.py`` lives at the repo root with hyphens in its name, so it is
loaded via importlib rather than a normal import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = REPO_ROOT / "kill-dev-trees.py"
_SPEC = importlib.util.spec_from_file_location("kill_dev_trees", _MODULE_PATH)
assert _SPEC and _SPEC.loader
kill_dev_trees = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(kill_dev_trees)

matches_sajtbyggaren = kill_dev_trees.matches_sajtbyggaren


# ---------------------------------------------------------------------------
# Path-scope tokens always qualify
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmdline",
    [
        r"node C:\Users\jakem\Desktop\sajtbyggaren\apps\viewser\scripts\dev.mjs",
        r"npx next start -p 4137  (cwd C:\Users\...\sajtbyggaren-output\.generated\painter\builds\x)",
        r"node ...\.generated\painter-palma\builds\20260531T184500Z\node_modules\.bin\next start",
    ],
)
def test_path_scope_tokens_match(cmdline: str) -> None:
    assert matches_sajtbyggaren(cmdline) is True


# ---------------------------------------------------------------------------
# next start/dev only qualifies on the Viewser preview port range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmdline",
    [
        "node next start -p 4100",  # low boundary
        "node next start -p 4199",  # high boundary
        "node next start -p 4137",
        "node next dev --port 4150",
        "node next dev --port=4150",
        "node next start -p4137",  # no separator
    ],
)
def test_next_on_preview_port_matches(cmdline: str) -> None:
    assert matches_sajtbyggaren(cmdline) is True


@pytest.mark.parametrize(
    "cmdline",
    [
        "node next dev -p 3000",  # an unrelated Next project on its default port
        "node next start -p 8080",
        "node next start -p 4099",  # just below the range
        "node next start -p 4200",  # just above the range
        "node next start",  # bare, no port at all
        "node next dev",
    ],
)
def test_foreign_next_processes_do_not_match(cmdline: str) -> None:
    # The whole point of the fix: a Next.js process that is NOT on Viewser's
    # preview port range and carries no Sajtbyggaren path must be left alone.
    assert matches_sajtbyggaren(cmdline) is False


# ---------------------------------------------------------------------------
# Unrelated processes + edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmdline",
    [
        None,
        "",
        r"node C:\Users\jakem\.vscode\extensions\ms-python\language-server.js",
        "node /usr/lib/code-server/out/server-main.js",
        "esbuild --serve",
    ],
)
def test_unrelated_or_empty_does_not_match(cmdline: str | None) -> None:
    assert matches_sajtbyggaren(cmdline) is False


def test_has_preview_port_boundaries() -> None:
    assert kill_dev_trees._has_preview_port("next start -p 4100") is True
    assert kill_dev_trees._has_preview_port("next start -p 4199") is True
    assert kill_dev_trees._has_preview_port("next start -p 4099") is False
    assert kill_dev_trees._has_preview_port("next start -p 4200") is False
    assert kill_dev_trees._has_preview_port("next start") is False


def test_path_scope_via_ancestry_not_only_own_cmdline() -> None:
    """Windows barnprocesser har ofta tom cmdline — scope_text från förälder."""
    assert (
        matches_sajtbyggaren(
            None,
            scope_text=(
                r"cmd /d /s /c npx next dev "
                r"C:\Users\jakem\Desktop\sajtbyggaren\apps\viewser"
            ),
        )
        is True
    )


def test_viewser_dev_port_with_path_scope_matches() -> None:
    cmd = r"node C:\...\sajtbyggaren\apps\viewser\node_modules\next\dist\bin\next dev -p 3000"
    assert matches_sajtbyggaren(cmd) is True


def test_preview_port_listener_matches_even_with_empty_cmdline() -> None:
    proc = {"ProcessId": 9999, "CommandLine": None}
    by_pid = {9999: proc}
    assert (
        kill_dev_trees.is_target_node_process(
            proc,
            by_pid=by_pid,
            preview_listener_pids={9999},
            dev_listener_pids=set(),
        )
        is True
    )


def test_dev_port_listener_requires_path_scope() -> None:
    proc = {"ProcessId": 8888, "CommandLine": None}
    by_pid = {8888: proc}
    # Tom cmdline, ingen förälder med sajtbyggaren → skyddad.
    assert (
        kill_dev_trees.is_target_node_process(
            proc,
            by_pid=by_pid,
            preview_listener_pids=set(),
            dev_listener_pids={8888},
        )
        is False
    )
    by_pid[8888] = proc
    by_pid[7777] = {
        "ProcessId": 7777,
        "ParentProcessId": 0,
        "CommandLine": r"node C:\Users\jakem\Desktop\sajtbyggaren\apps\viewser\scripts\dev.mjs",
    }
    proc["ParentProcessId"] = 7777
    assert (
        kill_dev_trees.is_target_node_process(
            proc,
            by_pid=by_pid,
            preview_listener_pids=set(),
            dev_listener_pids={8888},
        )
        is True
    )
