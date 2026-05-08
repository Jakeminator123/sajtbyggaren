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
def test_all_eight_engine_run_artifacts_present() -> None:
    """B1: data/runs/<runId>/ must hold all 8 artefakter (5 json + 1 ndjson + 1 dir + skeletons)."""
    from scripts.build_site import build

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    target, run_dir = build(project_input_path, do_build=False)
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
def test_build_result_has_model_usage_stub() -> None:
    """B2/BO1: ``modelUsage`` must be present even when LLM is not called yet."""
    from scripts.build_site import build

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False)
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
def test_generated_files_dir_points_to_run_snapshot() -> None:
    """B11: build-result.generatedFilesDir must be the canonical snapshot path."""
    from scripts.build_site import build

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False)
    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))

    rel_run = str(run_dir.relative_to(REPO_ROOT)).replace("\\", "/")
    assert result["generatedFilesDir"] == f"{rel_run}/generated-files"
    # Dev preview is also exposed but as a separate field, not the canonical one.
    assert result["devPreviewDir"].startswith(".generated/")


# ---------------------------------------------------------------------------
# B3 - trace event names use dotted form (input.written, files.written, ...)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_trace_event_names_use_dotted_form() -> None:
    """B3: event names must follow ``area.action`` format, matching dev_generate.py."""
    from scripts.build_site import build

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False)
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
# Repair + Quality skeletons report status=not-run
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_repair_and_quality_skeleton_status_not_run() -> None:
    """Skeleton artefakter must clearly say ``not-run`` so they cannot be confused with real results."""
    from scripts.build_site import build

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    _, run_dir = build(project_input_path, do_build=False)
    repair = json.loads((run_dir / "repair-result.json").read_text(encoding="utf-8"))
    quality = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))

    assert repair["status"] == "not-run"
    assert quality["status"] == "not-run"
