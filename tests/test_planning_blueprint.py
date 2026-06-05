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
    derive_faq,
    derive_quality_risks,
    derive_story,
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
    """Return the offer/services list block.

    kor-1c-copy also emits an FAQ list block, so the offer block is identified
    by its items carrying a ``title`` (offer items) rather than ``question``
    (FAQ items) - not merely "the first list".
    """
    for key, value in content_blocks.items():
        if isinstance(value, list) and value and all(
            isinstance(item, dict) and "title" in item for item in value
        ):
            return key, value
    return None, []


def _faq_block(content_blocks: dict[str, Any]) -> tuple[str | None, list[Any]]:
    """Return the FAQ list block (items carrying ``question``), else (None, [])."""
    for key, value in content_blocks.items():
        if isinstance(value, list) and value and all(
            isinstance(item, dict) and "question" in item for item in value
        ):
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
# kor-1c-copy: story / faq / offer-summaries are emitted, distinct & grounded
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_four_baselines_emit_distinct_grounded_story():
    """Every baseline emits a company story block composed from its own
    positioning, and the four stories are clearly different."""
    stories: list[str] = []
    for branch in BASELINES:
        blocks = _plan_for(branch).generation_package["contentBlocks"]
        story_blocks = [
            v
            for k, v in blocks.items()
            if isinstance(v, dict) and "body" in v and k.split(".")[1] in
            ("about-story", "about-story-block", "story")
        ]
        assert story_blocks, f"{branch}: a story block must be emitted"
        body = story_blocks[0]["body"]
        assert body, f"{branch}: story body must be non-empty"
        positioning = _baseline_brief(branch)["positioning"]
        one_liner = positioning["oneLiner"]
        # Gap 2: the hero already renders the oneLiner (headline); the story must
        # NOT echo it verbatim - it should complement the hero, not restate it.
        assert one_liner.rstrip(".").casefold() not in body.casefold(), (
            f"{branch}: story must not echo the hero headline (oneLiner): {body!r}"
        )
        # Still grounded: composed from the brief's complementary positioning
        # angles (never the raw prompt, never fabricated).
        complementary = [
            value
            for key in ("differentiator", "localAngle", "audienceNeed")
            if isinstance((value := positioning.get(key)), str) and value
        ]
        assert any(
            angle.rstrip(".").casefold() in body.casefold() for angle in complementary
        ), f"{branch}: story must be grounded in a complementary positioning angle: {body!r}"
        stories.append(body)
    assert len(set(stories)) == 4, f"stories must differ per branch: {stories}"


@pytest.mark.tooling
def test_offer_items_carry_distinct_grounded_summaries():
    """Each baseline offer item carries an honest per-service summary, and the
    summary sets differ per industry (not the generic template)."""
    summary_sets: list[tuple[str, ...]] = []
    for branch in BASELINES:
        blocks = _plan_for(branch).generation_package["contentBlocks"]
        _, items = _offer_block(blocks)
        assert items, f"{branch}: an offer block must be emitted"
        summaries = tuple(item.get("summary", "") for item in items)
        assert all(summaries), f"{branch}: every offer item must carry a summary"
        summary_sets.append(summaries)
    assert len(set(summary_sets)) == 4, (
        f"offer summaries must differ per branch: {summary_sets}"
    )


@pytest.mark.tooling
def test_offer_summaries_deduped_when_services_fall_back_to_generic():
    """Gap 3: two unknown services in a known industry both fall back to the
    same generic industry summary; the offer list must not render identical
    copy on two cards (the duplicate is qualified with its own title)."""
    from packages.generation.planning.blueprint import _dedupe_offer_summaries

    items = [
        {"title": "Ryggbehandling", "summary": "Behandling anpassad efter dina besvär."},
        {"title": "Nackbehandling", "summary": "Behandling anpassad efter dina besvär."},
    ]
    _dedupe_offer_summaries(items)
    summaries = [item["summary"] for item in items]
    assert all(summaries), "every offer item must keep a non-empty summary"
    assert len(set(summaries)) == 2, f"summaries must be distinct: {summaries}"
    # First occurrence keeps the clean generic line; the duplicate is qualified.
    assert summaries[0] == "Behandling anpassad efter dina besvär."
    assert summaries[1].startswith("Nackbehandling")


@pytest.mark.tooling
def test_service_branches_emit_distinct_grounded_faq():
    """The three branches whose scaffold surfaces a home FAQ (electrician,
    hair salon, naprapath) emit branschrelevant, grounded FAQ pairs that differ
    per industry; the ecommerce home (keramik) honestly carries no FAQ block."""
    faq_first_answers: list[str] = []
    for branch in ("elektriker-malmo", "frisor-goteborg", "naprapat-stockholm"):
        blocks = _plan_for(branch).generation_package["contentBlocks"]
        addr, pairs = _faq_block(blocks)
        assert addr == "home.faq", f"{branch}: FAQ must address the readable home.faq"
        assert len(pairs) >= 2, f"{branch}: expected several FAQ pairs, got {pairs}"
        for pair in pairs:
            assert pair["question"] and pair["answer"], f"{branch}: FAQ pair incomplete"
        # The services-answer is grounded in servicesMentioned.
        services = _baseline_brief(branch)["servicesMentioned"]
        assert any(services[0] in pair["answer"] for pair in pairs), (
            f"{branch}: a FAQ answer must surface the brief's concrete services"
        )
        faq_first_answers.append(pairs[0]["answer"])
    assert len(set(faq_first_answers)) == 3, (
        f"FAQ answers must differ per industry: {faq_first_answers}"
    )

    keramik_blocks = _plan_for("keramik-ehandel").generation_package["contentBlocks"]
    assert _faq_block(keramik_blocks) == (None, []), (
        "ecommerce-lite home has no FAQ section, so no FAQ block may be addressed"
    )


@pytest.mark.tooling
def test_story_and_faq_omitted_without_positioning_blueprint():
    """A legacy brief that carries no positioning blueprint (e.g. the builder's
    dossier-derived mock brief) must stay byte-identical: no story, no FAQ, and
    a title-only offer list so the renderer keeps the dossier's own copy."""
    brief = {
        "runId": "kor1c-legacy",
        "language": "sv",
        "rawPrompt": "Hemsida för en elektriker i Malmö.",
        "businessTypeGuess": "electrician",
        "servicesMentioned": ["elinstallationer", "felsökning"],
        "conversionGoals": ["quote-request"],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "createdAt": "2026-06-03T08:00:00+00:00",
    }
    blocks = produce_site_plan(brief, run_id="kor1c-legacy").generation_package["contentBlocks"]
    assert _faq_block(blocks) == (None, []), "no FAQ without a positioning blueprint"
    assert not any(
        isinstance(v, dict) and "body" in v for v in blocks.values()
    ), "no story without a positioning blueprint"
    _, items = _offer_block(blocks)
    assert items, "offer titles still emit from servicesMentioned"
    assert all("summary" not in item for item in items), (
        "offer stays title-only without enrichment so the dossier summaries win"
    )


@pytest.mark.tooling
def test_non_swedish_brief_keeps_template_copy():
    """An English brief keeps the template (no story/FAQ enrichment) so the mock
    never emits mismatched-language copy - same rule extract.py uses."""
    brief = dict(_baseline_brief("elektriker-malmo"))
    brief["language"] = "en"
    blocks = produce_site_plan(brief, run_id="kor1c-en").generation_package["contentBlocks"]
    assert _faq_block(blocks) == (None, []), "no Swedish FAQ on an English brief"
    assert not any(isinstance(v, dict) and "body" in v for v in blocks.values()), (
        "no Swedish story on an English brief"
    )


@pytest.mark.tooling
def test_derive_story_and_faq_are_pure_functions_of_the_brief():
    """derive_story/derive_faq read only the brief - same input, same output,
    and an empty/legacy brief yields nothing (no fabrication)."""
    brief = _baseline_brief("naprapat-stockholm")
    assert derive_story(brief) == derive_story(brief)
    assert derive_faq(brief) == derive_faq(brief)
    assert derive_story({"language": "sv"}) is None
    assert derive_faq({"language": "sv"}) == []


@pytest.mark.tooling
def test_derive_story_does_not_echo_hero_headline_or_subheadline():
    """Gap 2: the hero renders the positioning oneLiner (headline) +
    differentiator (subheadline), so the story must complement - not echo -
    the hero. With richer angles present the story uses them and drops the
    hero-consumed sentences."""
    brief = {
        "language": "sv",
        "positioning": {
            "oneLiner": "Elektriker i Malmö med snabb service",
            "differentiator": "Fast pris och jour dygnet runt",
            "localAngle": "Vi kan Malmös äldre fastigheter utan och innan",
            "audienceNeed": "Trygg el för villaägare och bostadsrättsföreningar",
        },
    }
    story = derive_story(brief)
    assert story is not None
    # Hero headline + subheadline must not be restated verbatim in the story.
    assert "Elektriker i Malmö med snabb service" not in story
    assert "Fast pris och jour dygnet runt" not in story
    # The complementary grounded angles carry the story instead.
    assert "Malmös äldre fastigheter" in story
    assert "villaägare" in story


@pytest.mark.tooling
def test_derive_story_falls_back_to_lead_when_only_hero_angles_exist():
    """A thin brief whose only angle is the hero oneLiner still grounds a story
    (the lead) rather than returning None - the degenerate echo is acceptable
    because it is the only honest content available."""
    brief = {"language": "sv", "positioning": {"oneLiner": "Naprapat i Stockholm"}}
    assert derive_story(brief) == "Naprapat i Stockholm."


@pytest.mark.tooling
def test_story_and_faq_carry_no_fabricated_contact_or_claims():
    """story + FAQ copy must never leak a placeholder contact, an invented
    cert/review, or the raw prompt."""
    for branch in BASELINES:
        blocks = _plan_for(branch).generation_package["contentBlocks"]
        raw_prompt = _baseline_brief(branch).get("rawPrompt", "")
        for key, value in blocks.items():
            if key.split(".")[1] not in (
                "about-story", "about-story-block", "story", "faq", "faq-accordion"
            ):
                continue
            for text in _iter_strings(value):
                low = text.lower()
                assert "@" not in text, f"{branch}: {key} leaked an email token: {text!r}"
                assert "08-000" not in text, f"{branch}: {key} leaked a placeholder phone"
                assert "example" not in low, f"{branch}: {key} leaked a placeholder token"
                assert raw_prompt not in text, f"{branch}: {key} leaked the raw prompt"


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
