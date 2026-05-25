"""Unit tests for the shared repo-root resolver (`scripts/_repo_root.py`).

Background: before this helper landed, several scripts used
``Path(env).resolve()`` for ``SAJTBYGGAREN_GENERATED_DIR`` /
``SAJTBYGGAREN_EVALS_DIR``. That collapses relative env values against
the process cwd, so the Python builder writing from a git worktree (or
from ``apps/viewser/``) wrote to a different directory than the Node
viewser tried to read from. This test suite locks in the new contract:

1. Absolute paths pass through unchanged.
2. Relative paths resolve against the repo root, NOT cwd. Tests use
   ``monkeypatch.chdir(tmp_path)`` to prove cwd-independence.
3. Unset / empty / whitespace-only fall back to a caller-supplied
   default.
4. Trailing whitespace in env values is ignored.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts._repo_root import REPO_ROOT, find_repo_root, resolve_path_setting


@pytest.mark.tooling
def test_repo_root_points_at_pyproject_marker() -> None:
    """REPO_ROOT must be the directory that contains pyproject.toml."""
    assert (REPO_ROOT / "pyproject.toml").is_file()


@pytest.mark.tooling
def test_repo_root_is_absolute() -> None:
    assert REPO_ROOT.is_absolute()


@pytest.mark.tooling
def test_find_repo_root_accepts_file_path() -> None:
    found = find_repo_root(REPO_ROOT / "scripts" / "_repo_root.py")
    assert found == REPO_ROOT


@pytest.mark.tooling
def test_find_repo_root_accepts_directory_path() -> None:
    found = find_repo_root(REPO_ROOT / "scripts")
    assert found == REPO_ROOT


@pytest.mark.tooling
def test_find_repo_root_raises_outside_repo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        find_repo_root(tmp_path)


@pytest.mark.tooling
def test_resolve_path_setting_passes_absolute_unchanged(tmp_path: Path) -> None:
    absolute = tmp_path / "explicit-absolute"
    resolved = resolve_path_setting(str(absolute), default="ignored")
    assert resolved == absolute
    assert resolved.is_absolute()


@pytest.mark.tooling
def test_resolve_path_setting_relative_anchors_on_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative env values must NOT collapse against cwd.

    Without the helper, ``Path("relative/dir").resolve()`` returns
    ``tmp_path / "relative" / "dir"`` after a chdir. The new contract
    pins the result to ``REPO_ROOT / "relative" / "dir"`` regardless.
    """
    monkeypatch.chdir(tmp_path)
    resolved = resolve_path_setting("relative/dir", default="ignored")
    assert resolved == (REPO_ROOT / "relative" / "dir").resolve()
    assert tmp_path not in resolved.parents


@pytest.mark.tooling
def test_resolve_path_setting_unset_uses_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = resolve_path_setting(None, default="../sibling/.generated")
    assert resolved == (REPO_ROOT / ".." / "sibling" / ".generated").resolve()


@pytest.mark.tooling
def test_resolve_path_setting_empty_string_uses_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = resolve_path_setting("", default="../sibling/.generated")
    assert resolved == (REPO_ROOT / ".." / "sibling" / ".generated").resolve()


@pytest.mark.tooling
def test_resolve_path_setting_whitespace_uses_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = resolve_path_setting("   ", default="../sibling/.generated")
    assert resolved == (REPO_ROOT / ".." / "sibling" / ".generated").resolve()


@pytest.mark.tooling
def test_resolve_path_setting_trims_whitespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Operators often paste env values with stray spaces; treat them as the value."""
    monkeypatch.chdir(tmp_path)
    resolved = resolve_path_setting("  relative/dir\n", default="ignored")
    assert resolved == (REPO_ROOT / "relative" / "dir").resolve()


@pytest.mark.tooling
def test_resolve_path_setting_absolute_default_used_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An absolute Path default must be honoured verbatim."""
    monkeypatch.chdir(tmp_path)
    absolute_default = tmp_path / "fallback"
    resolved = resolve_path_setting(None, default=absolute_default)
    assert resolved == absolute_default


@pytest.mark.tooling
def test_build_site_resolver_is_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end check: ``scripts.build_site.resolve_generated_dir`` must not
    drift when invoked from a different cwd.

    This is the regression test that pins the original bug: the builder
    used to share its env-var contract with viewser only because both
    happened to be invoked from canonical roots. Under a worktree or
    ``apps/viewser/`` cwd, the two ends silently diverged.
    """
    from scripts.build_site import resolve_generated_dir

    monkeypatch.setenv("SAJTBYGGAREN_GENERATED_DIR", "../sajtbyggaren-output/.generated")
    monkeypatch.chdir(tmp_path)
    resolved = resolve_generated_dir()
    expected = (REPO_ROOT / ".." / "sajtbyggaren-output" / ".generated").resolve()
    assert resolved == expected


@pytest.mark.tooling
def test_prune_generated_previews_resolver_is_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.prune_generated_previews import resolve_generated_dir

    monkeypatch.setenv("SAJTBYGGAREN_GENERATED_DIR", "../sajtbyggaren-output/.generated")
    monkeypatch.chdir(tmp_path)
    resolved = resolve_generated_dir()
    expected = (REPO_ROOT / ".." / "sajtbyggaren-output" / ".generated").resolve()
    assert resolved == expected


@pytest.mark.tooling
def test_verify_run_find_generated_dir_is_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.verify_run import find_generated_dir

    monkeypatch.setenv("SAJTBYGGAREN_GENERATED_DIR", "../sajtbyggaren-output/.generated")
    monkeypatch.chdir(tmp_path)
    resolved = find_generated_dir("painter-palma")
    expected = (
        REPO_ROOT / ".." / "sajtbyggaren-output" / ".generated" / "painter-palma"
    ).resolve()
    assert resolved == expected


@pytest.mark.tooling
def test_cleanup_dev_artifacts_resolvers_are_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.cleanup_dev_artifacts import (
        resolve_evals_dir,
        resolve_generated_dir,
    )

    monkeypatch.setenv("SAJTBYGGAREN_GENERATED_DIR", "../sajtbyggaren-output/.generated")
    monkeypatch.setenv("SAJTBYGGAREN_EVALS_DIR", "../sajtbyggaren-output/.evals")
    monkeypatch.chdir(tmp_path)

    generated = resolve_generated_dir()
    evals = resolve_evals_dir()

    expected_generated = (
        REPO_ROOT / ".." / "sajtbyggaren-output" / ".generated"
    ).resolve()
    expected_evals = (
        REPO_ROOT / ".." / "sajtbyggaren-output" / ".evals"
    ).resolve()
    assert generated == expected_generated
    assert evals == expected_evals


@pytest.mark.tooling
def test_mini_eval_resolver_is_cwd_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.mini_eval import resolve_evals_dir

    monkeypatch.setenv("SAJTBYGGAREN_EVALS_DIR", "../sajtbyggaren-output/.evals")
    monkeypatch.chdir(tmp_path)
    resolved = resolve_evals_dir()
    expected = (REPO_ROOT / ".." / "sajtbyggaren-output" / ".evals").resolve()
    assert resolved == expected
