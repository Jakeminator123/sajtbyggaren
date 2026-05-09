"""Smoke tests for the Viewser MVP file layout and scope discipline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
NAMING_PATH = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"


@pytest.mark.tooling
def test_viewser_expected_files_exist() -> None:
    expected = [
        "package.json",
        "app/layout.tsx",
        "app/page.tsx",
        "app/api/chat/route.ts",
        "app/api/build/route.ts",
        "app/api/runs/route.ts",
        "app/api/runs/[runId]/files/route.ts",
        # Builder UX MVP: artefact bundle endpoint feeds RunDetailsPanel
        # the four canonical Engine Run artefakter in one round-trip.
        "app/api/runs/[runId]/artifacts/route.ts",
        "components/chat-panel.tsx",
        "components/viewer-panel.tsx",
        "components/token-meter.tsx",
        "components/project-input-picker.tsx",
        "components/run-history.tsx",
        # Builder UX MVP: 5-section pedagogical render of build/quality/
        # repair/codegen/models with defensive fallbacks for older runs.
        "components/run-details-panel.tsx",
        "lib/openai.ts",
        "lib/build-runner.ts",
        "lib/localhost-guard.ts",
        "lib/project-inputs.ts",
        "lib/runs.ts",
        "lib/stackblitz-files.ts",
        ".env.example",
    ]
    missing = [path for path in expected if not (VIEWSER_DIR / path).exists()]
    assert not missing, f"Missing viewser files: {missing}"


@pytest.mark.tooling
def test_viewser_legacy_dossier_picker_removed() -> None:
    """Operator-mentalmodellen kräver Project Input - inte Dossier - picker."""
    assert not (VIEWSER_DIR / "components" / "dossier-picker.tsx").exists()
    assert not (VIEWSER_DIR / "lib" / "dossiers.ts").exists()


@pytest.mark.tooling
def test_viewser_env_file_is_not_committed() -> None:
    assert not (VIEWSER_DIR / ".env").exists()
    assert not (VIEWSER_DIR / ".env.local").exists()


@pytest.mark.tooling
def test_viewser_env_example_documents_localhost_and_token_cap() -> None:
    """Token cap och localhost-guard MÅSTE vara dokumenterade i .env.example."""
    text = (VIEWSER_DIR / ".env.example").read_text(encoding="utf-8")
    assert "VIEWSER_MAX_CHAT_TOKENS" in text
    assert "VIEWSER_ALLOW_NON_LOCALHOST" in text


@pytest.mark.tooling
def test_viewser_api_routes_call_localhost_guard() -> None:
    """Varje API route MÅSTE kalla localhost-guard innan den gör arbete."""
    routes = [
        "app/api/chat/route.ts",
        "app/api/build/route.ts",
        "app/api/runs/route.ts",
        "app/api/runs/[runId]/files/route.ts",
        "app/api/runs/[runId]/artifacts/route.ts",
    ]
    for route in routes:
        text = (VIEWSER_DIR / route).read_text(encoding="utf-8")
        assert "assertLocalhost" in text, f"{route} saknar localhost-guard"


@pytest.mark.tooling
def test_run_details_panel_handles_missing_artefakter_defensively() -> None:
    """B38 / Builder UX MVP: ÄLDRE runs (pre-Sprint 3A) saknar
    quality-result.json + repair-result.json, och dev_generate-runs
    saknar routes / npmSteps / generatedFilesDir på top-level. UI:t
    måste rendera dessa fall som "saknas i äldre run" / "ej spårad än"
    istället för att krascha eller visa odefinierade fält som rå JSON.

    Locking the fallback strings here makes accidental regression
    surface as a string-mismatch rather than a runtime crash in the
    browser.
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )
    expected_fallbacks = [
        "saknas i äldre run",
        "ej spårad än",
        "saknas i denna run",
    ]
    for fallback in expected_fallbacks:
        assert fallback in panel_text, (
            f"RunDetailsPanel saknar defensiv fallback-text {fallback!r}. "
            "UI:t måste vara läsbart för pre-Sprint-3A runs och dev_generate-mocks."
        )


@pytest.mark.tooling
def test_chat_panel_marks_prompt_as_experimental() -> None:
    """Builder UX MVP scope: free-form prompt får visas men ska inte
    framstå som primary path. Project Input + Build är den stabila
    vägen tills en separat sprint kopplar promptens output till
    run-flödet.
    """
    text = (VIEWSER_DIR / "components" / "chat-panel.tsx").read_text(encoding="utf-8")
    assert "experimentell" in text.lower() or "experimental" in text.lower(), (
        "Promptfältet ska visa pedagogisk text om att det är experimentellt "
        "och inte påverkar run-flödet i denna runda."
    )


@pytest.mark.tooling
def test_build_runner_returns_structured_failure_instead_of_throwing() -> None:
    """B40: when scripts/build_site.py exits 1 because npm install /
    npm run build failed, it STILL writes the canonical artefakter
    (build-result.json with status=failed, plus quality-result.json +
    repair-result.json + the generated-files/ snapshot) per the
    Builder MVP contract. The dev wrapper used to throw on any
    non-zero exit, which dropped the runId on the floor and forced
    /api/build to return 500 with no way for the UI to surface a
    failed run. The defensive path now reads build-result.json from
    disk and returns it as a normal result so the Run History entry
    shows up with status=failed and the RunDetailsPanel can render
    the four artefakter for diagnosis. Only when there's no runId
    AND no structured artefakt does the wrapper throw.
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")

    # The defensive read must call readBuildResult inside the
    # exitCode !== 0 branch and only throw when that read fails.
    # Locking these two phrases together as a source-level regression
    # guard keeps the contract stable without spinning up a Node
    # process.
    assert "structured-failure" in text or "strukturerad output" in text, (
        "build-runner.ts must document the structured-failure path "
        "(see B40). Either the inline comment or the throw-message "
        "needs to mention it so the next reader sees the contract."
    )
    assert "readBuildResult(runId)" in text, (
        "build-runner.ts must read build-result.json from disk in the "
        "exit !== 0 branch so failed runs reach the UI with their "
        "structured failure data instead of a bare 500."
    )


@pytest.mark.tooling
def test_run_history_uses_status_dot_colors() -> None:
    """UX-prioritet 2 (GPT-reviewer): Run History ska visa per-run
    status-färgning, inte bara en select med textstatus. Lås det
    färgkonceptet så framtida refactor inte återgår till plain
    select.
    """
    text = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    assert "STATUS_DOT_COLORS" in text, (
        "RunHistory ska mappa status -> färgklass via STATUS_DOT_COLORS-tabellen."
    )
    for status in ("ok", "failed", "degraded", "mock-complete"):
        assert status in text, (
            f"RunHistory saknar färg-mapping för status {status!r}."
        )


@pytest.mark.tooling
def test_viewser_does_not_register_ui_components_in_naming_dictionary() -> None:
    """v9 tar bort chatPanel/viewerPanel/tokenMeter; viewser stannar kvar."""
    naming = json.loads(NAMING_PATH.read_text(encoding="utf-8"))
    term_ids = {term["id"] for term in naming["terms"]}
    assert "viewser" in term_ids, "viewser ska vara canonical operator-yta"
    for forbidden in ["chatPanel", "viewerPanel", "tokenMeter"]:
        assert forbidden not in term_ids, (
            f"{forbidden} ska inte vara canonical term i naming-dictionary v9; "
            "det är en lokal UI-komponent i apps/viewser/"
        )


@pytest.mark.tooling
def test_viewser_scope_excludes_canonical_runtime_features() -> None:
    """Viewser MVP får INTE innehålla Dossier-edit, DNA, follow-up, repair, quality."""
    forbidden_substrings = [
        "ProjectDna",
        "RepairPipeline",
        "QualityGate",
        "FollowUp",
        "DossierEditor",
    ]
    for path in VIEWSER_DIR.rglob("*.ts*"):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_substrings:
            assert needle not in text, (
                f"{path.relative_to(REPO_ROOT)} innehåller out-of-scope-symbol "
                f"'{needle}'. Viewser MVP är localhost-prototype, inte canonical runtime."
            )
