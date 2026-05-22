"""Tests for read-only wizard field propagation diagnostics.

These tests are the contract between
``apps/viewser/components/discovery-wizard/wizard-constants.ts`` and
``backoffice/discovery_wizard_diagnostics.py``. Adding a new CTA chip or
must-have option to the wizard must surface in the Backoffice diagnostic;
the per-value coverage tests guarantee that.
"""

from __future__ import annotations

import pytest

from backoffice import discovery_wizard_diagnostics as diagnostics
from backoffice.paths import POLICIES_DIR, REPO_ROOT


def _rows_by_answer_path() -> dict[str, dict[str, str]]:
    return {row["answerPath"]: dict(row) for row in diagnostics.wizard_generation_rows()}


# ---------------------------------------------------------------------------
# Drift detection: wizard-constants.ts vs Python diagnostic
# ---------------------------------------------------------------------------


def test_cta_options_parser_returns_known_swedish_chip_labels() -> None:
    cta_options = diagnostics.parse_cta_options()

    assert "Boka tid" in cta_options
    assert "Läs mer" in cta_options
    assert "Ladda ner" in cta_options
    assert len(cta_options) >= 5
    assert all(isinstance(value, str) and value.strip() for value in cta_options)
    assert len(cta_options) == len(set(cta_options)), (
        "CTA_OPTIONS must not contain duplicates"
    )


def test_must_have_options_parser_returns_known_swedish_chip_labels() -> None:
    must_have_options = diagnostics.parse_must_have_options()

    for expected in (
        "Startsida / Hero",
        "Om oss / Om mig",
        "Kontaktformulär",
        "Priser och paket",
        "Bokning online",
        "FAQ",
        "Bildgalleri",
        "Karta / Hitta hit",
        "Vårt team",
        "Portfolio / Case",
        "Blogg / Nyheter",
        "Nyhetsbrev",
        "Kundrecensioner",
        "Webshop / Produkter",
        "Meny / Matsedel",
    ):
        assert expected in must_have_options, (
            f"{expected!r} missing from MUST_HAVE_OPTIONS - either wizard-"
            "constants.ts changed or the parser broke."
        )
    assert len(must_have_options) == len(set(must_have_options)), (
        "MUST_HAVE_OPTIONS must not contain duplicates"
    )


def test_parser_raises_when_array_block_is_missing() -> None:
    with pytest.raises(RuntimeError, match="block not found"):
        diagnostics._parse_wizard_option_array("DEFINITELY_NOT_A_REAL_ARRAY")


# ---------------------------------------------------------------------------
# Per-value coverage: every wizard chip gets a Backoffice row
# ---------------------------------------------------------------------------


def test_every_cta_option_value_gets_a_diagnostic_row() -> None:
    rows = _rows_by_answer_path()
    cta_options = diagnostics.parse_cta_options()

    for option in cta_options:
        answer_path = f"answers.primaryCta[{option}]"
        assert answer_path in rows, (
            f"Wizard CTA chip {option!r} (from CTA_OPTIONS) is missing a "
            "Backoffice diagnostic row. The diagnostic must surface every "
            "wizard UI value - unmapped chips have to be visible, not hidden."
        )


def test_every_must_have_option_value_gets_a_diagnostic_row() -> None:
    rows = _rows_by_answer_path()
    must_have_options = diagnostics.parse_must_have_options()

    for option in must_have_options:
        answer_path = f"answers.mustHave[{option}]"
        assert answer_path in rows, (
            f"Wizard must-have chip {option!r} (from MUST_HAVE_OPTIONS) is "
            "missing a Backoffice diagnostic row. Unmapped or gap chips "
            "have to be visible, not hidden."
        )


# ---------------------------------------------------------------------------
# Specific status truths (acceptance criteria from the task description)
# ---------------------------------------------------------------------------


def test_lasmer_cta_is_surfaced_as_unmapped_not_active_deterministic() -> None:
    row = _rows_by_answer_path()["answers.primaryCta[Läs mer]"]

    assert row["status"] == "no-known-destination"
    assert row["propagationLevel"] == "diagnostic-only"
    assert "saknar" in row["explanation"].lower()
    assert "_CTA_TO_CONVERSION_GOAL" in row["explanation"]
    assert "Läs mer" in row["explanation"]


def test_priser_och_paket_must_have_is_route_emission_not_capability_gap() -> None:
    row = _rows_by_answer_path()["answers.mustHave[Priser och paket]"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "deterministic"
    assert "/priser" in row["destination"]
    assert "_WIZARD_ROUTE_DEFINITIONS" in row["destination"]
    assert "_WIZARD_ROUTE_RENDERERS" in row["sourceChain"]
    assert "local-service-business" in row["destination"]


@pytest.mark.parametrize(
    "label,expected_path",
    [
        ("FAQ", "/faq"),
        ("Bildgalleri", "/galleri"),
        ("Karta / Hitta hit", "/karta"),
        ("Vårt team", "/team"),
        ("Priser och paket", "/priser"),
        ("Portfolio / Case", "/portfolio"),
    ],
)
def test_supported_wizard_routes_show_as_active_deterministic_emission(
    label: str, expected_path: str
) -> None:
    row = _rows_by_answer_path()[f"answers.mustHave[{label}]"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "deterministic"
    assert expected_path in row["destination"]
    assert "_WIZARD_ROUTE_DEFINITIONS" in row["destination"]


@pytest.mark.parametrize(
    "label,reason_fragment",
    [
        ("Bokning online", "booking integration"),
        ("Blogg / Nyheter", "editorial tooling"),
        ("Nyhetsbrev", "newsletter integration"),
    ],
)
def test_unsupported_wizard_pages_show_warning_shape_with_specific_reason(
    label: str, reason_fragment: str
) -> None:
    row = _rows_by_answer_path()[f"answers.mustHave[{label}]"]

    assert row["status"] == "gap"
    assert row["propagationLevel"] == "downstream-gap"
    assert "pageIntentWarnings" in row["destination"]
    assert reason_fragment in row["destination"]
    assert "_WIZARD_ROUTE_UNSUPPORTED_REASONS" in row["sourceChain"]


@pytest.mark.parametrize(
    "label,scaffold_route_id",
    [
        ("Startsida / Hero", "home"),
        ("Om oss / Om mig", "about"),
        ("Kontaktformulär", "contact"),
    ],
)
def test_scaffold_default_must_have_pages_show_as_basroute(
    label: str, scaffold_route_id: str
) -> None:
    row = _rows_by_answer_path()[f"answers.mustHave[{label}]"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "deterministic"
    assert "scaffold default" in row["destination"]
    assert scaffold_route_id in row["destination"]
    assert "local-service-business" in row["destination"]
    assert "ecommerce-lite" in row["destination"]


# ---------------------------------------------------------------------------
# Parent rows must reflect aggregate truth, not lie about determinism
# ---------------------------------------------------------------------------


def test_must_have_parent_row_reflects_aggregate_when_any_child_is_gap() -> None:
    rows = _rows_by_answer_path()
    parent = rows["answers.mustHave"]
    child_paths = [
        path
        for path in rows
        if path.startswith("answers.mustHave[") and path.endswith("]")
    ]
    child_statuses = {rows[path]["status"] for path in child_paths}

    if "gap" in child_statuses or "no-known-destination" in child_statuses:
        assert parent["status"] != "active", (
            "Parent row answers.mustHave must not claim status=active when "
            "some wizard mustHave values are unsupported or unmapped. "
            "Aggregate worst-of keeps the parent honest."
        )
        assert parent["propagationLevel"] != "deterministic", (
            "Parent row answers.mustHave must not claim deterministic "
            "propagation when some child values are gap/unmapped."
        )


def test_primary_cta_parent_row_reflects_lasmer_unmapped_state() -> None:
    rows = _rows_by_answer_path()
    parent = rows["answers.primaryCta"]
    lasmer = rows["answers.primaryCta[Läs mer]"]

    assert lasmer["status"] == "no-known-destination"
    assert parent["status"] != "active", (
        "answers.primaryCta parent must not claim active while a known CTA "
        "(Läs mer) is unmapped."
    )
    assert parent["propagationLevel"] != "deterministic"


# ---------------------------------------------------------------------------
# Taxonomy supportStatus handling (disabled must not show as planned)
# ---------------------------------------------------------------------------


def test_disabled_support_status_is_classified_as_gap_not_planned() -> None:
    status, label = diagnostics._classify_taxonomy_support_status("disabled")

    assert status == "gap"
    assert "disabled" in label.lower()
    assert "planned" not in label.lower()


@pytest.mark.parametrize(
    "support_status,expected_status",
    [
        ("active", "active"),
        ("fallback", "fallback"),
        ("planned", "planned"),
        ("disabled", "gap"),
        ("unknown-string", "unknown"),
    ],
)
def test_taxonomy_support_status_classifier_is_truthful(
    support_status: str, expected_status: str
) -> None:
    status, _label = diagnostics._classify_taxonomy_support_status(support_status)
    assert status == expected_status


# ---------------------------------------------------------------------------
# Original guard tests (taxonomy, capability classifier, value bounds)
# ---------------------------------------------------------------------------


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


def test_capability_classifier_applies_resolver_alias_normalisation() -> None:
    capability_map = {
        "newsletter-subscribe": {
            "dossiers": [],
            "comment": "alias target",
        }
    }

    classification = diagnostics.classify_capability("newsletter", capability_map)

    assert classification["status"] == "gap"
    assert "alias target" in classification["explanation"]


def test_prompt_signal_fields_are_not_marked_as_missing_destination() -> None:
    rows = _rows_by_answer_path()

    row = rows["answers.brand.designStyle"]
    assert row["status"] == "active"
    assert row["propagationLevel"] == "prompt-signal"

    diagnostic = rows["answers.scrapedFields"]
    assert diagnostic["status"] == "no-known-destination"
    assert diagnostic["propagationLevel"] == "diagnostic-only"


def test_brand_color_rows_show_deterministic_token_mapping() -> None:
    row = _rows_by_answer_path()["answers.brand.primaryColorHex"]

    assert row["status"] == "active"
    assert row["propagationLevel"] == "deterministic"
    assert "brand.primaryColorHex" in row["destination"]
    assert "CSS-tokenoverride" in row["explanation"]


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


def test_diagnostic_does_not_import_private_underscore_names_from_runtime() -> None:
    """The diagnostic must use the small public helpers, not private
    ``_``-prefixed imports from the runtime packages. This keeps the
    Backoffice/runtime boundary clean and makes the public surface
    discoverable.
    """
    diagnostics_source = (
        REPO_ROOT / "backoffice" / "discovery_wizard_diagnostics.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "_PAGE_TO_CAPABILITY",
        "_CTA_TO_CONVERSION_GOAL",
        "_WIZARD_ROUTE_DEFINITIONS",
        "_WIZARD_ROUTE_SCAFFOLDS",
        "_WIZARD_ROUTE_UNSUPPORTED_REASONS",
        "_PAGE_TO_ROUTE_HINT",
    ):
        import_line = f"import {forbidden}"
        assert import_line not in diagnostics_source, (
            f"Diagnostic must not import private runtime name {forbidden!r}; "
            "use the public get_* helpers in resolve.py / plan.py instead."
        )
