"""Tests for wizard Discovery Payload compatibility.

The wizard can send additive v2 directives before the backend fully switches
away from the v1 raw-prompt path. These tests keep that rollout safe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.discovery import resolve_discovery  # noqa: E402
from scripts.prompt_to_project_input import _load_discovery_file  # noqa: E402


@pytest.fixture(scope="module")
def project_input_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "discovery.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base_payload(*, schema_version: int = 1) -> dict[str, Any]:
    return {
        "schemaVersion": schema_version,
        "rawPrompt": "Måleri i Stockholm sedan 1998",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {"siteType": ["business"]},
    }


def _candidate_project_input() -> dict[str, Any]:
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "wizard-directives-test",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Brief Company AB",
            "businessType": "painter",
            "tagline": "Brief tagline",
            "story": "Brief story",
        },
        "location": {
            "city": "Stockholm",
            "country": "Sverige",
            "serviceAreas": ["Stockholm"],
        },
        "services": [
            {"id": "maleri", "label": "Måleri", "summary": "Måleri."}
        ],
        "tone": {"primary": "warm", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "requestedCapabilities": [],
        "contact": {
            "phone": "+46 8 000 00 00",
            "email": "hej@example.se",
            "addressLines": ["Exempelgatan 1"],
            "openingHours": "Mån-Fre 09:00-17:00",
        },
        "selectedDossiers": {"required": [], "recommended": [], "rationale": "x"},
    }


@pytest.mark.tooling
def test_load_discovery_accepts_schema_version_1_without_directives(
    tmp_path: Path,
) -> None:
    payload = _base_payload(schema_version=1)
    assert _load_discovery_file(_write_payload(tmp_path, payload)) == payload


@pytest.mark.tooling
def test_load_discovery_accepts_schema_version_1_with_additive_directives(
    tmp_path: Path,
) -> None:
    payload = _base_payload(schema_version=1)
    payload["directives"] = {"layoutHint": "centered"}
    assert _load_discovery_file(_write_payload(tmp_path, payload)) == payload


@pytest.mark.tooling
def test_load_discovery_accepts_schema_version_2(tmp_path: Path) -> None:
    payload = _base_payload(schema_version=2)
    assert _load_discovery_file(_write_payload(tmp_path, payload)) == payload


@pytest.mark.tooling
def test_resolver_persists_supported_directives(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "layoutHint": "centered",
        "uniqueSellingPoints": [
            "25 års erfarenhet",
            "Lokala hantverkare",
            "Lokala hantverkare",
            "",
            "F-skatt",
            "Snabba svar",
            "Extra punkt kapas",
        ],
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"] == {"layoutHint": "centered"}
    assert project_input["uniqueSellingPoints"] == [
        "25 års erfarenhet",
        "Lokala hantverkare",
        "F-skatt",
        "Snabba svar",
    ]
    assert decision.fieldSources["directives.layoutHint"] == "wizard"
    assert decision.fieldSources["uniqueSellingPoints"] == "wizard"


@pytest.mark.tooling
def test_resolver_ignores_unknown_directive_values(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "layoutHint": "diagonal",
        "uniqueSellingPoints": [123, "", None],
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert "directives" not in project_input
    assert "uniqueSellingPoints" not in project_input
    assert "directives.layoutHint" not in decision.fieldSources
    assert "uniqueSellingPoints" not in decision.fieldSources
