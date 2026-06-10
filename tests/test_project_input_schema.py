"""Schema guard for examples/<siteId>.project-input.json.

Project Input is the operator-facing structured interpretation of the
Init Prompt (ADR 0012, naming-dictionary id ``projectInput``). It bears
the operator's pinned scaffoldId/variantId and the concrete site data
that the planner and builder consume.

Until Starter/Dossier Hygiene 1A the three committed examples carried a
``$schema`` reference to
``../packages/generation/orchestration/project-input/project-input.schema.json``
which never existed on disk. Following the schema link from an IDE
returned 404, and there was no test that the link resolved.

Scope 5 of the hygiene round adds a real schema under
``governance/schemas/project-input.schema.json`` (per repo convention -
schemas live under governance/schemas/, not under packages/generation/),
repoints all three examples at it, and pins three guards:

1. Every example's ``$schema`` resolves to a file that exists on disk.
2. The schema itself is a valid JSON Schema 2020-12 document.
3. Every committed example validates against the schema. If a future
   example introduces a new shape the schema does not know about, the
   schema must be updated in the same commit.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"


def _project_input_files() -> list[Path]:
    if not EXAMPLES_DIR.exists():
        return []
    return sorted(EXAMPLES_DIR.glob("*.project-input.json"))


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.mark.governance
def test_project_input_schema_file_exists() -> None:
    """The repo MUST ship a real schema for Project Input, not an
    aspirational $schema link.
    """
    assert SCHEMA_PATH.exists(), (
        f"governance/schemas/project-input.schema.json missing at "
        f"{SCHEMA_PATH}. examples/<siteId>.project-input.json files "
        f"all reference it via $schema; the file must exist."
    )


@pytest.mark.governance
def test_project_input_schema_is_valid_json_schema_2020_12(schema: dict) -> None:
    """The schema document must itself be valid against the JSON Schema
    2020-12 metaschema. A typo in the schema (e.g. ``"type": "obj"``)
    would otherwise pass silently when no example happens to exercise
    the broken branch.
    """
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.governance
def test_project_input_schema_declares_canonical_metadata(schema: dict) -> None:
    """The schema must declare the same metadata fields the other
    governance schemas use ($schema link to draft 2020-12, $id matching
    the filename, title). This keeps tooling (IDE Json Schema support,
    schema-validate scripts) consistent across the policy folder.
    """
    assert (
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    ), "schema.$schema must point at the JSON Schema 2020-12 metaschema"
    assert schema.get("$id") == "project-input.schema.json", (
        "schema.$id must match the file name (project-input.schema.json) "
        "so IDE tooling can resolve the document by id"
    )
    assert schema.get("title"), "schema.title must be set"


@pytest.mark.governance
@pytest.mark.parametrize(
    "project_input_path", _project_input_files(), ids=lambda p: p.name
)
def test_project_input_schema_link_resolves(project_input_path: Path) -> None:
    """examples/*.project-input.json:$schema must resolve to a real file.

    The reference is parsed as a relative path from the example's parent
    directory (the standard JSON Schema convention). Absolute URLs are
    not used in this repo - the convention is local relative paths to
    governance/schemas/.
    """
    payload = json.loads(project_input_path.read_text(encoding="utf-8"))
    schema_ref = payload.get("$schema")
    assert isinstance(schema_ref, str) and schema_ref, (
        f"{project_input_path.name} is missing a $schema reference. "
        f"Either point it at "
        f"../governance/schemas/project-input.schema.json or remove "
        f"the field entirely."
    )
    if schema_ref.startswith(("http://", "https://")):
        pytest.skip("absolute URL $schema not supported by this guard")
    resolved = (project_input_path.parent / schema_ref).resolve()
    assert resolved.exists(), (
        f"{project_input_path.name} references $schema={schema_ref!r} "
        f"which resolves to {resolved} - file does not exist. The "
        f"canonical target is governance/schemas/project-input.schema.json."
    )


@pytest.mark.governance
@pytest.mark.parametrize(
    "project_input_path", _project_input_files(), ids=lambda p: p.name
)
def test_committed_project_input_validates(
    project_input_path: Path, schema: dict
) -> None:
    """Every committed Project Input must validate against the schema.

    If a new example introduces a shape the schema does not know about
    (e.g. a new ``products`` field on commerce-flavoured inputs), the
    schema bump and the example must land in the same commit. This
    guard is the regression-blocker for that drift.
    """
    payload = json.loads(project_input_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if errors:
        message = "\n".join(
            f"  - {'/'.join(str(p) for p in error.path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        pytest.fail(
            f"{project_input_path.name} failed schema validation:\n{message}"
        )


@pytest.mark.governance
def test_at_least_one_project_input_exists() -> None:
    """The Builder MVP and Viewser tests rely on at least one Project
    Input being committed; if all three are removed something is wrong.
    """
    assert _project_input_files(), (
        "No examples/<siteId>.project-input.json found. The Builder "
        "MVP and Viewser tests rely on at least one committed example."
    )


def _valid_project_input_example() -> dict:
    first = _project_input_files()[0]
    return json.loads(first.read_text(encoding="utf-8"))


@pytest.mark.governance
@pytest.mark.parametrize(
    "path",
    [
        ["unexpectedRootField"],
        ["company", "unexpectedCompanyField"],
        ["contact", "unexpectedContactField"],
        ["services", 0, "unexpectedServiceField"],
        ["tone", "unexpectedToneField"],
        ["selectedDossiers", "unexpectedSelectedField"],
    ],
)
def test_project_input_schema_rejects_unknown_fields(
    schema: dict,
    path: list[str | int],
) -> None:
    """B75: Project Input schema should fail closed for root and
    load-bearing nested objects.
    """
    payload = copy.deepcopy(_valid_project_input_example())
    cursor = payload
    for segment in path[:-1]:
        cursor = cursor[segment]
    cursor[path[-1]] = "not allowed"

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert errors, f"Expected schema error for extra field path {path!r}"
    assert any(
        "Additional properties are not allowed" in error.message
        or "is not valid under any of the given schemas" in error.message
        for error in errors
    )


# ----------------------------------------------------------------------
# ADR 0032 — directives.sectionTreatments enum guards
# ----------------------------------------------------------------------
#
# Phase 3 introduces directives.sectionTreatments as the operator-pin
# tier in front of variant-default in _treatment_for_section. The schema
# carries a closed enum table per section-id so a typo is caught by
# validation before the build starts. The tests below pin both the
# positive and negative paths and the cross-source-of-truth drift between
# the schema's enum table and the Python catalogue in build_site.py.

_SECTION_TREATMENTS_ENUMS_SCHEMA = {
    "selected-work-preview": ["editorial-stack", "asymmetric-grid", "marquee-row"],
    "treatment-list": ["minimal-rows", "split-cards", "numbered-stack"],
    "practice-grid": ["dense-grid", "tabular", "grouped"],
    "expertise-areas": ["numbered-2col", "tag-cluster"],
    "service-list": ["card-grid", "alternating-rows", "icon-strip", "tabular"],
}


@pytest.mark.governance
def test_section_treatments_property_present_under_directives(schema: dict) -> None:
    """The Phase 3 schema-bump must expose directives.sectionTreatments
    so brief/planning prompts and the wizard can discover the closed
    enum table without hard-coding it.
    """
    directives = schema["properties"]["directives"]
    assert directives.get("additionalProperties") is False, (
        "directives must keep additionalProperties=false so a typo in "
        "the directive name fails closed"
    )
    section_treatments = directives["properties"].get("sectionTreatments")
    assert section_treatments is not None, (
        "directives.sectionTreatments missing — Phase 3 schema-bump "
        "(ADR 0032) requires the property to land under directives"
    )
    assert section_treatments.get("type") == "object"
    assert section_treatments.get("additionalProperties") is False, (
        "sectionTreatments must fail closed for unknown section-ids"
    )


@pytest.mark.governance
@pytest.mark.parametrize(
    ("section_id", "expected_enum"),
    sorted(_SECTION_TREATMENTS_ENUMS_SCHEMA.items()),
)
def test_section_treatments_enum_matches_phase_1_2_catalogue(
    schema: dict,
    section_id: str,
    expected_enum: list[str],
) -> None:
    """Every section that participated in Phase 1+2 (5 sections × 14
    treatments) must be representable as an operator-pin in the schema.

    The expected enum here is the ground truth for the schema; a separate
    test below cross-checks it against the runtime catalogue in
    scripts/build_site.py so the schema and Python tabellen never drift.
    """
    section_treatments = schema["properties"]["directives"]["properties"][
        "sectionTreatments"
    ]
    section_schema = section_treatments["properties"].get(section_id)
    assert section_schema is not None, (
        f"sectionTreatments.{section_id} missing from schema — every "
        f"Phase 1+2 section must be pinnable"
    )
    actual_enum = section_schema.get("enum")
    assert isinstance(actual_enum, list), (
        f"sectionTreatments.{section_id}.enum must be a list"
    )
    assert sorted(actual_enum) == sorted(expected_enum), (
        f"sectionTreatments.{section_id}.enum drifted from the Phase 1+2 "
        f"catalogue. Schema={sorted(actual_enum)}, "
        f"expected={sorted(expected_enum)}. Update both schema and "
        f"_SECTION_TREATMENTS_BY_VARIANT in the same commit."
    )


@pytest.mark.governance
def test_section_treatments_enum_includes_every_runtime_treatment() -> None:
    """Cross-source-of-truth guard: every treatment id that the Phase 1+2
    runtime catalogue (_SECTION_TREATMENTS_BY_VARIANT in
    scripts/build_site.py) registers MUST appear in the schema enum for
    the matching section.

    This is the inverse of the previous test: it walks the runtime
    table and asserts every (section_id, treatment_id) pair is
    representable in the schema. If a future commit registers a new
    treatment in Python without bumping the schema, this test fails on
    CI before the operator-pin path can silently reject it.
    """
    from scripts.build_site import _SECTION_TREATMENTS_BY_VARIANT

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema_section_treatments = schema["properties"]["directives"][
        "properties"
    ]["sectionTreatments"]["properties"]

    runtime_pairs: set[tuple[str, str]] = set()
    for variant_bucket in _SECTION_TREATMENTS_BY_VARIANT.values():
        for section_id, treatment_id in variant_bucket.items():
            runtime_pairs.add((section_id, treatment_id))

    missing: list[str] = []
    for section_id, treatment_id in sorted(runtime_pairs):
        section_schema = schema_section_treatments.get(section_id)
        if section_schema is None:
            missing.append(
                f"section {section_id!r} not in schema enum table"
            )
            continue
        if treatment_id not in section_schema.get("enum", []):
            missing.append(
                f"section {section_id!r} treatment {treatment_id!r} "
                f"not in schema enum {section_schema.get('enum')}"
            )

    assert not missing, (
        "Schema enum table is missing runtime treatments:\n  - "
        + "\n  - ".join(missing)
    )


@pytest.mark.governance
def test_section_treatments_accepts_valid_pin(schema: dict) -> None:
    """Operator can pin one treatment per section and the payload must
    pass schema validation. Empty directives.sectionTreatments={} is
    also accepted (every section falls back to variant or section
    default).
    """
    payload = copy.deepcopy(_valid_project_input_example())
    payload.setdefault("directives", {})
    payload["directives"]["sectionTreatments"] = {
        "selected-work-preview": "asymmetric-grid",
        "service-list": "tabular",
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert not errors, (
        "Valid sectionTreatments pin should validate; got errors: "
        + "; ".join(e.message for e in errors)
    )


@pytest.mark.governance
@pytest.mark.parametrize(
    ("section_id", "bad_treatment"),
    [
        ("selected-work-preview", "tabbular-typo"),
        ("treatment-list", "card-grid"),
        ("practice-grid", "minimal-rows"),
        ("expertise-areas", "split-cards"),
        ("service-list", "asymmetric-grid"),
    ],
)
def test_section_treatments_rejects_invalid_treatment(
    schema: dict,
    section_id: str,
    bad_treatment: str,
) -> None:
    """A typo or a treatment id that belongs to a different section must
    be caught by schema validation before the build starts. The bad
    pairs here mix valid treatment ids with the wrong section so the
    test also pins that the enum is per-section, not a flat global list.
    """
    payload = copy.deepcopy(_valid_project_input_example())
    payload.setdefault("directives", {})
    payload["directives"]["sectionTreatments"] = {section_id: bad_treatment}

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert errors, (
        f"Expected schema validation error for "
        f"sectionTreatments.{section_id}={bad_treatment!r}"
    )
    assert any(
        "is not one of" in error.message
        or "is not valid under any of the given schemas" in error.message
        for error in errors
    ), f"Unexpected error shape: {[e.message for e in errors]}"


@pytest.mark.governance
def test_section_treatments_rejects_unknown_section(schema: dict) -> None:
    """An unknown section id under sectionTreatments must be rejected
    so a typo (e.g. 'service-lst') is caught instead of silently
    falling through to variant/section defaults.
    """
    payload = copy.deepcopy(_valid_project_input_example())
    payload.setdefault("directives", {})
    payload["directives"]["sectionTreatments"] = {
        "service-lst": "card-grid",
    }
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert errors, (
        "Expected schema validation error for unknown section "
        "'service-lst' under sectionTreatments"
    )
    assert any(
        "Additional properties are not allowed" in error.message
        for error in errors
    ), f"Unexpected error shape: {[e.message for e in errors]}"


@pytest.mark.governance
def test_section_treatments_optional(schema: dict) -> None:
    """Existing PI payloads without directives.sectionTreatments must
    still validate. ADR 0032 promises additive bump that keeps Phase
    1+2 snapshots intact.
    """
    payload = copy.deepcopy(_valid_project_input_example())
    if "directives" in payload and "sectionTreatments" in payload["directives"]:
        del payload["directives"]["sectionTreatments"]
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert not errors, (
        "Empty/missing sectionTreatments must validate so existing "
        "Project Inputs are not invalidated by the Phase 3 schema-bump"
    )
