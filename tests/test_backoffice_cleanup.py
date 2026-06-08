"""Regression tests for Backoffice maintenance cleanup helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path

from backoffice.maintenance import (
    apply_safe_cleanup,
    apply_warning_cleanup,
    assert_cleanup_path_allowed,
    path_size_bytes,
    plan_safe_cleanup,
    plan_warning_cleanup,
)
from packages.generation.maintenance import MAX_GENERATED_ENV_VAR, MAX_RUNS_ENV_VAR
from scripts.run_golden_path_eval import MAX_GOLDEN_PATH_EVALS_ENV


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


def _make_eval_generated(repo: Path, name: str, *, size: int, mtime_offset: float) -> Path:
    eval_dir = repo / "data" / "evals" / "generated" / name
    _write(eval_dir / "site-a" / "package.json", size)
    when = time.time() + mtime_offset
    _set_mtime(eval_dir, when)
    return eval_dir


def _make_golden_path_eval(repo: Path, name: str, *, size: int, mtime_offset: float) -> Path:
    eval_dir = repo / "data" / "evals" / "golden-path" / name
    _write(eval_dir / "cases" / "case.json", size)
    _write(repo / "data" / "evals" / "golden-path" / f"{name}.json", 2)
    _write(repo / "data" / "evals" / "golden-path" / f"{name}.md", 2)
    when = time.time() + mtime_offset
    _set_mtime(eval_dir, when)
    return eval_dir


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


def test_cleanup_plans_eval_generated_and_golden_path_retention(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    old_eval_generated = _make_eval_generated(repo, "eval-old", size=11, mtime_offset=-100)
    _make_eval_generated(repo, "eval-new", size=13, mtime_offset=0)
    old_golden = _make_golden_path_eval(repo, "golden-old", size=17, mtime_offset=-100)
    _make_golden_path_eval(repo, "golden-new", size=19, mtime_offset=0)

    plan = plan_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={
            MAX_GENERATED_ENV_VAR: "1",
            MAX_GOLDEN_PATH_EVALS_ENV: "1",
        },
    )

    assert old_eval_generated in [item.path for item in plan.items if item.kind == "eval-generated"]
    assert old_golden in [item.path for item in plan.items if item.kind == "golden-path-eval"]
    assert old_eval_generated.exists()
    assert old_golden.exists()


def test_cleanup_apply_removes_eval_generated_and_golden_path_summaries(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    old_eval_generated = _make_eval_generated(repo, "eval-old", size=11, mtime_offset=-100)
    _make_eval_generated(repo, "eval-new", size=13, mtime_offset=0)
    old_golden = _make_golden_path_eval(repo, "golden-old", size=17, mtime_offset=-100)
    _make_golden_path_eval(repo, "golden-new", size=19, mtime_offset=0)
    expected = path_size_bytes(old_eval_generated) + path_size_bytes(old_golden)

    result = apply_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={
            MAX_GENERATED_ENV_VAR: "1",
            MAX_GOLDEN_PATH_EVALS_ENV: "1",
        },
        skip_generated_live_check=True,
    )

    assert old_eval_generated in result.deleted_paths
    assert old_golden in result.deleted_paths
    assert result.freed_bytes == expected
    assert not old_eval_generated.exists()
    assert not old_golden.exists()
    assert not (repo / "data" / "evals" / "golden-path" / "golden-old.json").exists()
    assert not (repo / "data" / "evals" / "golden-path" / "golden-old.md").exists()


def test_starter_build_cache_planned_allowed_but_source_denied(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    starter = repo / "data" / "starters" / "portfolio-base"
    _write(starter / ".next" / "build.txt", 10)
    _write(starter / "node_modules" / "pkg" / "index.js", 10)
    _write(starter / "package.json", 10)  # tracked template source -> protected

    plan = plan_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={},
    )
    planned = {item.path for item in plan.items if item.kind == "starter-cache"}
    assert (starter / ".next") in planned
    assert (starter / "node_modules") in planned

    # The build artifacts are allowed; the starter source stays off-limits.
    assert_cleanup_path_allowed(starter / ".next", repo_root=repo)
    assert_cleanup_path_allowed(starter / "node_modules", repo_root=repo)
    try:
        assert_cleanup_path_allowed(starter / "package.json", repo_root=repo)
    except ValueError as exc:
        assert "off-limits" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("starter source file was accepted")

    result = apply_safe_cleanup(
        repo_root=repo,
        generated_dir=tmp_path / "generated",
        environ={},
    )
    assert not (starter / ".next").exists()
    assert not (starter / "node_modules").exists()
    assert (starter / "package.json").exists()
    assert (starter / ".next") in result.deleted_paths


def test_ovrigt_large_artifact_is_warning_gated(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _make_repo(tmp_path)
    monkeypatch.setattr("backoffice.maintenance._OVRIGT_LARGE_BYTES", 8)
    ovrigt = repo / "övrigt"
    _write(ovrigt / "chrome-win.zip", 20)  # >= threshold -> offered
    _write(ovrigt / "notes.md", 3)  # < threshold -> never offered

    plan = plan_warning_cleanup(repo_root=repo, environ={})
    artifact_paths = [item.path for item in plan.items if item.kind == "ovrigt-artifact"]
    assert (ovrigt / "chrome-win.zip") in artifact_paths
    assert (ovrigt / "notes.md") not in [item.path for item in plan.items]

    # Gate: övrigt is a warning target - needs explicit confirmation.
    try:
        assert_cleanup_path_allowed(ovrigt / "chrome-win.zip", repo_root=repo)
    except ValueError as exc:
        assert "Warning target" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("övrigt artifact accepted without warning confirmation")
    assert_cleanup_path_allowed(
        ovrigt / "chrome-win.zip", repo_root=repo, allow_warning_targets=True
    )

    # Without the include flag the artifact is skipped; with it, deleted.
    apply_warning_cleanup(repo_root=repo, environ={}, include_ovrigt=False)
    assert (ovrigt / "chrome-win.zip").exists()
    result = apply_warning_cleanup(repo_root=repo, environ={}, include_ovrigt=True)
    assert not (ovrigt / "chrome-win.zip").exists()
    assert (ovrigt / "notes.md").exists()
    assert (ovrigt / "chrome-win.zip") in result.deleted_paths
