"""Phase 3 (ADR 0031) — operator-pin propagation through the resolver.

These tests pin the propagation path
``payload.directives.sectionTreatments → project_input.directives.sectionTreatments``
in ``packages/generation/discovery/resolve.py::_apply_directives_fields``.

Together with ``tests/test_section_treatments_resolve.py`` (which
exercises ``_treatment_for_section``) this proves the full Phase 3
chain:

    wizard UI (operator pin)
        → DiscoveryPayload.directives.sectionTreatments
        → resolve_discovery (THIS FILE)
        → project_input.directives.sectionTreatments
        → dossier.directives.sectionTreatments  (load_json identity)
        → _operator_pin_for_section
        → _treatment_for_section  (resolve order, sibling test file)

The schema validation step is exercised separately by
``tests/test_project_input_schema.py``; we only need to prove that the
resolver actually persists the pins (and that the additive layoutHint
co-existence still works).
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


@pytest.fixture(scope="module")
def project_input_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _base_payload() -> dict[str, Any]:
    return {
        "schemaVersion": 2,
        "rawPrompt": "Måleri i Stockholm sedan 1998",
        "contentBranch": "business",
        "scaffoldHint": "local-service-business",
        "answers": {"siteType": ["business"]},
    }


def _candidate_project_input() -> dict[str, Any]:
    return {
        "$schema": "../governance/schemas/project-input.schema.json",
        "siteId": "section-treatments-resolver-test",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "language": "sv",
        "company": {
            "name": "Test AB",
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
def test_resolver_persists_section_treatments_pin(
    project_input_schema: dict[str, Any],
) -> None:
    """A single section pin survives the resolver and validates."""
    payload = _base_payload()
    payload["directives"] = {
        "language": "sv",
        "sectionTreatments": {"service-list": "tabular"},
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"] == {
        "sectionTreatments": {"service-list": "tabular"},
    }
    assert decision.fieldSources["directives.sectionTreatments"] == "wizard"


@pytest.mark.tooling
def test_resolver_coexists_layout_hint_and_section_treatments(
    project_input_schema: dict[str, Any],
) -> None:
    """layoutHint + sectionTreatments must both land on directives.

    ADR 0031 requires the directives slot to be additive, not
    destructive. Before Phase 3, ``_apply_directives_fields`` set
    ``project_input["directives"] = {"layoutHint": ...}`` which would
    have wiped any previous entry. The new code merges instead.
    """
    payload = _base_payload()
    payload["directives"] = {
        "language": "sv",
        "layoutHint": "centered",
        "sectionTreatments": {
            "service-list": "alternating-rows",
            "treatment-list": "split-cards",
        },
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"]["layoutHint"] == "centered"
    assert project_input["directives"]["sectionTreatments"] == {
        "service-list": "alternating-rows",
        "treatment-list": "split-cards",
    }
    assert decision.fieldSources["directives.layoutHint"] == "wizard"
    assert decision.fieldSources["directives.sectionTreatments"] == "wizard"


@pytest.mark.tooling
def test_resolver_strips_blank_pin_entries(
    project_input_schema: dict[str, Any],
) -> None:
    """Blank section ids or treatment ids are dropped during normalize."""
    payload = _base_payload()
    payload["directives"] = {
        "language": "sv",
        "sectionTreatments": {
            "service-list": "tabular",
            "": "ignored-because-section-blank",
            "treatment-list": "   ",
        },
    }

    project_input, _ = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"]["sectionTreatments"] == {
        "service-list": "tabular",
    }


@pytest.mark.tooling
def test_resolver_skips_section_treatments_when_all_blank() -> None:
    """No surviving pins → directives.sectionTreatments is not written."""
    payload = _base_payload()
    payload["directives"] = {
        "language": "sv",
        "sectionTreatments": {"service-list": "   ", "": "abc"},
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    directives = project_input.get("directives", {})
    assert "sectionTreatments" not in directives
    assert "directives.sectionTreatments" not in decision.fieldSources


@pytest.mark.tooling
def test_resolver_ignores_non_dict_section_treatments() -> None:
    """A non-dict payload value is ignored without raising."""
    payload = _base_payload()
    payload["directives"] = {
        "language": "sv",
        "sectionTreatments": ["service-list", "tabular"],
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    directives = project_input.get("directives", {})
    assert "sectionTreatments" not in directives
    assert "directives.sectionTreatments" not in decision.fieldSources
