"""Validate Engine Run artefakts against canonical JSON schemas.

ADR 0013 locks four schemas before Sprint 2B; this module exposes the
runtime validation that ``scripts/build_site.py`` and
``scripts/dev_generate.py`` use right before writing any artefact to
``data/runs/<runId>/``. Validation is strict by design - a contract
violation must fail loudly, not silently produce a malformed run.

The module also caches loaded schemas because both scripts call into
this on every run and re-reading the JSON files per artefact is wasteful.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "governance" / "schemas"


class ArtifactSchemaError(RuntimeError):
    """Raised when an Engine Run artefakt does not match its schema.

    The message includes the artefakt name plus the jsonschema validator
    path so operators see exactly which field failed without having to
    re-run jsonschema by hand.
    """


SCHEMAS: dict[str, str] = {
    "siteBrief": "site-brief.schema.json",
    "sitePlan": "site-plan.schema.json",
    "generationPackage": "generation-package.schema.json",
    "sections": "sections.schema.json",
    "scaffold": "scaffold.schema.json",
    "qualityResult": "quality-result.schema.json",
    "repairResult": "repair-result.schema.json",
}


@cache
def load_schema(artefact: str) -> dict[str, Any]:
    """Read and cache the schema for a known artefakt."""
    if artefact not in SCHEMAS:
        raise ArtifactSchemaError(
            f"Unknown artefakt {artefact!r}; expected one of {sorted(SCHEMAS)}"
        )
    schema_path = SCHEMAS_DIR / SCHEMAS[artefact]
    if not schema_path.exists():
        raise ArtifactSchemaError(
            f"Schema file missing: {schema_path}"
        )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_artifact(artefact: str, payload: dict[str, Any]) -> None:
    """Validate ``payload`` against the schema for ``artefact``.

    Raises ``ArtifactSchemaError`` on first failure with a message that
    points at the failing field (jsonschema's ``json_path``).
    """
    schema = load_schema(artefact)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return
    first = errors[0]
    location = first.json_path or "$"
    message = f"{artefact} artefakt failed schema check at {location}: {first.message}"
    if len(errors) > 1:
        message += f" (and {len(errors) - 1} more validation errors)"
    raise ArtifactSchemaError(message)


def validate_site_brief(payload: dict[str, Any]) -> None:
    validate_artifact("siteBrief", payload)


def validate_site_plan(payload: dict[str, Any]) -> None:
    validate_artifact("sitePlan", payload)


def validate_generation_package(payload: dict[str, Any]) -> None:
    validate_artifact("generationPackage", payload)


def validate_sections(payload: dict[str, Any]) -> None:
    """Validate a Scaffold's sections.json against sections.schema.json.

    Not a runtime Engine Run artefakt - it's a design-time Scaffold file -
    but reuses the same schema-loader plumbing because the validation
    semantics are identical and we want one home for jsonschema in this
    repo (per ADR 0013).
    """
    validate_artifact("sections", payload)


def validate_scaffold(payload: dict[str, Any]) -> None:
    """Validate a Scaffold's scaffold.json against scaffold.schema.json."""
    validate_artifact("scaffold", payload)


def validate_quality_result(payload: dict[str, Any]) -> None:
    """Validate a quality-result.json payload (Sprint 3C-lite, ADR 0017).

    Locks the QualityResult shape that ``packages.generation.quality_gate``
    produces. Schemas + validators were deferred from ADR 0013 until
    Sprint 3+; this is the closeout.
    """
    validate_artifact("qualityResult", payload)


def validate_repair_result(payload: dict[str, Any]) -> None:
    """Validate a repair-result.json payload (Sprint 3C-lite, ADR 0017).

    Locks the RepairResult shape (status, reason, mechanicalFixesApplied,
    llmFixesApplied, remainingErrors, qualityStatusBefore /After,
    iterations). Counterpart to validate_quality_result.
    """
    validate_artifact("repairResult", payload)


def _format_validation_error(error: ValidationError) -> str:
    """Helper used by tests that want a human-readable error string."""
    location = error.json_path or "$"
    return f"{location}: {error.message}"
