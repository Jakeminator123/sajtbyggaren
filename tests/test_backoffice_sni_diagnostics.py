"""Tests for Backoffice SNI → Discovery diagnostic helper.

Modulen ``backoffice/sni_diagnostics.py`` är read-only. Testerna låser
att radbyggaren visar Discovery Taxonomy-kedjan, lookup-helpern hanterar
trasiga koder utan exception och att SNI aldrig exponeras som direkt
starter/scaffold/variant/Dossier-val.
"""

from __future__ import annotations

from backoffice import sni_diagnostics


def test_warning_lines_are_in_swedish_and_explicit() -> None:
    text = "\n".join(sni_diagnostics.WARNING_LINES_SV)
    assert "branschsignal" in text
    assert "starter" in text
    assert "Discovery Taxonomy" in text


def test_mapping_rows_cover_all_policy_entries() -> None:
    rows = sni_diagnostics.mapping_rows()
    levels = {row["sniLevel"] for row in rows}

    assert "division" in levels
    assert "group" in levels
    assert len(rows) >= 20


def test_mapping_rows_include_discovery_taxonomy_chain_for_known_category() -> None:
    rows = sni_diagnostics.mapping_rows()
    restaurant_rows = [row for row in rows if row["wizardCategoryId"] == "restaurant"]

    assert restaurant_rows
    row = next(row for row in restaurant_rows if row["sniCode"] == "56")
    assert row["sniLevel"] == "division"
    assert row["sniLabelSv"].startswith("Restaurang")
    assert row["categoryKnown"] is True
    assert row["discoveryTargetScaffoldId"] == "restaurant-hospitality"
    assert row["discoveryFallbackScaffoldId"] == "local-service-business"
    assert row["discoveryDefaultVariantId"] == "nordic-trust"
    assert row["discoveryExpectedStarterId"] == "marketing-base"


def test_mapping_summary_counts_divisions_groups_and_unique_categories() -> None:
    rows = sni_diagnostics.mapping_rows()
    summary = sni_diagnostics.mapping_summary(rows)

    assert summary["total"] == len(rows)
    assert summary["divisionMappings"] >= 10
    assert summary["groupOverrides"] >= 5
    assert summary["uniqueCategories"] >= 5
    assert summary["unknownCategories"] == 0


def test_reference_summary_reads_committed_json() -> None:
    payload = sni_diagnostics.load_sni_reference()
    summary = sni_diagnostics.reference_summary(payload)

    assert summary["section"] >= 20
    assert summary["division"] >= 80
    assert summary["group"] >= 200
    assert summary["class"] >= 500
    assert summary["subclass"] >= 700
    assert summary["total"] >= 1500


def test_lookup_row_resolves_full_chain_for_known_code() -> None:
    row = sni_diagnostics.lookup_row("56100")

    assert row["matchedLevel"] == "group"
    assert row["matchedSniCode"] == "561"
    assert row["wizardCategoryId"] == "restaurant"
    assert row["categoryKnown"] is True
    assert row["discoveryTargetScaffoldId"] == "restaurant-hospitality"


def test_lookup_row_returns_unknown_without_exception_for_garbage_input() -> None:
    for value in ("foo", "", None, "00", "Z"):
        row = sni_diagnostics.lookup_row(value)
        assert row["matchedLevel"] == "unknown"
        assert row["wizardCategoryId"] is None
        assert row["discoveryTargetScaffoldId"] is None


def test_lookup_row_never_exposes_direct_pick_fields() -> None:
    row = sni_diagnostics.lookup_row("56100")
    for forbidden in ("starterId", "scaffoldId", "variantId", "dossierId", "selectedDossiers"):
        assert forbidden not in row


def test_filter_rows_by_category_returns_matching_rows() -> None:
    rows = sni_diagnostics.mapping_rows()
    construction_rows = sni_diagnostics.filter_rows_by_category(rows, "construction")

    assert construction_rows
    assert all(row["wizardCategoryId"] == "construction" for row in construction_rows)


def test_filter_rows_by_category_alla_returns_full_list() -> None:
    rows = sni_diagnostics.mapping_rows()
    full = sni_diagnostics.filter_rows_by_category(rows, "Alla")

    assert full == rows


def test_filter_rows_by_category_none_returns_full_list() -> None:
    rows = sni_diagnostics.mapping_rows()
    full = sni_diagnostics.filter_rows_by_category(rows, None)

    assert full == rows
