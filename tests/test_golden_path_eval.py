"""Tests for scripts/run_golden_path_eval.py."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.tooling
def test_list_generated_routes_detects_nested_next_routes(tmp_path: Path) -> None:
    from scripts.run_golden_path_eval import list_generated_routes

    app = tmp_path / "run" / "generated-files" / "app"
    root_page = app / "page.tsx"
    root_page.parent.mkdir(parents=True, exist_ok=True)
    root_page.write_text("export default function Page() {}", encoding="utf-8")
    nested = app / "tjanster" / "akut" / "page.tsx"
    nested.parent.mkdir(parents=True)
    nested.write_text("export default function Page() {}", encoding="utf-8")

    assert list_generated_routes(tmp_path / "run") == ["/", "/tjanster/akut"]


@pytest.mark.tooling
def test_route_path_by_id_resolves_scaffold_specific_slugs() -> None:
    """Contact/products paths come from routePlan ids, not a hardcoded slug."""

    from scripts.run_golden_path_eval import route_path_by_id

    clinic_plan = {
        "routePlan": [
            {"id": "home", "path": "/"},
            {"id": "treatments", "path": "/behandlingar"},
            {"id": "about", "path": "/om-oss"},
            {"id": "contact", "path": "/kontakta-oss"},
        ]
    }
    commerce_plan = {
        "routePlan": [
            {"id": "home", "path": "/"},
            {"id": "products", "path": "/produkter"},
            {"id": "contact", "path": "/kontakt"},
        ]
    }

    assert route_path_by_id(clinic_plan, "contact") == "/kontakta-oss"
    assert route_path_by_id(clinic_plan, "products") is None
    assert route_path_by_id(commerce_plan, "contact") == "/kontakt"
    assert route_path_by_id(commerce_plan, "products") == "/produkter"
    assert route_path_by_id({}, "contact") is None


@pytest.mark.tooling
def test_assess_contact_cta_accepts_clinic_kontakta_oss_route() -> None:
    """clinic-healthcare's /kontakta-oss must count as a valid contact path."""

    from scripts.run_golden_path_eval import BASELINE_CASES, assess_contact_cta

    naprapat = next(c for c in BASELINE_CASES if c.case_id == "naprapat-stockholm")
    plan_routes = ["/", "/behandlingar", "/om-oss", "/kontakta-oss"]
    fs_routes = ["/", "/behandlingar", "/om-oss", "/kontakta-oss"]
    text = '<a href={"/kontakta-oss"} className="...">Kontakta oss</a>'

    result = assess_contact_cta(
        naprapat,
        plan_routes,
        fs_routes,
        text,
        {"placeholderContactFields": []},
        contact_path="/kontakta-oss",
        products_path="/produkter",
    )

    assert result["status"] == "pass"
    assert result["hasContactRoute"] is True
    assert result["hasContactHref"] is True
    assert result["contactPath"] == "/kontakta-oss"


@pytest.mark.tooling
def test_assess_contact_cta_default_kontakt_slug_misses_clinic_route() -> None:
    """Regression guard: the old hardcoded /kontakt slug would fail clinic."""

    from scripts.run_golden_path_eval import BASELINE_CASES, assess_contact_cta

    naprapat = next(c for c in BASELINE_CASES if c.case_id == "naprapat-stockholm")
    plan_routes = ["/", "/behandlingar", "/om-oss", "/kontakta-oss"]
    fs_routes = ["/", "/behandlingar", "/om-oss", "/kontakta-oss"]
    text = '<a href={"/kontakta-oss"}>Kontakta oss</a>'

    # Resolving against the default /kontakt slug reproduces the false negative
    # the routePlan-id fix removes.
    result = assess_contact_cta(
        naprapat,
        plan_routes,
        fs_routes,
        text,
        {"placeholderContactFields": []},
    )

    assert result["status"] == "fail"
    assert result["hasContactRoute"] is False
    assert result["hasContactHref"] is False


@pytest.mark.tooling
def test_assess_contact_cta_placeholder_fields_warn_not_false_pass() -> None:
    """Placeholder contact data must keep status at warn, never a clean pass.

    Guards against the route-aware fix accidentally turning the legitimate
    placeholderContactFields penalty into a false pass: route + href resolve
    correctly, so the only remaining signal is the dummy contact data.
    """

    from scripts.run_golden_path_eval import BASELINE_CASES, assess_contact_cta

    naprapat = next(c for c in BASELINE_CASES if c.case_id == "naprapat-stockholm")
    plan_routes = ["/", "/behandlingar", "/om-oss", "/kontakta-oss"]
    fs_routes = ["/", "/behandlingar", "/om-oss", "/kontakta-oss"]
    text = '<a href={"/kontakta-oss"}>Kontakta oss</a>'

    result = assess_contact_cta(
        naprapat,
        plan_routes,
        fs_routes,
        text,
        {"placeholderContactFields": ["phone", "email", "addressLines", "openingHours"]},
        contact_path="/kontakta-oss",
        products_path="/produkter",
    )

    assert result["hasContactRoute"] is True
    assert result["hasContactHref"] is True
    assert result["status"] == "warn"
    assert result["placeholderContactFields"] == [
        "phone",
        "email",
        "addressLines",
        "openingHours",
    ]


@pytest.mark.tooling
def test_golden_path_eval_writes_all_four_cases_without_llm_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default mode writes JSON/Markdown and does not use OPENAI_API_KEY."""

    from scripts.run_golden_path_eval import (
        BASELINE_CASES,
        OPENAI_API_KEY_ENV,
        TRAIT_DEFINITIONS,
        run_golden_path_eval,
    )

    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-not-used")

    summary = run_golden_path_eval(
        mode="deterministic",
        evals_dir=tmp_path,
        eval_id="golden-contract",
    )

    assert summary["caseCount"] == 4
    assert summary["deterministicOffline"] is True
    assert summary["llmKeyRequired"] is False
    assert summary["thresholds"] == {
        "averageScoreGo": 7.0,
        "minimumCaseScoreGo": 6.5,
    }
    assert {item["prompt"] for item in summary["baselinePrompts"]} == {
        case.prompt for case in BASELINE_CASES
    }
    assert Path(summary["jsonPath"]).is_file()
    assert Path(summary["markdownPath"]).is_file()
    assert (tmp_path / "golden-contract" / "runs").is_dir()
    assert (tmp_path / "golden-contract" / "generated").is_dir()
    assert (tmp_path / "golden-contract" / "prompt-inputs").is_dir()

    on_disk = json.loads((tmp_path / "golden-contract.json").read_text(encoding="utf-8"))
    assert on_disk["caseCount"] == 4
    assert len(on_disk["cases"]) == 4

    expected_traits = set(TRAIT_DEFINITIONS)
    for case in on_disk["cases"]:
        assert isinstance(case["totalScore"], int | float)
        assert 0 <= case["totalScore"] <= 10
        assert set(case["traitScores"]) == expected_traits
        assert case["passThreshold"] == 6.5
        assert case["briefSource"] == "mock-no-key"
        assert case["planSource"] in {"pinned", "mock-no-key"}
        assert case["routeSanity"]["plannedRoutes"]
        assert case["contactCtaSanity"]["status"] in {"pass", "warn", "fail"}
        assert "selectedScaffoldId" in case["signalPropagation"]
        assert "expectedStarterId" in case["signalPropagation"]

    assert os.environ[OPENAI_API_KEY_ENV] == "sk-test-not-used"
    assert summary["embeddingsReadiness"] in {"go", "no-go"}
    assert summary["nextGate"] == summary["embeddingsReadiness"]


@pytest.mark.tooling
def test_golden_path_eval_gate_is_no_go_below_thresholds() -> None:
    from scripts.run_golden_path_eval import compute_gate

    gate = compute_gate(
        [
            {"caseId": "a", "totalScore": 8.0},
            {"caseId": "b", "totalScore": 7.0},
            {"caseId": "c", "totalScore": 6.4},
            {"caseId": "d", "totalScore": 7.0},
        ]
    )

    assert gate["embeddingsReadiness"] == "no-go"
    assert gate["nextGate"] == "no-go"
    assert gate["averagePassThreshold"] == 7.0
    assert gate["casePassThreshold"] == 6.5
    assert gate["casesBelowThreshold"] == ["c"]
    assert any("cases below 6.5" in reason for reason in gate["reasons"])


@pytest.mark.tooling
def test_golden_path_eval_gate_is_no_go_on_low_average() -> None:
    from scripts.run_golden_path_eval import compute_gate

    gate = compute_gate(
        [
            {"caseId": "a", "totalScore": 6.6},
            {"caseId": "b", "totalScore": 6.8},
            {"caseId": "c", "totalScore": 6.9},
            {"caseId": "d", "totalScore": 6.7},
        ]
    )

    assert gate["embeddingsReadiness"] == "no-go"
    assert gate["casesBelowThreshold"] == []
    assert any("average score" in reason for reason in gate["reasons"])


@pytest.mark.tooling
def test_golden_path_eval_gate_is_go_when_all_thresholds_pass() -> None:
    from scripts.run_golden_path_eval import compute_gate

    gate = compute_gate(
        [
            {"caseId": "a", "totalScore": 7.0},
            {"caseId": "b", "totalScore": 7.2},
            {"caseId": "c", "totalScore": 6.5},
            {"caseId": "d", "totalScore": 7.3},
        ]
    )

    assert gate["embeddingsReadiness"] == "go"
    assert gate["nextGate"] == "go"
    assert gate["casesBelowThreshold"] == []


@pytest.mark.tooling
def test_prune_golden_path_evals_removes_old_work_dirs_and_summaries(
    tmp_path: Path,
) -> None:
    from scripts.run_golden_path_eval import prune_golden_path_evals

    for index, eval_id in enumerate(("old", "middle", "new")):
        work_dir = tmp_path / eval_id
        work_dir.mkdir()
        (work_dir / "case.json").write_text("{}", encoding="utf-8")
        (tmp_path / f"{eval_id}.json").write_text("{}", encoding="utf-8")
        (tmp_path / f"{eval_id}.md").write_text("# report\n", encoding="utf-8")
        mtime = 1_700_000_000 + index
        os.utime(work_dir, (mtime, mtime))

    removed = prune_golden_path_evals(tmp_path, max_evals=2)

    assert removed == ["old"]
    assert not (tmp_path / "old").exists()
    assert not (tmp_path / "old.json").exists()
    assert not (tmp_path / "old.md").exists()
    assert (tmp_path / "middle").is_dir()
    assert (tmp_path / "new").is_dir()


@pytest.mark.tooling
def test_prune_golden_path_evals_protects_current_eval(tmp_path: Path) -> None:
    from scripts.run_golden_path_eval import prune_golden_path_evals

    for eval_id in ("newest", "current"):
        (tmp_path / eval_id).mkdir()
        (tmp_path / f"{eval_id}.json").write_text("{}", encoding="utf-8")
        (tmp_path / f"{eval_id}.md").write_text("# report\n", encoding="utf-8")
    os.utime(tmp_path / "newest", (1_700_000_010, 1_700_000_010))
    os.utime(tmp_path / "current", (1_700_000_000, 1_700_000_000))

    removed = prune_golden_path_evals(
        tmp_path,
        max_evals=1,
        protected_eval_ids={"current"},
    )

    assert removed == ["newest"]
    assert (tmp_path / "current").is_dir()


@pytest.mark.tooling
def test_prune_golden_path_evals_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    from scripts.run_golden_path_eval import prune_golden_path_evals

    for index, eval_id in enumerate(("old", "new")):
        (tmp_path / eval_id).mkdir()
        (tmp_path / f"{eval_id}.json").write_text("{}", encoding="utf-8")
        (tmp_path / f"{eval_id}.md").write_text("# report\n", encoding="utf-8")
        os.utime(tmp_path / eval_id, (1_700_000_000 + index, 1_700_000_000 + index))

    removed = prune_golden_path_evals(tmp_path, max_evals=1, dry_run=True)

    assert removed == ["old"]
    assert (tmp_path / "old").is_dir()
    assert (tmp_path / "old.json").is_file()
    assert (tmp_path / "old.md").is_file()


@pytest.mark.tooling
def test_read_positive_int_setting_falls_back_to_env_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.run_golden_path_eval import (
        MAX_GOLDEN_PATH_EVALS_ENV,
        read_positive_int_setting,
    )

    monkeypatch.delenv(MAX_GOLDEN_PATH_EVALS_ENV, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OTHER=value\n"
        f"{MAX_GOLDEN_PATH_EVALS_ENV}=10\n",
        encoding="utf-8",
    )

    assert read_positive_int_setting(MAX_GOLDEN_PATH_EVALS_ENV, env_file=env_file) == 10
