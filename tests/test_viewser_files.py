"""Smoke tests for the Viewser MVP file layout."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"


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
        "components/chat-panel.tsx",
        "components/viewer-panel.tsx",
        "components/token-meter.tsx",
        "lib/openai.ts",
        "lib/build-runner.ts",
        ".env.example",
    ]

    missing = [path for path in expected if not (VIEWSER_DIR / path).exists()]
    assert not missing, f"Missing viewser files: {missing}"


@pytest.mark.tooling
def test_viewser_env_file_is_not_committed() -> None:
    assert not (VIEWSER_DIR / ".env").exists()
    assert not (VIEWSER_DIR / ".env.local").exists()
