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


@pytest.mark.tooling
def test_only_fly_adapter_returns_unsupported() -> None:
    """local/stackblitz är implementerade adaptrar; bara fly är reserverad stub.

    Bevis på att Bite B-adaptrarna faktiskt delegerar i stället för att vara
    Bite A-stubbar: de får inte längre emittera `status: "unsupported"`. Endast
    `fly` (oimplementerad enligt ADR 0028 §3 + ADR 0030) gör det.
    """
    local = (PREVIEW_RUNTIME_SRC / "adapters" / "local.ts").read_text(encoding="utf-8")
    stackblitz = (
        PREVIEW_RUNTIME_SRC / "adapters" / "stackblitz.ts"
    ).read_text(encoding="utf-8")
    vercel_sandbox = (
        PREVIEW_RUNTIME_SRC / "adapters" / "vercel-sandbox.ts"
    ).read_text(encoding="utf-8")
    fly = (PREVIEW_RUNTIME_SRC / "adapters" / "fly.ts").read_text(encoding="utf-8")

    assert 'status: "unsupported"' not in local
    assert 'status: "unsupported"' not in stackblitz
    # VercelSandboxRuntime är en implementerad adapter (ADR 0033) — den
    # degraderar till "failed" vid saknad auth/handler, aldrig "unsupported".
    assert 'status: "unsupported"' not in vercel_sandbox
    assert 'status: "unsupported"' in fly


@pytest.mark.tooling
def test_viewser_wiring_exposes_env_driven_entry_point() -> None:
    """App-lagret har en idempotent install + env-styrd resolver.

    `currentViewserRuntime()`/`resolveViewserRuntime()` garanterar att DI-
    handlers är installerade innan adaptern resolvas, så `localRuntime`/
    `stackblitzRuntime` aldrig faller tillbaka på sina "saknar handler"-grenar
    i normal drift.
    """
    viewser_wiring = (VIEWSER_DIR / "lib" / "preview-runtime-server.ts").read_text(
        encoding="utf-8"
    )

    assert "ensureViewserPreviewRuntimeHandlers" in viewser_wiring
    assert "currentViewserRuntime" in viewser_wiring
    assert "resolveViewserRuntime" in viewser_wiring
    assert "currentRuntime(env)" in viewser_wiring


@pytest.mark.tooling
def test_vercel_sandbox_adapter_is_wired() -> None:
    """ADR 0033: vercel-sandbox är en implementerad PreviewRuntime-adapter.

    Source-locks: registry mappar env-värdet, adaptern delegerar via DI till
    den injicerade handlern, app-lagret wirear in den server-only runnern, och
    compile-testet exercerar den nya kind:en. @vercel/sandbox får bara
    importeras i app-lagret (apps/viewser/lib), aldrig i paketet (ADR 0030).
    """
    registry = (PREVIEW_RUNTIME_SRC / "registry.ts").read_text(encoding="utf-8")
    adapter = (
        PREVIEW_RUNTIME_SRC / "adapters" / "vercel-sandbox.ts"
    ).read_text(encoding="utf-8")
    handlers = (PREVIEW_RUNTIME_SRC / "handlers.ts").read_text(encoding="utf-8")
    viewser_wiring = (VIEWSER_DIR / "lib" / "preview-runtime-server.ts").read_text(
        encoding="utf-8"
    )
    compile_test = (VIEWSER_DIR / "lib" / "preview-runtime.test.ts").read_text(
        encoding="utf-8"
    )

    assert 'case "vercel-sandbox":' in registry
    assert '"vercel-sandbox": vercelSandboxRuntime' in registry
    assert 'kind: "vercel-sandbox"' in adapter
    assert "getPreviewRuntimeHandlers().vercelSandbox" in adapter
    assert "vercelSandbox?: vercelSandboxPreviewRuntimeHandlers" in handlers
    assert "vercelSandbox:" in viewser_wiring
    assert "createSandboxPreview(" in viewser_wiring
    # Produktadaptern måste använda den spike-agnostiska runnern, ALDRIG en
    # ``*-spike.ts``-fil (coach-review #147). Spike-grinden bor bara i CLI:t.
    assert 'from "./vercel-sandbox-runner"' in viewser_wiring
    assert "vercel-sandbox-spike" not in viewser_wiring
    assert 'currentRuntime(envWithPreviewMode("vercel-sandbox"))' in compile_test


@pytest.mark.tooling
def test_vercel_sandbox_runner_is_spike_agnostic() -> None:
    """Cleanup (coach-review #147): den återanvändbara runnern är icke-spike-
    namngiven och innehåller ingen spike-flagga; spike-CLI:t äger grinden och
    delegerar till runnern. SDK:n bor i runnern (app-lagret). Det finns ingen
    ``*-spike.ts``-modul kvar att importera produktadaptern från."""
    runner = (VIEWSER_DIR / "lib" / "vercel-sandbox-runner.ts").read_text(
        encoding="utf-8"
    )
    cli = (REPO_ROOT / "scripts" / "spike_vercel_sandbox.ts").read_text(
        encoding="utf-8"
    )

    # Runnern är spike-agnostisk: ingen flagg-grind (varken SPIKE_FLAG-konst
    # eller spikeEnabled-check), men äger SDK-anropet. (TTL-env-namnet delas
    # fortfarande med spiken, vilket är ok — det är bara en knob, inte en grind.)
    assert "SPIKE_FLAG" not in runner
    assert "spikeEnabled" not in runner
    assert 'import("@vercel/sandbox")' in runner
    # Spike-CLI:t äger grinden och delegerar till samma runner.
    assert "VIEWSER_SANDBOX_SPIKE" in cli
    assert "spikeEnabled" in cli
    assert "vercel-sandbox-runner" in cli
    # Den gamla wrapper-modulen är borttagen (produktadaptern importerar runnern).
    assert not (VIEWSER_DIR / "lib" / "vercel-sandbox-spike.ts").exists()


@pytest.mark.tooling
def test_vercel_sdk_not_imported_in_preview_runtime_package() -> None:
    """ADR 0030: @vercel/sandbox-SDK:n får aldrig importeras i
    packages/preview-runtime (leverantörsberoende stannar i app-lagret).

    Skannar bara import/export-rader (inte kommentarer) — adapterns docstring
    nämner ``@vercel/sandbox`` i prosa, vilket inte är ett beroende.
    """
    offenders: list[str] = []
    for path in PREVIEW_RUNTIME_SRC.rglob("*.ts"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not (stripped.startswith("import ") or stripped.startswith("export ")):
                continue
            if "@vercel/sandbox" in stripped:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders, (
        "@vercel/sandbox får inte importeras i packages/preview-runtime: "
        f"{offenders}"
    )
