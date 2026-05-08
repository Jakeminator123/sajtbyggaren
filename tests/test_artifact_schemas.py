"""Tests for governance/schemas/site-brief, site-plan, generation-package.

ADR 0013 locks these three artefakt schemas before Sprint 2B. Both
scripts/build_site.py and scripts/dev_generate.py validate against them
at write time, so a regression that drifts back into "two scripts, three
shapes" must fail loudly here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.artifacts import (
    SCHEMAS,
    ArtifactSchemaError,
    load_schema,
    validate_artifact,
    validate_generation_package,
    validate_site_brief,
    validate_site_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "governance" / "schemas"


def _minimal_site_brief() -> dict:
    return {
        "runId": "run-1",
        "language": "sv",
        "rawPrompt": "Skapa hemsida för en elektriker",
        "tone": [],
        "targetAudience": [],
        "requestedCapabilities": [],
        "conversionGoals": [],
        "servicesMentioned": [],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "createdAt": "2026-05-08T12:00:00+00:00",
    }


def _minimal_site_plan() -> dict:
    return {
        "runId": "run-1",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "starterId": "marketing-base",
        "routePlan": [
            {"id": "home", "path": "/", "purpose": "Position the company"},
        ],
        "selectedDossiers": [],
        "buildSpec": {
            "qualityTarget": 9.0,
            "verificationPolicy": "build-must-pass",
            "previewRuntime": "stackblitz",
        },
        "sourceModelRole": "planningModel",
        "modelUsed": "mock",
        "planSource": "mock-pre-sprint-2b",
        "createdAt": "2026-05-08T12:00:00+00:00",
    }


def _minimal_generation_package() -> dict:
    return {
        "runId": "run-1",
        "policyVersions": {"engineRun": "engine-run.v1"},
        "siteBriefRef": "site-brief.json",
        "sitePlanRef": "site-plan.json",
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "starterId": "marketing-base",
        "language": "sv",
        "engineMode": "init",
        "createdAt": "2026-05-08T12:00:00+00:00",
    }


@pytest.mark.tooling
def test_all_three_schemas_are_loadable_and_valid_json_schema():
    """Each registered schema parses as JSON and is a draft 2020-12 document."""
    for artefact, filename in SCHEMAS.items():
        path = SCHEMAS_DIR / filename
        assert path.exists(), f"Schema file missing: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["$schema"].endswith("2020-12/schema"), (
            f"{filename} must declare draft 2020-12; got {data['$schema']}"
        )
        # load_schema caches; should produce identical content.
        assert load_schema(artefact) == data


@pytest.mark.tooling
def test_minimal_payloads_validate():
    validate_site_brief(_minimal_site_brief())
    validate_site_plan(_minimal_site_plan())
    validate_generation_package(_minimal_generation_package())


@pytest.mark.tooling
def test_site_brief_rejects_missing_required_field():
    payload = _minimal_site_brief()
    del payload["runId"]
    with pytest.raises(ArtifactSchemaError, match="runId"):
        validate_site_brief(payload)


@pytest.mark.tooling
def test_site_brief_rejects_unknown_field():
    payload = _minimal_site_brief()
    payload["_status"] = "real"  # legacy field removed by ADR 0013
    with pytest.raises(ArtifactSchemaError, match="_status"):
        validate_site_brief(payload)


@pytest.mark.tooling
def test_site_brief_rejects_wrong_briefSource_value():
    payload = _minimal_site_brief()
    payload["briefSource"] = "totally-made-up"
    with pytest.raises(ArtifactSchemaError, match="briefSource"):
        validate_site_brief(payload)


@pytest.mark.tooling
def test_site_brief_rejects_wrong_sourceModelRole():
    payload = _minimal_site_brief()
    payload["sourceModelRole"] = "planningModel"
    with pytest.raises(ArtifactSchemaError, match="sourceModelRole"):
        validate_site_brief(payload)


@pytest.mark.tooling
def test_site_plan_accepts_both_dossier_shapes():
    payload = _minimal_site_plan()
    payload["selectedDossiers"] = ["contact-form", "reviews"]
    validate_site_plan(payload)
    payload["selectedDossiers"] = {
        "required": ["interactive-game-loop"],
        "recommended": [],
        "conditional": ["postgres-storage"],
    }
    validate_site_plan(payload)


@pytest.mark.tooling
def test_site_plan_rejects_unknown_previewRuntime():
    payload = _minimal_site_plan()
    payload["buildSpec"]["previewRuntime"] = "browser"
    with pytest.raises(ArtifactSchemaError, match="previewRuntime"):
        validate_site_plan(payload)


@pytest.mark.tooling
def test_site_plan_rejects_empty_routePlan():
    payload = _minimal_site_plan()
    payload["routePlan"] = []
    with pytest.raises(ArtifactSchemaError, match="routePlan|minItems|too short"):
        validate_site_plan(payload)


@pytest.mark.tooling
@pytest.mark.parametrize(
    "value",
    ["real", "mock-no-key", "mock-llm-error", "mock-pre-sprint-2b", "pinned"],
)
def test_site_plan_accepts_all_planSource_enum_values(value: str):
    """Sprint 2B added 'pinned' for the builder path (Project Input pre-pin
    skips planningModel). 'mock-pre-sprint-2b' stays for historical artefakts.
    """
    payload = _minimal_site_plan()
    payload["planSource"] = value
    validate_site_plan(payload)


@pytest.mark.tooling
def test_site_plan_rejects_unknown_planSource():
    payload = _minimal_site_plan()
    payload["planSource"] = "totally-made-up"
    with pytest.raises(ArtifactSchemaError, match="planSource"):
        validate_site_plan(payload)


@pytest.mark.tooling
def test_generation_package_rejects_bad_engineMode():
    payload = _minimal_generation_package()
    payload["engineMode"] = "draft"
    with pytest.raises(ArtifactSchemaError, match="engineMode"):
        validate_generation_package(payload)


@pytest.mark.tooling
def test_validate_artifact_rejects_unknown_artefact_name():
    with pytest.raises(ArtifactSchemaError, match="Unknown artefakt"):
        validate_artifact("unknown-thing", {})


@pytest.mark.tooling
def test_engine_run_policy_points_artefacts_at_schemas():
    """ADR 0013 requires engine-run.v1.json to point fas 1+2 artefacts at schemas."""
    policy_path = REPO_ROOT / "governance" / "policies" / "engine-run.v1.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    artefacts_by_id = {a["id"]: a for a in policy["artifacts"]}
    assert artefacts_by_id["siteBrief"]["schema"] == "site-brief.schema.json"
    assert artefacts_by_id["sitePlan"]["schema"] == "site-plan.schema.json"
    assert (
        artefacts_by_id["generationPackage"]["schema"]
        == "generation-package.schema.json"
    )
