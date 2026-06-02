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
def test_site_brief_accepts_company_and_contact_fields():
    payload = _minimal_site_brief()
    payload.update(
        {
            "companyName": "Volt & Co",
            "contactPhone": "0701234567",
            "contactEmail": "hej@voltco.se",
            "contactAddress": "Storgatan 1, 211 22 Malmö",
            "contactOpeningHours": "mån-fre 08-17",
        }
    )
    validate_site_brief(payload)


@pytest.mark.tooling
def test_site_brief_opening_hours_is_optional_and_nullable():
    """S3 Fas 1: contactOpeningHours accepts a string, accepts explicit null,
    and may be omitted entirely (it is not a required property).
    """
    payload = _minimal_site_brief()
    assert "contactOpeningHours" not in payload  # omitted is valid (optional)
    validate_site_brief(payload)

    payload["contactOpeningHours"] = "tisdag–söndag 07–16"
    validate_site_brief(payload)

    payload["contactOpeningHours"] = None
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
def test_site_plan_accepts_page_intent_warnings():
    payload = _minimal_site_plan()
    payload["pageIntentWarnings"] = [
        {
            "page": "Bildgalleri",
            "expectedPath": "/galleri",
            "reason": "Wizard must-have page is not emitted by the route plan.",
        }
    ]
    validate_site_plan(payload)


@pytest.mark.tooling
def test_site_plan_rejects_extra_page_intent_warning_fields():
    payload = _minimal_site_plan()
    payload["pageIntentWarnings"] = [
        {
            "page": "Bildgalleri",
            "expectedPath": "/galleri",
            "reason": "Wizard must-have page is not emitted by the route plan.",
            "routeWasBuilt": False,
        }
    ]
    with pytest.raises(ArtifactSchemaError, match="routeWasBuilt"):
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


# ---------------------------------------------------------------------------
# KÖR-1a blueprint skeleton (docs/heavy-llm-flow/01 + kor-1a).
#
# Optional blueprint fields are added to all three artefakt schemas. They are
# additive and optional: the minimal payloads above must keep validating
# unchanged (test_minimal_payloads_validate is the "without blueprint" case),
# while the tests below cover the "with blueprint" case, the
# "<routeId>.<sectionId>" addressing contract, and the four baseline-branch
# mock fixtures. No model fills these fields in kor-1a (that is kor-1b/kor-1c).
# ---------------------------------------------------------------------------

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "blueprints"
BASELINE_BRANCHES = [
    "elektriker-malmo",
    "frisor-goteborg",
    "naprapat-stockholm",
    "keramik-ehandel",
]


def _brief_blueprint() -> dict:
    return {
        "businessFacts": {
            "facts": ["verksam i Malmö"],
            "unknowns": ["telefonnummer", "certifieringar"],
        },
        "positioning": {
            "oneLiner": "Elektriker i Malmö för trygga installationer.",
            "differentiator": "lokal, tydlig, trygg",
            "audienceNeed": "någon som löser eljobbet rätt",
            "localAngle": "snabb på plats i Malmö",
            "tone": "trygg, kunnig, rak",
            "avoid": ["påhittade certifieringar"],
        },
        "contentStrategy": {
            "heroAngle": "trygg lokal elektriker",
            "trustStrategy": "ärlig trust utan påhittade claims",
            "offerStrategy": "lyft tre till fem tjänster",
            "avoidGenericClaims": True,
        },
        "conversion": {
            "primaryAction": "request_quote",
            "primaryCta": "Be om offert",
            "secondaryCta": "Se våra tjänster",
            "contactPriority": ["phone_if_real", "form"],
            "ctaRules": ["visa inte telefon om telefon saknas"],
        },
    }


def _section_plan_blueprint() -> dict:
    return {
        "home.hero": {
            "goal": "position fast",
            "copyIntent": "trygg lokal elektriker",
            "visualTreatment": "split-proof",
            "ctaRole": "primary",
        },
        "home.trust-proof": {
            "goal": "build credibility without fake claims",
            "proofSources": ["prompt", "wizard"],
        },
    }


def _package_blueprint() -> dict:
    return {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker i Malmö",
                "subheadline": "Vi hjälper privatpersoner och företag.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "Elinstallationer", "summary": "Säkra installationer."},
            ],
        },
        "visualDirection": {
            "mood": "trygg, modern",
            "density": "medium",
            "heroStyle": "split_with_image",
            "colorIntent": "warm_neutral_with_electric_accent",
            "sectionTreatments": {"service-list": "alternating-rows"},
            "imageBriefs": ["elektriker i Malmö, naturligt ljus"],
            "layoutSignals": {"useTrustBandNearHero": True},
        },
        "qualityRisks": ["No fake certifications", "Do not show phone if missing"],
    }


@pytest.mark.tooling
def test_site_brief_accepts_blueprint_fields():
    payload = _minimal_site_brief()
    payload.update(_brief_blueprint())
    validate_site_brief(payload)


@pytest.mark.tooling
def test_site_plan_accepts_section_plan_blueprint():
    payload = _minimal_site_plan()
    payload["sectionPlan"] = _section_plan_blueprint()
    validate_site_plan(payload)


@pytest.mark.tooling
def test_generation_package_accepts_blueprint_fields():
    payload = _minimal_generation_package()
    payload.update(_package_blueprint())
    validate_generation_package(payload)


@pytest.mark.tooling
def test_blueprint_fields_are_optional_on_all_three_artefacts():
    """Additive contract: artefacts with no blueprint field at all must keep
    validating, so existing runs never regress when the schema gains fields."""
    brief = _minimal_site_brief()
    plan = _minimal_site_plan()
    package = _minimal_generation_package()
    for key in ("businessFacts", "positioning", "contentStrategy", "conversion"):
        assert key not in brief
    assert "sectionPlan" not in plan
    for key in ("contentBlocks", "visualDirection", "qualityRisks"):
        assert key not in package
    validate_site_brief(brief)
    validate_site_plan(plan)
    validate_generation_package(package)


@pytest.mark.tooling
def test_section_plan_enforces_route_section_address_keys():
    payload = _minimal_site_plan()
    payload["sectionPlan"] = {"homehero": {"goal": "missing the dot"}}
    with pytest.raises(ArtifactSchemaError, match="homehero|does not match"):
        validate_site_plan(payload)


@pytest.mark.tooling
def test_section_plan_entry_rejects_unknown_field():
    payload = _minimal_site_plan()
    payload["sectionPlan"] = {"home.hero": {"goal": "ok", "bogus": "nope"}}
    with pytest.raises(ArtifactSchemaError, match="bogus"):
        validate_site_plan(payload)


@pytest.mark.tooling
def test_content_blocks_enforces_route_section_address_keys():
    payload = _minimal_generation_package()
    payload["contentBlocks"] = {"home-hero": {"headline": "missing the dot"}}
    with pytest.raises(ArtifactSchemaError, match="home-hero|does not match"):
        validate_generation_package(payload)


@pytest.mark.tooling
def test_visual_direction_rejects_unknown_field():
    payload = _minimal_generation_package()
    payload["visualDirection"] = {"mood": "trygg", "bogus": "nope"}
    with pytest.raises(ArtifactSchemaError, match="bogus"):
        validate_generation_package(payload)


@pytest.mark.tooling
@pytest.mark.parametrize("branch", BASELINE_BRANCHES)
def test_baseline_blueprint_fixture_validates(branch: str):
    """Each baseline-branch mock fixture carries a fully populated blueprint on
    all three artefacts and must validate against the extended schemas."""
    path = FIXTURES_DIR / f"{branch}.blueprint.json"
    assert path.exists(), f"Missing baseline blueprint fixture: {path}"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    validate_site_brief(fixture["siteBrief"])
    validate_site_plan(fixture["sitePlan"])
    validate_generation_package(fixture["generationPackage"])


@pytest.mark.tooling
def test_all_four_baseline_branches_have_fixtures():
    found = sorted(
        path.name[: -len(".blueprint.json")] for path in FIXTURES_DIR.glob("*.blueprint.json")
    )
    assert found == sorted(BASELINE_BRANCHES)
