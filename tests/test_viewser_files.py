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
def test_prompt_builder_exposes_followup_mode_and_cleans_stage_timer() -> None:
    text = (VIEWSER_DIR / "components" / "prompt-builder.tsx").read_text(
        encoding="utf-8"
    )
    assert '"followup"' in text and "Följdprompt på vald run/siteId" in text, (
        "PromptBuilder måste låta operatorn välja följdprompt-läge."
    )
    assert "clearTimeout(stageTimerRef.current)" in text, (
        "PromptBuilder måste städa stage-transition-timeouten vid unmount "
        "och när prompt-anropet avslutas."
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

    # Isolate the success-path block from the dynamic import to the
    # final setStatus call.
    block = re.search(
        r"const sdk = \(await import\(\"@stackblitz/sdk\"\)\)[\s\S]*?setStatus\(`Förhandsvisning aktiv",
        text,
    )
    assert block, (
        "viewer-panel.tsx: kunde inte hitta success-path-blocket från "
        "StackBlitz-import till final setStatus. Refactor utan ekvivalent "
        "kommunikation av runId-success bryter detta test."
    )
    cancelled_checks = re.findall(r"\bcancelled\b", block.group(0))
    assert len(cancelled_checks) >= 2, (
        "viewer-panel.tsx success-path saknar tillräcklig cancelled-guard-"
        "täthet mellan StackBlitz-import och setStatus. Förväntat minst 2 "
        "cancelled-referenser (en efter import, en efter embedProject) - "
        f"hittade {len(cancelled_checks)}. B43-fyndet: stale embed kan "
        "mountas i ref-divden om operatör byter runId mid-flight."
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
    # the `response.status === 404` check and `setUnavailable(true)`.
    # Multi-line regex is more robust than substring tricks here.
    pattern = re.compile(
        r"response\.status\s*===\s*404[\s\S]{0,400}?if\s*\(\s*cancelled\s*\)\s*return\s*;[\s\S]{0,200}?setUnavailable\(true\)",
        re.MULTILINE,
    )
    assert pattern.search(text), (
        "viewer-panel.tsx 404-branch saknar cancelled-guard innan "
        "setUnavailable / setStatus. Det skapar race-condition mellan "
        "snabba runId-byten där en stale 404 skriver över state för en "
        "nyladdad run."
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
