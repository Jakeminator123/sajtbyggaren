"""Tests for Sprint 3B mechanical fixes + sandwich loop.

Locks the public contract of:

- ``packages/generation/repair/fixes/ensure_default_export.py``
- ``packages/generation/repair/repair.py:run_repair_pipeline``
  (with the Sprint 3B sandwich-loop signature)
- ``packages/generation/repair/orchestration.py:execute_phase3_quality_and_repair``
- The parity contract between ``MECHANICAL_FIXES`` and
  ``governance/policies/fix-registry.v1.json:mechanicalFixes``.

All filesystem mutations stay under ``tmp_path`` so the canonical
``data/runs/`` and ``.generated/`` directories are never touched
(per AGENTS.md Gotchas).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.quality_gate import (
    CheckResult,
    QualityResult,
    run_quality_gate,
)
from packages.generation.quality_gate.gate import _aggregate_status
from packages.generation.repair import (
    MECHANICAL_FIXES,
    RepairResult,
    execute_phase3_quality_and_repair,
    run_repair_pipeline,
)
from packages.generation.repair.fixes.ensure_default_export import (
    ENSURE_DEFAULT_EXPORT_SPEC,
    apply_ensure_default_export,
)
from packages.generation.repair.repair import _MAX_TOTAL_SANDWICH_PASSES

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX_REGISTRY = REPO_ROOT / "governance" / "policies" / "fix-registry.v1.json"


def _write_page(target: Path, route: str, body: str) -> Path:
    """Helper: write ``body`` as the page.tsx for ``route`` and return
    the absolute path so tests can read it back after a fix."""
    if route == "/":
        path = target / "app" / "page.tsx"
    else:
        path = target / "app" / route.lstrip("/") / "page.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _route_scan_finding(route: str, relpath: str, kind: str) -> str:
    """Build a finding string in the EXACT format that
    quality_gate/checks.py:run_route_scan_check emits.

    ``kind`` must be ``"saknas"`` (file missing) or
    ``"saknar export default"`` (file exists, no default export).
    """
    return f"{route} -> {relpath} ({kind})"


def _make_quality_with_route_findings(findings: list[str]) -> QualityResult:
    """Build a QualityResult that mirrors what
    ``run_quality_gate`` would emit when route-scan found problems but
    other checks were ok / skipped. Status is computed by the real
    aggregator so fixtures stay self-consistent.
    """
    checks = [
        CheckResult(name="typecheck", status="skipped"),
        CheckResult(
            name="route-scan",
            status="failed",
            detail=f"{len(findings)} routes saknar default export",
            findings=findings,
        ),
        CheckResult(name="build-status", status="skipped"),
        CheckResult(name="policy-compliance", status="ok"),
    ]
    status = _aggregate_status(checks)
    return QualityResult(status=status, checks=checks)


# ---------------------------------------------------------------------------
# ensure_default_export (unit-level)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_ensure_default_export_appends_for_top_level_function(tmp_path):
    """Page with ``function Page(...)`` but no default export gets
    ``export default Page;`` appended."""
    page = _write_page(
        tmp_path,
        "/tjanster",
        "function Page() { return <div>tjanster</div>; }\n",
    )
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/tjanster", "app/tjanster/page.tsx", "saknar export default"
        )]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert len(fixes) == 1
    assert fixes[0].kind == "mechanical"
    assert fixes[0].name == "ensure-default-export"
    assert fixes[0].target == "app/tjanster/page.tsx"
    assert fixes[0].success is True
    after = page.read_text(encoding="utf-8")
    assert "export default Page;" in after
    assert "function Page()" in after


@pytest.mark.tooling
def test_ensure_default_export_appends_for_const_arrow(tmp_path):
    """``const Page = () => ...`` is also picked up as exportable."""
    page = _write_page(
        tmp_path,
        "/om-oss",
        "const Page = () => <h1>about</h1>;\n",
    )
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/om-oss", "app/om-oss/page.tsx", "saknar export default"
        )]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert fixes[0].success is True
    assert "export default Page;" in page.read_text(encoding="utf-8")


@pytest.mark.tooling
def test_ensure_default_export_prefers_page_symbol_over_others(tmp_path):
    """When the file declares both ``Page`` and other component-cased
    symbols, the fix MUST default-export ``Page`` because that is the
    Next.js App Router convention for the route entry of
    app/<route>/page.tsx.

    Sprint 3B v1.0 picked the first match, which would have exported
    ``Header`` here - that makes route-scan green but renders the
    wrong component. Sprint 3B v1.1 (ADR 0016) prefers ``Page``.
    """
    page = _write_page(
        tmp_path,
        "/",
        (
            "function Header() { return <header />; }\n"
            "function Page() { return <main><Header/></main>; }\n"
        ),
    )
    quality = _make_quality_with_route_findings(
        [_route_scan_finding("/", "app/page.tsx", "saknar export default")]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert fixes[0].success is True
    text = page.read_text(encoding="utf-8")
    assert "export default Page;" in text
    assert "export default Header;" not in text


@pytest.mark.tooling
def test_ensure_default_export_uses_only_candidate_when_no_page(tmp_path):
    """If the file declares exactly ONE component-cased symbol and it
    is not named ``Page``, default-export that single candidate. Common
    for files that name the component after the route, e.g. ``Hero``,
    ``About``."""
    page = _write_page(
        tmp_path,
        "/hero",
        "function Hero() { return <div>hero</div>; }\n",
    )
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/hero", "app/hero/page.tsx", "saknar export default"
        )]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert fixes[0].success is True
    assert "export default Hero;" in page.read_text(encoding="utf-8")


@pytest.mark.tooling
def test_ensure_default_export_skips_when_no_page_and_multiple_candidates(
    tmp_path,
):
    """File declares Header + Footer (no Page) - the fix MUST refuse
    rather than guess wrong. Sprint 3B v1.0 would have exported
    Header (first match); v1.1 returns success=False and leaves the
    file untouched so the operator (or a Sprint 5+ LLM-fix) can pick.
    """
    body = (
        "function Header() { return <header />; }\n"
        "function Footer() { return <footer />; }\n"
    )
    page = _write_page(tmp_path, "/", body)
    quality = _make_quality_with_route_findings(
        [_route_scan_finding("/", "app/page.tsx", "saknar export default")]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert len(fixes) == 1
    assert fixes[0].success is False
    assert "no exportable" in fixes[0].detail.lower()
    assert page.read_text(encoding="utf-8") == body


@pytest.mark.tooling
def test_ensure_default_export_skips_lowercase_helpers(tmp_path):
    """A file that only declares lowercase helpers (utility functions)
    is NOT default-exported; the fix returns success=False and does
    not mutate the file."""
    body = (
        "const cn = (...x: string[]) => x.join(' ');\n"
        "function slugify(s: string) { return s.toLowerCase(); }\n"
    )
    page = _write_page(tmp_path, "/utils-only", body)
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/utils-only",
            "app/utils-only/page.tsx",
            "saknar export default",
        )]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert len(fixes) == 1
    assert fixes[0].success is False
    assert "no exportable" in fixes[0].detail.lower()
    assert page.read_text(encoding="utf-8") == body


@pytest.mark.tooling
def test_ensure_default_export_only_acts_on_no_export_findings(tmp_path):
    """Findings tagged ``(saknas)`` (missing file) must be ignored. The
    fix never invents structure; route-recovery is an LLM-fix in the
    registry (Sprint 5+)."""
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/missing", "app/missing/page.tsx", "saknas"
        )]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert fixes == []


@pytest.mark.tooling
def test_ensure_default_export_idempotent_on_existing_default(tmp_path):
    """File that already has ``export default`` is not mutated again
    (idempotency safety net even though route-scan would not flag such
    a file)."""
    body = (
        "function Page() { return <div>x</div>; }\n"
        "export default Page;\n"
    )
    page = _write_page(tmp_path, "/", body)
    quality = _make_quality_with_route_findings(
        [_route_scan_finding("/", "app/page.tsx", "saknar export default")]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert len(fixes) == 1
    assert fixes[0].success is True
    assert "idempotency" in fixes[0].detail.lower()
    assert page.read_text(encoding="utf-8") == body


@pytest.mark.tooling
def test_ensure_default_export_handles_unreadable_file(tmp_path):
    """If a finding points at a file that does not exist, the fix
    surfaces a structured failure instead of crashing the pipeline."""
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/ghost", "app/ghost/page.tsx", "saknar export default"
        )]
    )

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert len(fixes) == 1
    assert fixes[0].success is False
    assert (
        "could not read file" in fixes[0].detail.lower()
        or "no such file" in fixes[0].detail.lower()
    )


@pytest.mark.tooling
def test_ensure_default_export_dedupes_repeated_paths(tmp_path):
    """A finding listed twice (defensive against future check changes)
    must only mutate the file once."""
    page = _write_page(
        tmp_path,
        "/",
        "function Page() { return <div>x</div>; }\n",
    )
    finding = _route_scan_finding(
        "/", "app/page.tsx", "saknar export default"
    )
    quality = _make_quality_with_route_findings([finding, finding])

    fixes = apply_ensure_default_export(tmp_path, quality)

    assert len(fixes) == 1
    text = page.read_text(encoding="utf-8")
    assert text.count("export default Page;") == 1


# ---------------------------------------------------------------------------
# run_repair_pipeline sandwich loop
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_repair_pipeline_applies_fix_on_route_scan_no_export(tmp_path):
    """Integration: route-scan flags missing default export; repair
    pipeline applies the fix and re-runs the gate; status flips to
    ``fixed``."""
    page = _write_page(
        tmp_path,
        "/tjanster",
        "function Page() { return <div>tjanster</div>; }\n",
    )

    initial_quality = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/tjanster"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    assert initial_quality.status == "degraded"

    result = run_repair_pipeline(
        initial_quality,
        target_dir=tmp_path,
        required_routes=["/tjanster"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )

    assert isinstance(result, RepairResult)
    assert result.status == "fixed"
    assert result.iterations == 1
    assert result.qualityStatusBefore == "degraded"
    assert result.qualityStatusAfter == "ok"
    assert len(result.mechanicalFixesApplied) == 1
    fix = result.mechanicalFixesApplied[0]
    assert fix.name == "ensure-default-export"
    assert fix.success is True
    assert "export default Page;" in page.read_text(encoding="utf-8")
    assert result.remainingErrors == []


@pytest.mark.tooling
def test_repair_pipeline_partial_fix_when_some_findings_remain(tmp_path):
    """Two routes with no default export, but one is unfixable
    (lowercase helpers only). Pipeline reports ``partial-fix``: the
    fixable one is repaired, the other remains in remainingErrors.
    """
    _write_page(
        tmp_path,
        "/tjanster",
        "function Page() { return <div>x</div>; }\n",
    )
    _write_page(
        tmp_path,
        "/utils",
        "const cn = (...args: string[]) => args.join(' ');\n",
    )

    initial_quality = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/tjanster", "/utils"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    assert initial_quality.status == "degraded"

    result = run_repair_pipeline(
        initial_quality,
        target_dir=tmp_path,
        required_routes=["/tjanster", "/utils"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )

    assert result.status == "partial-fix"
    assert result.iterations == 1
    assert result.qualityStatusBefore == "degraded"
    assert result.qualityStatusAfter == "degraded"
    successes = [f for f in result.mechanicalFixesApplied if f.success]
    failures = [f for f in result.mechanicalFixesApplied if not f.success]
    assert len(successes) == 1
    assert successes[0].target == "app/tjanster/page.tsx"
    assert len(failures) == 1
    assert failures[0].target == "app/utils/page.tsx"
    assert any("/utils" in err for err in result.remainingErrors)


@pytest.mark.tooling
def test_repair_pipeline_iterations_zero_when_no_fixes_match(tmp_path):
    """A failure type the registry does not cover (typecheck) leaves
    iterations=0 because the fix dispatcher emits an empty list and
    the loop breaks before incrementing."""
    quality = QualityResult(
        status="failed",
        checks=[
            CheckResult(
                name="typecheck",
                status="failed",
                findings=["app/page.tsx(1,1): error TS2304"],
            ),
            CheckResult(name="route-scan", status="ok"),
            CheckResult(name="build-status", status="ok"),
            CheckResult(name="policy-compliance", status="ok"),
        ],
    )

    result = run_repair_pipeline(
        quality,
        target_dir=tmp_path,
        required_routes=[],
        npm_steps=[],
        build_status="ok",
        do_typecheck=False,
    )

    assert result.status == "no-fix-applied"
    assert result.iterations == 0
    assert result.mechanicalFixesApplied == []
    assert "Sprint 3B v1" in result.reason


@pytest.mark.tooling
def test_repair_pipeline_aborts_on_no_progress(tmp_path, monkeypatch):
    """Sandwich-loop progress guard: if the post-rerun gate has the
    same number of failed findings as before this pass, the loop must
    stop instead of re-attempting the same failed targets pass after
    pass.

    Sprint 3B v1 prefers this guard over the raw
    ``maxTotalSandwichPasses`` cap because we only ship one mechanical
    fix today; with no fix cascades a second pass over identical
    findings is by definition wasted work. The cap remains in code +
    locked by ``test_max_total_sandwich_passes_matches_registry_loop_limit``
    as an upper bound for Sprint 3B-next when fix cascades become
    possible.
    """
    pass_counter = {"i": 0}

    def fake_dispatch(target, quality_result):
        pass_counter["i"] += 1
        from packages.generation.repair.models import RepairFix

        return [
            RepairFix(
                kind="mechanical",
                name="ensure-default-export",
                target="app/synthetic/page.tsx",
                detail=f"synthetic pass {pass_counter['i']}",
                success=True,
            )
        ]

    def fake_rerun(**kwargs):
        # Same finding count after every rerun -> progress guard
        # should fire after the first sandwich pass.
        return QualityResult(
            status="degraded",
            checks=[
                CheckResult(
                    name="route-scan",
                    status="failed",
                    findings=["/x -> app/x/page.tsx (saknar export default)"],
                ),
                CheckResult(name="typecheck", status="skipped"),
                CheckResult(name="build-status", status="skipped"),
                CheckResult(name="policy-compliance", status="ok"),
            ],
        )

    import packages.generation.repair.repair as repair_module

    monkeypatch.setattr(repair_module, "_dispatch_mechanical_fixes", fake_dispatch)
    monkeypatch.setattr(repair_module, "run_quality_gate", fake_rerun)

    initial = fake_rerun()

    result = run_repair_pipeline(
        initial,
        target_dir=tmp_path,
        required_routes=["/x"],
        npm_steps=[],
        build_status="ok",
        do_typecheck=False,
    )

    # Pass 1 dispatches and applies; rerun returns the same finding
    # count -> progress guard fires before pass 2 dispatch. Loop never
    # reaches the cap.
    assert result.iterations == 1
    assert result.iterations <= _MAX_TOTAL_SANDWICH_PASSES
    assert result.status == "partial-fix"
    assert pass_counter["i"] == 1


@pytest.mark.tooling
def test_repair_pipeline_skips_rerun_when_no_route_params(tmp_path):
    """The Sprint 3A signature ``run_repair_pipeline(quality, *,
    target_dir, do_repair=True)`` (no rerun params) must keep working.
    The fix is still applied; the gate is just not re-run.
    """
    _write_page(
        tmp_path,
        "/tjanster",
        "function Page() { return <div>x</div>; }\n",
    )
    quality = _make_quality_with_route_findings(
        [_route_scan_finding(
            "/tjanster", "app/tjanster/page.tsx", "saknar export default"
        )]
    )

    result = run_repair_pipeline(quality, target_dir=tmp_path)

    assert result.status == "partial-fix"  # no rerun -> can't claim "fixed"
    assert result.iterations == 1
    assert result.qualityStatusBefore == "degraded"
    # ``qualityStatusAfter`` mirrors the before-status because we
    # could not independently confirm an improvement.
    assert result.qualityStatusAfter == "degraded"
    assert any(f.success for f in result.mechanicalFixesApplied)


# ---------------------------------------------------------------------------
# orchestration helper + scripts/ wiring
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_execute_phase3_orchestration_returns_post_repair_quality(tmp_path):
    """``execute_phase3_quality_and_repair`` must surface the
    POST-repair QualityResult so quality-result.json reflects the
    final state (after the sandwich loop)."""
    _write_page(
        tmp_path,
        "/tjanster",
        "function Page() { return <div>x</div>; }\n",
    )

    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=tmp_path,
        required_routes=["/tjanster"],
        npm_steps=[],
        build_status="ok",
        do_typecheck=False,
    )

    assert final_quality.status == "ok"
    assert repair_result.status == "fixed"
    assert repair_result.iterations == 1


@pytest.mark.tooling
def test_execute_phase3_orchestration_reruns_when_findings_reduced_but_status_same(
    tmp_path,
):
    """Sprint 3B v1.1 regression for Bug B: when a sandwich pass fixes
    SOME findings but the aggregate status is unchanged (degraded ->
    degraded with fewer findings), the orchestration helper must
    still re-run Quality Gate so quality-result.json reflects the
    reduced findings list. Sprint 3B v1.0 short-circuited on status
    equality and returned the stale initial QualityResult.
    """
    _write_page(
        tmp_path,
        "/tjanster",
        "function Page() { return <div>x</div>; }\n",
    )
    _write_page(
        tmp_path,
        "/utils",
        "const cn = (...args: string[]) => args.join(' ');\n",
    )

    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=tmp_path,
        required_routes=["/tjanster", "/utils"],
        npm_steps=[],
        build_status="ok",
        do_typecheck=False,
    )

    assert repair_result.iterations == 1
    assert repair_result.status == "partial-fix"
    # Status stays degraded (utils is unfixable), but findings list
    # MUST shrink: pre-repair had 2 route-scan findings, post-repair
    # has 1 (only utils remains).
    assert final_quality.status == "degraded"
    route_scan = next(c for c in final_quality.checks if c.name == "route-scan")
    assert route_scan.status == "failed"
    assert len(route_scan.findings) == 1
    assert any("/utils" in f for f in route_scan.findings)
    assert not any("/tjanster" in f for f in route_scan.findings), (
        "Stale finding for /tjanster still present in final quality "
        "result - orchestration helper short-circuited on status "
        "equality (Sprint 3B v1.0 Bug B regressed)."
    )


@pytest.mark.tooling
def test_execute_phase3_orchestration_skipped_when_build_skipped(tmp_path):
    """``--skip-build`` (build_status="skipped") must NOT trigger
    repair; the helper mirrors Sprint 3A behaviour for skip-build
    runs even when the gate would otherwise have findings.

    The fixture deliberately uses a page that already has
    ``export default`` so route-scan does not produce findings,
    isolating the "skip repair when build skipped" semantics.
    """
    _write_page(
        tmp_path,
        "/",
        "export default function Page() { return <div>x</div>; }\n",
    )

    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )

    assert repair_result.iterations == 0
    assert repair_result.mechanicalFixesApplied == []
    # All checks ok or skipped -> aggregate ok
    assert final_quality.status == "ok"


@pytest.mark.tooling
def test_execute_phase3_orchestration_skipped_with_findings_means_no_repair(
    tmp_path,
):
    """When ``build_status="skipped"`` AND the gate has findings, the
    helper still runs the gate (so quality-result.json is honest about
    the findings) but does NOT attempt repair (do_repair=False
    semantics from Sprint 3A skip-build path)."""
    _write_page(
        tmp_path,
        "/",
        "function Page() { return <div>x</div>; }\n",
    )

    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )

    assert final_quality.status == "degraded"
    assert repair_result.iterations == 0
    assert repair_result.mechanicalFixesApplied == []
    assert repair_result.status == "no-fix-applied"
    assert "do_repair=False" in repair_result.reason or "skipped" in repair_result.reason.lower()


# ---------------------------------------------------------------------------
# parity with governance/policies/fix-registry.v1.json
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_mechanical_fixes_dispatch_table_is_subset_of_registry():
    """Every ``MECHANICAL_FIXES`` entry must correspond to an entry in
    ``governance/policies/fix-registry.v1.json:mechanicalFixes`` so a
    reviewer can audit "what fixes does the code actually run?"
    against the policy.
    """
    registry = json.loads(FIX_REGISTRY.read_text(encoding="utf-8"))
    registry_ids = {entry["id"] for entry in registry["mechanicalFixes"]}
    code_ids = {spec.fix_id for spec in MECHANICAL_FIXES}
    assert code_ids.issubset(registry_ids), (
        f"Code dispatches fixes not in registry: {code_ids - registry_ids}. "
        f"Add them to fix-registry.v1.json or remove from MECHANICAL_FIXES."
    )


@pytest.mark.tooling
def test_ensure_default_export_spec_matches_registry_entry():
    """The SPEC constant must mirror the registry entry exactly so a
    drift in the policy is caught at test time."""
    registry = json.loads(FIX_REGISTRY.read_text(encoding="utf-8"))
    entry = next(
        e for e in registry["mechanicalFixes"]
        if e["id"] == "ensure-default-export"
    )
    assert ENSURE_DEFAULT_EXPORT_SPEC.fix_id == entry["id"]
    assert ENSURE_DEFAULT_EXPORT_SPEC.stage == entry["stage"]
    assert ENSURE_DEFAULT_EXPORT_SPEC.priority == entry["priority"]
    assert ENSURE_DEFAULT_EXPORT_SPEC.idempotent is entry["idempotent"]
    assert ENSURE_DEFAULT_EXPORT_SPEC.on_failure == entry["onFailure"]


@pytest.mark.tooling
def test_max_total_sandwich_passes_matches_registry_loop_limit():
    """The hardcoded loop cap must mirror
    ``fix-registry.v1.json:loopLimits.maxTotalSandwichPasses``."""
    registry = json.loads(FIX_REGISTRY.read_text(encoding="utf-8"))
    assert (
        _MAX_TOTAL_SANDWICH_PASSES
        == registry["loopLimits"]["maxTotalSandwichPasses"]
    ), (
        "_MAX_TOTAL_SANDWICH_PASSES drifted from fix-registry.v1.json. "
        "Either bump the policy or the constant; the two must match."
    )


# ---------------------------------------------------------------------------
# build-result + scripts/ integration
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_build_site_emits_repair_telemetry_for_skipped_builds(tmp_path, monkeypatch):
    """End-to-end: running scripts/build_site.py:build with
    --skip-build (do_build=False) must produce a repair-result.json
    that includes the Sprint 3B telemetry fields (qualityStatusBefore,
    qualityStatusAfter, iterations)."""
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input, do_build=False, runs_dir=tmp_path)

    repair_result = json.loads(
        (run_dir / "repair-result.json").read_text(encoding="utf-8")
    )

    assert "qualityStatusBefore" in repair_result
    assert "qualityStatusAfter" in repair_result
    assert "iterations" in repair_result
    assert repair_result["llmFixesApplied"] == []


@pytest.mark.tooling
def test_dev_generate_repair_payload_remains_compatible(tmp_path, monkeypatch):
    """``scripts/dev_generate.py`` mock pipeline still uses the Sprint
    3A signature ``run_repair_pipeline(quality, *, target_dir,
    do_repair=False)`` and must keep producing a valid
    repair-result.json that round-trips through Pydantic.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "scripts.dev_generate.DATA_RUNS_DIR", tmp_path
    )

    import sys

    saved_argv = sys.argv
    try:
        sys.argv = [
            "dev_generate.py",
            "Skapa hemsida för en elektriker i Malmö",
            "--phase",
            "build",
            "--data-runs-dir",
            str(tmp_path),
            "--run-id",
            "test-3b-compat",
        ]
        # Pre-create the inputs that --phase build expects.
        from scripts.dev_generate import (
            run_phase_build,
            run_phase_plan,
            run_phase_understand,
        )

        run_dir = tmp_path / "test-3b-compat"
        run_dir.mkdir(parents=True, exist_ok=True)
        site_brief = run_phase_understand(
            "Skapa hemsida för en elektriker i Malmö",
            run_dir,
            "test-3b-compat",
        )
        gen_pkg = run_phase_plan(run_dir, "test-3b-compat", site_brief)
        run_phase_build(run_dir, "test-3b-compat", gen_pkg)
    finally:
        sys.argv = saved_argv

    repair_payload = json.loads(
        (run_dir / "repair-result.json").read_text(encoding="utf-8")
    )

    assert repair_payload["status"] in (
        "not-needed",
        "no-fix-applied",
        "fixed",
        "partial-fix",
    )
    # do_repair=False path -> iterations stays at 0.
    assert repair_payload["iterations"] == 0
    assert "qualityStatusBefore" in repair_payload
    assert "qualityStatusAfter" in repair_payload
