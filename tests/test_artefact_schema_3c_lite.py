"""Sprint 3C-lite (ADR 0017) regression tests.

Locks three closeout pieces:

1. JSON schemas for ``quality-result.json`` and ``repair-result.json``
   exist, are valid Draft 2020-12, reject malformed payloads, and stay
   in sync with their Pydantic counterparts in
   ``packages.generation.{quality_gate, repair}.models``.
2. ``build-result.json:modelUsage`` populates ``byRole`` with explicit
   ``briefModel`` / ``planningModel`` / ``codegenModel`` keys (null when
   the role does not track usage yet) and merges ``codegen.usage`` into
   ``byRole.codegenModel`` when source == "real".
3. Page Quality Traits stays out of the live ``QualityResult.checks``
   list; Sprint 3C-full lands the fifth check.

Each test points at the ADR / B-ID it locks so a future drift surfaces
its motivation in the failure message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "governance" / "schemas"
QUALITY_SCHEMA = SCHEMAS_DIR / "quality-result.schema.json"
REPAIR_SCHEMA = SCHEMAS_DIR / "repair-result.schema.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Schema files exist + are valid Draft 2020-12
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_quality_result_schema_file_exists() -> None:
    assert QUALITY_SCHEMA.exists(), (
        f"governance/schemas/quality-result.schema.json missing at "
        f"{QUALITY_SCHEMA}. Sprint 3C-lite (ADR 0017) ships this schema."
    )


@pytest.mark.governance
def test_repair_result_schema_file_exists() -> None:
    assert REPAIR_SCHEMA.exists(), (
        f"governance/schemas/repair-result.schema.json missing at "
        f"{REPAIR_SCHEMA}. Sprint 3C-lite (ADR 0017) ships this schema."
    )


@pytest.mark.governance
def test_quality_result_schema_is_valid_json_schema_2020_12() -> None:
    schema = json.loads(QUALITY_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.governance
def test_repair_result_schema_is_valid_json_schema_2020_12() -> None:
    schema = json.loads(REPAIR_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)


@pytest.mark.governance
def test_schemas_declare_canonical_metadata() -> None:
    for path in (QUALITY_SCHEMA, REPAIR_SCHEMA):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert (
            schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        ), f"{path.name}.$schema must point at JSON Schema Draft 2020-12"
        assert schema.get("$id"), f"{path.name}.$id must be set"
        assert schema.get("title"), f"{path.name}.title must be set"
        assert schema.get("additionalProperties") is False, (
            f"{path.name} must set additionalProperties=false at the top "
            f"level so Pydantic-extra fields cannot smuggle into the artefakt."
        )


# ---------------------------------------------------------------------------
# Live Pydantic payloads validate against the schemas
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_live_quality_result_payload_validates() -> None:
    """A QualityResult freshly produced by ``run_quality_gate`` must
    validate against the schema. If the test fails, the schema and
    Pydantic model have drifted - update both in the same commit."""
    from packages.generation.artifacts import validate_quality_result
    from packages.generation.quality_gate import run_quality_gate

    result = run_quality_gate(
        target_dir=Path("/this/path/does/not/exist"),
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    payload = result.model_dump()
    validate_quality_result(payload)  # raises ArtifactSchemaError on mismatch


@pytest.mark.governance
def test_live_repair_result_payload_validates() -> None:
    from packages.generation.artifacts import validate_repair_result
    from packages.generation.quality_gate import run_quality_gate
    from packages.generation.repair import run_repair_pipeline

    quality = run_quality_gate(
        target_dir=Path("/this/path/does/not/exist"),
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    repair = run_repair_pipeline(quality, target_dir=Path("/tmp"), do_repair=False)
    payload = repair.model_dump()
    validate_repair_result(payload)


# ---------------------------------------------------------------------------
# Schemas reject malformed payloads
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_quality_result_schema_rejects_invalid_status() -> None:
    """Invalid status values (e.g. 'pending' which never existed) must
    fail validation. Locks the enum so a future status addition is
    intentional."""
    from packages.generation.artifacts import (
        ArtifactSchemaError,
        validate_quality_result,
    )

    bad = {"status": "pending", "checks": []}  # pending is not in the enum
    with pytest.raises(ArtifactSchemaError):
        validate_quality_result(bad)


@pytest.mark.governance
def test_quality_result_schema_rejects_invalid_check_name() -> None:
    """Adding a fifth check name (e.g. 'page-quality-traits' for Sprint
    3C-full) requires bumping the schema enum. The current schema must
    REJECT such payloads so the bump is intentional, not silent."""
    from packages.generation.artifacts import (
        ArtifactSchemaError,
        validate_quality_result,
    )

    payload = {
        "status": "ok",
        "checks": [
            {"name": "page-quality-traits", "status": "ok"},  # not in enum (yet)
        ],
    }
    with pytest.raises(ArtifactSchemaError):
        validate_quality_result(payload)


@pytest.mark.governance
def test_repair_result_schema_rejects_invalid_status() -> None:
    from packages.generation.artifacts import (
        ArtifactSchemaError,
        validate_repair_result,
    )

    bad = {"status": "in-progress"}  # not in the enum
    with pytest.raises(ArtifactSchemaError):
        validate_repair_result(bad)


@pytest.mark.governance
def test_repair_result_schema_rejects_unknown_top_level_field() -> None:
    """additionalProperties=false must keep unknown top-level fields out
    of the artefakt."""
    from packages.generation.artifacts import (
        ArtifactSchemaError,
        validate_repair_result,
    )

    bad = {"status": "not-needed", "unknownField": 42}
    with pytest.raises(ArtifactSchemaError):
        validate_repair_result(bad)


# ---------------------------------------------------------------------------
# Schema <-> Pydantic drift guard
# ---------------------------------------------------------------------------


def _schema_property_names(schema: dict, defs_key: str | None = None) -> set[str]:
    """Return the set of property names at a schema level.

    ``defs_key=None`` -> top-level ``properties``.
    ``defs_key="checkResult"`` -> ``$defs.checkResult.properties``.

    Sprint 3C-lite v2 (audit fynd 2): the drift guard previously only
    looked at the top level, so a Pydantic-vs-schema mismatch on a
    nested model (CheckResult, RepairFix) slipped through.
    """
    if defs_key is None:
        return set(schema.get("properties", {}).keys())
    nested = schema.get("$defs", {}).get(defs_key, {})
    return set(nested.get("properties", {}).keys())


def _pydantic_field_names(model_cls) -> set[str]:
    return set(model_cls.model_fields.keys())


def _assert_no_drift(
    *,
    schema_props: set[str],
    pydantic_fields: set[str],
    schema_label: str,
    model_label: str,
) -> None:
    missing_in_schema = pydantic_fields - schema_props
    missing_in_pydantic = schema_props - pydantic_fields
    assert not missing_in_schema, (
        f"{model_label} Pydantic fields {missing_in_schema} are not in "
        f"{schema_label}. Bump both together."
    )
    assert not missing_in_pydantic, (
        f"{schema_label} properties {missing_in_pydantic} are not on "
        f"the {model_label} Pydantic model."
    )


@pytest.mark.governance
def test_quality_result_schema_matches_pydantic_fields() -> None:
    """Every field in QualityResult must appear in the schema, and vice
    versa. Drift in either direction means the artefakt-on-disk and the
    in-memory type disagree.
    """
    from packages.generation.quality_gate import QualityResult

    schema = json.loads(QUALITY_SCHEMA.read_text(encoding="utf-8"))
    _assert_no_drift(
        schema_props=_schema_property_names(schema),
        pydantic_fields=_pydantic_field_names(QualityResult),
        schema_label="quality-result.schema.json",
        model_label="QualityResult",
    )


@pytest.mark.governance
def test_quality_result_nested_check_result_matches_pydantic() -> None:
    """Sprint 3C-lite v2 audit fynd 2: the previous drift guard only
    walked top-level fields. ``QualityResult.checks`` is an array of
    ``CheckResult``; if someone adds a field to the Pydantic CheckResult
    without updating ``$defs.checkResult.properties`` (or vice versa),
    the artefakt-on-disk and the in-memory model silently disagree at
    the nested level. Lock that here too.
    """
    from packages.generation.quality_gate import CheckResult

    schema = json.loads(QUALITY_SCHEMA.read_text(encoding="utf-8"))
    _assert_no_drift(
        schema_props=_schema_property_names(schema, defs_key="checkResult"),
        pydantic_fields=_pydantic_field_names(CheckResult),
        schema_label="quality-result.schema.json:$defs/checkResult",
        model_label="CheckResult",
    )


@pytest.mark.governance
def test_repair_result_schema_matches_pydantic_fields() -> None:
    from packages.generation.repair import RepairResult

    schema = json.loads(REPAIR_SCHEMA.read_text(encoding="utf-8"))
    _assert_no_drift(
        schema_props=_schema_property_names(schema),
        pydantic_fields=_pydantic_field_names(RepairResult),
        schema_label="repair-result.schema.json",
        model_label="RepairResult",
    )


@pytest.mark.governance
def test_repair_result_nested_repair_fix_matches_pydantic() -> None:
    """Same nested-drift guard for RepairFix - the Pydantic model that
    backs ``mechanicalFixesApplied[]`` and ``llmFixesApplied[]``."""
    from packages.generation.repair import RepairFix

    schema = json.loads(REPAIR_SCHEMA.read_text(encoding="utf-8"))
    _assert_no_drift(
        schema_props=_schema_property_names(schema, defs_key="repairFix"),
        pydantic_fields=_pydantic_field_names(RepairFix),
        schema_label="repair-result.schema.json:$defs/repairFix",
        model_label="RepairFix",
    )


# ---------------------------------------------------------------------------
# Validators wired into the build pipeline
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_phase3_quality_and_repair_validates_before_write(
    tmp_path: Path, monkeypatch
) -> None:
    """``run_phase3_quality_and_repair`` must call the schema validators
    so a contract drift fails the build before write_json corrupts
    data/runs/. We monkeypatch validate_quality_result to raise and
    confirm the call surfaces."""
    import packages.generation.artifacts as artifacts

    saw_call = {"hit": False}

    def boom(payload):
        saw_call["hit"] = True
        raise artifacts.ArtifactSchemaError("synthetic drift")

    monkeypatch.setattr(artifacts, "validate_quality_result", boom)
    # Re-bind the symbol that scripts/build_site.py imports lazily.
    import scripts.build_site as build_site_module

    monkeypatch.setattr(
        build_site_module.write_json, "__name__", build_site_module.write_json.__name__
    )

    project_input = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(artifacts.ArtifactSchemaError):
        build_site_module.build(project_input, do_build=False, runs_dir=tmp_path)
    assert saw_call["hit"], (
        "validate_quality_result must be called before write_json so "
        "a malformed payload never reaches data/runs/."
    )


# ---------------------------------------------------------------------------
# modelUsage byRole shape
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_model_usage_byrole_lists_three_canonical_roles() -> None:
    """``empty_model_usage`` must seed byRole with all three canonical
    LLM roles so Backoffice can render their slots even when no role
    has tracked usage yet. Sprint 3C-lite contract.
    """
    from scripts.build_site import empty_model_usage

    usage = empty_model_usage()
    assert "byRole" in usage
    by_role = usage["byRole"]
    assert set(by_role.keys()) == {"briefModel", "planningModel", "codegenModel"}
    # Sprint 3C-lite truthful default: roles that don't track usage are
    # null, not 0. Sprint 3C-full or later flips brief/planning to dicts.
    assert by_role["briefModel"] is None
    assert by_role["planningModel"] is None
    assert by_role["codegenModel"] is None


@pytest.mark.tooling
def test_model_usage_includes_codegen_when_real_call_returned_tokens() -> None:
    """When codegen.source == "real" and totalTokens > 0, the codegen
    role gets populated; brief/planning stay null because they do not
    yet track usage."""
    from packages.generation.artifacts import compose_model_usage

    codegen_summary = {
        "source": "real",
        "modelUsed": "gpt-5.4",
        "fileCount": 9,
        "rationale": "...",
        "riskNotes": [],
        "usage": {
            "promptTokens": 533,
            "completionTokens": 164,
            "totalTokens": 697,
        },
    }
    usage = compose_model_usage("real", codegen_summary)
    assert usage["byRole"]["codegenModel"] == {
        "promptTokens": 533,
        "completionTokens": 164,
        "totalTokens": 697,
    }
    assert usage["byRole"]["briefModel"] is None
    assert usage["byRole"]["planningModel"] is None
    assert usage["totalInputTokens"] == 533
    assert usage["totalOutputTokens"] == 164


@pytest.mark.tooling
def test_model_usage_keeps_codegen_null_for_non_real_source() -> None:
    """deterministic-v1 / mock-no-key / mock-llm-error must not produce
    a codegenModel byRole entry - only real LLM calls contribute usage.
    """
    from packages.generation.artifacts import compose_model_usage

    for source in ("deterministic-v1", "mock-no-key", "mock-llm-error"):
        codegen_summary = {
            "source": source,
            "usage": {"promptTokens": 0, "completionTokens": 0, "totalTokens": 0},
        }
        usage = compose_model_usage("mock-no-key", codegen_summary)
        assert usage["byRole"]["codegenModel"] is None, (
            f"codegenModel must stay null for source={source!r}; only "
            "real calls populate it."
        )


@pytest.mark.tooling
def test_compose_model_usage_lives_in_shared_artifacts_module() -> None:
    """Sprint 3C-lite v2 audit fynd 1 required moving the helper out of
    scripts/build_site.py so scripts/dev_generate.py can use the same
    composition without importing a private (underscore-prefixed)
    helper across script boundaries.
    """
    # Public symbol, callable. The same module exposes
    # CANONICAL_LLM_ROLES so callers can iterate the canonical role set
    # without hardcoding it.
    from packages.generation.artifacts import (
        CANONICAL_LLM_ROLES,
        compose_model_usage,
    )

    assert callable(compose_model_usage)
    assert CANONICAL_LLM_ROLES == ("briefModel", "planningModel", "codegenModel")


@pytest.mark.tooling
def test_dev_generate_writes_modelusage_into_build_result(
    tmp_path: Path, monkeypatch
) -> None:
    """Sprint 3C-lite v2 audit fynd 1: dev_generate.py used to write
    build-result.json without modelUsage, leaving Backoffice / Builder
    UX consumers with a missing field whenever they read a mock run.
    Verify the field is populated end-to-end through run_phase_build.
    """
    from scripts.dev_generate import (
        run_phase_build,
        run_phase_plan,
        run_phase_understand,
    )

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    run_id = "test-3c-lite-modelusage"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    site_brief = run_phase_understand(
        "Skapa en hemsida för en elektriker i Malmö", run_dir, run_id
    )
    gen_pkg = run_phase_plan(run_dir, run_id, site_brief)
    run_phase_build(run_dir, run_id, gen_pkg, site_brief=site_brief)

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )

    assert "modelUsage" in build_result, (
        "dev_generate.py:build-result.json must include modelUsage so "
        "Backoffice / Builder UX consumers see the same shape "
        "regardless of which runner produced the run."
    )
    usage = build_result["modelUsage"]
    assert "byRole" in usage
    assert set(usage["byRole"].keys()) == {
        "briefModel",
        "planningModel",
        "codegenModel",
    }
    # Without an API key the codegen path is mock-no-key -> all roles null.
    for role, value in usage["byRole"].items():
        assert value is None, (
            f"Without OPENAI_API_KEY the {role} byRole entry must be "
            f"null (we did not run a real model). Got {value!r}."
        )
    # Envelope-level invariants from Sprint 2A still hold.
    for field in ("totalInputTokens", "totalOutputTokens", "totalCostUsd", "currency", "source"):
        assert field in usage


@pytest.mark.tooling
@pytest.mark.parametrize(
    "brief_source",
    ["real", "mock-no-key", "mock-llm-error"],
)
def test_dev_generate_modelusage_source_follows_brief_source(
    tmp_path: Path, monkeypatch, brief_source: str
) -> None:
    """B38 (post-3C-lite-audit-2): ``run_phase_build`` used to hardcode
    ``base_source="mock-no-key"`` when composing
    ``build-result.json:modelUsage``. That meant a real-key run with
    ``site-brief.json:briefSource=real`` would still surface as
    ``modelUsage.source="mock-no-key"`` to Backoffice / Builder UX
    consumers, breaking the Sprint 2A invariant that the envelope-level
    ``source`` reflects how the OVERALL pipeline ran.

    The fix threads ``site_brief`` through ``run_phase_build`` and reads
    ``briefSource`` off it. This regression locks the new behaviour for
    all three Sprint 2A truth values without requiring a real OpenAI
    call (we synthesise the brief dict directly).
    """
    from scripts.dev_generate import run_phase_build, run_phase_plan, run_phase_understand

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    run_id = f"test-modelusage-source-{brief_source}"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    site_brief = run_phase_understand(
        "Skapa en hemsida för en elektriker i Malmö", run_dir, run_id
    )
    # Override the briefSource so we can prove the value is threaded
    # through to modelUsage.source without relying on real LLM calls.
    site_brief["briefSource"] = brief_source

    gen_pkg = run_phase_plan(run_dir, run_id, site_brief)
    run_phase_build(run_dir, run_id, gen_pkg, site_brief=site_brief)

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    assert build_result["modelUsage"]["source"] == brief_source, (
        f"modelUsage.source must mirror site-brief.briefSource "
        f"({brief_source!r}). Got {build_result['modelUsage']['source']!r}."
    )


@pytest.mark.tooling
def test_dev_generate_modelusage_source_defaults_to_mock_no_key_without_brief(
    tmp_path: Path, monkeypatch
) -> None:
    """B38 backwards compatibility: callers that have not threaded the
    brief through (passing ``site_brief=None`` or omitting it) keep the
    legacy ``mock-no-key`` value so existing tests / scripts do not
    break silently. New callsites in ``main()`` always pass it; this
    test pins the fallback so a future refactor cannot regress to
    ``KeyError`` or ``None`` source.
    """
    from scripts.dev_generate import run_phase_build, run_phase_plan, run_phase_understand

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    run_id = "test-modelusage-fallback"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    site_brief = run_phase_understand(
        "Skapa en hemsida för en elektriker i Malmö", run_dir, run_id
    )
    gen_pkg = run_phase_plan(run_dir, run_id, site_brief)
    # Intentionally omit site_brief argument to lock the fallback path.
    run_phase_build(run_dir, run_id, gen_pkg)

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    assert build_result["modelUsage"]["source"] == "mock-no-key"


@pytest.mark.tooling
def test_build_result_modelusage_byrole_populated_in_skip_build_run(
    tmp_path: Path, monkeypatch
) -> None:
    """End-to-end: run scripts/build_site.py:build with --skip-build-
    semantics and check that build-result.json:modelUsage.byRole
    contains the three canonical roles, all null because no API key.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input, do_build=False, runs_dir=tmp_path)

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    by_role = build_result["modelUsage"]["byRole"]
    assert set(by_role.keys()) == {"briefModel", "planningModel", "codegenModel"}
    # No API key -> no real LLM calls -> all null.
    assert by_role["briefModel"] is None
    assert by_role["planningModel"] is None
    assert by_role["codegenModel"] is None


# ---------------------------------------------------------------------------
# Page Quality Traits stays out of QualityResult.checks (Sprint 3C-full)
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_quality_result_checks_enum_excludes_page_quality_traits() -> None:
    """Sprint 3C-lite explicitly leaves Page Quality Traits as Sprint
    3C-full work. The check enum must NOT include ``page-quality-traits``
    yet; adding it requires bumping schema + Pydantic Literal +
    quality_gate dispatcher together (see builder-mvp.md ADR 0017
    section).
    """
    schema = json.loads(QUALITY_SCHEMA.read_text(encoding="utf-8"))
    check_name_enum = (
        schema["$defs"]["checkResult"]["properties"]["name"]["enum"]
    )
    assert "page-quality-traits" not in check_name_enum, (
        "Adding 'page-quality-traits' here is Sprint 3C-full scope. "
        "Bump the schema, the Pydantic Literal in "
        "packages/generation/quality_gate/models.py:CheckName, and "
        "the dispatcher together."
    )
    # Lock the canonical v1 check set.
    assert set(check_name_enum) == {
        "typecheck",
        "route-scan",
        "build-status",
        "policy-compliance",
        "contact-cta-presence",
        "placeholder-copy-scan",
    }
