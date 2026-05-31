"""Tests for scripts/gc_old_builds.py - B157 level 4, Stage B delayed GC.

Covers the retention policy (active build, <24h, keep-latest-5), the
conservative skips (missing/corrupt current.json, legacy flat layout), the
dry-run default vs --apply, and robust deletes (a locked build is skipped and
the GC keeps going).

The locked-build case simulates the lock by making ``shutil.rmtree`` raise
``OSError`` for one build rather than holding a real OS file handle: a real
handle only blocks deletion on Windows (POSIX unlinks open files), so a
handle-based test would pass falsely on Linux CI. Monkeypatching rmtree
exercises the exact error-handling branch deterministically on every OS.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from packages.generation.build.immutable_builds import write_active_pointer
from scripts.gc_old_builds import (
    DECISION_DELETE_FAILED,
    DECISION_DELETED,
    DECISION_KEEP_ACTIVE,
    DECISION_KEEP_LATEST,
    DECISION_KEEP_RECENT,
    DECISION_WOULD_DELETE,
    SKIP_NO_BUILDS_DIR,
    SKIP_NO_VALID_POINTER,
    main,
    run_gc,
)

HOUR = 3600.0


def _bid(index: int) -> str:
    """Return a valid build id; the embedded time is just a unique label
    (GC ranks by directory mtime, not by the id), so any 0..59 index works."""
    return f"20260101T0000{index:02d}Z"


def _make_build(
    site_dir: Path, build_id: str, *, age_hours: float, now: float
) -> Path:
    """Create ``<site_dir>/builds/<build_id>/`` with a controlled mtime."""
    build_dir = site_dir / "builds" / build_id
    (build_dir / "app").mkdir(parents=True)
    (build_dir / "app" / "page.tsx").write_text(
        "export default function Page() { return null; }", encoding="utf-8"
    )
    swc = build_dir / "node_modules" / "@next" / "swc-win32-x64-msvc"
    swc.mkdir(parents=True)
    (swc / "next-swc.win32-x64-msvc.node").write_bytes(b"\x00fake-native\x00")
    timestamp = now - age_hours * HOUR
    os.utime(build_dir, (timestamp, timestamp))
    return build_dir


def _make_site(
    generated: Path,
    site_id: str,
    ages_by_id: dict[str, float],
    active: str | None,
    now: float,
) -> Path:
    """Create a Stage-A site with builds at the given ages + optional pointer."""
    site_dir = generated / site_id
    for build_id, age in ages_by_id.items():
        _make_build(site_dir, build_id, age_hours=age, now=now)
    if active is not None:
        write_active_pointer(site_dir, active, f"builds/{active}")
    return site_dir


# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------


def test_active_build_preserved_even_if_old_and_outside_top5(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(7)]
    # All older than 24h; ages 25h..31h so the oldest is well outside top-5.
    ages = {ids[i]: 25.0 + i for i in range(7)}
    active = ids[6]  # the OLDEST build is the active one
    site_dir = _make_site(generated, "site-a", ages, active, now)

    report = run_gc(generated, apply=True, keep_latest=5, now=now)

    assert (site_dir / "builds" / active).is_dir(), "active build must never be deleted"
    decisions = {d.build_id: d.decision for d in report.decisions}
    assert decisions[active] == DECISION_KEEP_ACTIVE


def test_build_within_24h_preserved(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(6)]
    # All younger than 24h (ages 1h..6h). The 6th-newest is outside top-5 but
    # must still be kept by the <24h rule.
    ages = {ids[i]: float(i + 1) for i in range(6)}
    active = ids[0]
    site_dir = _make_site(generated, "site-a", ages, active, now)

    report = run_gc(generated, apply=True, keep_latest=5, now=now)

    for build_id in ids:
        assert (site_dir / "builds" / build_id).is_dir()
    decisions = {d.build_id: d.decision for d in report.decisions}
    # ids[5] is the oldest (outside top-5) -> kept only because it is < 24h.
    assert decisions[ids[5]] == DECISION_KEEP_RECENT
    assert report.deleted_count == 0


def test_keep_latest_5_gcs_the_sixth_oldest(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(6)]
    # All older than 24h so the only protection is keep-latest.
    ages = {ids[i]: 25.0 + i for i in range(6)}
    active = ids[0]  # newest, so the active build is inside top-5
    site_dir = _make_site(generated, "site-a", ages, active, now)

    report = run_gc(generated, apply=True, keep_latest=5, now=now)

    for build_id in ids[:5]:
        assert (site_dir / "builds" / build_id).is_dir(), "5 most recent kept"
    assert not (site_dir / "builds" / ids[5]).exists(), "6th oldest GC'd"
    decisions = {d.build_id: d.decision for d in report.decisions}
    assert decisions[ids[0]] == DECISION_KEEP_ACTIVE
    assert decisions[ids[1]] == DECISION_KEEP_LATEST
    assert decisions[ids[5]] == DECISION_DELETED


# ---------------------------------------------------------------------------
# Conservative skips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["missing", "corrupt"])
def test_missing_or_corrupt_pointer_deletes_nothing(tmp_path: Path, mode: str) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(6)]
    ages = {ids[i]: 25.0 + i for i in range(6)}  # all old -> would be GC'd
    site_dir = _make_site(generated, "site-a", ages, active=None, now=now)
    if mode == "corrupt":
        (site_dir / "current.json").write_text("{ not valid json", encoding="utf-8")

    report = run_gc(generated, apply=True, keep_latest=5, now=now)

    for build_id in ids:
        assert (site_dir / "builds" / build_id).is_dir(), "conservative: keep all"
    assert report.deleted_count == 0
    assert report.decisions == []
    assert ("site-a", SKIP_NO_VALID_POINTER) in report.skipped_sites


def test_legacy_flat_layout_site_untouched(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    legacy = generated / "legacy-site"
    (legacy / ".next").mkdir(parents=True)
    (legacy / "app").mkdir()
    (legacy / "app" / "page.tsx").write_text("legacy", encoding="utf-8")

    report = run_gc(generated, apply=True, now=now)

    assert (legacy / ".next").is_dir()
    assert (legacy / "app" / "page.tsx").is_file()
    assert report.decisions == []
    assert ("legacy-site", SKIP_NO_BUILDS_DIR) in report.skipped_sites


# ---------------------------------------------------------------------------
# Dry-run vs apply
# ---------------------------------------------------------------------------


def test_dry_run_default_then_apply(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(6)]
    ages = {ids[i]: 25.0 + i for i in range(6)}
    active = ids[0]
    site_dir = _make_site(generated, "site-a", ages, active, now)

    dry = run_gc(generated, apply=False, keep_latest=5, now=now)
    assert (site_dir / "builds" / ids[5]).is_dir(), "dry-run must not delete"
    assert dry.would_delete_count == 1
    assert dry.deleted_count == 0
    dry_decisions = {d.build_id: d.decision for d in dry.decisions}
    assert dry_decisions[ids[5]] == DECISION_WOULD_DELETE

    applied = run_gc(generated, apply=True, keep_latest=5, now=now)
    assert not (site_dir / "builds" / ids[5]).exists(), "--apply deletes"
    assert applied.deleted_count == 1


def test_cli_main_defaults_to_dry_run(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(6)]
    ages = {ids[i]: 25.0 + i for i in range(6)}
    active = ids[0]
    site_dir = _make_site(generated, "site-a", ages, active, now)

    # No --apply -> dry-run, nothing removed, exit 0.
    rc = main(["--generated-dir", str(generated)])
    assert rc == 0
    assert (site_dir / "builds" / ids[5]).is_dir()

    # --apply -> deletes the single candidate.
    rc = main(["--generated-dir", str(generated), "--apply"])
    assert rc == 0
    assert not (site_dir / "builds" / ids[5]).exists()


# ---------------------------------------------------------------------------
# Robust deletes + scope filter
# ---------------------------------------------------------------------------


def test_locked_build_is_skipped_and_gc_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.gc_old_builds as gc

    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(7)]
    ages = {ids[i]: 25.0 + i for i in range(7)}  # all old -> two GC candidates
    active = ids[0]
    site_dir = _make_site(generated, "site-a", ages, active, now)

    # Candidates are the two oldest (ids[5], ids[6]); make ids[6] "locked".
    locked_path = site_dir / "builds" / ids[6]
    real_rmtree = shutil.rmtree

    def fake_rmtree(path: object, *args: object, **kwargs: object) -> None:
        if Path(path) == locked_path:
            raise PermissionError(13, "Access is denied (simulated WinError 5)")
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(gc.shutil, "rmtree", fake_rmtree)

    report = run_gc(generated, apply=True, keep_latest=5, now=now)

    decisions = {d.build_id: d.decision for d in report.decisions}
    assert decisions[ids[5]] == DECISION_DELETED
    assert not (site_dir / "builds" / ids[5]).exists()
    assert decisions[ids[6]] == DECISION_DELETE_FAILED
    assert locked_path.is_dir(), "locked build is left intact, not half-deleted"
    assert report.deleted_count == 1
    assert report.failed_count == 1


def test_site_id_filter_limits_scope(tmp_path: Path) -> None:
    now = time.time()
    generated = tmp_path / "generated"
    ids = [_bid(i) for i in range(6)]
    ages = {ids[i]: 25.0 + i for i in range(6)}
    _make_site(generated, "site-a", ages, ids[0], now)
    _make_site(generated, "site-b", ages, ids[0], now)

    report = run_gc(generated, apply=True, keep_latest=5, site_id="site-a", now=now)

    assert not (generated / "site-a" / "builds" / ids[5]).exists()
    assert (generated / "site-b" / "builds" / ids[5]).is_dir(), "other site untouched"
    assert all(d.site_id == "site-a" for d in report.decisions)
    assert all(site != "site-b" for site, _ in report.skipped_sites)
