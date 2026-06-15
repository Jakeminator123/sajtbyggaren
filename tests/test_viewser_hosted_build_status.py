"""Source-level locks för review-sweep 2026-06-11 (extern granskning #284).

Tre härdningar i den hostade byggvägen, alla i TS-koden under
``apps/viewser`` (samma testmönster som ``test_viewser_hosted_blob_cleanup.py``
— källkods-lås som körs i pytest-banan CI faktiskt kör):

- B196: ``GET /api/hosted-build/[runId]`` är site-bunden — kräver
  ``?siteId=`` och svarar 404 med EXAKT samma text vid saknad nyckel och vid
  siteId-mismatch (ingen orakel-yta som bekräftar gissade runId:n).
- KV-preflight (#284 fynd 1): ``startHostedBuild`` failar hårt FÖRE
  ``Sandbox.create`` när hostat läge saknar Upstash-env — annars hänger
  status-pollningen till timeout. Lokalt (utan VERCEL=1) blockeras inget.
- Synkront kontrakt (#284 fynd 2): den hostade icke-stream-vägen i
  ``/api/prompt`` väntar in done/failed server-side i stället för att svara
  202 direkt — icke-streamande klienter (floating-chat, use-followup-build)
  tolkade accepted-svaret som ett färdigt bygge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
STATUS_ROUTE = VIEWSER / "app" / "api" / "hosted-build" / "[runId]" / "route.ts"
PROMPT_ROUTE = VIEWSER / "app" / "api" / "prompt" / "route.ts"
RUNNER = VIEWSER / "lib" / "hosted-build-runner.ts"


# ---------------------------------------------------------------------------
# B196 — site-bindning av status-routen
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hosted_build_status_route_requires_site_id() -> None:
    source = STATUS_ROUTE.read_text(encoding="utf-8")

    # Query-parametern krävs och valideras med samma siteId-regel som runnern.
    assert 'searchParams.get("siteId")' in source
    assert "SITE_ID_PATTERN" in source
    # Statusen lämnas bara ut när siteId matchar.
    assert "status.siteId !== siteId" in source


@pytest.mark.tooling
def test_hosted_build_status_404_is_not_an_oracle() -> None:
    """Saknad nyckel och siteId-mismatch MÅSTE dela exakt samma 404-svar —
    annars avslöjar svaret om ett gissat runId existerar för en annan sajt."""
    source = STATUS_ROUTE.read_text(encoding="utf-8")

    assert "STATUS_NOT_FOUND_MESSAGE" in source
    # En enda 404-gren som täcker BÅDA fallen via den delade konstanten.
    assert "!status || status.siteId !== siteId" in source
    # Den gamla separata "nyckeln saknas"-texten får inte leva kvar som en
    # andra, särskiljbar 404-variant.
    assert source.count("STATUS_NOT_FOUND_MESSAGE") >= 2


@pytest.mark.tooling
def test_prompt_route_points_clients_at_site_bound_status_url() -> None:
    """Budget-slut-hänvisningen i /api/prompt måste peka på den siteId-bundna
    status-URL:en (B196), inte den gamla obundna."""
    source = PROMPT_ROUTE.read_text(encoding="utf-8")

    assert "?siteId=${siteId}" in source


# ---------------------------------------------------------------------------
# KV-preflight i startHostedBuild (#284 fynd 1)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hosted_build_runner_requires_kv_store_before_sandbox_create() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    # Preflighten är gate:ad på hostat läge (process.env.VERCEL === "1" via
    # den delade helpern) så lokalt memory-läge aldrig blockeras.
    assert "isHostedVercelRuntime()" in source
    assert "upstashRestUrl() && upstashRestToken()" in source
    assert "Hostat bygge kräver kv-store" in source
    # Preflighten körs FÖRE Sandbox.create.
    preflight_idx = source.index("Hostat bygge kräver kv-store")
    create_idx = source.index("Sandbox.create({")
    assert preflight_idx < create_idx


# ---------------------------------------------------------------------------
# Synkront kontrakt för icke-streamande klienter (#284 fynd 2)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_hosted_non_stream_path_waits_for_settled_status() -> None:
    source = PROMPT_ROUTE.read_text(encoding="utf-8")

    # Det omedelbara 202 { accepted, ... }-svaret är borta från icke-stream-
    # vägen: inga icke-stream-klienter förstår accepted-kontraktet.
    assert "{ status: 202 }" not in source
    # Båda svarslägena delar samma KV-pollning till done/failed.
    assert "async function pollHostedRunUntilSettled(" in source
    assert source.count("pollHostedRunUntilSettled(") >= 3
    # Budget-slut är ett ärligt fel (504) med status-route-hänvisning, aldrig
    # ett ok-svar som kan misstas för ett färdigt bygge.
    assert "hostedBudgetExhaustedMessage" in source
    assert "{ status: 504 }" in source
