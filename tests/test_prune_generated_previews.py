"""Regression tests for ``scripts/prune_generated_previews.py``.

Locks the cleanup/prune-sprint contract from ``docs/current-focus.md``
queue-item 1 and the Scout RO-spec from 2026-05-15:

- Default execution is dry-run; ``--apply`` is the only path to deletion.
- Current pointers in ``data/prompt-inputs/<siteId>.project-input.json``
  and ``data/runs/*/build-result.json`` always protect their siteIds.
- Versioned prompt-input snapshots (``<siteId>.vN.project-input.json``)
  are NOT treated as current pointers - matches the Viewser
  ``VERSIONED_PROJECT_INPUT_PATTERN`` filter so a stale snapshot cannot
  keep an orphan preview alive forever.
- Live-target detection refuses to operate when port 3000 is in use.
- Per-site and total retention caps each remove the right oldest entries.
- ``--apply`` actually removes the would-delete directories.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from prune_generated_previews import (  # noqa: E402
    DECISION_DELETE_APPLIED,
    DECISION_DELETE_PER_SITE,
    DECISION_DELETE_TOTAL,
    DECISION_KEEP_WITHIN,
    DECISION_SKIP_CURRENT,
    DRY_RUN_ENV_VAR,
    GENERATED_DIR_ENV_VAR,
    PreviewEntry,
    _decide_retention,
    collect_protected_site_ids,
    main,
    prune,
    resolve_generated_dir,
)


def _make_preview(generated_dir: Path, site_id: str, *, mtime_offset: float) -> Path:
    """Create a fake preview directory with a deterministic mtime."""
    target = generated_dir / site_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "package.json").write_text(
        json.dumps({"name": site_id}), encoding="utf-8"
    )
    when = time.time() + mtime_offset
    os.utime(target, (when, when))
    return target


def _write_pointer(prompt_inputs_dir: Path, site_id: str) -> Path:
    prompt_inputs_dir.mkdir(parents=True, exist_ok=True)
    target = prompt_inputs_dir / f"{site_id}.project-input.json"
    target.write_text(
        json.dumps({"siteId": site_id, "scaffoldId": "x", "variantId": "y"}),
        encoding="utf-8",
    )
    return target


def _write_versioned_snapshot(
    prompt_inputs_dir: Path, site_id: str, version: int
) -> Path:
    prompt_inputs_dir.mkdir(parents=True, exist_ok=True)
    target = (
        prompt_inputs_dir / f"{site_id}.v{version}.project-input.json"
    )
    target.write_text(
        json.dumps({"siteId": site_id, "scaffoldId": "x", "variantId": "y"}),
        encoding="utf-8",
    )
    return target


def _write_build_result(runs_dir: Path, run_id: str, site_id: str) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    target = run_dir / "build-result.json"
    target.write_text(
        json.dumps({"runId": run_id, "siteId": site_id, "status": "ok"}),
        encoding="utf-8",
    )
    return target


@pytest.fixture
def isolated_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, Path]:
    """Provide isolated generated/prompt-inputs/runs roots per test."""
    generated_dir = tmp_path / "generated"
    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir.mkdir()
    prompt_inputs_dir.mkdir()
    runs_dir.mkdir()
    # Default: live-checks should be skipped unless a test opts in. The
    # env var defaults to dry-run so the CLI smoke path is exercised
    # without surprise deletions.
    monkeypatch.setenv(DRY_RUN_ENV_VAR, "true")
    monkeypatch.delenv(GENERATED_DIR_ENV_VAR, raising=False)
    return {
        "generated": generated_dir,
        "prompt_inputs": prompt_inputs_dir,
        "runs": runs_dir,
    }


@pytest.mark.tooling
def test_prune_dry_run_default_does_not_delete(isolated_env: dict[str, Path]) -> None:
    """Default invocation must not touch disk even when overflow exists."""
    for index in range(15):
        _make_preview(
            isolated_env["generated"],
            f"orphan-site-{index:02d}",
            mtime_offset=-index,
        )

    report = prune(
        generated_dir=isolated_env["generated"],
        prompt_inputs_dir=isolated_env["prompt_inputs"],
        runs_dir=isolated_env["runs"],
    )

    assert report.dry_run is True
    survivors_on_disk = sorted(p.name for p in isolated_env["generated"].iterdir())
    assert len(survivors_on_disk) == 15
    decisions = {entry.path.name: entry.decision for entry in report.entries}
    delete_count = sum(
        1
        for decision in decisions.values()
        if decision in {DECISION_DELETE_PER_SITE, DECISION_DELETE_TOTAL}
    )
    assert delete_count >= 1
    assert DECISION_DELETE_APPLIED not in decisions.values()


@pytest.mark.tooling
def test_prune_protects_pointer_site_ids_from_data_prompt_inputs(
    isolated_env: dict[str, Path],
) -> None:
    """Pointer files in data/prompt-inputs/ must shield their siteId."""
    _make_preview(
        isolated_env["generated"], "current-pointer-site", mtime_offset=-1000
    )
    for index in range(12):
        _make_preview(
            isolated_env["generated"],
            f"orphan-site-{index:02d}",
            mtime_offset=-index,
        )
    _write_pointer(isolated_env["prompt_inputs"], "current-pointer-site")

    report = prune(
        generated_dir=isolated_env["generated"],
        prompt_inputs_dir=isolated_env["prompt_inputs"],
        runs_dir=isolated_env["runs"],
        keep_total=2,
    )

    pointer_decisions = [
        entry.decision
        for entry in report.entries
        if entry.site_id == "current-pointer-site"
    ]
    assert pointer_decisions == [DECISION_SKIP_CURRENT]
    assert "current-pointer-site" in report.protected_site_ids


@pytest.mark.tooling
def test_prune_protects_site_ids_from_build_result_json(
    isolated_env: dict[str, Path],
) -> None:
    """build-result.json siteIds protect previews even without a pointer file."""
    _make_preview(isolated_env["generated"], "build-only-site", mtime_offset=-2000)
    for index in range(8):
        _make_preview(
            isolated_env["generated"],
            f"orphan-site-{index:02d}",
            mtime_offset=-index,
        )
    _write_build_result(isolated_env["runs"], "run-001", "build-only-site")

    report = prune(
        generated_dir=isolated_env["generated"],
        prompt_inputs_dir=isolated_env["prompt_inputs"],
        runs_dir=isolated_env["runs"],
        keep_total=1,
    )

    decisions = {entry.site_id: entry.decision for entry in report.entries}
    assert decisions["build-only-site"] == DECISION_SKIP_CURRENT
    assert "build-only-site" in report.protected_site_ids


@pytest.mark.tooling
def test_prune_versioned_snapshots_are_not_treated_as_pointers(
    isolated_env: dict[str, Path],
) -> None:
    """``<siteId>.vN.project-input.json`` snapshots must not protect siteIds.

    Mirrors apps/viewser/lib/project-inputs.ts:VERSIONED_PROJECT_INPUT_PATTERN
    which filters the same files out of the picker. A stale immutable
    snapshot left behind from an old prompt run cannot be allowed to
    keep its preview alive forever.
    """
    _make_preview(
        isolated_env["generated"], "snapshot-only-site", mtime_offset=-100
    )
    _write_versioned_snapshot(
        isolated_env["prompt_inputs"], "snapshot-only-site", version=2
    )

    protected = collect_protected_site_ids(
        prompt_inputs_dir=isolated_env["prompt_inputs"],
        runs_dir=isolated_env["runs"],
    )
    assert "snapshot-only-site" not in protected


@pytest.mark.tooling
def test_prune_refuses_when_port_3000_is_in_use(
    isolated_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live preview/dev server on port 3000 must abort ``--apply``."""
    _make_preview(isolated_env["generated"], "site-a", mtime_offset=-1)
    _make_preview(isolated_env["generated"], "site-b", mtime_offset=-2)

    def fake_port_in_use(*_args: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(
        "prune_generated_previews.is_port_in_use", fake_port_in_use
    )

    with pytest.raises(SystemExit, match="port 3000 is in use"):
        prune(
            generated_dir=isolated_env["generated"],
            prompt_inputs_dir=isolated_env["prompt_inputs"],
            runs_dir=isolated_env["runs"],
            apply=True,
        )

    assert {p.name for p in isolated_env["generated"].iterdir()} == {
        "site-a",
        "site-b",
    }


@pytest.mark.tooling
def test_prune_keep_per_site_caps_oldest(tmp_path: Path) -> None:
    """Per-site cap keeps the N newest entries within the same siteId group.

    Builds the entry list directly because the current builder layout
    writes one directory per siteId (``.generated/<siteId>/``); two
    PreviewEntry objects cannot share both a real path AND a siteId on
    disk. ``_decide_retention`` is the public algorithm under test, and
    a future per-siteId-versioned layout would feed it grouped entries
    the same way this test does.
    """
    site_id = "site-a"
    entries = [
        PreviewEntry(
            site_id=site_id,
            path=tmp_path / f"{site_id}-{index}",
            last_write=1_000_000.0 - index,
        )
        for index in range(5)
    ]

    _decide_retention(
        entries,
        protected=set(),
        keep_per_site=2,
        keep_total=10,
    )

    entries.sort(key=lambda e: e.last_write, reverse=True)
    decisions_in_age_order = [entry.decision for entry in entries]
    assert decisions_in_age_order[0:2] == [
        DECISION_KEEP_WITHIN,
        DECISION_KEEP_WITHIN,
    ]
    assert all(
        decision == DECISION_DELETE_PER_SITE
        for decision in decisions_in_age_order[2:]
    )


@pytest.mark.tooling
def test_prune_keep_total_global_cap(isolated_env: dict[str, Path]) -> None:
    """Total cap removes the global oldest survivors after per-site filtering."""
    for index in range(7):
        _make_preview(
            isolated_env["generated"],
            f"orphan-site-{index:02d}",
            mtime_offset=-index,
        )

    report = prune(
        generated_dir=isolated_env["generated"],
        prompt_inputs_dir=isolated_env["prompt_inputs"],
        runs_dir=isolated_env["runs"],
        keep_per_site=10,
        keep_total=3,
    )

    keepers = [
        entry for entry in report.entries if entry.decision == DECISION_KEEP_WITHIN
    ]
    assert len(keepers) == 3
    keepers.sort(key=lambda e: e.last_write, reverse=True)
    expected_keepers = {
        "orphan-site-00",
        "orphan-site-01",
        "orphan-site-02",
    }
    assert {entry.site_id for entry in keepers} == expected_keepers
    deletions = [
        entry for entry in report.entries if entry.decision == DECISION_DELETE_TOTAL
    ]
    assert len(deletions) == 4


@pytest.mark.tooling
def test_prune_apply_actually_deletes_when_flagged(
    isolated_env: dict[str, Path],
) -> None:
    """``apply=True`` removes the would-delete directories from disk."""
    _make_preview(isolated_env["generated"], "current-site", mtime_offset=0)
    for index in range(5):
        _make_preview(
            isolated_env["generated"],
            f"orphan-site-{index:02d}",
            mtime_offset=-index - 10,
        )
    _write_pointer(isolated_env["prompt_inputs"], "current-site")

    report = prune(
        generated_dir=isolated_env["generated"],
        prompt_inputs_dir=isolated_env["prompt_inputs"],
        runs_dir=isolated_env["runs"],
        keep_per_site=10,
        keep_total=2,
        apply=True,
        skip_live_check=True,
    )

    assert report.dry_run is False
    survivors = {p.name for p in isolated_env["generated"].iterdir()}
    assert "current-site" in survivors
    deleted_decisions = [
        entry.decision
        for entry in report.entries
        if entry.path.name.startswith("orphan-site-")
        and not entry.path.exists()
    ]
    assert deleted_decisions
    assert all(decision == DECISION_DELETE_APPLIED for decision in deleted_decisions)
    # Two non-protected survivors retained (keep_total=2).
    non_protected_survivors = [
        name for name in survivors if name != "current-site"
    ]
    assert len(non_protected_survivors) == 2


@pytest.mark.tooling
def test_resolve_generated_dir_honours_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``SAJTBYGGAREN_GENERATED_DIR`` env mirrors the builder's helper."""
    custom = tmp_path / "custom-generated"
    custom.mkdir()
    monkeypatch.setenv(GENERATED_DIR_ENV_VAR, str(custom))
    assert resolve_generated_dir() == custom


@pytest.mark.tooling
def test_main_dry_run_env_overrides_apply_flag(
    isolated_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``SAJTBYGGAREN_PREVIEW_RETENTION_DRY_RUN=true`` neutralises ``--apply``."""
    _make_preview(isolated_env["generated"], "orphan-site-00", mtime_offset=-1)
    monkeypatch.setenv(DRY_RUN_ENV_VAR, "true")

    exit_code = main(
        [
            "--apply",
            "--generated-dir",
            str(isolated_env["generated"]),
            "--keep-total",
            "0",
        ]
    )

    assert exit_code == 0
    survivors = {p.name for p in isolated_env["generated"].iterdir()}
    assert survivors == {"orphan-site-00"}
    captured = capsys.readouterr().out
    assert DRY_RUN_ENV_VAR in captured
