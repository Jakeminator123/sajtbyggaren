"""Security/source locks for demo-baseline-fix 1B Viewser changes.

The long-standing ``tests/test_viewser_files.py`` source-lock file is
off-limits for this sprint because it also guards the parked StackBlitz
surface. These focused checks cover only the localhost guard and
build-runner whitelist changes introduced by B70/B78.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"


@pytest.mark.tooling
def test_localhost_guard_parses_bracketed_ipv6_hosts() -> None:
    """B70: ``Host: [::1]:3000`` must not be split on the first colon."""
    text = (VIEWSER_DIR / "lib" / "localhost-guard.ts").read_text(
        encoding="utf-8"
    )

    assert "hostFromHeader" in text
    assert "::1" in text
    assert re.search(r"\\\[\(\.\+\)\\\]", text), (
        "localhost-guard.ts must parse bracketed IPv6 host headers "
        "such as [::1]:3000 before comparing against LOCAL_HOST_NAMES."
    )
    assert '["localhost", "127.0.0.1", "::1"]' in text
    assert 'split(":")[0]' not in text, (
        "B70 regression: splitting Host on ':' turns '[::1]:3000' into '['."
    )


@pytest.mark.tooling
def test_build_runner_realpaths_dossier_override_before_whitelist() -> None:
    """B78: dossier override whitelist must compare real paths, not
    syntactic ``path.resolve`` values that a symlink can spoof.
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(
        encoding="utf-8"
    )

    assert "async function assertDossierPathAllowed" in text
    assert "await fs.realpath(path.resolve(absoluteDossierPath))" in text
    assert "await fs.realpath(path.resolve(root, subdir))" in text
    assert "await assertDossierPathAllowed(dossierPathOverride)" in text
    assert "path.relative(allowed, resolved)" in text


@pytest.mark.tooling
def test_list_runs_slices_before_reading_build_results() -> None:
    """B72: listRuns may stat all run directories, but JSON reads should
    happen only for the newest ``limit`` survivors.
    """
    text = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    function_start = text.index("export async function listRuns")
    function_body = text[function_start : text.index("function stringOrUndefined")]

    slice_idx = function_body.index(".slice(0, limit)")
    build_read_idx = function_body.index("readJsonFile<")
    assert slice_idx < build_read_idx, (
        "listRuns must sort/stat directories and slice to limit before "
        "reading build-result.json, otherwise GET /api/runs remains O(N) "
        "JSON reads per refresh."
    )
    assert "b.stats.mtimeMs - a.stats.mtimeMs" in function_body


@pytest.mark.tooling
def test_run_details_bundle_and_panel_include_site_plan() -> None:
    """B76: Run Details should surface ``site-plan.json`` alongside
    build, quality, repair and model artefacts.
    """
    runs_text = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )

    assert "sitePlan: Record<string, unknown> | null" in runs_text
    assert '"site-plan.json"' in runs_text
    assert "sitePlan," in runs_text
    assert "SitePlanSection" in panel_text
    assert "routePlan:" in panel_text
    assert "<SitePlanSection sitePlan={bundle.sitePlan} />" in panel_text
