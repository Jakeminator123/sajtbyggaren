"""Tests for local dev artifact cleanup tooling."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.tooling
def test_resolve_evals_dir_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from scripts.cleanup_dev_artifacts import resolve_evals_dir

    target = tmp_path / "custom-evals"
    monkeypatch.setenv("SAJTBYGGAREN_EVALS_DIR", str(target))

    assert resolve_evals_dir() == target.resolve()


@pytest.mark.tooling
def test_default_evals_dir_is_inside_data_evals_artifacts_mini() -> None:
    from scripts.cleanup_dev_artifacts import (
        DEFAULT_EVALS_DIR,
        LEGACY_OUTPUT_EVALS_DIR,
        REPO_ROOT,
        resolve_evals_dir,
    )

    assert resolve_evals_dir() == DEFAULT_EVALS_DIR.resolve()
    assert resolve_evals_dir() == (REPO_ROOT / "data" / "evals" / "artifacts" / "mini").resolve()
    # The pre-migration default still resolves to the external
    # ``../sajtbyggaren-output/.evals/`` so operators with that env-var
    # override keep working.
    assert LEGACY_OUTPUT_EVALS_DIR == (REPO_ROOT.parent / "sajtbyggaren-output" / ".evals")


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "marker.txt").write_text(path.name, encoding="utf-8")
    return path


@pytest.mark.tooling
def test_evals_dry_run_deletes_nothing(tmp_path: Path) -> None:
    from scripts.cleanup_dev_artifacts import cleanup_evals

    evals_dir = tmp_path / ".evals"
    old = _mkdir(evals_dir / "20250101T000000Z-mini-eval")
    keep = _mkdir(evals_dir / "20250102T000000Z-mini-eval")

    report = cleanup_evals(evals_dir=evals_dir, keep=1, apply=False, allow_outside_root=True)

    assert old.exists()
    assert keep.exists()
    assert [entry["name"] for entry in report["wouldDelete"]] == [old.name]
    assert report["deleted"] == []


@pytest.mark.tooling
def test_evals_apply_deletes_only_matching_eval_run_dirs(tmp_path: Path) -> None:
    from scripts.cleanup_dev_artifacts import cleanup_evals

    evals_dir = tmp_path / ".evals"
    delete_me = _mkdir(evals_dir / "20250101T000000Z-mini-eval")
    keep_me = _mkdir(evals_dir / "20250102T000000Z-mini-eval")
    not_eval = _mkdir(evals_dir / "notes")

    report = cleanup_evals(evals_dir=evals_dir, keep=1, apply=True, allow_outside_root=True)

    assert not delete_me.exists()
    assert keep_me.exists()
    assert not_eval.exists()
    assert [entry["name"] for entry in report["deleted"]] == [delete_me.name]


@pytest.mark.tooling
def test_eval_cleanup_never_touches_generated_dir(tmp_path: Path) -> None:
    from scripts.cleanup_dev_artifacts import cleanup_evals

    evals_dir = tmp_path / ".evals"
    generated_dir = tmp_path / ".generated"
    _mkdir(evals_dir / "20250101T000000Z-mini-eval")
    generated_site = _mkdir(generated_dir / "site-a")

    cleanup_evals(evals_dir=evals_dir, keep=0, apply=True, allow_outside_root=True)

    assert generated_site.exists()


@pytest.mark.tooling
def test_python_cache_cleanup_deletes_only_cache_dirs_under_allowed_roots(tmp_path: Path) -> None:
    from scripts.cleanup_dev_artifacts import cleanup_python_cache

    package = tmp_path / "pkg"
    pycache = _mkdir(package / "__pycache__")
    pytest_cache = _mkdir(tmp_path / ".pytest_cache")
    normal_dir = _mkdir(package / "not_cache")

    report = cleanup_python_cache(
        roots=[tmp_path],
        apply=True,
        allow_outside_root=True,
    )

    deleted = {entry["name"] for entry in report["deleted"]}
    assert deleted == {"__pycache__", ".pytest_cache"}
    assert not pycache.exists()
    assert not pytest_cache.exists()
    assert normal_dir.exists()


@pytest.mark.tooling
def test_cleanup_refuses_outside_roots_without_override(tmp_path: Path) -> None:
    from scripts.cleanup_dev_artifacts import cleanup_evals

    evals_dir = tmp_path / ".evals"
    _mkdir(evals_dir / "20250101T000000Z-mini-eval")

    with pytest.raises(SystemExit, match="Refusing cleanup outside"):
        cleanup_evals(evals_dir=evals_dir, keep=0, apply=False)
