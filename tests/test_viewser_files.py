"""Smoke tests for the Viewser MVP file layout and scope discipline."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWSER_DIR = REPO_ROOT / "apps" / "viewser"
NAMING_PATH = REPO_ROOT / "governance" / "policies" / "naming-dictionary.v1.json"


def _is_tracked_in_git(path: Path) -> bool:
    """Return True iff ``path`` is tracked by git.

    Uses ``git ls-files`` which returns the path if it is tracked and an
    empty string otherwise. Gitignored files that exist on disk are not
    tracked and therefore return False. This lets a developer keep a
    local ``.env.local`` without breaking the "not committed" guard.
    """
    rel = path.relative_to(REPO_ROOT).as_posix()
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", rel],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


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
        # Prompt-till-sajt MVP v1: free-prompt -> Project Input -> build.
        "app/api/prompt/route.ts",
        "app/api/discovery-options/route.ts",
        "components/viewer-panel.tsx",
        "components/token-meter.tsx",
        "components/project-input-picker.tsx",
        "components/run-history.tsx",
        # Builder UX MVP: 5-section pedagogical render of build/quality/
        # repair/codegen/models with defensive fallbacks for older runs.
        "components/run-details-panel.tsx",
        # Prompt-till-sajt MVP v1: prompt textarea + status panel that
        # wires through /api/prompt to runBuild.
        "components/prompt-builder.tsx",
        "components/discovery-wizard/discovery-options.ts",
        "lib/openai.ts",
        "lib/build-runner.ts",
        "lib/localhost-guard.ts",
        "lib/project-inputs.ts",
        "lib/prompt-runner.ts",
        "lib/runs.ts",
        "lib/stackblitz-files.ts",
        ".env.example",
    ]
    missing = [path for path in expected if not (VIEWSER_DIR / path).exists()]
    assert not missing, f"Missing viewser files: {missing}"


@pytest.mark.tooling
def test_discovery_options_route_reads_taxonomy_and_omits_starter_id() -> None:
    text = (VIEWSER_DIR / "app" / "api" / "discovery-options" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "discovery-taxonomy.v1.json" in text, (
        "Discovery-options-routen måste läsa Discovery Taxonomy server-side."
    )
    assert "scaffold-contract.v1.json" in text, (
        "Discovery-options-routen måste slå upp targetScaffoldLabel från "
        "scaffold-kontraktet istället för att hårdkoda UI-labels."
    )
    assert "expectedStarterId" not in text and "starterId" not in text, (
        "Discovery-options-routen får inte exponera starterId/expectedStarterId "
        "till frontend."
    )
    for field in (
        "id",
        "label",
        "contentBranch",
        "supportStatus",
        "defaultVariantId",
        "targetScaffoldLabel",
        "fallbackLabel",
    ):
        assert field in text, f"Discovery-options-routen saknar fältet {field!r}."


@pytest.mark.tooling
def test_discovery_wizard_uses_governance_options_with_ts_cache_fallback() -> None:
    wizard = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    site_type = (
        VIEWSER_DIR
        / "components"
        / "discovery-wizard"
        / "steps"
        / "site-type-step.tsx"
    ).read_text(encoding="utf-8")
    constants = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-constants.ts"
    ).read_text(encoding="utf-8")

    assert 'fetch("/api/discovery-options"' in wizard, (
        "DiscoveryWizard måste hämta kategori-options från governance-routen "
        "när overlayen öppnas."
    )
    assert "fallbackDiscoveryOptions" in wizard, (
        "DiscoveryWizard behöver en lokal UI-cache fallback så overlayen inte "
        "blockas av ett transient route-fel."
    )
    assert "source === \"governance\"" in site_type, (
        "SiteTypeStep ska kunna visa att listan följer Discovery Taxonomy."
    )
    assert "Backendens resolver avgör slutlig scaffold" in site_type, (
        "SiteTypeStep ska göra fallback/planned-status begriplig utan att "
        "frontend tar scaffold-beslutet."
    )
    assert "Discovery Taxonomy is the canonical" in constants, (
        "wizard-constants.ts måste dokumentera att TS-listan bara är UI-cache."
    )


@pytest.mark.tooling
def test_discovery_payload_blocks_unknown_categories_and_preserves_schema_version() -> None:
    payload = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-payload.ts"
    ).read_text(encoding="utf-8")

    assert "schemaVersion: 1" in payload, (
        "Discovery payload måste behålla schemaVersion=1."
    )
    assert "validateDiscoveryCategoryIds" in payload, (
        "buildDiscoveryPayload måste blocka category ids som saknas i "
        "governance-options."
    )
    assert "Okänd kategori" in payload, (
        "Okända category ids ska ge tydligt klientfel före /api/prompt."
    )
    assert "resolveScaffoldHintFromOptions" in payload, (
        "buildDiscoveryPayload ska härleda scaffoldHint från category-options "
        "så ecommerce inte skickar local-service-business som motsägande hint."
    )
    assert '"starterId"' not in payload, (
        "Frontendens discovery payload får inte sätta starterId."
    )


@pytest.mark.tooling
def test_prompt_route_rejects_discovery_starter_id_and_followup_discovery() -> None:
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )

    assert "Discovery-payload får inte sätta starterId" in text, (
        "/api/prompt måste avvisa starterId i discovery.answers."
    )
    assert "Discovery-wizarden används bara i init-läge" in text, (
        "Followup mode får inte acceptera discovery-payload."
    )


@pytest.mark.tooling
def test_viewser_legacy_dossier_picker_removed() -> None:
    """Operator-mentalmodellen kräver Project Input - inte Dossier - picker."""
    assert not (VIEWSER_DIR / "components" / "dossier-picker.tsx").exists()
    assert not (VIEWSER_DIR / "lib" / "dossiers.ts").exists()


@pytest.mark.tooling
def test_viewser_env_file_is_not_committed() -> None:
    """B57: ``.gitignore`` says ``.env.*`` (allt), undantag ``.env.example``.
    Tidigare guard (B55) kollade bara två hårdkodade filer
    (``.env`` + ``.env.local``) vilket lämnade en lucka för
    ``.env.production``, ``.env.staging``, ``.env.development`` eller
    en framtida variant som råkar bli ``git add``-ad. Reviewer-fyndet
    (2026-05-14) flaggade detta som mellanrisk: 35% sannolikhet, 8/10
    impact (secret leakage).

    B57-guarden glob-listar **alla** trackade filer som matchar
    ``apps/viewser/.env*`` via ``git ls-files`` och verifierar att den
    enda tillåtna är ``apps/viewser/.env.example`` (publik placeholder,
    explicit ``!.env.example`` i ``.gitignore``). En framtida
    ``.env.production`` som råkar trackas failar testet med tydlig
    remediation.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "apps/viewser/.env*"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()}")
    tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    allowed = {"apps/viewser/.env.example"}
    unexpected = tracked - allowed
    assert not unexpected, (
        f"Otrackade env-filer hittade i git: {sorted(unexpected)!r}. "
        ".env*-filer (utom .env.example) får aldrig committas. "
        "Kör `git rm --cached <fil>` och säkerställ att .gitignore "
        "blockar dem. Endast .env.example är tillåten i index "
        "(publik placeholder, explicit !.env.example i .gitignore)."
    )


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
        "app/api/prompt/route.ts",
    ]
    for route in routes:
        text = (VIEWSER_DIR / route).read_text(encoding="utf-8")
        assert "assertLocalhost" in text, f"{route} saknar localhost-guard"


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
        r'\.toLowerCase\(\)',
        text,
    ), (
        "stackblitz-files.ts ``.env*``-filtret måste vara case-insensitivt "
        "(toLowerCase). Mirror B4:s case-variant-täckning (``.ENV``, "
        "``.Env.Local`` etc.)."
    )
    assert re.search(
        r'\.env\.example',
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
        r'stats\.size\s*>\s*MAX_FILE_BYTES\s*&&\s*relPath\s*!==\s*NPM_LOCKFILE',
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
        "stackblitz-files.ts måste innehålla en package.json-patch-funktion "
        "för StackBlitz-preview."
    )
    assert 'scripts.dev = ensureWebpackFlag(currentDev)' in text, (
        "stackblitz-files.ts måste patcha scripts.dev via ensureWebpackFlag."
    )
    assert 'scripts.build = ensureWebpackFlag(currentBuild)' in text, (
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
    assert '"use client"' in text, (
        "global-error.tsx-overriden måste vara en client component."
    )
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
def test_build_runner_whitelists_dossier_path_overrides() -> None:
    """Prompt-till-sajt MVP v1 låter API-routen `/api/prompt` skicka in en
    absolut dossier-path direkt till `runBuild`. Det är medvetet, men en
    crafted payload får ALDRIG kunna peka build_site.py mot en godtycklig
    fil utanför `examples/` eller `data/prompt-inputs/`. Lås whitelist-
    funktionen så en framtida refactor inte tar bort guarden."""
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    assert "ALLOWED_DOSSIER_ROOTS" in text, (
        "build-runner.ts saknar ALLOWED_DOSSIER_ROOTS-whitelist för "
        "dossier-path overrides från prompt-flödet."
    )
    assert "examples" in text and "prompt-inputs" in text, (
        "build-runner.ts whitelisten måste täcka både examples/ och "
        "data/prompt-inputs/ - de två rötter där en Project Input får ligga."
    )
    assert "assertDossierPathAllowed" in text, (
        "build-runner.ts saknar assertDossierPathAllowed-anrop som "
        "validerar override-paths innan spawn av build_site.py."
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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Lock 1: konstanten finns och har rätt definition
    pattern_const = re.compile(
        r'const\s+IS_STACKBLITZ_MODE\s*=\s*VIEWSER_PREVIEW_MODE\s*===\s*["\']stackblitz["\']',
        re.MULTILINE,
    )
    assert pattern_const.search(text), (
        "viewer-panel.tsx saknar ``const IS_STACKBLITZ_MODE = "
        "VIEWSER_PREVIEW_MODE === 'stackblitz'``. Krävs för att gate:a "
        "Steg 1 (lokal preview-server) i strikt stackblitz-mode."
    )

    # Lock 2: Steg 1-blocket gated på !IS_STACKBLITZ_MODE
    pattern_gate = re.compile(
        r'if\s*\(\s*!\s*IS_STACKBLITZ_MODE\s*&&\s*siteId\s*\)\s*\{',
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
def test_viewer_panel_progress_card_hint_is_mode_aware() -> None:
    """Reviewer-fynd post-PR #101: BuildProgressCard:s preview-steg
    visade fortfarande ``"Förbereder StackBlitz-iframen."`` även i
    ``local-next``-mode där flödet faktiskt startar en lokal
    ``next start``-server. Felaktig mental modell för operatören.

    Fix: ``PREVIEW_PREP_HINT``-konstant väljer text baserat på
    ``IS_LOCAL_NEXT_MODE`` så hint:en matchar faktisk preview-väg.
    BUILD_STEPS-listan refererar konstanten istället för
    hårdkodad sträng.

    Två lås:
      1. ``PREVIEW_PREP_HINT``-konstant finns med mode-conditional.
      2. BUILD_STEPS preview-steg använder ``hint: PREVIEW_PREP_HINT``
         istället för en hårdkodad sträng.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Lock 1: konstanten finns med mode-conditional
    pattern_const = re.compile(
        r"const\s+PREVIEW_PREP_HINT\s*=\s*IS_LOCAL_NEXT_MODE\s*\?",
        re.MULTILINE,
    )
    assert pattern_const.search(text), (
        "viewer-panel.tsx saknar ``const PREVIEW_PREP_HINT = "
        "IS_LOCAL_NEXT_MODE ? ... : ...``. Krävs för att "
        "BuildProgressCard:s preview-steg ska visa rätt copy per mode."
    )

    # Lock 2: BUILD_STEPS refererar konstanten istället för hårdkodad sträng
    pattern_usage = re.compile(
        r'id:\s*["\']preview["\'][\s\S]{0,200}?hint:\s*PREVIEW_PREP_HINT',
        re.MULTILINE,
    )
    assert pattern_usage.search(text), (
        "viewer-panel.tsx: BUILD_STEPS preview-steget måste använda "
        "``hint: PREVIEW_PREP_HINT`` så texten är mode-aware. "
        "Hårdkodad ``\"Förbereder StackBlitz-iframen.\"`` gav fel "
        "mental modell i local-next-mode (reviewer-fynd post-PR #101)."
    )

    # Negativt: den hårdkodade strängen får inte återinföras i
    # BUILD_STEPS preview-stegets hint-fält.
    pattern_forbidden = re.compile(
        r'id:\s*["\']preview["\'][\s\S]{0,200}?hint:\s*["\']Förbereder StackBlitz',
        re.MULTILINE,
    )
    assert not pattern_forbidden.search(text), (
        "viewer-panel.tsx: BUILD_STEPS preview-steget får inte "
        "hårdkoda ``hint: \"Förbereder StackBlitz-iframen.\"`` igen. "
        "Använd PREVIEW_PREP_HINT-konstanten så local-next-mode får "
        "korrekt text."
    )


@pytest.mark.tooling
def test_viewer_panel_sets_cross_origin_isolated_on_stackblitz_embed() -> None:
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
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"crossOriginIsolated\s*:\s*true",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "viewer-panel.tsx: ``crossOriginIsolated: true`` saknas i "
        "``sdk.embedProject``-options. Krävs för Permissions Policy-"
        "delegering till stackblitz.com — utan den boota:r WebContainern "
        "inte och visar 'Unable to run Embedded Project'. Se "
        "EmbedOptions i @stackblitz/sdk/types/interfaces.d.ts och "
        "https://blog.stackblitz.com/posts/cross-browser-with-coop-coep/."
    )


@pytest.mark.tooling
def test_next_config_trusts_dispatcher_env_over_argv_for_https_check() -> None:
    """B145: ``process.argv`` är opålitlig under Turbopack — config laddas
    i worker-processer vars argv inte ärver parent-processens flaggor.
    Det gav falsk ``--experimental-https saknas``-varning i transport-
    mismatch-checken trots att dispatchern startat ``next dev`` med
    flaggan.

    Fix: ``next.config.ts`` konsulterar primärt
    ``process.env.VIEWSER_DISPATCHER_HTTPS === "1"`` (env-var som
    ``scripts/dev.mjs`` sätter när dispatchern valt https-grenen) och
    faller tillbaka till argv-checken för operatörer som kör
    ``next dev --experimental-https`` direkt utan dispatchern.

    Den dispatcher-managed env-varianten är auktoritativ signal — argv
    fungerar bara som fallback för manuell körning.
    """
    text = (VIEWSER_DIR / "next.config.ts").read_text(encoding="utf-8")
    pattern = re.compile(
        r"process\s*\.\s*env\s*\.\s*VIEWSER_DISPATCHER_HTTPS\s*===\s*[\"']1[\"']",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "next.config.ts: HTTPS-checken måste läsa "
        "``process.env.VIEWSER_DISPATCHER_HTTPS === \"1\"`` primärt — "
        "``process.argv``-grenen ger false-positiva varningar i "
        "Turbopack-workers vars argv inte ärver parent-processens "
        "flaggor (B145)."
    )


@pytest.mark.tooling
def test_dev_dispatcher_exports_https_signal_to_child() -> None:
    """Spegelfix till next.config.ts:s VIEWSER_DISPATCHER_HTTPS-check.
    ``scripts/dev.mjs`` MÅSTE exportera ``VIEWSER_DISPATCHER_HTTPS``
    baserat på ``useHttps`` så next.config.ts ser auktoritativ signal
    om dispatchern valt https-transport. Utan denna export ger
    transport-mismatch-checken false-positiva varningar i Turbopack-
    workers även när allt är korrekt konfigurerat.
    """
    text = (VIEWSER_DIR / "scripts" / "dev.mjs").read_text(encoding="utf-8")
    pattern = re.compile(
        r"VIEWSER_DISPATCHER_HTTPS\s*:\s*useHttps\s*\?\s*[\"']1[\"']\s*:\s*[\"']0[\"']",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "scripts/dev.mjs: child-env måste sätta "
        "``VIEWSER_DISPATCHER_HTTPS: useHttps ? \"1\" : \"0\"`` så "
        "next.config.ts kan verifiera transport-valet utan argv-"
        "gissning. Speglar den nya check:en i next.config.ts (B145)."
    )


@pytest.mark.tooling
def test_build_runner_uses_per_site_mutex_not_global_inflight() -> None:
    """Reviewer-fynd 2026-05-25 (Round 2 #5): den tidigare implementationen
    hade en enda global ``let inFlight: Promise | null = null`` som
    serialiserade ALLA byggen i Viewser-processen. Ett segt eller
    hängande bygge på t.ex. ``cafe-bistro`` blockerade då en helt
    orelaterad ``painter-palma``-build i samma process. Per-siteId-
    låsen är nödvändig (två build_site.py-processer som samtidigt
    skriver till ``.generated/<siteId>/`` ger korrupta artefakter),
    men den ska INTE vara global.

    Fix: ``Map<string, Promise<...>>`` keyat på siteId.
    ``runBuild(siteId)`` queue:ar bara mot SAMMA siteId — olika
    siteIds kan köra parallellt.

    Source-lock-mönstret:
      1. NEGATIVT: ingen ``let inFlight: Promise<...> | null`` (skalär).
      2. POSITIVT: ``const inFlight = new Map<string, Promise<...>>()``.
      3. POSITIVT: ``runBuild(siteId)``-loop:en kollar
         ``inFlight.has(siteId)`` (siteId-keyat) snarare än ``inFlight``
         (truthy global).
      4. POSITIVT: rensning sker via ``inFlight.delete(siteId)`` med
         identity-guard så en samtidig follow-up build inte nukas av
         misstag.
    """
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")

    # Negativt: gamla globala scalar-formen får inte återinföras.
    forbidden_global = re.compile(
        r"let\s+inFlight\s*:\s*Promise\s*<[^>]*>\s*\|\s*null",
        re.MULTILINE,
    )
    assert not forbidden_global.search(text), (
        "build-runner.ts: ``let inFlight: Promise<...> | null`` är "
        "den gamla globala mutex:en som blockerade orelaterade siteIds. "
        "Använd ``const inFlight = new Map<string, Promise<...>>()`` "
        "istället (Reviewer Round 2 #5)."
    )

    # Positivt: Map-deklaration med siteId-key + Promise-value.
    map_decl = re.compile(
        r"const\s+inFlight\s*=\s*new\s+Map\s*<\s*string\s*,\s*Promise\s*<[^>]*>\s*>\s*\(\s*\)",
        re.MULTILINE,
    )
    assert map_decl.search(text), (
        "build-runner.ts saknar ``const inFlight = new Map<string, "
        "Promise<...>>()``. Per-siteId-mutex kräver Map keyat på siteId "
        "så olika sajter kan bygga parallellt."
    )

    # Positivt: while-loop:en måste kolla per-siteId, inte den globala
    # Map-instansens truthy:hood.
    while_check = re.compile(
        r"while\s*\(\s*inFlight\s*\.\s*has\s*\(\s*siteId\s*\)\s*\)",
        re.MULTILINE,
    )
    assert while_check.search(text), (
        "build-runner.ts: ``while (inFlight.has(siteId))`` saknas. "
        "Tidigare ``while (inFlight)`` blockerade alla siteIds — den "
        "nya per-siteId-mutex:en måste kolla pending build för EXAKT "
        "den siteId callern frågar om."
    )

    # Positivt: rensningen ska gå via Map.delete med identity-guard så
    # en samtidig follow-up build (som hunnit skriva ny entry) inte
    # nukas av misstag.
    delete_with_guard = re.compile(
        r"if\s*\(\s*inFlight\s*\.\s*get\s*\(\s*siteId\s*\)\s*===\s*promise\s*\)\s*\{\s*"
        r"inFlight\s*\.\s*delete\s*\(\s*siteId\s*\)",
        re.MULTILINE,
    )
    assert delete_with_guard.search(text), (
        "build-runner.ts: rensningen i ``finally``-grenen ska göra "
        "``if (inFlight.get(siteId) === promise) inFlight.delete(siteId)`` "
        "så en samtidig follow-up build (som hunnit skriva ny entry för "
        "samma siteId) inte oavsiktligt nukas. Speglar samma identity-"
        "guard som den tidigare globala ``if (inFlight === promise)``."
    )


@pytest.mark.tooling
def test_prompt_route_returns_400_for_zod_validation_errors() -> None:
    """Audit fynd 1: ogiltig payload (tom prompt, för lång prompt, fel
    typ) är ett klient-/valideringsfel, inte serverfel. Före fixen
    fångade en bred try alla fel som 500, vilket gjorde API-kontraktet
    missvisande och försvårade felsökning.

    Lås att routen särskiljer ZodError -> 400 från övriga fel -> 500
    så framtida refactor inte återinför den breda 500-grenen.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "instanceof z.ZodError" in text, (
        "/api/prompt måste skilja Zod-valideringsfel från serverfel via "
        "`error instanceof z.ZodError` och returnera 400 för validering, "
        "inte den breda 500-grenen."
    )
    assert re.search(r"status:\s*400", text), (
        "/api/prompt saknar `status: 400`-svar för Zod-validering. "
        "Klient-/valideringsfel ska aldrig returneras som 500."
    )


@pytest.mark.tooling
def test_prompt_payload_schema_trims_whitespace_before_length_check() -> None:
    """Audit fynd 2: en whitespace-only prompt (`"   "`) passerar
    `.string().min(1)` men trimmades senare i `runPromptToProjectInput`
    och kastades som "Prompt får inte vara tom." vilket sedan blev 500.
    UI:n stoppar normalfallet men API-gränsen gjorde inte det.

    Lås att schemat trimmar FÖRE min/max så whitespace-only fångas vid
    API-gränsen och returneras som 400 (via ZodError).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"z\s*\.\s*string\(\)\s*\.\s*trim\(\)\s*\.\s*min\(\s*1",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "PromptPayloadSchema.prompt måste vara `z.string().trim().min(1)..."
        ".max(4000)` så whitespace-only payloads fångas av `.min(1)` "
        "EFTER trim. Utan trim slipper `' '` igenom till helpern."
    )


@pytest.mark.tooling
def test_prompt_route_passes_dossier_override_to_run_build() -> None:
    """Prompt-flödet får inte falla tillbaka till `runBuild(siteId)` utan
    dossier-path override - det skulle leta i `examples/` istället för
    `data/prompt-inputs/` och misslyckas med 'Project Input saknas'.
    Lås kontraktet att routen alltid skickar in helper.dossierPath."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "runBuild(helper.siteId, helper.dossierPath)" in text, (
        "/api/prompt måste anropa runBuild med BÅDE siteId och "
        "helper.dossierPath. Utan path-override hamnar lookupen i "
        "examples/ och det prompt-genererade Project Inputet hittas "
        "inte (det ligger i data/prompt-inputs/)."
    )


@pytest.mark.tooling
def test_prompt_route_supports_followup_mode_without_schema_migration() -> None:
    """Follow-up prompt ska styras av sidecar-meta, inte Project Input-schema."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert 'z.enum(["init", "followup"])' in text, (
        "/api/prompt måste ha explicit init/followup-läge så UI:t kan "
        "skilja ny sajt från ny version."
    )
    assert "siteId" in text and "Följdprompt kräver valt siteId" in text, (
        "Följdprompt-läget måste kräva siteId vid API-gränsen innan "
        "prompt-helpern spawnas."
    )
    assert "projectId: z" not in text and "version: z" not in text, (
        "/api/prompt ska inte validera projectId/version som klientpayload; "
        "sidecar-meta räcker i denna sprint."
    )


@pytest.mark.tooling
def test_prompt_route_serializes_prompt_helper_before_build() -> None:
    """Sidecar version bump + Project Input write must not race before build."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "promptInFlight" in text, (
        "/api/prompt måste serialisera prompt-helpern före runBuild så två "
        "följdpromptar för samma siteId inte läser samma meta.version."
    )
    helper_index = text.index("const helper = await runPromptToProjectInput")
    build_index = text.index("runBuild(helper.siteId, helper.dossierPath)")
    queue_index = text.index("promptInFlight")
    assert queue_index < helper_index < build_index, (
        "Prompt-queue måste omfatta både helpern och builden, inte bara "
        "runBuild-steget."
    )


@pytest.mark.tooling
def test_prompt_runner_uses_double_dash_to_protect_dashed_prompts() -> None:
    """Audit fynd 3: vanliga prompter börjar med `-` eller `--` (t.ex.
    en inklistrad punktlista: "- skapa en sajt..."). Utan `--`-separator
    tolkar argparse i `scripts/prompt_to_project_input.py` prompten som
    en CLI-option och spawnen fallerar innan Project Input hinner
    skrivas.

    Lås att lib/prompt-runner.ts skickar in `--` mellan scriptPath och
    prompten så argparse stannar option-parsning.
    """
    text = (VIEWSER_DIR / "lib" / "prompt-runner.ts").read_text(encoding="utf-8")
    pattern = re.compile(
        r"args\.push\(\s*\"--\"\s*,\s*trimmed\s*\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "prompt-runner.ts spawn-args måste lägga `--` direkt före prompten "
        "så en prompt som börjar med `-` (punktlista) eller `--` inte "
        "tolkas som CLI-option av argparse i prompt_to_project_input.py."
    )


@pytest.mark.tooling
def test_prompt_runner_passes_followup_site_id_to_helper() -> None:
    text = (VIEWSER_DIR / "lib" / "prompt-runner.ts").read_text(encoding="utf-8")
    assert "--followup-site-id" in text, (
        "prompt-runner.ts måste kunna skicka valt siteId till "
        "prompt_to_project_input.py för följdprompt-versioner."
    )
    assert "Följdprompt kräver ett valt siteId" in text, (
        "prompt-runner.ts måste stoppa följdprompt utan siteId innan spawn."
    )


@pytest.mark.tooling
def test_project_input_picker_includes_prompt_inputs_directory() -> None:
    text = (VIEWSER_DIR / "lib" / "project-inputs.ts").read_text(encoding="utf-8")
    assert '"prompt-inputs"' in text, (
        "listProjectInputs måste även läsa data/prompt-inputs/ så operatorn "
        "kan välja prompt-genererade siteIds för följdprompt."
    )
    assert '"examples"' in text, (
        "examples/ måste fortsatt finnas kvar som Project Input-källa."
    )


@pytest.mark.tooling
def test_prompt_builder_exposes_followup_mode_and_consumes_ndjson_stream() -> None:
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(
        encoding="utf-8"
    )
    # Följdprompt-läget exponerades tidigare via en synlig "Ny sajt /
    # Följdprompt"-pill-rad. Efter total-minimalism 2026-05-27 deriveras
    # läget automatiskt från `followupReady` istället. Testet förankrar
    # därför auto-derive-mönstret som det stabila kontraktet.
    assert '"followup"' in text and "followupReady" in text, (
        "PromptBuilder måste fortfarande exponera followup-läge — antingen "
        "via UI-val eller auto-derivering."
    )
    assert 'followupReady ? "followup" : "init"' in text, (
        "PromptBuilder måste auto-derivera mode från followupReady så "
        "operatorns prompt routas rätt utan manuell pill-växling."
    )
    assert 'submissionMode: "followup"' in text, (
        "PromptBuilder måste skicka submissionMode='followup' till "
        "executeBuild när followupReady är sant."
    )
    # B122-fix 2026-05-27: setTimeout(1500)-baserad stage-flip ersatt
    # av NDJSON-stream från /api/prompt. PromptBuilder ska skicka
    # `Accept: application/x-ndjson`, läsa `response.body` som stream
    # och flippa stage på `stage:"building"`-eventet.
    # `setTimeout(` (med öppningsparentes) flaggar faktiska function-
    # anrop. Historiska referenser i kommentarer/docstrings ("den gamla
    # setTimeout-baserade flippen") är tillåtna så fixet kan dokumentera
    # bort-refaktoreringen utan att triggas av sin egen förklaringstext.
    assert "setTimeout(" not in text, (
        "PromptBuilder får inte ANROPA setTimeout för stage-transitions "
        "längre — använd riktig signal från /api/prompt:s NDJSON-stream."
    )
    assert '"application/x-ndjson"' in text, (
        "PromptBuilder måste sätta Accept: application/x-ndjson så "
        "/api/prompt svarar med stream istället för synkron JSON."
    )
    assert "response.body.getReader()" in text, (
        "PromptBuilder måste läsa /api/prompt-svaret som stream via "
        "response.body.getReader()."
    )
    assert 'event.stage === "building"' in text, (
        "PromptBuilder måste flippa stage till 'building' när NDJSON-"
        "eventet `stage:\"building\"` kommer från route:n (riktig signal)."
    )
    assert 'event.stage === "done"' in text, (
        "PromptBuilder måste behandla `stage:\"done\"`-eventet som "
        "slutsignal med runId + siteId + buildStatus."
    )


@pytest.mark.tooling
def test_run_history_can_show_prompt_project_id_and_version() -> None:
    run_history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(
        encoding="utf-8"
    )
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    assert "projectId?: string" in run_history and "version?: number" in run_history, (
        "RunHistoryItem måste kunna bära sidecar projectId/version för "
        "prompt-genererade runs."
    )
    assert "run.projectId" in run_history and "run.version" in run_history, (
        "RunHistory måste rendera projectId/version när /api/runs skickar dem."
    )
    assert "prompt-inputs" in runs_lib and "projectId" in runs_lib, (
        "listRuns måste enrich:a runs med data/prompt-inputs/<siteId>.meta.json."
    )


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
def test_run_details_panel_surfaces_npm_failure_log_excerpt() -> None:
    """Build mismatch triage needs the original npm error in Run Details."""
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )

    assert "devPreviewDir" in panel_text, (
        "RunDetailsPanel must show build-result.json:devPreviewDir so "
        "operators can compare the runnable preview dir with generatedFilesDir."
    )
    assert "logExcerpt" in panel_text, (
        "RunDetailsPanel must render npmSteps[].logExcerpt so transient "
        "npm build failures keep their first actionable error."
    )
    assert "whitespace-pre-wrap" in panel_text, (
        "npm failure excerpts must preserve line breaks when rendered."
    )


@pytest.mark.tooling
def test_run_details_panel_renders_placeholder_contact_warning() -> None:
    """B133: when scripts/build_site.py writes ``placeholderContactFields``
    into build-result.json (because scripts/prompt_to_project_input.py
    filled contact slots with the B88 dummy fallback), the Build section
    of RunDetailsPanel must render an operator-facing warning instead
    of silently letting "+46 8 000 00 00" / "kontakt@example.se" /
    "Adress lämnas på förfrågan" reach the published site without any
    signal. Verified live in Viewser Overlay E2E Scout Case 3a
    2026-05-19 (`docs/reports/viewser-overlay-e2e-scout-2026-05-19.md`).
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )

    assert "placeholderContactFields" in panel_text, (
        "RunDetailsPanel must read build-result.json:placeholderContactFields "
        "so the operator sees that the contact block is dummy data."
    )
    assert "Kontakt-fält är platshållare" in panel_text, (
        "Warning copy must include the Swedish phrase 'Kontakt-fält är "
        "platshållare' — operators see the badge but not the JSON."
    )
    assert "Slutanvändaren ser dummy-värden tills operatör fyllt dem." in panel_text, (
        "Warning copy must explain the consequence in Swedish so the "
        "operator can act before sharing the preview with a customer."
    )
    assert "placeholder-contact-warning" in panel_text, (
        "Warning element must carry data-testid='placeholder-contact-warning' "
        "so future Playwright/Vitest coverage can target it without DOM "
        "scraping."
    )
    assert "amber-500" in panel_text, (
        "Warning must use the existing amber-500 utility class so it "
        "matches the established 'warn' tone in STATUS_TONE."
    )


@pytest.mark.tooling
def test_run_details_panel_renders_site_plan_warnings() -> None:
    """B144: när Builder-sprinten 2026-05-21 (B137 + B138 + Intent Guard
    light) skrev ``pageCountWarning`` (route_plan trim på brief.pageCount)
    och ``intentGuardWarnings`` (wizard categoryId vs brief
    businessTypeGuess) till ``site-plan.json``, renderade Run Details
    inte fälten. Operatören saknade synlig signal trots att artefakten
    bar warnings — verifierat live mot sköldpaddssoppa-runen där
    intentGuardWarnings flaggade ``categoryId='fitness'`` mot
    ``conflictingTerm='mat'`` utan att Run Details visade det. Reviewer
    2026-05-21 (~7/10) öppnade B144 (Medel) som följd, med PR #49-
    inventeringen ``docs/reports/run-details-warnings-inventory-2026-05-21.md``
    som placeringsskissen.

    Mirror placeholderContactFields-mönstret i BuildSection
    (``test_run_details_panel_renders_placeholder_contact_warning``):
    amber-block, ``data-testid``, svensk operatörsrubrik. Den äldre
    ``pageIntentWarnings`` (B132) tas med i samma block eftersom den
    redan finns i schemat men aldrig fick en strukturerad rendering.

    Locks:

    1. ``site-plan.json`` är canonical källa — komponenten läser fälten
       från sitePlan-objektet, inte build-result.json. Lock både
       fältnamnen OCH att källan är sitePlan (inte build).
    2. ``data-testid='site-plan-warnings'`` så framtida Playwright/Vitest
       coverage kan targeta blocket utan DOM-scraping.
    3. Amber tone (STATUS_TONE.warn) matchar placeholderContactFields-
       blocket — ej röd/destructive, eftersom warnings är non-blocking.
    4. Svensk rubrik ``Site Plan-varningar`` så operatören förstår
       blockets ursprung utan att läsa JSON.
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )

    for field in ("pageCountWarning", "intentGuardWarnings", "pageIntentWarnings"):
        assert field in panel_text, (
            f"RunDetailsPanel måste läsa site-plan.json:{field} så "
            f"operatören ser varningen i Site Plan-sektionen. Sprinten "
            f"2026-05-21 landade fälten i artefakten utan att rendera dem."
        )

    assert "sitePlan.pageCountWarning" in panel_text, (
        "Site Plan warning-blocket måste läsa pageCountWarning från "
        "sitePlan-objektet — site-plan.json är canonical källa enligt "
        "B144-skissen i docs/reports/run-details-warnings-inventory-"
        "2026-05-21.md. Build-result.json bär en kopia av "
        "pageIntentWarnings men plan-fältena (pageCountWarning + "
        "intentGuardWarnings) lever bara i site-plan.json."
    )
    assert "sitePlan.intentGuardWarnings" in panel_text, (
        "Site Plan warning-blocket måste läsa intentGuardWarnings från "
        "sitePlan-objektet (Intent Guard light skriver bara till "
        "site-plan.json, inte build-result.json — se B144-skissen)."
    )

    assert "site-plan-warnings" in panel_text, (
        "Site Plan warning-blocket måste bära "
        "data-testid='site-plan-warnings' så framtida Playwright/Vitest-"
        "coverage kan targeta det utan DOM-scraping. Mirror "
        "placeholder-contact-warning-mönstret från BuildSection."
    )

    assert "amber-500" in panel_text, (
        "Site Plan warning-blocket måste använda amber-500 "
        "(STATUS_TONE.warn), samma palett som placeholderContactFields-"
        "blocket. Warnings är non-blocking; röd/destructive skulle "
        "felaktigt signalera att builden stoppats."
    )

    assert "Site Plan-varningar" in panel_text, (
        "Site Plan warning-blocket måste ha en svensk rubrik så "
        "operatören förstår blockets innehåll utan att läsa JSON — "
        "mirror 'Kontakt-fält är platshållare'-mönstret från "
        "BuildSection. AGENTS.md kräver svenska operatörslabels."
    )

    assert "Build blockas inte" in panel_text, (
        "Site Plan warning-blocket måste förklara att varningarna är "
        "non-blocking så operatören inte tror att builden stoppats. "
        "Quality Gate/Repair-sektionerna driver build-status; planner-"
        "warnings är ren signalering."
    )


@pytest.mark.tooling
def test_chat_panel_component_is_removed() -> None:
    """B46: legacy ChatPanel component is dead code as of audit-fix
    2026-05-14. PromptBuilder is the only operator-facing prompt
    surface (test_viewser_prompt_primary.py locks it as canonical on
    home). The component file was deleted to remove the second
    "runId == success" code path the audit flagged. Lock the deletion
    here so a future restore would surface as a test failure rather
    than silently re-introducing the false-success surface.
    """
    assert not (VIEWSER_DIR / "components" / "chat-panel.tsx").exists(), (
        "components/chat-panel.tsx should not exist after the B46 audit-fix. "
        "Use PromptBuilder for the operator prompt -> Project Input -> build flow."
    )


@pytest.mark.tooling
def test_prompt_route_surfaces_build_status() -> None:
    """B44: /api/prompt must propagate build-result.json:status to the
    client so PromptBuilder can render success / degraded / failed
    instead of treating any returned runId as a green build.
    build-runner.ts intentionally returns the structured failure path
    with a runId (B40) so failed runs still appear in Run History;
    without buildStatus on the wire the operator UI used to flag those
    as "Build klar".
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "buildStatus" in text, (
        "/api/prompt route.ts must include `buildStatus` in the response "
        "payload so PromptBuilder can classify the build outcome."
    )
    assert "extractBuildStatus" in text or "buildResult.status" in text, (
        "/api/prompt route.ts must read build-result.json:status to populate "
        "buildStatus on the response."
    )


def test_prompt_route_emits_ndjson_stream_on_accept_header() -> None:
    """B122-fix 2026-05-27: /api/prompt måste exponera en NDJSON-stream
    när klienten signalerar `Accept: application/x-ndjson`, så PromptBuilder
    kan flippa stage från `thinking` till `building` på en RIKTIG signal
    (Phase 1 → Phase 2-övergången) istället för den gamla gissade
    `setTimeout(1500)`-flippen som producerade falsk 'Bygger sajt' om
    svaret kom under 1.5s eller motsatt — hängde i 'thinking' om Phase 1
    tog över 1.5s.

    Stream-kontrakt:
      1. `{stage:"building"}` exakt när Phase 1 (runPromptToProjectInput)
         är klar — innan runBuild startar.
      2. `{stage:"done", runId, siteId, ...}` när Phase 2 (runBuild) är klar.
      3. `{stage:"error", error:"..."}` vid fel.

    Bakåtkompatibelt: klienter som INTE skickar Accept-headern (t.ex.
    floating-chat.tsx och use-followup-build.ts) får fortfarande en
    synkron NextResponse.json med samma fält som tidigare.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert '"application/x-ndjson"' in text, (
        "/api/prompt route.ts måste exponera content-type 'application/x-ndjson' "
        "när Accept-headern begär stream-läge."
    )
    assert "ReadableStream" in text, (
        "/api/prompt route.ts måste returnera en ReadableStream när "
        "klienten begär NDJSON-läge."
    )
    assert "onPhase1Done" in text, (
        "/api/prompt route.ts måste skicka ett `onPhase1Done`-callback "
        "in i runPromptBuildOnce/runPromptBuildSerially så stream-läget "
        "kan emittera `stage:'building'` exakt mellan Phase 1 och Phase 2."
    )
    assert 'stage: "building"' in text, (
        "/api/prompt route.ts måste emittera `{stage:'building'}` i "
        "NDJSON-streamen när Phase 1 är klar."
    )
    assert 'stage: "done"' in text, (
        "/api/prompt route.ts måste emittera `{stage:'done', ...result}` "
        "som slutevent i NDJSON-streamen."
    )
    assert 'stage: "error"' in text, (
        "/api/prompt route.ts måste emittera `{stage:'error', error:'...'}` "
        "om något fas-anrop kastar inom streamen."
    )
    # Bakåtkompatibilitet: synkron NextResponse.json-fallback finns kvar
    # för klienter utan Accept-headern (floating-chat, use-followup-build).
    assert "NextResponse.json(await runPromptBuildSerially(payload))" in text, (
        "/api/prompt route.ts måste behålla den synkrona NextResponse.json-"
        "fallbacken för klienter som inte sätter Accept: application/x-ndjson."
    )


@pytest.mark.tooling
def test_prompt_builder_classifies_failed_build_distinctly() -> None:
    """B44: PromptBuilder must classify build outcomes via classifyBuildStatus
    and render distinct UI for success / degraded / failed instead of
    falling through to a single green "Build klar" banner whenever a
    runId is present. Lock the classification helper and the three
    distinct UI strings so a future refactor cannot collapse them.
    """
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(
        encoding="utf-8"
    )
    assert "classifyBuildStatus" in text, (
        "prompt-builder.tsx must export/use a classifyBuildStatus helper "
        "that maps build-result.json:status to ok/degraded/failed/unknown."
    )
    assert "PromptBuildOutcome" in text, (
        "prompt-builder.tsx must expose a PromptBuildOutcome type so page.tsx "
        "can render an outcome-aware header instead of a hard-coded 'Build klar'."
    )
    for stage_literal in (
        "\"degraded\"",
        "\"failed\"",
    ):
        assert stage_literal in text, (
            f"prompt-builder.tsx must distinguish stage {stage_literal} so "
            "degraded/failed builds do not render as success."
        )
    assert "Build klar med varning" in text, (
        "prompt-builder.tsx must render a degraded headline distinct from "
        "the success banner."
    )
    assert "Build misslyckades" in text, (
        "prompt-builder.tsx must render a dedicated failure headline when "
        "build-result.json status=failed."
    )


@pytest.mark.tooling
def test_page_uses_outcome_aware_header_for_prompt_build_done() -> None:
    """B44: app/page.tsx must propagate the PromptBuildOutcome from
    PromptBuilder into setStatusText so the page header does not say
    "Build klar via prompt:" for a structured failure run. Source-lock
    the headerStatusForOutcome helper so a future refactor cannot drop
    the classification.
    """
    text = (VIEWSER_DIR / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "PromptBuildOutcome" in text, (
        "page.tsx must import PromptBuildOutcome from @/components/prompt-builder."
    )
    assert "headerStatusForOutcome" in text, (
        "page.tsx must use headerStatusForOutcome to map the outcome to a "
        "header string instead of hardcoding 'Build klar via prompt:'."
    )
    assert "Build misslyckades" in text, (
        "page.tsx header must show a dedicated failure string when the "
        "PromptBuilder reports outcome=failed."
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

    # B40: the failure branch must read build-result.json from disk so
    # the UI sees a structured failed run instead of bare 500.
    assert re.search(r"exitCode\s*!==\s*0", text), (
        "build-runner.ts saknar exitCode !== 0-gren - hela B40-kontraktet "
        "hänger på den."
    )
    assert "readBuildResult" in text, (
        "build-runner.ts måste läsa build-result.json från disk i failure-"
        "grenen så failed runs når UI:t med strukturerad data istället för "
        "bare 500."
    )

    # B42 (post-review-2): the failure path must NOT fall back to
    # detectLatestRunIdByMtime() - that would return a PRIOR run-dir
    # whenever build_site.py crashes BEFORE printing `runId:`,
    # mislabeling someone else's run as the current failed build.
    # Only the success path may use the mtime fallback (where
    # exitCode === 0 guarantees the latest dir IS this build's).
    failure_block = re.search(
        r"if\s*\(\s*exitCode\s*!==\s*0\s*\)\s*\{[\s\S]*?\n\s{0,4}\}",
        text,
        re.MULTILINE,
    )
    assert failure_block, (
        "Kunde inte hitta `if (exitCode !== 0) { ... }`-blocket i "
        "build-runner.ts."
    )
    assert "detectLatestRunIdByMtime" not in failure_block.group(0), (
        "build-runner.ts failure-grenen får inte använda "
        "detectLatestRunIdByMtime() som fallback. När build_site.py "
        "kraschar FÖRE `print(runId:)` returnerar mtime-fallbacken en "
        "tidigare run och felaktigt märker den som denna build:s "
        "strukturerade failure (B42 post-review-2 fynd)."
    )


@pytest.mark.tooling
def test_page_useeffect_guards_success_path_with_cancelled_check() -> None:
    """Race-condition guard for app/page.tsx initial fetch:
    the success path of the useEffect-IIFE used to call refreshRuns()
    which itself ran setRuns / setProjectInputs / setSelectedRunId /
    setSelectedSiteId / setStatusText UNCONDITIONALLY after its own
    await. The cancelled-flag on the catch branch then only protected
    error-path stale updates, not success-path stale updates. If the
    component unmounted (or the dependency array changed) while
    /api/runs was in flight, a successful resolution arriving after
    unmount still wrote five setState calls onto a stale tree.

    The fix splits the call into a pure ``fetchRuns`` data fetcher
    and a separate ``applyRunsData`` state mutator, with the
    cancelled-guard sitting between them. Source-lock that ordering
    so a future refactor cannot collapse the two back into one
    function and silently drop the guard.
    """
    text = (VIEWSER_DIR / "app" / "page.tsx").read_text(encoding="utf-8")

    # Look for ``await fetchRuns()`` -> ``if (cancelled) return`` ->
    # ``applyRunsData`` (or ``setRuns(``) ordering inside the same
    # try-block. The 0-300 character window keeps the regex tight
    # against accidental matches across unrelated code.
    pattern = re.compile(
        r"await\s+fetchRuns\(\)[\s\S]{0,300}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,300}?(?:applyRunsData|setRuns\()",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "page.tsx useEffect saknar cancelled-guard mellan await fetchRuns() "
        "och applyRunsData / setRuns. Det skapar race condition där en "
        "stale success-resolution skriver state efter unmount."
    )


@pytest.mark.tooling
def test_viewer_panel_keeps_containerref_mounted_across_unavailable_transitions() -> None:
    """Stuck-state guard: when a 404-driven setUnavailable(true) used to
    replace ``<div ref={containerRef}>`` with the pedagogic tips block
    via an ``unavailable ? tips : <div ref>`` ternary, containerRef.current
    fell to null. The effect's first-line check
    ``if (!runId || !containerRef.current) { ... return; }`` then
    short-circuited on the NEXT runId change, leaving the UI stale
    because useEffect only depends on ``[runId]`` - the dependency
    array does not re-trigger on ``unavailable``-transitions, so the
    fetch never runs for the new runId.

    Fix: render containerRef-div ALWAYS and toggle visibility via the
    Tailwind ``hidden`` class. That keeps containerRef.current bound
    across transitions so subsequent fetches can run normally.

    Source-lock both the negative pattern (no ternary swap) and the
    positive pattern (containerRef-div has ``unavailable``-conditional
    ``hidden`` in className) so a future refactor cannot regress.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Negative: containerRef-div must NOT sit as the else-branch of an
    # `unavailable ? tips : <div ref={containerRef}>` ternary. That
    # pattern unmounts the ref whenever unavailable flips to true.
    forbidden = re.compile(
        r"unavailable\s*\?\s*\([\s\S]{0,400}?\)\s*:\s*\(\s*<div\s+ref=\{containerRef\}",
        re.MULTILINE,
    )
    assert not forbidden.search(text), (
        "viewer-panel.tsx: containerRef-div får inte sitta i else-grenen "
        "av en `unavailable ? tips : <div ref>` ternary - det avmonterar "
        "ref när unavailable=true och låser UI:t i stuck state vid nästa "
        "runId-byte (effekten har bara `[runId]` som dep)."
    )

    # Positive (beteende, inte exakt syntax): containerRef måste
    # vara always-mounted via en `<div ... ref={containerRef} ... />`
    # som finns OAVSETT `unavailable`-state. Hitta `ref={containerRef}`
    # och kontrollera att JSX-elementet i samma element-block referar
    # till `unavailable` på något sätt (className-toggle, data-attr,
    # cn(...)-helper, eller annan visibility-mekanism) - alla
    # acceptabla refactorer som behåller beteendet.
    #
    # B43 (post-review-2): den tidigare regex låste exakt
    # `className="...unavailable...hidden"`-ordning + literal `"hidden"`
    # vilket gjorde att en harmlös `cn(...)` / template-literal-refactor
    # bröt testet. Nu testar vi bara att unavailable-flaggan påverkar
    # ref-divden via något observerbart JSX-attribut.
    ref_element = re.search(
        r"<div\b[^>]*\bref=\{containerRef\}[^>]*/?>",
        text,
    )
    assert ref_element, (
        "viewer-panel.tsx: ingen `<div ... ref={containerRef} ... />` "
        "hittades. Always-mounted pattern kräver en self-closing eller "
        "kort JSX-tag med ref={containerRef}."
    )
    assert "unavailable" in ref_element.group(0), (
        "viewer-panel.tsx: ref-div måste referera till `unavailable` i "
        "ett JSX-attribut (t.ex. className-toggle, data-attr, cn(...)). "
        "Det signalerar att unavailable-flaggan styr visibility utan att "
        "avmontera ref:en. Hittad ref-div:\n"
        f"{ref_element.group(0)!r}"
    )


@pytest.mark.tooling
def test_viewer_panel_guards_cancelled_after_dynamic_import_and_embed() -> None:
    """B43 (post-review-2): the StackBlitz embed path has TWO awaits
    after the initial cancelled-guard: ``await import("@stackblitz/sdk")``
    and ``await sdk.embedProject(...)``. If the operator switches runId
    between them, useEffect cleanup sets cancelled=true but the
    in-flight embedProject still mounts the STALE preview into the
    always-mounted ref-div. Reviewer flagged this in the post-review-2
    audit.

    Fix: re-check cancelled AFTER the dynamic import and AFTER the
    embedProject await. When cancelled is true post-embed, clear the
    node so the next runId starts from a clean slate.

    Source-lock the guard density: at least two cancelled-checks must
    appear between the StackBlitz import and the final setStatus call.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Status-pillen ("Förhandsvisning aktiv för {runId}") togs medvetet
    # bort i christopher-ui refactor:n (krockade visuellt med
    # SiteHeader-logon). Det ursprungliga B43-testet använde
    # ``setStatus(\`Förhandsvisning aktiv``-strängen som slutpunkt för
    # success-blocket; den finns inte längre. Vi ankrar nu på
    # ``setLoading(false)`` direkt efter iframe-höjd/bredd-setningen,
    # vilket är den nya success-path-terminatorn.
    block = re.search(
        r"const sdk = \(await import\(\"@stackblitz/sdk\"\)\)[\s\S]*?setLoading\(false\);\s*\n\s*\}\s*catch",
        text,
    )
    assert block, (
        "viewer-panel.tsx: kunde inte hitta success-path-blocket från "
        "StackBlitz-import till setLoading(false)-terminatorn före catch. "
        "Refactor utan ekvivalent kommunikation av runId-success bryter "
        "detta test."
    )
    cancelled_checks = re.findall(r"\bcancelled\b", block.group(0))
    assert len(cancelled_checks) >= 2, (
        "viewer-panel.tsx success-path saknar tillräcklig cancelled-guard-"
        "täthet mellan StackBlitz-import och setLoading(false). Förväntat "
        "minst 2 cancelled-referenser (en efter import, en efter "
        f"embedProject) - hittade {len(cancelled_checks)}. B43-fyndet: "
        "stale embed kan mountas i ref-divden om operatör byter runId "
        "mid-flight."
    )

    # Verify the node-cleanup on stale embed exists (otherwise we'd
    # just NOT setStatus but the iframe still sits in the DOM). The
    # cleanup now uses replaceChildren() instead of innerHTML so the
    # React-owned shell keeps a cleaner DOM mutation pattern.
    assert re.search(
        r"if\s*\(\s*cancelled\s*\)\s*\{[\s\S]{0,300}?replaceChildren\(\)",
        text,
    ), (
        "viewer-panel.tsx: post-embed cancelled-grenen måste rensa "
        "containerRef.current så stale embed inte sitter kvar i "
        "den always-mounted ref-divden."
    )


@pytest.mark.tooling
def test_viewer_panel_surfaces_stackblitz_sdk_error_details() -> None:
    """StackBlitz SDK failures must show actionable details, not "unknown"."""
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )
    assert "formatViewerError" in text, (
        "viewer-panel.tsx måste formatera SDK-fel centralt så catch-grenen "
        "inte faller tillbaka till ett opakt 'Okänt viewer-fel'."
    )
    for expected in ("name:", "message:", "stack:", "slice(0, 20)"):
        assert expected in text, (
            "Viewer-felet måste visa Error.name, Error.message och de första "
            f"20 stackraderna. Saknar {expected!r}."
        )
    assert "non-Error rejection" in text, (
        "StackBlitz SDK kan rejecta med icke-Error-värden; de måste också "
        "renderas läsbart."
    )
    assert "whitespace-pre-wrap" in text and "<pre" in text, (
        "Viewer-feldetaljer måste renderas i ett pre-block så stackrader "
        "och radbrytningar bevaras."
    )


@pytest.mark.tooling
def test_viewer_panel_404_branch_guards_cancelled_before_setstate() -> None:
    """Race-condition guard: when /api/runs/<runId>/files returns 404,
    the in-flight async effect must not write setState for a runId
    that has already been replaced by a newer one. Without the
    cancelled-guard a stale 404 from a previous runId overwrites the
    UI state for the currently selected run (e.g. flips it to
    "preview saknas" even though the new run has preview files).

    Source-lock the cancelled-check inside the 404 branch so a future
    refactor cannot drop it. The other branches (success, catch) are
    already guarded; this brings the 404 path in line with them.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Find the 404 branch and verify a `cancelled` guard sits between
    # the `response.status === 404` check and the call to setUnavailable.
    # Multi-line regex is more robust than substring tricks here.
    #
    # Argument-shape till setUnavailable är medvetet permissivt
    # (``setUnavailable\([\s\S]+?\)``) så testet förblir grönt över både
    # den ursprungliga ``setUnavailable(true)``-formen och den utvidgade
    # ``setUnavailable({title, message, hint})``-formen som
    # fix-fallback-headers introducerade. ``[\s\S]+?`` (med ``+``, INTE
    # ``*``) kräver minst ett tecken inuti parenteserna så ett tomt
    # ``setUnavailable()``-anrop INTE matchar — det vore en regression
    # som skulle dölja 404-fallet i UI:t. Race-condition-låsen är
    # ``if (cancelled) return;`` MELLAN 404-checken och setUnavailable;
    # argumentets exakta form är inte poängen.
    pattern = re.compile(
        r"response\.status\s*===\s*404[\s\S]{0,400}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,400}?setUnavailable\([\s\S]+?\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "viewer-panel.tsx 404-branch saknar cancelled-guard innan "
        "setUnavailable / setStatus. Det skapar race-condition mellan "
        "snabba runId-byten där en stale 404 skriver över state för en "
        "nyladdad run."
    )


@pytest.mark.tooling
def test_viewer_panel_local_next_failure_branches_guard_cancelled() -> None:
    """Same race-condition guard som test_viewer_panel_404_branch_guards_
    cancelled_before_setstate, fast för de TRE nya local-next-failure-
    grenarna som fix-fallback-headers introducerade:

      1. POST /api/preview/<siteId> returnerar non-OK i local-next-mode
         → setUnavailable med strukturerad info från
           unavailableForPreviewError(errPayload).
      2. POST /api/preview/<siteId> kastar (network error) i
         local-next-mode → setUnavailable("Lokal preview-server kunde
         inte nås").
      3. siteId saknas men runId finns i local-next-mode →
         setUnavailable("Saknar siteId för lokal preview").

    Alla tre måste guarda mot stale runId-switch via ``cancelled``
    INNAN de skriver UI-state. Utan denna lock kan en framtida
    refactor släppa guarden och åter introducera samma race som
    den ursprungliga 404-fixen redan stoppat.

    Vi söker efter mönstret ``IS_LOCAL_NEXT_MODE`` följt inom 300 chars
    av ``if (cancelled) return;`` följt inom 200 chars av
    ``setUnavailable(``. Förväntar minst 3 sådana matchningar (en per
    failure-gren).
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    # Limits är frikostiga (800/600) så regex tål både kompakta varianter
    # och de pedagogiska inline-kommentarer som dokumenterar varför
    # cancelled-guarden behövs i respektive gren. Testets syfte är att
    # låsa ATT guarden finns — inte att tvinga fram en kompakt stil.
    pattern = re.compile(
        r"IS_LOCAL_NEXT_MODE[\s\S]{0,800}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,600}?setUnavailable\([\s\S]+?\)",
        re.MULTILINE,
    )
    matches = pattern.findall(text)
    assert len(matches) >= 3, (
        f"Förväntade ≥3 IS_LOCAL_NEXT_MODE-grenar med cancelled-guard "
        f"före setUnavailable, hittade {len(matches)}. "
        f"De tre grenarna är: (a) non-OK från POST /api/preview/<siteId>, "
        f"(b) network-error från samma fetch, (c) siteId saknas men "
        f"runId finns. Alla tre måste skydda mot stale runId-switch "
        f"så att en sen async-respons inte skriver över state för en "
        f"nyladdad run."
    )


@pytest.mark.tooling
def test_viewer_panel_local_next_non_ok_branch_reguards_after_json_parse() -> None:
    """Codex P2 (PR #97 review): i ``IS_LOCAL_NEXT_MODE``-grenen för
    non-OK response från ``POST /api/preview/<siteId>`` kollas
    ``cancelled`` FÖRE ``await previewResponse.json()`` men inte
    EFTER. Om operatören byter run under JSON-parsen kan den stale
    requesten fortfarande anropa ``setUnavailable(...)`` /
    ``setLoading(false)`` och skriva över state för den nyvalda runen
    — exakt samma race-condition som den ursprungliga 404-fixen
    redan stoppat på StackBlitz-vägen.

    Lås mönstret: mellan ``await previewResponse.json()`` (som ger
    ``errPayload``) och ``setUnavailable(unavailableForPreviewError``
    måste det finnas en ``if (cancelled) return;``. Source-lock så
    framtida refactor inte tar bort den.

    Implementationsdetalj: vi hittar errPayload-deklarationen (unik
    lokal variabel som bara existerar i denna gren), söker fram till
    ``setUnavailable(unavailableForPreviewError``, och verifierar att
    en ``if (cancelled) return;`` sitter mellan dem. Mer robust än
    en ren one-shot regex eftersom det inte bryts av inline-kommentarer
    eller indenterings-refactors.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(
        encoding="utf-8"
    )

    err_payload_idx = text.find("errPayload = (await previewResponse")
    assert err_payload_idx != -1, (
        "viewer-panel.tsx saknar `errPayload = (await previewResponse...` "
        "i IS_LOCAL_NEXT_MODE non-OK-grenen. Annars test kan inte ankra "
        "mellan parsen och state-skrivningen."
    )
    setunavail_idx = text.find(
        "setUnavailable(unavailableForPreviewError", err_payload_idx
    )
    assert setunavail_idx != -1, (
        "viewer-panel.tsx saknar `setUnavailable(unavailableForPreviewError(...))` "
        "efter errPayload-deklarationen — non-OK-grenen måste rendera "
        "strukturerad felinfo via unavailableForPreviewError."
    )
    between = text[err_payload_idx:setunavail_idx]
    assert re.search(r"if\s*\(\s*cancelled\s*\)\s*return\s*;", between), (
        "viewer-panel.tsx IS_LOCAL_NEXT_MODE non-OK-grenen saknar "
        "`if (cancelled) return;` mellan `await previewResponse.json()` "
        "och `setUnavailable(unavailableForPreviewError(...))`. Utan "
        "denna re-check kan en stale request som passerar den pre-await "
        "cancelled-checken fortfarande skriva över UI-state för en "
        "nyvald run (Codex P2 fynd, PR #97 review). Mirror samma mönster "
        "som success-grenen redan har efter `await previewResponse.json() "
        "as PreviewServerInfo`."
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
def test_page_on_build_done_passes_apply_runs_context() -> None:
    """Stale-closure guard: after onBuildDone sets selectedRunId, the
    fetchRuns().then(applyRunsData) path must pass an explicit context
    snapshot so applyRunsData does not read a pre-build selectedRunId
    and reset selectedSiteId to the first Project Input.
    """
    text = (VIEWSER_DIR / "app" / "page.tsx").read_text(encoding="utf-8")
    pattern = re.compile(
        r"fetchRuns\(\)[\s\S]{0,400}?applyRunsData\(\s*data\s*,\s*\{[\s\S]{0,200}?selectedRunId:\s*runId",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "page.tsx onBuildDone ska anropa applyRunsData med ctx.selectedRunId "
        "= runId — annars vinner stale closure och run-following bryts."
    )


@pytest.mark.tooling
def test_run_details_panel_clears_bundle_on_run_change() -> None:
    """Stale-artefakt guard: when runId changes the effect must clear
    bundle before fetching so the panel never shows the previous run's
    build/quality cards under the new run badge.
    """
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"setBundle\(null\)[\s\S]{0,120}?setLoading\(true\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "run-details-panel.tsx måste nollställa bundle innan ny fetch "
        "vid runId-byte — annars visas gamla artefakter under laddning."
    )


@pytest.mark.tooling
def test_prompt_builder_blocks_followup_when_run_siteid_unknown() -> None:
    """Follow-up guard: when the selected run has siteId unknown the UI
    must not fall back to selectedSiteId for targetSiteId (silent wrong
    site). Source-lock runSiteIdUnknown + explicit submit error.
    """
    prompt_text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(
        encoding="utf-8"
    )
    assert "runSiteIdUnknown" in prompt_text
    assert "follow-up kan inte" in prompt_text
    picker_text = (
        VIEWSER_DIR / "components" / "project-input-picker.tsx"
    ).read_text(encoding="utf-8")
    assert "project-input-run-siteid-unknown" in picker_text


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
    """Viewser MVP får INTE innehålla Dossier-edit, DNA, repair, quality."""
    forbidden_substrings = [
        "ProjectDna",
        "RepairPipeline",
        "QualityGate",
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
