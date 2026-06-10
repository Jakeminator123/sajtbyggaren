"""Tests for Backoffice branschtäckning helpers."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backoffice import industry_coverage
from backoffice.views import building_blocks
from packages.generation.discovery.taxonomy import (
    TaxonomyCategory,
    load_discovery_taxonomy,
)


def _rows_by_category() -> dict[str, dict[str, Any]]:
    return {
        row["wizardCategoryId"]: row
        for row in industry_coverage.industry_coverage_rows()
    }


def test_rows_include_all_discovery_categories() -> None:
    rows = industry_coverage.industry_coverage_rows()
    taxonomy = load_discovery_taxonomy()

    assert {row["wizardCategoryId"] for row in rows} == taxonomy.known_category_ids()
    assert len(rows) == len(taxonomy.known_category_ids())


@pytest.mark.parametrize("category_id", ["restaurant", "construction", "legal"])
def test_sni_mapped_categories_get_mapping_counts(category_id: str) -> None:
    row = _rows_by_category()[category_id]

    assert row["sniMappingCount"] > 0
    assert row["mappedSniDivisions"] or row["mappedSniGroups"]


def test_unmapped_non_catch_all_categories_are_flagged_not_fatal() -> None:
    category = TaxonomyCategory(
        id="specific-demo",
        labelSv="Specifik demo",
        contentBranch="business",
        supportStatus="active",
        targetScaffoldId="local-service-business",
        activeScaffoldId="local-service-business",
        defaultVariantId="nordic-trust",
        expectedStarterId="marketing-base",
        requestedCapabilities=["contact-form"],
        candidateDossiers=[],
        recommendedPages=["Startsida"],
        rationale="Regression fixture.",
    )

    status = industry_coverage._coverage_status(
        category=category,
        selected_runtime_scaffold_id="local-service-business",
        sni_mapping_count=0,
        target_is_runtime=True,
    )

    assert status == "missing_mapping"


@pytest.mark.parametrize(
    ("category_id", "expect_sni_mappings"),
    [("business", True), ("landing", False), ("other", True)],
)
def test_catch_all_categories_keep_runtime_or_taxonomy_status(
    category_id: str,
    expect_sni_mappings: bool,
) -> None:
    """Catch-all-kategorier ska aldrig flaggas som missing_mapping.

    Sedan full SNI-täckning (ADR 0045) har business + other LEGITIMA
    mappningar (t.ex. SNI 64-66 finans -> business, 01-03 jordbruk ->
    other) — bara landing står avsiktligt utan SNI-mappning (den nås
    via wizardens explicita val, inte via bransch)."""
    row = _rows_by_category()[category_id]

    if expect_sni_mappings:
        assert row["sniMappingCount"] > 0
    else:
        assert row["sniMappingCount"] == 0
    assert row["coverageStatus"] != "missing_mapping"
    assert "missing_sni_mapping" not in row["attentionReasons"]
    assert "add_sni_mapping" not in row["recommendedActions"]


def test_unmapped_minimal_catch_all_category_does_not_force_missing_mapping() -> None:
    category = TaxonomyCategory(
        id="minimal",
        labelSv="Minimal",
        contentBranch="minimal",
        supportStatus="fallback",
        targetScaffoldId="local-service-business",
        fallbackScaffoldId="local-service-business",
        defaultVariantId="nordic-trust",
        expectedStarterId="marketing-base",
        requestedCapabilities=["contact-form"],
        candidateDossiers=[],
        recommendedPages=["Startsida"],
        rationale="Regression fixture.",
    )

    status = industry_coverage._coverage_status(
        category=category,
        selected_runtime_scaffold_id="local-service-business",
        sni_mapping_count=0,
        target_is_runtime=True,
    )

    assert status == "fallback_only"


def test_unmapped_catch_all_landing_is_planned_not_missing_mapping() -> None:
    row = _rows_by_category()["landing"]

    assert row["sniMappingCount"] == 0
    assert row["coverageStatus"] == "planned"
    assert isinstance(row["recommendedActions"], list)


def test_rows_do_not_expose_sni_direct_pick_fields() -> None:
    forbidden = {
        "starterId",
        "scaffoldId",
        "variantId",
        "dossierId",
        "selectedDossiers",
    }

    for row in industry_coverage.industry_coverage_rows():
        assert forbidden.isdisjoint(row)


def test_content_branch_summary_totals_match_rows() -> None:
    rows = industry_coverage.industry_coverage_rows()
    summary = industry_coverage.content_branch_summary(rows)

    assert sum(row["categories"] for row in summary) == len(rows)
    assert sum(row["sniMappings"] for row in summary) == sum(
        row["sniMappingCount"] for row in rows
    )
    assert sum(row["variantCandidates"] for row in summary) == sum(
        row["variantCandidateCount"] for row in rows
    )
    assert sum(row["dossierCandidates"] for row in summary) == sum(
        row["dossierCandidateCount"] for row in rows
    )


def test_recommended_actions_include_planned_or_gap_case() -> None:
    rows = industry_coverage.industry_coverage_rows()
    action_rows = industry_coverage.recommended_action_rows(rows)

    assert action_rows
    assert any(
        row["coverageStatus"] in {"planned", "fallback_only", "missing_mapping"}
        for row in action_rows
    )
    assert any(
        action["action"] in {"create_variant_candidate", "review_capability_gap"}
        for action in action_rows
    )


def test_restaurant_runtime_active_after_path_a_promotion() -> None:
    """Restaurant-kategorin promoterades till active 2026-05-25 via
    GAP-backend-restaurant-activation. Coverage-raden ska nu spegla att
    activeScaffoldId och selectedRuntimeScaffoldId båda pekar mot
    restaurant-hospitality (inte fallback) och att supportStatus är
    active. Testen som tidigare kontrollerade planned/fallback-vägen
    ersätts av denna runtime-aktiv-invariant."""
    row = _rows_by_category()["restaurant"]

    assert row["supportStatus"] == "active"
    assert row["targetScaffoldId"] == "restaurant-hospitality"
    assert row["fallbackScaffoldId"] == "local-service-business"
    assert row["selectedRuntimeScaffoldId"] == "restaurant-hospitality"
    assert row["targetScaffoldStatus"] == "active-runtime"
    assert row["coverageStatus"] == "active_native"


def test_active_category_without_selected_runtime_is_not_native_or_taxonomy_drift() -> None:
    category = TaxonomyCategory(
        id="active-demo",
        labelSv="Aktiv demo",
        contentBranch="business",
        supportStatus="active",
        targetScaffoldId="local-service-business",
        activeScaffoldId="local-service-business",
        defaultVariantId="nordic-trust",
        expectedStarterId="marketing-base",
        requestedCapabilities=["contact-form"],
        candidateDossiers=[],
        recommendedPages=["Startsida"],
        rationale="Regression fixture.",
    )
    capability_state = {
        "unknownCapabilities": [],
        "capabilityGaps": [],
    }

    status = industry_coverage._coverage_status(
        category=category,
        selected_runtime_scaffold_id=None,
        sni_mapping_count=1,
        target_is_runtime=True,
    )
    reasons = industry_coverage._attention_reasons(
        category=category,
        selected_runtime_scaffold_id=None,
        default_variant_id="nordic-trust",
        has_default_variant=False,
        runtime_starter_id="",
        target_is_runtime=True,
        capability_state=capability_state,
        sni_mapping_count=1,
    )

    assert status == "active_fallback"
    assert status != "active_native"
    assert "missing_runtime_scaffold" in reasons
    assert "policy_asset_divergence" not in reasons


def test_candidate_briefs_include_category_context() -> None:
    row = _rows_by_category()["restaurant"]

    variant_brief = industry_coverage.build_variant_candidate_brief(row)
    dossier_brief = industry_coverage.build_dossier_candidate_brief(
        row,
        capability_id="carousel",
    )

    assert "wizardCategoryId: restaurant" in variant_brief
    assert "contentBranch: restaurant" in variant_brief
    assert "Candidate only" in variant_brief
    assert "data/variant-candidates" in variant_brief
    assert "wizardCategoryId: restaurant" in dossier_brief
    assert "carousel" in dossier_brief
    assert "soft, instructions-only" in dossier_brief
    assert "data/dossier-candidates" in dossier_brief
    assert "Do not write a generic industry description" in dossier_brief


def test_candidate_actions_use_candidate_directories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_variant: dict[str, Any] = {}
    captured_dossier: dict[str, Any] = {}

    def fake_generate_variant_candidates(**kwargs: Any) -> list[SimpleNamespace]:
        captured_variant.update(kwargs)
        return [
            SimpleNamespace(
                path=Path("data/variant-candidates/local-service-business/test.json"),
                payload={"id": "test", "enabled": False},
                source="deterministic-v1",
                model_used="deterministic",
            )
        ]

    def fake_generate_dossier_candidate(**kwargs: Any) -> SimpleNamespace:
        captured_dossier.update(kwargs)
        return SimpleNamespace(
            candidate_dir=Path("data/dossier-candidates/soft/carousel"),
            manifest={"id": "carousel", "enabled": False},
            instructions="# When to use\n",
            source="deterministic-v1",
            model_used="deterministic",
        )

    monkeypatch.setattr(
        building_blocks,
        "generate_variant_candidates",
        fake_generate_variant_candidates,
    )
    monkeypatch.setattr(
        building_blocks,
        "generate_dossier_candidate",
        fake_generate_dossier_candidate,
    )

    building_blocks.create_variant_candidate_from_ui(
        scaffold_id="local-service-business",
        brief="Local branch visual direction",
        variant_id="local-branch",
        use_llm=False,
        force=False,
    )
    building_blocks.create_dossier_candidate_from_ui(
        brief="Carousel guidance",
        candidate_id="carousel-guidance",
        capability="carousel",
        use_llm=False,
        force=False,
    )

    assert captured_variant["output_dir"] == building_blocks.VARIANT_CANDIDATES_DIR
    assert captured_dossier["output_dir"] == building_blocks.DOSSIER_CANDIDATES_DIR
    assert "packages/generation/orchestration" not in str(captured_variant["output_dir"])
    assert "packages/generation/orchestration" not in str(captured_dossier["output_dir"])


def test_backoffice_control_plane_renders_industry_coverage_before_asset_graph() -> None:
    source = inspect.getsource(building_blocks.view_control_plane)

    assert hasattr(building_blocks, "_render_industry_coverage")
    assert "Branschtäckning" in inspect.getsource(building_blocks._render_industry_coverage)
    assert source.index("_render_sni_discovery_mapping()") < source.index(
        "_render_industry_coverage()"
    )
    assert source.index("_render_industry_coverage()") < source.index(
        "_render_asset_graph()"
    )


def test_industry_coverage_helpers_are_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_write(*_args: Any, **_kwargs: Any) -> int:
        raise AssertionError("industry coverage helpers must not write files")

    def fail_mkdir(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("industry coverage helpers must not create directories")

    monkeypatch.setattr(Path, "write_text", fail_write)
    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    rows = industry_coverage.industry_coverage_rows()

    assert rows
    assert industry_coverage.content_branch_summary(rows)
    assert isinstance(industry_coverage.recommended_action_rows(rows), list)
    assert industry_coverage.build_variant_candidate_brief(rows[0])
