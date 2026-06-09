"""Tests for the single-source repo-root .env loader + generated-dir resolution.

``scripts/build_site.py:load_repo_root_env`` lets an operator keep shared
builder settings (``SAJTBYGGAREN_GENERATED_DIR`` etc.) in ONE repo-root ``.env``
file. It is dependency-free, file-optional and never overrides a value already
in ``os.environ``. ``resolve_generated_dir`` resolves a relative value against
the repo root; the Node preview resolver (apps/viewser/lib/generated-dir.ts)
mirrors the same contract so the builder and the preview always agree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.build_site as build_site  # noqa: E402


def _restore_env(applied: list[str], previous: dict[str, str | None]) -> None:
    """Undo os.environ mutations a test triggered so the suite stays isolated."""
    for key in applied:
        if previous.get(key) is None:
            build_site.os.environ.pop(key, None)
        else:
            build_site.os.environ[key] = previous[key]  # type: ignore[assignment]


def test_missing_env_is_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No .env at the repo root -> no-op (CI/test-safe), returns []."""
    monkeypatch.setattr(build_site, "REPO_ROOT", tmp_path)
    assert build_site.load_repo_root_env() == []


def test_loads_keys_and_os_environ_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Loads missing keys into os.environ, but never overrides an existing one."""
    (tmp_path / ".env").write_text(
        "SAJTBYGGAREN_GENERATED_DIR=data/output/.generated\n"
        "ALREADY_SET=from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_site, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("ALREADY_SET", "from-shell")
    monkeypatch.delenv("SAJTBYGGAREN_GENERATED_DIR", raising=False)

    previous = {
        "SAJTBYGGAREN_GENERATED_DIR": build_site.os.environ.get(
            "SAJTBYGGAREN_GENERATED_DIR"
        ),
    }
    applied = build_site.load_repo_root_env()
    try:
        # The unset key is loaded from .env.
        assert "SAJTBYGGAREN_GENERATED_DIR" in applied
        assert (
            build_site.os.environ["SAJTBYGGAREN_GENERATED_DIR"]
            == "data/output/.generated"
        )
        # The shell-set key wins (NOT overridden, NOT in the applied list).
        assert build_site.os.environ["ALREADY_SET"] == "from-shell"
        assert "ALREADY_SET" not in applied
    finally:
        _restore_env(applied, previous)


def test_parses_export_quotes_and_comments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The minimal parser handles `export `, quotes and trailing comments."""
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "# a comment line",
                "export EXPORTED=plain",
                'QUOTED="value with spaces" # trailing note',
                "WITH_COMMENT=bare # note",
                "EMPTY=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_site, "REPO_ROOT", tmp_path)
    for key in ("EXPORTED", "QUOTED", "WITH_COMMENT", "EMPTY"):
        monkeypatch.delenv(key, raising=False)

    applied = build_site.load_repo_root_env()
    try:
        assert build_site.os.environ["EXPORTED"] == "plain"
        assert build_site.os.environ["QUOTED"] == "value with spaces"
        assert build_site.os.environ["WITH_COMMENT"] == "bare"
        assert build_site.os.environ["EMPTY"] == ""
    finally:
        _restore_env(applied, dict.fromkeys(applied))


def test_resolve_generated_dir_relative_is_repo_root_relative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A relative SAJTBYGGAREN_GENERATED_DIR resolves against the repo root.

    This is the Python half of the cross-language contract the Node preview
    resolver (apps/viewser/lib/generated-dir.ts) mirrors, so the builder writes
    and the preview reads the exact same absolute directory.
    """
    monkeypatch.setattr(build_site, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("SAJTBYGGAREN_GENERATED_DIR", "data/output/.generated")
    resolved = build_site.resolve_generated_dir()
    assert resolved == (tmp_path / "data" / "output" / ".generated").resolve()


def test_resolve_generated_dir_absolute_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An absolute override is returned as-is (matches the Node resolver)."""
    abs_dir = (tmp_path / "abs" / "generated").resolve()
    monkeypatch.setenv("SAJTBYGGAREN_GENERATED_DIR", str(abs_dir))
    assert build_site.resolve_generated_dir() == abs_dir
