"""Immutable build directories + atomic active-build pointer (B157 level 4, Stage A).

Background (``docs/gaps/GAP-windows-safe-rebuild-pipeline.md``): the Builder
used to rebuild in place at ``<generated>/<siteId>/`` while a live
``next start``/``next dev`` preview held that exact directory open. On Windows
the native ``next-swc.win32-x64-msvc.node`` binary is hard-locked, so
``copy_starter()``'s ``shutil.rmtree`` failed with ``PermissionError:
[WinError 5]`` (registered as B157). The architectural fix is to make every
build immutable: write into ``<generated>/<siteId>/builds/<buildId>/`` and
publish the active build via a pointer file. Builder and preview then never
touch the same files.

On-disk layout::

    <generated>/<siteId>/
      builds/
        20260531T184500Z/        <- immutable build (this run wrote here)
        20260531T184500Z-01/     <- a second build in the same UTC second
      current.json               <- pointer to the active build

``current.json`` schema (locked in Stage A)::

    {
      "activeBuildId": "20260531T184500Z",
      "updatedAt": "<ISO-8601 UTC>",
      "buildPath": "builds/20260531T184500Z"
    }

This module is intentionally dependency-free (stdlib only) so it can be
imported from ``scripts/build_site.py`` without pulling in the rest of the
generation package. ``scripts/build_site.py`` owns the build orchestration
and calls these helpers; no build-flow logic lives here, and no pointer/
build-id logic lives in the monolith.

Stage A scope: this module does not garbage-collect old builds and does not
touch the preview UI. Retention/GC is Stage B.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

#: Name of the pointer file that lives directly under ``<generated>/<siteId>/``.
POINTER_FILENAME = "current.json"

#: Directory under ``<generated>/<siteId>/`` that holds the immutable builds.
BUILDS_DIRNAME = "builds"

# A build id is YYYYMMDDTHHMMSSZ with an optional -NN collision suffix.
# ``read_active_build_dir`` validates the id from ``current.json`` against this
# pattern before joining it to a path so a tampered or corrupt pointer cannot
# trigger directory traversal (no ``/``, ``\`` or ``..`` can match).
_BUILD_ID_RE = re.compile(r"^\d{8}T\d{6}Z(?:-\d{2,})?$")


def new_build_id(
    now: datetime | None = None,
    *,
    exists: Callable[[str], bool] | None = None,
) -> str:
    """Return a fresh build id YYYYMMDDTHHMMSSZ (UTC, second precision).

    ``now`` defaults to the current UTC time; tests pass a fixed
    ``datetime`` to make the id deterministic. Aware datetimes are converted
    to UTC; naive datetimes are assumed to already be UTC.

    Two builds for the same site can land in the same wall-clock second
    (follow-ups, batch evals). ``exists`` is an optional predicate that
    reports whether a candidate id already has a build directory on disk; when
    a collision is detected a ``-NN`` suffix (``-01``, ``-02``, ...) is
    appended until a free id is found. The caller supplies the predicate so
    the filesystem lookup stays in the build orchestrator, not in this module.
    """
    moment = now or datetime.now(UTC)
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    base = moment.strftime("%Y%m%dT%H%M%SZ")
    if exists is None or not exists(base):
        return base
    for suffix in range(1, 100):
        candidate = f"{base}-{suffix:02d}"
        if not exists(candidate):
            return candidate
    raise RuntimeError(
        f"Could not allocate a unique build id for {base}: 99 collisions in the "
        "same second. This points at a runaway build loop, not normal usage."
    )


def build_dir_for(generated_root: Path | str, site_id: str, build_id: str) -> Path:
    """Return ``<generated_root>/<site_id>/builds/<build_id>``.

    This is the immutable directory a single build writes into. The path is
    constructed, not created; the caller materialises it (``copy_starter``
    creates it via ``shutil.copytree``).
    """
    return Path(generated_root) / site_id / BUILDS_DIRNAME / build_id


def write_active_pointer(site_dir: Path | str, build_id: str, build_path: str) -> None:
    """Atomically point ``<site_dir>/current.json`` at ``build_id``.

    Writes ``current.json.tmp-<pid>`` in the *same* directory and then
    ``os.replace()`` over the real pointer. ``os.replace`` is atomic on both
    Windows and POSIX as long as source and destination are on the same
    volume, which is guaranteed here because the temp file is created in the
    same directory as the target. A process killed mid-swap therefore leaves
    the previous ``current.json`` intact (and at worst an orphan temp file),
    never a half-written pointer.

    ``build_path`` is the pointer's relative ``buildPath`` value (e.g.
    ``"builds/20260531T184500Z"``); the caller passes it so this module does
    not re-derive the layout.
    """
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "activeBuildId": build_id,
        "updatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "buildPath": build_path,
    }
    tmp_path = site_dir / f"{POINTER_FILENAME}.tmp-{os.getpid()}"
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.replace(tmp_path, site_dir / POINTER_FILENAME)
    except OSError:
        # Best-effort cleanup so a failed swap does not litter the site dir
        # with temp files; re-raise so the caller sees the real failure.
        tmp_path.unlink(missing_ok=True)
        raise


def read_active_build_dir(site_dir: Path | str) -> Path | None:
    """Return the active build directory for ``site_dir`` or ``None``.

    Reads ``<site_dir>/current.json`` and returns
    ``<site_dir>/builds/<activeBuildId>`` when the pointer is valid *and* that
    directory exists. Returns ``None`` for every failure mode (missing or
    unreadable pointer, malformed JSON, missing/invalid ``activeBuildId``, or a
    pointer that references a build directory that no longer exists) so callers
    can cleanly fall back to a legacy flat layout.
    """
    site_dir = Path(site_dir)
    pointer = site_dir / POINTER_FILENAME
    try:
        raw = pointer.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    build_id = payload.get("activeBuildId")
    if not isinstance(build_id, str) or not _BUILD_ID_RE.match(build_id):
        return None
    # Cross-validate the decorative ``buildPath`` against ``activeBuildId``.
    # ``write_active_pointer`` always writes ``builds/<activeBuildId>``; if a
    # tampered or half-updated pointer has the two fields disagreeing the
    # pointer is inconsistent, so reject it rather than silently trusting
    # ``activeBuildId``. ``buildPath`` is optional (older pointers may omit it):
    # only a present-and-mismatching value rejects.
    build_path = payload.get("buildPath")
    if build_path is not None and build_path != f"{BUILDS_DIRNAME}/{build_id}":
        return None
    build_dir = site_dir / BUILDS_DIRNAME / build_id
    if not build_dir.is_dir():
        return None
    return build_dir
