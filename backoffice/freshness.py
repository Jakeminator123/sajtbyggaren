"""Freshness badges for backoffice views, driven by the governance registry.

A view's freshness is derived purely from its ``backoffice-views.v1.json``
entry (``status`` + ``readsFrom``) and what is actually present on disk — so no
view can pretend to be current:

- green  (🟢) = ``active`` and at least one data source has data on disk.
- grey   (⚪) = ``active`` but every data source is empty/missing.
- green  (🟢) = ``diagnostic`` (runs live checks, has no stored surface to be
                stale against).
- yellow (🟡) = ``stale`` or ``legacy`` (drifted / retirement candidate).

This module is pure (no Streamlit) so it is fully unit-testable. The view layer
turns a :class:`Freshness` into a small badge/table cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Freshness:
    """Resolved freshness for one view entry."""

    state: str  # "green" | "grey" | "yellow"
    label: str  # Swedish operator label
    emoji: str  # 🟢 / ⚪ / 🟡

    @property
    def badge(self) -> str:
        """Compact ``emoji label`` string for table cells."""
        return f"{self.emoji} {self.label}"


_GREEN = ("green", "🟢")
_GREY = ("grey", "⚪")
_YELLOW = ("yellow", "🟡")


def _source_has_data(repo_root: Path, source: str) -> bool:
    """True when a repo-relative data source exists and is non-empty.

    A directory counts as having data when it contains at least one file
    (recursively); a file counts when it exists and is non-empty.
    """
    path = repo_root / source
    if path.is_file():
        try:
            return path.stat().st_size > 0
        except OSError:
            return False
    if path.is_dir():
        return any(child.is_file() for child in path.rglob("*"))
    return False


def compute_freshness(entry: dict, repo_root: Path) -> Freshness:
    """Resolve the freshness badge for a single ``backoffice-views.v1`` entry."""
    status = entry.get("status", "active")

    if status in {"stale", "legacy"}:
        return Freshness(_YELLOW[0], "driftar / legacy", _YELLOW[1])

    if status == "diagnostic":
        return Freshness(_GREEN[0], "live-diagnostik", _GREEN[1])

    # status == "active" (or unknown -> treat as active and judge by data).
    reads_from = entry.get("readsFrom", []) or []
    has_data = any(_source_has_data(repo_root, source) for source in reads_from)
    if has_data:
        return Freshness(_GREEN[0], "aktuell", _GREEN[1])
    return Freshness(_GREY[0], "tom datakälla", _GREY[1])
