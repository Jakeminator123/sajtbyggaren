"""Tests for Backoffice branschtäckning helpers."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backoffice import industry_coverage
from backoffice.views import building_blocks
from packages.generation.discovery.taxonomy import load_discovery_taxonomy


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


def test_unmapped_categories_are_flagged_not_fatal() -> None:
    row = _rows_by_category()["landing"]

    assert row["sniMappingCount"] == 0
    assert row["coverageStatus"] == "missing_mapping"
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


def test_existing_restaurant_asset_and_taxonomy_status_are_separate() -> None:
    row = _rows_by_category()["restaurant"]

    assert row["supportStatus"] == "planned"
    assert row["targetScaffoldId"] == "restaurant-hospitality"
    assert row["fallbackScaffoldId"] == "local-service-business"
    assert row["selectedRuntimeScaffoldId"] == "local-service-business"
    assert row["targetScaffoldStatus"] in {"active-runtime", "planned"}
    assert row["coverageStatus"] == "planned"
    if row["targetScaffoldStatus"] == "active-runtime":
        assert "policy_asset_divergence" in row["attentionReasons"]


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
