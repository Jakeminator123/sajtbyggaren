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
    payload["directives"] = {"language": "sv", "scaffoldHint": "local-service-business"}
    assert _load_discovery_file(_write_payload(tmp_path, payload)) == payload


@pytest.mark.tooling
def test_load_discovery_rejects_future_schema_version(tmp_path: Path) -> None:
    payload = _base_payload(schema_version=3)
    with pytest.raises(SystemExit, match="schemaVersion 1 eller 2"):
        _load_discovery_file(_write_payload(tmp_path, payload))


@pytest.mark.tooling
def test_load_discovery_requires_language_for_schema_version_2(
    tmp_path: Path,
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {"scaffoldHint": "local-service-business"}
    with pytest.raises(SystemExit, match="directives.language"):
        _load_discovery_file(_write_payload(tmp_path, payload))


@pytest.mark.tooling
def test_resolver_persists_supported_directives(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "layoutHint": "centered",
        "language": "sv",
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
def test_resolver_persists_directives_media(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "language": "sv",
        "media": {
            "favicon": {
                "assetId": "01JXXX1234567890ABCDEFGHIJK",
                "filename": "logo-test.webp",
                "mimeType": "image/webp",
                "sizeBytes": 4096,
                "width": 256,
                "height": 256,
                "alt": "Företagslogotyp",
                "role": "favicon",
                "sourceUrl": "https://blob.example/logo-test.webp",
            },
            "backgroundVideo": {
                "assetId": "01JYYY9876543210ZYXWVUTSRQP",
                "filename": "hero-loop.mp4",
                "mimeType": "video/mp4",
                "sizeBytes": 2_400_000,
                "width": None,
                "height": None,
                "alt": "Bakgrundsvideo",
                "role": "backgroundVideo",
                "placement": "home",
            },
            "ogImage": {"assetId": "missing-required-fields"},
        },
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["media"]["favicon"]["role"] == "favicon"
    assert project_input["media"]["favicon"]["sourceUrl"] == (
        "https://blob.example/logo-test.webp"
    )
    assert project_input["media"]["backgroundVideo"]["mimeType"] == "video/mp4"
    assert "ogImage" not in project_input["media"]
    assert decision.fieldSources["media"] == "wizard"


@pytest.mark.tooling
def test_resolver_ignores_unknown_directive_values(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "language": "sv",
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


@pytest.mark.tooling
def test_resolver_persists_directives_notes_for_planner(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 5: wizardens ``directives.notesForPlanner`` ska persisteras till
    Project Input ``directives.notesForPlanner`` med field-source
    ``"wizard"``. ``build_site.py`` prepend:ar sedan noten på briefens
    egen ``notesForPlanner`` så ``planningModel`` ser operator-intent
    först. Whitespace ska trimmas men innehållet bevaras 1:1."""
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "language": "sv",
        "notesForPlanner": "  visa Instagram-feed på startsidan — USP: lokala hantverkare  ",
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"] == {
        "notesForPlanner": "visa Instagram-feed på startsidan — USP: lokala hantverkare",
    }
    assert decision.fieldSources["directives.notesForPlanner"] == "wizard"


@pytest.mark.tooling
def test_resolver_caps_notes_for_planner_at_1024_chars(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 5: fritext-noten cappas vid 1024 tecken så planner-prompten
    inte sväller okontrollerat. Cappningen sker på det redan trimmade
    värdet — föregående test säkerställer trim-beteendet."""
    payload = _base_payload(schema_version=2)
    long_text = "x" * 1500
    payload["directives"] = {"language": "sv", "notesForPlanner": long_text}

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    stored = project_input["directives"]["notesForPlanner"]
    assert len(stored) == 1024
    assert stored == "x" * 1024
    assert decision.fieldSources["directives.notesForPlanner"] == "wizard"


@pytest.mark.tooling
def test_resolver_ignores_empty_or_non_string_notes_for_planner(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 5: tom sträng, whitespace-only och icke-string ska inte
    persisteras och inte registrera en field-source."""
    for raw_value in ["", "   ", 123, None, ["list", "not", "string"]]:
        payload = _base_payload(schema_version=2)
        payload["directives"] = {"language": "sv", "notesForPlanner": raw_value}

        project_input, decision = resolve_discovery(
            raw_prompt=payload["rawPrompt"],
            payload=payload,
            project_input_candidate=_candidate_project_input(),
        )

        jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
        assert "directives" not in project_input or "notesForPlanner" not in (
            project_input.get("directives") or {}
        )
        assert "directives.notesForPlanner" not in decision.fieldSources


@pytest.mark.tooling
def test_resolver_merges_directive_requested_capabilities(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 4: ``directives.requestedCapabilities`` mappade från wizardens
    ``answers.selectedFunctions`` ska mergas deterministiskt i
    ``project_input["requestedCapabilities"]`` av ``_resolve_capabilities()``
    innan Dossier-resolvern klassificerar dem. Source-label "wizard"
    (samma bucket som ``mustHave``-deriverade caps)."""
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "language": "sv",
        "requestedCapabilities": ["booking", "pricing-table"],
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"]["requestedCapabilities"] == [
        "booking",
        "pricing-table",
    ]
    assert "booking" in project_input["requestedCapabilities"]
    assert "pricing-table" in project_input["requestedCapabilities"]
    assert decision.fieldSources["requestedCapabilities"] == "wizard"


@pytest.mark.tooling
def test_resolver_dedupes_directive_caps_with_must_have_derived(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 4: när wizardens ``mustHave`` mappar till samma capability
    som ``directives.requestedCapabilities`` ska resultatet vara unikt —
    capabilityn dyker bara upp en gång i ``requestedCapabilities``."""
    payload = _base_payload(schema_version=2)
    payload["answers"]["mustHave"] = ["Bokning online"]  # → "booking" via _PAGE_TO_CAPABILITY
    payload["directives"] = {
        "language": "sv",
        "requestedCapabilities": ["booking"],
    }

    project_input, _decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    booking_count = project_input["requestedCapabilities"].count("booking")
    assert booking_count == 1, (
        f"booking ska bara förekomma en gång i requestedCapabilities, hittade "
        f"{booking_count} i {project_input['requestedCapabilities']!r}"
    )


@pytest.mark.tooling
def test_resolver_directive_caps_unknown_emits_warning_and_review_flag(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 4: en directive-supplied capability som inte finns i
    ``capability-map.v1.json`` ska ge en ``capability-unknown``-warning
    OCH höja ``operatorReviewRequired`` — samma kontrakt som för andra
    capability-källor (wizard/taxonomy/brief)."""
    payload = _base_payload(schema_version=2)
    payload["directives"] = {
        "language": "sv",
        "requestedCapabilities": ["imaginary-future-feature"],
    }

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert "imaginary-future-feature" in project_input["requestedCapabilities"]
    codes = {warning.code for warning in decision.fallbackWarnings}
    assert "capability-unknown" in codes
    by_capability = {
        warning.capabilityId for warning in decision.fallbackWarnings
        if warning.code == "capability-unknown"
    }
    assert "imaginary-future-feature" in by_capability
    assert decision.operatorReviewRequired is True


@pytest.mark.tooling
def test_resolver_directive_caps_caps_at_32_items_and_dedupes_input(
    project_input_schema: dict[str, Any],
) -> None:
    """Gap 4: directive-listan saniteras i ``_apply_directives_fields()``
    — tomma strängar/non-string hoppas över, dedup bevarar ordning, och
    listan cappas vid 32 items (samma som schema-maxItems)."""
    big_list: list[Any] = []
    for i in range(50):
        big_list.append(f"cap-{i:02d}")
    big_list.extend([" ", "", None, 123, "cap-00", "  cap-01  "])

    payload = _base_payload(schema_version=2)
    payload["directives"] = {"language": "sv", "requestedCapabilities": big_list}

    project_input, _decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=_candidate_project_input(),
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    stored = project_input["directives"]["requestedCapabilities"]
    assert len(stored) == 32
    assert stored[0] == "cap-00"
    assert stored[-1] == "cap-31"
    assert len(set(stored)) == 32, "deduperade slugs ska vara unika"


@pytest.mark.tooling
def test_resolver_empty_directive_caps_clear_existing_requested_capabilities(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["answers"].pop("siteType", None)
    payload["directives"] = {"language": "sv", "requestedCapabilities": []}
    candidate = _candidate_project_input()
    candidate["requestedCapabilities"] = ["booking"]

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=candidate,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"]["requestedCapabilities"] == []
    assert project_input["requestedCapabilities"] == []
    assert decision.fieldSources["requestedCapabilities"] == "wizard"


@pytest.mark.tooling
def test_resolver_empty_conversion_goals_clear_existing_wizard_cta() -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {"language": "sv", "conversionGoals": []}
    payload["answers"]["primaryCta"] = ""
    candidate = _candidate_project_input()
    candidate["conversionGoals"] = ["booking"]

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=candidate,
    )

    assert project_input["conversionGoals"] == []
    assert decision.fieldSources["conversionGoals"] == "wizard"


@pytest.mark.tooling
def test_resolver_empty_unique_selling_points_clear_existing_values(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {"language": "sv", "uniqueSellingPoints": []}
    candidate = _candidate_project_input()
    candidate["uniqueSellingPoints"] = ["Gammal USP"]

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=candidate,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert "uniqueSellingPoints" not in project_input
    assert decision.fieldSources["uniqueSellingPoints"] == "wizard"


@pytest.mark.tooling
def test_resolver_empty_section_treatments_clear_existing_pins(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {"language": "sv", "sectionTreatments": {}}
    candidate = _candidate_project_input()
    candidate["directives"] = {"sectionTreatments": {"service-list": "icon-strip"}}

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=candidate,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert project_input["directives"]["sectionTreatments"] == {}
    assert decision.fieldSources["directives.sectionTreatments"] == "wizard"


@pytest.mark.tooling
def test_resolver_empty_notes_for_planner_clears_existing_directive(
    project_input_schema: dict[str, Any],
) -> None:
    payload = _base_payload(schema_version=2)
    payload["directives"] = {"language": "sv", "notesForPlanner": ""}
    candidate = _candidate_project_input()
    candidate["directives"] = {"notesForPlanner": "Gammal planner-not"}

    project_input, decision = resolve_discovery(
        raw_prompt=payload["rawPrompt"],
        payload=payload,
        project_input_candidate=candidate,
    )

    jsonschema.Draft202012Validator(project_input_schema).validate(project_input)
    assert "notesForPlanner" not in project_input.get("directives", {})
    assert decision.fieldSources["directives.notesForPlanner"] == "wizard"
