"""Source-locks för Projektinnehåll-ytan (composition-route + panel).

Ytan visar operatören vad sajt-projektet faktiskt består av — sidor,
funktioner (dossiers), komponenter och npm-paket (bas + dossier-tillagda
per ADR 0056) — DERIVERAT ur befintliga källor utan ny lagring:

  - ``GET /api/site/[siteId]/composition`` (route) +
    ``lib/site-composition.ts`` (härledningen, lokal + hostad gren),
  - ``components/builder/project-composition-panel.tsx`` (svensk UI),
    monterad i ConsoleDrawer.

Låsen här skyddar kontraktets hörnstenar: siteId-validering, ärlig hostad
degradering (hostedRuntimeNotice-mönstret), defensivt nullbara fält och
att panelen inte importerar från inspector-katalogen (annan lane äger den).
"""

from __future__ import annotations

import pytest

from tests.support.viewser import VIEWSER_DIR

ROUTE_PATH = (
    VIEWSER_DIR / "app" / "api" / "site" / "[siteId]" / "composition" / "route.ts"
)
LIB_PATH = VIEWSER_DIR / "lib" / "site-composition.ts"
PANEL_PATH = (
    VIEWSER_DIR / "components" / "builder" / "project-composition-panel.tsx"
)
DRAWER_PATH = VIEWSER_DIR / "components" / "console-drawer.tsx"


@pytest.mark.tooling
def test_composition_route_exists_and_validates_site_id() -> None:
    """Routen måste finnas, vara localhost-gated och validera siteId mot
    samma mönster som övriga siteId-routes (gemener/siffror/bindestreck)
    innan någon läsning sker."""
    assert ROUTE_PATH.exists(), "composition-routen saknas"
    text = ROUTE_PATH.read_text(encoding="utf-8")
    assert "assertLocalhost" in text, "routen måste vara localhost-gated"
    assert "SITE_ID_PATTERN" in text, "routen måste validera siteId"
    assert "status: 400" in text, "ogiltigt siteId måste ge 400"
    assert "status: 404" in text, "okänd sajt måste ge 404, inte tom gissning"

    lib = LIB_PATH.read_text(encoding="utf-8")
    assert "^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$" in lib, (
        "site-composition måste använda samma SITE_ID_PATTERN som övriga routes"
    )


@pytest.mark.tooling
def test_composition_route_has_honest_hosted_branch() -> None:
    """Hostat (VERCEL=1) ska samma bild läsas ur B199-kedjan (KV-index →
    run-artifacts-tarball → run-state-pekarens project-input) och saknade
    källor ge hostedRuntimeNotice — aldrig påhittade data."""
    route = ROUTE_PATH.read_text(encoding="utf-8")
    assert "isHostedVercelRuntime()" in route, (
        "routen måste välja hostad gren via isHostedVercelRuntime()"
    )
    assert "readHostedSiteComposition" in route

    lib = LIB_PATH.read_text(encoding="utf-8")
    for marker in (
        "listHostedRunsForSite",
        "fetchHostedRunArtefactsTar",
        "hostedRunArtefactBundle",
        "hostedProjectInputForSite",
        "hostedRuntimeNotice",
        "hostedNotice",
    ):
        assert marker in lib, (
            f"site-composition.ts saknar hostad källa/degradering: {marker}"
        )


@pytest.mark.tooling
def test_composition_derives_from_existing_sources_only() -> None:
    """Härledningen ska läsa BEFINTLIGA artefakter (ingen ny lagring):
    senaste runens bundle, genererad package.json/component-manifest och
    ADR 0056-trace-eventet som källa för dossier-tillagda paket. Alla
    okända värden ska vara ärligt nullbara via skeleton-defaulten."""
    lib = LIB_PATH.read_text(encoding="utf-8")
    for marker in (
        "generated-files/package.json",
        "generated-files/component-manifest.json",
        "npm.install.dependency_drift",
        "compositionSkeleton",
        '"required" | "recommended" | "conditional" | "rejected"',
    ):
        assert marker in lib, f"site-composition.ts saknar källa/kontrakt: {marker}"
    # Skeleton-defaulten är null för varje okänd dimension — inga gissningar.
    for nullable in (
        "version: null",
        "routes: null",
        "dossiers: null",
        "components: null",
        "dependencies: null",
        "lastBuild: null",
    ):
        assert nullable in lib, (
            f"compositionSkeleton måste defaulta '{nullable}' (ärligt okänt)"
        )


@pytest.mark.tooling
def test_composition_panel_swedish_ui_and_lane_isolation() -> None:
    """Panelen ska finnas, ha svensk rubrik + 'Tillagda paket'-kategorin
    (ADR 0056) och INTE importera från components/builder/inspector/
    (annan lane äger den katalogen)."""
    assert PANEL_PATH.exists(), "project-composition-panel.tsx saknas"
    text = PANEL_PATH.read_text(encoding="utf-8")
    assert '"use client"' in text
    assert "Projektinnehåll" in text, "panelen måste ha svensk rubrik"
    assert "Tillagda paket" in text, (
        "dossier-tillagda paket (ADR 0056) ska visas som egen kategori"
    )
    assert "Operatörskuraterade" in text, (
        "paket ska markeras som operatörskuraterade (ändras inte via prompt)"
    )
    import_lines = [
        line
        for line in text.splitlines()
        if line.strip().startswith(("import ", "} from ", 'from "'))
    ]
    for line in import_lines:
        assert "builder/inspector" not in line, (
            "panelen får inte importera från inspector-katalogen "
            f"(annan lane äger den): {line.strip()}"
        )


@pytest.mark.tooling
def test_console_drawer_mounts_composition_panel() -> None:
    """ConsoleDrawer är infästningen (minst diff i delade filer): panelen
    ska monteras med run-följande siteId-fallback."""
    drawer = DRAWER_PATH.read_text(encoding="utf-8")
    assert "ProjectCompositionPanel" in drawer, (
        "ConsoleDrawer måste montera ProjectCompositionPanel"
    )
    assert "runSiteId ?? selectedSiteId" in drawer, (
        "panelen ska följa vald runs sajt och falla tillbaka på pickern"
    )
