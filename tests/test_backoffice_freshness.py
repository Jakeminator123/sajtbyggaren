"""Unit tests for the pure freshness logic behind the per-view badges."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backoffice.freshness import compute_freshness

pytestmark = pytest.mark.tooling


@pytest.mark.tooling
def test_active_with_data_is_green(tmp_path: Path):
    (tmp_path / "data" / "runs").mkdir(parents=True)
    (tmp_path / "data" / "runs" / "run-1.json").write_text("{}", encoding="utf-8")
    entry = {"status": "active", "readsFrom": ["data/runs"]}
    fresh = compute_freshness(entry, tmp_path)
    assert fresh.state == "green"
    assert fresh.emoji == "🟢"
    assert "aktuell" in fresh.label


@pytest.mark.tooling
def test_active_empty_source_is_grey(tmp_path: Path):
    # Directory exists but is empty -> no data.
    (tmp_path / "data" / "runs").mkdir(parents=True)
    entry = {"status": "active", "readsFrom": ["data/runs"]}
    fresh = compute_freshness(entry, tmp_path)
    assert fresh.state == "grey"
    assert fresh.emoji == "⚪"


@pytest.mark.tooling
def test_active_missing_source_is_grey(tmp_path: Path):
    entry = {"status": "active", "readsFrom": ["data/does-not-exist"]}
    fresh = compute_freshness(entry, tmp_path)
    assert fresh.state == "grey"


@pytest.mark.tooling
def test_active_green_when_any_source_has_data(tmp_path: Path):
    (tmp_path / "governance" / "policies").mkdir(parents=True)
    (tmp_path / "governance" / "policies" / "x.json").write_text("{}", encoding="utf-8")
    # First source empty, second has data -> green.
    entry = {"status": "active", "readsFrom": ["data/runs", "governance/policies"]}
    fresh = compute_freshness(entry, tmp_path)
    assert fresh.state == "green"


@pytest.mark.tooling
@pytest.mark.parametrize("status", ["stale", "legacy"])
def test_stale_or_legacy_is_yellow(tmp_path: Path, status: str):
    entry = {"status": status, "readsFrom": ["governance/policies"]}
    fresh = compute_freshness(entry, tmp_path)
    assert fresh.state == "yellow"
    assert fresh.emoji == "🟡"


@pytest.mark.tooling
def test_diagnostic_is_green_without_data(tmp_path: Path):
    # Diagnostic views run live checks -> green even with no stored surface.
    entry = {"status": "diagnostic", "readsFrom": ["governance/policies"]}
    fresh = compute_freshness(entry, tmp_path)
    assert fresh.state == "green"
    assert "diagnostik" in fresh.label


@pytest.mark.tooling
def test_empty_file_counts_as_no_data(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x").write_text("", encoding="utf-8")
    entry = {"status": "active", "readsFrom": ["data/x"]}
    assert compute_freshness(entry, tmp_path).state == "grey"


@pytest.mark.tooling
def test_every_registry_entry_resolves_to_a_known_state(repo_root: Path):
    """Every real registry entry must resolve to a valid badge state."""
    policy = json.loads(
        (repo_root / "governance" / "policies" / "backoffice-views.v1.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in policy["views"]:
        fresh = compute_freshness(entry, repo_root)
        assert fresh.state in {"green", "grey", "yellow"}
        assert fresh.emoji and fresh.label
