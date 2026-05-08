"""Tests for governance/schemas/sections.schema.json.

ADR 0013 locks the sections.json grammar so future scaffolds cannot drift
from local-service-business' shape. These tests pin two things:

1. local-service-business/sections.json (and any future <scaffoldId>/sections.json)
   validates against the schema as it is committed.
2. The validator rejects the shapes the schema explicitly forbids
   (missing required keys, wrong section ID format, non-list orderRules).

Plus a regression guard that scaffold-contract.v1.json points sections.json
at the schema via the new validatedAgainst map.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.artifacts import (
    ArtifactSchemaError,
    validate_sections,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"


def _scaffolds_with_sections() -> list[Path]:
    """All <scaffoldId>/sections.json files currently committed."""
    if not SCAFFOLDS_DIR.exists():
        return []
    return sorted(SCAFFOLDS_DIR.glob("*/sections.json"))


@pytest.mark.tooling
def test_at_least_one_scaffold_has_sections_json():
    paths = _scaffolds_with_sections()
    assert paths, (
        "No <scaffoldId>/sections.json files found - the test cannot guard "
        "the contract if there is nothing to validate."
    )


@pytest.mark.tooling
@pytest.mark.parametrize("sections_path", _scaffolds_with_sections(), ids=lambda p: p.parent.name)
def test_committed_sections_json_validates(sections_path: Path):
    payload = json.loads(sections_path.read_text(encoding="utf-8"))
    validate_sections(payload)


@pytest.mark.tooling
def test_minimal_valid_sections_payload():
    validate_sections(
        {
            "home": {
                "requiredSections": ["hero"],
                "optionalSections": [],
                "sectionOrderRules": [],
            }
        }
    )


@pytest.mark.tooling
def test_rejects_missing_requiredSections():
    with pytest.raises(ArtifactSchemaError, match="requiredSections"):
        validate_sections(
            {
                "home": {
                    "optionalSections": [],
                    "sectionOrderRules": [],
                }
            }
        )


@pytest.mark.tooling
def test_rejects_uppercase_section_id():
    with pytest.raises(ArtifactSchemaError, match="requiredSections"):
        validate_sections(
            {
                "home": {
                    "requiredSections": ["Hero"],
                    "optionalSections": [],
                    "sectionOrderRules": [],
                }
            }
        )


@pytest.mark.tooling
def test_rejects_unknown_route_top_level_field():
    with pytest.raises(ArtifactSchemaError, match="HOME"):
        validate_sections(
            {
                "HOME": {
                    "requiredSections": ["hero"],
                    "optionalSections": [],
                    "sectionOrderRules": [],
                }
            }
        )


@pytest.mark.tooling
def test_rejects_empty_payload():
    with pytest.raises(ArtifactSchemaError, match="non-empty|minProperties|too few"):
        validate_sections({})


@pytest.mark.tooling
def test_scaffold_contract_points_sections_at_schema():
    """Regression guard: scaffold-contract.v1.json validatedAgainst map exists."""
    policy = json.loads(
        (REPO_ROOT / "governance" / "policies" / "scaffold-contract.v1.json").read_text(
            encoding="utf-8"
        )
    )
    layout = policy["scaffoldDirectoryLayout"]
    assert "validatedAgainst" in layout, (
        "scaffold-contract.v1.json must declare which scaffold files have schemas"
    )
    assert layout["validatedAgainst"]["sections.json"] == "sections.schema.json"
