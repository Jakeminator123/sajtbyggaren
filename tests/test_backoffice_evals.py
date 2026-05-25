"""Regression tests for the Backoffice eval controls."""

from __future__ import annotations

import subprocess
from typing import Any


class _FakeProcess:
    pid = 12345

    def __init__(self, wait_results: list[int | None]) -> None:
        self.wait_results = wait_results
        self.wait_timeouts: list[float] = []

    def poll(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        self.wait_timeouts.append(float(timeout or 0))
        result = self.wait_results.pop(0)
        if result is None:
            raise subprocess.TimeoutExpired(cmd="fake-eval", timeout=timeout)
        return result


def test_backoffice_eval_labels_follow_canonical_case_lists() -> None:
    from backoffice.views.evals import _full_button_label, _quick_button_label

    assert _quick_button_label() == "Snabb regression (6x skip-build)"
    assert _full_button_label() == (
        "Full build (painter-palma + atelje-bird + cafe-bistro + clinic-tandvard)"
    )


def test_stop_process_tree_after_timeout_escalates_to_force(monkeypatch: Any) -> None:
    from backoffice.views import evals

    process = _FakeProcess(wait_results=[None, 1])
    signals: list[bool] = []

    def _record_signal(_proc: _FakeProcess, *, force: bool) -> None:
        signals.append(force)

    monkeypatch.setattr(evals, "_signal_process_tree", _record_signal)

    assert evals._stop_process_tree_after_timeout(process) == 1
    assert signals == [False, True]
    assert process.wait_timeouts == [
        evals.TERMINATE_GRACE_SECONDS,
        evals.KILL_GRACE_SECONDS,
    ]


def test_stop_process_tree_after_timeout_skips_force_when_soft_stop_exits(
    monkeypatch: Any,
) -> None:
    from backoffice.views import evals

    process = _FakeProcess(wait_results=[0])
    signals: list[bool] = []

    def _record_signal(_proc: _FakeProcess, *, force: bool) -> None:
        signals.append(force)

    monkeypatch.setattr(evals, "_signal_process_tree", _record_signal)

    assert evals._stop_process_tree_after_timeout(process) == 0
    assert signals == [False]
    assert process.wait_timeouts == [evals.TERMINATE_GRACE_SECONDS]
