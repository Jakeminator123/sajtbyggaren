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
    # Promotades till warm-bistro 2026-05-25 när restaurant-kategorin
    # flippades till supportStatus=active via GAP-backend-restaurant-
    # activation. Speglar plan.py:_DEFAULT_VARIANT_BY_SCAFFOLD.
    assert row["discoveryDefaultVariantId"] == "warm-bistro"
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


# ---------------------------------------------------------------------------
# Confidence breakdown
# ---------------------------------------------------------------------------


def test_confidence_breakdown_counts_each_level() -> None:
    rows = sni_diagnostics.mapping_rows()
    breakdown = sni_diagnostics.confidence_breakdown(rows)

    assert set(breakdown.keys()) == {"high", "medium", "low", "other"}
    assert breakdown["high"] + breakdown["medium"] + breakdown["low"] + breakdown["other"] == len(rows)
    assert breakdown["high"] >= 1
    assert breakdown["medium"] >= 0


def test_confidence_breakdown_handles_unknown_levels() -> None:
    fake_rows = [
        {"confidence": "high"},
        {"confidence": "medium"},
        {"confidence": "low"},
        {"confidence": "weird"},
        {"confidence": ""},
        {"confidence": None},
    ]

    breakdown = sni_diagnostics.confidence_breakdown(fake_rows)

    assert breakdown["high"] == 1
    assert breakdown["medium"] == 1
    assert breakdown["low"] == 1
    assert breakdown["other"] == 3  # weird + "" + None all fall into "other"


# ---------------------------------------------------------------------------
# Taxonomy coverage gaps
# ---------------------------------------------------------------------------


def test_taxonomy_coverage_gaps_returns_categories_without_sni_mapping() -> None:
    gaps = sni_diagnostics.taxonomy_coverage_gaps()
    gap_ids = {gap["wizardCategoryId"] for gap in gaps}

    # Discovery Taxonomy har 25 kategorier; SNI Discovery Map täcker 19
    # unika kategorier. De 6 utan mappning ska finnas i listan.
    assert "landing" in gap_ids  # Single-page-koncept, ingen relevant SNI
    assert "other" in gap_ids   # Catch-all, per design utan SNI-koppling
    assert "business" in gap_ids  # Catch-all för generisk tjänsteverksamhet
    # Kategorier vi täcker ska INTE finnas i listan
    assert "restaurant" not in gap_ids
    assert "construction" not in gap_ids
    assert "tech" not in gap_ids


def test_taxonomy_coverage_gaps_includes_label_and_support_status() -> None:
    gaps = sni_diagnostics.taxonomy_coverage_gaps()
    sample = next(gap for gap in gaps if gap["wizardCategoryId"] == "landing")

    assert sample["labelSv"]
    assert sample["supportStatus"] in {"active", "fallback", "planned", "disabled"}
    assert isinstance(sample["rationale"], str)


# ---------------------------------------------------------------------------
# Parent chain lookup
# ---------------------------------------------------------------------------


def test_lookup_parent_chain_for_exact_subclass_code_returns_full_chain() -> None:
    chain = sni_diagnostics.lookup_parent_chain("56110")

    codes = [entry["code"] for entry in chain]
    levels = [entry["level"] for entry in chain]

    assert codes == ["I", "56", "561", "5611", "56110"]
    assert levels == ["section", "division", "group", "class", "subclass"]


def test_lookup_parent_chain_normalizes_dotted_form() -> None:
    chain = sni_diagnostics.lookup_parent_chain("56.110")

    codes = [entry["code"] for entry in chain]
    assert codes == ["I", "56", "561", "5611", "56110"]


def test_lookup_parent_chain_truncates_synthetic_prefix_to_real_code() -> None:
    # 56100 är operatör-vänlig form som inte är en faktisk SNI-kod —
    # närmaste verkliga match är 561. Chainet ska följa 561, inte vara tomt.
    chain = sni_diagnostics.lookup_parent_chain("56100")
    codes = [entry["code"] for entry in chain]

    assert codes == ["I", "56", "561"]


def test_lookup_parent_chain_returns_empty_for_unknown_code() -> None:
    # SNI har inga koder som börjar med 0 eller bara består av "Z"-letters,
    # och tomma/None ska kortslutas direkt i helpern.
    assert sni_diagnostics.lookup_parent_chain("ZZZ") == []
    assert sni_diagnostics.lookup_parent_chain("") == []
    assert sni_diagnostics.lookup_parent_chain(None) == []
    assert sni_diagnostics.lookup_parent_chain("00") == []


def test_lookup_parent_chain_truncates_to_existing_short_prefix() -> None:
    # "999" trunkeras till "99" som är en faktisk SNI-division (under V);
    # kontraktet är "närmaste verkliga match", inte "exakt eller inget".
    chain = sni_diagnostics.lookup_parent_chain("999")
    codes = [entry["code"] for entry in chain]

    assert codes  # icke-tomt eftersom 99 är en real division
    assert codes[-1] == "99"
    assert codes[0] in {"V", "U"}  # division 99 ligger under section V eller U
