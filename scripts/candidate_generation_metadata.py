"""Shared metadata helpers for ``scripts/generate_*_candidate.py`` generators.

Centralises four helpers that were previously duplicated line-for-line
between ``scripts/generate_variant_candidate.py`` and
``scripts/generate_dossier_candidate.py``:

- :func:`repo_or_output_relative` builds a non-absolute path string for
  sidecar metadata fields (``outputPath``/``instructionsPath``).
- :func:`brief_fingerprint` returns the ``sha256:<digest>`` fingerprint
  stored in ``operatorBriefHash`` so the raw operator brief never leaves
  memory.
- :func:`created_at` returns the canonical ISO-8601 UTC timestamp used
  by candidate sidecars (``2026-05-25T03:00:00Z``).
- :func:`guard_candidate_output_dir` refuses any candidate write that
  would land inside the canonical ``packages/generation/orchestration``
  tree (scaffolds or dossiers), keeping the safety-critical check in
  one place.

Keeping these in one module means a future fix to the output-dir guard
or the sidecar path logic applies to both generators automatically. Each
caller still owns its own exception type (the Variant and Dossier
generator-specific generation-error subclasses);
:func:`guard_candidate_output_dir` accepts the exception class as a
parameter so the generator-specific error contract is preserved.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "repo_or_output_relative",
    "brief_fingerprint",
    "created_at",
    "guard_candidate_output_dir",
]


def repo_or_output_relative(
    path: Path,
    *,
    repo_root: Path,
    output_dir: Path,
) -> str:
    """Return a non-absolute path string for metadata sidecars.

    The lookup order is repo root first, then the candidate output dir;
    if ``path`` lives outside both roots (rare, but happens when callers
    pass an absolute ``tmp_path``-style location) the bare filename is
    returned so sidecars never leak absolute paths.
    """
    resolved = path.resolve(strict=False)
    for root in (repo_root.resolve(strict=False), output_dir.resolve(strict=False)):
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            continue
    return path.name


def brief_fingerprint(brief: str) -> str:
    """Return ``sha256:<digest>`` for the trimmed operator brief."""
    digest = hashlib.sha256(brief.strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def created_at() -> str:
    """Return the canonical sidecar ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def guard_candidate_output_dir(
    output_dir: Path,
    *,
    forbidden_roots: Iterable[Path],
    error_cls: type[Exception],
    kind: str,
) -> None:
    """Refuse candidate writes inside canonical orchestration roots.

    Raises ``error_cls`` (typically the generator's own generation-error
    subclass) so each CLI keeps its existing exception contract;
    ``kind`` is interpolated into the message so the operator sees
    "Variant candidate" vs "Dossier candidate" in the error text.
    """
    resolved_output = output_dir.resolve(strict=False)
    for forbidden_root in forbidden_roots:
        resolved_forbidden = forbidden_root.resolve(strict=False)
        if (
            resolved_output == resolved_forbidden
            or resolved_forbidden in resolved_output.parents
        ):
            raise error_cls(
                f"Refusing to write {kind} candidate output under canonical "
                f"orchestration path: {resolved_output}"
            )
