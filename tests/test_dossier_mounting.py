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


@pytest.mark.tooling
def test_explicit_empty_requested_capabilities_is_respected() -> None:
    """An explicit empty ``requestedCapabilities`` must NOT fall back to service ids."""
    from scripts.build_site import build_site_brief_mock

    dossier = {
        "language": "sv",
        "company": {"name": "Test", "businessType": "painter", "tagline": "t"},
        "location": {"city": "x", "region": "y", "country": "z", "serviceAreas": []},
        "tone": {"primary": "lugn", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "services": [{"id": "interior-painting", "label": "x", "summary": "y"}],
        "requestedCapabilities": [],
    }
    scaffold = {"id": "local-service-business"}

    brief = build_site_brief_mock(dossier, scaffold)

    assert brief["requestedCapabilities"] == [], (
        "Explicit empty requestedCapabilities must be honoured, not silently "
        "replaced by service ids."
    )


@pytest.mark.tooling
def test_missing_requested_capabilities_falls_back_to_services() -> None:
    """When the field is absent the legacy service-id fallback still kicks in."""
    from scripts.build_site import build_site_brief_mock

    dossier = {
        "language": "sv",
        "company": {"name": "Test", "businessType": "painter", "tagline": "t"},
        "location": {"city": "x", "region": "y", "country": "z", "serviceAreas": []},
        "tone": {"primary": "lugn", "secondary": [], "avoid": []},
        "trustSignals": [],
        "conversionGoals": [],
        "services": [
            {"id": "interior-painting", "label": "a", "summary": "b"},
            {"id": "exterior-painting", "label": "c", "summary": "d"},
        ],
    }
    scaffold = {"id": "local-service-business"}

    brief = build_site_brief_mock(dossier, scaffold)

    assert brief["requestedCapabilities"] == ["interior-painting", "exterior-painting"]


@pytest.mark.tooling
def test_dossier_component_collision_fails_fast(tmp_path: Path) -> None:
    """Two dossiers exporting the same component filename must fail loudly."""
    from scripts.build_site import mount_dossier_components

    dossier_a = tmp_path / "dossier-a"
    (dossier_a / "components").mkdir(parents=True)
    (dossier_a / "components" / "card-component.tsx").write_text(
        "export default function A() { return null; }\n", encoding="utf-8"
    )

    dossier_b = tmp_path / "dossier-b"
    (dossier_b / "components").mkdir(parents=True)
    (dossier_b / "components" / "card-component.tsx").write_text(
        "export default function B() { return null; }\n", encoding="utf-8"
    )

    target = tmp_path / "site"

    selected = [
        {"id": "dossier-a", "class": "soft", "dir": dossier_a, "manifest": {}},
        {"id": "dossier-b", "class": "soft", "dir": dossier_b, "manifest": {}},
    ]

    with pytest.raises(SystemExit) as excinfo:
        mount_dossier_components(target, selected)

    message = str(excinfo.value)
    assert "card-component.tsx" in message
    assert "dossier-a" in message
    assert "dossier-b" in message
