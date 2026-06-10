"""Schema lock for the router decision artefakt-shape (KÖR-6a).

Mirrors the Sprint 3C-lite pattern (tests/test_artefact_schema_3c_lite.py):
the JSON schema must exist, be valid Draft 2020-12, declare canonical
metadata, validate live ``RouterDecision.model_dump()`` payloads, reject
malformed payloads, and stay in sync with the Pydantic models (top-level +
nested $defs) so the schema-on-disk and the in-memory type never drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.router import (  # noqa: E402
    RouterDecision,
    RouterReference,
    RouterSubtask,
    RouterTarget,
    classify_message,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "router-decision.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# File exists + valid Draft 2020-12 + canonical metadata
# ---------------------------------------------------------------------------


def test_schema_file_exists():
    assert SCHEMA_PATH.exists(), f"router-decision.schema.json missing at {SCHEMA_PATH}"


def test_schema_is_valid_draft_2020_12():
    jsonschema.Draft202012Validator.check_schema(_schema())


def test_schema_declares_canonical_metadata():
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("$id")
    assert schema.get("title")
    assert schema.get("additionalProperties") is False, (
        "router-decision.schema.json must set additionalProperties=false so "
        "Pydantic-extra fields cannot smuggle into the artefakt."
    )


# ---------------------------------------------------------------------------
# Live payloads validate (the five clock examples)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "vad är klockan?",
        "lägg en klocka i andra sektionen till vänster",
        "vilka klockor finns att tillgå?",
        "samma klocka som på aftonbladet.se",
        "gör sidan mer premium, lägg en klocka i andra sektionen, ändra inte texterna",
    ],
)
def test_live_decision_validates_against_schema(prompt: str):
    decision = classify_message(prompt)
    payload = decision.model_dump()
    jsonschema.Draft202012Validator(_schema()).validate(payload)


# ---------------------------------------------------------------------------
# Schema rejects malformed payloads
# ---------------------------------------------------------------------------


def _valid_payload() -> dict:
    return classify_message("lägg en klocka i andra sektionen till vänster").model_dump()


def test_schema_rejects_unknown_message_kind():
    payload = _valid_payload()
    payload["messageKind"] = "totally-made-up"
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(payload)


def test_schema_rejects_unknown_build_requirement():
    payload = _valid_payload()
    payload["buildRequirement"] = "rebuild-everything-now"
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(payload)


def test_schema_rejects_unknown_top_level_field():
    payload = _valid_payload()
    payload["surpriseField"] = 42
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(payload)


def test_schema_rejects_bad_position_in_target():
    payload = _valid_payload()
    payload["target"]["position"] = "diagonal"
    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(payload)


# ---------------------------------------------------------------------------
# Schema <-> Pydantic drift guard (top-level + nested $defs)
# ---------------------------------------------------------------------------


def _props(schema: dict, defs_key: str | None = None) -> set[str]:
    if defs_key is None:
        return set(schema.get("properties", {}).keys())
    return set(schema.get("$defs", {}).get(defs_key, {}).get("properties", {}).keys())


def _fields(model_cls) -> set[str]:
    return set(model_cls.model_fields.keys())


def _assert_no_drift(schema_props: set[str], pydantic_fields: set[str], label: str) -> None:
    missing_in_schema = pydantic_fields - schema_props
    missing_in_pydantic = schema_props - pydantic_fields
    assert not missing_in_schema, f"{label}: Pydantic fields {missing_in_schema} not in schema."
    assert not missing_in_pydantic, f"{label}: schema props {missing_in_pydantic} not on model."


def test_top_level_schema_matches_router_decision():
    _assert_no_drift(_props(_schema()), _fields(RouterDecision), "RouterDecision")


def test_nested_router_target_matches():
    _assert_no_drift(_props(_schema(), "routerTarget"), _fields(RouterTarget), "RouterTarget")


def test_nested_router_reference_matches():
    _assert_no_drift(
        _props(_schema(), "routerReference"), _fields(RouterReference), "RouterReference"
    )


def test_nested_router_subtask_matches():
    _assert_no_drift(_props(_schema(), "routerSubtask"), _fields(RouterSubtask), "RouterSubtask")


def test_message_kind_enum_is_locked():
    """Lock the canonical eight message kinds so adding one is intentional."""
    schema = _schema()
    assert set(schema["properties"]["messageKind"]["enum"]) == {
        "answer_only",
        "site_review",
        "edit_instruction",
        "component_discovery",
        "reference_analysis",
        "bug_report",
        "multi_intent",
        "unclear",
    }
