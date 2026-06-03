"""kor-1c: planning fills the Generation Package blueprint.

Covers the kor-1c definition of done
(``docs/heavy-llm-flow/kor-1c-generationpackage-blueprint.md``):

1. The four baseline branches produce clearly different ``contentBlocks``
   (hero + offer list) and ``visualDirection`` per industry.
2. Every ``<routeId>.<sectionId>`` address written into the artefacts exists in
   the chosen scaffold's ``sections.json``; an invalid section is rejected by
   the resolver, never written.
3. ``qualityRisks`` mirror ``businessFacts.unknowns`` (and ``positioning.avoid``)
   without inventing contact/cert claims.
4. Without ``OPENAI_API_KEY`` the contract is identical (the mock path produces
   the same blueprint fields), and the pinned builder path still produces the
   blueprint deterministically so the renderer (kor-2) has data to render.

These tests run on the deterministic mock path (no API key) so they are
byte-stable in CI. The nested-structured-output real path is smoke-tested
separately via ``SAJTBYGGAREN_E2E=1`` (see the kor-1c delivery note).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from packages.generation.artifacts import (
    validate_generation_package,
    validate_site_plan,
)
from packages.generation.brief.models import OPENAI_API_KEY_ENV
from packages.generation.planning import (
    PlanningChoice,
    SectionPlanEntry,
    derive_quality_risks,
    load_scaffold_registry,
    produce_site_plan,
    resolve_section_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "blueprints"
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"

# branch -> (fixture stem, expected scaffold the mock heuristic routes to)
BASELINES: dict[str, str] = {
    "elektriker-malmo": "local-service-business",
    "frisor-goteborg": "local-service-business",
    "naprapat-stockholm": "clinic-healthcare",
    "keramik-ehandel": "ecommerce-lite",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline_brief(branch: str) -> dict[str, Any]:
    """The kor-1b-shaped Site Brief from the kor-1a baseline fixture."""
    fixture = json.loads((FIXTURES_DIR / f"{branch}.blueprint.json").read_text(encoding="utf-8"))
    return fixture["siteBrief"]


def _disk_section_addresses(scaffold_id: str) -> set[str]:
    """Valid '<routeId>.<sectionId>' read directly from the scaffold on disk.

    Independent of the planning helper so it is a genuine cross-check that the
    blueprint never addresses a section the scaffold does not declare.
    """
    data = json.loads(
        (SCAFFOLDS_DIR / scaffold_id / "sections.json").read_text(encoding="utf-8")
    )
    addresses: set[str] = set()
    for route_id, spec in data.items():
        for section_id in spec.get("requiredSections", []) + spec.get("optionalSections", []):
            addresses.add(f"{route_id}.{section_id}")
    return addresses


def _offer_block(content_blocks: dict[str, Any]) -> tuple[str | None, list[Any]]:
    """Return the single list-shaped content block (the offer/services list)."""
    for key, value in content_blocks.items():
        if isinstance(value, list):
            return key, value
    return None, []


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _plan_for(branch: str) -> Any:
    return produce_site_plan(_baseline_brief(branch), run_id=f"kor1c-{branch}")


@pytest.fixture(autouse=True)
def _no_api_key(request, monkeypatch):
    """Default to the deterministic mock path.

    The opt-in real-LLM smoke (``*_e2e``) is the one test that needs the
    ambient ``OPENAI_API_KEY``, so it is exempt from the deletion.
    """
    if "e2e" not in request.node.name:
        monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)


# ---------------------------------------------------------------------------
# DoD 1: four baselines -> four clearly different blueprints
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_four_baselines_route_to_expected_scaffolds():
    for branch, scaffold_id in BASELINES.items():
        result = _plan_for(branch)
        assert result.site_plan["scaffoldId"] == scaffold_id, (
            f"{branch} should route to {scaffold_id}, got {result.site_plan['scaffoldId']}"
        )


@pytest.mark.tooling
def test_four_baselines_produce_distinct_hero_and_services():
    headlines: list[str] = []
    service_title_sets: list[tuple[str, ...]] = []

    for branch in BASELINES:
        result = _plan_for(branch)
        validate_site_plan(result.site_plan)
        validate_generation_package(result.generation_package)

        blocks = result.generation_package["contentBlocks"]
        hero = blocks["home.hero"]
        assert hero["headline"], f"{branch} hero must have a headline"
        headlines.append(hero["headline"])

        _, items = _offer_block(blocks)
        titles = tuple(item["title"] for item in items)
        assert titles, f"{branch} must surface the concrete services from the brief"
        service_title_sets.append(titles)

    assert len(set(headlines)) == 4, f"hero headlines must differ per branch: {headlines}"
    assert len(set(service_title_sets)) == 4, (
        f"service lists must differ per branch: {service_title_sets}"
    )


@pytest.mark.tooling
def test_visual_direction_differs_per_industry():
    moods: list[str] = []
    hero_styles: list[str] = []
    color_intents: list[str] = []

    for branch in BASELINES:
        vd = _plan_for(branch).generation_package["visualDirection"]
        moods.append(vd["mood"])
        hero_styles.append(vd["heroStyle"])
        color_intents.append(vd["colorIntent"])

    assert len(set(moods)) == 4, f"mood must differ per industry: {moods}"
    assert len(set(hero_styles)) == 4, f"heroStyle must differ per industry: {hero_styles}"
    assert len(set(color_intents)) == 4, f"colorIntent must differ per industry: {color_intents}"


# ---------------------------------------------------------------------------
# DoD 2: every addressed section exists in the scaffold's sections.json
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_blueprint_addresses_exist_in_sections_json():
    for branch, scaffold_id in BASELINES.items():
        result = _plan_for(branch)
        valid = _disk_section_addresses(scaffold_id)

        addressed: list[str] = []
        addressed += list(result.site_plan.get("sectionPlan", {}).keys())
        addressed += list(result.generation_package.get("contentBlocks", {}).keys())
        addressed += list(
            result.generation_package.get("visualDirection", {})
            .get("sectionTreatments", {})
            .keys()
        )
        assert addressed, f"{branch} should address at least one section"
        for key in addressed:
            assert key in valid, (
                f"{branch}: address {key!r} is not a real section in {scaffold_id}/sections.json"
            )


# ---------------------------------------------------------------------------
# DoD 2 (resolver): an invalid section is rejected, never written
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_resolve_section_plan_drops_invalid_keeps_valid():
    registry = load_scaffold_registry()
    scaffold = next(s for s in registry if s["id"] == "local-service-business")
    entries = [
        SectionPlanEntry(section="home.hero", goal="ok"),
        SectionPlanEntry(section="about.team", copyIntent="named clinician"),
        SectionPlanEntry(section="home.not-a-real-section", goal="nope"),
        SectionPlanEntry(section="totally.bogus"),
    ]
    resolved, rejected = resolve_section_plan(entries, scaffold)

    assert "home.hero" in resolved
    assert "about.team" in resolved
    assert "home.not-a-real-section" not in resolved
    assert "totally.bogus" not in resolved
    assert set(rejected) == {"home.not-a-real-section", "totally.bogus"}


@pytest.mark.tooling
def test_real_path_rejects_invalid_llm_section(monkeypatch):
    """A planningModel-proposed section that the scaffold does not declare is
    rejected by the resolver and never reaches the Site Plan, while a valid
    proposed section is merged on top of the deterministic baseline."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")

    def fake_real_plan_choice(site_brief, registry, capability_map, *, model):
        scaffold = next(s for s in registry if s["id"] == "local-service-business")
        return (
            PlanningChoice(
                scaffoldId="local-service-business",
                variantId="nordic-trust",
                selectedDossiers=[],
                rejectedCapabilities=[],
                rationale="fake real plan",
                sectionPlan=[
                    SectionPlanEntry(section="about.team", goal="introduce the team"),
                    SectionPlanEntry(section="services.totally-made-up", goal="invalid"),
                ],
            ),
            scaffold,
        )

    monkeypatch.setattr(
        "packages.generation.planning.plan._real_plan_choice",
        fake_real_plan_choice,
    )

    result = produce_site_plan(_baseline_brief("elektriker-malmo"), run_id="kor1c-reject")
    assert result.source == "real"
    section_plan = result.site_plan["sectionPlan"]
    validate_site_plan(result.site_plan)

    assert "about.team" in section_plan, "valid LLM-proposed section must be kept"
    assert section_plan["about.team"]["goal"] == "introduce the team"
    assert "services.totally-made-up" not in section_plan, (
        "invalid LLM-proposed section must be rejected by the resolver"
    )
    # The deterministic baseline still anchors the plan.
    assert "home.hero" in section_plan


# ---------------------------------------------------------------------------
# DoD 3: qualityRisks mirror unknowns, never invent contact/cert
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    "branch,expected_subset",
    [
        ("elektriker-malmo", {"Do not show phone if missing", "No fake certifications"}),
        (
            "frisor-goteborg",
            {
                "No fake prices",
                "Do not show opening hours if missing",
                "Do not offer booking unless booking exists",
            },
        ),
        (
            "naprapat-stockholm",
            {
                "No fake certifications",
                "No medical guarantees",
                "Do not offer booking unless booking exists",
            },
        ),
        (
            "keramik-ehandel",
            {
                "No promised delivery times unless known",
                "Do not show stock levels if missing",
                "No invented reviews",
            },
        ),
    ],
)
def test_quality_risks_mirror_unknowns(branch: str, expected_subset: set[str]):
    risks = set(_plan_for(branch).generation_package["qualityRisks"])
    assert expected_subset <= risks, (
        f"{branch}: expected {expected_subset} to be derived from the brief, got {risks}"
    )


@pytest.mark.tooling
def test_quality_risks_never_invent_contact_or_cert():
    """A brief that states its phone and lists no cert/phone unknown must not
    produce a phone or certification risk - qualityRisks mirror the brief, they
    do not assume missing data."""
    brief = _baseline_brief("elektriker-malmo")
    brief = dict(brief)
    brief["contactPhone"] = "0701234567"
    brief["businessFacts"] = {"facts": ["verksam i Malmö"], "unknowns": ["öppettider"]}
    brief["positioning"] = {**brief["positioning"], "avoid": ["generiska superlativ"]}

    risks = derive_quality_risks(brief)
    assert "Do not show phone if missing" not in risks
    assert "No fake certifications" not in risks
    assert "Do not show opening hours if missing" in risks


@pytest.mark.tooling
def test_content_blocks_carry_no_fabricated_contact():
    """No content block string may contain a placeholder email/phone - honesty
    rule: a field the brief did not state is never rendered as invented copy."""
    for branch in BASELINES:
        blocks = _plan_for(branch).generation_package["contentBlocks"]
        for text in _iter_strings(blocks):
            assert "@" not in text, f"{branch}: content block leaked an email-like token: {text!r}"
            assert "08-000" not in text, f"{branch}: content block leaked placeholder phone: {text!r}"
            assert "example" not in text.lower(), (
                f"{branch}: content block leaked a placeholder token: {text!r}"
            )


# ---------------------------------------------------------------------------
# DoD 4: identical contract via mock + pinned builder path produces blueprint
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_mock_path_emits_full_blueprint_contract():
    """Without a key the artefacts carry the full blueprint contract: sectionPlan
    on the Site Plan; contentBlocks + visualDirection + qualityRisks on the
    Generation Package."""
    result = _plan_for("elektriker-malmo")
    assert result.source == "mock-no-key"
    assert "sectionPlan" in result.site_plan and result.site_plan["sectionPlan"]
    for key in ("contentBlocks", "visualDirection", "qualityRisks"):
        assert key in result.generation_package and result.generation_package[key], (
            f"mock path must emit {key}"
        )


@pytest.mark.tooling
def test_real_path_without_section_plan_still_emits_deterministic_blueprint(monkeypatch):
    """Even when planningModel adds no sectionPlan, the deterministic baseline
    guarantees the same contract (sectionPlan + contentBlocks + visualDirection
    + qualityRisks) so 'real' and 'mock' are shape-identical."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")

    def fake_real_plan_choice(site_brief, registry, capability_map, *, model):
        scaffold = next(s for s in registry if s["id"] == "local-service-business")
        return (
            PlanningChoice(
                scaffoldId="local-service-business",
                variantId="nordic-trust",
                rationale="fake real plan, no sectionPlan",
            ),
            scaffold,
        )

    monkeypatch.setattr(
        "packages.generation.planning.plan._real_plan_choice",
        fake_real_plan_choice,
    )

    result = produce_site_plan(_baseline_brief("elektriker-malmo"), run_id="kor1c-real-empty")
    assert result.source == "real"
    assert result.site_plan.get("sectionPlan"), "deterministic sectionPlan must anchor the plan"
    for key in ("contentBlocks", "visualDirection", "qualityRisks"):
        assert result.generation_package.get(key), f"real path must still emit {key}"


@pytest.mark.tooling
def test_pinned_builder_path_produces_blueprint_deterministically(monkeypatch):
    """The builder path pins scaffold/variant and never calls planningModel, yet
    the blueprint must still be produced so kor-2 has data to render."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")  # pinned path ignores the key

    result = produce_site_plan(
        _baseline_brief("frisor-goteborg"),
        run_id="kor1c-pinned",
        pinned={"scaffoldId": "local-service-business", "variantId": "nordic-trust"},
    )
    assert result.source == "pinned"
    validate_site_plan(result.site_plan)
    validate_generation_package(result.generation_package)

    assert result.site_plan.get("sectionPlan"), "pinned path must still emit sectionPlan"
    blocks = result.generation_package.get("contentBlocks", {})
    assert "home.hero" in blocks, "pinned path must still emit a hero content block"
    assert result.generation_package.get("visualDirection")
    assert result.generation_package.get("qualityRisks")


# ---------------------------------------------------------------------------
# Real-LLM smoke for the nested structured output (sectionPlan on
# PlanningChoice). Opt-in like the kor-1b brief smoke - the kor-1b lesson was
# that nested structured output must be verified against the real model + SDK,
# not just the mock. Skipped unless SAJTBYGGAREN_E2E=1 and OPENAI_API_KEY.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.skipif(
    os.environ.get("SAJTBYGGAREN_E2E") != "1" or not os.environ.get(OPENAI_API_KEY_ENV),
    reason="SAJTBYGGAREN_E2E=1 and OPENAI_API_KEY required for real LLM call",
)
def test_real_planning_emits_section_plan_e2e():
    """planningModel must parse the extended PlanningChoice (incl. the nested
    sectionPlan list) via real structured output. source == 'real' proves the
    API accepted the schema and the parse did not crash; any sectionPlan the
    model returns must still address real scaffold sections."""
    result = produce_site_plan(_baseline_brief("elektriker-malmo"), run_id="kor1c-e2e")
    assert result.source == "real", (
        f"expected planSource=real, got {result.source} (planError={result.error})"
    )
    validate_site_plan(result.site_plan)
    validate_generation_package(result.generation_package)

    scaffold_id = result.site_plan["scaffoldId"]
    valid = _disk_section_addresses(scaffold_id)
    for key in result.site_plan.get("sectionPlan", {}):
        assert key in valid, f"real sectionPlan addressed an invalid section {key!r}"
