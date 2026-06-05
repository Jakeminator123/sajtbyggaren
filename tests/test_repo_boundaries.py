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


@pytest.mark.tooling
def test_build_may_import_orchestration_for_section_treatments():
    """repo-boundaries v10: build may import orchestration.

    kor-3a's section-treatment loader lives in
    ``packages/generation/orchestration/section_treatments.py``; the build
    dispatcher re-exports it, so build must be allowed to import orchestration.
    """
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    build = _ownership_entry(policy, "packages/generation/build/")
    allowed = set(build.get("mayImportFrom", []))
    assert "packages/generation/orchestration" in allowed


@pytest.mark.tooling
def test_planning_does_not_import_from_build():
    """Real-import regression: fas-2 planning must not import fas-3 build.

    The policy-content assertions above only check the policy document; this
    scans actual source so a planning->build import (Pushvakt P1, kor-3a)
    cannot regress silently. planning ``mayImportFrom`` lists ``orchestration``,
    never ``build``.
    """
    planning_dir = REPO_ROOT / "packages" / "generation" / "planning"
    offenders: list[str] = []
    for path in sorted(planning_dir.rglob("*.py")):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and (
                "packages.generation.build" in stripped
            ):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: {stripped}"
                )
    assert not offenders, (
        "planning must not import from packages.generation.build "
        f"(repo-boundaries.v1): {offenders}"
    )
