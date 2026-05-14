"""Regression tests for Builder MVP hardening (round 2).

Each test corresponds to a specific bug ID from the audit captured in
``docs/known-issues.md``. New bugs found in audits MUST land here as a
test before they are fixed.

These tests do not require Node, npm or network. They exercise the Python
helpers in ``scripts/build_site.py`` directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# B4 - .env guard must be case-insensitive
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_env_guard_blocks_case_variants(tmp_path: Path) -> None:
    """B4: writing `.ENV`, `.Env.Local`, `.env.production` must raise."""
    from scripts.build_site import write

    for variant in [".env", ".ENV", ".Env", ".env.local", ".ENV.LOCAL", ".env.production"]:
        target = tmp_path / variant
        with pytest.raises(AssertionError):
            write(target, "SECRET=oops\n")


@pytest.mark.tooling
def test_env_example_still_allowed(tmp_path: Path) -> None:
    """B4 negative: .env.example is the canonical placeholder and must work."""
    from scripts.build_site import write

    target = tmp_path / ".env.example"
    write(target, "# placeholder\n")
    assert target.exists()


# ---------------------------------------------------------------------------
# B5 - copy_starter must ignore .env*
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_copy_starter_ignore_blocks_env_files(tmp_path: Path) -> None:
    """B5: a starter that accidentally contains a real `.env.local` must not leak."""
    from scripts.build_site import _ignore_combined

    names = [
        ".env",
        ".env.local",
        ".env.production",
        ".ENV",
        ".env.example",
        "package.json",
        "node_modules",
        ".next",
    ]
    skipped = _ignore_combined(str(tmp_path), names)
    assert ".env" in skipped
    assert ".env.local" in skipped
    assert ".env.production" in skipped
    assert ".ENV" in skipped
    assert ".env.example" not in skipped
    assert "package.json" not in skipped
    assert "node_modules" in skipped
    assert ".next" in skipped


@pytest.mark.tooling
def test_copy_starter_drops_stale_next_cache_but_preserves_node_modules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B41: regeneration must not carry stale `.next` build output forward.

    The builder intentionally preserves ``node_modules`` between
    regenerations to avoid a full npm install on every run, but ``.next``
    is framework-derived output. Keeping it lets stale prerender/cache
    state survive package or template changes and can surface as Next's
    internal ``/_global-error`` prerender crash even though a clean target
    builds successfully.
    """
    import scripts.build_site as build_site

    starters_dir = tmp_path / "starters"
    source = starters_dir / "marketing-base"
    (source / "app").mkdir(parents=True)
    (source / "app" / "page.tsx").write_text(
        "export default function Home() { return <main />; }\n",
        encoding="utf-8",
    )
    (source / "package.json").write_text('{"name":"marketing-base"}\n', encoding="utf-8")
    (source / ".next").mkdir()
    (source / ".next" / "source-cache").write_text("ignored\n", encoding="utf-8")

    target = tmp_path / "generated" / "painter-palma"
    (target / "node_modules").mkdir(parents=True)
    (target / "node_modules" / "kept.txt").write_text("keep\n", encoding="utf-8")
    (target / ".next").mkdir()
    (target / ".next" / "stale.txt").write_text("stale\n", encoding="utf-8")
    (target / "old.txt").write_text("remove\n", encoding="utf-8")

    monkeypatch.setattr(build_site, "STARTERS_DIR", starters_dir)

    build_site.copy_starter("marketing-base", target)

    assert (target / "node_modules" / "kept.txt").exists()
    assert not (target / ".next").exists(), (
        "copy_starter must remove stale .next output before each regeneration "
        "so Next prerender caches cannot leak across builds."
    )
    assert not (target / "old.txt").exists()
    assert (target / "app" / "page.tsx").exists()
    assert (target / "package.json").exists()


# ---------------------------------------------------------------------------
# B6/B10 - runId must not collide on rapid regeneration
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_id_unique_under_rapid_calls() -> None:
    """B6/B10: 50 sequential make_run_id calls must produce 50 unique ids."""
    from scripts.build_site import make_run_id

    ids = [make_run_id("painter-palma") for _ in range(50)]
    assert len(ids) == len(set(ids)), "runId collisions detected"
    for run_id in ids:
        assert run_id.endswith("-painter-palma")
        # Format: 20260507T185115.481Z-<8hex>-<siteId>
        head, _, _site = run_id.rpartition("-painter-palma")
        # head looks like 20260507T185115.481Z-ab12cd34
        assert "Z-" in head
        stamp_part, _, suffix = head.partition("Z-")
        assert "." in stamp_part
        assert len(suffix) == 8


# ---------------------------------------------------------------------------
# B8/B9 - route guard must check default export
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_route_guard_blocks_missing_default_export(tmp_path: Path) -> None:
    """B9: a page.tsx without a default export must fail the guard."""
    from scripts.build_site import assert_routes_present

    app_dir = tmp_path / "app"
    (app_dir / "kontakt").mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Home() { return <main />; }\n",
        encoding="utf-8",
    )
    # Missing default export on /kontakt
    (app_dir / "kontakt" / "page.tsx").write_text(
        "export const ContactPage = () => null;\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        assert_routes_present(tmp_path, ["/", "/kontakt"])
    assert "default export" in str(exc.value)


@pytest.mark.tooling
def test_route_guard_accepts_valid_pages(tmp_path: Path) -> None:
    """B9 negative: pages with default export must pass."""
    from scripts.build_site import assert_routes_present

    app_dir = tmp_path / "app"
    (app_dir / "kontakt").mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Home() { return <main />; }\n",
        encoding="utf-8",
    )
    (app_dir / "kontakt" / "page.tsx").write_text(
        "export default function ContactPage() { return <main />; }\n",
        encoding="utf-8",
    )
    assert_routes_present(tmp_path, ["/", "/kontakt"])  # must not raise


@pytest.mark.tooling
def test_route_guard_blocks_missing_route(tmp_path: Path) -> None:
    """B8: a missing required route file must fail the guard."""
    from scripts.build_site import assert_routes_present

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "page.tsx").write_text(
        "export default function Home() { return <main />; }\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        assert_routes_present(tmp_path, ["/", "/tjanster"])
    assert "missing route files" in str(exc.value)


# ---------------------------------------------------------------------------
# B1 - all 8 Engine Run artefakter must exist after build()
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_all_eight_engine_run_artifacts_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B1: data/runs/<runId>/ must hold all 8 artefakter (5 json + 1 ndjson + 1 dir + skeletons)."""
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    target, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)
    assert target.exists()

    expected = [
        "input.json",
        "site-brief.json",
        "site-plan.json",
        "generation-package.json",
        "build-result.json",
        "trace.ndjson",
        "repair-result.json",
        "quality-result.json",
    ]
    for name in expected:
        assert (run_dir / name).exists(), f"Missing artefakt: {name}"

    # Generated files snapshot
    snap = run_dir / "generated-files"
    assert snap.is_dir()
    assert (snap / "package.json").exists()
    assert (snap / "app" / "page.tsx").exists()
    # Snapshot must NOT contain node_modules.
    assert not (snap / "node_modules").exists()


# ---------------------------------------------------------------------------
# B2/BO1 - build-result.json must contain modelUsage with zeroed fields
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_build_result_has_model_usage_stub(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B2/BO1: ``modelUsage`` must be present even when LLM is not called yet."""
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)
    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))

    assert "modelUsage" in result
    usage = result["modelUsage"]
    for field in ["totalInputTokens", "totalOutputTokens", "totalCostUsd", "currency", "source"]:
        assert field in usage
    assert usage["totalInputTokens"] == 0
    assert usage["totalOutputTokens"] == 0
    assert usage["totalCostUsd"] == 0.0
    assert usage["source"] == "mock-no-key"


# ---------------------------------------------------------------------------
# B11 - generatedFilesDir must point to data/runs/<runId>/generated-files/
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generated_files_dir_points_to_run_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B11: build-result.generatedFilesDir must be the canonical snapshot path."""
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)
    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))

    from scripts.build_site import _to_repo_relative

    expected = _to_repo_relative(run_dir / "generated-files")
    assert result["generatedFilesDir"] == expected
    # Dev preview is also exposed but as a separate field, not the canonical one.
    assert "/.generated/" in result["devPreviewDir"]


# ---------------------------------------------------------------------------
# B3 - trace event names use dotted form (input.written, files.written, ...)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_trace_event_names_use_dotted_form(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B3: event names must follow ``area.action`` format, matching dev_generate.py."""
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)
    events: list[dict] = []
    with (run_dir / "trace.ndjson").open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))

    expected_events = {
        "phase.started",
        "input.written",
        "site_brief.written",
        "site_plan.written",
        "generation_package.written",
        "files.written",
        "phase.completed",
        "generated_files.snapshotted",
        "repair_result.written",
        "quality_result.written",
        "build.result.written",
    }
    seen = {e["event"] for e in events}
    missing = expected_events - seen
    assert not missing, f"Missing dotted trace events: {missing}"


# ---------------------------------------------------------------------------
# Sprint 3A (ADR 0015): Quality Gate + Repair Pipeline produce real results,
# not the Sprint 2B skeleton with status=not-run.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_repair_and_quality_results_are_not_skeleton(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Sprint 3A replaces the skeleton writers with real pipeline calls.

    The artefakter must:
      - Use the new statuses (quality: ok/degraded/failed; repair:
        not-needed/no-fix-applied/fixed/partial-fix), never ``not-run``.
      - Carry a ``checks`` array on quality-result.json with the four
        Sprint 3A check names (typecheck, route-scan, build-status,
        policy-compliance).

    For ``--skip-build``, the painter-palma example produces all required
    routes from the marketing-base starter, so route-scan and policy-
    compliance pass while typecheck and build-status are skipped. Quality
    Gate aggregates this to ``ok`` and Repair Pipeline reports ``not-needed``.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False, runs_dir=tmp_path)
    repair = json.loads((run_dir / "repair-result.json").read_text(encoding="utf-8"))
    quality = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))

    assert quality["status"] in {"ok", "degraded", "failed"}, (
        f"Quality Gate must report Sprint 3A status, got {quality['status']!r}. "
        f"If this says 'not-run', the skeleton writer has crept back into "
        f"scripts/build_site.py (B-test in test_build_site_size.py should "
        f"have caught it first)."
    )
    assert repair["status"] in {
        "not-needed", "no-fix-applied", "fixed", "partial-fix"
    }, (
        f"Repair Pipeline must report Sprint 3A status, got {repair['status']!r}. "
        f"The skeleton path returned 'not-run' which Sprint 3A removed."
    )

    check_names = {check["name"] for check in quality["checks"]}
    assert check_names == {
        "typecheck", "route-scan", "build-status", "policy-compliance"
    }, (
        f"Quality Gate must run the four Sprint 3A checks. Got {check_names!r}."
    )

    by_name = {check["name"]: check for check in quality["checks"]}
    assert by_name["build-status"]["status"] == "skipped", (
        "do_build=False must produce build-status=skipped, not failed/ok."
    )
    assert by_name["typecheck"]["status"] == "skipped", (
        "typecheck must be skipped when build was skipped (no node_modules)."
    )
    assert by_name["route-scan"]["status"] == "ok", (
        "painter-palma + marketing-base produces all required routes; "
        "route-scan should be ok."
    )

    assert quality["status"] == "ok"
    assert repair["status"] == "not-needed"
    assert repair["mechanicalFixesApplied"] == []
    assert repair["llmFixesApplied"] == []


# ---------------------------------------------------------------------------
# B16 - npm install / npm run build must not hang forever
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_npm_returns_failure_on_timeout(monkeypatch, tmp_path: Path) -> None:
    """run_npm must catch subprocess.TimeoutExpired and return (False, elapsed, msg)."""
    import subprocess

    from scripts import build_site

    monkeypatch.setattr(build_site.shutil, "which", lambda _: "/usr/bin/npm")

    def fake_run(*_args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args", ["npm", "install"]),
            timeout=kwargs.get("timeout", 1.0),
            output=b"partial install output\nstill working\n",
            stderr=b"",
        )

    monkeypatch.setattr(build_site.subprocess, "run", fake_run)

    ok, elapsed, last = build_site.run_npm(["npm", "install"], tmp_path, timeout=1.0)

    assert ok is False
    assert elapsed >= 0.0
    assert "timeout" in last.lower()
    assert "npm install" in last


@pytest.mark.tooling
def test_npm_timeout_constants_are_defined() -> None:
    """build_site.py must expose NPM_INSTALL_TIMEOUT_SECONDS and NPM_BUILD_TIMEOUT_SECONDS."""
    from scripts import build_site

    assert hasattr(build_site, "NPM_INSTALL_TIMEOUT_SECONDS"), (
        "Removing the npm install timeout would re-open B16."
    )
    assert hasattr(build_site, "NPM_BUILD_TIMEOUT_SECONDS"), (
        "Removing the npm run build timeout would re-open B16."
    )
    assert build_site.NPM_INSTALL_TIMEOUT_SECONDS > 0
    assert build_site.NPM_BUILD_TIMEOUT_SECONDS > 0


@pytest.mark.tooling
def test_build_calls_run_npm_with_documented_timeouts(monkeypatch, tmp_path: Path) -> None:
    """build() must pass the documented timeouts to run_npm for both steps.

    npm install is skipped when ``node_modules`` already exists in the
    generated dir (which is the case in dev), so the assertion only
    enforces the timeout value when run_npm is actually called for that
    step. ``npm run build`` always runs in do_build=True so it is
    asserted unconditionally.
    """
    from scripts import build_site

    captured: list[dict] = []

    def fake_run_npm(command, _cwd, *, timeout=None):
        captured.append({"command": list(command), "timeout": timeout})
        return True, 0.1, ""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(build_site, "run_npm", fake_run_npm)

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    build_site.build(project_input_path, do_build=True, runs_dir=tmp_path)

    install_calls = [c for c in captured if c["command"][:2] == ["npm", "install"]]
    build_calls = [c for c in captured if c["command"][:2] == ["npm", "run"]]

    assert build_calls, "build(do_build=True) must call run_npm for npm run build"
    for call in build_calls:
        assert call["timeout"] == build_site.NPM_BUILD_TIMEOUT_SECONDS, (
            f"npm run build must use NPM_BUILD_TIMEOUT_SECONDS, got {call['timeout']!r}"
        )
    for call in install_calls:
        assert call["timeout"] == build_site.NPM_INSTALL_TIMEOUT_SECONDS, (
            f"npm install must use NPM_INSTALL_TIMEOUT_SECONDS, got {call['timeout']!r}"
        )


@pytest.mark.tooling
def test_failed_npm_build_step_is_written_with_log_excerpt(
    monkeypatch, tmp_path: Path
) -> None:
    """Run Details must preserve the real npm error, not just ok/failed."""
    from scripts import build_site

    def fake_run_npm(command, _cwd, *, timeout=None):
        if command[:3] == ["npm", "run", "build"]:
            return False, 2.3, "Failed to compile\napp/page.tsx\nType error: boom"
        return True, 0.4, ""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(build_site, "run_npm", fake_run_npm)

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    with pytest.raises(SystemExit):
        build_site.build(
            project_input_path,
            do_build=True,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
        )

    run_dirs = [path for path in runs_dir.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    build_result = json.loads(
        (run_dirs[0] / "build-result.json").read_text(encoding="utf-8")
    )

    build_step = next(
        step for step in build_result["npmSteps"] if step["name"] == "npm run build"
    )
    assert build_step["ok"] is False
    assert "Type error: boom" in build_step["logExcerpt"]
