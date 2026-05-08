"""Regression tests for dossier mounting in Builder MVP."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.mark.tooling
def test_builder_mounts_pacman_dossier_files() -> None:
    from scripts.build_site import build

    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"
    target, _run_dir = build(project_input_path, do_build=False)

    assert (target / "components" / "pacman-game.tsx").exists(), (
        "Selected dossier component must be copied into generated components/"
    )
    spel_page = target / "app" / "spel" / "page.tsx"
    assert spel_page.exists(), "Selected dossier route /spel must be generated"
    assert "export default" in spel_page.read_text(encoding="utf-8")


@pytest.mark.tooling
def test_generated_pacman_site_passes_npm_build() -> None:
    npm = shutil.which("npm")
    if not npm:
        pytest.skip("npm is required for dossier mounting build verification")

    script_path = REPO_ROOT / "scripts" / "build_site.py"
    project_input_path = REPO_ROOT / "examples" / "painter-palma.project-input.json"

    run = subprocess.run(
        [sys.executable, str(script_path), "--dossier", str(project_input_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
