"""Tests för Intent Guard light (B137-/B138-sprint, 2026-05-21).

Intent Guard är en warning-only-check som flaggar wizard-vs-brief-konflikt
i ``scripts/build_site.py:build_plan_artefakts``. När operatören valt
``fitness``-kategori i wizardens overlay men briefen indikerar mat-/
restaurang-verksamhet (sköldpaddssoppa-case Scout 4) emitterar helpern en
``intentGuardWarnings``-rad i ``site-plan.json`` så Backoffice/Run Details
ser konflikten. Build:en stoppas INTE — bara warning.

Konflikt-tabellen är medvetet minimal i v1 (per operatör-OK 2026-05-21):
fitness/construction/beauty mot några vanliga motstridiga termer.
Utbyggnad sker i separat sprint om Scout visar fler false-negative-case.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.artifacts import validate_site_plan  # noqa: E402
from packages.generation.brief.models import OPENAI_API_KEY_ENV  # noqa: E402
from packages.generation.planning import produce_site_plan  # noqa: E402
from scripts.build_site import _intent_guard_warnings  # noqa: E402


def _brief(**overrides: Any) -> dict[str, Any]:
    brief: dict[str, Any] = {
        "runId": "test-intent-guard",
        "language": "sv",
        "rawPrompt": "Hemsida om sköldpaddssoppa, mat",
        "tone": [],
        "targetAudience": [],
        "requestedCapabilities": [],
        "conversionGoals": ["call"],
        "servicesMentioned": [],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "createdAt": "2026-05-21T12:00:00+00:00",
    }
    brief.update(overrides)
    return brief


def _prompt_meta(category_ids: list[str] | None) -> dict[str, Any] | None:
    """Bygg sidecar-meta med en minimal discoveryDecision."""
    if category_ids is None:
        return None
    return {
        "mode": "init",
        "projectId": "test-project",
        "version": 1,
        "discoveryDecision": {
            "schemaVersion": 1,
            "categoryIds": list(category_ids),
            "contentBranch": "business",
            "selectedScaffoldId": "local-service-business",
            "targetScaffoldId": "local-service-business",
            "selectedVariantId": "nordic-trust",
            "requestedCapabilities": [],
            "candidateDossiers": [],
            "fieldSources": {},
            "selectionSource": "wizard",
            "operatorReviewRequired": False,
        },
    }


# ---------------------------------------------------------------------------
# Enheten: _intent_guard_warnings()
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_intent_guard_warns_on_fitness_category_vs_food_business() -> None:
    """Sköldpaddssoppa-case: wizardens fitness-kategori vs briefens
    restaurant-businessTypeGuess + mat i servicesMentioned ska ge
    minst en warning."""
    brief = _brief(
        businessTypeGuess="restaurant",
        servicesMentioned=["mat", "soppa"],
    )
    warnings = _intent_guard_warnings(brief, _prompt_meta(["fitness"]))
    assert warnings, "Fitness-kategori + mat/restaurant ska ge minst 1 warning."
    assert all(w["categoryId"] == "fitness" for w in warnings)
    assert any(w["reason"] == "category-vs-business-mismatch" for w in warnings)
    assert any(w.get("conflictingTerm") in {"mat", "restaurang"} for w in warnings)


@pytest.mark.tooling
def test_intent_guard_warns_on_construction_vs_beauty_business() -> None:
    """Construction-kategori vs hår/naglar/salong-business ska ge warning."""
    brief = _brief(
        businessTypeGuess="hairdresser",
        servicesMentioned=["hårklippning", "naglar"],
    )
    warnings = _intent_guard_warnings(brief, _prompt_meta(["construction"]))
    assert warnings
    assert all(w["categoryId"] == "construction" for w in warnings)


@pytest.mark.tooling
def test_intent_guard_warns_on_beauty_vs_construction_business() -> None:
    """Beauty-kategori vs elektriker/vvs/bygg-business ska ge warning.

    Konflikt-tabellen matchar svenska termer (briefModels
    ``businessTypeGuess`` är engelska slugs, men ``servicesMentioned``
    är fri-text på prompt-språket — för svenska prompts hamnar svenska
    termer där).
    """
    brief = _brief(
        businessTypeGuess="electrician",
        servicesMentioned=["elektriker i Stockholm", "vvs och avlopp"],
    )
    warnings = _intent_guard_warnings(brief, _prompt_meta(["beauty"]))
    assert warnings
    assert all(w["categoryId"] == "beauty" for w in warnings)
    assert any(w.get("conflictingTerm") == "elektriker" for w in warnings)
    assert any(w.get("conflictingTerm") == "vvs" for w in warnings)


@pytest.mark.tooling
def test_intent_guard_silent_on_consistent_electrician_payload() -> None:
    """Konsistent fall: business-kategori + electrician-brief → 0 warnings."""
    brief = _brief(
        businessTypeGuess="electrician",
        servicesMentioned=["elinstallation", "felsökning"],
    )
    warnings = _intent_guard_warnings(brief, _prompt_meta(["business"]))
    assert warnings == [], (
        f"Konsistent payload ska inte ge warnings, fick: {warnings}"
    )


@pytest.mark.tooling
def test_intent_guard_silent_when_prompt_meta_is_none() -> None:
    """Defensiv: builder utan discovery-payload (CLI-direktbygge utan
    wizard) → 0 warnings, inte krasch."""
    brief = _brief(businessTypeGuess="restaurant", servicesMentioned=["mat"])
    assert _intent_guard_warnings(brief, None) == []


@pytest.mark.tooling
def test_intent_guard_silent_when_discovery_decision_missing() -> None:
    """Builder med prompt_meta men utan discoveryDecision (legacy run) →
    0 warnings."""
    brief = _brief(businessTypeGuess="restaurant")
    meta = {"mode": "init", "projectId": "p"}
    assert _intent_guard_warnings(brief, meta) == []


@pytest.mark.tooling
def test_intent_guard_silent_when_categoryids_empty() -> None:
    """Wizard utan vald kategori → ingen konflikt kan beräknas."""
    brief = _brief(businessTypeGuess="restaurant", servicesMentioned=["mat"])
    assert _intent_guard_warnings(brief, _prompt_meta([])) == []


@pytest.mark.tooling
def test_intent_guard_warning_shape_includes_business_type_guess_when_set() -> None:
    """Warning ska inkludera businessTypeGuess när det finns i briefen."""
    brief = _brief(businessTypeGuess="restaurant", servicesMentioned=["mat"])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["fitness"]))
    assert warnings
    first = warnings[0]
    assert first["categoryId"] == "fitness"
    assert first.get("businessTypeGuess") == "restaurant"
    assert first.get("reason") == "category-vs-business-mismatch"


@pytest.mark.tooling
def test_intent_guard_warning_dedupes_same_category_term_pair() -> None:
    """Samma (categoryId, conflictingTerm) får inte upprepas i listan."""
    brief = _brief(
        businessTypeGuess="restaurant",
        servicesMentioned=["mat", "mat och dryck", "MAT-leverans"],
    )
    warnings = _intent_guard_warnings(brief, _prompt_meta(["fitness"]))
    mat_warnings = [
        w for w in warnings if w.get("conflictingTerm") == "mat"
    ]
    assert len(mat_warnings) == 1, (
        f"Mat-konflikten ska dedupes per (category, term), fick "
        f"{len(mat_warnings)} dubbletter."
    )


# ---------------------------------------------------------------------------
# Integration: site-plan.json får intentGuardWarnings via produce_site_plan
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_produce_site_plan_emits_intent_guard_warnings_in_site_plan(
    monkeypatch,
) -> None:
    """produce_site_plan tar ``intent_guard_warnings``-parameter och
    surfacar den i ``site_plan["intentGuardWarnings"]``."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _brief(
        businessTypeGuess="restaurant",
        servicesMentioned=["mat"],
    )
    warnings = [
        {
            "categoryId": "fitness",
            "businessTypeGuess": "restaurant",
            "conflictingTerm": "mat",
            "reason": "category-vs-business-mismatch",
        }
    ]
    result = produce_site_plan(
        brief,
        run_id="intent-guard-integration",
        intent_guard_warnings=warnings,
    )
    site_plan = result.site_plan
    validate_site_plan(site_plan)
    assert site_plan.get("intentGuardWarnings") == warnings


@pytest.mark.tooling
def test_produce_site_plan_omits_intent_guard_warnings_when_empty(
    monkeypatch,
) -> None:
    """Tom warning-lista ska inte lägga intentGuardWarnings-fältet alls
    (mirror av page_count_warning-mönstret)."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _brief(businessTypeGuess="electrician")
    result = produce_site_plan(
        brief,
        run_id="intent-guard-empty",
        intent_guard_warnings=[],
    )
    assert "intentGuardWarnings" not in result.site_plan


@pytest.mark.tooling
def test_produce_site_plan_works_without_intent_guard_warnings_param(
    monkeypatch,
) -> None:
    """Bakåtkompatibilitet: legacy-callers (dev_generate.py som inte
    skickar intent_guard_warnings) ska inte krascha."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _brief()
    result = produce_site_plan(brief, run_id="intent-guard-legacy")
    assert "intentGuardWarnings" not in result.site_plan


# ---------------------------------------------------------------------------
# B143 regressions: English slug matching (pure businessTypeGuess, no
# servicesMentioned) — Intent Guard must fire on English slugs that briefModel
# returns as businessTypeGuess without relying on Swedish servicesMentioned.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b143_fitness_vs_restaurant_slug_no_services() -> None:
    """B143 core case: fitness category + businessTypeGuess='restaurant'
    with empty servicesMentioned must produce a warning."""
    brief = _brief(businessTypeGuess="restaurant", servicesMentioned=[])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["fitness"]))
    assert warnings, (
        "fitness + businessTypeGuess='restaurant' without servicesMentioned "
        "must trigger intent guard warning (B143)."
    )
    assert warnings[0]["categoryId"] == "fitness"
    assert warnings[0]["reason"] == "category-vs-business-mismatch"
    assert warnings[0].get("businessTypeGuess") == "restaurant"


@pytest.mark.tooling
def test_b143_beauty_vs_electrician_slug_no_services() -> None:
    """B143: salon/beauty category + businessTypeGuess='electrician'
    with empty servicesMentioned must produce a warning."""
    brief = _brief(businessTypeGuess="electrician", servicesMentioned=[])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["beauty"]))
    assert warnings, (
        "beauty + businessTypeGuess='electrician' without servicesMentioned "
        "must trigger intent guard warning (B143)."
    )
    assert warnings[0]["categoryId"] == "beauty"
    assert warnings[0]["conflictingTerm"] == "electrician"


@pytest.mark.tooling
def test_b143_construction_vs_hairdresser_slug_no_services() -> None:
    """B143: construction category + businessTypeGuess='hairdresser'
    with empty servicesMentioned must produce a warning."""
    brief = _brief(businessTypeGuess="hairdresser", servicesMentioned=[])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["construction"]))
    assert warnings, (
        "construction + businessTypeGuess='hairdresser' without "
        "servicesMentioned must trigger intent guard warning (B143)."
    )
    assert warnings[0]["categoryId"] == "construction"
    assert warnings[0]["conflictingTerm"] == "hairdresser"


@pytest.mark.tooling
def test_b143_construction_vs_hair_salon_slug_no_services() -> None:
    """B143: construction category + businessTypeGuess='hair-salon'
    with empty servicesMentioned must produce a warning."""
    brief = _brief(businessTypeGuess="hair-salon", servicesMentioned=[])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["construction"]))
    assert warnings, (
        "construction + businessTypeGuess='hair-salon' without "
        "servicesMentioned must trigger intent guard warning (B143)."
    )
    assert warnings[0]["categoryId"] == "construction"
    assert warnings[0]["conflictingTerm"] == "hair-salon"


@pytest.mark.tooling
def test_b143_consistent_business_electrician_silent() -> None:
    """B143 negative: business + electrician is consistent, no warning."""
    brief = _brief(businessTypeGuess="electrician", servicesMentioned=[])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["business"]))
    assert warnings == [], (
        "business + electrician is consistent and must not produce warnings."
    )


@pytest.mark.tooling
def test_b143_consistent_construction_electrician_silent() -> None:
    """B143 negative: construction + electrician slug is consistent."""
    brief = _brief(businessTypeGuess="electrician", servicesMentioned=[])
    warnings = _intent_guard_warnings(brief, _prompt_meta(["construction"]))
    assert warnings == [], (
        "construction + electrician is consistent and must not produce warnings."
    )


@pytest.mark.tooling
def test_b143_existing_mat_case_still_warns() -> None:
    """B143: the original sköldpaddssoppa/mat-case must still produce
    a warning after the English slug expansion."""
    brief = _brief(
        businessTypeGuess="restaurant",
        servicesMentioned=["sköldpaddssoppa", "mat"],
    )
    warnings = _intent_guard_warnings(brief, _prompt_meta(["fitness"]))
    assert warnings, (
        "fitness + restaurant + mat servicesMentioned must still warn."
    )
    mat_warnings = [w for w in warnings if w["conflictingTerm"] == "mat"]
    assert mat_warnings, "The 'mat' term conflict must still trigger."
