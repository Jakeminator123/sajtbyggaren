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
