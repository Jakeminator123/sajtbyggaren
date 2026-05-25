"""Tests för scripts/run_eval_suite.py.

Täcker den rena Python-logiken: parsern måste hantera båda formerna av
`selectedDossiers` (oneOf array | object enligt
governance/schemas/site-plan.schema.json) och summary-writern måste
producera ett dict med de nio spårfälten plus oförändrad shape efter
round-trip till disk.

Inget test triggar `scripts/build_site.py` som subprocess — det är
täckt av `tests/test_builder_smoke.py`. Här bygger vi syntetiska
`data/runs/<runId>/`-strukturer via `tmp_path` så testerna är snabba
och deterministiska.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_eval_suite import (
    extract_rejected_capabilities,
    extract_selected_dossiers,
    make_eval_run_id,
    parse_case_artifacts,
)


def test_extract_selected_dossiers_array_form() -> None:
    plan = {"selectedDossiers": ["dossier-a", "dossier-b"]}
    assert extract_selected_dossiers(plan) == ["dossier-a", "dossier-b"]


def test_extract_selected_dossiers_object_form_required_bucket() -> None:
    plan = {
        "selectedDossiers": {
            "required": ["dossier-a", "dossier-b"],
            "recommended": ["dossier-c"],
            "conditional": [],
            "rejected": [{"id": "cap-x", "reason": "no Dossier yet"}],
        }
    }
    assert extract_selected_dossiers(plan) == ["dossier-a", "dossier-b"]


def test_extract_selected_dossiers_missing_field_returns_empty() -> None:
    assert extract_selected_dossiers({}) == []
    assert extract_selected_dossiers(None) == []


def test_extract_selected_dossiers_object_form_without_required() -> None:
    plan = {"selectedDossiers": {"recommended": ["dossier-a"]}}
    assert extract_selected_dossiers(plan) == []


def test_extract_selected_dossiers_skips_non_string_items() -> None:
    plan = {"selectedDossiers": ["valid", 42, None, "also-valid"]}
    assert extract_selected_dossiers(plan) == ["valid", "also-valid"]


def test_extract_rejected_capabilities_object_form() -> None:
    plan = {
        "selectedDossiers": {
            "required": ["dossier-a"],
            "rejected": [
                {"id": "cap-x", "reason": "no Dossier yet"},
                {"id": "cap-y", "reason": "out of scope"},
            ],
        }
    }
    rejected = extract_rejected_capabilities(plan)
    assert rejected == [
        {"id": "cap-x", "reason": "no Dossier yet"},
        {"id": "cap-y", "reason": "out of scope"},
    ]


def test_extract_rejected_capabilities_array_form_returns_empty() -> None:
    plan = {"selectedDossiers": ["dossier-a"]}
    assert extract_rejected_capabilities(plan) == []


def test_extract_rejected_capabilities_handles_missing_or_malformed() -> None:
    assert extract_rejected_capabilities({}) == []
    assert extract_rejected_capabilities(None) == []
    plan = {"selectedDossiers": {"rejected": [{"id": "ok", "reason": "x"}, "garbage", {}]}}
    assert extract_rejected_capabilities(plan) == [{"id": "ok", "reason": "x"}]


def _write_run_dir(
    base: Path,
    run_id: str,
    *,
    brief_source: str = "real",
    plan_source: str = "pinned",
    scaffold_id: str = "marketing-base",
    variant_id: str = "marketing-base.v1",
    starter_id: str = "marketing-base",
    selected: dict | list | None = None,
    quality_status: str = "ok",
    build_status: str = "skipped",
    repair_status: str = "not-needed",
    quality_checks: list[dict] | None = None,
) -> Path:
    run_dir = base / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if selected is None:
        selected = ["dossier-a"]
    if quality_checks is None:
        quality_checks = [
            {"name": "typecheck", "status": "skipped"},
            {"name": "route-scan", "status": "ok"},
            {"name": "build-status", "status": "skipped"},
            {"name": "policy-compliance", "status": "ok"},
        ]
    (run_dir / "site-brief.json").write_text(
        json.dumps({"briefSource": brief_source}), encoding="utf-8"
    )
    (run_dir / "site-plan.json").write_text(
        json.dumps(
            {
                "planSource": plan_source,
                "scaffoldId": scaffold_id,
                "variantId": variant_id,
                "starterId": starter_id,
                "selectedDossiers": selected,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "quality-result.json").write_text(
        json.dumps({"status": quality_status, "checks": quality_checks}), encoding="utf-8"
    )
    (run_dir / "build-result.json").write_text(
        json.dumps({"status": build_status}), encoding="utf-8"
    )
    (run_dir / "repair-result.json").write_text(
        json.dumps({"status": repair_status}), encoding="utf-8"
    )
    return run_dir


def test_parse_case_artifacts_happy_path(tmp_path: Path) -> None:
    run_dir = _write_run_dir(tmp_path, "20260525T-x-painter-palma")
    parsed = parse_case_artifacts(run_dir)
    assert parsed["briefSource"] == "real"
    assert parsed["planSource"] == "pinned"
    assert parsed["scaffoldId"] == "marketing-base"
    assert parsed["variantId"] == "marketing-base.v1"
    assert parsed["starterId"] == "marketing-base"
    assert parsed["selectedDossiers"] == ["dossier-a"]
    assert parsed["rejectedCapabilities"] == []
    assert parsed["qualityStatus"] == "ok"
    assert parsed["buildStatus"] == "skipped"
    assert parsed["repairStatus"] == "not-needed"
    assert {c["name"] for c in parsed["qualityChecks"]} == {
        "typecheck",
        "route-scan",
        "build-status",
        "policy-compliance",
    }


def test_parse_case_artifacts_object_form_selected_dossiers(tmp_path: Path) -> None:
    run_dir = _write_run_dir(
        tmp_path,
        "20260525T-x-foto-ram",
        selected={
            "required": ["interactive-game-loop"],
            "recommended": ["something-soft"],
            "rejected": [{"id": "cap-z", "reason": "not implemented"}],
        },
    )
    parsed = parse_case_artifacts(run_dir)
    assert parsed["selectedDossiers"] == ["interactive-game-loop"]
    assert parsed["rejectedCapabilities"] == [
        {"id": "cap-z", "reason": "not implemented"}
    ]


def test_parse_case_artifacts_partial_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "20260525T-x-broken"
    run_dir.mkdir()
    (run_dir / "site-brief.json").write_text(
        json.dumps({"briefSource": "mock-no-key"}), encoding="utf-8"
    )
    parsed = parse_case_artifacts(run_dir)
    assert parsed["briefSource"] == "mock-no-key"
    assert parsed["planSource"] is None
    assert parsed["scaffoldId"] is None
    assert parsed["selectedDossiers"] == []
    assert parsed["rejectedCapabilities"] == []
    assert parsed["qualityStatus"] is None
    assert parsed["qualityChecks"] == []
    assert parsed["buildStatus"] is None


def test_parse_case_artifacts_invalid_json_is_tolerant(tmp_path: Path) -> None:
    run_dir = tmp_path / "20260525T-x-junk"
    run_dir.mkdir()
    (run_dir / "site-brief.json").write_text("this is not json", encoding="utf-8")
    (run_dir / "site-plan.json").write_text("{ also not", encoding="utf-8")
    parsed = parse_case_artifacts(run_dir)
    assert parsed["briefSource"] is None
    assert parsed["planSource"] is None
    assert parsed["selectedDossiers"] == []


def test_make_eval_run_id_format() -> None:
    eval_run_id = make_eval_run_id()
    assert eval_run_id.startswith("eval-")
    head, tail = eval_run_id.split("-", 1)
    assert head == "eval"
    # The trailing part should look like <stamp>.<ms>Z-<8hex>.
    stamp_part, _, hex_part = tail.rpartition("-")
    assert stamp_part.endswith("Z")
    assert len(hex_part) == 8
    int(hex_part, 16)  # raises if not hex


def test_run_suite_writes_summary_with_missing_dossiers(tmp_path: Path) -> None:
    """run_suite must produce a summary file even when every case errors.

    We point ``--examples-dir`` at an empty directory so each case fails
    fast with "dossier not found" but the suite still finishes and
    writes a parseable JSON summary.
    """

    from scripts.run_eval_suite import run_suite

    empty_examples = tmp_path / "examples"
    empty_examples.mkdir()
    evals_dir = tmp_path / "evals"
    runs_dir = tmp_path / "runs"

    summary = run_suite(
        "quick",
        evals_dir=evals_dir,
        runs_dir=runs_dir,
        examples_dir=empty_examples,
        verbose=False,
    )

    assert summary["mode"] == "quick"
    assert len(summary["cases"]) == 4
    assert all(case["error"] for case in summary["cases"])

    summary_path = evals_dir / "eval-runs" / f"{summary['evalRunId']}.json"
    assert summary_path.exists()
    on_disk = json.loads(summary_path.read_text(encoding="utf-8"))
    assert on_disk["evalRunId"] == summary["evalRunId"]
    assert on_disk["mode"] == "quick"
    assert {case["siteId"] for case in on_disk["cases"]} == {
        "atelje-bird",
        "painter-palma",
        "foto-ram",
        "arcade-hall",
    }


def test_run_suite_rejects_unknown_mode(tmp_path: Path) -> None:
    from scripts.run_eval_suite import run_suite

    with pytest.raises(ValueError):
        run_suite(
            "nonsense",
            evals_dir=tmp_path / "evals",
            runs_dir=tmp_path / "runs",
            examples_dir=tmp_path / "examples",
            verbose=False,
        )
