"""Structural / scope-discipline guards for the Viewser MVP file layout."""

from __future__ import annotations

import json
import subprocess

import pytest

from tests.support.viewser import NAMING_PATH, REPO_ROOT, VIEWSER_DIR


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
