"""Source-level locks for B195 — stale-blob-cleanup in hosted preview.

Hostat bygge laddar upp filer till blob under ``generated/<siteId>/`` med
overwrite per fil men raderar ALDRIG blobbar som försvunnit mellan två byggen
mot samma ``siteId``. Utan en härdning blir en borttagen route/asset kvar och
visas stale i previewen. Fixet (approach a): bygget publicerar ett
``.manifest.json`` med exakt fil-setet och serveringen visar bara
manifest-listade filer. Dessa lås speglar testmönstret i
``test_preview_runtime_di.py`` — de körs i pytest-banan som CI faktiskt kör,
medan ``generated-blob-source.test.ts`` ger den körbara enhetstäckningen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER_LIB = REPO_ROOT / "apps" / "viewser" / "lib"


@pytest.mark.tooling
def test_blob_source_serves_only_manifest_listed_files() -> None:
    source = (VIEWSER_LIB / "generated-blob-source.ts").read_text(encoding="utf-8")

    assert 'MANIFEST_RELPATH = ".manifest.json"' in source
    assert "export function selectServedRelPaths(" in source
    # Serveringen MÅSTE gå via urvalsfunktionen, annars listas hela prefixet
    # (det stale-buggade beteendet).
    assert "selectServedRelPaths([...byRel.keys()], manifestRelPaths)" in source
    assert "fetchManifestRelPaths(" in source


@pytest.mark.tooling
def test_select_served_relpaths_drops_stale_and_falls_back() -> None:
    source = (VIEWSER_LIB / "generated-blob-source.ts").read_text(encoding="utf-8")
    body = source.split("export function selectServedRelPaths(", 1)[1]

    # Utan manifest: bakåtkompatibel fallback till hela listningen.
    assert "if (!manifestRelPaths) {" in body
    # Defensivt: en manifest-post utan motsvarande blob serveras inte.
    assert "if (!listed.has(rel)) continue;" in body


@pytest.mark.tooling
def test_hosted_build_publishes_manifest_last() -> None:
    runner = (VIEWSER_LIB / "hosted-build-runner.ts").read_text(encoding="utf-8")

    # Bygget ackumulerar det faktiska upload-setet och publicerar manifestet.
    assert "/tmp/served-manifest.txt" in runner
    assert 'BUILD_DIR/.manifest.json' in runner
    assert 'upload_file ".manifest.json"' in runner
    # Manifestet skrivs EFTER den hårda "0 filer"-kontrollen så det aldrig
    # pekar på en saknad blob.
    guard_idx = runner.index("0 filer laddades upp till blob")
    manifest_idx = runner.index('upload_file ".manifest.json"')
    assert guard_idx < manifest_idx


@pytest.mark.tooling
def test_b195_unit_test_exists() -> None:
    test_src = (VIEWSER_LIB / "generated-blob-source.test.ts").read_text(encoding="utf-8")

    assert "selectServedRelPaths" in test_src
    assert "stale" in test_src.lower()


# --- Hostad pre-built (2026-06-12): .next i blob-uploaden + pre-built-gren ----


@pytest.mark.tooling
def test_hosted_build_uploads_root_next_without_cache_and_trace() -> None:
    """Orkestrerings-skriptets find-kommando måste inkludera rot-nivåns
    färdiga .next/ MEN pruna .next/cache + .next/trace och nästlade .next —
    exakt spegel av collectSource(includeBuiltNext)-skip-logiken. Pruna
    fortfarande node_modules m.fl."""
    runner = (VIEWSER_LIB / "hosted-build-runner.ts").read_text(encoding="utf-8")
    find_line = next(
        (line for line in runner.splitlines() if line.startswith("find . ")),
        None,
    )
    assert find_line is not None, "Orkestrerings-skriptet måste lista filer med find."
    assert "-name node_modules" in find_line
    # Rot-.next får INTE general-prunas längre (det var pre-pre-built-läget).
    assert "-o -name .next -o" not in find_line, (
        "find får inte längre pruna ALLA .next — rot-nivåns .next ska med "
        "(pre-built-vägen). Nästlade .next prunas separat."
    )
    assert "-path ./.next/cache -prune" in find_line, (
        ".next/cache (webpack-cachen, ~95 % av bytes) får aldrig laddas upp."
    )
    assert "-path ./.next/trace -prune" in find_line, (
        ".next/trace (build-telemetri) får aldrig laddas upp."
    )
    assert "-name .next ! -path ./.next" in find_line, (
        "Nästlade .next-kataloger (i undermappar) ska prunas precis som förr."
    )


@pytest.mark.tooling
def test_blob_source_filters_prebuilt_relpaths() -> None:
    """generated-blob-source måste (a) exponera pre-built-filtret som ren
    funktion, (b) köra det på served-listan styrt av includeBuiltNext, och
    (c) exponera BUILD_ID-readiness-hjälpen som sandbox-runnern grenar på."""
    source = (VIEWSER_LIB / "generated-blob-source.ts").read_text(encoding="utf-8")
    assert "export function filterPrebuiltRelPaths(" in source
    assert "export function hasPrebuiltNextRelPath(" in source
    assert 'relPaths.includes(".next/BUILD_ID")' in source
    assert "filterPrebuiltRelPaths(\n    selectServedRelPaths([...byRel.keys()], manifestRelPaths),\n    options?.includeBuiltNext === true,\n  )" in source, (
        "collectSourceFromBlob måste filtrera served-listan genom "
        "filterPrebuiltRelPaths styrt av options.includeBuiltNext."
    )


@pytest.mark.tooling
def test_sandbox_runner_takes_prebuilt_branch_from_blob() -> None:
    """Sandbox-runnern: blob-grenen ska begära .next bara när pre-built får
    användas (allowPrebuilt + flaggan), gren-beslutet ska kräva en KOMPLETT
    .next (BUILD_ID via hasPrebuiltNextRelPath), och en saknad/trasig .next
    ska ärligt falla tillbaka till fulla bygg-vägen."""
    runner_src = (VIEWSER_LIB / "vercel-sandbox-runner.ts").read_text(encoding="utf-8")
    assert "const wantPrebuilt = allowPrebuilt && prebuiltUploadEnabled();" in runner_src
    assert "includeBuiltNext: wantPrebuilt," in runner_src
    assert "hasPrebuiltNextRelPath(collected.files.map((f) => f.relPath))" in runner_src
    # Fallback-berättigande: ett blob-collect-fel i pre-built-läget (t.ex.
    # storlekstaket nått pga .next) får prova fulla vägen EN gång.
    assert "fallbackEligible: wantPrebuilt" in runner_src
