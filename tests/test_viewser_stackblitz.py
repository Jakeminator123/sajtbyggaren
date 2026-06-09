"""Viewser StackBlitz preview file filtering and package.json patching."""

from __future__ import annotations

import re

import pytest

from tests.support.viewser import VIEWSER_DIR


@pytest.mark.tooling
def test_stackblitz_files_filter_dotenv_files_from_preview_upload() -> None:
    """B54 + B58: ``readRunFilesForStackblitz`` reads every file under the
    run's ``generated-files/`` snapshot (or ``.generated/<siteId>/`` fallback)
    and bundles it for the StackBlitz preview upload. Builder already
    blocks ``.env*`` from landing in those snapshots today (B4/B5 enforce
    a case-insensitive ignore in ``copy_starter``), but the upload layer
    must have its own defensive filter so a future starter, manual
    operator edit, or drift in the builder cannot leak a
    ``.env``/``.env.local``/``.env.production`` into a public preview.

    B58 follow-up (reviewer 2026-05-14): the filter must NOT block
    ``.env.example``. That file is a public placeholder (explicit
    ``!.env.example`` in ``.gitignore``) documenting which env variables
    the generated site expects. Operators in the preview need it to wire
    up live env-vars. Reviewer flagged the original B54 filter as a
    low-risk functional regression (20% / 3/10).

    Lock both invariants:
    1. A case-insensitive ``.env``-prefix check exists in the filter.
    2. ``.env.example`` is explicitly allowlisted so it passes through.
    """
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert re.search(
        r'\.startsWith\(["\']\.env["\']\)',
        text,
    ), (
        "stackblitz-files.ts saknar ``.env*``-filter i upload-loopen. B54 "
        "kräver att en ``.env``/``.env.local``/``.ENV`` aldrig kan följa "
        "med upp till StackBlitz-preview, även om Builder-blockaden "
        "tappar effekt eller om en operatör manuellt lägger en .env i en "
        "starter för lokal test."
    )
    assert re.search(
        r"\.toLowerCase\(\)",
        text,
    ), (
        "stackblitz-files.ts ``.env*``-filtret måste vara case-insensitivt "
        "(toLowerCase). Mirror B4:s case-variant-täckning (``.ENV``, "
        "``.Env.Local`` etc.)."
    )
    assert re.search(
        r"\.env\.example",
        text,
    ), (
        "stackblitz-files.ts saknar allowlist-undantag för ``.env.example``. "
        "B58 kräver att den publika placeholder-filen följer med upp till "
        "StackBlitz-preview så operatörer ser vilka env-vars sajten "
        "förväntar sig. Endast ``.env.example`` (lower-case) får passera "
        "genom det annars heltäckande ``.env*``-filtret."
    )


@pytest.mark.tooling
def test_stackblitz_files_allow_env_example_through_filter() -> None:
    """B58: explicit lock that ``.env.example`` is not filtered out by the
    ``.env*`` guard. Uses source-text inspection (same pattern as the
    other stackblitz-files lock tests) because the TS function is
    internal and not directly callable from Python.

    The expected pattern: a check that returns ``false`` (i.e. NOT a
    dotenv file to filter) only when the original basename is exactly
    ``.env.example``. Case variants are treated as real ``.env*`` files.
    """
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert re.search(
        r'basename\s*===\s*["\']\.env\.example["\']',
        text,
    ), (
        "stackblitz-files.ts måste ha en explicit allowlist-check för "
        'exakt ``.env.example`` (typ ``if (basename === ".env.example") return false;``) '
        "innan det generella ``.env*``-filtret slår till. Annars blockas den "
        "publika placeholder-filen från StackBlitz-preview (B58), eller så "
        "slipper case-varianter som ``.ENV.EXAMPLE`` igenom."
    )


@pytest.mark.tooling
def test_stackblitz_files_keeps_package_lock_in_preview_upload() -> None:
    """StackBlitz must receive package-lock.json to avoid dependency drift."""
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert "FILES_TO_SKIP" not in text, (
        "stackblitz-files.ts får inte ha en generell skiplista som filtrerar "
        "bort package-lock.json från StackBlitz-payloaden."
    )
    assert re.search(
        r"stats\.size\s*>\s*MAX_FILE_BYTES\s*&&\s*relPath\s*!==\s*NPM_LOCKFILE",
        text,
    ), (
        "package-lock.json är ofta större än MAX_FILE_BYTES och måste därför "
        "undantas från per-filgränsen. Den ska fortfarande räknas mot "
        "MAX_TOTAL_BYTES så payloaden förblir begränsad."
    )


@pytest.mark.tooling
def test_stackblitz_files_total_size_uses_patched_bytes_and_skips_oversized_file() -> None:
    """Total payload cap must use the exact bytes we store.

    package.json patching can change file size, so MAX_TOTAL_BYTES has to use
    Buffer.byteLength(patchedContent). If one file does not fit, the loop
    should continue so later smaller files can still be included.
    """
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert 'const patchedBytes = Buffer.byteLength(patchedContent, "utf-8");' in text, (
        "MAX_TOTAL_BYTES-kontrollen måste baseras på patched bytes, inte "
        "original stats.size, annars kan payloaden bli större än taket."
    )
    assert re.search(
        r"if\s*\(\s*totalBytes\s*\+\s*patchedBytes\s*>\s*MAX_TOTAL_BYTES\s*\)\s*continue;",
        text,
    ), (
        "När en fil inte får plats under MAX_TOTAL_BYTES ska loopen använda "
        "`continue` så senare mindre filer fortfarande kan inkluderas."
    )


@pytest.mark.tooling
def test_stackblitz_files_patches_package_json_for_webpack() -> None:
    """B56: StackBlitz-preview ska patcha package.json i-memory så Next 16
    kör med Webpack i WebContainer.
    """
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert "patchPackageJsonForStackblitz" in text, (
        "stackblitz-files.ts måste innehålla en package.json-patch-funktion för StackBlitz-preview."
    )
    assert "scripts.dev = ensureWebpackFlag(currentDev)" in text, (
        "stackblitz-files.ts måste patcha scripts.dev via ensureWebpackFlag."
    )
    assert "scripts.build = ensureWebpackFlag(currentBuild)" in text, (
        "stackblitz-files.ts måste patcha scripts.build via ensureWebpackFlag "
        "eftersom StackBlitz startCommand kör `npm run build` före `npm run start`."
    )
    assert 'scripts.start = "next start"' in text, (
        "stackblitz-files.ts måste säkra scripts.start-fallback till "
        "`next start` när start-script saknas."
    )
    assert 'stackblitz.startCommand = "npm run build && npm run start"' in text, (
        "stackblitz-files.ts måste sätta stackblitz.startCommand till "
        "`npm run build && npm run start` så StackBlitz undviker Next dev-"
        "runtimebuggen i WebContainer och kör samma gröna production-build."
    )
    assert re.search(
        r'relPath\s*===\s*["\']package\.json["\']\s*\?\s*patchPackageJsonForStackblitz\(content\)\s*:\s*content',
        text,
    ), (
        "package.json-patchen måste ske inline i fil-map-loopen (bytes till "
        "StackBlitz), inte via diskmutation."
    )


@pytest.mark.tooling
def test_stackblitz_files_does_not_duplicate_webpack_flag() -> None:
    """Idempotens: redan patchat kommando ska inte få dubbel --webpack."""
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert 'if (trimmed.includes("--webpack")) return trimmed;' in text, (
        "ensureWebpackFlag måste kortsluta när --webpack redan finns."
    )
    assert "return `${trimmed} --webpack`;" in text, (
        "ensureWebpackFlag måste append:a --webpack när det saknas."
    )
    assert "dev|build" in text, (
        "ensureWebpackFlag måste omfatta både `next dev` och `next build`; "
        "StackBlitz WebContainer saknar native Turbopack-bindings för build."
    )


@pytest.mark.tooling
def test_stackblitz_files_inject_global_error_override() -> None:
    """Next 16 default ``/_global-error`` prerender kraschar i StackBlitz/
    WebContainer med ``Expected workStore to be initialized``. Lokal build
    är grön; det är en känd Next 16 + WebContainer WASM-runtime-bugg.

    StackBlitz-payloaden måste därför injicera en egen
    ``app/global-error.tsx`` så Next använder vår komponent istället för
    sin defaulta UI och slipper den trasiga prerender-pathen. Override
    sker bara i in-memory file-mapen; aldrig till disk, aldrig till
    builder/starter/snapshot.
    """
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert 'GLOBAL_ERROR_OVERRIDE_PATH = "app/global-error.tsx"' in text, (
        "stackblitz-files.ts saknar konstant för global-error override-path."
    )
    assert "GLOBAL_ERROR_OVERRIDE_CONTENT" in text, (
        "stackblitz-files.ts saknar innehåll för global-error override."
    )
    assert '"use client"' in text, "global-error.tsx-overriden måste vara en client component."
    assert "if (!(GLOBAL_ERROR_OVERRIDE_PATH in projectFiles))" in text, (
        "stackblitz-files.ts måste bara injicera overriden om generated "
        "site inte redan har en egen app/global-error.tsx."
    )


# NOTE: Tidigare lockade vi in att Viewser INTE skulle sätta
# Cross-Origin-Embedder-Policy (commit 98e8364, motivering: "Chrome
# blockerar då StackBlitz-iframe:n"). Det stämde för require-corp men
# missade att credentialless är specifikt designad för att tillåta
# embedding av tredjepartsiframes som inte själva skickar CORP. När
# next.config.ts var tom failade StackBlitz-embeddet med "Unable to
# run Embedded Project — Looks like this project is being embedded
# without proper isolation headers" eftersom WebContainer kräver
# SharedArrayBuffer som bara finns i cross-origin isolated dokument.
# Den gamla locken togs bort i samma commit som B123 stängdes; den
# nya specifika locken (COEP MÅSTE finnas och MÅSTE vara
# credentialless) lever i tests/test_viewser_isolation_headers.py.


@pytest.mark.tooling
def test_stackblitz_files_does_not_write_back_package_json_to_disk() -> None:
    """B56-scope: patchen får inte skriva starter/run-snapshot till disk."""
    text = (VIEWSER_DIR / "lib" / "stackblitz-files.ts").read_text(encoding="utf-8")
    assert "writeFile(" not in text and ".writeFile(" not in text, (
        "stackblitz-files.ts får inte skriva package.json till disk i B56; "
        "endast in-memory patch innan embedProject."
    )


@pytest.mark.tooling
def test_viewer_panel_skips_local_preview_in_strict_stackblitz_mode() -> None:
    """Reviewer-fynd post-PR #101: configens namn (``stackblitz``) var
    inte sann end-to-end — flödet provade alltid
    ``POST /api/preview/<siteId>`` först, oavsett mode. Om sajten råkade
    ha en lokal ``.next/`` hamnade operatören på lokal preview ändå
    (designglapp, inte krasch).

    Fix: i strikt ``stackblitz``-mode hoppa Steg 1 (lokal preview-
    server) helt — gå direkt till Steg 2 (StackBlitz Steg 2 / files-
    fetch). ``auto``-mode behåller "try local first, fall back to
    StackBlitz"-beteendet eftersom det är vad ``auto`` betyder.
    ``local-next``-mode visar pedagogiskt fel vid lokal miss (oförändrat
    från PR #97).

    Tre lås:
      1. ``IS_STACKBLITZ_MODE``-konstant exporterad från samma plats
         som ``IS_LOCAL_NEXT_MODE``.
      2. Steg 1 (``if (siteId)``-blocket med
         ``await fetch("/api/preview/${siteId}")``) gated med
         ``!IS_STACKBLITZ_MODE``.
      3. Den interna ``IS_LOCAL_NEXT_MODE``-pedagogiska gren strukturen
         INTE förändrad (404-guards + cancelled-guards fortsatt
         source-lockade av separata tester).
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    # Lock 1: konstanten finns och härleds ur descriptorn (Bite C, ee68add).
    # ``kind === "stackblitz"`` är 1:1 med rawMode här; descriptorn mappar
    # ``stackblitz`` rakt igenom medan ``auto`` ger ``kind === "local"``.
    pattern_const = re.compile(
        r'const\s+IS_STACKBLITZ_MODE\s*=\s*PREVIEW_RUNTIME\.kind\s*===\s*["\']stackblitz["\']',
        re.MULTILINE,
    )
    assert pattern_const.search(text), (
        "viewer-panel.tsx saknar ``const IS_STACKBLITZ_MODE = "
        "PREVIEW_RUNTIME.kind === 'stackblitz'``. Krävs för att gate:a "
        "Steg 1 (lokal preview-server) i strikt stackblitz-mode."
    )

    # Lock 2: Steg 1-blocket gated på !IS_STACKBLITZ_MODE
    pattern_gate = re.compile(
        r"if\s*\(\s*!\s*IS_STACKBLITZ_MODE\s*&&\s*siteId\s*\)\s*\{",
        re.MULTILINE,
    )
    assert pattern_gate.search(text), (
        "viewer-panel.tsx: Steg 1 (lokal preview-server) måste vara "
        "gated på ``if (!IS_STACKBLITZ_MODE && siteId)`` så strikt "
        "stackblitz-mode hoppar lokal-preview helt och går direkt till "
        "Steg 2. Annars är configens namn (``stackblitz``) inte "
        "auktoritativt."
    )


@pytest.mark.tooling
def test_viewer_panel_does_not_eagerly_import_stackblitz_sdk() -> None:
    """Bundle-bloat-fix (ADR 0033): ``viewer-panel.tsx`` importeras statiskt
    av studio-sidan, så allt som ligger i dess EAGER-analyserade modulgraf
    pre-scriptas i den serverade ``studio.html`` (verifierat empiriskt: SDK-
    vendor-chunken låg som ``<script async>`` vid vercel-sandbox-load trots att
    SDK:n aldrig kördes).

    VIKTIGT — ett top-level ``next/dynamic(() => import("x"))`` RÄCKER INTE:
    Next/Turbopack statiskt-analyserar modulnivå-``dynamic()`` och pre-scriptar
    ``x``:s chunk-graf (inkl. den nästlade ``@stackblitz/sdk``-chunken). Därför
    måste ``viewer-panel.tsx`` ladda StackblitzPreview via en RUNTIME
    ``import()`` i en effekt som gate:as på ``useStackblitz`` — INTE via
    top-level ``dynamic()``.

    Lås:
      1. ingen ``import("@stackblitz/sdk")`` / ``from "@stackblitz/sdk"``.
      2. ingen top-level ``next/dynamic`` (``from "next/dynamic"`` förbjudet) —
         det var just det som pre-scriptade SDK-chunken.
      3. StackblitzPreview laddas via en runtime ``import(".../stackblitz-
         preview")``.
      4. handoff:en gate:ad på descriptorns ``canFallbackToStackblitz``
         (``CAN_FALL_BACK_TO_STACKBLITZ``).
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    # 1. Förbjud det som skapar en modulgraf-kant till SDK:n: en statisk
    # ``from "@stackblitz/sdk"`` ELLER en dynamisk ``import("@stackblitz/sdk")``.
    # (En ren omnämning i en kommentar skapar ingen kant och är OK.)
    assert not re.search(r'import\(\s*["\']@stackblitz/sdk["\']', text), (
        "viewer-panel.tsx får INTE innehålla ``import(\"@stackblitz/sdk\")``. "
        "Hela StackBlitz-vägen ska ligga i den lazy-laddade "
        "``stackblitz-preview.tsx``."
    )
    assert not re.search(r'from\s+["\']@stackblitz/sdk["\']', text), (
        "viewer-panel.tsx får INTE statiskt importera ``@stackblitz/sdk``."
    )
    # 2. Inget top-level next/dynamic — det pre-scriptar SDK-chunken i
    # studio.html (verifierat). Runtime ``import()`` används i stället.
    # Vi förbjuder IMPORT-satsen (``import ... from "next/dynamic"``), inte
    # prosa-omnämnanden i kommentarer (som förklarar varför vi undviker den).
    # Förbjud IMPORT-satsen (``import ... from "next/dynamic"``), inte
    # prosa-omnämnanden i kommentarer (som förklarar varför vi undviker den).
    assert not re.search(r'import\s+\w+\s+from\s+["\']next/dynamic["\']', text), (
        "viewer-panel.tsx får INTE importera ``next/dynamic`` för StackblitzPreview. "
        "Next/Turbopack pre-scriptar en modulnivå-``dynamic()``-komponents "
        "chunk-graf (inkl. @stackblitz/sdk) som <script async> i studio.html. "
        "Ladda i stället via en runtime ``import()`` gate:ad på useStackblitz."
    )
    # 3. StackblitzPreview laddas via en runtime import() (referensen finns,
    # men inte bakom dynamic()).
    assert re.search(
        r"import\(\s*[\"'][^\"']*stackblitz-preview[\"']",
        text,
    ), (
        "viewer-panel.tsx måste ladda StackblitzPreview via en runtime "
        "``import(\".../stackblitz-preview\")`` (gate:ad på useStackblitz)."
    )
    # 4. Handoff gate:ad på descriptorns canFallbackToStackblitz.
    assert "CAN_FALL_BACK_TO_STACKBLITZ" in text and "canFallbackToStackblitz" in text, (
        "viewer-panel.tsx måste gate:a StackBlitz-handoffen på descriptorns "
        "``canFallbackToStackblitz`` (materialiserad som "
        "``CAN_FALL_BACK_TO_STACKBLITZ``)."
    )


@pytest.mark.tooling
def test_stackblitz_preview_owns_the_sdk_dynamic_import() -> None:
    """Bundle-bloat-fix (ADR 0033): den lazy-laddade ``stackblitz-preview.tsx``
    är ENDA stället i preview-canvasen som når ``@stackblitz/sdk``. Den når
    SDK:n via ``await import`` (embed + openProject) så att även själva SDK-
    chunken är lazy INUTI den redan lazy komponenten.

    Lås:
      1. ``stackblitz-preview.tsx`` innehåller ``await import("@stackblitz/sdk")``.
      2. Den är en klient-komponent (``"use client"``).
      3. Den exporterar ``StackblitzPreview`` (det namn ViewerPanel
         dynamiskt importerar).
    """
    text = (VIEWSER_DIR / "components" / "stackblitz-preview.tsx").read_text(
        encoding="utf-8"
    )
    assert 'await import("@stackblitz/sdk")' in text, (
        "stackblitz-preview.tsx måste nå SDK:n via ``await "
        "import(\"@stackblitz/sdk\")`` (lazy) — både för embed och openProject."
    )
    assert '"use client"' in text, (
        "stackblitz-preview.tsx måste vara en client component."
    )
    assert "export function StackblitzPreview" in text, (
        "stackblitz-preview.tsx måste exportera ``StackblitzPreview`` — namnet "
        "ViewerPanel dynamiskt importerar via next/dynamic."
    )


@pytest.mark.tooling
def test_stackblitz_preview_sets_cross_origin_isolated_on_stackblitz_embed() -> None:
    """B125/B145: StackBlitz-embedden behöver Permissions Policy-delegering
    av cross-origin-isolation för att ``window.crossOriginIsolated`` ska
    bli ``true`` inuti iframen — annars kan WebContainern inte boota
    SharedArrayBuffer och visar "Unable to run Embedded Project — Looks
    like this project is being embedded without proper isolation headers"
    trots korrekt levererade COEP/COOP-headers på host:en.

    StackBlitz SDK exponerar detta via ``crossOriginIsolated: true``-
    flaggan i ``EmbedOptions`` (dokumenterad i
    ``@stackblitz/sdk/types/interfaces.d.ts``). SDK:n applicerar den
    genom ``setFrameAllowList`` som lägger till ``cross-origin-isolated``
    i iframens ``allow``-attribut (Permissions Policy-delegering).

    Båda lager behövs:
      1. ``credentialless``-attributet på iframen (löser COEP-kravet —
         redan source-lockat via test_viewer_panel_keeps_containerref...).
      2. ``crossOriginIsolated: true`` i embedOptions (löser Permissions
         Policy-delegeringen — denna lock).

    Tas raden bort fallerar embedden tyst inuti StackBlitz med kryptiskt
    "Unable to run Embedded Project" och operatören har ingen ledtråd
    om att host-headers faktiskt är korrekta.

    Bundle-bloat-fix (ADR 0033): embedden bor numera i den lazy-laddade
    ``stackblitz-preview.tsx`` (inte ``viewer-panel.tsx``) så
    ``@stackblitz/sdk`` inte prefetchas i ViewerPanel:s eager-chunk.
    """
    text = (VIEWSER_DIR / "components" / "stackblitz-preview.tsx").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"crossOriginIsolated\s*:\s*true",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "stackblitz-preview.tsx: ``crossOriginIsolated: true`` saknas i "
        "``sdk.embedProject``-options. Krävs för Permissions Policy-"
        "delegering till stackblitz.com — utan den boota:r WebContainern "
        "inte och visar 'Unable to run Embedded Project'. Se "
        "EmbedOptions i @stackblitz/sdk/types/interfaces.d.ts och "
        "https://blog.stackblitz.com/posts/cross-browser-with-coop-coep/."
    )


@pytest.mark.tooling
def test_stackblitz_preview_surfaces_stackblitz_sdk_error_details() -> None:
    """StackBlitz SDK failures must show actionable details, not "unknown".

    Bundle-bloat-fix (ADR 0033): fel-formateringen + error-pre:t bor numera i
    ``stackblitz-preview.tsx`` (lazy via next/dynamic), inte ``viewer-panel.tsx``.
    """
    text = (VIEWSER_DIR / "components" / "stackblitz-preview.tsx").read_text(
        encoding="utf-8"
    )
    assert "formatViewerError" in text, (
        "stackblitz-preview.tsx måste formatera SDK-fel centralt så catch-grenen "
        "inte faller tillbaka till ett opakt 'Okänt viewer-fel'."
    )
    for expected in ("name:", "message:", "stack:", "slice(0, 20)"):
        assert expected in text, (
            "Viewer-felet måste visa Error.name, Error.message och de första "
            f"20 stackraderna. Saknar {expected!r}."
        )
    assert "non-Error rejection" in text, (
        "StackBlitz SDK kan rejecta med icke-Error-värden; de måste också renderas läsbart."
    )
    assert "whitespace-pre-wrap" in text and "<pre" in text, (
        "Viewer-feldetaljer måste renderas i ett pre-block så stackrader och radbrytningar bevaras."
    )
