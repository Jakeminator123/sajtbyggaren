"""Shared fixtures for governance and tooling tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
POLICIES_DIR = GOVERNANCE_DIR / "policies"
SCHEMAS_DIR = GOVERNANCE_DIR / "schemas"
RULES_DIR = GOVERNANCE_DIR / "rules"
DECISIONS_DIR = GOVERNANCE_DIR / "decisions"
SCRIPTS_DIR = REPO_ROOT / "scripts"
CURSOR_RULES_DIR = REPO_ROOT / ".cursor" / "rules"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def policies() -> dict[str, dict]:
    """Load every policy under governance/policies/ keyed by filename."""
    out: dict[str, dict] = {}
    for path in sorted(POLICIES_DIR.glob("*.json")):
        out[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return out


@pytest.fixture(scope="session")
def schemas() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        out[path.name] = json.loads(path.read_text(encoding="utf-8"))
    return out


@pytest.fixture(scope="session")
def naming_dictionary(policies: dict[str, dict]) -> dict:
    return policies["naming-dictionary.v1.json"]


@pytest.fixture(scope="session")
def repo_boundaries(policies: dict[str, dict]) -> dict:
    return policies["repo-boundaries.v1.json"]


@pytest.fixture(scope="session")
def scaffold_contract(policies: dict[str, dict]) -> dict:
    return policies["scaffold-contract.v1.json"]


@pytest.fixture(scope="session")
def scaffold_selection(policies: dict[str, dict]) -> dict:
    return policies["scaffold-selection.v1.json"]


@pytest.fixture(scope="session")
def dossier_contract(policies: dict[str, dict]) -> dict:
    return policies["dossier-contract.v1.json"]


@pytest.fixture(scope="session")
def llm_flow(policies: dict[str, dict]) -> dict:
    return policies["llm-flow-concepts.v1.json"]


@pytest.fixture(scope="session")
def page_quality(policies: dict[str, dict]) -> dict:
    return policies["page-quality-traits.v1.json"]


@pytest.fixture(scope="session")
def preview_runtime_policy(policies: dict[str, dict]) -> dict:
    return policies["preview-runtime-policy.v1.json"]
