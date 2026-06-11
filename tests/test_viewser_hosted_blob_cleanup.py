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
