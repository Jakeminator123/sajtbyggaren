"""Regression tests for ``packages/generation/maintenance/auto_prune.py``.

Locks the opt-in retention contract from ``.env.example``:

- Unset / empty / 0 / negative env-var means "do nothing" for that resource.
- ``data/runs/`` keeps the N newest mtime-sorted directories.
- ``data/prompt-inputs/`` keeps the N newest current-pointer files and
  removes the matching sidecar + all ``.vN.*``-snapshots in the same
  pass so orphan snapshots cannot be left behind.
- Port 3000 listener triggers an unconditional skip of the entire
  auto-prune (defence in depth shared with
  ``scripts/prune_generated_previews.py``).
- ``scripts/build_site.py:build()`` calls auto-prune only when
  ``runs_dir`` is left at default (production path); tests passing
  ``tmp_path`` opt out automatically.
- ``scripts/prompt_to_project_input.py:main()`` calls auto-prune
  immediately after argparse, before any disk write.
"""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest

from packages.generation.maintenance import (
    MAX_PROMPT_INPUTS_ENV_VAR,
    MAX_RUNS_ENV_VAR,
    auto_prune_all,
    prune_prompt_inputs,
    prune_runs,
)
from packages.generation.maintenance.auto_prune import _read_max


def _touch(path: Path, content: str = "{}") -> None:
    path.write_text(content, encoding="utf-8")


def _set_mtime(path: Path, mtime: float) -> None:
    import os

    os.utime(path, (mtime, mtime))


def test_read_max_returns_none_for_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(MAX_RUNS_ENV_VAR, raising=False)
    assert _read_max(MAX_RUNS_ENV_VAR) is None


@pytest.mark.parametrize("raw", ["", "   ", "0", "-3", "abc", "1.5"])
def test_read_max_treats_blank_zero_negative_and_garbage_as_optout(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(MAX_RUNS_ENV_VAR, raw)
    assert _read_max(MAX_RUNS_ENV_VAR) is None


def test_read_max_returns_int_for_positive_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MAX_RUNS_ENV_VAR, "7")
    assert _read_max(MAX_RUNS_ENV_VAR) == 7


def test_prune_runs_keeps_n_newest_by_mtime(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    now = time.time()
    for index in range(5):
        run = runs / f"run{index}"
        run.mkdir()
        _touch(run / "build-result.json")
        _set_mtime(run, now - (5 - index) * 100)

    removed = prune_runs(runs, max_runs=2)

    assert sorted(removed) == ["run0", "run1", "run2"]
    survivors = sorted(child.name for child in runs.iterdir() if child.is_dir())
    assert survivors == ["run3", "run4"]


def test_prune_runs_noop_when_under_cap(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "only-run").mkdir()
    _touch(runs / "only-run" / "build-result.json")

    removed = prune_runs(runs, max_runs=5)

    assert removed == []
    assert (runs / "only-run").is_dir()


def test_prune_runs_noop_when_max_is_zero_or_negative(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "leftover").mkdir()
    _touch(runs / "leftover" / "build-result.json")

    assert prune_runs(runs, max_runs=0) == []
    assert prune_runs(runs, max_runs=-1) == []
    assert (runs / "leftover").is_dir()


def test_prune_runs_dry_run_reports_but_keeps_files(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    now = time.time()
    for index in range(3):
        run = runs / f"r{index}"
        run.mkdir()
        _set_mtime(run, now - (3 - index) * 100)

    removed = prune_runs(runs, max_runs=1, dry_run=True)

    assert sorted(removed) == ["r0", "r1"]
    assert (runs / "r0").is_dir(), "dry-run must not delete"
    assert (runs / "r1").is_dir(), "dry-run must not delete"


def test_prune_prompt_inputs_removes_pointer_meta_and_versioned_snapshots(
    tmp_path: Path,
) -> None:
    pi = tmp_path / "prompt-inputs"
    pi.mkdir()
    now = time.time()
    # Two siteIds; site-old is the oldest pointer and will be removed.
    _touch(pi / "site-old.project-input.json")
    _touch(pi / "site-old.meta.json")
    _touch(pi / "site-old.v1.project-input.json")
    _touch(pi / "site-old.v1.meta.json")
    _touch(pi / "site-old.v2.project-input.json")
    _touch(pi / "site-old.v2.meta.json")
    _touch(pi / "site-new.project-input.json")
    _touch(pi / "site-new.meta.json")
    _set_mtime(pi / "site-old.project-input.json", now - 1000)
    _set_mtime(pi / "site-new.project-input.json", now)

    removed = prune_prompt_inputs(pi, max_inputs=1)

    assert removed == ["site-old"]
    assert not (pi / "site-old.project-input.json").exists()
    assert not (pi / "site-old.meta.json").exists()
    assert not (pi / "site-old.v1.project-input.json").exists()
    assert not (pi / "site-old.v1.meta.json").exists()
    assert not (pi / "site-old.v2.project-input.json").exists()
    assert not (pi / "site-old.v2.meta.json").exists()
    assert (pi / "site-new.project-input.json").exists()
    assert (pi / "site-new.meta.json").exists()


def test_prune_prompt_inputs_ignores_unrelated_files(tmp_path: Path) -> None:
    pi = tmp_path / "prompt-inputs"
    pi.mkdir()
    _touch(pi / "README.md", "# notes")
    _touch(pi / ".keep", "")
    _touch(pi / "site-a.project-input.json")
    _touch(pi / "site-b.project-input.json")
    now = time.time()
    _set_mtime(pi / "site-a.project-input.json", now - 1000)
    _set_mtime(pi / "site-b.project-input.json", now)

    removed = prune_prompt_inputs(pi, max_inputs=1)

    assert removed == ["site-a"]
    assert (pi / "README.md").exists(), "non-pointer files must be untouched"
    assert (pi / ".keep").exists()
    assert (pi / "site-b.project-input.json").exists()


def test_prune_prompt_inputs_noop_when_under_cap(tmp_path: Path) -> None:
    pi = tmp_path / "prompt-inputs"
    pi.mkdir()
    _touch(pi / "lonely.project-input.json")

    removed = prune_prompt_inputs(pi, max_inputs=10)

    assert removed == []
    assert (pi / "lonely.project-input.json").exists()


def test_auto_prune_all_no_env_no_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(MAX_RUNS_ENV_VAR, raising=False)
    monkeypatch.delenv(MAX_PROMPT_INPUTS_ENV_VAR, raising=False)
    monkeypatch.delenv("SAJTBYGGAREN_MAX_GENERATED", raising=False)

    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "kept").mkdir()
    _touch(runs / "kept" / "build-result.json")

    report = auto_prune_all(
        runs_dir=runs,
        prompt_inputs_dir=tmp_path / "pi",
        skip_port_guard=True,
        verbose=False,
    )

    assert report.runs_removed == []
    assert report.prompt_inputs_removed == []
    assert report.generated_removed == []
    assert (runs / "kept").is_dir()


def test_auto_prune_all_prunes_only_resources_with_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    now = time.time()
    for index in range(3):
        run = runs / f"r{index}"
        run.mkdir()
        _set_mtime(run, now - (3 - index) * 100)

    monkeypatch.setenv(MAX_RUNS_ENV_VAR, "1")
    monkeypatch.delenv(MAX_PROMPT_INPUTS_ENV_VAR, raising=False)
    monkeypatch.delenv("SAJTBYGGAREN_MAX_GENERATED", raising=False)

    report = auto_prune_all(
        runs_dir=runs,
        prompt_inputs_dir=tmp_path / "pi",
        skip_port_guard=True,
        verbose=False,
    )

    assert sorted(report.runs_removed) == ["r0", "r1"]
    assert report.prompt_inputs_removed == []
    assert report.generated_removed == []
    assert (runs / "r2").is_dir()


def test_auto_prune_all_refuses_when_port_3000_listening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(MAX_RUNS_ENV_VAR, "1")
    runs = tmp_path / "runs"
    runs.mkdir()
    for index in range(3):
        (runs / f"r{index}").mkdir()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        try:
            server.bind(("127.0.0.1", 3000))
        except OSError:
            pytest.skip("port 3000 unavailable in this environment")
        server.listen(1)

        accepted: list[socket.socket] = []

        def _accept_loop() -> None:
            while True:
                try:
                    conn, _ = server.accept()
                except OSError:
                    break
                accepted.append(conn)

        thread = threading.Thread(target=_accept_loop, daemon=True)
        thread.start()

        report = auto_prune_all(
            runs_dir=runs,
            prompt_inputs_dir=tmp_path / "pi",
            verbose=False,
        )
        assert report.skipped_due_to_dev_server is True
        assert report.runs_removed == []
        assert all((runs / f"r{i}").is_dir() for i in range(3))
    finally:
        server.close()
        for conn in accepted:
            conn.close()


def test_build_site_skips_auto_prune_when_runs_dir_overridden() -> None:
    """tmp_path-based smoke-tests must not trigger production auto-prune.

    Source-lock so a future refactor of ``build(runs_dir=...)`` keeps the
    ``auto_prune and runs_dir is None`` guard intact.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "build_site.py"
    ).read_text(encoding="utf-8")
    assert "if auto_prune and runs_dir is None:" in source
    assert "from packages.generation.maintenance import auto_prune_all" in source


def test_prompt_to_project_input_calls_auto_prune_on_main() -> None:
    """Source-lock that ``main()`` invokes auto-prune before disk writes."""
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prompt_to_project_input.py"
    ).read_text(encoding="utf-8")
    main_index = source.index("def main()")
    body = source[main_index:]
    args_index = body.index("args = parser.parse_args()")
    auto_index = body.index("auto_prune_all()")
    output_index = body.index("output_dir = Path(args.output_dir).resolve()")
    assert args_index < auto_index < output_index, (
        "auto_prune_all() must run after argparse but before any disk write"
    )
