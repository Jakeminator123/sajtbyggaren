"""kor-1c-copy: the planning copy actually RENDERS branschnära (kor-1c -> kor-2).

This is the integration proof for the kor-1c-copy card
(``docs/heavy-llm-flow/kor-1c-generationpackage-blueprint.md`` +
``kor-2-renderer-konsumerar-blueprint.md``): kor-2 wired the renderer to consume
``contentBlocks.<route>.story`` / ``faq[]`` / offer summaries, but kor-1c only
emitted structure + hero + offer *titles*, so the four live branches fell back
to the generic template. This test drives the REAL planning path
(``produce_site_plan``, mock) for each baseline brief, feeds the resulting
Generation Package into the deterministic renderer exactly as ``build_site``
does, and asserts that the story, the offer summaries and the FAQ now render
industry-near and clearly different per branch - not the template fallback.

The dossier handed to the renderer is deliberately GENERIC (placeholder company,
story and services), so any industry-specific copy that appears in the rendered
output must have come from the blueprint the planning path produced, not the
dossier.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.brief.models import OPENAI_API_KEY_ENV  # noqa: E402
from packages.generation.build.blueprint_render import (  # noqa: E402
    RenderBlueprint,
    apply_blueprint_to_dossier,
)
from packages.generation.build.renderers import (  # noqa: E402
    _faq_pairs,
    render_section_about_story,
    render_section_faq,
    render_section_product_grid,
    render_section_service_list,
    render_section_treatment_list,
)
from packages.generation.planning import produce_site_plan  # noqa: E402

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "blueprints"

BRANCHES = ("elektriker-malmo", "frisor-goteborg", "naprapat-stockholm", "keramik-ehandel")

# Per-branch render expectations grounded in the brief + fixtures: a phrase that
# must appear in the rendered story, a summary that must appear in the rendered
# offer section, and whether the scaffold surfaces a home FAQ at all.
_EXPECT: dict[str, dict[str, Any]] = {
    "elektriker-malmo": {
        "offer_renderer": "service-list",
        "story_phrase": "Snabb på plats i hela Malmö",
        "offer_summary": "Säkra installationer för hem och företag.",
        "has_home_faq": True,
    },
    "frisor-goteborg": {
        "offer_renderer": "service-list",
        "story_phrase": "En frisör som förstår vad kunden vill ha",
        "offer_summary": "Klippning för dam och herr.",
        "has_home_faq": True,
    },
    "naprapat-stockholm": {
        "offer_renderer": "treatment-list",
        "story_phrase": "Lindra smärta och förstå orsaken",
        "offer_summary": "Behandling av besvär i muskler och leder.",
        "has_home_faq": True,
    },
    "keramik-ehandel": {
        "offer_renderer": "product-grid",
        "story_phrase": "Vacker keramik som tål att användas",
        "offer_summary": "Handdrejade skålar för vardagsbruk.",
        "has_home_faq": False,
    },
}

_GENERIC_SUMMARY = "En generisk tjänstebeskrivning som inte är branschspecifik."
_GENERIC_STORY = "En kort, generisk berättelse om företaget."


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """Drive the deterministic mock planning path so the test is byte-stable."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)


def _baseline_brief(branch: str) -> dict[str, Any]:
    fixture = json.loads((FIXTURES_DIR / f"{branch}.blueprint.json").read_text(encoding="utf-8"))
    return fixture["siteBrief"]


def _plan(branch: str) -> Any:
    """Run the REAL planning path (mock) so the test proves kor-1c's output."""
    return produce_site_plan(_baseline_brief(branch), run_id=f"kor1c-copy-{branch}")


def _generic_dossier(branch: str, scaffold_id: str, variant_id: str) -> dict[str, Any]:
    """A minimal, deliberately generic dossier for the branch's scaffold.

    No branch-specific copy lives here, so any industry copy in the render had
    to come from the blueprint (the kor-1c-copy contract).
    """
    dossier: dict[str, Any] = {
        "siteId": f"kor1c-copy-{branch}",
        "language": "sv",
        "scaffoldId": scaffold_id,
        "variantId": variant_id,
        "company": {
            "name": "Företaget AB",
            "tagline": "Vi hjälper dig framåt.",
            "story": _GENERIC_STORY,
            "businessType": "business",
            "team": [],
        },
        "location": {"city": "Sverige", "country": "Sverige", "serviceAreas": ["Sverige"]},
        "contact": {
            "phone": "+46 70 123 45 67",
            "email": "hej@exempel.se",
            "addressLines": ["Gatan 1", "111 11 Orten"],
            "openingHours": "Mån-Fre 9-17",
        },
        "services": [
            {"id": "generisk-tjanst", "label": "Generisk tjänst", "summary": _GENERIC_SUMMARY}
        ],
        "trustSignals": [],
        "conversionGoals": list(_baseline_brief(branch).get("conversionGoals") or []),
    }
    if scaffold_id == "ecommerce-lite":
        dossier["products"] = [
            {"id": "generisk-produkt", "label": "Generisk produkt", "summary": _GENERIC_SUMMARY}
        ]
    return dossier


def _setup(branch: str) -> tuple[RenderBlueprint, dict[str, Any]]:
    plan = _plan(branch)
    gp = plan.generation_package
    blueprint = RenderBlueprint.from_artifacts(gp, _baseline_brief(branch))
    dossier = _generic_dossier(branch, gp["scaffoldId"], gp["variantId"])
    return blueprint, dossier


def _render_offer(branch: str, dossier: dict[str, Any]) -> str:
    kind = _EXPECT[branch]["offer_renderer"]
    variant_id = dossier["variantId"]
    if kind == "service-list":
        return render_section_service_list(dossier, contact_path="/kontakt", variant_id=variant_id)
    if kind == "treatment-list":
        return render_section_treatment_list(dossier, contact_path="/kontakt", variant_id=variant_id)
    return render_section_product_grid(dossier)


# ---------------------------------------------------------------------------
# Story renders branschnära and differs per branch
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_story_renders_per_branch_and_is_distinct():
    rendered_stories: list[str] = []
    for branch in BRANCHES:
        blueprint, dossier = _setup(branch)
        effective, changed = apply_blueprint_to_dossier(dossier, blueprint)
        assert changed, f"{branch}: the blueprint must change the render (story/offer)"
        # The generic dossier story has been replaced by the grounded blueprint story.
        assert effective["company"]["story"] != _GENERIC_STORY, (
            f"{branch}: blueprint story must override the generic dossier story"
        )
        about = render_section_about_story(effective)
        assert _EXPECT[branch]["story_phrase"] in about, (
            f"{branch}: rendered about-story must carry the branschnära story"
        )
        assert _GENERIC_STORY not in about
        rendered_stories.append(effective["company"]["story"])
    assert len(set(rendered_stories)) == 4, "the four rendered stories must differ"


# ---------------------------------------------------------------------------
# Offer summaries render branschnära and differ per branch
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_offer_summaries_render_per_branch_and_are_distinct():
    offer_renders: list[str] = []
    for branch in BRANCHES:
        blueprint, dossier = _setup(branch)
        effective, _ = apply_blueprint_to_dossier(dossier, blueprint)
        section = _render_offer(branch, effective)
        assert _EXPECT[branch]["offer_summary"] in section, (
            f"{branch}: rendered offer must carry the branschnära service summary"
        )
        assert _GENERIC_SUMMARY not in section, (
            f"{branch}: generic dossier summary must be replaced by the blueprint"
        )
        offer_renders.append(section)
    assert len(set(offer_renders)) == 4, "offer sections must differ per branch"


# ---------------------------------------------------------------------------
# FAQ renders branschnära (service + clinic branches) / honestly absent (shop)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_faq_renders_for_service_and_clinic_branches_and_is_distinct():
    first_questions: list[str] = []
    for branch in ("elektriker-malmo", "frisor-goteborg", "naprapat-stockholm"):
        blueprint, dossier = _setup(branch)
        pairs = _faq_pairs(dossier, blueprint)
        questions = [q for q, _ in pairs]
        assert "Vad kan ni hjälpa till med?" in questions, (
            f"{branch}: the branschnära FAQ must replace the template questions"
        )
        # The services answer is grounded in the brief's concrete services.
        first_service = _baseline_brief(branch)["servicesMentioned"][0]
        services_answer = next(a for q, a in pairs if q == "Vad kan ni hjälpa till med?")
        assert first_service in services_answer
        section = render_section_faq(dossier, dossier_routes=[], blueprint=blueprint)
        assert "Vad kan ni hjälpa till med?" in section
        # The second (conversion) question differs per industry.
        first_questions.append(pairs[1][0])
    # request a quote (elektriker) vs book a time (frisör + naprapat) -> >= 2 distinct.
    assert len(set(first_questions)) >= 2, f"conversion FAQ must vary: {first_questions}"


@pytest.mark.tooling
def test_keramik_home_has_no_blueprint_faq():
    """ecommerce-lite has no home FAQ section, so the renderer keeps its honest
    template FAQ (the blueprint contributes none) - not a fabricated one."""
    blueprint, dossier = _setup("keramik-ehandel")
    assert blueprint.faq() == [], "keramik blueprint must not carry a home FAQ"


# ---------------------------------------------------------------------------
# Honesty: nothing fabricated leaks into the rendered copy
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_rendered_copy_has_no_fabricated_contact_or_placeholder():
    for branch in BRANCHES:
        blueprint, dossier = _setup(branch)
        effective, _ = apply_blueprint_to_dossier(dossier, blueprint)
        story = render_section_about_story(effective)
        offer = _render_offer(branch, effective)
        faq = render_section_faq(dossier, dossier_routes=[], blueprint=blueprint)
        # The blueprint-sourced copy must not invent a contact or a cert/review.
        story_body = effective["company"]["story"]
        for label, text in (("story", story_body),):
            assert "08-000" not in text, f"{branch}: {label} leaked a placeholder phone"
            assert "exempel.se" not in text, f"{branch}: {label} leaked a placeholder email"
        # The blueprint never asserts a certification it cannot back.
        assert "certifierad" not in story_body.lower()
        # Sanity: the sections rendered (non-empty) so the assertions are meaningful.
        assert story and offer and faq
