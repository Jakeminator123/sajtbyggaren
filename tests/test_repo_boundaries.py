"""Regression checks for repo-boundaries.v1 import allowances."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "governance" / "policies" / "repo-boundaries.v1.json"


def _ownership_entry(policy: dict, path_value: str) -> dict:
    for entry in policy.get("ownership", []):
        if entry.get("path") == path_value:
            return entry
    raise AssertionError(f"repo-boundaries ownership entry not found: {path_value}")


@pytest.mark.tooling
def test_planning_imports_from_brief_are_allowed():
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    planning = _ownership_entry(policy, "packages/generation/planning/")
    allowed = set(planning.get("mayImportFrom", []))
    assert "packages/generation/brief" in allowed
    assert "packages/generation/artifacts" in allowed


@pytest.mark.tooling
def test_scripts_imports_from_planning_are_allowed():
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    scripts = _ownership_entry(policy, "scripts/")
    allowed = set(scripts.get("mayImportFrom", []))
    assert "packages/generation/planning" in allowed
