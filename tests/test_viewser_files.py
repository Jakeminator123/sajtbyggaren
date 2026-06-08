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
        # Marknadssajt P0 (scout-marketing-site): route-group-split. Konsolen
        # flyttad till (console)/studio; (marketing) äger "/".
        "app/(console)/layout.tsx",
        "app/(console)/studio/page.tsx",
        "app/(marketing)/layout.tsx",
        "app/(marketing)/page.tsx",
        "app/(marketing)/for/[yrke]/page.tsx",
        "components/marketing/marketing-header.tsx",
        "components/marketing/marketing-footer.tsx",
        # Marknadssajt P6 (cookie-consent + legal-sidor).
        "components/marketing/cookie-consent.tsx",
        "components/marketing/cookie-banner.tsx",
        "components/marketing/manage-cookies-button.tsx",
        "components/marketing/legal-page-layout.tsx",
        "app/(marketing)/cookies/page.tsx",
        "app/(marketing)/integritetspolicy/page.tsx",
        "app/(marketing)/anvandarvillkor/page.tsx",
        "app/(marketing)/kontakt/page.tsx",
        # Marknadssajt P8 (SEO-finish).
        "app/sitemap.ts",
        "app/robots.ts",
        # Publika route-konstanter (auth/billing parkerat — egen seam senare).
        "lib/routes.ts",
        # Starters-banan (juni 2026): yrkessida/hero-chip/studio-onboarding
        # förifyller DiscoveryWizarden via en lätt seed. Rör inte bygg-logiken.
        "lib/starter-presets.ts",
        "components/marketing/starter-cta.tsx",
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
        "Discovery-options-routen får inte exponera starterId/expectedStarterId till frontend."
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
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "site-type-step.tsx"
    ).read_text(encoding="utf-8")
    constants = (VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-constants.ts").read_text(
        encoding="utf-8"
    )

    assert 'fetch("/api/discovery-options"' in wizard, (
        "DiscoveryWizard måste hämta kategori-options från governance-routen när overlayen öppnas."
    )
    assert "fallbackDiscoveryOptions" in wizard, (
        "DiscoveryWizard behöver en lokal UI-cache fallback så overlayen inte "
        "blockas av ett transient route-fel."
    )
    assert 'source === "governance"' in site_type, (
        "SiteTypeStep ska skilja governance-källan från UI-cache-fallbacken "
        "(gat:ar supportHelper + renderSupportNotice)."
    )
    # Wave 3 (Steg 7): fallback/planned-status ska fortfarande vara begriplig
    # men i KUNDSPRÅK — den gamla 'Backendens resolver avgör slutlig scaffold'
    # -jargongen ersattes med en kundvänlig formulering.
    assert "Vi väljer en närliggande mall som grund så länge." in site_type, (
        "SiteTypeStep ska göra fallback/planned-status begriplig i kundspråk "
        "utan att frontend tar scaffold-beslutet."
    )
    assert "Discovery Taxonomy is the canonical" in constants, (
        "wizard-constants.ts måste dokumentera att TS-listan bara är UI-cache."
    )


@pytest.mark.tooling
def test_discovery_payload_blocks_unknown_categories_and_emits_schema_version_2() -> None:
    payload = (VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-payload.ts").read_text(
        encoding="utf-8"
    )

    assert "schemaVersion: 1 | 2" in payload, (
        "DiscoveryPayload-typen måste fortsätta acceptera legacy v1 för bakåtkompatibilitet."
    )
    assert "schemaVersion: 2," in payload, (
        "buildDiscoveryPayload ska emit:a schemaVersion=2 när v2-directives skickas från wizarden."
    )
    assert "validateDiscoveryCategoryIds" in payload, (
        "buildDiscoveryPayload måste blocka category ids som saknas i governance-options."
    )
    assert "Okänd kategori" in payload, (
        "Okända category ids ska ge tydligt klientfel före /api/prompt."
    )
    assert "resolveScaffoldHintFromOptions" in payload, (
        "buildDiscoveryPayload ska härleda scaffoldHint från category-options "
        "så ecommerce inte skickar local-service-business som motsägande hint."
    )
    assert '"starterId"' not in payload, "Frontendens discovery payload får inte sätta starterId."


@pytest.mark.tooling
def test_discovery_payload_preserves_empty_list_tombstones() -> None:
    payload = (VIEWSER_DIR / "components" / "discovery-wizard" / "wizard-payload.ts").read_text(
        encoding="utf-8"
    )

    for key in (
        '"products"',
        '"moodImages"',
        '"requestedCapabilities"',
        '"conversionGoals"',
        '"uniqueSellingPoints"',
        '"sectionTreatments"',
        '"notesForPlanner"',
    ):
        assert key in payload, (
            f"wizard-payload.ts måste bevara tom lista för {key} så backend "
            "kan rensa tidigare wizard-värden när operatören tar bort allt."
        )
    assert "directives.requestedCapabilities = capabilities" in payload, (
        "requestedCapabilities måste skickas även när listan är tom."
    )
    # D2 (scout-fynd, 2026-06-05): conversionGoals ligger i PRESERVE_EMPTY_KEYS,
    # så en tom lista skickas som tombstone och NOLLAR backendens
    # conversion_goals. Det får BARA ske när operatören tömt CTA-valet — inte
    # när hen valt en CTA som bara inte keyword-matchar ("Läs mer"/"Registrera
    # dig"). Tidigare ``directives.conversionGoals = mapCtaToConversionGoals(...)``
    # nollade målen även då. Lås den nya distinktionen: mappa till en mellan-
    # variabel och emittera bara fältet vid tom CTA (tombstone) eller faktisk
    # matchning; omatchad icke-tom CTA utelämnar fältet så briefModel-
    # extraktionen står kvar.
    assert "const mappedGoals = mapCtaToConversionGoals(primaryCtaTrimmed);" in payload, (
        "conversionGoals måste mappas till en mellan-variabel så omatchad CTA "
        "kan utelämna fältet i stället för att nolla backendens mål."
    )
    assert (
        "if (primaryCtaTrimmed.length === 0 || mappedGoals.length > 0) {" in payload
    ), (
        "conversionGoals-tombstonen får bara emitteras vid tom CTA eller "
        "faktisk keyword-matchning — annars utelämnas fältet (D2)."
    )
    assert "directives.conversionGoals = mappedGoals;" in payload
    assert "directives.uniqueSellingPoints = answers.uniqueSellingPoints" in payload
    assert "directives.sectionTreatments = sectionPins" in payload


@pytest.mark.tooling
def test_prompt_route_rejects_discovery_starter_id_and_followup_discovery() -> None:
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    assert "Discovery-payload får inte sätta starterId" in text, (
        "/api/prompt måste avvisa starterId i discovery.answers."
    )
    assert "Discovery-wizarden används bara i init-läge" in text, (
        "Followup mode får inte acceptera discovery-payload."
    )


@pytest.mark.tooling
def test_python_spawn_routes_fail_explicitly_on_hosted_vercel() -> None:
    helper = (VIEWSER_DIR / "lib" / "hosted-python-runtime.ts").read_text(encoding="utf-8")
    assert 'process.env.VERCEL === "1"' in helper
    assert "hosted-python-runtime-unavailable" in helper

    for relative, feature in (
        ("app/api/prompt/route.ts", "prompt-build"),
        ("app/api/build/route.ts", "build"),
        ("app/api/scrape-site/route.ts", "scrape-site"),
    ):
        text = (VIEWSER_DIR / relative).read_text(encoding="utf-8")
        assert "isHostedVercelRuntime()" in text, (
            f"{relative} måste stoppa hosted Vercel innan Python-spawn."
        )
        assert f'hostedPythonRuntimeUnavailable("{feature}")' in text


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
        "app/api/preview/[siteId]/route.ts",
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
def test_viewer_panel_drives_preview_mode_through_descriptor() -> None:
    """Bite C (commit ee68add): ViewerPanel får INTE längre läsa
    ``NEXT_PUBLIC_VIEWSER_PREVIEW_MODE`` rått och härleda IS_*-booleanerna
    via ``=== "..."`` mot en lokal lower-cased sträng. Den client-säkra
    ``resolvePreviewRuntimeDescriptor`` (@preview-runtime) ska vara EN
    delad mode-normaliserare med host-transporten (``scripts/dev.mjs``).

    Fyra lås:
      1. ``resolvePreviewRuntimeDescriptor`` importeras från
         ``@preview-runtime``.
      2. Descriptorn drivs av ``process.env.NEXT_PUBLIC_VIEWSER_PREVIEW_MODE``
         (med behållen ``?? "local-next"``-default så en osatt env beter
         sig EXAKT som förr).
      3. KRITISKT — ``auto`` ≠ ``local-next``: ``IS_LOCAL_NEXT_MODE`` måste
         härledas ur ``PREVIEW_RUNTIME.rawMode`` (som bevarar distinktionen),
         ALDRIG ur ``.kind`` (som kollapsar local-next/auto/local till
         ``"local"`` och därmed skulle flippa ``auto`` till local-next och
         tappa StackBlitz-fallbacken).
      4. Det gamla råa mönstret
         ``const VIEWSER_PREVIEW_MODE = (...).toLowerCase()`` får inte vara
         kvar — annars finns två konkurrerande normaliserare igen.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    # Lock 1: importen från @preview-runtime.
    assert re.search(
        r'import\s*\{\s*resolvePreviewRuntimeDescriptor\s*\}\s*from\s*["\']@preview-runtime["\']',
        text,
    ), (
        "viewer-panel.tsx måste importera ``resolvePreviewRuntimeDescriptor`` "
        "från ``@preview-runtime`` (Bite C, ee68add) i stället för att läsa "
        "preview-mode rått."
    )

    # Lock 2: descriptorn drivs av NEXT_PUBLIC_VIEWSER_PREVIEW_MODE med
    # behållen local-next-default.
    assert re.search(
        r"resolvePreviewRuntimeDescriptor\(\s*process\.env\."
        r'NEXT_PUBLIC_VIEWSER_PREVIEW_MODE\s*\?\?\s*["\']local-next["\']',
        text,
    ), (
        "viewer-panel.tsx måste driva descriptorn med "
        "``resolvePreviewRuntimeDescriptor(process.env."
        "NEXT_PUBLIC_VIEWSER_PREVIEW_MODE ?? 'local-next')``. ``?? 'local-next'`` "
        "är beteende-bevarande: descriptorns egna tomma default är ``'local'``, "
        "men en osatt env ska fortsätta bete sig som local-next (COEP av, "
        "ingen StackBlitz-fallback)."
    )

    # Lock 3: auto ≠ local-next — IS_LOCAL_NEXT_MODE härleds ur rawMode.
    assert re.search(
        r'const\s+IS_LOCAL_NEXT_MODE\s*=\s*PREVIEW_RUNTIME\.rawMode\s*===\s*["\']local-next["\']',
        text,
    ), (
        "viewer-panel.tsx måste härleda ``IS_LOCAL_NEXT_MODE`` ur "
        "``PREVIEW_RUNTIME.rawMode === 'local-next'`` (INTE ur ``.kind``). "
        "``kind`` kollapsar local-next/auto/local till ``'local'`` — om "
        "IS_LOCAL_NEXT_MODE härleddes ur ``.kind`` skulle ``auto`` felaktigt "
        "flippas till local-next och tappa sin StackBlitz-fallback. "
        "``rawMode`` bevarar distinktionen auto ≠ local-next."
    )
    # Negativ guard: IS_LOCAL_NEXT_MODE får inte härledas ur ``.kind``.
    assert not re.search(
        r"const\s+IS_LOCAL_NEXT_MODE\s*=\s*PREVIEW_RUNTIME\.kind\b",
        text,
    ), (
        "viewer-panel.tsx: ``IS_LOCAL_NEXT_MODE`` får ALDRIG härledas ur "
        "``PREVIEW_RUNTIME.kind`` — det skulle slå ihop ``auto`` med "
        "``local-next`` (kind-kollaps) och bryta StackBlitz-fallbacken."
    )

    # Lock 4: det gamla råa env-mönstret är borta.
    assert not re.search(
        r"const\s+VIEWSER_PREVIEW_MODE\s*=\s*\(",
        text,
    ), (
        "viewer-panel.tsx får inte längre deklarera "
        "``const VIEWSER_PREVIEW_MODE = (...).toLowerCase()`` — den råa "
        "env-läsningen ersätts av resolvePreviewRuntimeDescriptor så klient "
        "och host delar en enda mode-normaliserare."
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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
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
        '``process.env.VIEWSER_DISPATCHER_HTTPS === "1"`` primärt — '
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
        '``VIEWSER_DISPATCHER_HTTPS: useHttps ? "1" : "0"`` så '
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
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
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
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
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
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "runBuild(helper.siteId, helper.dossierPath)" in text, (
        "/api/prompt måste anropa runBuild med BÅDE siteId och "
        "helper.dossierPath. Utan path-override hamnar lookupen i "
        "examples/ och det prompt-genererade Project Inputet hittas "
        "inte (det ligger i data/prompt-inputs/)."
    )


@pytest.mark.tooling
def test_prompt_route_supports_followup_mode_without_schema_migration() -> None:
    """Follow-up prompt ska styras av sidecar-meta, inte Project Input-schema."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert 'z.enum(["init", "followup"])' in text, (
        "/api/prompt måste ha explicit init/followup-läge så UI:t kan "
        "skilja ny sajt från ny version."
    )
    assert "siteId" in text and "Följdprompt kräver valt siteId" in text, (
        "Följdprompt-läget måste kräva siteId vid API-gränsen innan prompt-helpern spawnas."
    )
    assert "projectId: z" not in text and "version: z" not in text, (
        "/api/prompt ska inte validera projectId/version som klientpayload; "
        "sidecar-meta räcker i denna sprint."
    )


@pytest.mark.tooling
def test_prompt_route_serializes_prompt_helper_before_build() -> None:
    """Sidecar version bump + Project Input write must not race before build."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "promptInFlight" in text, (
        "/api/prompt måste serialisera prompt-helpern före runBuild så två "
        "följdpromptar för samma siteId inte läser samma meta.version."
    )
    helper_index = text.index("const helper = await runPromptToProjectInput")
    build_index = text.index("runBuild(helper.siteId, helper.dossierPath)")
    queue_index = text.index("promptInFlight")
    assert queue_index < helper_index < build_index, (
        "Prompt-queue måste omfatta både helpern och builden, inte bara runBuild-steget."
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
    assert '"examples"' in text, "examples/ måste fortsatt finnas kvar som Project Input-källa."
    assert "return null" in text and "JSON.parse" in text, (
        "Korrupta Project Input-filer ska hoppas över lokalt i listProjectInputs "
        "så en trasig fil inte 500:ar hela /api/runs."
    )
    assert "bySiteId.set(item.siteId, item)" in text, (
        "listProjectInputs måste dedupe:a på siteId och låta prompt-inputs "
        "vinna över examples när samma siteId finns i båda rötter."
    )


@pytest.mark.tooling
def test_prompt_builder_exposes_followup_mode_and_consumes_ndjson_stream() -> None:
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
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
        "PromptBuilder måste läsa /api/prompt-svaret som stream via response.body.getReader()."
    )
    assert 'event.stage === "building"' in text, (
        "PromptBuilder måste flippa stage till 'building' när NDJSON-"
        'eventet `stage:"building"` kommer från route:n (riktig signal).'
    )
    assert 'event.stage === "done"' in text, (
        'PromptBuilder måste behandla `stage:"done"`-eventet som '
        "slutsignal med runId + siteId + buildStatus."
    )


@pytest.mark.tooling
def test_run_history_can_show_prompt_project_id_and_version() -> None:
    run_history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    assert "projectId?: string" in run_history and "version?: number" in run_history, (
        "RunHistoryItem måste kunna bära sidecar projectId/version för prompt-genererade runs."
    )
    assert "run.projectId" in run_history and "run.version" in run_history, (
        "RunHistory måste rendera projectId/version när /api/runs skickar dem."
    )
    assert "prompt-inputs" in runs_lib and "projectId" in runs_lib, (
        "listRuns måste enrich:a runs med data/prompt-inputs/<siteId>.meta.json."
    )


@pytest.mark.tooling
def test_runs_api_handles_missing_runs_dir_and_invalid_since() -> None:
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")
    trace_route = (
        VIEWSER_DIR / "app" / "api" / "runs" / "[runId]" / "trace" / "route.ts"
    ).read_text(encoding="utf-8")

    assert 'code === "ENOENT"' in runs_lib and "return []" in runs_lib, (
        "listRuns ska returnera tom lista när data/runs saknas i en färsk miljö."
    )
    assert "Ogiltigt since-timestamp" in runs_lib, (
        "readRunTrace ska flagga ogiltig since i stället för att tyst "
        "returnera hela trace-loggen igen."
    )
    assert "Ogiltigt since" in trace_route and "status: 400" in trace_route, (
        "trace API ska rapportera ogiltig since som 400 inputfel."
    )


@pytest.mark.tooling
def test_build_runner_latest_run_fallback_tolerates_missing_runs_dir() -> None:
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    function_start = text.index("async function detectLatestRunIdByMtime")
    function_body = text[function_start : text.index("async function runBuildOnce")]

    assert 'code === "ENOENT"' in function_body and "return null" in function_body, (
        "detectLatestRunIdByMtime ska returnera null när data/runs saknas "
        "så färska miljöer inte 500:ar efter en lyckad build utan stdout-runId."
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
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
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
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

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
    2026-05-19 (`docs/archive/2026-05-19/viewser-overlay-e2e-scout-2026-05-19.md`).
    """
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

    assert "placeholderContactFields" in panel_text, (
        "RunDetailsPanel must read build-result.json:placeholderContactFields "
        "so the operator sees that the contact block is dummy data."
    )
    assert "Kontakt-fält är platshållare" in panel_text, (
        "Warning copy must include the Swedish phrase 'Kontakt-fält är "
        "platshållare' — operators see the badge but not the JSON."
    )
    # B158/B159 (2e0c55f, 2026-06-01): the published site no longer renders
    # the dummy values — it suppresses them and shows a generic contact CTA.
    # The warning copy must therefore say the fields are HIDDEN (real contact
    # info missing), not that visitors see dummies.
    assert "Sajten döljer fälten publikt" in panel_text, (
        "Warning copy must reflect post-B158/B159 behaviour: the site hides "
        "placeholder contact fields and shows a generic CTA instead of "
        "publishing dummy values. The old 'Slutanvändaren ser dummy-värden' "
        "copy is now factually wrong."
    )
    assert "Slutanvändaren ser dummy-värden" not in panel_text, (
        "Stale pre-suppression copy must be removed — it claims visitors see "
        "dummy contact values, which B158/B159 no longer do."
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
    inventeringen ``docs/archive/run-details-warnings-inventory-2026-05-21.md``
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
    panel_text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

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
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "buildStatus" in text, (
        "/api/prompt route.ts must include `buildStatus` in the response "
        "payload so PromptBuilder can classify the build outcome."
    )
    assert "extractBuildStatus" in text or "buildResult.status" in text, (
        "/api/prompt route.ts must read build-result.json:status to populate "
        "buildStatus on the response."
    )


def test_ui_textarea_forwards_ref_explicitly() -> None:
    """Lock the explicit `ref` forwarding in the shared Textarea wrapper.

    FloatingChat (``apps/viewser/components/builder/floating-chat.tsx``)
    auto-fokuserar composern när panelen expanderas från minimerat
    läge via ``composerRef.current?.focus()``. Det fungerar bara om
    Textarea-komponenten explicit destrukturerar ``ref`` ur props och
    vidarebefordrar den till underliggande ``<textarea>``.

    Tidigare läckte komponenten ref bara via ``{...props}``-spread,
    vilket är en bräcklig React 19-detalj (ref behandlas som vanlig
    prop sedan v19, men spread-vidarebefordran är inte garanterat
    dokumenterad). Den här testen låser explicit destruktur + bindning
    så en framtida refaktor inte tyst kan tappa ref:n och bryta
    auto-focus utan att någon märker det förrän en operator klagar.
    """
    text = (VIEWSER_DIR / "components" / "ui" / "textarea.tsx").read_text(encoding="utf-8")
    # Destruktur av `ref` ur funktionssignaturen — det är detta som
    # gör ref tillgänglig som en explicit referens istället för att
    # gömmas i `...props`.
    assert "ref,\n" in text or "ref," in text, (
        "Textarea måste destrukturera `ref` ur sina props så ref-"
        "vidarebefordran är explicit. Förlita dig inte på att "
        "{...props}-spread implicit propsar ref."
    )
    # `ref={ref}` på <textarea>-elementet — den faktiska bindningen.
    assert "ref={ref}" in text, (
        "Textarea måste explicit binda `ref={ref}` på underliggande "
        "<textarea>-element så DOM-noden exponeras för callers som "
        "FloatingChat:s composerRef auto-focus."
    )


def test_floating_chat_composer_ref_used_for_expand_focus() -> None:
    """Anti-regression för auto-focus-flödet i FloatingChat.

    När operatören klickar på den minimerade FAB:en/sidotab:en ska
    panelen expandera OCH focus flytta till composer-textarean i ett
    enda steg, så användaren kan börja skriva direkt utan att Tab:a
    sig in i fältet. Det här testet låser hela kedjan:
      1. composerRef tilldelas Textarea via `ref={composerRef}`
      2. expandAndFocus kallar `composerRef.current?.focus()`
      3. Minimerade FAB-knappen och sidotab-knappen routar onClick
         genom expandAndFocus (inte setIsMinimized(false) direkt).
    Tappar någon av dessa bryts mobil-/desktop-fokuseringen tyst.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "composerRef" in text, (
        "FloatingChat måste ha en composerRef för att kunna flytta focus till textarean vid expand."
    )
    assert "ref={composerRef}" in text, (
        "FloatingChat:s Textarea måste få `ref={composerRef}` så "
        "expand-focus-flödet kan referera DOM-noden."
    )
    assert "composerRef.current?.focus()" in text, (
        "expandAndFocus måste anropa composerRef.current?.focus() — "
        "annars stannar tangentbords-focus på FAB-knappen efter "
        "expand och operatören måste Tab:a sig in i textfältet."
    )
    assert "onClick={expandAndFocus}" in text, (
        "Både mobil-FAB och desktop-sidotab måste routa sin onClick "
        "genom expandAndFocus, inte setIsMinimized(false) direkt — "
        "annars sker ingen focus-flytt vid återöppning."
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
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert '"application/x-ndjson"' in text, (
        "/api/prompt route.ts måste exponera content-type 'application/x-ndjson' "
        "när Accept-headern begär stream-läge."
    )
    assert "ReadableStream" in text, (
        "/api/prompt route.ts måste returnera en ReadableStream när klienten begär NDJSON-läge."
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
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "classifyBuildStatus" in text, (
        "prompt-builder.tsx must export/use a classifyBuildStatus helper "
        "that maps build-result.json:status to ok/degraded/failed/unknown."
    )
    assert "PromptBuildOutcome" in text, (
        "prompt-builder.tsx must expose a PromptBuildOutcome type so page.tsx "
        "can render an outcome-aware header instead of a hard-coded 'Build klar'."
    )
    for stage_literal in (
        '"degraded"',
        '"failed"',
    ):
        assert stage_literal in text, (
            f"prompt-builder.tsx must distinguish stage {stage_literal} so "
            "degraded/failed builds do not render as success."
        )
    assert "Build klar med varning" in text, (
        "prompt-builder.tsx must render a degraded headline distinct from the success banner."
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
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
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
        "build-runner.ts saknar exitCode !== 0-gren - hela B40-kontraktet hänger på den."
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
        "Kunde inte hitta `if (exitCode !== 0) { ... }`-blocket i build-runner.ts."
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

    Tier 1 (2026-06-01): vi extraherade fetch-loopen till en
    återanvändbar ``loadRuns``-callback (för retry-knapp i
    runsLoadError-cardet). Guarden använder nu ``cancelledRef.current``
    istället för en bool-variabel ``cancelled``. Båda mönstren
    accepteras av denna regex.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    # Look for ``await fetchRuns()`` -> ``if (cancelled) return`` eller
    # ``if (cancelledRef?.current) return`` -> ``applyRunsData`` (eller
    # ``setRuns(``) ordering inside the same try-block. 0-300 character
    # window håller regexen tight.
    pattern = re.compile(
        r"await\s+fetchRuns\(\)[\s\S]{0,300}?"
        r"if\s*\(\s*(?:cancelled|cancelledRef\??\.current)\s*\)\s*return\s*;"
        r"[\s\S]{0,300}?(?:applyRunsData|setRuns\()",
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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
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
        "StackBlitz SDK kan rejecta med icke-Error-värden; de måste också renderas läsbart."
    )
    assert "whitespace-pre-wrap" in text and "<pre" in text, (
        "Viewer-feldetaljer måste renderas i ett pre-block så stackrader och radbrytningar bevaras."
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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

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
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    err_payload_idx = text.find("errPayload = (await previewResponse")
    assert err_payload_idx != -1, (
        "viewer-panel.tsx saknar `errPayload = (await previewResponse...` "
        "i IS_LOCAL_NEXT_MODE non-OK-grenen. Annars test kan inte ankra "
        "mellan parsen och state-skrivningen."
    )
    setunavail_idx = text.find("setUnavailable(unavailableForPreviewError", err_payload_idx)
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
        assert status in text, f"RunHistory saknar färg-mapping för status {status!r}."


@pytest.mark.tooling
def test_runs_lib_marks_stale_pending_runs_as_aborted() -> None:
    """Bug A: ett bygge som dödas mitt i (flik stängd, Cursor-omstart) hinner
    aldrig skriva build-result.json eller promota current.json, så runen
    fastnade `pending`/grå för evigt och vilseledde operatören. listRuns OCH
    readRunTrace måste i stället rapportera en pending-run som varit inaktiv
    längre än en timeout som `aborted` (röd), och båda måste dela samma gräns
    så Run History och trace-pollern är överens. Lås invarianterna här så en
    refactor inte tyst återinför grå-för-evigt-buggen.
    """
    runs_lib = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")

    assert '"aborted"' in runs_lib, (
        "RunStatus måste innehålla 'aborted' för avbrutna/stale-pending byggen."
    )
    assert "isStalePending" in runs_lib and "STALE_PENDING_TIMEOUT_MS" in runs_lib, (
        "runs.ts måste härleda stale-pending via en delad timeout (isStalePending "
        "+ STALE_PENDING_TIMEOUT_MS) så listRuns och readRunTrace är överens."
    )
    assert "VIEWSER_STALE_PENDING_MS" in runs_lib, (
        "Stale-pending-timeouten ska gå att justera via VIEWSER_STALE_PENDING_MS."
    )
    # Båda kodvägarna (lista + trace) måste markera aborted, annars pollar
    # use-build-trace-polling ett dött bygge i all oändlighet.
    assert runs_lib.count('"aborted"') >= 2, (
        "Både listRuns/buildPendingMeta och readRunTrace måste sätta 'aborted'."
    )

    run_history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    assert "aborted:" in run_history, (
        "RunHistory STATUS_DOT_COLORS måste mappa 'aborted' till en röd prick "
        "(annars faller den tillbaka till samma grå som pending)."
    )

    details = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
    assert "aborted:" in details, (
        "RunDetailsPanel STATUS_TONE måste mappa 'aborted' till fail-ton, inte neutral."
    )


@pytest.mark.tooling
def test_page_on_build_done_passes_apply_runs_context() -> None:
    """Stale-closure guard: after onBuildDone sets selectedRunId, the
    fetchRuns().then(applyRunsData) path must pass an explicit context
    snapshot so applyRunsData does not read a pre-build selectedRunId
    and reset selectedSiteId to the first Project Input.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
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
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")
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
    prompt_text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "runSiteIdUnknown" in prompt_text
    assert "follow-up kan inte" in prompt_text
    picker_text = (VIEWSER_DIR / "components" / "project-input-picker.tsx").read_text(
        encoding="utf-8"
    )
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


# ---------------------------------------------------------------------------
# B151+B152+B153 — AI Bug Review-fynd från PR #117 (mobile responsive).
# Source-lock-tester som verifierar fixarnas närvaro i TSX-filerna så de
# inte kan tas bort i framtida UI-refactor utan att testerna failar.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b151_floating_chat_useismobile_feature_detects_addeventlistener() -> None:
    """B151: useIsMobileViewport måste feature-detect:a addEventListener på
    matchMedia-resultatet. iOS Safari < 14 stödjer bara den deprecated
    addListener-/removeListener-signaturen, så ovillkorlig
    ``mq.addEventListener("change", ...)`` kraschar chatten på äldre
    iOS-enheter. AI Bug Review (P 79 %, impact 8/10) flaggade detta på
    PR #117.

    Locks:
      1. ``typeof mq.addEventListener === "function"``-checken finns.
      2. Fallback-grenen anropar ``addListener`` / ``removeListener``
         via en legacy-cast (TS-typen finns inte i lib.dom utan klassisk
         matchMedia-typing).
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    pattern_feature_detect = re.compile(
        r'typeof\s+mq\.addEventListener\s*===\s*["\']function["\']',
        re.MULTILINE,
    )
    assert pattern_feature_detect.search(text), (
        "floating-chat.tsx useIsMobileViewport saknar feature-detect mot "
        "``typeof mq.addEventListener === 'function'``. Krävs för iOS "
        "Safari < 14 fallback per B151."
    )

    pattern_legacy_fallback = re.compile(
        r"\.addListener\(\s*update\s*\)[\s\S]{0,200}?\.removeListener\(\s*update\s*\)",
        re.MULTILINE,
    )
    assert pattern_legacy_fallback.search(text), (
        "floating-chat.tsx useIsMobileViewport saknar legacy "
        "``addListener``/``removeListener``-fallback för iOS Safari < 14. "
        "Båda måste finnas så cleanup-funktionen avregistrerar listenern."
    )


@pytest.mark.tooling
def test_b152_compare_modal_pane_width_accounts_for_gap() -> None:
    """B152: compare-preview-modal PreviewPane använder
    ``w-[calc(100%-0.5rem)]`` istället för ``w-full`` så bredden
    kompenserar för parent-flex-rowens ``gap-2`` (0.5rem). Med ``w-full``
    + ``gap-2`` overflowade scrollern (200 % + 0.5rem) vilket lät pane-
    A:s högra kant smyga in i viewporten när snappat till pane B.
    AI Bug Review (P 88 %, impact 7/10) flaggade detta på PR #117.

    Lock: PreviewPane <section>-elementets className ska INTE innehålla
    ``flex min-h-0 w-full`` (gamla mönstret) utan ``w-[calc(100%-0.5rem)]``.
    """
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "compare-preview-modal.tsx"
    ).read_text(encoding="utf-8")

    pattern_fix = re.compile(
        r"w-\[calc\(100%-0\.5rem\)\][\s\S]{0,200}?snap-start",
        re.MULTILINE,
    )
    assert pattern_fix.search(text), (
        "compare-preview-modal.tsx PreviewPane måste använda "
        "``w-[calc(100%-0.5rem)]`` så pane-bredden + gap-2 = 100 % per "
        "snap-segment. ``w-full`` + ``gap-2`` overflowar scrollern och "
        "bryter one-pane-snap (B152)."
    )

    # Negative: säkerställ att gamla mönstret ``w-full shrink-0 snap-start``
    # inte finns kvar (skulle vara regression).
    pattern_regression = re.compile(
        r"w-full\s+shrink-0\s+snap-start",
        re.MULTILINE,
    )
    assert not pattern_regression.search(text), (
        "compare-preview-modal.tsx har återgått till ``w-full shrink-0 "
        "snap-start`` per pane (B152-regression). Måste vara "
        "``w-[calc(100%-0.5rem)]`` för att kompensera för parent gap-2."
    )


@pytest.mark.tooling
def test_b153_device_preset_hydrates_full_device_preset() -> None:
    """B153: sessionStorage-hydration måste inkludera
    ``"full"`` bland accepterade DevicePreset-värden. Tidigare listades bara
    ``"mobile"``/``"tablet"``/``"laptop"`` så en sparad ``"full"``-preset
    relied på att default-värdet råkade vara ``"full"``. Inkonsekvent
    med övriga preset-värden (alla restoreras explicit) och om default
    någonsin ändras tappas ``"full"``. AI Bug Review (P 84 %, impact
    5/10) flaggade detta på PR #117.

    Hydration-logiken flyttades 2026-05-26 från ``viewer-panel.tsx`` till
    den nya ``device-preset-context.tsx`` så toggle-UI:t kunde lyftas in i
    FloatingChat:s footer utan prop-drilling. Testet följer hydrationen
    dit; B153-fixen lever kvar i providern.

    Lock: hydration-checken ska innehålla alla fyra Device-värden.
    """
    text = (VIEWSER_DIR / "components" / "device-preset-context.tsx").read_text(encoding="utf-8")

    pattern = re.compile(
        r'stored\s*===\s*["\']mobile["\'][\s\S]{0,200}?'
        r'stored\s*===\s*["\']tablet["\'][\s\S]{0,200}?'
        r'stored\s*===\s*["\']laptop["\'][\s\S]{0,200}?'
        r'stored\s*===\s*["\']full["\']',
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "device-preset-context.tsx sessionStorage-hydration saknar "
        "``stored === 'full'`` i listan av accepterade DevicePreset-värden. "
        "Alla fyra preset-värden måste restoreras explicit per B153 — "
        "annars bryts persistensen för 'full' om default-värdet någonsin "
        "ändras."
    )


@pytest.mark.tooling
def test_b155_floating_chat_reads_applied_visible_effect() -> None:
    """B155 (2026-05-30): FloatingChat måste läsa ``appliedVisibleEffect``
    från ``build-result.json`` (auktoritativ källa enligt Jakobs
    PR #136). Trace-eventet ``followup.no_op_detected`` skickar samma
    information men ``parseTraceLine`` plockar bara sju kända fält så
    UI-skiktet får inte bero på trace-payloaden.

    Kontraktet låser tre saker:
      1. ``PromptApiResponse`` exponerar ``buildResult`` så fältet faktiskt
         når success-grenen i ``summarizeBuildResult``.
      2. En extractor läser specifikt ``appliedVisibleEffect`` (boolean)
         och ``appliedVisibleEffectReason`` (string) — annars riskerar vi
         att vi börjar parsa trace-eventets ``reason`` av bekvämlighet.
      3. När ``applied === false`` byts success-bubblan till en ärlig
         info-rad i stil med "Ingen synlig ändring fångades" — så
         operatören inte luras tro att fri-text-följdprompten landade.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "buildResult?: Record<string, unknown>" in text, (
        "PromptApiResponse måste deklarera ``buildResult`` så följdprompts "
        "build-result.json når summarizeBuildResult — annars kan UI:t inte "
        "läsa appliedVisibleEffect."
    )
    assert "buildResult.appliedVisibleEffect" in text, (
        "FloatingChat måste läsa ``appliedVisibleEffect`` från build-result "
        "(auktoritativ källa per B155). Trace-eventet är inte ett godkänt "
        "alternativ — parseTraceLine plockar inte ``reason``-fältet."
    )
    assert "appliedVisibleEffectReason" in text, (
        "Reason-fältet måste finnas i extraheringen så vi kan utvidga "
        "info-bubblan med varför ingen synlig effekt sågs (ADR 0034 path)."
    )
    assert "extractAppliedVisibleEffect" in text, (
        "Helper ``extractAppliedVisibleEffect`` ska kapsla boolean-checken "
        "så den inte upprepas i flera grenar — om operatören får en "
        "follow-up som bygger ok men flippar appliedVisibleEffect=false "
        "ska info-grenen fortfarande träffa."
    )
    assert "Jag kunde inte fånga någon synlig ändring" in text, (
        "Den ärliga raden måste ha en igenkännbar text-anchor (ADR-stil) "
        "så fil-disciplin inte tappar B155 under refaktorisering. "
        "Texten matchar Jakobs handoff för ADR 0034 väg B."
    )


@pytest.mark.tooling
def test_b155_floating_chat_no_op_does_not_claim_success() -> None:
    """B155: säkerställ att success-grenen i ``summarizeBuildResult``
    *inte* returnerar variant ``"success"`` när ``appliedVisibleEffect``
    är ``false``. Pattern matchar att info-grenen kommer FÖRE
    standardsuccess-grenen i koden, och att den explicit sätter
    variant ``"info"``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    pattern = re.compile(
        r"effect\.applied\s*===\s*false[\s\S]{0,400}?"
        r'variant:\s*"info"',
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "Info-grenen för B155 (no-op-followup) saknas eller har bytt form. "
        "När backend rapporterar ``appliedVisibleEffect: false`` ska UI:t "
        'byta success-bubblan till variant ``"info"`` med en ärlig text '
        "— annars luras operatören att tro att följdprompten landade."
    )


@pytest.mark.tooling
def test_floating_chat_differentiates_layout_no_op_honestly() -> None:
    """Bug B-ärlighet: deterministisk codegen-v1 kan ÄNNU inte göra layout-/
    strukturändringar (centrera hero, lägg till gallery) — de blir ärliga
    no-ops med ``appliedVisibleEffectReason: "visible_files_unchanged"``. Att
    då be operatören vara "mer exakt" (samma råd som för
    ``intent_no_semantic_change``) vore vilseledande: problemet är saknad
    codegen-kapabilitet, inte otydlighet. FloatingChat måste därför skilja på
    de två no-op-orsakerna och säga ärligt att layout/struktur inte stöds än,
    utan att lova en synlig ändring. Riktig codegenModel för dessa intents är
    Sprint 3B (backend-lane) — den här testen låser bara UI-ärligheten.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert '"visible_files_unchanged"' in text, (
        "FloatingChat måste gren-skilja på reason ``visible_files_unchanged`` "
        "(bygget gav identiska filer → layout/struktur stöds inte än) från "
        "``intent_no_semantic_change`` (be om konkret text)."
    )
    # Layout-grenen får INTE råda operatören att bara vara mer specifik — den
    # ska ärligt säga att större layout/struktur-ändringar inte stöds än.
    assert "stöds inte än" in text, (
        "Layout-no-op-grenen måste ärligt säga att layout/struktur inte stöds "
        "än, i st.f. att antyda att otydlighet var problemet."
    )
    # Den layout-specifika grenen måste komma FÖRE den generiska
    # 'mer specifik'-raden så rätt råd vinner. Och båda måste vara info,
    # aldrig success (regression-skyddat separat i no_op_does_not_claim_success).
    layout_idx = text.index('"visible_files_unchanged"')
    generic_idx = text.index("Jag kunde inte fånga någon synlig ändring")
    assert layout_idx < generic_idx, (
        "Layout-grenen (visible_files_unchanged) måste utvärderas före den "
        "generiska 'ange exakt rubrik/text'-raden."
    )


@pytest.mark.tooling
def test_floating_chat_router_decision_readiness() -> None:
    """KÖR-6a readiness: FloatingChat måste kunna ge en ärlig rad per
    ``RouterDecision.messageKind`` OM/NÄR ``/api/prompt`` börjar skicka
    ``routerDecision`` — utan att ändra dagens beteende (fältet skickas inte
    än; classify_message konsumeras bara internt i patch/+context/, follow-up-
    bryggan kor-7d/#176 wirar in det).

    Locks (graceful degradation + ärlighet, samma mönster som
    appliedVisibleEffect):
      1. ``PromptApiResponse`` exponerar ett valfritt ``routerDecision``-fält.
      2. En defensiv ``extractRouterDecision`` läser fältet utan att lita på
         dess typ och returnerar null när det saknas → oförändrat beteende.
      3. ``summarizeRouterDecision`` grenar på de messageKind/buildRequirement
         som routern äger och som UI:t måste vara ärligt om.
      4. Preempten körs INNAN success-/no-op-grenarna i summarizeBuildResult,
         men edit/multi_intent med targeted_rebuild/full_rebuild faller igenom
         (→ null) så den vanliga bygg-summeringen (Bug B) tar vid.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "routerDecision?: Record<string, unknown>" in text, (
        "PromptApiResponse måste exponera ett valfritt routerDecision-fält "
        "(speglar router-decision.schema.json) så UI:t kan tändas när backend "
        "börjar skicka det — utan ny deploy."
    )
    assert "function extractRouterDecision(" in text, (
        "FloatingChat måste läsa routerDecision defensivt (extractRouterDecision), "
        "exakt som extractAppliedVisibleEffect, så ett saknat/okänt fält ger null."
    )
    assert "function summarizeRouterDecision(" in text, (
        "FloatingChat måste härleda en ärlig rad per messageKind (summarizeRouterDecision)."
    )

    # Alla messageKind ur schemat som UI:t måste kunna bemöta ärligt.
    for kind in (
        '"answer_only"',
        '"site_review"',
        '"reference_analysis"',
        '"component_discovery"',
        '"multi_intent"',
        '"unclear"',
    ):
        assert kind in text, (
            f"summarizeRouterDecision måste hantera messageKind {kind} "
            "(annars är readiness-kontraktet ofullständigt mot schemat)."
        )

    # Plan-only/patch-only edits får inte låtsas vara klara: ärlig rad om att
    # bygget som gör ändringen synlig inte är klart än (orchestrator-punkt 5).
    assert '"plan_only"' in text and '"artifact_patch_only"' in text, (
        "summarizeRouterDecision måste skilja plan_only/artifact_patch_only "
        "(plan skapad, inget synligt bygge än) från targeted_rebuild/full_rebuild."
    )

    # Preempten måste ligga FÖRE den vanliga bygg-summeringen så ett router-
    # beslut för icke-bygg-utfall vinner över "Klart!"-raden.
    preempt_idx = text.index("const routerView = extractRouterDecision(payload)")
    ok_branch_idx = text.index('if (outcome === "ok") {')
    assert preempt_idx < ok_branch_idx, (
        "Router-preempten måste utvärderas innan outcome==='ok'-grenen så vi "
        "aldrig visar bygg-success för det routern klassat som fråga/oklart/"
        "referens/discovery/plan-only."
    )

    # B1 (2026-06-05): router-preempten får BARA köra på outcome==='ok'. Annars
    # döljer router-raden (variant 'info') den auktoritativa failed/degraded-
    # grenen och operatören tappar 'Försök igen' (retryPrompt sätts bara på
    # variant 'error'). Lås att gaten finns.
    assert 'if (routerView && outcome === "ok")' in text, (
        "Router-preempten måste vara gated på outcome==='ok' så ett misslyckat "
        "eller degraderat bygge aldrig döljs bakom en router-info-rad (och "
        "behåller 'Försök igen')."
    )

    # Ärlighets-nyans (2026-06-05): en ``unclear``/``requiresClarification``-
    # gissning får INTE preempta när bygget faktiskt rapporterade ett
    # auktoritativt no-op-skäl (B155 ``appliedVisibleEffect.applied === false``).
    # Då är B155-raden ärligare ("kan bara ändra texter, layout stöds ej än")
    # än routerns "jag förstår inte vad du menar" över en tydlig men ej stödd
    # förfrågan ("gör hero-knappen större" klassas deterministiskt som unclear).
    # Preempt-regionen måste alltså konsultera bygg-sanningen innan den fyrar.
    preempt_region = text[preempt_idx:ok_branch_idx]
    assert "extractAppliedVisibleEffect(payload.buildResult)" in preempt_region, (
        "Router-preempten måste läsa appliedVisibleEffect så unclear/"
        "requiresClarification kan lämna över till den mer specifika B155-"
        "no-op-raden när bygget redan rapporterat varför inget syntes."
    )
    assert "requiresClarification" in preempt_region and "unclear" in preempt_region, (
        "Defer-till-bygg-sanningen måste vara begränsad till unclear/"
        "requiresClarification — övriga router-utfall (fråga/referens/discovery/"
        "bug/plan-only) ska fortsatt preempta med sin mer specifika rad."
    )

    # Graceful: edit/multi_intent som krävde ett synligt bygge ska falla igenom
    # till den vanliga summeringen (Bug B m.m.) — summarizeRouterDecision ska
    # alltså ha en gren som returnerar null.
    summarize_start = text.index("function summarizeRouterDecision(")
    summarize_end = text.index("function summarizeBuildResult(")
    summarize_body = text[summarize_start:summarize_end]
    assert "return null;" in summarize_body, (
        "summarizeRouterDecision måste returnera null för bygg-krävande edits "
        "(targeted_rebuild/full_rebuild) så den vanliga bygg-summeringen tar vid."
    )


@pytest.mark.tooling
def test_openclaw_runner_spawns_followup_seam() -> None:
    """Skiva 1b (UI half): ``lib/openclaw-runner.ts`` måste shella till
    ``scripts/run_openclaw_followup.py`` med exakt samma spawn-mönster som
    ``router-classify-runner.ts`` — och ALDRIG kunna krascha /api/prompt.

    Locks:
      1. Exporterar ``runOpenClawFollowup`` + ``OpenClawDecisionPayload``.
      2. Spawnar rätt scripts/-seam (repo-boundaries: viewser importerar aldrig
         packages/ direkt — Python-scriptet äger importen).
      3. ``--`` -separatorn finns så en prompt som börjar med ``-`` inte tolkas
         som ett CLI-flagga, och --site-id/--base-run-id skickas vidare.
      4. En timeout + degradering till ``null`` (read-only metadata får aldrig
         bli en 500 på bygg-routen).
    """
    text = (VIEWSER_DIR / "lib" / "openclaw-runner.ts").read_text(encoding="utf-8")

    assert "export async function runOpenClawFollowup" in text, (
        "openclaw-runner.ts måste exportera runOpenClawFollowup så /api/prompt "
        "kan konsumera OpenClaw-beslutet."
    )
    assert "export type OpenClawDecisionPayload" in text, (
        "Exportera OpenClawDecisionPayload-typen (loose record som speglar "
        "OpenClawDecision.model_dump())."
    )
    assert "run_openclaw_followup.py" in text, (
        "Runnern måste spawna scripts/run_openclaw_followup.py (skiva-1b-seamen)."
    )
    assert 'args.push("--", trimmed)' in text, (
        "``--``-separatorn måste finnas så en prompt som börjar med - inte "
        "tolkas som ett argparse-flagga."
    )
    assert '"--site-id"' in text and '"--base-run-id"' in text, (
        "siteId + baseRunId måste skickas till seamen för RouterContext/"
        "context-assembly."
    )
    assert "setTimeout(" in text and "child.kill()" in text, (
        "Runnern måste timeouta + döda subprocessen så en hängd Python inte "
        "wedge:ar bygg-routen."
    )
    # Degraderingen: minst en `return null;` så fel/timeout aldrig 500:ar.
    assert "return null;" in text, (
        "Alla felvägar måste degradera till null (aldrig kasta upp i "
        "/api/prompt-flödet)."
    )


@pytest.mark.tooling
def test_openclaw_runner_apply_bridge_seam() -> None:
    """Skiva 1b (action half): ``lib/openclaw-runner.ts`` måste exponera
    ``runOpenClawFollowupApply`` som shellar ``run_openclaw_followup.py --apply``
    och returnerar ``{decision, bridge}`` — och ALDRIG krascha /api/prompt.

    Locks:
      1. Exporterar ``runOpenClawFollowupApply`` + apply-result-/bridge-typerna.
      2. Skickar ``--apply`` + ``--site-id`` (apply kräver en konkret sajt).
      3. Tree-killar subprocessen vid timeout (--apply spawnar npm/next-barn —
         ett plain child.kill() vore en process-/fil-lås-läcka, B157-klassen).
      4. Parsar ut ``decision`` + ``bridge`` och degraderar till ``null`` vid fel.
    """
    text = (VIEWSER_DIR / "lib" / "openclaw-runner.ts").read_text(encoding="utf-8")

    assert "export async function runOpenClawFollowupApply" in text, (
        "openclaw-runner.ts måste exportera runOpenClawFollowupApply (action-"
        "bryggan som /api/prompt rutar follow-ups genom)."
    )
    assert (
        "export type OpenClawApplyResult" in text
        and "export type OpenClawBridge" in text
    ), (
        "Exportera apply-result/bridge-typerna ({decision, bridge:{status, "
        "applied, previewShouldRefresh, chain}})."
    )
    assert '"--apply"' in text and '"--site-id"' in text, (
        "Apply-bryggan måste skicka --apply + --site-id (kräver en konkret sajt)."
    )
    # Tree-kill istället för plain child.kill() i apply-vägen (npm/next-barn).
    assert "killProcessTree(child" in text, (
        "Apply-vägen måste tree-killa subprocess-trädet vid timeout (npm/next "
        "spawnas som barn — child.kill() lämnar dem som läckande processer)."
    )
    apply_start = text.index("export async function runOpenClawFollowupApply")
    apply_body = text[apply_start:]
    assert "obj.decision" in apply_body and "coerceBridge(" in apply_body, (
        "Runnern måste parsa ut både decision och bridge ur scriptets stdout."
    )
    assert "return null;" in apply_body, (
        "Alla felvägar i apply-runnern måste degradera till null (aldrig 500:a "
        "bygg-routen)."
    )


@pytest.mark.tooling
def test_prompt_route_exposes_openclaw_decision() -> None:
    """Skiva 1b (action bridge): ``/api/prompt`` måste ruta follow-ups genom
    OpenClaw-apply-bryggan och, när den materialiserade en ändring, exponera
    den runen som det auktoritativa bygget — annars falla tillbaka på legacy
    med samma ärlighetsgrind för ``openClawDecision``.

    Locks:
      1. Routen importerar + anropar runOpenClawFollowupApply.
      2. Anropet är gated på ``payload.mode === "followup"`` (init-flödet är
         byte-för-byte oförändrat).
      3. När ``bridge.applied`` + ``chain.runId`` finns re-surface:as den runen
         (ingen legacy-build → ingen dubbel-build).
      4. Samma legacyPathAppliedVisibleChange-grind nollar beslutet på fallback-
         vägen; ``openClawDecision`` (härledd ur bryggans decision) + ``bridge``
         ligger i return-objektet (NDJSON-vägen sprider ``...result``).
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )

    assert (
        'import { runOpenClawFollowupApply } from "@/lib/openclaw-runner"' in text
    ), "route.ts måste importera apply-bryggan (runOpenClawFollowupApply)."
    assert "runOpenClawFollowupApply(payload.prompt" in text, (
        "Routen måste anropa apply-bryggan med prompten."
    )
    # Gated på follow-up: init-flödet ska inte spawna bryggan.
    call_idx = text.index("runOpenClawFollowupApply(payload.prompt")
    gate_region = text[text.index("const applyResult") : call_idx]
    assert 'payload.mode === "followup"' in gate_region, (
        "Apply-bryggan får bara köras på follow-ups (init-flödet oförändrat)."
    )
    # När bryggan applicerade: använd dess chain.runId som det riktiga bygget.
    assert "applyResult.bridge.applied" in text, (
        "Routen måste gren:a på bridge.applied (materialiserad ändring)."
    )
    assert "chain.runId" in text, (
        "Den applicerade bryggans chain.runId måste re-surface:as som runId så "
        "klientens preview-refresh-flöde fungerar oförändrat (ingen dubbel-build)."
    )
    assert "const openClawDecision = legacyPathAppliedVisibleChange" in text, (
        "Samma honesty-gate som routerDecision på fallback-vägen: nolla "
        "beslutet när den gamla vägen redan applicerade en synlig ändring."
    )
    # openClawDecision härleds nu ur bryggans decision-fält (ingen andra spawn).
    assert "applyResult?.decision" in text, (
        "openClawDecision ska komma från apply-bryggans decision-fält."
    )
    # Både openClawDecision och bridge måste ligga i return-objektet.
    return_idx = text.index("routerDecision,\n")
    assert text.index("openClawDecision,", return_idx) > return_idx, (
        "openClawDecision måste returneras (NDJSON sprider ...result)."
    )
    assert "bridge: applyResult" in text, (
        "bridge-utfallet måste returneras så FloatingChat kan visa en ärlig "
        "restyle/capability-rad + preview-refresh-status."
    )


@pytest.mark.tooling
def test_floating_chat_renders_openclaw_bridge_honestly() -> None:
    """Skiva 1b (action half): FloatingChat måste visa OpenClaw-apply-utfallet
    ärligt — en success-rad NÄR bryggan materialiserade en ändring, annars
    falla tillbaka på den vanliga summeringen (lovar aldrig en ändring som inte
    landade).

    Locks:
      1. ``PromptApiResponse`` exponerar ett valfritt ``bridge``-fält.
      2. Defensiv ``extractOpenClawBridge`` + ``summarizeOpenClawBridge`` (bara
         success när applied=true; null annars).
      3. Bridge-preempten ligger FÖRE openClawView och är gated på
         ``bridgeView.applied`` + outcome === "ok".
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "bridge?: Record<string, unknown>" in text, (
        "PromptApiResponse måste exponera ett valfritt bridge-fält."
    )
    assert "function extractOpenClawBridge(" in text, (
        "FloatingChat måste läsa bridge defensivt (extractOpenClawBridge)."
    )
    assert "function summarizeOpenClawBridge(" in text, (
        "FloatingChat måste härleda en ärlig success-rad (summarizeOpenClawBridge)."
    )
    # summarizeOpenClawBridge får BARA ge en rad när applied=true.
    summarize_start = text.index("function summarizeOpenClawBridge(")
    summarize_body = text[summarize_start : summarize_start + 1800]
    assert "if (!view.applied) return null;" in summarize_body, (
        "summarizeOpenClawBridge måste returnera null när inget applicerades "
        "(vi lovar aldrig en ändring som bryggan inte materialiserade)."
    )
    # Honesty split (Vercel-agent-fynd 2026-06-08): applied=true men
    # previewShouldRefresh=false (mount-only, ingen synlig effekt) får INTE säga
    # "Jag genomförde ändringen" — då blir det en falsk success. Grinda på
    # previewShouldRefresh och ge en ärlig info-rad i stället.
    assert "if (!view.previewShouldRefresh) {" in summarize_body, (
        "summarizeOpenClawBridge måste grinda den synliga success-raden på "
        "previewShouldRefresh (annars lovar en mount-only-montering en synlig "
        "ändring som inte syns)."
    )
    assert 'variant: "info"' in summarize_body, (
        "Mount-only-utfallet (applied men inte synligt) ska vara en ärlig "
        "info-rad, inte en success-rad."
    )
    # Bridge-preempten ligger FÖRE openClawView-preempten och är gated rätt.
    bridge_preempt_idx = text.index(
        "const bridgeView = extractOpenClawBridge(payload)"
    )
    openclaw_preempt_idx = text.index(
        "const openClawView = extractOpenClawDecision(payload)"
    )
    assert bridge_preempt_idx < openclaw_preempt_idx, (
        "Bridge-utfallet (en faktiskt landad ändring) måste preempta FÖRE "
        "OpenClaw-beslutet (som annars säger 'inte inkopplad än')."
    )
    assert 'bridgeView.applied && outcome === "ok"' in text, (
        "Bridge-preempten måste vara gated på applied + outcome ok (failed/"
        "degraded faller igenom till den auktoritativa fel-/varningsgrenen)."
    )


@pytest.mark.tooling
def test_add_module_dialog_only_offers_backend_mountable_modules() -> None:
    """Vercel-agent-fynd 2026-06-08: AddModuleDialog erbjöd hero/services/
    cta-banner som section_add, men de är INTE mountbara (hero/services är
    sidsektioner, cta-banner saknar dossier) -> falsk affordance. Lås att
    katalogen bara listar backend-mountbara moduler och att dialogen är ärlig
    om att exakt sida/position inte styrs av backend ännu."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "dialogs" / "add-module-dialog.tsx"
    ).read_text(encoding="utf-8")
    catalog_start = text.index("const MODULE_CATALOG")
    catalog_body = text[catalog_start : text.index("];", catalog_start)]
    for forbidden in ('id: "hero"', 'id: "services"', 'id: "cta-banner"'):
        assert forbidden not in catalog_body, (
            f"AddModuleDialog får inte erbjuda {forbidden} — backend kan inte "
            "montera den som section_add (falsk affordance)."
        )
    # The supported, dossier-backed modules stay offered.
    for supported in ('id: "gallery"', 'id: "faq"', 'id: "team"', 'id: "pricing"'):
        assert supported in catalog_body, (
            f"AddModuleDialog ska fortsatt erbjuda {supported} (backend-mountbar)."
        )
    # Honest about placement: the dialog must not promise exact page/position.
    assert "position är" in text and "kommer senare" in text, (
        "Dialogen måste vara ärlig om att exakt sida/position inte styrs av "
        "backend ännu (ingen överlovad placering)."
    )


@pytest.mark.tooling
def test_floating_chat_renders_openclaw_decision_honestly() -> None:
    """Skiva 1b (UI half): FloatingChat måste rendera OpenClaw-beslutet ärligt
    och preempta FÖRE routerDecision (rikare superset), med samma
    failed/degraded-grind.

    Locks:
      1. ``PromptApiResponse`` exponerar ett valfritt ``openClawDecision``-fält.
      2. Defensiv ``extractOpenClawDecision`` (okänd action → null →
         oförändrat beteende, faller tillbaka på routerDecision).
      3. ``summarizeOpenClawDecision`` hanterar alla fyra actions inkl. den
         ärliga patch_plan_request-raden ("inte inkopplad än").
      4. Preempten ligger FÖRE routerView och är gated på outcome === "ok".
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "openClawDecision?: Record<string, unknown>" in text, (
        "PromptApiResponse måste exponera ett valfritt openClawDecision-fält."
    )
    assert "function extractOpenClawDecision(" in text, (
        "FloatingChat måste läsa openClawDecision defensivt (extractOpenClawDecision)."
    )
    assert "function summarizeOpenClawDecision(" in text, (
        "FloatingChat måste härleda en ärlig rad per action (summarizeOpenClawDecision)."
    )
    assert "OPENCLAW_ACTIONS" in text, (
        "En allowlist av kända actions måste finnas så en okänd action ger null."
    )
    # Alla fyra actions ur OpenClawAction-enumen måste vara kända (allowlist)
    # och bemötas i besluts-regionen (patch_plan_request via fall-through).
    decision_start = text.index("const OPENCLAW_ACTIONS")
    decision_end = text.index("function summarizeBuildResult(")
    decision_body = text[decision_start:decision_end]
    for action in (
        '"answer_only"',
        '"clarification"',
        '"plan_only"',
        '"patch_plan_request"',
    ):
        assert action in decision_body, (
            f"OpenClaw-beslutsregionen måste känna till action {action}."
        )
    # patch_plan_request måste vara ärlig om att action-bryggan saknas.
    summarize_start = text.index("function summarizeOpenClawDecision(")
    summarize_body = text[summarize_start:decision_end]
    assert "inte inkopplad än" in summarize_body, (
        "patch_plan_request-raden måste ärligt säga att funktionen som utför "
        "ändringen inte är inkopplad än (V0 fejkar aldrig en success)."
    )
    # Preempten måste ligga FÖRE routerView och vara gated på outcome === "ok".
    openclaw_preempt_idx = text.index("const openClawView = extractOpenClawDecision(payload)")
    router_preempt_idx = text.index("const routerView = extractRouterDecision(payload)")
    assert openclaw_preempt_idx < router_preempt_idx, (
        "OpenClaw-beslutet (rikare superset) måste preempta FÖRE routerDecision."
    )
    assert 'if (openClawView && outcome === "ok")' in text, (
        "OpenClaw-preempten måste vara gated på outcome === 'ok' så ett "
        "misslyckat/degraderat bygge aldrig döljs bakom en info-rad."
    )


@pytest.mark.tooling
def test_b155_path_b_runs_lib_exports_applied_copy_directives() -> None:
    """ADR 0034 väg B (B155 path B): ``lib/runs.ts`` måste exportera
    ``readAppliedCopyDirectives`` + en strikt ``AppliedCopyDirective``-typ
    som speglar schema-enumen i
    ``governance/schemas/project-input.schema.json:directives.copyDirectives``.

    Locks:
      1. Funktionen finns och är exporterad så ``/api/prompt`` kan
         konsumera den utan att duplicera readern någonannanstans.
      2. Type-enumen matchar schema-värdena exakt
         (company-name | tagline; replace-text | include-token).
      3. Path-traversal-skyddet är på plats: läsaren begränsar
         dossierPath till ``data/prompt-inputs/`` eller ``examples/``
         under repo-root så en stulen ``input.json`` inte kan
         dirigera UI:t att läsa godtyckliga filer.
    """
    text = (VIEWSER_DIR / "lib" / "runs.ts").read_text(encoding="utf-8")

    assert "export async function readAppliedCopyDirectives" in text, (
        "lib/runs.ts måste exportera ``readAppliedCopyDirectives`` så "
        "/api/prompt-routen kan inkludera direktiven på response. "
        "Annars måste FloatingChat duplicera readern på client-sidan."
    )
    assert "export type AppliedCopyDirective" in text, (
        "AppliedCopyDirective-typen måste exporteras strikt-typad så "
        "client och server delar exakt samma shape (target/operation/"
        "payload/source-enum)."
    )
    enum_pattern = re.compile(
        r'target:\s*"company-name"\s*\|\s*"tagline"\s*\|\s*"about-text"'
        r'\s*\|\s*"services"[\s\S]{0,200}?'
        r'operation:\s*"replace-text"\s*\|\s*"include-token"',
        re.MULTILINE,
    )
    assert enum_pattern.search(text), (
        "AppliedCopyDirective-enumen måste låsa alla fyra schema-targets "
        "(company-name|tagline|about-text|services) och operation="
        "replace-text|include-token så schema-drift fångas i typecheck "
        "istället för att läcka okända värden till UI:t."
    )
    assert "targetRef?: string" in text, (
        "AppliedCopyDirective måste bära ``targetRef`` (services[].id|label) "
        "så ett services-direktiv kan peka ut vilken tjänst som ändrades — "
        "schemat kräver fältet när target=services."
    )
    # Schemat (project-input.schema.json:226-234) gör targetRef OBLIGATORISK när
    # target=services. Läsaren måste enforca det och SLÄNGA services-direktiv som
    # saknar giltig targetRef — annars läcker de igenom och UI:t faller tillbaka
    # på den generiska "Jag uppdaterade en tjänst."-raden som tappar VILKEN
    # tjänst som ändrades (operatörskontext).
    drop_guard = re.compile(
        r'candidate\.target\s*===\s*"services"\s*&&\s*!targetRefValid',
        re.MULTILINE,
    )
    assert drop_guard.search(text), (
        "readAppliedCopyDirectives måste droppa services-direktiv utan giltig "
        "targetRef (schema-required) i stället för att visa den generiska "
        '"uppdaterade en tjänst"-raden. Saknas drop-guarden bryter UI:t mot '
        "schema-kontraktet och tappar operatörskontext."
    )
    assert 'path.resolve(root, "data", "prompt-inputs")' in text and (
        'path.resolve(root, "examples")' in text
    ), (
        "Path-traversal-skyddet i readAppliedCopyDirectives måste vitlista "
        "data/prompt-inputs/ + examples/ under repo-root. Utan denna guard "
        "kan en stulen input.json dirigera UI:t att läsa godtyckliga filer."
    )


@pytest.mark.tooling
def test_b155_path_b_prompt_route_exposes_applied_copy_directives() -> None:
    """``/api/prompt`` måste returnera ``appliedCopyDirectives`` på
    top-level efter en build så FloatingChat har direkt tillgång till
    fältet utan att behöva en separat round-trip.

    Auktoritetskedjan: build_site.py skriver project-input-snapshotet
    till dossierPath, prompt-routen läser via readAppliedCopyDirectives,
    UI:t härleder svenska success-rader. Vi kontrollerar det mellersta
    steget här.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")

    assert "readAppliedCopyDirectives" in text, (
        "/api/prompt måste anropa readAppliedCopyDirectives efter att "
        "runBuild returnerar — annars är fältet alltid undefined på "
        "wire och path B-success-raden kan aldrig skickas."
    )
    assert "appliedCopyDirectives" in text, (
        "Top-level-fältet måste finnas i return-objektet från "
        "runPromptBuildOnce. Utan det kan FloatingChat inte härleda "
        "några svenska success-rader."
    )


@pytest.mark.tooling
def test_b155_path_b_floating_chat_summarises_copy_directives() -> None:
    """ADR 0034 väg B (B155 path B): FloatingChat måste härleda en svensk
    success-rad per applicerat copy-direktiv enligt Jakobs handoff:
      - target=company-name → "Jag ändrade företagsnamnet till '...'."
      - target=tagline + operation=replace-text → "Jag uppdaterade rubriken till '...'."
      - target=tagline + operation=include-token → "Jag la in '...' i hero-texten."

    Pattern verifierar att payload renderas via template-strängen (textnod
    i React) och inte via ``dangerouslySetInnerHTML`` — payload kommer från
    operatören och måste alltid escapas.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    assert "function summarizeCopyDirectives" in text, (
        "Helper ``summarizeCopyDirectives`` ska kapsla mappningen från "
        "AppliedCopyDirective[] till svenska rader så success-grenen i "
        "summarizeBuildResult inte blandar mappnings-logik med dispatch."
    )
    assert "Jag ändrade företagsnamnet till" in text, (
        "Mappningen för target=company-name saknas eller har bytt form. "
        "Jakobs handoff kräver exakt rad-prefix för operatör-igenkänning."
    )
    assert "Jag uppdaterade rubriken till" in text, (
        "Mappningen för target=tagline + operation=replace-text saknas eller har bytt form."
    )
    assert "Jag la in" in text and "i hero-texten" in text, (
        "Mappningen för target=tagline + operation=include-token saknas eller har bytt form."
    )
    # Slice 2a/2c: about-text + services måste också ge en ärlig rad nu när
    # backend-läsaren (lib/runs.ts) släpper igenom dem (annars syns följdprompt
    # mot om oss-texten/tjänster aldrig i FloatingChat — current-focus #5).
    assert "Jag skrev om om oss-texten" in text, (
        "Mappningen för target=about-text saknas. Om oss-följdprompter måste "
        "bekräftas i FloatingChat (utan att eka hela 600-teckens-payloaden)."
    )
    assert 'Jag uppdaterade tjänsten "' in text and "targetRef" in text, (
        "Mappningen för target=services saknas. Tjänst-följdprompter måste "
        "bekräftas med tjänstnamnet (targetRef), inte den långa summaryn."
    )
    assert "appliedCopyDirectives" in text, (
        "PromptApiResponse måste exponera ``appliedCopyDirectives`` så "
        "summarizeBuildResult kan plocka fältet utan att casta till "
        "Record<string, unknown>."
    )


@pytest.mark.tooling
def test_b155_path_b_floating_chat_does_not_inject_payload_as_html() -> None:
    """Säkerhet: copyDirective.payload är en validerad sträng från
    backend men kommer ursprungligen från operatörens prompt. Den
    måste alltid renderas som textnod, aldrig via
    ``dangerouslySetInnerHTML``.

    Vi söker bara JSX-attribut-användning (``dangerouslySetInnerHTML=``
    eller ``dangerouslySetInnerHTML:``) — kommentar-referenser som
    förklarar varför vi *inte* använder det räknas inte. Om någon
    framtida feature behöver det måste den medvetet introduceras i en
    separat komponent och vi uppdaterar testet då.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    jsx_use_pattern = re.compile(r"dangerouslySetInnerHTML\s*[=:]")
    assert not jsx_use_pattern.search(text), (
        "floating-chat.tsx får inte använda dangerouslySetInnerHTML på "
        "JSX-element eller i config-object — copyDirective.payload härstammar "
        "från operatörens prompt och måste renderas som textnod via React's "
        "automatic escape."
    )


# --- UI-gap-fix: exakt change-set i FloatingChat (2026-06-02) --------------
#
# Jakobs flagga: listan "Troligen ändrat" i FloatingChat var en
# prompt-heuristik, inte en backend-diff. Christopher-lane efter PR:
# härled en EXAKT change-set serverside genom att diffa nya runen mot
# föregående och visa den under "Ändrat". Dessa source-lock-tester hindrar
# att den exakta vägen tystas bort i en framtida refactor.


@pytest.mark.tooling
def test_change_set_helper_reuses_run_diff() -> None:
    """``lib/run-change-set.ts`` ska härleda change-set:en genom att
    återanvända den pure ``computeRunDiff`` + ``readRunArtefacts`` — inte
    genom att duplicera diff-logik eller röra build_site.py.
    """
    path = VIEWSER_DIR / "lib" / "run-change-set.ts"
    assert path.exists(), "run-change-set.ts saknas — exakt change-set kan inte härledas."
    text = path.read_text(encoding="utf-8")
    assert "export async function readRunChangeSet" in text, (
        "readRunChangeSet måste exporteras så /api/prompt kan kalla den."
    )
    assert "computeRunDiff" in text and "readRunArtefacts" in text, (
        "Change-set:en ska byggas på befintliga artefakter via computeRunDiff "
        "+ readRunArtefacts — ingen ny diff-implementation, ingen "
        "build_site.py-ändring."
    )


@pytest.mark.tooling
def test_prompt_route_exposes_change_set() -> None:
    """``/api/prompt`` måste anropa ``readRunChangeSet`` och exponera
    ``changeSet`` på top-level för follow-ups så FloatingChat kan rendera
    exakta deltas utan en separat round-trip.
    """
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "readRunChangeSet" in text, (
        "/api/prompt måste anropa readRunChangeSet efter runBuild — annars "
        "är changeSet alltid undefined och den exakta vägen kan aldrig användas."
    )
    assert "changeSet" in text, "changeSet måste ligga i return-objektet från runPromptBuildOnce."


@pytest.mark.tooling
def test_floating_chat_prefers_exact_change_set_over_heuristic() -> None:
    """FloatingChat måste föredra den exakta change-set:en
    (``summarizeChangeSet``) framför prompt-heuristiken
    (``summarizeChangesFromPrompt``) och växla rubriken "Ändrat" /
    "Troligen ändrat" på ``changesExact`` så operatören ser om listan är
    bekräftad eller en uppskattning.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "summarizeChangeSet" in text, (
        "FloatingChat måste importera/anropa summarizeChangeSet — annars "
        "renderas aldrig den exakta change-set:en."
    )
    assert "changesExact" in text, (
        "ChatMessage måste bära changesExact så UI:t kan skilja exakt diff "
        "från heuristik i rubriken."
    )
    assert '"Ändrat"' in text and '"Troligen ändrat"' in text, (
        "Rubriken måste växla mellan 'Ändrat' (exakt) och 'Troligen ändrat' "
        "(heuristik) — annars går ärlighetssignalen förlorad."
    )
    # Den exakta grenen måste ligga FÖRE heuristik-fallbacken i
    # summarizeBuildResult, annars blir prompt-gissningen aldrig ersatt.
    exact_idx = text.find("summarizeChangeSet(payload.changeSet)")
    heuristic_idx = text.find("summarizeChangesFromPrompt(userPrompt)")
    assert exact_idx != -1 and heuristic_idx != -1, (
        "Båda vägarna måste finnas i summarizeBuildResult."
    )
    assert exact_idx < heuristic_idx, (
        "Den exakta change-set-grenen måste utvärderas före prompt-"
        "heuristiken så bekräftade deltas vinner."
    )


# --- Tier 1 (robusthet, 2026-06-01) ---------------------------------------
#
# Tre regressionstester för Tier 1-frontend-paketet:
#   * ErrorBoundary måste finnas och wrappa fel-prona subtree:er i page.tsx
#   * ToastProvider måste vara mountat högst upp i Providers
#   * /api/runs-failure visar retry-card + toast (inte tyst stuck status)
#
# Syftet är att hindra framtida refactors från att tysta dessa fel-
# hanteringsytor utan att vi märker det. Att radera ErrorBoundary eller
# ToastProvider av misstag är en regression som är svår att upptäcka
# tills produktionen kraschar.


@pytest.mark.tooling
def test_tier1_error_boundary_component_exists() -> None:
    """ErrorBoundary-komponenten måste finnas i ``components/error-boundary.tsx``.

    Den är en klasskomponent (React 19 har inget hook-API för error
    boundaries) och måste exportera ``ErrorBoundary`` med en ``area``-
    prop så fallback-rubriken kan anpassas per call-site.
    """
    path = VIEWSER_DIR / "components" / "error-boundary.tsx"
    assert path.exists(), "ErrorBoundary-komponenten saknas"
    text = path.read_text(encoding="utf-8")

    assert "export class ErrorBoundary" in text, (
        "ErrorBoundary måste vara en exporterad klass — React 19 har "
        "fortfarande inget hook-API för error boundaries"
    )
    assert "getDerivedStateFromError" in text, (
        "ErrorBoundary måste implementera getDerivedStateFromError för att fånga rendering-fel"
    )
    assert "componentDidCatch" in text, (
        "ErrorBoundary måste implementera componentDidCatch för att "
        "logga fel till devtools/operatör-konsolen"
    )
    assert "area:" in text or "area: string" in text, (
        "ErrorBoundary måste ta en ``area``-prop så fallback-rubriken kan "
        "anpassas per call-site (t.ex. 'Builder', 'Wizard')"
    )


@pytest.mark.tooling
def test_tier1_page_wraps_subtrees_in_error_boundary() -> None:
    """``app/page.tsx`` måste wrappa ViewerPanel, PromptBuilder och
    BuilderShell i ErrorBoundary så ett crash i någon subtree inte
    ger vit skärm för hela appen.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert 'from "@/components/error-boundary"' in text, "page.tsx måste importera ErrorBoundary"

    # Räkna antal ErrorBoundary-öppningar i JSX. Tre boundaries:
    # ViewerPanel, PromptBuilder, BuilderShell. Mindre tolerant vore
    # bättre men gör testet sprödare; nuvarande gräns säger bara
    # "minst tre", vilket fångar borttagningar.
    boundary_opens = len(re.findall(r"<ErrorBoundary\s+area=", text))
    assert boundary_opens >= 3, (
        "page.tsx måste wrappa minst tre fel-prona subtree:er "
        "(ViewerPanel, PromptBuilder, BuilderShell) i ErrorBoundary "
        f"— hittade bara {boundary_opens}"
    )


@pytest.mark.tooling
def test_tier1_toast_system_exists_and_is_mounted() -> None:
    """Toast-systemet måste finnas i ``components/ui/toast.tsx`` med
    publika API:erna ``ToastProvider``, ``useToast`` och en viewport-
    region som mountas via Provider:n. Providers.tsx ska wrappa
    ToastProvider runt resten av app:en så ``useToast()`` är tillgängligt
    från hela komponentträdet.
    """
    toast_path = VIEWSER_DIR / "components" / "ui" / "toast.tsx"
    assert toast_path.exists(), "Toast-systemet saknas"
    toast_text = toast_path.read_text(encoding="utf-8")

    assert "export function ToastProvider" in toast_text, "toast.tsx måste exportera ToastProvider"
    assert "export function useToast" in toast_text, "toast.tsx måste exportera useToast()"
    # aria-live krävs för skärmläsar-uppläsning av toaster.
    assert "aria-live" in toast_text, (
        "Toast-regionen/items måste ha aria-live så skärmläsare läser upp dem när de visas"
    )
    # role="alert" eller role="status" krävs för att toaster ska
    # annonseras.
    assert 'role="alert"' in toast_text or "liveRole" in toast_text, (
        'Toast-items måste ha role="alert"/"status" beroende på variant'
    )

    providers_text = (VIEWSER_DIR / "app" / "providers.tsx").read_text(encoding="utf-8")
    assert "ToastProvider" in providers_text, (
        "Providers.tsx måste mounta ToastProvider så useToast() funkar från hela komponentträdet"
    )


@pytest.mark.tooling
def test_tier1_page_handles_runs_load_failure_with_retry() -> None:
    """``app/page.tsx`` måste visa en retry-yta när initial /api/runs
    failar — inte bara en tyst stuck loading-text. Vi söker efter
    ``runsLoadError``-state och en RunsLoadErrorCard- (eller
    motsvarande) -komponent med retry-knapp.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert "runsLoadError" in text, (
        "page.tsx måste ha runsLoadError-state för att visa retry-card vid /api/runs-failures"
    )
    assert "RunsLoadErrorCard" in text or "onRetry" in text, (
        "page.tsx måste rendera ett retry-card med onRetry-callback när runsLoadError är satt"
    )
    # Toast-feedback för failure-pathen så operatören ser felet även
    # om hen inte tittar på hero-ytan.
    assert 'variant: "error"' in text and "Kunde inte ladda runs" in text, (
        "page.tsx måste visa en error-toast med titel 'Kunde inte "
        "ladda runs' när initial fetch failar"
    )


# ---------------------------------------------------------------------------
# Bite C — vercel-sandbox preview wiring (ADR 0033)
# ---------------------------------------------------------------------------
# Källåls-lås så local-next-vägen förblir oförändrad medan vercel-sandbox-
# vägen wiras in: route via currentViewserRuntime, ViewerPanel-iframe av den
# returnerade publika URL:en, tom-header-gren i next.config, dev-dispatcher
# som inte kastar, ärlig auth-degradering och sandbox-livscykel (stoppa gamla).


@pytest.mark.tooling
def test_preview_route_dispatches_via_current_viewser_runtime() -> None:
    """Bite C task 1: ``app/api/preview/[siteId]/route.ts`` ska gå via
    ``currentViewserRuntime()`` (DI) i stället för att hårdkoda local-
    preview-server. local-next-grenen MÅSTE behålla sitt exakta beteende
    (``startPreviewServer`` + strukturerad felshape), och en
    ``vercel_auth``-felkod måste finnas så UI:t kan visa pedagogiskt fel
    i stället för tyst fallback."""
    text = (VIEWSER_DIR / "app" / "api" / "preview" / "[siteId]" / "route.ts").read_text(
        encoding="utf-8"
    )

    assert "currentViewserRuntime" in text, (
        "route.ts måste resolva runtime via currentViewserRuntime() (DI), "
        "inte hårdkoda local-preview-server."
    )
    assert 'from "@/lib/preview-runtime-server"' in text, (
        "route.ts måste importera currentViewserRuntime från @/lib/preview-runtime-server."
    )
    # local-next-grenen oförändrad: startPreviewServer + classifyStartError.
    assert "await startPreviewServer(siteId)" in text, (
        "route.ts local-grenen måste fortsatt anropa startPreviewServer(siteId) "
        "så local-next-beteendet är oförändrat."
    )
    assert 'runtime.kind !== "local"' in text, (
        "route.ts måste grena på runtime.kind så icke-lokala adaptrar "
        "(vercel-sandbox) går via adapterns start/stop."
    )
    # Ärlig degradering: vercel_auth-felkod finns.
    assert '"vercel_auth"' in text, (
        "route.ts PreviewErrorCode måste innehålla 'vercel_auth' för "
        "saknad/utgången Vercel-token (ärlig degradering, inte tyst fallback)."
    )
    # DELETE stoppar sandbox-sessionen i vercel-sandbox-läge (livscykel/kostnad).
    assert "stopSandboxSessionForSite" in text, (
        "route.ts DELETE måste stoppa sandbox-sessionen i vercel-sandbox-läge "
        "(stopSandboxSessionForSite) så vi inte läcker sandboxar."
    )


@pytest.mark.tooling
def test_viewer_panel_has_vercel_sandbox_branch() -> None:
    """Bite C task 2: ViewerPanel måste behandla vercel-sandbox EXAKT som
    local-next-vägen (POST /api/preview → iframe:a returnerad URL) och visa
    pedagogiskt fel vid miss i stället för att falla till StackBlitz.

    Lås:
      1. ``IS_VERCEL_SANDBOX_MODE``-konstant.
      2. Failure-grenarna gated på ``IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE``
         (≥3 ggr — non-OK, network-error, siteId-saknas).
      3. ``vercel_auth`` hanteras i unavailableForPreviewError.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")

    pattern_const = re.compile(
        r'const\s+IS_VERCEL_SANDBOX_MODE\s*=\s*PREVIEW_RUNTIME\.kind\s*===\s*["\']vercel-sandbox["\']',
        re.MULTILINE,
    )
    assert pattern_const.search(text), (
        "viewer-panel.tsx saknar ``const IS_VERCEL_SANDBOX_MODE = "
        "PREVIEW_RUNTIME.kind === 'vercel-sandbox'`` (Bite C, ee68add)."
    )

    combined = len(re.findall(r"IS_LOCAL_NEXT_MODE\s*\|\|\s*IS_VERCEL_SANDBOX_MODE", text))
    assert combined >= 3, (
        "viewer-panel.tsx: de tre preview-failure-grenarna (non-OK, "
        "network-error, siteId-saknas) måste vara gated på "
        "``IS_LOCAL_NEXT_MODE || IS_VERCEL_SANDBOX_MODE`` så vercel-sandbox "
        f"visar pedagogiskt fel i stället för StackBlitz-fallback. Hittade {combined}."
    )

    assert 'code === "vercel_auth"' in text, (
        "viewer-panel.tsx unavailableForPreviewError måste hantera "
        "'vercel_auth' med ett pedagogiskt svenskt inloggningsfel."
    )


@pytest.mark.tooling
def test_next_config_vercel_sandbox_gets_empty_headers() -> None:
    """Bite C task 3: ``vercel-sandbox`` måste få TOMMA headers (som
    local-next), INTE COEP/COOP. En publik https-iframe behöver ingen
    cross-origin-isolation (det krävs bara av StackBlitz/WebContainers)."""
    text = (VIEWSER_DIR / "next.config.ts").read_text(encoding="utf-8")

    pattern = re.compile(
        r'if\s*\(\s*effectiveMode\s*===\s*["\']local-next["\']\s*\|\|\s*'
        r'effectiveMode\s*===\s*["\']vercel-sandbox["\']\s*\)\s*\{\s*return\s*\[\s*\]\s*;',
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "next.config.ts headers() måste returnera [] för BÅDE local-next och "
        "vercel-sandbox (``if (effectiveMode === 'local-next' || effectiveMode "
        "=== 'vercel-sandbox') { return []; }``). Annars hamnar vercel-sandbox "
        "i COEP/COOP-grenen som blockerar en cross-origin iframe."
    )


@pytest.mark.tooling
def test_dev_dispatcher_allows_vercel_sandbox_over_http() -> None:
    """Bite C task 4: ``scripts/dev.mjs`` får INTE kasta på
    ``VIEWSER_PREVIEW_MODE=vercel-sandbox`` — det ska köra vanlig
    ``next dev`` (http, COEP off), samma transport som local-next."""
    text = (VIEWSER_DIR / "scripts" / "dev.mjs").read_text(encoding="utf-8")

    assert '"vercel-sandbox"' in text, (
        "dev.mjs VALID_MODES måste innehålla 'vercel-sandbox' så dispatchern "
        "inte kastar på det läget."
    )
    # http/COEP-off: vercel-sandbox måste ge useHttps=false (ingen
    # --experimental-https), precis som local-next.
    assert "HTTP_COEP_OFF_MODES" in text, (
        "dev.mjs måste ha en HTTP_COEP_OFF_MODES-mängd som styr useHttps."
    )
    pattern = re.compile(
        r"HTTP_COEP_OFF_MODES\s*=\s*new\s+Set\(\s*\[[^\]]*['\"]vercel-sandbox['\"]",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "dev.mjs: 'vercel-sandbox' måste ligga i HTTP_COEP_OFF_MODES så "
        "useHttps=false (http, COEP off) — sandbox-URL:en är en publik "
        "https-iframe som bäddas utan cross-origin-isolation."
    )
    assert "!HTTP_COEP_OFF_MODES.has(mode)" in text, (
        "dev.mjs useHttps måste härledas ur HTTP_COEP_OFF_MODES."
    )


@pytest.mark.tooling
def test_vercel_sandbox_sessions_module_bridges_siteid_to_sandbox() -> None:
    """Bite C task 6: en sessionsmodul bryggar ``siteId -> sandboxId`` så
    build-runner och DELETE kan stoppa en sandbox via siteId (de känner inte
    sandboxId). Modulen delegerar stop till runnern."""
    path = VIEWSER_DIR / "lib" / "vercel-sandbox-sessions.ts"
    assert path.exists(), (
        "apps/viewser/lib/vercel-sandbox-sessions.ts saknas — registret som "
        "bryggar siteId -> sandboxId för sandbox-livscykeln."
    )
    text = path.read_text(encoding="utf-8")
    assert "recordSandboxSession" in text
    assert "getSandboxSession" in text
    assert "export async function stopSandboxSessionForSite" in text
    assert 'from "./vercel-sandbox-runner"' in text and "stopSandboxPreview" in text, (
        "sessionsmodulen måste delegera stop till runnerns stopSandboxPreview."
    )


@pytest.mark.tooling
def test_preview_runtime_server_records_and_stops_old_sandbox() -> None:
    """Bite C task 5+6: DI-wiringen registrerar en ny sandbox-session och
    stoppar en ev. tidigare sandbox för samma siteId innan en ny skapas (så
    vi aldrig kör två parallellt → läcker inte kostnad)."""
    text = (VIEWSER_DIR / "lib" / "preview-runtime-server.ts").read_text(encoding="utf-8")
    assert "recordSandboxSession" in text, (
        "preview-runtime-server.ts måste registrera den nya sandbox-sessionen "
        "efter en lyckad createSandboxPreview."
    )
    assert "stopSandboxSessionForSite(siteId)" in text, (
        "preview-runtime-server.ts vercelSandbox.start måste stoppa en ev. "
        "tidigare sandbox för samma siteId innan en ny skapas."
    )


@pytest.mark.tooling
def test_build_runner_stops_sandbox_session_before_rebuild() -> None:
    """Bite C task 6: ett nytt bygge/följdprompt ska stoppa den gamla
    sandboxen — wirat där local-next:s ``stopAndWaitPreviewServer`` anropas
    idag. Idempotent no-op i local-next-läge (tomt register)."""
    text = (VIEWSER_DIR / "lib" / "build-runner.ts").read_text(encoding="utf-8")
    assert "stopSandboxSessionForSite(siteId)" in text, (
        "build-runner.ts måste anropa stopSandboxSessionForSite(siteId) "
        "(bredvid stopAndWaitPreviewServer) så en gammal sandbox stoppas "
        "innan en ny build — annars läcker sandboxar (TTL ~15 min, kostar ören)."
    )


@pytest.mark.tooling
def test_vercel_sandbox_runner_autoloads_env_vercel_local() -> None:
    """Bite C task 5 (auth-wiring): Next auto-laddar inte ``.env.vercel.local``
    (filen vercel env pull skapar för OIDC-token). Runnern måste därför läsa
    den filen själv så den körande viewser-processen hittar VERCEL_OIDC_TOKEN —
    annars visar iframen bara 'credentials saknas' trots en pullad token."""
    text = (VIEWSER_DIR / "lib" / "vercel-sandbox-runner.ts").read_text(encoding="utf-8")
    assert ".env.vercel.local" in text, (
        "vercel-sandbox-runner.ts måste läsa apps/viewser/.env.vercel.local "
        "så OIDC-token från `vercel env pull` hittas (Next auto-laddar den inte)."
    )
    assert "VERCEL_OIDC_TOKEN" in text


# ---------------------------------------------------------------------------
# Tier 2 — skeleton-konsekvens + Cmd+K shortcut
# ---------------------------------------------------------------------------


def test_tier2_inspector_uses_skeleton_during_loading() -> None:
    """``site-inspector-sheet.tsx`` måste rendera Skeleton-block under
    artefact-loading istället för en spinner-only "Läser artefakter…"-
    rad. Skeleton-mönstret ger operatören en visuell preview av tab-
    strukturen som kommer dyka upp och förhindrar layout-hopp.
    """
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "site-inspector-sheet.tsx"
    ).read_text(encoding="utf-8")

    assert "InspectorLoadingSkeleton" in text, (
        "site-inspector-sheet.tsx måste ha en InspectorLoadingSkeleton-"
        "komponent som ersätter den gamla Loader2-spinnern"
    )
    assert "import { Skeleton }" in text, (
        "site-inspector-sheet.tsx måste importera Skeleton från @/components/ui/skeleton"
    )
    # Loader2 var den gamla spinnern — bekräfta att den är borta från
    # imports OCH från jsx-trädet i loading-blocket.
    assert "Loader2" not in text, (
        "site-inspector-sheet.tsx ska inte längre använda Loader2 — "
        "skeleton-tillståndet ersätter spinnern"
    )
    assert 'role="status"' in text and 'aria-live="polite"' in text, (
        "InspectorLoadingSkeleton måste ha role=status + aria-live så "
        "skärmläsare läser upp att vi laddar"
    )


def test_tier2_variants_tab_uses_skeleton_during_loading() -> None:
    """``variants-tab.tsx`` måste byta sin Loader2-spinner mot Skeleton-
    kort medan ``options === null``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "variants-tab.tsx").read_text(
        encoding="utf-8"
    )

    assert "import { Skeleton }" in text, "variants-tab.tsx måste importera Skeleton"
    assert "Loader2" not in text, "variants-tab.tsx ska inte använda Loader2 i loading-blocket"
    # 4 skeleton-kort matchar variant-grid (2 cols × 2 rader på sm+).
    assert "length: 4" in text, (
        "variants-tab.tsx måste rendera 4 Skeleton-kort som approximerar variant-grid"
    )


def test_tier2_versions_tab_uses_skeleton_for_init_and_diff() -> None:
    """``versions-tab.tsx`` måste byta båda Loader2-spinners (initial-
    load + diff-load) mot Skeleton-rader. Loader2 får finnas kvar för
    pågående-bygge-raden (annan use case).
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )

    assert "import { Skeleton }" in text, "versions-tab.tsx måste importera Skeleton"
    # Initial-load: text "Läser versioner" får finnas kvar som sr-only-
    # span, men måste sitta i ett block som också renderar Skeleton.
    init_idx = text.find("Läser versioner")
    assert init_idx != -1, (
        "versions-tab.tsx förväntas ha 'Läser versioner' som sr-only-text i loading-blocket"
    )
    init_block = text[init_idx - 400 : init_idx + 600]
    assert "Skeleton" in init_block and "sr-only" in init_block, (
        "Initial-loading-blocket i versions-tab.tsx måste rendera "
        "Skeleton + sr-only istället för en Loader2-spinner"
    )
    # Diff-load ("Räknar diff…") får inte längre kombineras med Loader2.
    diff_loading_idx = text.find("Räknar diff")
    if diff_loading_idx != -1:
        # Räknar bara om strängen finns kvar (sr-only). Då måste
        # samma block också använda Skeleton.
        block = text[diff_loading_idx - 400 : diff_loading_idx + 400]
        assert "Skeleton" in block, (
            "Diff-loading-blocket i versions-tab.tsx måste rendera Skeleton istället för Loader2"
        )


def test_tier2_run_details_panel_uses_skeleton_during_loading() -> None:
    """``run-details-panel.tsx`` måste byta "Laddar artefakter…"-text
    mot Skeleton-rader.
    """
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(encoding="utf-8")

    assert "import { Skeleton }" in text, "run-details-panel.tsx måste importera Skeleton"
    # Säkerställ att den nakna text-only loading-paragrafen är borta.
    assert '<p className="text-sm text-muted-foreground">Laddar artefakter' not in text, (
        "run-details-panel.tsx ska inte längre rendera en text-only 'Laddar artefakter…'-paragraf"
    )


def test_tier2_page_registers_cmd_k_shortcut_for_console_drawer() -> None:
    """``app/page.tsx`` måste registrera en global Cmd/Ctrl+K-listener
    som togglar ConsoleDrawer. Listenern måste hoppa över input/textarea-
    fokus så genvägen inte stjäl tangenten från composern.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert 'event.key !== "k"' in text or 'event.key === "k"' in text, (
        "page.tsx måste lyssna på 'k'-tangenten för Cmd+K-shortcut"
    )
    assert "metaKey" in text and "ctrlKey" in text, (
        "Cmd+K-listenern måste kolla både metaKey (Mac) och ctrlKey (Windows/Linux)"
    )
    assert "setConsoleOpen" in text, "page.tsx måste toggla setConsoleOpen från Cmd+K-listenern"
    # Bekräfta att vi hoppar över edit-targets (TEXTAREA / INPUT /
    # contentEditable) så vi inte stjäl tangent från composern.
    assert "TEXTAREA" in text and "isContentEditable" in text, (
        "Cmd+K-listenern måste hoppa över editable-element så den inte "
        "stjäl tangenten från composern"
    )


def test_tier2_console_drawer_shows_keyboard_hint() -> None:
    """``console-drawer.tsx`` måste visa en ⌘K-kbd-hint i headern så
    operatören upptäcker shortcuten.
    """
    text = (VIEWSER_DIR / "components" / "console-drawer.tsx").read_text(encoding="utf-8")

    assert "⌘K" in text or "Cmd+K" in text, (
        "console-drawer.tsx måste visa en synlig ⌘K-hint i headern"
    )
    assert "<kbd" in text, (
        "Hinten ska renderas som ett <kbd>-element (semantisk markering för tangentbordsgenvägar)"
    )


# ---------------------------------------------------------------------------
# Tier 3 — a11y-pass + fil-split (versions-tab + viewer-panel)
# ---------------------------------------------------------------------------


def test_tier3_sheet_and_dialog_use_swedish_close_label() -> None:
    """De svenska sr-only-labels för close-knappar i ``ui/sheet.tsx`` +
    ``ui/dialog.tsx`` måste vara "Stäng", inte engelska "Close". Resten
    av UI:t är konsekvent svenskt — sr-only-text får inte glida.
    """
    sheet = (VIEWSER_DIR / "components" / "ui" / "sheet.tsx").read_text(encoding="utf-8")
    dialog = (VIEWSER_DIR / "components" / "ui" / "dialog.tsx").read_text(encoding="utf-8")

    assert '<span className="sr-only">Stäng</span>' in sheet, (
        "ui/sheet.tsx måste använda 'Stäng' (inte 'Close') som sr-only-text på close-knappen"
    )
    assert '<span className="sr-only">Stäng</span>' in dialog, (
        "ui/dialog.tsx måste använda 'Stäng' (inte 'Close') som sr-only-text på close-knappen"
    )
    # Bekräfta att engelska "Close" inte ligger kvar i fixerade strängar.
    # Stränget kan dyka upp i kommentarer eller komponentnamn (`SheetClose`),
    # så vi söker bara sr-only-mönstret.
    assert '"sr-only">Close<' not in sheet, (
        "ui/sheet.tsx har fortfarande 'Close' i sr-only-text — ska vara 'Stäng'"
    )
    assert '"sr-only">Close<' not in dialog, (
        "ui/dialog.tsx har fortfarande 'Close' i sr-only-text — ska vara 'Stäng'"
    )


def test_tier3_floating_chat_decorative_icons_are_aria_hidden() -> None:
    """Dekorativa ikoner inuti knappar med egen aria-label måste vara
    ``aria-hidden`` så skärmläsare inte läser upp ikonnamnet ovanpå
    knappens label. Vi kontrollerar Send + Loader2 + ImagePlus i
    floating-chat.tsx vars parent-knappar har 'Skicka instruktion'
    respektive 'Bifoga bild' som aria-label.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    # Send-ikonen i Skicka-knappen.
    assert "<Send aria-hidden" in text, (
        "floating-chat.tsx: <Send>-ikonen i Skicka-knappen måste ha "
        "aria-hidden (parent-knappen har aria-label='Skicka instruktion')"
    )
    # ImagePlus-ikonen i Bifoga-bild-knappen.
    assert "<ImagePlus aria-hidden" in text, (
        "floating-chat.tsx: <ImagePlus>-ikonen i Bifoga-bild-knappen måste "
        "ha aria-hidden (parent-knappen har aria-label='Bifoga bild')"
    )


def test_tier3_versions_tab_diff_view_is_extracted() -> None:
    """``versions-tab.tsx`` växte till 1438 rader innan split — den
    delade ut DiffView + helpers + EmptyState till en egen fil. Vi
    kontrollerar att huvudfilen importerar från den nya filen istället
    för att definiera lokalt, och att den nya filen exporterar det
    förväntade publika API:et.
    """
    main = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )
    split = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab" / "diff-view.tsx"
    ).read_text(encoding="utf-8")

    # Importerar från den nya filen.
    assert 'from "@/components/builder/inspector/versions-tab/diff-view"' in main, (
        "versions-tab.tsx måste importera DiffView/CompareEmptyHint/"
        "VersionsEmptyState från den nya diff-view-filen"
    )
    # Lokala definitioner är borta — annars dubbeldefinition.
    assert "function DiffView(" not in main, (
        "versions-tab.tsx ska inte längre definiera DiffView lokalt"
    )
    assert "function ScalarChangeRow(" not in main, (
        "versions-tab.tsx ska inte längre definiera ScalarChangeRow lokalt"
    )
    assert "function ValueChip(" not in main, (
        "versions-tab.tsx ska inte längre definiera ValueChip lokalt"
    )
    assert "function ChipDiffRow(" not in main, (
        "versions-tab.tsx ska inte längre definiera ChipDiffRow lokalt"
    )
    assert "function ChangeChip(" not in main, (
        "versions-tab.tsx ska inte längre definiera ChangeChip lokalt"
    )
    assert "function CompareEmptyHint(" not in main, (
        "versions-tab.tsx ska inte längre definiera CompareEmptyHint lokalt"
    )

    # Splitfilen exporterar förväntat API.
    assert "export function DiffView(" in split, "diff-view.tsx måste exportera DiffView"
    assert "export function CompareEmptyHint(" in split, (
        "diff-view.tsx måste exportera CompareEmptyHint"
    )
    assert "export function VersionsEmptyState(" in split, (
        "diff-view.tsx måste exportera VersionsEmptyState"
    )


def test_tier3_versions_tab_shrunk_below_1300_lines() -> None:
    """Sanity-check: ``versions-tab.tsx`` ska vara mätbart mindre efter
    Tier 3-splittet. Var 1438 rader → mål under 1300 (faktiskt resultat:
    1184). Tröskeln är generös så framtida tilltäg i huvudfilen inte
    bryter testet förrän det är dags för nästa split.
    """
    path = VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx"
    line_count = sum(1 for _ in path.open(encoding="utf-8"))
    assert line_count < 1300, (
        f"versions-tab.tsx har växt till {line_count} rader — splitta "
        f"ytterligare innan vi går över 1300"
    )


# ----------------------------------------------------------------------
# Pre-push-fixar (efter Tier 3 scout)
# ----------------------------------------------------------------------
# Fem P1-fynd från pre-push-scouten:
#   1. ErrorBoundary måste applicera ``className`` även i success-render
#      så ``h-full w-full``-kedjan till ViewerPanel inte bryts.
#   2. Toast ``dismiss`` måste vara idempotent + rensa både auto-dismiss
#      och cleanup-timers så Map:en inte läcker entries.
#   3. ToastViewport flyttades från ``bottom-4`` till ``top-20`` för att
#      inte skymma FloatingChat-composern eller mobil bottom-sheet.
#   4. ``build-progress-card.tsx`` måste normalisera env-variabeln på
#      samma sätt som ``viewer-panel.tsx`` (``trim`` + ``toLowerCase``)
#      annars ljuger PREVIEW_PREP_HINT vid casing-varianter.
#   5. Cmd+K-listenern hoppar nu över ``SELECT``-element så ConsoleDrawer
#      inte togglar mitt i ett val.


def test_pre_push_toast_dismiss_is_idempotent() -> None:
    """``dismiss`` ska vara idempotent (hoppar över om cleanup redan
    pågår) och rensa både auto-dismiss-timern och cleanup-timern i
    ``removeToast`` så Map-entries inte läcker.
    """
    path = VIEWSER_DIR / "components" / "ui" / "toast.tsx"
    content = path.read_text(encoding="utf-8")
    assert re.search(
        r"timeoutsRef\.current\.has\(`\$\{id\}:cleanup`\)",
        content,
    ), "dismiss måste tidigt-returnera om cleanup-timern redan finns"
    assert "timeoutsRef.current.delete(`${id}:cleanup`)" in content, (
        "removeToast måste rensa ``${id}:cleanup``-nyckeln så Map:en "
        "inte växer obegränsat när manuell dismiss races med auto-timeout"
    )


def test_pre_push_toast_viewport_positioned_above_floating_chat() -> None:
    """ToastViewport får inte ligga på ``bottom-*`` — det krockar med
    FloatingChat-composern (desktop bottom-6) och mobil bottom-sheet.
    Top-placement är säkrare yta.
    """
    path = VIEWSER_DIR / "components" / "ui" / "toast.tsx"
    content = path.read_text(encoding="utf-8")
    assert "top-20" in content, (
        "ToastViewport ska använda top-20 så aviseringar inte skymmer "
        "FloatingChat eller PromptBuilder-composern"
    )
    # Säkerhetsnät: bottom-positionering ska inte ha smugit tillbaka.
    # ``bottom-2`` används bara i animations-namnet (slide-in-from-bottom-2)
    # som vi också ändrade — så vi tillåter den substring som regex.
    assert "fixed inset-x-0 bottom-" not in content, (
        "ToastViewport får inte använda bottom-positionering"
    )


def test_pre_push_cmd_k_skips_select_targets() -> None:
    """⌘K-listenern i ``page.tsx`` ska hoppa över SELECT-element så
    operatören inte tappar fokus i ConsoleDrawer's projekt-väljare
    eller andra select:s i appen. Matchar DiscoveryWizard's egen
    ⌘K-skip-lista.
    """
    path = VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx"
    content = path.read_text(encoding="utf-8")
    # Hitta useEffect-blocket för ⌘K och säkerställ att SELECT-skip finns.
    assert re.search(
        r'tagName === "SELECT"',
        content,
    ), "⌘K-listenern måste skippa SELECT-element (matcha wizardens mönster)"


# ----------------------------------------------------------------------
# Jakob-handoff bite-A + bite-C (post-PR #139)
# ----------------------------------------------------------------------
# Två låg-impact-fynd som flaggades av Jakobs bot efter PR #139:
#   A. prompt-builder.tsx NDJSON-parsing: inre try/catch runt JSON.parse
#      så en korrupt rad inte sprider "Unexpected token X" till operatören.
#      Final-buffer-union utökades med "building" så snabba builds där
#      Phase 1 + Phase 2 hamnar i samma chunk inte typ-fail:ar.
#   C. more-info-dialog.tsx activeTab-state ska nollställas till "about"
#      varje gång dialogen öppnas (Radix unmountar inte tree:t mellan
#      open-toggles när controlled).


def test_handoff_a_prompt_builder_ndjson_parse_is_defensive() -> None:
    """``prompt-builder.tsx`` NDJSON-parsing måste ha inre try/catch
    runt BÅDA ``JSON.parse``-anrop (line-iterator + final-buffer) så
    en korrupt NDJSON-rad inte sprider SyntaxError till operatören.
    """
    path = VIEWSER_DIR / "components" / "prompt-builder.tsx"
    content = path.read_text(encoding="utf-8")
    # Räkna JSON.parse-anrop i samma kontext — båda måste vara inom
    # en try/catch-block som loggar och fortsätter/fallback:ar.
    parse_calls = re.findall(r"JSON\.parse\((line|buffer)\)", content)
    assert len(parse_calls) == 2, (
        f"Förväntade 2 JSON.parse-anrop (line + buffer), hittade {len(parse_calls)}: {parse_calls}"
    )
    # Båda måste föregås av ``try {`` på samma indent (inom while-loopen
    # för line, eller efter ``if (buffer.trim())`` för buffer).
    assert content.count("try {\n            event = JSON.parse(line)") == 1, (
        "JSON.parse(line) måste vara inom inre try-block i NDJSON-loopen"
    )
    assert content.count("try {\n          event = JSON.parse(buffer)") == 1, (
        "JSON.parse(buffer) måste vara inom inre try-block i final-buffern"
    )
    # Final-buffer-union ska inkludera "building" — annars typfail om
    # en snabb build pushar building+done i samma chunk utan terminator.
    final_buffer_section = content[content.index("if (buffer.trim())") :]
    final_buffer_section = final_buffer_section[: final_buffer_section.index("}") + 200]
    assert '"building"' in final_buffer_section, (
        'final-buffer-union måste ha ``stage: "building"`` för att hantera '
        "snabba builds där Phase 1 + done hamnar i samma chunk"
    )


def test_handoff_c_more_info_dialog_resets_active_tab_on_open() -> None:
    """``more-info-dialog.tsx`` måste nollställa ``activeTab`` till den
    begärda ``initialTab`` (default "about") varje gång ``open`` flippar
    från false → true så operatören inte ser föregående flik (Radix
    Dialog-content unmountar inte tree:t mellan open-toggles när
    controlled).

    Reset:en görs som en render-tids state-justering (Reacts "föregående
    props"-mönster via ``wasOpen``) istället för en ``onOpenChange``-
    wrapper: dels ogillar React 19:s ``react-hooks/set-state-in-effect``
    effekt-driven setState, dels är dialogen fullt parent-controlled —
    Radix routar aldrig open-flanken genom onOpenChange, så en wrapper
    skulle inte hinna nollställa fliken vid öppning. Render-mönstret kör
    pålitligt på varje false→true-övergång oavsett trigger (knapp,
    telefon-nudge etc.).
    """
    path = VIEWSER_DIR / "components" / "discovery-wizard" / "more-info-dialog.tsx"
    content = path.read_text(encoding="utf-8")
    # initialTab-prop med "about"-default måste finnas.
    assert re.search(r'initialTab\s*=\s*"about"', content), (
        'MoreInfoDialog måste ha en initialTab-prop med default "about"'
    )
    # Render-tids reset: open !== wasOpen → setActiveTab(initialTab).
    assert re.search(
        r"if \(open !== wasOpen\)\s*\{\s*setWasOpen\(open\);\s*"
        r"setTrackedInitialTab\(initialTab\);\s*"
        r"if \(open\)\s*setActiveTab\(initialTab\);",
        content,
        re.DOTALL,
    ), (
        "MoreInfoDialog måste nollställa activeTab till initialTab på "
        "open-flanken via render-tids wasOpen-mönstret"
    )
    # initialTab-byte MEDAN dialogen är öppen ska också byta flik (djuplänk
    # som byter mål utan att stänga). Annars hängde activeTab kvar.
    assert re.search(
        r"else if \(open && initialTab !== trackedInitialTab\)\s*\{\s*"
        r"setTrackedInitialTab\(initialTab\);\s*setActiveTab\(initialTab\);",
        content,
        re.DOTALL,
    ), (
        "MoreInfoDialog måste byta flik när initialTab ändras medan open "
        "redan är true (annars följer djuplänken inte med)"
    )
    # Dialog ska drivas direkt av parent's onOpenChange (ingen wrapper
    # längre — reset:en bor i render-mönstret ovan).
    assert "<Dialog open={open} onOpenChange={onOpenChange}>" in content, (
        "Dialog ska driva sin onOpenChange direkt från parent"
    )


def test_wizard_contact_nudge_deeplinks_to_contact_tab() -> None:
    """``discovery-wizard.tsx`` ska visa en nudge när telefonnummer
    saknas och kunna öppna MoreInfoDialog direkt på Kontakt-fliken så
    operatören inte oavsiktligt publicerar platshållar-numret
    (+46 8 000 00 00). Ren UI/UX — backend-payloaden är oförändrad.
    """
    path = VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx"
    content = path.read_text(encoding="utf-8")
    # openMoreInfo-helper som sätter både flik och open.
    assert "const openMoreInfo = useCallback(" in content, (
        "Wizarden måste ha en openMoreInfo-helper som sätter flik + open"
    )
    # Nudge-knappen måste djuplänka till Kontakt-fliken.
    assert 'openMoreInfo("contact")' in content, (
        'Nudge-knappen måste djuplänka via openMoreInfo("contact")'
    )
    # Nudgen ska villkoras på saknat (trimmat) telefonnummer.
    assert "!answers.contact.phone.trim()" in content, (
        "Telefon-nudgen måste villkoras på answers.contact.phone.trim()"
    )
    # initialTab måste skickas vidare till MoreInfoDialog.
    assert "initialTab={moreInfoTab}" in content, (
        "MoreInfoDialog måste få initialTab={moreInfoTab} så djuplänken "
        "till Kontakt-fliken fungerar"
    )


def test_b160_logo_image_has_explicit_auto_width() -> None:
    """B160: logon i ``site-header.tsx`` + ``discovery-wizard.tsx``
    renderas via next/image med höjden styrd av ``h-7``. Utan en inline
    ``style`` med ``width: "auto"`` varnar Next ("Image ... has either
    width or height modified, but not the other") eftersom Next läser
    inline-style, inte Tailwind-klassen ``w-auto``. Lås att båda har
    ``style.width: "auto"`` så devtools-bruset/CLS-risken inte återkommer.
    """
    for rel in (
        ("components", "layout", "site-header.tsx"),
        ("components", "discovery-wizard", "discovery-wizard.tsx"),
    ):
        path = VIEWSER_DIR.joinpath(*rel)
        content = path.read_text(encoding="utf-8")
        assert 'src="/sajtbyggaren_logo.png"' in content, (
            f"{path.name} ska rendera sajtbyggaren-logon"
        )
        assert re.search(r'style=\{\{\s*width:\s*"auto"\s*\}\}', content), (
            f"{path.name}: logo-Image måste ha style={{ width: 'auto' }} "
            "för att tysta Next:s aspect-ratio-varning (B160)"
        )


def test_builder_followup_drives_buildstage_via_real_trace_signal() -> None:
    """Scout-fynd (P1): i builder-läge drevs ``buildStage`` aldrig under
    follow-ups (``onStageChange={builderActive ? undefined : setBuildStage}``
    stänger av PromptBuilder:s rapport), så ViewerPanel:s BuildProgressCard
    frös på föregående bygges sista stage och stegmarkören hoppade direkt
    till sista steget.

    Fixen trådar ``onStageChange`` page.tsx → BuilderShell → FloatingChat och
    driver stegen från den RIKTIGA trace.ndjson-signalen
    (``useBuildTracePolling.currentPhase``), inte en setTimeout-flip (jfr
    B122). Lås kedjan så den inte tyst kopplas bort igen.
    """
    page = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    shell = (VIEWSER_DIR / "components" / "builder" / "builder-shell.tsx").read_text(
        encoding="utf-8"
    )
    chat = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )

    # page.tsx måste skicka setBuildStage till BuilderShell (annars är
    # buildStage frusen under follow-ups).
    assert "onStageChange={setBuildStage}" in page, (
        "page.tsx måste skicka onStageChange={setBuildStage} till BuilderShell "
        "så follow-up-bygget driver BuildProgressCard"
    )
    # BuilderShell återställer stage vid VARJE byggstart (FloatingChat ELLER
    # dialog) + vidarebefordrar till FloatingChat.
    assert 'onStageChange?.("thinking")' in shell, (
        "BuilderShell.handleBuildStart måste återställa stage till 'thinking' "
        "så stegmarkören aldrig fryser på föregående bygges sista stage"
    )
    assert "onStageChange={onStageChange}" in shell, (
        "BuilderShell måste tråda onStageChange vidare till FloatingChat"
    )
    # FloatingChat förfinar från trace.ndjson-fasen (riktig signal).
    assert 'tracePolling.currentPhase === "build"' in chat, (
        "FloatingChat måste mappa trace.ndjson-fasen 'build' → buildStage "
        "'building' (riktig signal, inte setTimeout)"
    )
    assert 'onStageChange("building")' in chat, (
        "FloatingChat måste rapportera 'building' när trace når build-fasen"
    )
    # Avslut: success/degraded/failed rapporteras när bygget landar. Mappningen
    # delas med PromptBuilder via outcomeToStage (P2-fix #26: degraded/unknown
    # → "degraded", inte "success", så progress-cardet inte visar grönt medan
    # chatten rapporterar varning).
    assert "onStageChange?.(outcomeToStage(outcome));" in chat, (
        "FloatingChat måste rapportera stage via outcomeToStage när bygget landar"
    )


def test_studio_preserves_iterate_base_on_failed_build() -> None:
    """Scout-fynd (P1, 2026-06-05): onBuildDone rensade pendingBaseRunId
    ovillkorligt — även för outcome=failed (failed returnerar en runId, så
    onBuildDone körs). Då tappade error-bubblans 'Försök igen' iterera-från-
    bas-läget och nästa retry grenade från latest i stället för vald bas, vilket
    motsäger onBuildEnd-kommentarens uttryckliga intent. Lås att base-run:en bara
    rensas när bygget producerade en riktig version (ok/degraded), inte vid failed.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")
    assert 'if (outcome !== "failed") setPendingBaseRunId(null);' in text, (
        "onBuildDone måste behålla pendingBaseRunId vid failed så error-bubblans "
        "'Försök igen' itererar från samma bas i stället för latest."
    )


def test_wizard_finish_timer_is_cancelled_on_close() -> None:
    """Scout-fynd (P1): submit-overlayns 700 ms-timer fyrade av onComplete
    (bygg-start) även om operatören stängde wizarden (Esc) under väntan.
    Timern måste sparas i en ref och avbrytas när ``open`` blir false samt
    vid unmount — annars startas ett oönskat bygge efter att hen backat ut.
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "submitTimerRef" in content, (
        "finish() måste spara submit-timern i submitTimerRef så den kan avbrytas"
    )
    assert "submitTimerRef.current = window.setTimeout(" in content, (
        "submit-timern måste lagras i submitTimerRef (inte en lös setTimeout)"
    )
    # Avbrott när open blir false (Esc/stäng).
    assert re.search(
        r"if \(open\) return;\s*\n\s*if \(submitTimerRef\.current !== null\)\s*\{\s*"
        r"clearTimeout\(submitTimerRef\.current\);",
        content,
        re.DOTALL,
    ), "Wizarden måste avbryta submit-timern i en effekt när open blir false"


def test_wizard_keyboard_help_lists_all_four_steps() -> None:
    """Scout-fynd (P1): genvägs-hjälpen sa 'Hoppa till tab 1–3' men wizarden
    har fyra steg (foundation→assets). Lås att hjälptexten listar steg 1–4.

    Wave 2 (Steg 4): steg-hoppet flyttades från ⌘/Ctrl+siffra till ⌥+siffra
    eftersom ⌘/Ctrl+siffra är webbläsarens egna flik-genvägar — matchningen
    görs på event.code (Digit1–9) eftersom Option+siffra ger specialtecken
    på Mac. ⌘/-genvägen har samma inEditable-guard som ?.
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert '"⌥1", "⌥2", "⌥3", "⌥4"' in content, (
        "Genvägs-hjälpen måste lista alla fyra steg med ⌥-modifier (⌥1–⌥4)"
    )
    assert "Hoppa till tab 1–3" not in content, (
        "Den föråldrade 'tab 1–3'-texten måste bort — wizarden har fyra steg"
    )
    assert '"⌘1", "⌘2", "⌘3", "⌘4"' not in content, (
        "⌘-baserade steg-genvägar måste bort — de krockar med webbläsarens flik-genvägar (Steg 4)"
    )
    # Handlern måste matcha ⌥ + event.code (inte ⌘/Ctrl + event.key).
    assert "event.altKey" in content and re.search(
        r"/\^Digit\[1-9\]\$/\.test\(event\.code\)", content
    ), (
        "Steg-hoppet måste matcha event.altKey + event.code (Digit1–9) så det "
        "inte krockar med webbläsarens ⌘/Ctrl+siffra-flikbyte"
    )
    # Scout-fynd (P1, 2026-06-05): wizardens globala genvägar ligger på document
    # och fyrade bakom MoreInfoDialog (egen Dialog-portal ovanpå) — ⌘↵ kunde
    # avancera/submit:a wizarden utan att operatören såg det. Handlern måste
    # early-return:a när moreInfoOpen är true OCH ha moreInfoOpen i dep-arrayen.
    assert "if (moreInfoOpen) return;" in content, (
        "keydown-handlern måste lämna över tangentbordet till MoreInfoDialog "
        "(early-return på moreInfoOpen) så wizard-genvägar inte fyrar bakom modalen."
    )
    assert "goToStep, helpOpen, moreInfoOpen]" in content, (
        "moreInfoOpen måste ligga i keydown-effektens dep-array, annars läser "
        "guarden ett stale värde."
    )


def test_wizard_submit_overlay_uses_customer_language() -> None:
    """Scout-fynd (microcopy): submit-overlayn visade pipeline-jargong
    ('Discovery → Plan → Codegen') för en icke-teknisk kund. Lås kundvänlig
    svenska så kärnflödet prompt→sajt känns begripligt.
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "Discovery → Plan → Codegen" not in content, (
        "Pipeline-jargong får inte visas i den kundvända submit-overlayn"
    )
    assert "Vi läser dina svar, planerar sidorna och bygger sajten." in content, (
        "Submit-overlayn ska förklara bygget i kundvänlig svenska"
    )


def test_cmd_k_has_modal_guard() -> None:
    """Wave 2 (Steg 1): global ⌘K togglade ConsoleDrawer även när en annan
    modal (DiscoveryWizard/MoreInfoDialog/Verktyg/bygg-dialog) var öppen och
    ryckte upp en bakgrundspanel mitt i kärnflödet. Handlern måste suppressa
    öppning när konsolen är stängd OCH ett [role="dialog"]/[aria-modal]-
    element finns i DOM, men fortfarande kunna STÄNGA en öppen konsol.
    """
    content = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "consoleOpenRef" in content, (
        "⌘K-handlern måste spegla consoleOpen via en ref (lever i []-effekt)"
    )
    assert re.search(
        r"if \(!consoleOpenRef\.current\)\s*\{\s*if \(\s*document\.querySelector\(",
        content,
        re.DOTALL,
    ), (
        "⌘K måste suppressas när konsolen är stängd och en annan modal är "
        "öppen (querySelector på role=dialog/aria-modal)"
    )
    assert '[role="dialog"], [role="alertdialog"], [aria-modal="true"]' in content, (
        "Modal-guarden måste täcka role=dialog, role=alertdialog och aria-modal=true"
    )


def test_builder_actions_arrow_keys_scope_to_current_target() -> None:
    """Wave 2 (Steg 2): handleMenuKeyDown frågade containerRef, men i
    inline-varianten renderas Verktyg-modalen i en portal UTANFÖR
    containerRef → piltangenterna var döda i just den modal operatören
    använder. Handlern måste fråga event.currentTarget och onKeyDown måste
    sitta på grid-diven inuti dialogen (inte bara på container-diven).
    """
    content = (VIEWSER_DIR / "components" / "builder" / "builder-actions.tsx").read_text(
        encoding="utf-8"
    )
    assert "const node = event.currentTarget;" in content, (
        "handleMenuKeyDown måste scope:a sökningen till event.currentTarget "
        "(inte containerRef) så inline-portalens knappar hittas"
    )
    # onKeyDown måste förekomma minst två gånger: container-diven (fixed) +
    # grid-diven i dialogen (inline).
    assert content.count("onKeyDown={handleMenuKeyDown}") >= 2, (
        "onKeyDown={handleMenuKeyDown} måste sitta både på container-diven "
        "och på inline-dialogens grid-div"
    )


def test_console_button_exposes_cmd_k_hint() -> None:
    """Wave 2 (Steg 3): ⌘K-hinten syntes bara inuti den redan öppna konsolen.
    Header-konsolknappen måste exponera genvägen (title + aria-label) så den
    är upptäckbar innan konsolen öppnats.
    """
    content = (VIEWSER_DIR / "components" / "layout" / "site-header.tsx").read_text(
        encoding="utf-8"
    )
    assert "⌘K (Ctrl+K på Windows)" in content, (
        "Header-konsolknappen måste ha en title som visar ⌘K-genvägen"
    )
    assert "(genväg ⌘K)" in content, "aria-label måste nämna ⌘K-genvägen för skärmläsare"


def test_wizard_help_button_visible_on_mobile() -> None:
    """Wave 2 (Steg 5): genvägs-/hjälp-knappen var ``hidden sm:inline-flex``
    → osynlig på smal viewport (t.ex. iPad i porträtt med tangentbord). Den
    måste vara synlig på alla viewports med ett 44px tap-target på mobil
    (min-tap).
    """
    content = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    # Hjälp-knappens block (aria-label="Visa tangentbordsgenvägar") får inte
    # längre döljas på mobil.
    help_btn_idx = content.find('aria-label="Visa tangentbordsgenvägar"')
    assert help_btn_idx != -1, "Hjälp-knappen måste finnas kvar"
    btn_class_window = content[help_btn_idx : help_btn_idx + 600]
    assert "hidden" not in btn_class_window or "min-tap sm:min-tap-0" in btn_class_window, (
        "Hjälp-knappen får inte vara dold på mobil — gör den inline-flex med "
        "min-tap för 44px tap-target"
    )
    assert "min-tap sm:min-tap-0 inline-flex" in btn_class_window, (
        "Hjälp-knappen måste vara inline-flex med min-tap (44px) på mobil"
    )


def test_device_preset_keyboard_shortcuts() -> None:
    """Wave 3 (Steg 6): device-preset (375/768/1024/Full) saknade genvägar
    + kbd-hints. ⌥1–⌥4 ska växla preview-bredd (desktop, ej i composern,
    via event.code) och knapparna ska exponera genvägen via title.
    """
    content = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert re.search(r"/\^Digit\[1-4\]\$/\.test\(event\.code\)", content), (
        "Device-preset-genvägen måste matcha ⌥ + event.code (Digit1–4)"
    )
    assert "DEVICE_PRESET_OPTIONS[parseInt(event.code.slice(5), 10) - 1]" in content, (
        "⌥1–⌥4 måste mappa till DEVICE_PRESET_OPTIONS-index"
    )
    assert "title={`Genväg ${shortcut}`}" in content, (
        "Device-preset-knapparna måste exponera genvägen via title"
    )


def test_run_history_shows_skeleton_while_loading() -> None:
    """Wave 3 (Steg 8): under initial /api/runs-laddning visades tom-CTA:n
    ('Inga runs än') i förtid. RunHistory ska rendera en skeleton när
    loading och inga runs ännu finns, och page.tsx → ConsoleDrawer →
    RunHistory ska tråda loading-flaggan.
    """
    history = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    drawer = (VIEWSER_DIR / "components" / "console-drawer.tsx").read_text(encoding="utf-8")
    page = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(encoding="utf-8")

    assert "RunHistorySkeleton" in history and "Skeleton" in history, (
        "RunHistory måste ha en RunHistorySkeleton som använder Skeleton-primitiven"
    )
    assert "loading && runs.length === 0" in history, (
        "RunHistory måste visa skeleton när loading och inga runs ännu finns"
    )
    assert "loading={runsLoading}" in drawer, (
        "ConsoleDrawer måste tråda runsLoading → RunHistory.loading"
    )
    assert "runsLoading={runsLoading}" in page, (
        "page.tsx måste skicka runsLoading till ConsoleDrawer"
    )


def test_wizard_foundation_copy_avoids_dev_jargon() -> None:
    """Wave 3 (Steg 7): kundvända hjälptexter i foundation- och
    site-type-stegen exponerade dev-jargong ('scaffold', 'Next.js-mall
    backend bygger på', 'Discovery Taxonomy', 'Backendens resolver',
    'runtime-aktiv'). Lås bort de tydligaste på de kundvända ytorna.
    """
    foundation = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "foundation-step.tsx"
    ).read_text(encoding="utf-8")
    site_type = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "site-type-step.tsx"
    ).read_text(encoding="utf-8")

    assert "vilken Next.js-mall backend bygger på" not in foundation, (
        "Foundation-hjälptexten ska inte exponera 'Next.js-mall backend'-jargong"
    )
    assert 'subtitle="Scaffold, vibe, typografi, branch' not in foundation, (
        "MetadataPanel-subtitle ska inte lista 'Scaffold/branch'-jargong"
    )
    # Endast den kundvända HelperText-meningen ska bort — kod-kommentaren som
    # dokumenterar att listan kommer från Discovery Taxonomy får stå kvar.
    assert "Listan följer Discovery Taxonomy." not in site_type, (
        "Den kundvända HelperText-meningen om 'Discovery Taxonomy' ska bort"
    )
    assert "Visar lokal UI-cache tills governance-listan laddats." not in site_type, (
        "Den kundvända UI-cache-jargongen ska bort från HelperText"
    )
    assert "Backendens resolver avgör slutlig scaffold" not in site_type, (
        "Support-notisen ska inte exponera 'Backendens resolver/scaffold'-jargong"
    )
    assert "är runtime-aktiv" not in site_type, (
        "'runtime-aktiv' ska ersättas med kundvänligt 'tillgänglig'"
    )


# ----------------------------------------------------------------------
# Marknadssajt P0 (scout-marketing-site, 2026-06-01)
# Route-group-split: (marketing) äger "/", konsolen flyttad till
# (console)/studio. Minimal header/footer + serverad optimerad bild.
# ----------------------------------------------------------------------


def test_console_moved_to_studio_route_group() -> None:
    """Konsolen ska ligga i app/(console)/studio/page.tsx (flyttad från
    app/page.tsx) och fortfarande vara klient-konsolen — INTE kvar på "/".
    """
    old_path = VIEWSER_DIR / "app" / "page.tsx"
    new_path = VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx"
    assert not old_path.exists(), 'app/page.tsx ska vara flyttad — (marketing) äger nu "/"'
    assert new_path.exists(), "Konsolen ska bo i app/(console)/studio/page.tsx"
    console = new_path.read_text(encoding="utf-8")
    assert '"use client"' in console, "Konsol-sidan ska förbli en klientkomponent"
    # Regressionsvakt: ⌘K-listenern + build-wiringen ska ha följt med oförändrad.
    assert 'event.key !== "k"' in console, "⌘K-listenern ska ha följt med konsolen till studio"
    # (console)-layouten ska sätta noindex så konsolen aldrig indexeras publikt.
    console_layout = (VIEWSER_DIR / "app" / "(console)" / "layout.tsx").read_text(encoding="utf-8")
    assert "index: false" in console_layout, (
        "(console)/layout.tsx måste sätta robots index:false (noindex)"
    )


def test_marketing_header_has_exact_nav_items() -> None:
    """Marknads-headern ska ha exakt Hem/Produkt/Om oss + en primär bygg-CTA
    som pekar in i studion. Auth/billing (Priser-nav + login-entry) är PARKERAT
    i den här PR:en, så headern får inte importera auth-config eller rendera
    en login-/Priser-yta.
    """
    header = (VIEWSER_DIR / "components" / "marketing" / "marketing-header.tsx").read_text(
        encoding="utf-8"
    )
    for label in ('label: "Hem"', 'label: "Produkt"', 'label: "Om oss"'):
        assert label in header, f"Headern saknar nav-item {label}"
    assert 'label: "Priser"' not in header, (
        "Priser-nav är parkerat tillsammans med billing — får inte finnas i den här auth-fria PR:en"
    )
    assert "auth-config" not in header and "authHeaderEntry" not in header, (
        "Headern får inte importera auth-config-seamen i den här PR:en (parkerat)"
    )
    assert 'from "@/lib/routes"' in header and "STUDIO_HREF" in header, (
        "Bygg-CTA:n ska peka in i studion via den auth-fria route-konstanten"
    )


def test_marketing_header_centers_nav() -> None:
    """Operatörsönskemål (juni 2026): menyvalen ska ligga centrerat i headern."""
    header = (VIEWSER_DIR / "components" / "marketing" / "marketing-header.tsx").read_text(
        encoding="utf-8"
    )
    # Centrerad nav: absolut-centrerad via left-1/2 + -translate-x-1/2.
    assert "left-1/2" in header and "-translate-x-1/2" in header, (
        "Desktop-nav:en ska vara horisontellt centrerad i headern"
    )


def test_marketing_footer_has_legal_links() -> None:
    """Footern ska länka till de juridiska/hjälpsidor som byggs ut senare
    (de finns som platshållare i P0 så länkarna inte 404:ar).
    """
    footer = (VIEWSER_DIR / "components" / "marketing" / "marketing-footer.tsx").read_text(
        encoding="utf-8"
    )
    for href in ("/cookies", "/integritetspolicy", "/anvandarvillkor", "/kontakt"):
        assert f'href: "{href}"' in footer, f"Footern saknar länk till {href}"


def test_marketing_homepage_serves_optimized_image() -> None:
    """Startsidan ska rendera optimerade (WebP) yrkesbilder som faktiskt
    serveras från apps/viewser/public/Bilder — beviset på asset-pipelinen.
    P2: bilderna renderas via ProfessionGrid över det delade professions-
    registret i st.f. en hårdkodad <img> i page.tsx.
    """
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert "ProfessionGrid" in home, "Startsidan ska rendera ProfessionGrid (bildväggen)"
    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    assert "/Bilder/bilmekaniker.webp" in professions, (
        "professions.ts ska peka på de optimerade WebP-bilderna"
    )
    served = VIEWSER_DIR / "public" / "Bilder" / "bilmekaniker.webp"
    assert served.exists(), (
        "Den optimerade bilden måste finnas i apps/viewser/public/Bilder "
        "(kör npm run assets:images)"
    )


def test_optimize_images_script_targets_served_public() -> None:
    """optimize-images.mjs ska läsa repo-root public/Bilder och skriva till
    apps/viewser/public/Bilder (den enda mapp Next.js serverar).
    """
    script = (VIEWSER_DIR / "scripts" / "optimize-images.mjs").read_text(encoding="utf-8")
    assert '"../../../public/Bilder"' in script, (
        "Scriptet ska läsa repo-root public/Bilder som källa"
    )
    assert '"../public/Bilder"' in script, (
        "Scriptet ska skriva till apps/viewser/public/Bilder (serverad mapp)"
    )


def test_marketing_header_has_active_state_and_mobile_menu() -> None:
    """P1: headern ska markera aktiv route (usePathname → aria-current) och
    ha en mobil Sheet-meny så nav:en aldrig trängs ihop på smal viewport.
    """
    header = (VIEWSER_DIR / "components" / "marketing" / "marketing-header.tsx").read_text(
        encoding="utf-8"
    )
    assert '"use client"' in header, (
        "Headern måste vara en klientkomponent för usePathname-aktivstate"
    )
    assert "usePathname" in header and 'aria-current={active ? "page"' in header, (
        "Headern ska härleda aktiv route och sätta aria-current=page"
    )
    assert "SheetTrigger" in header and "SheetContent" in header, (
        "Headern ska ha en mobil Sheet-meny (SheetTrigger/SheetContent)"
    )


def test_marketing_homepage_has_hero_and_sections() -> None:
    """P2: startsidan ska ha en video-hero (reduced-motion-säker) + de
    centrala scroll-sektionerna (så-funkar-det-steg, bildvägg, slut-CTA).
    """
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert "HeroVideo" in home, "Startsidan ska rendera HeroVideo"
    assert "Så funkar det" in home, "Startsidan saknar 'Så funkar det'-sektionen"
    for step in ("Beskriv", "Bygg", "Förhandsgranska", "Förfina"):
        assert f'"{step}"' in home, f"Så-funkar-det saknar steget {step}"

    hero = (VIEWSER_DIR / "components" / "marketing" / "hero-video.tsx").read_text(encoding="utf-8")
    assert '"use client"' in hero, "HeroVideo måste vara klient (matchMedia)"
    assert "prefers-reduced-motion" in hero, (
        "HeroVideo måste respektera prefers-reduced-motion (still poster)"
    )
    assert "hero-poster.webp" in hero, "HeroVideo ska använda den committade poster-framen"
    poster = VIEWSER_DIR / "public" / "hero-poster.webp"
    assert poster.exists(), "hero-poster.webp måste finnas i apps/viewser/public"


def test_professions_registry_covers_all_images() -> None:
    """P2: det delade yrkesregistret ska täcka alla 20 optimerade bilder och
    varje slug ha en serverad WebP (grid + framtida /for/[yrke] delar källan).
    """
    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    slugs = re.findall(r'slug:\s*"([^"]+)"', professions)
    assert len(slugs) == 20, f"Förväntade 20 yrken, fann {len(slugs)}"
    bilder_dir = VIEWSER_DIR / "public" / "Bilder"
    for slug in slugs:
        assert (bilder_dir / f"{slug}.webp").exists(), f"Saknar optimerad bild för slug {slug}"


def test_profession_grid_is_interactive_living_wall() -> None:
    """P3: bildväggen ska vara en interaktiv FLIP-swap-wall (Framer Motion)
    som är reduced-motion-säker och pausar vid hover/fokus/dold flik/utanför
    viewport — annars glider en ruta bort från en klickare.
    """
    grid = (VIEWSER_DIR / "components" / "marketing" / "profession-grid.tsx").read_text(
        encoding="utf-8"
    )
    assert '"use client"' in grid, "Living wall måste vara klientkomponent"
    assert 'from "motion/react"' in grid, "Living wall ska använda Framer Motion (motion/react)"
    assert "motion.li" in grid and "layout" in grid, (
        "Tiles ska vara motion.li med layout-prop för FLIP-swap"
    )
    assert "useReducedMotion" in grid and "if (reduced) return" in grid, (
        "Auto-swap måste stängas av vid prefers-reduced-motion"
    )
    assert "IntersectionObserver" in grid and "document.hidden" in grid, (
        "Auto-swap ska pausa utanför viewport och när fliken är dold"
    )
    assert "onMouseEnter" in grid and "onFocusCapture" in grid, (
        "Auto-swap ska pausa vid hover och fokus"
    )
    # motion-depen ska vara deklarerad i package.json.
    pkg = json.loads((VIEWSER_DIR / "package.json").read_text(encoding="utf-8"))
    assert "motion" in pkg.get("dependencies", {}), (
        "motion (Framer Motion) ska vara en deklarerad dependency (D3)"
    )


def test_profession_landing_pages_are_static_and_seo() -> None:
    """P4: /for/[yrke] ska SSG:a alla 20 yrken (generateStaticParams),
    404:a okända slugs (dynamicParams=false + notFound) och ha per-yrke SEO
    (generateMetadata + OG-bild). Varje yrke ska ha headline + pitch.
    """
    page = (VIEWSER_DIR / "app" / "(marketing)" / "for" / "[yrke]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "generateStaticParams" in page, "/for/[yrke] måste exportera generateStaticParams (SSG)"
    assert "export const dynamicParams = false" in page, (
        "Okända slugs ska inte renderas on-demand (dynamicParams=false)"
    )
    assert "notFound()" in page, "Okänd slug ska ge 404 via notFound()"
    assert "generateMetadata" in page and "openGraph" in page, (
        "/for/[yrke] måste ha per-yrke generateMetadata med OG-bild"
    )

    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    # Räkna bara fält med strängvärde (datat) — typdefinitionen
    # ``headline: string`` har inget citat och ska inte räknas med.
    assert len(re.findall(r'headline:\s*"', professions)) == 20, (
        "Alla 20 yrken måste ha en headline för landningssidan"
    )
    assert len(re.findall(r'pitch:\s*"', professions)) == 20, (
        "Alla 20 yrken måste ha en pitch för landningssidan"
    )

    # Bildväggen ska nu länka till landningssidorna, inte rakt in i studion.
    grid = (VIEWSER_DIR / "components" / "marketing" / "profession-grid.tsx").read_text(
        encoding="utf-8"
    )
    assert "href={`/for/${p.slug}`}" in grid, (
        "ProfessionGrid-tiles ska länka till /for/[slug] (P4-rewire)"
    )


def test_professions_have_starter_seed_mapping() -> None:
    """Starters-banan: varje yrke ska mappa till en verksamhetsfamilj +
    kategori + en svensk prompt-seed så landningssidans CTA kan förifylla
    DiscoveryWizarden. Alla 20 yrken måste ha alla tre fälten.
    """
    professions = (VIEWSER_DIR / "lib" / "professions.ts").read_text(encoding="utf-8")
    # Typerna ska komma från wizard-constants (samma källa som wizarden) så
    # familj/kategori aldrig driftar isär från BUSINESS_FAMILIES.
    assert "wizard-constants" in professions, (
        "professions.ts ska importera BusinessFamilyId/WizardCategoryId från "
        "discovery-wizard/wizard-constants"
    )
    assert len(re.findall(r"\bfamily:\s*\"", professions)) == 20, (
        "Alla 20 yrken måste ha en verksamhetsfamilj"
    )
    assert len(re.findall(r"\bcategory:\s*\"", professions)) == 20, (
        "Alla 20 yrken måste ha en kategori"
    )
    assert (
        len(re.findall(r"\bpromptSeed:\s*$", professions, re.MULTILINE))
        + len(re.findall(r"\bpromptSeed:\s*\"", professions))
        >= 20
    ), "Alla 20 yrken måste ha en promptSeed"


def test_profession_landing_cta_seeds_wizard_not_empty_studio() -> None:
    """Starters-banan: yrkessidans "Bygg din sida" ska gå via StarterCta som
    lämnar en wizard-seed (familj/kategori/prompt) i stället för att länka
    rakt till en TOM /studio. Seed:en får bara bära hints — aldrig starterId.
    """
    page = (VIEWSER_DIR / "app" / "(marketing)" / "for" / "[yrke]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "StarterCta" in page, "/for/[yrke] ska använda StarterCta för bygg-knappen"
    assert "profession.promptSeed" in page and "profession.family" in page, (
        "StarterCta ska seedas från yrkets promptSeed + family/category"
    )

    cta = (VIEWSER_DIR / "components" / "marketing" / "starter-cta.tsx").read_text(encoding="utf-8")
    assert "setWizardSeed" in cta and "STUDIO_HREF" in cta, (
        "StarterCta ska lämna en wizard-seed och navigera till studion"
    )
    assert "starterId" not in cta, (
        "Starter-seed:en får inte sätta starterId (backend äger scaffold-valet)"
    )


def test_hero_has_starter_chips() -> None:
    """Starters-banan: heron ska visa klickbara starter-chips som förifyller
    prompten OCH förväljer verksamhet i wizarden (initialAnswers).
    """
    hero = (VIEWSER_DIR / "components" / "marketing" / "hero-prompt-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "STARTER_PRESETS" in hero, "Heron ska rendera starter-presets som chips"
    assert "startWithPreset" in hero, (
        "Heron ska ha en preset-handler som förifyller prompt + familj"
    )
    assert "initialAnswers" in hero, (
        "Heron ska skicka förvalda svar till DiscoveryWizarden vid chip-klick"
    )


def test_studio_empty_state_offers_starters() -> None:
    """Starters-banan: en tom /studio (ingen handoff) ska visa starter-
    onboarding i stället för en blank canvas, och kunna konsumera en
    wizard-seed från en yrkessida/hero-chip.
    """
    builder = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "consumeWizardSeed" in builder, "PromptBuildern ska konsumera wizard-seed vid mount"
    assert "openWizardFromPreset" in builder and "STARTER_PRESETS" in builder, (
        "Tom-läget ska erbjuda starter-chips som öppnar wizarden förvald"
    )
    assert "showStarters" in builder, "PromptBuildern ska ha ett tom-läges-onboarding-tillstånd"


def test_wizard_seed_handoff_carries_hints_only() -> None:
    """Starters-banan: seed-handoffen får bara bära lätta hints
    (prompt + businessFamily + siteType) — inga fullständiga build-beslut
    och absolut inget starterId (samma invariant som /api/prompt).
    """
    handoff = (VIEWSER_DIR / "lib" / "init-prompt-handoff.ts").read_text(encoding="utf-8")
    assert "setWizardSeed" in handoff and "consumeWizardSeed" in handoff, (
        "init-prompt-handoff ska exponera set/consumeWizardSeed"
    )
    assert "businessFamily" in handoff and "siteType" in handoff, (
        "WizardSeed ska bära familj + kategori-hints"
    )
    assert "starterId" not in handoff, (
        "WizardSeed får inte bära starterId (backend äger scaffold-valet)"
    )


def test_about_page_has_founders_and_philosophy() -> None:
    """P5: /om-oss ska presentera båda grundarna (verbatim-roller) via
    FounderCard och den delade filosofin med slagordet.
    """
    about = (VIEWSER_DIR / "app" / "(marketing)" / "om-oss" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "FounderCard" in about, "/om-oss ska rendera grundarkort"
    assert "Jakob Eberg" in about and "Christopher Genberg" in about, (
        "Båda grundarna ska finnas med på /om-oss"
    )
    # Operatörens verbatim-beskrivningar.
    assert "AI-fantast och smått galen" in about, "Jakobs verbatim-roll ska stå kvar oförändrad"
    assert "Fullstack-utvecklare & bipolär" in about, (
        "Christophers verbatim-roll ska stå kvar oförändrad"
    )
    assert "Lämna huvudvärken att bygga och underhålla en hemsida med oss." in about, (
        "Slagordet ska finnas på /om-oss"
    )
    # Startsidans teaser (P2) ska länka in till /om-oss.
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert 'href="/om-oss"' in home, "Startsidans grundar-teaser ska länka till /om-oss"


def test_marketing_layout_has_skip_link() -> None:
    """P1: marknads-layouten ska ha en skip-länk till #main-content (WCAG
    2.4.1) och ett main-landmärke med matchande id.
    """
    layout = (VIEWSER_DIR / "app" / "(marketing)" / "layout.tsx").read_text(encoding="utf-8")
    assert 'href="#main-content"' in layout, "Layouten saknar skip-länk till #main-content"
    assert 'id="main-content"' in layout, (
        'Layouten saknar <main id="main-content"> som skip-länken pekar på'
    )


def test_cookie_consent_provider_persists_versioned_choice() -> None:
    """P6: cookie-consent ska vara en klient-provider som läser/skriver ett
    versionerat localStorage-val via det sanktionerade async-IIFE-mönstret
    (await Promise.resolve() före setState) — inte synkront setState i effect.
    """
    consent = (VIEWSER_DIR / "components" / "marketing" / "cookie-consent.tsx").read_text(
        encoding="utf-8"
    )
    assert consent.lstrip().startswith('"use client"'), (
        "cookie-consent måste vara en klientkomponent"
    )
    assert "sajtbyggaren.cookie-consent.v1" in consent, (
        "Consent-nyckeln ska vara versionerad så den kan migreras senare"
    )
    assert '"granted"' in consent and '"denied"' in consent, (
        "Consent ska lagra explicit granted/denied"
    )
    assert "await Promise.resolve()" in consent, (
        "Storage-läsningen ska följa async-IIFE-mönstret (set-state-in-effect)"
    )
    assert "localStorage.setItem" in consent, "Valet ska persisteras i localStorage"
    assert "export function useCookieConsent" in consent, "useCookieConsent-hooken ska exporteras"


def test_cookie_banner_is_non_blocking_with_manager() -> None:
    """P6: cookie-baren ska vara icke-blockerande (role=region, ingen
    cookie-wall) med accept/avvisa och en manager-dialog som kan öppnas igen.
    """
    banner = (VIEWSER_DIR / "components" / "marketing" / "cookie-banner.tsx").read_text(
        encoding="utf-8"
    )
    assert 'role="region"' in banner, "Cookie-baren ska vara en region, inte en wall"
    assert "Acceptera alla" in banner and "Endast nödvändiga" in banner, (
        "Baren ska ge både accept och endast-nödvändiga"
    )
    assert "Dialog" in banner and "managerOpen" in banner, (
        "Managern ska vara en dialog som styrs av managerOpen"
    )
    assert "useCookieConsent" in banner, "Baren ska läsa consent-state via hooken"
    # Baren ska bara visas innan ett val gjorts (consent === null).
    assert "consent === null" in banner, "Baren ska bara visas tills ett val gjorts"

    layout = (VIEWSER_DIR / "app" / "(marketing)" / "layout.tsx").read_text(encoding="utf-8")
    assert "CookieConsentProvider" in layout and "CookieBanner" in layout, (
        "Layouten ska wrappa marknadssajten i provider + rendera baren"
    )


def test_footer_has_manage_cookies_trigger() -> None:
    """P6: footern ska ha en 'Hantera cookies'-trigger som öppnar managern."""
    footer = (VIEWSER_DIR / "components" / "marketing" / "marketing-footer.tsx").read_text(
        encoding="utf-8"
    )
    assert "ManageCookiesButton" in footer, "Footern ska rendera 'Hantera cookies'-knappen"
    button = (VIEWSER_DIR / "components" / "marketing" / "manage-cookies-button.tsx").read_text(
        encoding="utf-8"
    )
    assert "openManager" in button, "Knappen ska öppna cookie-managern via consent-hooken"


def test_legal_pages_use_shared_legal_layout() -> None:
    """P6: cookies/integritetspolicy/användarvillkor ska byggas på den delade
    LegalPageLayout-komponenten (konsekvent prose + utkast-notis).
    """
    layout = (VIEWSER_DIR / "components" / "marketing" / "legal-page-layout.tsx").read_text(
        encoding="utf-8"
    )
    assert "Senast uppdaterad" in layout, "Legal-layouten ska visa senast-uppdaterad"
    for slug in ("cookies", "integritetspolicy", "anvandarvillkor"):
        page = (VIEWSER_DIR / "app" / "(marketing)" / slug / "page.tsx").read_text(encoding="utf-8")
        assert "LegalPageLayout" in page, f"/{slug} ska använda den delade LegalPageLayout"
    # Kontaktsidan ska vara ärlig: mailto, inget fejkat formulär-flöde.
    contact = (VIEWSER_DIR / "app" / "(marketing)" / "kontakt" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "mailto:" in contact, (
        "Kontaktsidan ska länka till e-post (mailto) tills en backend finns"
    )


def test_build_pipeline_has_no_auth_or_credit_imports() -> None:
    """Hård gräns (UI-utan-auth-PR, juni 2026): auth/billing är PARKERAT — det
    finns ingen auth-kod på den här branchen. Som framåtriktad spärr säkrar vi
    att bygg-ingångarna (runners + prompt-route + studions prompt-builder) inte
    importerar auth/session/credits, så en framtida auth-PR aldrig får läcka in
    i bygg-pipelinen.
    """
    for rel in ("lib/build-runner.ts", "lib/prompt-runner.ts", "lib/runs.ts"):
        text = (VIEWSER_DIR / rel).read_text(encoding="utf-8")
        assert "@/lib/auth" not in text and "lib/billing" not in text, (
            f"{rel} får inte importera auth/billing — bygget ska vara orört"
        )
    prompt_route = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(encoding="utf-8")
    assert "auth/session" not in prompt_route and "consumeCredits" not in prompt_route, (
        "Prompt-routen (bygg-ingången) får inte dra in auth/krediter"
    )
    builder = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "@/lib/auth" not in builder and "claim-site" not in builder, (
        "prompt-builder.tsx får inte importera auth eller anropa claim-site "
        "i den här PR:en — den ytan är parkerad"
    )


def test_marketing_hero_owns_build_cta() -> None:
    """u1: bygg-CTA:n ska bo på heron — besökaren beskriver sin sajt direkt
    där (HeroPromptForm) och slut-CTA:n scrollar tillbaka dit (#start),
    aldrig till studions tomma prompt-landning.
    """
    home = (VIEWSER_DIR / "app" / "(marketing)" / "page.tsx").read_text(encoding="utf-8")
    assert "HeroPromptForm" in home, (
        "Heron ska rendera HeroPromptForm (prompt direkt på startsidan)"
    )
    assert 'id="start"' in home and 'href="#start"' in home, (
        "Slut-CTA:n ska scrolla upp till hero-prompten (#start), inte studion"
    )


def test_hero_prompt_opens_wizard_and_hands_off_to_studio() -> None:
    """u1 (juni 2026): DiscoveryWizarden öppnas DIREKT på marknads-heron så
    besökaren stannar på den nya startsidan (hero + logotyp bakom popupen).
    Vid "Skapa sajt" lämnas hela wizard-resultatet över via wizard-handoffen
    och vi navigerar till studion, som bygger direkt utan en andra wizard.
    """
    form = (VIEWSER_DIR / "components" / "marketing" / "hero-prompt-form.tsx").read_text(
        encoding="utf-8"
    )
    assert "DiscoveryWizard" in form, "Heron ska rendera DiscoveryWizarden som popup på startsidan"
    assert "setWizardHandoff" in form and "STUDIO_HREF" in form, (
        "Heron ska lämna över hela wizard-resultatet och navigera till studion"
    )
    # Scout-fynd (P1, 2026-06-05): hero-textarean kan vara TOM när besökaren
    # öppnade wizarden direkt och bara fyllde "Vad gör ni?" där (answers.offer).
    # Handoffen måste falla tillbaka på offer-svaret så discovery.rawPrompt
    # aldrig blir "" — annars tappas "Operatörens beskrivning" ur master-prompten.
    assert "prompt.trim() || answers.offer.trim()" in form, (
        "Hero-handoffen måste falla tillbaka på wizardens offer-svar när hero-"
        'textarean är tom — annars blir discovery.rawPrompt "" och '
        "'Operatörens beskrivning' tappas ur master-prompten på /studio."
    )
    builder = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "consumeWizardHandoff" in builder, (
        "PromptBuildern ska konsumera wizard-handoffen vid mount"
    )
    assert "startBuildFromWizardHandoff" in builder, (
        "PromptBuildern ska bygga direkt från wizard-handoffen (ingen andra wizard i studion)"
    )


def test_marketing_has_sitemap_and_robots() -> None:
    """P8: SEO-finish — sitemap ska täcka statiska sidor + 20 yrkessidor;
    robots ska indexera marknaden men blockera /studio + /api.
    """
    sitemap = (VIEWSER_DIR / "app" / "sitemap.ts").read_text(encoding="utf-8")
    assert "PROFESSIONS" in sitemap, (
        "Sitemap ska generera per-yrke-sidor från professions-registret"
    )
    assert "/for/" in sitemap, "Sitemap ska inkludera /for/[yrke]-sidorna"

    robots = (VIEWSER_DIR / "app" / "robots.ts").read_text(encoding="utf-8")
    assert "/studio" in robots and "/api/" in robots, (
        "Robots ska blockera konsolen (/studio) och /api"
    )
    assert "sitemap" in robots, "Robots ska peka på sitemap.xml"


def test_floating_chat_first_run_hint_surfaces_core_loop() -> None:
    """Synliggör kärnloopen: FloatingChat ska visa en första-gångs-hint som
    förklarar att en följdprompt bygger om sajten OCH att varje bygge blir en
    ny version. Hinten ska vara dismiss:bar och persisterad (en gång per
    webbläsare) och erbjuda en djuplänk till versionsvyn.
    """
    chat = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "Så funkar det" in chat, "FloatingChat ska ha en första-gångs-hint som förklarar loopen"
    assert "ny version" in chat, "Hinten ska nämna att varje bygge blir en ny version"
    assert "STORAGE_KEY_LOOP_HINT" in chat and "readLoopHintSeen" in chat, (
        "Hinten ska persistera dismissen så den bara visas en gång"
    )
    assert "onShowVersions" in chat and "Visa versioner" in chat, (
        "Hinten ska kunna djuplänka till versionsvyn"
    )
    shell = (VIEWSER_DIR / "components" / "builder" / "builder-shell.tsx").read_text(
        encoding="utf-8"
    )
    assert "onShowVersions={onOpenHistory}" in shell, (
        "BuilderShell ska koppla 'Visa versioner' till historik-ingången"
    )


# ---------------------------------------------------------------------------
# UX-batch (versionssynlighet / preview-tillstånd / FloatingChat / a11y).
# Source-lock-tester som låser de fyra in-lane-förbättringarna så de inte
# tyst tas bort i framtida UI-refactor.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_history_pending_dot_is_distinct_and_pulses() -> None:
    """S1: `pending` (faktiskt pågående bygge) ska ha en egen färg + puls
    så det inte konflateras med de grå terminal-statusarna skipped/unknown.
    """
    text = (VIEWSER_DIR / "components" / "run-history.tsx").read_text(encoding="utf-8")
    assert 'pending: "bg-sky-400"' in text, (
        "Run History ska ge pending en egen sky-färg, inte falla igenom "
        "till den grå muted-foreground-pricken."
    )
    assert 'status === "pending"' in text and "motion-safe:animate-pulse" in text, (
        "pending-pricken ska pulsera (motion-safe) för att signalera pågående bygge."
    )
    assert "formatAbsolute" in text and "toLocaleString" in text, (
        "Relativa tider ska ha en absolut tidsstämpel-tooltip (title) via formatAbsolute."
    )


@pytest.mark.tooling
def test_versions_tab_status_palette_and_absolute_timestamp() -> None:
    """S1: Versioner-tabbens status-palett ska vara konsekvent med
    run-history (pending + aborted) och visa absolut tidsstämpel-tooltip.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx").read_text(
        encoding="utf-8"
    )
    assert 'pending: "bg-sky-400"' in text and 'aborted: "bg-destructive"' in text, (
        "Versioner-tabben ska spegla run-history-paletten (pending + aborted) "
        "så de två versionsvyerna är konsekventa."
    )
    assert "formatAbsolute" in text, (
        "Versioner-tabben ska ha samma absolut-tidsstämpel-tooltip som run-history."
    )


@pytest.mark.tooling
def test_viewer_panel_iframe_has_load_state_overlay() -> None:
    """S2: preview-iframen ska flippa ett iframeLoaded-state via onLoad och
    visa en skelett-overlay tills dokumentet laddat, gate:ad mot
    isBuilding/isFinalizing så den inte dubblerar BuildProgressCard.
    """
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
    assert "iframeLoaded" in text and "setIframeLoaded" in text, (
        "ViewerPanel ska spåra iframens laddningsstatus."
    )
    assert "onLoad={() => setIframeLoaded(true)}" in text, (
        "Iframens onLoad ska flippa iframeLoaded → overlayn döljs."
    )
    assert "!iframeLoaded && !isBuilding && !isFinalizing" in text, (
        "Skelett-overlayn ska gate:as mot build-tillstånd så den inte dubblerar BuildProgressCard."
    )


@pytest.mark.tooling
def test_floating_chat_failed_build_offers_retry() -> None:
    """S3: ett pipeline-failed bygge (summary.variant === 'error') ska
    sätta retryPrompt så ErrorBubble visar 'Försök igen'. Tidigare fick
    bara HTTP/network-fel en retry-knapp, inte själva bygg-felet.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert 'summary.variant === "error" ? trimmed || undefined : undefined' in text, (
        "Failed-bygget ska sätta retryPrompt så retry-knappen dyker upp."
    )


@pytest.mark.tooling
def test_wizard_tab_strip_is_keyboard_navigable() -> None:
    """S4: wizard-stegstripen ska följa WAI-ARIA tabs-mönstret — roving
    tabindex, pil/Home/End-navigering och tabpanel-koppling.
    """
    text = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "tabIndex={isActive ? 0 : -1}" in text, (
        "Stegstripen ska använda roving tabindex (bara aktiv flik i tab-ordningen)."
    )
    assert '"ArrowRight"' in text and '"Home"' in text and '"End"' in text, (
        "Stegstripen ska hantera pil/Home/End-navigering."
    )
    assert 'role="tabpanel"' in text and 'aria-controls="wizard-tabpanel"' in text, (
        "Flikarna ska peka på en tabpanel (aria-controls) och panelen ska ha role=tabpanel."
    )


@pytest.mark.tooling
def test_more_info_dialog_tab_strip_is_keyboard_navigable() -> None:
    """Scout-fynd (P1, 2026-06-05, två oberoende agenter): MoreInfoDialog-
    flikarna hade role=tab/aria-selected men SAKNADE pil/Home/End-tangentbord,
    roving tabindex och tabpanel-koppling — inne i Dialog-portalen gick de inte
    att nå med tangentbord (till skillnad från huvud-wizardens stegstrip).
    Lås att MoreInfoDialog nu följer samma WAI-ARIA tabs-mönster.
    """
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "more-info-dialog.tsx"
    ).read_text(encoding="utf-8")
    assert "tabIndex={isActive ? 0 : -1}" in text, (
        "MoreInfoDialog-flikarna ska använda roving tabindex (bara aktiv flik i "
        "tab-ordningen)."
    )
    assert '"ArrowRight"' in text and '"Home"' in text and '"End"' in text, (
        "MoreInfoDialog-flikarna ska hantera pil/Home/End-navigering."
    )
    assert 'role="tabpanel"' in text and 'aria-controls="more-info-tabpanel"' in text, (
        "MoreInfoDialog-flikarna ska peka på en tabpanel (aria-controls) och "
        "panelen ska ha role=tabpanel + aria-labelledby."
    )


@pytest.mark.tooling
def test_quality_tab_reads_canonical_artefact_schema() -> None:
    """P0: Kvalitet-tabben måste läsa de canonical artefakt-shaparna, inte
    ett påhittat parallellt schema. Den läste tidigare qualityResult.findings
    / qualityResult.gates och repairResult.actions — fält som inte finns —
    vilket fick failade runs att visa "Quality Gate gick rent" och dolde
    hela Repair Pipeline-blocket.

    Sanningskällor:
      - packages/generation/quality_gate/models.py: QualityResult har
        status + checks[] (name/status/detail/severity/findings).
      - packages/generation/repair/models.py: RepairResult har status,
        iterations, mechanicalFixesApplied[], remainingErrors[],
        qualityStatusBefore.
      - build-result.json: runDurationMs (inte durationMs), inget exitCode.

    Source-lock så en framtida refaktor inte kan återinföra fel fältnamn
    och tysta gate-resultatet igen.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "quality-tab.tsx").read_text(
        encoding="utf-8"
    )

    # Quality Gate: måste läsa checks[] + status + summary (canonical), inte
    # findings/gates (det icke-existerande parallella schemat).
    assert "qualityResult.checks" in text, (
        "Kvalitet-tabben ska läsa qualityResult.checks[] (canonical), inte "
        "qualityResult.findings/gates."
    )
    assert "qualityResult.status" in text, (
        "Kvalitet-tabben ska visa gate-status från qualityResult.status."
    )
    assert "qualityResult.findings" not in text and "qualityResult.gates" not in text, (
        "Kvalitet-tabben får inte läsa det påhittade findings/gates-schemat — "
        "det var P0-buggen som fick failade runs att se rena ut."
    )
    assert 'check.status === "failed"' in text, (
        "Kvalitet-tabben ska härleda failade checks från check.status, inte "
        "anta att en tom findings-lista betyder rent gate."
    )

    # Repair Pipeline: canonical mechanicalFixesApplied/remainingErrors, inte actions.
    assert "repairResult.mechanicalFixesApplied" in text, (
        "Repair-blocket ska läsa repairResult.mechanicalFixesApplied[]."
    )
    assert "repairResult.remainingErrors" in text, (
        "Repair-blocket ska läsa repairResult.remainingErrors[]."
    )
    assert "repairResult.actions" not in text, (
        "Repair-blocket får inte läsa det icke-existerande repairResult.actions."
    )

    # Build: runDurationMs (inte durationMs), inget exitCode-fält.
    assert "buildResult.runDurationMs" in text, (
        "Build-statusen ska läsa runDurationMs (canonical), inte durationMs."
    )
    assert "buildResult.durationMs" not in text and "buildResult.exitCode" not in text, (
        "Build-statusen får inte läsa durationMs/exitCode — de finns inte i build-result.json."
    )

    # A1 (2026-06-05): kor-4a/4b copy-kritik läses från qualityResult.critic
    # (score/source/issues[]) — warning-lane som backend skriver men UI tidigare
    # aldrig visade. Source-lock så en refaktor inte tappar critic-ytan igen.
    assert "qualityResult.critic" in text, (
        "Kvalitet-tabben måste läsa qualityResult.critic (kor-4a/4b) — score, "
        "source och issues[] skrivs av critic-lanen men visades inte alls."
    )
    assert "repairHint" in text and "issue.target" in text, (
        "Critic-blocket ska visa issue.repairHint + issue.target så operatören "
        "ser var fyndet ligger och får ett konkret fix-förslag."
    )

    # A2 (2026-06-05): repair-telemetri som backend redan skriver men UI tappade
    # — gate-efter, reason, blueprint-repairs (kor-5), llm-fixes och per-check
    # severity/durationMs. Source-lock per fält.
    assert "repairResult.qualityStatusAfter" in text, (
        "Repair-blocket ska visa gate-status EFTER reparationen "
        "(qualityStatusAfter), inte bara qualityStatusBefore."
    )
    assert "repairResult.reason" in text, (
        "Repair-blocket ska visa repairResult.reason (operatörsförklaring av "
        "varför pipelinen stannade på sin status)."
    )
    assert "repairResult.blueprintRepairs" in text, (
        "Repair-blocket ska visa kor-5 blueprintRepairs[] (issueType/field/"
        "success) — annars är blueprint-repair-telemetrin osynlig."
    )
    assert "repairResult.llmFixesApplied" in text, (
        "Repair-blocket ska läsa llmFixesApplied[] (tomt idag, populeras "
        "Sprint 5+) så framtida LLM-fixar syns utan ny UI-deploy."
    )
    assert "check.durationMs" in text and "check.severity" in text, (
        "Check-raden ska visa severity (blocking/warning) och durationMs så "
        "operatören ser blockerande vs varning och gate-latens per check."
    )


@pytest.mark.tooling
def test_run_details_panel_repair_fix_reads_canonical_fields() -> None:
    """B3 (2026-06-05): RepairSection läste ``fix.status`` / ``fix.description``
    — fält som inte finns på RepairFix. Canonical shape
    (packages/generation/repair/models.py:RepairFix + repair-result.schema.json
    :$defs.repairFix) är ``kind``/``name``/``target``/``detail``/``success``.
    Effekten var att mekaniska fixar renderades namn-bara (success + operatörs-
    detalj tappades tyst). Source-lock att panelen läser de riktiga fälten.
    """
    text = (VIEWSER_DIR / "components" / "run-details-panel.tsx").read_text(
        encoding="utf-8"
    )
    assert "fix.status" not in text and "fix.description" not in text, (
        "run-details-panel får inte läsa fix.status/fix.description — de finns "
        "inte på RepairFix (canonical: success/detail/kind/target)."
    )
    assert "fix.success" in text and "fix.detail" in text, (
        "RepairSection ska visa fix.success (fixad/misslyckades) och fix.detail "
        "från den canonical RepairFix-shapen."
    )


@pytest.mark.tooling
def test_floating_chat_surfaces_unapplied_followup_intents() -> None:
    """A3 (2026-06-05): backend skriver ``unappliedFollowupIntents`` (lista av
    {target, reason}) i build-result.json — följd-asks den deterministiska v1-
    pipelinen kände igen men inte kunde applicera. FloatingChat ignorerade dem
    helt; operatören såg bara den generiska no-op-raden. Source-lock att UI:t
    läser fältet och appenderar det till no-op-/degraded-grenarna.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "function summarizeUnappliedFollowupIntents(" in text, (
        "FloatingChat måste ha en helper som läser unappliedFollowupIntents "
        "defensivt (samma mönster som extractAppliedVisibleEffect)."
    )
    assert "buildResult.unappliedFollowupIntents" in text, (
        "Helpern måste läsa unappliedFollowupIntents från build-result-payloaden."
    )
    assert "const unappliedNote = summarizeUnappliedFollowupIntents(" in text, (
        "summarizeBuildResult ska beräkna en unapplied-svans en gång och "
        "appenda den i no-op-/degraded-grenarna."
    )
    assert text.count("${unappliedNote}") >= 3, (
        "unappliedNote ska appendas i båda no-op-grenarna OCH degraded-grenen "
        "så oapplicerade följd-asks blir synliga oavsett utfall."
    )


@pytest.mark.tooling
def test_dossiers_tab_handles_flat_selected_dossiers() -> None:
    """P1: site-plan.json:selectedDossiers är ANTINGEN en platt id-lista
    (vanligast) eller objektformen { required, recommended, conditional,
    rejected }. Tabben castade tidigare alltid till objekt → den platta
    listan tappade alla fält och fyra tomma grupper visades på vanliga runs.
    Source-lock att båda formerna hanteras (Array.isArray-gren)."""
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "dossiers-tab.tsx").read_text(
        encoding="utf-8"
    )
    assert "Array.isArray(rawSelected)" in text, (
        "Dossiers-tabben måste detektera den platta listformen av "
        "selectedDossiers (Array.isArray), inte bara objektformen."
    )
    assert "isFlatList" in text, (
        "Dossiers-tabben ska rendera en 'Valda'-grupp för den platta listan "
        "istället för fyra tomma objekt-grupper."
    )


@pytest.mark.tooling
def test_floating_chat_copy_directive_keeps_exact_change_set() -> None:
    """P1: när en run har BÅDE copy-direktiv OCH en exakt change-set (routes/
    variant) ska den strukturella change-set:en fortfarande visas under
    'Ändrat'. Tidigare returnerade copy-grenen utan changes och dolde
    tillagda/borttagna sidor. Source-lock att exactChanges beräknas före
    copy-grenen och bifogas där."""
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    copy_idx = text.find("const copyLines = summarizeCopyDirectives")
    exact_idx = text.find("const exactChanges = summarizeChangeSet")
    assert exact_idx != -1 and copy_idx != -1, (
        "Både exactChanges och copyLines måste härledas i build-outcome-mappningen."
    )
    assert exact_idx < copy_idx, (
        "exactChanges måste beräknas FÖRE copy-grenen så copy-grenen kan "
        "bifoga den strukturella change-set:en."
    )


@pytest.mark.tooling
def test_floating_chat_persist_gated_on_hydration() -> None:
    """P1: persist-effekterna i FloatingChat skrev default-värdet ('false')
    till localStorage vid mount INNAN hydrerings-IIFE:n läst stored-värdena,
    och nollställde därmed operatörens sparade minimized/quick-prompts-
    preference. Source-lock att en hasHydratedRef-gate finns."""
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "hasHydratedRef" in text, (
        "FloatingChat ska gat:a persist-effekterna mot en hasHydratedRef så "
        "default-värden inte skriver över sparad localStorage före hydrering."
    )
    assert text.count("if (!hasHydratedRef.current) return;") >= 3, (
        "Alla tre persist-effekterna (position/minimized/quick-prompts) ska "
        "early-returna tills hydreringen läst klart."
    )


@pytest.mark.tooling
def test_discovery_wizard_gates_forward_jumps() -> None:
    """P1: tab-klick, pil-navigering och ⌥-siffra hoppade tidigare till valfritt
    steg utan validering → operatören kunde skippa ett halvfyllt foundation-
    steg. Source-lock att en resolveReachableStep-gate clamp:ar framåt-hopp
    mot maxReachableStep (bakåt fortsatt fritt)."""
    text = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "maxReachableStep" in text and "resolveReachableStep" in text, (
        "Wizarden ska beräkna maxReachableStep och routa hopp genom resolveReachableStep."
    )
    assert "resolveReachableStep(idx, current)" in text, (
        "Tab-klick ska gå genom resolveReachableStep, inte rå setStepIndex(idx)."
    )


@pytest.mark.tooling
def test_visual_step_revalidates_vibe_against_scaffold() -> None:
    """P1: vid family-byte av-/återmonteras VisualStep men auto-default-
    effekten early-returnade så snart vibeId var truthy → ett stale vibe-id
    från föregående family behölls (syntes ej markerat men låg kvar i
    payloaden). Source-lock att den nu validerar mot vibes-listan."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "visual-step.tsx"
    ).read_text(encoding="utf-8")
    assert (
        "currentVibeValid" in text and "vibes.some((v) => v.id === answers.vibe.vibeId)" in text
    ), (
        "VisualStep ska validera vald vibe mot scaffoldens vibe-lista och "
        "byta ut en stale vibe mot familjens default."
    )


@pytest.mark.tooling
def test_tokens_tab_clears_session_storage_on_commit() -> None:
    """P1: sessionStorage-overrides överlevde en commit och återuppväcktes vid
    reload — trots att färgerna redan bakats in i sajten — så tabben erbjöd
    om samma commit i oändlighet. Source-lock att handleCommit rensar storage
    och att en settle-effekt tömmer buffern efter bygget."""
    text = (VIEWSER_DIR / "components" / "builder" / "inspector" / "tokens-tab.tsx").read_text(
        encoding="utf-8"
    )
    commit_idx = text.find("const handleCommit = useCallback(")
    assert commit_idx != -1, "tokens-tab.tsx ska ha handleCommit."
    # clearStoredTokens måste anropas inom handleCommit (före onPrompt).
    window = text[commit_idx : commit_idx + 600]
    assert "clearStoredTokens();" in window, (
        "handleCommit ska rensa sessionStorage vid commit så overrides inte "
        "återuppväcks vid reload."
    )
    assert "committedPromptRef" in text, (
        "Tokens-tabben ska spåra den committade prompten och settle:a buffern "
        "efter att bygget konsumerat den."
    )


@pytest.mark.tooling
def test_focus_trap_hook_used_by_custom_dialogs() -> None:
    """P1: de custom overlay-dialogerna (AI-bildgenerator + wizardens
    kortkommando-overlay) saknade focus-trap trots role=dialog/aria-modal.
    Source-lock att useFocusTrap-hooken finns och används i båda."""
    hook = VIEWSER_DIR / "lib" / "use-focus-trap.ts"
    assert hook.exists(), "lib/use-focus-trap.ts ska finnas."
    hook_text = hook.read_text(encoding="utf-8")
    assert "export function useFocusTrap" in hook_text, (
        "use-focus-trap.ts ska exportera useFocusTrap."
    )
    ai_dialog = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "ai-image-generator-dialog.tsx"
    ).read_text(encoding="utf-8")
    wizard = (VIEWSER_DIR / "components" / "discovery-wizard" / "discovery-wizard.tsx").read_text(
        encoding="utf-8"
    )
    assert "useFocusTrap(dialogRef, open)" in ai_dialog, (
        "AI-bilddialogen ska fånga Tab inom dialogen via useFocusTrap."
    )
    assert "useFocusTrap(helpPanelRef, helpOpen)" in wizard, (
        "Wizardens kortkommando-overlay ska fånga Tab via useFocusTrap."
    )


@pytest.mark.tooling
def test_viewer_panel_unavailable_banner_has_retry() -> None:
    """P2: otillgänglig-bannern var helt pointer-events-none utan retry —
    operatören tvingades välja om runen för att hämta om previewn. Source-lock
    att kortet är klickbart (pointer-events-auto) och bumpar en retryNonce som
    ingår i preview-effektens deps."""
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
    assert "retryNonce" in text and "[runId, siteId, retryNonce]" in text, (
        "Preview-effekten ska köra om när retryNonce bumpas."
    )
    assert "setRetryNonce((n) => n + 1)" in text and "Försök igen" in text, (
        "Otillgänglig-bannern ska ha en 'Försök igen'-knapp som bumpar retryNonce."
    )


@pytest.mark.tooling
def test_viewer_panel_hero_respects_reduced_motion() -> None:
    """P2: studio-hero-videorna autoplayade alltid (ingen reduced-motion-
    respekt). Source-lock att autoPlay/loop gat:as mot en reducedMotion-flagga
    läst via useSyncExternalStore (samma kontrakt som marketing-hero:n)."""
    text = (VIEWSER_DIR / "components" / "viewer-panel.tsx").read_text(encoding="utf-8")
    assert "useSyncExternalStore" in text and "reducedMotion" in text, (
        "ViewerPanel ska läsa prefers-reduced-motion via useSyncExternalStore."
    )
    assert text.count("autoPlay={!reducedMotion}") >= 2, (
        "Båda hero-videorna (mobil + desktop) ska sluta autoplaya under reduced-motion."
    )


@pytest.mark.tooling
def test_site_inspector_tab_controlled_and_clears_error() -> None:
    """P2: <Tabs> använde defaultValue och av-/återmonterades vid refresh →
    aktiv tab nollades till 'Sidor'; och buildError överlevde sheet-stängning.
    Source-lock att tab-värdet är kontrollerat och clearError körs vid stängning."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "site-inspector-sheet.tsx"
    ).read_text(encoding="utf-8")
    assert "value={activeTab}" in text and "onValueChange={setActiveTab}" in text, (
        "Inspector-tabbarna ska vara kontrollerade så valet överlever refresh."
    )
    assert "if (!open) clearError();" in text, (
        "buildError ska rensas när inspectorn stängs."
    )


@pytest.mark.tooling
def test_compare_modal_sets_cross_origin_isolated() -> None:
    """P2: jämförelse-embedden saknade crossOriginIsolated (paritet med
    ViewerPanel) → WebContainern kunde faila att boota. Source-lock att flaggan
    sätts."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "compare-preview-modal.tsx"
    ).read_text(encoding="utf-8")
    assert "crossOriginIsolated: true," in text, (
        "Compare-modalens embed ska sätta crossOriginIsolated för paritet med ViewerPanel."
    )


@pytest.mark.tooling
def test_payload_popover_uses_effective_scaffold_hint() -> None:
    """P2: popover:n härledde scaffoldHint bara från family.scaffoldHint och
    missade sub-kategori-uppgraderingar → visade en annan hint än backend fick.
    Source-lock att den använder deriveEffectiveScaffoldHint (samma som
    buildDiscoveryPayload)."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "payload-alignment-popover.tsx"
    ).read_text(encoding="utf-8")
    assert "deriveEffectiveScaffoldHint(family, answers.siteType)" in text, (
        "Popover:n ska härleda scaffoldHint via deriveEffectiveScaffoldHint."
    )


@pytest.mark.tooling
def test_floating_chat_uses_outcome_to_stage() -> None:
    """P2: onStageChange mappade degraded/unknown → 'success' så progress-cardet
    visade grönt medan chatten rapporterade varning. Source-lock att den nu
    delar outcomeToStage med PromptBuilder."""
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "onStageChange?.(outcomeToStage(outcome));" in text, (
        "FloatingChat ska mappa outcome via outcomeToStage (degraded ≠ success)."
    )


@pytest.mark.tooling
def test_asset_dropzone_keeps_partial_uploads() -> None:
    """P2: vid fel på fil N i en multi-upload kastades de redan uppladdade
    filerna 1..N-1 bort (onUploaded kördes aldrig) → föräldralösa på servern.
    Source-lock att catch-grenen lyfter de lyckade uppladdningarna."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "asset-dropzone.tsx"
    ).read_text(encoding="utf-8")
    assert "if (uploaded.length > 0) onUploaded(uploaded);" in text, (
        "Partiellt misslyckad batch ska ändå lyfta de redan uppladdade filerna."
    )


@pytest.mark.tooling
def test_assets_step_auto_hero_is_decoupled() -> None:
    """P2: auto-hero delade objektreferens med galleri-raden (alt/placement
    forkade tyst) och en galleri-borttagning nollade inte hero. Source-lock att
    kandidaten klonas och att hero nollas när dess källrad tas bort."""
    text = (
        VIEWSER_DIR / "components" / "discovery-wizard" / "steps" / "assets-step.tsx"
    ).read_text(encoding="utf-8")
    assert "heroImage: { ...candidate }" in text, (
        "Auto-hero ska klona kandidaten så den inte delar referens med galleri-raden."
    )
    assert "heroFromThisRow" in text, (
        "Borttagning av en galleri-rad ska nolla hero om den auto-pickades därifrån."
    )


@pytest.mark.tooling
def test_versions_tab_refetches_on_active_bundle_change() -> None:
    """P2: compare-diffen re-fetchade bara på id-byten → om ena sidan var den
    aktiva runen och dess bundle byggdes om visades en stale diff. Source-lock
    att en activeBundleSignal ingår i fetch-effektens deps."""
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "versions-tab.tsx"
    ).read_text(encoding="utf-8")
    assert "activeBundleSignal" in text, (
        "CompareSection ska härleda en activeBundleSignal för den aktiva sidan."
    )
    assert "[runIdA, runIdB, currentRunId, activeBundleSignal]" in text, (
        "Fetch-effekten ska re-köra när den aktiva runens bundle ändras."
    )


@pytest.mark.tooling
def test_toast_dedupes_and_caps_stack() -> None:
    """P2: identiska toaster (t.ex. upprepade retry-fel) staplades obegränsat.
    Source-lock att show:en dedupar mot aktiva toaster och har ett max-stack-tak."""
    text = (VIEWSER_DIR / "components" / "ui" / "toast.tsx").read_text(encoding="utf-8")
    assert "MAX_VISIBLE_TOASTS" in text, (
        "Toast-systemet ska ha ett tak (MAX_VISIBLE_TOASTS) på samtidiga toaster."
    )
    assert "const duplicate = toastsRef.current.find(" in text, (
        "show() ska deduplicera identiska aktiva toaster i st.f. att stapla dubbletter."
    )


@pytest.mark.tooling
def test_followup_build_hook_supports_global_lock_and_base_run_id() -> None:
    """C1 + C2 (scout-fynd 2026-06-05): useFollowupBuild ägde varken globalt
    bygg-lås eller "Iterera från denna"-pin.

    C2: varje dialog hade bara sin egen lokala isBusy → två öppna dialoger
    (eller en dialog + FloatingChat) kunde starta parallella byggen mot samma
    siteId. Hooken måste ta emot ett globalt ``isBuilding`` och avvisa när det
    är sant.

    C1: FloatingChat skickade redan ``baseRunId`` men dialogerna gjorde det
    inte → en pinnad iteration tappades tyst när operatören bytte t.ex. färg.
    Hooken måste ta emot ``baseRunId`` och inkludera den i fetch-bodyn.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "use-followup-build.ts").read_text(
        encoding="utf-8"
    )
    assert "isBuilding?: boolean;" in text, (
        "useFollowupBuild måste exponera ett globalt isBuilding-bygg-lås (C2)."
    )
    assert "baseRunId?: string | null;" in text, (
        "useFollowupBuild måste ta emot baseRunId för 'Iterera från denna' (C1)."
    )
    assert "if (isBusy || isBuilding) {" in text, (
        "runFollowup måste avvisa när ett globalt bygge pågår, inte bara lokalt (C2)."
    )
    assert "...(baseRunId ? { baseRunId } : {})" in text, (
        "runFollowup måste skicka baseRunId i bodyn när en pin är aktiv (C1)."
    )


@pytest.mark.tooling
def test_builder_shell_threads_lock_and_base_run_id_into_dialogs() -> None:
    """C1 + C2: BuilderShell måste skicka både det globala isBuilding-låset och
    den aktiva baseRunId-pinnen till alla bygg-utlösande dialoger (variant/
    färg/bild/scrape). Utan detta är hookens nya parametrar döda på dialog-
    vägen och pin/lock gäller bara FloatingChat + Inspector.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "builder-shell.tsx").read_text(
        encoding="utf-8"
    )
    # Minst fyra dialoger (variant/color/asset/scrape) ska få bägge propsen.
    assert text.count("baseRunId={pendingBaseRunId?.baseRunId ?? null}") >= 4, (
        "Alla fyra bygg-dialoger måste få baseRunId från BuilderShell (C1)."
    )
    assert text.count("isBuilding={isBuilding}") >= 4, (
        "Alla fyra bygg-dialoger måste få det globala isBuilding-låset (C2)."
    )


@pytest.mark.tooling
def test_inspector_threads_base_run_id_into_followup_hook() -> None:
    """C1: Inspectorns quick-prompts (t.ex. 'Be om fix' i Kvalitet) gick via
    useFollowupBuild men skickade aldrig den pinnade baseRunId:n. Lås att
    SiteInspectorSheet trådar pendingBaseRunId in i hooken.
    """
    text = (
        VIEWSER_DIR / "components" / "builder" / "inspector" / "site-inspector-sheet.tsx"
    ).read_text(encoding="utf-8")
    assert "baseRunId: pendingBaseRunId?.baseRunId ?? null," in text, (
        "SiteInspectorSheet måste skicka pendingBaseRunId till useFollowupBuild (C1)."
    )


@pytest.mark.tooling
def test_floating_chat_trace_polling_covers_dialog_builds() -> None:
    """C3 (scout-fynd 2026-06-05): trace-polling + stage-refine var gated på
    enbart ``isSending`` (FloatingChat:s egna byggen). Ett dialog-bygge driver
    page-level ``isBuilding`` men inte isSending → BuildProgressCard frös på
    'thinking' hela bygget. Lås att både polling-enabled och stage-refinen
    körs på ``isSending || isBuilding``.
    """
    text = (VIEWSER_DIR / "components" / "builder" / "floating-chat.tsx").read_text(
        encoding="utf-8"
    )
    assert "enabled: isSending || isBuilding," in text, (
        "trace-polling måste aktiveras även för dialog-byggen (isBuilding), C3."
    )
    assert "if ((!isSending && !isBuilding) || !onStageChange) return;" in text, (
        "stage-refinen måste köra för dialog-byggen (isBuilding), inte bara isSending (C3)."
    )


@pytest.mark.tooling
def test_viewer_panel_site_id_follows_selected_run() -> None:
    """C4 (P0, scout-fynd 2026-06-05): ViewerPanel fick siteId={selectedSiteId}
    medan runId={selectedRunId}. Project Input-väljaren kan sätta selectedSiteId
    utan att rensa selectedRunId → previewen (/api/preview/<siteId>) startade
    fel .generated/<siteId>/ medan runId pekade på en annan sajt. Lås att
    siteId följer den valda runens faktiska site (runSiteId) med picker-sajten
    som fallback.
    """
    text = (VIEWSER_DIR / "app" / "(console)" / "studio" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "siteId={runSiteId ?? selectedSiteId}" in text, (
        "ViewerPanel:s siteId måste följa den valda runens site (runSiteId) så "
        "preview-POST:en inte desynkar mot runId (C4)."
    )


@pytest.mark.tooling
def test_prompt_builder_does_not_replay_stale_stage_on_callback_change() -> None:
    """C5 (scout-fynd 2026-06-05): stage-rapporteringen var gated på
    [stage, onStageChange]. onStageChange byter identitet i page.tsx
    (builderActive ? undefined : setBuildStage), så vid 'Ny sajt' re-kördes
    effekten med ett oförändrat stage (oftast 'success' från init-bygget) och
    skrev över 'idle' som onNewSite precis satt → ViewerPanel visade ett stale
    success-card. Lås att vi bara rapporterar när stage FAKTISKT ändrats sedan
    förra rapporten (ref-vakt).
    """
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(encoding="utf-8")
    assert "lastReportedStageRef" in text, (
        "PromptBuilder måste spåra senast rapporterade stage i en ref (C5)."
    )
    assert "if (lastReportedStageRef.current === stage) return;" in text, (
        "stage-effekten måste bail:a när stage är oförändrat så en ren "
        "callback-identitetsändring inte replayar ett stale stage (C5)."
    )
