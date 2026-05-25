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
    compute_exit_code,
    extract_rejected_capabilities,
    extract_selected_dossiers,
    format_case_list,
    get_full_case_ids,
    get_quick_case_ids,
    make_eval_run_id,
    parse_case_artifacts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_eval_case_lists_are_the_cli_source_of_truth() -> None:
    assert get_quick_case_ids() == (
        "atelje-bird",
        "painter-palma",
        "foto-ram",
        "arcade-hall",
        "cafe-bistro",
    )
    assert get_full_case_ids() == (
        "painter-palma",
        "atelje-bird",
        "cafe-bistro",
    )
    assert format_case_list(get_full_case_ids(), separator=" + ") == (
        "painter-palma + atelje-bird + cafe-bistro"
    )


def test_full_suite_covers_local_ecommerce_and_restaurant_scaffolds() -> None:
    scaffolds: set[str] = set()
    for case_id in get_full_case_ids():
        path = REPO_ROOT / "examples" / f"{case_id}.project-input.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        scaffolds.add(payload["scaffoldId"])

    assert scaffolds == {
        "local-service-business",
        "ecommerce-lite",
        "restaurant-hospitality",
    }


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

    from scripts.run_eval_suite import QUICK_CASES

    summary = run_suite(
        "quick",
        evals_dir=evals_dir,
        runs_dir=runs_dir,
        examples_dir=empty_examples,
        verbose=False,
    )

    assert summary["mode"] == "quick"
    # Cases follow the canonical QUICK_CASES tuple; using set equality
    # below keeps the assertion working when new fixtures are added to
    # the suite (e.g. cafe-bistro from Issue #90).
    assert len(summary["cases"]) == len(QUICK_CASES)
    assert all(case["error"] for case in summary["cases"])

    summary_path = evals_dir / "eval-runs" / f"{summary['evalRunId']}.json"
    assert summary_path.exists()
    on_disk = json.loads(summary_path.read_text(encoding="utf-8"))
    assert on_disk["evalRunId"] == summary["evalRunId"]
    assert on_disk["mode"] == "quick"
    assert {case["siteId"] for case in on_disk["cases"]} == set(QUICK_CASES)


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


def test_compute_exit_code_clean_suite_returns_zero() -> None:
    summary = {
        "cases": [
            {"siteId": "a", "error": None},
            {"siteId": "b", "error": ""},
        ],
    }
    assert compute_exit_code(summary) == 0


def test_compute_exit_code_any_failure_returns_one() -> None:
    summary = {
        "cases": [
            {"siteId": "a", "error": None},
            {"siteId": "b", "error": "dossier not found: ..."},
            {"siteId": "c", "error": None},
        ],
    }
    assert compute_exit_code(summary) == 1


def test_compute_exit_code_empty_summary_returns_zero() -> None:
    """A summary with no cases at all should not signal failure here.

    Empty case lists only happen in tests that exercise unknown modes
    via ``run_suite`` (which raises before populating ``cases``). The
    real CLI always produces at least one case, so degrading exit codes
    on emptiness would surprise the operator without surfacing a
    concrete failure.
    """

    assert compute_exit_code({"cases": []}) == 0
    assert compute_exit_code({}) == 0


def test_run_suite_with_missing_dossiers_drives_exit_one(tmp_path: Path) -> None:
    """When every case errors, compute_exit_code must signal failure.

    Pairs with test_run_suite_writes_summary_with_missing_dossiers
    above — the same scenario, but checking the new
    ``compute_exit_code`` contract introduced in response to the
    Codex P1 review on PR #87.
    """

    from scripts.run_eval_suite import run_suite

    empty_examples = tmp_path / "examples"
    empty_examples.mkdir()
    summary = run_suite(
        "quick",
        evals_dir=tmp_path / "evals",
        runs_dir=tmp_path / "runs",
        examples_dir=empty_examples,
        verbose=False,
    )
    assert compute_exit_code(summary) == 1


def test_run_one_case_records_generated_dir(tmp_path: Path) -> None:
    """Full-mode cases pass --generated-dir to build_site.py.

    We do not actually invoke build_site.py here — the dossier is
    missing on purpose so the case errors fast — but we verify that
    ``generatedDir`` lands in the case dict so summary readers can
    confirm each full-mode run had an isolated target directory.
    """

    from scripts.run_eval_suite import run_one_case

    case_generated = tmp_path / "evals" / "generated" / "evalX" / "site-a"
    case = run_one_case(
        "site-a",
        skip_build=False,
        runs_dir=tmp_path / "runs",
        examples_dir=tmp_path / "examples",
        generated_dir=case_generated,
        verbose=False,
    )
    assert case["generatedDir"] == str(case_generated)
    assert case["error"] and "dossier not found" in case["error"]


def _discover_on_disk_scaffold_ids() -> set[str]:
    """Return the set of scaffoldIds whose directory + scaffold.json exist.

    Mirrors the discovery that ``run_scaffold_selection_probe.py`` does
    (an on-disk scaffold is a folder under
    ``packages/generation/orchestration/scaffolds/`` that contains a
    ``scaffold.json``). Reading the filesystem keeps the coverage
    assertion below honest when a fourth scaffold (e.g.
    professional-services from Issue #91) lands; a hard-coded set of
    expected scaffoldIds would silently grant a pass.
    """

    repo_root = Path(__file__).resolve().parent.parent
    scaffolds_dir = repo_root / "packages" / "generation" / "orchestration" / "scaffolds"
    if not scaffolds_dir.is_dir():
        return set()
    return {
        child.name
        for child in scaffolds_dir.iterdir()
        if child.is_dir() and (child / "scaffold.json").is_file()
    }


def _scaffolds_covered_by(case_ids: tuple[str, ...]) -> set[str]:
    """Return the set of scaffoldIds pinned by the project-input fixtures.

    Each ``examples/<siteId>.project-input.json`` declares the scaffold
    it pins to; collecting these tells us which scaffolds a given suite
    actually exercises.
    """

    repo_root = Path(__file__).resolve().parent.parent
    examples_dir = repo_root / "examples"
    covered: set[str] = set()
    for case_id in case_ids:
        fixture = examples_dir / f"{case_id}.project-input.json"
        if not fixture.is_file():
            continue
        data = json.loads(fixture.read_text(encoding="utf-8"))
        scaffold_id = data.get("scaffoldId")
        if isinstance(scaffold_id, str) and scaffold_id:
            covered.add(scaffold_id)
    return covered


def test_full_cases_covers_every_on_disk_scaffold() -> None:
    """FULL_CASES must pin at least one fixture per on-disk scaffold.

    The contract is enforced dynamically against the filesystem: when a
    new scaffold (e.g. professional-services from Issue #91) lands as a
    real directory under ``packages/generation/orchestration/scaffolds/``,
    this test fails until someone adds a fixture for it to FULL_CASES.
    Without that net the full suite would silently fall back to "only
    the older scaffolds get a real npm build" and the next
    restaurant-hospitality-style regression could ship undetected.
    """

    from scripts.run_eval_suite import FULL_CASES

    on_disk = _discover_on_disk_scaffold_ids()
    covered = _scaffolds_covered_by(FULL_CASES)
    missing = on_disk - covered
    assert not missing, (
        f"FULL_CASES misses on-disk scaffolds: {sorted(missing)}. "
        f"Add a fixture to examples/<siteId>.project-input.json pinned to "
        f"each missing scaffoldId and list its siteId in FULL_CASES. "
        f"Current FULL_CASES={FULL_CASES} cover scaffolds={sorted(covered)}; "
        f"on-disk scaffolds={sorted(on_disk)}."
    )


def test_quick_cases_covers_every_on_disk_scaffold() -> None:
    """QUICK_CASES must also pin at least one fixture per on-disk scaffold.

    Same dynamic contract as FULL_CASES — quick is the cheap smoke layer
    that runs daily, so it has to track on-disk reality too. Dropping
    cafe-bistro (today the sole restaurant-hospitality fixture in
    either suite) would regress smoke coverage of the menu+booking
    renderers added in PR #93.
    """

    from scripts.run_eval_suite import QUICK_CASES

    on_disk = _discover_on_disk_scaffold_ids()
    covered = _scaffolds_covered_by(QUICK_CASES)
    missing = on_disk - covered
    assert not missing, (
        f"QUICK_CASES misses on-disk scaffolds: {sorted(missing)}. "
        f"Add a fixture to examples/<siteId>.project-input.json pinned to "
        f"each missing scaffoldId and list its siteId in QUICK_CASES. "
        f"Current QUICK_CASES={QUICK_CASES} cover scaffolds={sorted(covered)}; "
        f"on-disk scaffolds={sorted(on_disk)}."
    )


def test_utc_now_iso_single_clock_read() -> None:
    """utc_now_iso reads the clock once to avoid a torn timestamp.

    Bugbot LOW finding on PR #87: previously the function called
    ``datetime.now`` twice — once for the strftime prefix and once
    for the millisecond suffix — which could produce a timestamp where
    the seconds and milliseconds came from different instants if the
    second boundary was crossed between the two reads. We assert the
    format here; the single-read property is enforced by the
    implementation containing exactly one ``datetime.now`` call.
    """

    import re as _re

    from scripts.run_eval_suite import utc_now_iso

    stamp = utc_now_iso()
    assert _re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", stamp)
