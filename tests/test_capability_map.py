"""Tests for governance/policies/capability-map.v1.json.

ADR 0013 locks capability-map.v1 as a Sprint 2B prerequisite. The map
documents what Capability slugs the planningModel will see in
siteBrief.requestedCapabilities and which Dossiers are even candidates.

These tests pin three things:

1. The committed capability-map.v1.json validates against its schema.
2. Every non-empty 'dossiers' entry actually exists under
   packages/generation/orchestration/dossiers/{soft,hard}/. An empty
   list is allowed (with a 'comment' explaining the plan) - that's the
   whole point of the Sprint-2B-prerequisite framing.
3. The default field, when present, points at a Dossier ID that's also
   in the entry's dossiers list.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "governance" / "policies" / "capability-map.v1.json"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "capability-map.schema.json"
DOSSIERS_ROOT = (
    REPO_ROOT / "packages" / "generation" / "orchestration" / "dossiers"
)


@pytest.fixture(scope="module")
def policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.tooling
def test_policy_validates_against_schema(policy: dict, schema: dict):
    jsonschema.Draft202012Validator(schema).validate(policy)


@pytest.mark.tooling
def test_policy_has_at_least_one_capability(policy: dict):
    assert len(policy["capabilities"]) >= 1


@pytest.mark.tooling
def test_every_referenced_dossier_exists_on_disk(policy: dict):
    """Every Dossier ID in any capability's 'dossiers' list must be a real folder."""
    missing: list[tuple[str, str]] = []
    for capability_slug, entry in policy["capabilities"].items():
        for dossier_id in entry.get("dossiers", []):
            soft = DOSSIERS_ROOT / "soft" / dossier_id
            hard = DOSSIERS_ROOT / "hard" / dossier_id
            if not soft.exists() and not hard.exists():
                missing.append((capability_slug, dossier_id))
    assert not missing, (
        "capability-map references Dossier IDs that have no folder under "
        f"packages/generation/orchestration/dossiers/{{soft,hard}}/: {missing}. "
        "Either add the Dossier or remove the ID from the capability entry."
    )


@pytest.mark.tooling
def test_default_dossier_is_in_dossiers_list(policy: dict):
    """default must point at one of the listed Dossier candidates."""
    drift: list[tuple[str, str, list[str]]] = []
    for capability_slug, entry in policy["capabilities"].items():
        default = entry.get("default")
        if default is None:
            continue
        if default not in entry.get("dossiers", []):
            drift.append((capability_slug, default, entry.get("dossiers", [])))
    assert not drift, (
        "Some default values point at Dossier IDs that are not in the entry's "
        f"dossiers list: {drift}"
    )


@pytest.mark.tooling
def test_empty_dossiers_list_has_explanatory_comment(policy: dict):
    """If a capability has no Dossier yet, the comment field documents the plan."""
    silent_gaps: list[str] = []
    for capability_slug, entry in policy["capabilities"].items():
        if entry.get("dossiers"):
            continue
        if not entry.get("comment"):
            silent_gaps.append(capability_slug)
    assert not silent_gaps, (
        "Capabilities with no Dossier yet must have a 'comment' field describing "
        f"the plan; missing on: {silent_gaps}"
    )


@pytest.mark.tooling
def test_capability_map_is_referenced_in_naming_dictionary():
    """Regression guard for ADR 0013: capabilityMap is canonical in naming-dictionary."""
    naming = json.loads(
        (REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json").read_text(
            encoding="utf-8"
        )
    )
    canonicals = {term["id"] for term in naming["terms"]}
    assert "capabilityMap" in canonicals, (
        "naming-dictionary.v1.json must declare 'capabilityMap' as a canonical term"
    )
