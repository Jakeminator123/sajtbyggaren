"""Shared repo-root resolution for scripts/ and packages/generation.

Why this exists:

Several scripts duplicated ``REPO_ROOT = Path(__file__).resolve().parent.parent``
and a ``resolve_*_dir`` helper that treated relative env-var values as
``Path(env).resolve()`` -- i.e. relative-to-cwd. That silently broke when
a script was invoked from a git worktree, from ``apps/viewser/``, or
from any other subdirectory: the resolved path landed somewhere the
sister consumer (Python builder vs. Node viewser) never expected, so the
two ends of the dev-preview pipeline could write to and read from
different directories without any error.

This module centralises three things so every call site agrees:

1. :func:`find_repo_root` -- a walk-up from a given file/dir that
   anchors on ``pyproject.toml`` (canonical marker for this repo). The
   walk has a small depth cap so a misconfigured caller bails out fast
   instead of walking to ``/``.
2. :data:`REPO_ROOT` -- computed once at import time from this
   module's own file location, NOT from cwd. Importers get the same
   value regardless of how they were launched.
3. :func:`resolve_path_setting` -- applies the documented contract for
   env-var / CLI path overrides: absolute pass-through, relative
   anchored on :data:`REPO_ROOT`, unset/whitespace falls back to a
   caller-supplied default (also run through the same contract).
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["REPO_ROOT", "find_repo_root", "resolve_path_setting"]


_REPO_ROOT_MARKER = "pyproject.toml"
_MAX_WALK_DEPTH = 8


def find_repo_root(start: str | os.PathLike[str]) -> Path:
    """Walk upward from ``start`` until ``pyproject.toml`` is found.

    ``start`` may be a file or a directory. Files are normalised to
    their parent directory before the walk begins. The walk stops once
    a directory containing ``pyproject.toml`` is found, when the
    filesystem root is reached, or after ``_MAX_WALK_DEPTH`` parents
    have been checked -- whichever happens first. The depth cap is a
    defensive guard so a caller running from a sandboxed temp directory
    outside the repo does not silently walk all the way to ``/``.

    Raises :class:`FileNotFoundError` when no marker is found within
    the depth cap.
    """
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for _ in range(_MAX_WALK_DEPTH + 1):
        if (current / _REPO_ROOT_MARKER).is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise FileNotFoundError(
        f"Could not locate repo root (no {_REPO_ROOT_MARKER!r} marker "
        f"found within {_MAX_WALK_DEPTH} levels above {start})."
    )


REPO_ROOT = find_repo_root(Path(__file__))


def resolve_path_setting(
    value: str | os.PathLike[str] | None,
    *,
    default: str | os.PathLike[str],
) -> Path:
    """Resolve an operator-supplied path setting against the repo root.

    Contract (mirrors ``apps/viewser/lib/local-preview-server.ts``):

    1. Absolute path -> returned unchanged (preserves operator override
       to a totally different location, e.g. ``D:\\stuff\\.generated``).
    2. Relative path -> resolved against :data:`REPO_ROOT`, **not**
       cwd, so the same env var means the same directory whether the
       script is launched from the repo root, from a worktree, from
       ``apps/viewser/`` or from any subdirectory.
    3. Unset / empty / whitespace-only -> falls back to ``default``,
       which itself is run through the same logic (so callers can
       safely pass a relative default like
       ``"../sajtbyggaren-output/.generated"``).

    All return paths are absolute and normalised. ``~`` is expanded.
    """
    candidate: str | os.PathLike[str] | None = value
    if isinstance(candidate, str):
        candidate = candidate.strip() or None
    if candidate is None:
        candidate = default
    resolved = Path(candidate).expanduser()
    if not resolved.is_absolute():
        resolved = (REPO_ROOT / resolved).resolve()
    return resolved
