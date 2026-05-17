"""Regression tests for Backoffice maintenance cleanup helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path

from backoffice.maintenance import (
    apply_safe_cleanup,
    assert_cleanup_path_allowed,
    path_size_bytes,
    plan_safe_cleanup,
)
from packages.generation.maintenance import MAX_RUNS_ENV_VAR


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def _set_mtime(path: Path, mtime: float) -> None:
    os.utime(path, (mtime, mtime))


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "data" / "runs").mkdir(parents=True)
    (repo / "data" / "prompt-inputs").mkdir(parents=True)
    (repo / "data" / "starters").mkdir(parents=True)
    (repo / "packages" / "preview-runtime").mkdir(parents=True)
    (repo / "apps" / "viewser").mkdir(parents=True)
    return repo


def _make_run(repo: Path, name: str, *, size: int, mtime_offset: float) -> Path:
    run_dir = repo / "data" / "runs" / name
    _write(run_dir / "build-result.json", size)
    when = time.time() + mtime_offset
    _set_mtime(run_dir, when)
    return run_dir


def test_cleanup_dry_run_does_not_delete(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_run(repo, "old-run", size=10, mtime_offset=-100)
    _make_run(repo, "new-run", size=10, mtime_offset=0)
    _write(repo / ".pytest_cache" / "cache.bin", 7)
    _write(repo / "root.log", 5)

    plan = plan_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={MAX_RUNS_ENV_VAR: "1"},
    )

    assert plan.total_count >= 3
    assert (repo / "data" / "runs" / "old-run").is_dir()
    assert (repo / ".pytest_cache").is_dir()
    assert (repo / "root.log").is_file()


def test_cleanup_apply_respects_current_pointer_protection(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _make_run(repo, "protected-old", size=3, mtime_offset=-300)
    _make_run(repo, "delete-old", size=5, mtime_offset=-200)
    _make_run(repo, "new-run", size=7, mtime_offset=0)

    result = apply_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={MAX_RUNS_ENV_VAR: "1"},
        protected_run_ids={"protected-old"},
    )

    assert (repo / "data" / "runs" / "protected-old").is_dir()
    assert (repo / "data" / "runs" / "new-run").is_dir()
    assert not (repo / "data" / "runs" / "delete-old").exists()
    assert repo / "data" / "runs" / "delete-old" in result.deleted_paths


def test_cleanup_apply_skips_off_limits_paths(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    forbidden = repo / "data" / "starters" / "marketing-base"
    forbidden.mkdir(parents=True)

    try:
        assert_cleanup_path_allowed(forbidden, repo_root=repo)
    except ValueError as exc:
        assert "off-limits" in str(exc)
    else:  # pragma: no cover - explicit failure branch for readability
        raise AssertionError("off-limits path was accepted")

    plan = plan_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={MAX_RUNS_ENV_VAR: "1"},
    )
    assert forbidden not in [item.path for item in plan.items]


def test_cleanup_apply_reports_size_freed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    old_run = _make_run(repo, "old-run", size=11, mtime_offset=-100)
    _make_run(repo, "new-run", size=13, mtime_offset=0)
    _write(repo / ".ruff_cache" / "cache.bin", 17)
    expected = path_size_bytes(old_run) + path_size_bytes(repo / ".ruff_cache")

    result = apply_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={MAX_RUNS_ENV_VAR: "1"},
    )

    assert result.freed_bytes == expected
    assert result.deleted_count == 2
    assert not old_run.exists()
    assert not (repo / ".ruff_cache").exists()
