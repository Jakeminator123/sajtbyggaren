"""Source-level locks för preview-refresh-gaten (2026-06-12).

Före gaten nollade studio-sidan ALLTID ViewerPanels runId-prop på varje
lyckad follow-up — ViewerPanel-effekten (deps: runId/siteId/retryNonce)
rev då preview-state och POST:ade /api/preview/<siteId> igen ÄVEN när
kedjan ärligt rapporterat att ingen synlig ändring landade
(bridge.previewShouldRefresh=false: answer-only/no-op/mount-only). I
vercel-sandbox-läget betyder det en onödig sandbox-kallstart på flera
minuter för en ändring som inte syns.

Gaten (källkods-lås, samma mönster som övriga test_viewser_*-moduler):

SIGNALEN (use-followup-build.ts + floating-chat.tsx)
  - ``readFollowupVisibleEffect`` är EXPORTERAD och delad: FloatingChat
    läser samma granulära signal som dialog-vägen i stället för en egen
    kopia som kan driva isär.
  - FloatingChat trådar signalen som tredje arg i ``onBuildDone`` så
    studio-sidan får den för chat-byggen (dialogerna gjorde det redan).

GATEN (studio-sidan)
  - Separat ``previewRunId``-state driver ViewerPanel (inte
    ``selectedRunId``): historik/versions-valet följer alltid nya runen,
    men previewn hålls kvar när ``visibleEffect`` är ``none`` eller
    ``registered`` (FollowupVisibleEffect-semantiken: ärlig no-op resp.
    monterad-men-ej-synlig).
  - Designprincip: init-byggen, synliga ändringar och SAKNAD/okänd
    signal refreshar EXAKT som förr — bara en explicit
    ingen-synlig-ändring-signal hoppar över rebuilden, och bara när en
    preview redan är aktiv (previewRunId satt).
  - Explicita operatörsval (ConsoleDrawer-run-val,
    sessionStorage-återställning, Ny sajt) uppdaterar previewRunId så
    previewn alltid följer ett aktivt val.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.core, pytest.mark.tooling]

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
STUDIO_PAGE = VIEWSER / "app" / "(console)" / "studio" / "page.tsx"
FLOATING_CHAT = VIEWSER / "components" / "builder" / "floating-chat.tsx"
USE_FOLLOWUP_BUILD = VIEWSER / "components" / "builder" / "use-followup-build.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- 1. Signalen: delad läsare + FloatingChat trådar den ----------------------


def test_visible_effect_reader_is_exported_and_shared() -> None:
    """``readFollowupVisibleEffect`` måste vara EXPORTERAD ur
    use-followup-build.ts och importerad i floating-chat.tsx — en lokal
    kopia i FloatingChat skulle kunna driva isär från dialog-vägens
    semantik (visible/registered/none/unknown)."""
    hook_source = _read(USE_FOLLOWUP_BUILD)
    assert "export function readFollowupVisibleEffect" in hook_source, (
        "readFollowupVisibleEffect måste vara exporterad så FloatingChat "
        "delar exakt samma signal-läsning som dialogerna."
    )
    chat_source = _read(FLOATING_CHAT)
    assert "readFollowupVisibleEffect" in chat_source, (
        "FloatingChat måste importera/använda den delade "
        "readFollowupVisibleEffect i stället för en egen kopia."
    )


def test_floating_chat_threads_visible_effect_to_on_build_done() -> None:
    """FloatingChat:s lyckade bygg-gren måste skicka visible-effect-signalen
    som tredje arg till onBuildDone — annars ser studio-sidan "unknown"
    för chat-byggen och gaten kan aldrig hoppa över en onödig
    preview-rebuild för dem."""
    source = _read(FLOATING_CHAT)
    assert (
        "onBuildDone(payload.runId, outcome, readFollowupVisibleEffect(payload))"
        in source
    ), (
        "FloatingChat ska anropa onBuildDone med "
        "readFollowupVisibleEffect(payload) som tredje argument."
    )


def test_visible_effect_semantics_unchanged() -> None:
    """FollowupVisibleEffect-semantiken är gatens kontrakt: en positiv
    synlig signal (appliedVisibleEffect=true ELLER previewShouldRefresh=true)
    ger "visible"; bryggan applied utan refresh ger "registered"; explicit
    appliedVisibleEffect=false ger "none"; allt annat "unknown"."""
    source = _read(USE_FOLLOWUP_BUILD)
    assert (
        'if (appliedVisibleEffect === true || bridgeRefresh === true) return "visible";'
        in source
    )
    assert 'if (bridgeApplied === true) return "registered";' in source
    assert 'if (appliedVisibleEffect === false) return "none";' in source
    assert 'return "unknown";' in source


# --- 2. Gaten: previewRunId i studio-sidan -------------------------------------


def test_studio_page_has_separate_preview_run_id_state() -> None:
    source = _read(STUDIO_PAGE)
    assert "const [previewRunId, setPreviewRunId] = useState<string | null>(null);" in source, (
        "Studio-sidan måste hålla ett separat previewRunId-state — det är "
        "mekanismen som låter historik-valet flyttas utan att riva previewn."
    )


def test_viewer_panel_is_driven_by_preview_run_id() -> None:
    """ViewerPanel måste få previewRunId (inte selectedRunId) som runId-prop —
    annars river ViewerPanel-effekten preview-sandboxen på varje runId-byte
    oavsett gate."""
    source = _read(STUDIO_PAGE)
    assert re.search(r"<ViewerPanel\s+runId=\{previewRunId\}", source), (
        "ViewerPanel ska drivas av previewRunId. Hittas "
        "<ViewerPanel runId={selectedRunId}> har gaten kopplats ur."
    )
    assert not re.search(r"<ViewerPanel\s+runId=\{selectedRunId\}", source), (
        "selectedRunId får inte driva ViewerPanels runId-prop — det är "
        "exakt den koppling gaten bröt upp. (BuilderShell får däremot "
        "fortsatt följa selectedRunId.)"
    )


def test_gate_skips_refresh_only_on_explicit_no_visible_effect() -> None:
    """Gatens villkor: hoppa över preview-rebuild BARA när signalen explicit
    säger ingen synlig ändring ("none"/"registered") OCH en preview redan
    är aktiv. Saknad/okänd signal ("unknown"/undefined) och "visible" ska
    refresha som förr — ärligt default."""
    source = _read(STUDIO_PAGE)
    assert "const skipPreviewRefresh =" in source
    assert "previewRunId !== null" in source, (
        "Gaten får bara hoppa över refresh när en preview redan är aktiv "
        "(previewRunId satt) — annars kan första previewn aldrig starta."
    )
    assert (
        'visibleEffect === "none" || visibleEffect === "registered"' in source
    ), (
        "Gaten ska enbart trigga på de två explicita "
        "ingen-synlig-ändring-signalerna (none/registered) ur "
        "FollowupVisibleEffect — aldrig på unknown/undefined."
    )
    assert "if (!skipPreviewRefresh) {" in source and "setPreviewRunId(runId);" in source, (
        "Alla andra utfall (init, visible, unknown) måste fortsatt "
        "uppdatera previewRunId → refresh exakt som före gaten."
    )


def test_explicit_selection_paths_always_follow_preview() -> None:
    """Operatörens explicita val ska alltid flytta previewn: run-val i
    ConsoleDrawer (selectRunAndSyncSiteId), sessionStorage-återställningen
    efter omladdning, och Ny sajt (null = hero-läget)."""
    source = _read(STUDIO_PAGE)
    select_body = source.split("function selectRunAndSyncSiteId", 1)[1].split(
        "\n  }", 1
    )[0]
    assert "setPreviewRunId(runId);" in select_body, (
        "selectRunAndSyncSiteId måste sätta previewRunId — ett explicit "
        "run-val ska alltid visa den valda versionen."
    )
    restore_body = source.split("restoredSelectionRef.current = true;", 1)[1].split(
        "setRunsLoadError", 1
    )[0]
    assert "setPreviewRunId(saved.runId);" in restore_body, (
        "sessionStorage-återställningen måste sätta previewRunId så "
        "previewn kommer tillbaka efter en hård omladdning."
    )
    assert "setPreviewRunId(null);" in source, (
        "Ny sajt-vägen måste nolla previewRunId så hero-läget visas."
    )
