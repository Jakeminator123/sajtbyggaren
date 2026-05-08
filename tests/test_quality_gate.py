"""Tests for packages/generation/quality_gate/ (Sprint 3A v1).

Locks the QualityResult contract and the four checks (typecheck,
route-scan, build-status, policy-compliance). Tests use ``tmp_path``
fixtures so they never touch the canonical ``data/runs/`` directory
(per AGENTS.md Gotchas).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.generation.quality_gate import (
    CheckResult,
    QualityResult,
    run_quality_gate,
)
from packages.generation.quality_gate.checks import (
    run_build_status_check,
    run_policy_compliance_check,
    run_route_scan_check,
    run_typecheck_check,
)
from packages.generation.quality_gate.gate import _aggregate_status


def _write_page(target: Path, route: str, default_export: bool = True) -> None:
    """Helper: write a fake page.tsx at the route's expected location."""
    if route == "/":
        path = target / "app" / "page.tsx"
    else:
        path = target / "app" / route.lstrip("/") / "page.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    if default_export:
        path.write_text(
            "export default function Page() { return <div>x</div>; }",
            encoding="utf-8",
        )
    else:
        path.write_text("// no export here", encoding="utf-8")


# ---------------------------------------------------------------------------
# route-scan
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_route_scan_passes_when_all_routes_have_default_export(tmp_path):
    """All required routes exist with `export default` -> status=ok."""
    routes = ["/", "/tjanster", "/om-oss", "/kontakt"]
    for r in routes:
        _write_page(tmp_path, r, default_export=True)
    result = run_route_scan_check(tmp_path, routes)
    assert result.status == "ok"
    assert result.findings == []
    assert "4 required routes" in result.detail


@pytest.mark.tooling
def test_route_scan_flags_missing_files(tmp_path):
    """When a required route file is missing, route-scan must list it in
    findings (not raise SystemExit like the builder's hard guard).
    """
    _write_page(tmp_path, "/")
    result = run_route_scan_check(tmp_path, ["/", "/missing"])
    assert result.status == "failed"
    assert any("/missing" in f for f in result.findings)


@pytest.mark.tooling
def test_route_scan_flags_pages_without_default_export(tmp_path):
    """A page.tsx without `export default` must be flagged as missing
    that export so Repair Pipeline can act on it later.
    """
    _write_page(tmp_path, "/", default_export=True)
    _write_page(tmp_path, "/no-export", default_export=False)
    result = run_route_scan_check(tmp_path, ["/", "/no-export"])
    assert result.status == "failed"
    assert any("export default" in f.lower() or "default export" in f for f in result.findings)


# ---------------------------------------------------------------------------
# build-status
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_build_status_check_passes_when_all_steps_ok():
    result = run_build_status_check(
        build_status="ok",
        npm_steps=[
            {"name": "npm install", "ok": True, "seconds": 10.0},
            {"name": "npm run build", "ok": True, "seconds": 5.0},
        ],
    )
    assert result.status == "ok"


@pytest.mark.tooling
def test_build_status_check_skipped_when_skip_build():
    """--skip-build path returns status=skipped (not failed)."""
    result = run_build_status_check(build_status="skipped", npm_steps=[])
    assert result.status == "skipped"


@pytest.mark.tooling
def test_build_status_check_fails_when_step_failed():
    """A failed npm step must surface in findings."""
    result = run_build_status_check(
        build_status="failed",
        npm_steps=[
            {"name": "npm install", "ok": True, "seconds": 10.0},
            {"name": "npm run build", "ok": False, "seconds": 5.0},
        ],
    )
    assert result.status == "failed"
    assert "npm run build" in result.findings


# ---------------------------------------------------------------------------
# policy-compliance
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_policy_compliance_passes_on_clean_target(tmp_path):
    """No .env files anywhere -> status=ok."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text("ok", encoding="utf-8")
    (tmp_path / ".env.example").write_text("PUBLIC=ok", encoding="utf-8")
    result = run_policy_compliance_check(tmp_path)
    assert result.status == "ok"


@pytest.mark.tooling
def test_policy_compliance_flags_forbidden_env_files(tmp_path):
    """A stray .env or .env.local -> status=failed with the path in
    findings.
    """
    (tmp_path / ".env").write_text("SECRET=x", encoding="utf-8")
    (tmp_path / ".env.local").write_text("SECRET=y", encoding="utf-8")
    result = run_policy_compliance_check(tmp_path)
    assert result.status == "failed"
    assert ".env" in result.findings
    assert ".env.local" in result.findings


@pytest.mark.tooling
def test_policy_compliance_skips_node_modules(tmp_path):
    """node_modules is huge and we never own it. Make sure we don't flag
    transient .env files inside it (e.g. test fixtures of dependencies).
    """
    nm = tmp_path / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / ".env").write_text("FROM_DEPENDENCY=x", encoding="utf-8")
    result = run_policy_compliance_check(tmp_path)
    assert result.status == "ok"
    assert result.findings == []


# ---------------------------------------------------------------------------
# typecheck (skipped paths)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_typecheck_skipped_when_disabled(tmp_path):
    """do_typecheck=False -> status=skipped without invoking npx."""
    result = run_typecheck_check(tmp_path, do_typecheck=False)
    assert result.status == "skipped"
    assert "do_typecheck=False" in result.detail


@pytest.mark.tooling
def test_typecheck_skipped_when_no_node_modules(tmp_path):
    """node_modules missing -> skipped with explanation, no subprocess."""
    result = run_typecheck_check(tmp_path, do_typecheck=True)
    assert result.status == "skipped"
    assert "node_modules" in result.detail


# ---------------------------------------------------------------------------
# aggregate gate
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_quality_gate_aggregates_to_ok_when_all_pass(tmp_path):
    routes = ["/"]
    _write_page(tmp_path, "/")
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=routes,
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    assert isinstance(result, QualityResult)
    assert result.status == "ok"
    assert len(result.checks) == 4


@pytest.mark.tooling
def test_run_quality_gate_returns_failed_on_blocking_failure():
    """build-status=failed makes the aggregate failed (blocking)."""
    checks = [
        CheckResult(name="typecheck", status="ok"),
        CheckResult(name="route-scan", status="ok"),
        CheckResult(name="build-status", status="failed", detail="npm run build failed"),
        CheckResult(name="policy-compliance", status="ok"),
    ]
    assert _aggregate_status(checks) == "failed"


@pytest.mark.tooling
def test_run_quality_gate_returns_degraded_on_soft_failure():
    """route-scan failed but build/typecheck ok -> degraded, not failed."""
    checks = [
        CheckResult(name="typecheck", status="skipped"),
        CheckResult(name="route-scan", status="failed", detail="missing route"),
        CheckResult(name="build-status", status="ok"),
        CheckResult(name="policy-compliance", status="ok"),
    ]
    assert _aggregate_status(checks) == "degraded"


@pytest.mark.tooling
def test_run_quality_gate_summary_lists_failed_and_skipped(tmp_path):
    """The summary string is what shows up in trace events. It must list
    failed and skipped check names so an operator scanning trace.ndjson
    sees them without opening quality-result.json.
    """
    _write_page(tmp_path, "/")
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/", "/missing"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    assert "route-scan" in result.summary or "failed" in result.summary
    assert "skipped" in result.summary


@pytest.mark.tooling
def test_quality_result_round_trips_through_pydantic(tmp_path):
    """The orchestrator writes QualityResult.model_dump() to disk; the
    payload must be JSON-clean and reconstructable.
    """
    import json

    _write_page(tmp_path, "/")
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
    )
    payload = result.model_dump()
    json.dumps(payload)
    restored = QualityResult.model_validate(payload)
    assert restored.status == result.status
    assert len(restored.checks) == len(result.checks)


# ---------------------------------------------------------------------------
# Bug-fix locks (post-ec8339e cloud-agent review)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_typecheck_does_not_use_shell_true_with_list():
    """Cloud-agent finding: ``subprocess.run([list], shell=True)`` silently
    drops every argument after the first on POSIX (sh -c "npx" passes the
    rest as positional args $0..$N to the shell, not to the command). The
    typecheck check must mirror scripts/build_site.py:run_npm and use
    shutil.which + shell=False.
    """
    import inspect

    from packages.generation.quality_gate import checks as quality_checks

    source = inspect.getsource(quality_checks.run_typecheck_check)
    assert "shutil.which(" in source, (
        "run_typecheck_check must resolve the executable via "
        "shutil.which (mirrors scripts/build_site.py:run_npm)."
    )
    code_lines = [
        line for line in source.splitlines()
        if not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines)
    assert "shell=False" in code, (
        "run_typecheck_check must call subprocess.run with shell=False."
    )
    assert "shell=True" not in code, (
        "run_typecheck_check must not use shell=True in actual code "
        "(comments are fine, but the subprocess.run call must use "
        "shell=False). shell=True with a list silently drops args on "
        "POSIX. Use shutil.which + shell=False instead."
    )


@pytest.mark.tooling
def test_quality_gate_route_scan_is_authoritative_in_builder(tmp_path, monkeypatch):
    """Cloud-agent finding: assert_routes_present used to crash the build
    via SystemExit before Quality Gate route-scan could write structured
    findings to quality-result.json. Sprint 3A removed the call from the
    canonical build flow so route-scan owns the route check.
    """
    import inspect

    from scripts import build_site

    build_source = inspect.getsource(build_site.build)
    assert "assert_routes_present(target," not in build_source, (
        "scripts/build_site.py:build() must not call assert_routes_present. "
        "Quality Gate route-scan handles missing routes structurally; "
        "calling assert_routes_present here would crash the build before "
        "quality-result.json is written. The function still exists for "
        "B8/B9 regression tests in tests/test_builder_hardening.py."
    )
