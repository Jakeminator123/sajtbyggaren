"""Source-level locks for PreviewRuntime Bite B dependency injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_RUNTIME_SRC = REPO_ROOT / "packages" / "preview-runtime" / "src"
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"


@pytest.mark.tooling
def test_preview_runtime_package_does_not_import_viewser_app() -> None:
    offenders: list[str] = []
    for path in PREVIEW_RUNTIME_SRC.rglob("*.ts"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("export ")):
                continue
            if "apps/viewser" in stripped or "@/lib/" in stripped:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert not offenders, (
        "packages/preview-runtime får inte importera apps/viewser direkt: "
        f"{offenders}"
    )


@pytest.mark.tooling
def test_viewser_tsconfig_exposes_preview_runtime_path_alias() -> None:
    tsconfig = json.loads((VIEWSER_DIR / "tsconfig.json").read_text(encoding="utf-8"))
    paths = tsconfig["compilerOptions"]["paths"]

    assert paths["@preview-runtime"] == ["../../packages/preview-runtime/src/index"]
    assert paths["@preview-runtime/*"] == ["../../packages/preview-runtime/src/*"]
    assert "../../packages/preview-runtime/src/**/*.ts" in tsconfig["include"]


@pytest.mark.tooling
def test_preview_runtime_registry_and_di_delegation_are_locked() -> None:
    registry = (PREVIEW_RUNTIME_SRC / "registry.ts").read_text(encoding="utf-8")
    local = (PREVIEW_RUNTIME_SRC / "adapters" / "local.ts").read_text(encoding="utf-8")
    stackblitz = (
        PREVIEW_RUNTIME_SRC / "adapters" / "stackblitz.ts"
    ).read_text(encoding="utf-8")
    viewser_wiring = (VIEWSER_DIR / "lib" / "preview-runtime-server.ts").read_text(
        encoding="utf-8"
    )
    compile_test = (VIEWSER_DIR / "lib" / "preview-runtime.test.ts").read_text(
        encoding="utf-8"
    )

    assert "case \"local-next\":" in registry
    assert "case \"stackblitz\":" in registry
    assert "getPreviewRuntimeHandlers().local" in local
    assert "handler.start(config)" in local
    assert "getPreviewRuntimeHandlers().stackblitz" in stackblitz
    assert "handler.readFiles(config)" in stackblitz
    assert "configurePreviewRuntimeHandlers" in viewser_wiring
    assert "startPreviewServer(requireSiteId(config))" in viewser_wiring
    assert "readRunFilesForStackblitz(requireRunId(config))" in viewser_wiring
    assert "currentRuntime(envWithPreviewMode(\"local-next\"))" in compile_test
    assert "currentRuntime(envWithPreviewMode(\"stackblitz\"))" in compile_test
