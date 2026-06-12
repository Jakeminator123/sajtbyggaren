"""Source-level locks för preview-bundle-tarballen (G2, ADR 0058).

Prod-incidenten 2026-06-12 (site-3e7d71ad): hostad preview-uppstart tog 6–7
minuter eftersom källinhämtningen listade + hämtade hundratals enskilda
blob-filer (inkl. förbyggd .next) och laddade upp dem fil-för-fil i sandboxen.
G2 paketerar det publicerade fil-setet som EN tar.gz vid byggtid
(``preview-bundles/<siteId>/<buildId>/preview-bundle.tar.gz``) och låter
preview-sandboxen skapas direkt från tarballen (source { type: "tarball" } —
samma mönster som build-kontexten).

Låsen (samma källkods-mönster som test_viewser_hosted_followup_parity.py):

1. Byggsidan: bundlen skapas av EXAKT det publicerade fil-setet
   (served-manifest), bara med komplett next-build, inom samma tak som
   blob-källans vakter, och publiceras best-effort (ett bundle-fel faller
   aldrig bygget). Pekaren bär URL:en bara när uploaden bevisligen lyckades.
2. Preview-sidan: tarball-FÖRST när bundlen finns, fil-för-fil-fallback
   annars (bakåtkompat för sajter byggda före G2) — och fallbacken/vägvalet
   loggas alltid (källväg + källinhämtningstid i den strukturerade
   preview-start-raden).
3. Vakterna förblir ärliga: storlekstak i MAX_TOTAL_BYTES-anda på BÅDE
   bygg- och preview-sidan, och den ärliga fallbacken till fulla bygg-vägen
   (allowPrebuilt=false) använder aldrig bundlen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling]

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
BUILD_RUNNER = VIEWSER / "lib" / "hosted-build-runner.ts"
SANDBOX_RUNNER = VIEWSER / "lib" / "vercel-sandbox-runner.ts"
BUNDLE_MODULE = VIEWSER / "lib" / "hosted-preview-bundle.ts"
SESSIONS = VIEWSER / "lib" / "vercel-sandbox-sessions.ts"


def _build_runner() -> str:
    return BUILD_RUNNER.read_text(encoding="utf-8")


def _sandbox_runner() -> str:
    return SANDBOX_RUNNER.read_text(encoding="utf-8")


def _bundle_module() -> str:
    return BUNDLE_MODULE.read_text(encoding="utf-8")


# --- 1. Byggsidan: bundle av exakt det publicerade fil-setet -------------------


def test_bundle_is_built_from_served_manifest_with_guards() -> None:
    runner = _build_runner()
    bundle_block = runner.split("# G2 (ADR 0058) — preview-bundle", 1)[1].split(
        "# Hostad current.json-motsvarighet", 1
    )[0]
    assert '/tmp/served-manifest.txt' in bundle_block, (
        "Bundlen måste byggas av EXAKT det publicerade fil-setet "
        "(served-manifest), inte av en egen fil-listning."
    )
    # Taken speglar generated-blob-source.ts (4000 filer / 64 MB) — samma
    # fil-set, samma tak.
    assert "MAX_FILES = 4000" in bundle_block
    assert "MAX_TOTAL_BYTES = 64 * 1024 * 1024" in bundle_block
    assert '".next/BUILD_ID" not in files' in bundle_block, (
        "Bundlen publiceras bara med komplett next-build — då kan "
        "preview-sidan lita på att bundle => pre-built."
    )
    assert "tarfile.open" in bundle_block, (
        "Tarballen skapas med python3 stdlib tarfile (filnamn med "
        "mellanslag/specialtecken hanteras utan GNU tar-flaggor)."
    )


def test_bundle_upload_is_best_effort_and_versioned() -> None:
    runner = _build_runner()
    bundle_block = runner.split("# G2 (ADR 0058) — preview-bundle", 1)[1].split(
        "# Hostad current.json-motsvarighet", 1
    )[0]
    assert (
        '"$BLOB_API/preview-bundles/$SITE_ID/$ACTIVE_BUILD_ID/preview-bundle.tar.gz"'
        in bundle_block
    ), (
        "Bundle-layouten är versions-scopad per buildId — varje bygge skriver "
        "en NY path (ingen stale-overwrite-problematik som generated/)."
    )
    assert "fail " not in bundle_block and "|| fail" not in bundle_block, (
        "Bundle-publiceringen är best-effort: ett fel får ALDRIG falla bygget "
        "(fil-för-fil-källan är redan publicerad)."
    )
    assert "VARNING — preview-bundlen kunde inte publiceras" in bundle_block, (
        "Misslyckad bundle-publicering måste loggas ärligt."
    )
    assert "preview-bundle hoppades over" in bundle_block, (
        "Hoppade bundles (size-guard/no-prebuilt-next) måste loggas med orsak."
    )


def test_current_pointer_carries_bundle_url_only_when_published() -> None:
    runner = _build_runner()
    pointer_block = runner.split("# Hostad current.json-motsvarighet", 1)[1].split(
        "# B194 — persistera run-state", 1
    )[0]
    assert 'BUNDLE_URL="$PREVIEW_BUNDLE_PUBLISHED"' in pointer_block
    assert 'if bundle_url.startswith("https://"):' in pointer_block, (
        "previewBundleUrl skrivs bara när uploaden bevisligen lyckades "
        "(annars degraderar preview-sidan ärligt till fil-för-fil)."
    )
    assert '"previewBundleUrl"' in pointer_block
    assert '"previewBundleBytes"' in pointer_block
    assert '"previewBundleFileCount"' in pointer_block
    # Ordning: bundle-sektionen FÖRE pekar-skrivningen (pekaren får aldrig
    # peka på en bundle som inte hunnit publiceras).
    bundle_idx = runner.find("# G2 (ADR 0058) — preview-bundle")
    pointer_idx = runner.find("# Hostad current.json-motsvarighet")
    manifest_idx = runner.find("hosted-build: manifest publicerat")
    assert -1 not in (bundle_idx, pointer_idx, manifest_idx)
    assert manifest_idx < bundle_idx < pointer_idx, (
        "Bundle-sektionen ska ligga EFTER manifest-publiceringen (fil-setet "
        "är då final) och FÖRE current-pekarens skrivning."
    )


# --- 2. Preview-sidan: tarball-först + fil-för-fil-fallback --------------------


def test_preview_tries_bundle_first_then_falls_back_to_blob_files() -> None:
    runner = _sandbox_runner()
    attempt = runner.split("async function createSandboxPreviewAttempt", 1)[1].split(
        "async function tryReuseSandboxPreview", 1
    )[0]
    bundle_idx = attempt.find("resolvePreviewBundleSource(request.siteId, logs)")
    blob_idx = attempt.find("collectSourceFromBlob(request.siteId")
    assert bundle_idx != -1, (
        "Blob-grenen måste prova preview-bundlen först (tarball-först)."
    )
    assert blob_idx != -1 and bundle_idx < blob_idx, (
        "Fil-för-fil-vägen är fallbacken och måste ligga EFTER bundle-försöket."
    )
    # Bundlen provas bara när pre-built-vägen får användas: den ärliga
    # fallbacken (allowPrebuilt=false) och kill-switchen tar fil-för-fil.
    gate = attempt[:bundle_idx].rsplit("if", 1)[1]
    assert "wantPrebuilt" in gate, (
        "Bundle-försöket måste vara gatat på wantPrebuilt — den ärliga "
        "fulla-vägen-fallbacken får aldrig återanvända bundlen."
    )


def test_bundle_mode_creates_sandbox_from_tarball_without_upload() -> None:
    runner = _sandbox_runner()
    attempt = runner.split("async function createSandboxPreviewAttempt", 1)[1].split(
        "async function tryReuseSandboxPreview", 1
    )[0]
    assert (
        '{ source: { type: "tarball" as const, url: bundleSource.url } }'
        in attempt
    ), (
        "Bundle-läget måste skapa sandboxen med source { type: tarball } — "
        "samma mönster som build-kontext-tarballen."
    )
    assert "if (collected) {" in attempt, (
        "mkdir/writeFiles-uploaden måste hoppas över i bundle-läget "
        "(källan extraherades redan i Sandbox.create)."
    )
    assert "sandbox !== null || bundleSource !== null" in attempt, (
        "Ett create-kast i bundle-läget (korrupt tarball) måste vara "
        "fallback-berättigat — fil-för-fil-vägen kan lyckas."
    )


def test_source_path_and_timing_are_logged_in_both_paths() -> None:
    runner = _sandbox_runner()
    assert "source: result.source ?? null," in runner, (
        "Den strukturerade preview-start-raden måste bära vilken källväg som "
        "togs (preview-bundle | blob-files | disk)."
    )
    attempt = runner.split("async function createSandboxPreviewAttempt", 1)[1].split(
        "async function tryReuseSandboxPreview", 1
    )[0]
    assert 'sourceKind = "preview-bundle";' in attempt
    assert 'sourceKind = "blob-files";' in attempt
    assert attempt.count("sourceMs = Date.now() - tSource;") >= 3, (
        "Källinhämtningstiden måste mätas i disk-, bundle- OCH "
        "fil-för-fil-vägen så vinsten är verifierbar i loggarna."
    )
    assert "sourceMs, createMs, uploadMs" in attempt, (
        "sourceMs ska följa med i timings-blocket."
    )


# --- 3. Vakter + nyckel-paritet -------------------------------------------------


def test_bundle_reader_is_read_only_with_size_guard() -> None:
    module = _bundle_module()
    # Skriv-API:er och sandbox-SDK-import är förbjudna i modulen
    # (anrops-/importformer — JSDoc-prosa som FÖRKLARAR mönstret är ok).
    for forbidden in (
        "kvSetJson(",
        ".put(",
        'from "@vercel/sandbox"',
        "writeFiles(",
    ):
        assert forbidden not in module, (
            f"hosted-preview-bundle.ts får inte innehålla {forbidden!r} — "
            "modulen läser bara (KV GET + HEAD)."
        )
    assert (
        "export const PREVIEW_BUNDLE_MAX_COMPRESSED_BYTES = 64 * 1024 * 1024;"
        in module
    ), (
        "Storlekstaket på tarballen ska spegla MAX_TOTAL_BYTES-andan (64 MB)."
    )
    assert "compressedBytes > PREVIEW_BUNDLE_MAX_COMPRESSED_BYTES" in module
    assert 'method: "HEAD"' in module, (
        "Bundle-URL:en ska HEAD-probas före Sandbox.create så en raderad/"
        "trasig blob ger fil-för-fil-fallback i stället för ett dyrt create-fel."
    )
    assert module.count("fil-för-fil-fallback") >= 3, (
        "Varje fallback-orsak (saknad pekare, död blob, för stor tarball) "
        "måste loggas tydligt."
    )


def test_current_pointer_key_literal_parity() -> None:
    """Bundle-läsaren duplicerar medvetet KV-nyckel-literalen (cykel-skäl,
    se modul-JSDoc) — literalen måste vara EXAKT densamma som sessions-modulens
    hostedSiteCurrentKey och orkestrerings-skriptets skrivning."""
    literal = "`viewser:site:${siteId}:current`"
    assert literal in _bundle_module()
    assert literal in SESSIONS.read_text(encoding="utf-8")
    assert '"viewser:site:" + os.environ["SITE_ID"] + ":current"' in _build_runner()
