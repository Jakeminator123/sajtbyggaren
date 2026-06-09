"""Shared constants and helpers for Viewser (operator UI) tests.

These were previously defined at module scope inside the monolithic
``tests/test_viewser_files.py``. They now live here so the topic-focused
``tests/test_viewser_*.py`` files can share a single source of truth.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
NAMING_PATH = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"


def is_tracked_in_git(path: Path) -> bool:
    """Return True iff ``path`` is tracked by git.

    Uses ``git ls-files`` which returns the path if it is tracked and an
    empty string otherwise. Gitignored files that exist on disk are not
    tracked and therefore return False. This lets a developer keep a
    local ``.env.local`` without breaking the "not committed" guard.
    """
    rel = path.relative_to(REPO_ROOT).as_posix()
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", rel],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0
