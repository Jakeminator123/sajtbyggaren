"""Source-code regression guards for scripts/build_site.py.

Sprint 3A added codegenModel v1, Quality Gate and Repair Pipeline as
separate packages under ``packages/generation/``. The discipline is that
``scripts/build_site.py`` only carries thin wiring; product/check/repair
logic lives in the packages.

These tests fail loudly if a future commit:

- Reintroduces the Sprint 2B-era skeleton writers
  (``write_repair_result_skeleton`` / ``write_quality_result_skeleton``).
- Implements Quality Gate or Repair Pipeline logic inline in scripts/.
- Drops the imports that prove the wiring goes through the canonical
  packages.
- Replaces the canonical ``produce_site_plan`` plan source.

Locks ADR 0015's discipline contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SITE = REPO_ROOT / "scripts" / "build_site.py"


@pytest.mark.tooling
def test_build_site_does_not_reintroduce_skeleton_writers():
    """The Sprint 2B-era skeleton functions are gone; reintroducing them
    would mean the pipeline produces ``status=not-run`` artefacts again.
    Sprint 3A explicitly closed that path (ADR 0015).
    """
    source = BUILD_SITE.read_text(encoding="utf-8")
    assert re.search(r"def\s+write_repair_result_skeleton\s*\(", source) is None, (
        "write_repair_result_skeleton was removed in Sprint 3A. "
        "Reintroducing it means the pipeline writes status=not-run "
        "artefacts again, which masks real Quality Gate failures. "
        "Use packages.generation.repair.run_repair_pipeline instead."
    )
    assert re.search(r"def\s+write_quality_result_skeleton\s*\(", source) is None, (
        "write_quality_result_skeleton was removed in Sprint 3A. "
        "Use packages.generation.quality_gate.run_quality_gate instead."
    )


@pytest.mark.tooling
def test_build_site_imports_sprint_3a_packages():
    """The thin wiring depends on the Sprint 3A+ packages.

    Sprint 3A required direct imports of all three packages
    (codegen, quality_gate, repair). Sprint 3B (ADR 0016) routes
    Quality Gate through ``packages.generation.repair`` because the
    fix-registry policy mandates that the sandwich pattern (mechanical
    -> validate -> mechanical -> ...) lives in EXACTLY ONE place. As a
    result ``packages.generation.quality_gate`` is now an indirect
    dependency for scripts/, called via
    ``execute_phase3_quality_and_repair`` in
    ``packages/generation/repair/orchestration.py``.

    This test enforces:
    - Direct imports of codegen + repair must remain in scripts/.
    - The repair package must import quality_gate (so the indirection
      cannot silently drop the gate).
    """
    source = BUILD_SITE.read_text(encoding="utf-8")
    for module in (
        "packages.generation.codegen",
        "packages.generation.repair",
    ):
        assert module in source, (
            f"scripts/build_site.py must import {module}. "
            f"Sprint 3A+ wiring is incomplete without it "
            f"(ADR 0015 + 0016)."
        )

    repair_orch = (
        REPO_ROOT
        / "packages"
        / "generation"
        / "repair"
        / "orchestration.py"
    )
    repair_orch_source = repair_orch.read_text(encoding="utf-8")
    assert "from packages.generation.quality_gate" in repair_orch_source, (
        "packages/generation/repair/orchestration.py must import "
        "quality_gate so the Sprint 3B sandwich loop can re-run the "
        "gate after applying a mechanical fix (ADR 0016 + "
        "fix-registry.v1.json:loopLimits)."
    )


@pytest.mark.tooling
def test_build_site_does_not_implement_quality_gate_inline():
    """All four Quality Gate check names are implemented in
    packages/generation/quality_gate/checks.py. A function definition
    inside scripts/build_site.py with one of these names would mean
    quality logic has drifted back into scripts/, breaking ADR 0015 +
    repo-boundaries.
    """
    source = BUILD_SITE.read_text(encoding="utf-8")
    for inline_name in (
        "def run_typecheck_check",
        "def run_route_scan_check",
        "def run_build_status_check",
        "def run_policy_compliance_check",
    ):
        assert inline_name not in source, (
            f"{inline_name!r} found in scripts/build_site.py. "
            f"Quality Gate checks must live in "
            f"packages/generation/quality_gate/checks.py per "
            f"repo-boundaries.v1.json."
        )


@pytest.mark.tooling
def test_build_site_does_not_implement_repair_inline():
    """Repair Pipeline lives in packages/generation/repair/. If a fix
    function lands in scripts/build_site.py it would duplicate the
    pipeline that ADR 0015 just centralised.
    """
    source = BUILD_SITE.read_text(encoding="utf-8")
    forbidden = ["def run_repair_pipeline", "def apply_mechanical_fix"]
    for name in forbidden:
        assert name not in source, (
            f"{name!r} must not be defined in scripts/build_site.py. "
            f"Repair logic belongs in packages/generation/repair/."
        )


@pytest.mark.tooling
def test_build_site_snapshot_runs_after_phase3_quality_and_repair():
    """Sprint 3B v1.1 regression for Bug A: ``snapshot_generated_files``
    must be called AFTER ``run_phase3_quality_and_repair`` in the
    builder so the canonical ``data/runs/<runId>/generated-files/``
    snapshot reflects any mechanical fixes the Repair Pipeline applied
    to ``target/``. Sprint 3B v1.0 had snapshot first which made the
    snapshot stale whenever a fix succeeded.

    Source-level lock: read ``build()`` and assert the
    ``snapshot_generated_files(`` call site appears AFTER the
    ``run_phase3_quality_and_repair(`` call site.
    """
    import inspect

    from scripts import build_site

    body = inspect.getsource(build_site.build)
    snapshot_idx = body.find("snapshot_generated_files(")
    repair_idx = body.find("run_phase3_quality_and_repair(")
    assert snapshot_idx > 0 and repair_idx > 0, (
        "Both snapshot_generated_files() and "
        "run_phase3_quality_and_repair() must be called from build()."
    )
    assert snapshot_idx > repair_idx, (
        "snapshot_generated_files() must run AFTER "
        "run_phase3_quality_and_repair() so the canonical "
        "data/runs/<runId>/generated-files/ snapshot captures any "
        "mechanical fixes the Repair Pipeline applied to target/. "
        "Sprint 3B v1.0 had this order reversed (Bug A)."
    )


@pytest.mark.tooling
def test_build_site_phase3_orchestration_is_thin():
    """The phase 3 wiring helper ``run_phase3_quality_and_repair`` exists
    and stays under ~50 lines. If it grows past that, Quality Gate or
    Repair logic is being duplicated in scripts/ instead of being
    delegated.
    """
    source = BUILD_SITE.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+run_phase3_quality_and_repair\s*\([\s\S]*?(?=\ndef\s|\Z)",
        source,
    )
    assert match is not None, (
        "run_phase3_quality_and_repair was removed or renamed. "
        "Sprint 3A relies on this thin wiring helper; if you renamed "
        "it, update this test to match the new symbol."
    )
    body = match.group(0)
    line_count = body.count("\n")
    assert line_count < 60, (
        f"run_phase3_quality_and_repair is {line_count} lines - "
        f"that smells like Quality Gate or Repair logic has crept "
        f"back into scripts/build_site.py. Move it to "
        f"packages/generation/quality_gate/ or "
        f"packages/generation/repair/ instead."
    )


@pytest.mark.tooling
def test_produce_site_plan_remains_canonical_plan_source():
    """B19 closure plus Sprint 3A relies on produce_site_plan being the
    SINGLE plan-construction entrypoint. Sprint 3A did not introduce a
    second plan path; this guard fails loudly if one appears.

    Complements the existing tests/test_planning.py:test_b19_* checks
    by re-running the assertion in the Sprint 3A test file so a future
    Sprint-3-specific refactor sees this guard alongside the new code.
    """
    source = BUILD_SITE.read_text(encoding="utf-8")
    assert "produce_site_plan" in source, (
        "scripts/build_site.py must continue to call into "
        "packages.generation.planning.produce_site_plan. Sprint 3A "
        "did not add a second plan source."
    )
    assert "build_site_plan_mock" not in source, (
        "Legacy build_site_plan_mock helper reappeared in scripts/build_site.py. "
        "Plan construction must go through produce_site_plan (B19, ADR 0014)."
    )


@pytest.mark.tooling
def test_build_result_includes_codegen_summary(tmp_path, monkeypatch):
    """ADR 0015 reserves a ``codegen`` slot in build-result.json for the
    codegenModel manifest metadata. ADR 0017 (Sprint 3B-next) extends
    the slot with ``riskNotes`` and ``usage`` so token-tracking and
    LLM-emitted risk notes can surface to Backoffice without opening
    trace.ndjson.

    With OPENAI_API_KEY removed and starter=marketing-base, the new
    expected source is ``mock-no-key`` (was ``deterministic-v1`` before
    Sprint 3B-next; deterministic-v1 is now reserved for starters that
    are explicitly out of real-codegen scope).
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input, do_build=False, runs_dir=tmp_path)

    import json

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    assert "codegen" in build_result, (
        "build-result.json must include a 'codegen' field per ADR 0015. "
        "The codegenModel manifest source/modelUsed/fileCount/rationale "
        "(plus riskNotes/usage from ADR 0017) must be surfaced here so "
        "Backoffice can show codegen status without opening trace.ndjson."
    )
    codegen = build_result["codegen"]
    # marketing-base + no-key -> mock-no-key per ADR 0017.
    assert codegen["source"] == "mock-no-key"
    assert codegen["modelUsed"] == "mock"
    assert codegen["fileCount"] >= 1
    assert "marketing-base" in codegen["rationale"]
    # Sprint 3B-next contract: riskNotes + usage always present.
    assert "riskNotes" in codegen
    assert codegen["riskNotes"] == []  # mock-no-key never emits risk notes
    assert "usage" in codegen
    assert codegen["usage"]["totalTokens"] == 0  # no LLM call -> zero usage


@pytest.mark.tooling
def test_degraded_quality_propagates_to_build_status():
    """ADR 0015 says Quality Gate ``degraded`` status flips
    overall_status to ``degraded`` so build-result.json is honest about
    soft-failure runs (route-scan or policy-compliance failed but
    typecheck/build are ok). Exit code stays 0.

    Source-level lock: the propagation logic must be present in
    scripts/build_site.py:build(). If a future refactor drops it,
    degraded runs would silently report status=ok which would mislead
    operators looking at build-result.json.
    """
    import inspect

    from scripts import build_site

    source = inspect.getsource(build_site.build)
    assert (
        'quality_payload["status"] == "degraded"' in source
        and 'overall_status = "degraded"' in source
    ), (
        "build() must propagate Quality Gate 'degraded' to overall_status "
        "(ADR 0015). Otherwise a route-scan or policy-compliance soft "
        "failure would report status=ok in build-result.json."
    )


@pytest.mark.tooling
def test_quality_result_payload_has_real_checks_not_skeleton():
    """Black-box read of the wiring: the runtime payload that ends up in
    quality-result.json must contain a ``checks`` list with the four
    Sprint 3A check names, not the legacy ``status=not-run`` shape.
    """
    from packages.generation.quality_gate import run_quality_gate

    result = run_quality_gate(
        target_dir=Path("/this/path/does/not/exist"),
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    payload = result.model_dump()
    assert "status" in payload
    assert payload["status"] in ("ok", "degraded", "failed")
    assert "checks" in payload
    check_names = {c["name"] for c in payload["checks"]}
    assert check_names == {
        "typecheck",
        "route-scan",
        "build-status",
        "policy-compliance",
    }
    for check in payload["checks"]:
        assert check["status"] != "not-run", (
            "Sprint 3A removed the not-run skeleton status. If a check "
            "returns not-run, the skeleton has crept back somewhere."
        )
