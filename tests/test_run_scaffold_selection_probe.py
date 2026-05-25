"""Tests för scripts/run_scaffold_selection_probe.py.

Inga OpenAI-anrop och inga ``dev_generate.py``-subprocess. Vi täcker
bara den rena Python-logiken: dossier-/rejected-extractorerna, probe-id-
formatet, scaffold-existence-checken och kategoriserings-strängarna.
LLM-vägen är täckt av separat end-to-end körning som operatören gör
manuellt med ``python scripts/run_scaffold_selection_probe.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest  # noqa: F401  -- pytest discovery convention

from scripts.run_scaffold_selection_probe import (
    PROBE_CASES,
    _classify_runtime_readiness,
    _extract_rejected_capabilities,
    _extract_selected_dossiers,
    _scaffold_dir_status,
    make_probe_run_id,
    write_markdown_report,
)


def test_probe_cases_match_registry_size() -> None:
    """Probe-listan ska täcka exakt scaffold-contract.v1.json:s registry.

    Vi laddar registry från filen (utan att importera planner-modulen) och
    kollar att probe-listan har samma id-set. Detta håller proben i synk
    med governance-policyn när nya scaffolds läggs till.
    """

    import json

    repo_root = Path(__file__).resolve().parent.parent
    policy_path = (
        repo_root / "governance" / "policies" / "scaffold-contract.v1.json"
    )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    registry_ids = {entry["id"] for entry in policy["primaryScaffoldRegistry"]}
    probe_ids = {case["expectedScaffold"] for case in PROBE_CASES}
    assert probe_ids == registry_ids, (
        "Probe cases drifted from scaffold-contract.v1.json registry. "
        f"Only in probe: {probe_ids - registry_ids}. "
        f"Only in registry: {registry_ids - probe_ids}."
    )


def test_extract_selected_dossiers_array_form() -> None:
    plan = {"selectedDossiers": ["dossier-a", "dossier-b"]}
    assert _extract_selected_dossiers(plan) == ["dossier-a", "dossier-b"]


def test_extract_selected_dossiers_object_form() -> None:
    plan = {
        "selectedDossiers": {
            "required": ["dossier-a"],
            "recommended": ["dossier-b"],
        }
    }
    assert _extract_selected_dossiers(plan) == ["dossier-a"]


def test_extract_selected_dossiers_missing_returns_empty() -> None:
    assert _extract_selected_dossiers({}) == []
    assert _extract_selected_dossiers(None) == []


def test_extract_rejected_capabilities_object_form() -> None:
    plan = {
        "selectedDossiers": {
            "required": ["dossier-a"],
            "rejected": [
                {"id": "cap-x", "reason": "no Dossier"},
                {"id": "cap-y", "reason": "out of scope"},
                "garbage",
                {},
            ],
        }
    }
    assert _extract_rejected_capabilities(plan) == [
        {"id": "cap-x", "reason": "no Dossier"},
        {"id": "cap-y", "reason": "out of scope"},
    ]


def test_extract_rejected_capabilities_array_form_returns_empty() -> None:
    plan = {"selectedDossiers": ["dossier-a"]}
    assert _extract_rejected_capabilities(plan) == []


def test_scaffold_dir_status_real_scaffold_on_disk() -> None:
    status = _scaffold_dir_status("local-service-business")
    assert status["directoryExists"]
    assert status["scaffoldJsonExists"]


def test_scaffold_dir_status_registry_placeholder() -> None:
    # ``saas-product`` is still a planned registry placeholder (no on-disk
    # scaffold directory). ``professional-services`` and ``clinic-healthcare``
    # both moved to active in Path B steps 12 and 13 (2026-05-25), so they
    # can no longer represent the placeholder case here.
    status = _scaffold_dir_status("saas-product")
    assert status["directoryExists"] is False
    assert status["scaffoldJsonExists"] is False


def test_make_probe_run_id_format() -> None:
    probe_id = make_probe_run_id()
    assert probe_id.startswith("scaffold-probe-")
    assert re.fullmatch(
        r"scaffold-probe-\d{8}T\d{6}\.\d{3}Z-[0-9a-f]{8}", probe_id
    ), f"unexpected format: {probe_id}"


def test_classify_runtime_readiness_real_match() -> None:
    text = _classify_runtime_readiness(
        "local-service-business",
        "local-service-business",
        {"local-service-business": "marketing-base"},
        {"directoryExists": True, "scaffoldJsonExists": True},
    )
    assert text == "planner picked the intended scaffold"


def test_classify_runtime_readiness_placeholder() -> None:
    # See ``test_scaffold_dir_status_registry_placeholder`` — we switched
    # the placeholder probe to ``saas-product`` after professional-services
    # graduated to active in Path B step 13.
    text = _classify_runtime_readiness(
        "saas-product",
        "local-service-business",
        {"local-service-business": "marketing-base"},
        {"directoryExists": False, "scaffoldJsonExists": False},
    )
    assert "registry-placeholder" in text


def test_classify_runtime_readiness_no_starter_mapping() -> None:
    text = _classify_runtime_readiness(
        "restaurant-hospitality",
        "restaurant-hospitality",
        {},
        {"directoryExists": True, "scaffoldJsonExists": True},
    )
    assert "no starter mapping" in text


def test_write_markdown_report_round_trip(tmp_path: Path) -> None:
    summary = {
        "probeId": "scaffold-probe-test-0000",
        "createdAt": "2026-05-25T00:00:00.000Z",
        "openaiKeyPresent": True,
        "totalCases": 1,
        "cases": [
            {
                "promptId": "ecommerce-lite",
                "expectedScaffold": "ecommerce-lite",
                "expectedHasScaffoldJson": True,
                "scaffoldId": "ecommerce-lite",
                "variantId": "clean-store",
                "starterId": "commerce-base",
                "selectedMatchesExpected": True,
                "comment": "planner picked the intended scaffold",
                "error": None,
            }
        ],
    }
    out = tmp_path / "report.md"
    write_markdown_report(summary, out)
    content = out.read_text(encoding="utf-8")
    assert "scaffold-probe-test-0000" in content
    assert "ecommerce-lite" in content
    assert "1 / 1" in content
