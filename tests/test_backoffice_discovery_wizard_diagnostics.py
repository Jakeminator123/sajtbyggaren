"""Tests for read-only wizard field propagation diagnostics."""

from __future__ import annotations

from backoffice import discovery_wizard_diagnostics as diagnostics
from backoffice.paths import POLICIES_DIR


def _rows_by_answer_path() -> dict[str, dict[str, str]]:
    return {row["answerPath"]: dict(row) for row in diagnostics.wizard_generation_rows()}


def test_known_wizard_fields_are_present_in_diagnostics_table() -> None:
    rows = _rows_by_answer_path()

    for answer_path in (
        "answers.siteType",
        "answers.mustHave",
        "answers.primaryCta",
        "answers.companyName",
        "answers.contact.email",
        "answers.assets.logo",
        "answers.brand.primaryColorHex",
    ):
        assert answer_path in rows


def test_site_type_row_shows_taxonomy_chain() -> None:
    row = _rows_by_answer_path()["answers.siteType"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "deterministic"
    assert "discovery-taxonomy.v1.json" in row["sourcePath"]
    assert "scaffoldId" in row["destination"]
    assert "variantId" in row["destination"]
    assert "expectedStarterId" in row["destination"]
    assert "requestedCapabilities" in row["destination"]
    assert "starterId direkt" in row["explanation"]


def test_must_have_row_shows_capability_chain() -> None:
    row = _rows_by_answer_path()["answers.mustHave"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "deterministic"
    assert "_PAGE_TO_CAPABILITY" in row["sourceChain"]
    assert "requestedCapabilities" in row["destination"]
    assert "capability-map.v1.json" in row["sourcePath"]
    assert "dossier-selection.v1.json" in row["sourcePath"]


def test_capability_classifier_marks_empty_dossier_list_as_gap() -> None:
    classification = diagnostics.classify_capability(
        "fixture-gap",
        {"fixture-gap": {"dossiers": [], "comment": "planned fixture"}},
    )

    assert classification["status"] == "gap"
    assert "planned fixture" in classification["explanation"]


def test_capability_classifier_marks_unknown_fixture_as_unknown() -> None:
    capability_map = diagnostics.load_capability_map()
    unknown = "__test_unknown_capability__"
    assert unknown not in capability_map

    classification = diagnostics.classify_capability(unknown, capability_map)

    assert classification["status"] == "unknown"


def test_prompt_signal_fields_are_not_marked_as_missing_destination() -> None:
    rows = _rows_by_answer_path()

    row = rows["answers.brand.designStyle"]
    assert row["status"] == "active"
    assert row["propagationLevel"] == "prompt-signal"

    diagnostic = rows["answers.scrapedFields"]
    assert diagnostic["status"] == "no-known-destination"
    assert diagnostic["propagationLevel"] == "diagnostic-only"


def test_brand_color_rows_show_downstream_gap_without_losing_active_mapping() -> None:
    row = _rows_by_answer_path()["answers.brand.primaryColorHex"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "downstream-gap"
    assert "brand.primaryColorHex" in row["destination"]
    assert "B140" in row["explanation"]


def test_diagnostics_helper_does_not_expose_write_api_or_modify_policies() -> None:
    taxonomy_path = POLICIES_DIR / "discovery-taxonomy.v1.json"
    capability_path = POLICIES_DIR / "capability-map.v1.json"
    before_taxonomy = taxonomy_path.read_text(encoding="utf-8")
    before_capability = capability_path.read_text(encoding="utf-8")

    assert not [
        name
        for name in dir(diagnostics)
        if name.startswith(("save", "write", "atomic_write"))
    ]
    diagnostics.wizard_generation_rows()

    assert taxonomy_path.read_text(encoding="utf-8") == before_taxonomy
    assert capability_path.read_text(encoding="utf-8") == before_capability


def test_diagnostics_status_and_propagation_values_are_bounded() -> None:
    rows = diagnostics.wizard_generation_rows()
    statuses = {row["status"] for row in rows}
    propagation_levels = {row["propagationLevel"] for row in rows}

    assert statuses <= set(diagnostics.STATUS_ORDER)
    assert propagation_levels <= set(diagnostics.PROPAGATION_ORDER)
    assert "active-with-gap-explanation" not in statuses
