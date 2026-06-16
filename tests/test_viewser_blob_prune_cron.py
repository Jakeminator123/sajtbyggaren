"""Source-level locks for ADR 0063 — auto-prune of hosted blob via daily cron.

Den hostade blob-storen växer obegränsat (generated/<siteId>/ m.fl.). En daglig
Vercel Cron anropar /api/cron/prune-blob och raderar sajt-data äldre än
RETENTION_DAYS med EXAKT samma logik som CLI:t (delad lib/blob-prune.mjs).
build-context/ (Python-motorn) får ALDRIG raderas, och routen får aldrig vara
en oskyddad delete-relä (CRON_SECRET-gatead, 401 utan giltig secret — samma
öppen-relä-lärdom som #156).

Dessa lås körs i pytest-banan som CI faktiskt kör; den körbara
enhetstäckningen ligger i apps/viewser/lib/blob-prune.test.mjs (kör med
``node --test apps/viewser/lib/blob-prune.test.mjs`` på Node 18+).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWSER = REPO_ROOT / "apps" / "viewser"
LIB = VIEWSER / "lib"
PRUNE_MJS = LIB / "blob-prune.mjs"
PRUNE_TEST_MJS = LIB / "blob-prune.test.mjs"
BLOB_ADMIN = VIEWSER / "scripts" / "blob-admin.mjs"
ROUTE = VIEWSER / "app" / "api" / "cron" / "prune-blob" / "route.ts"
VERCEL_JSON = VIEWSER / "vercel.json"
ENV_EXAMPLE = VIEWSER / ".env.example"


@pytest.mark.tooling
def test_shared_prune_module_exports_reused_core() -> None:
    source = PRUNE_MJS.read_text(encoding="utf-8")
    # Den delade kärnan måste exponera radering, plan/staleness, auth och
    # env-parsing som importeras av BÅDE CLI och route.
    for symbol in (
        "export async function deleteSite(",
        "export function planPrune(",
        "export async function pruneBlob(",
        "export function isAuthorizedBearer(",
        "export function assertSafeSiteId(",
        "export function resolveRetentionDays(",
        "export function pruneEnabled(",
    ):
        assert symbol in source, f"saknar export: {symbol}"


@pytest.mark.tooling
def test_build_context_can_never_be_pruned() -> None:
    source = PRUNE_MJS.read_text(encoding="utf-8")
    # Explicit skydd: build-context-prefixet + en grind som vägrar det som id.
    assert 'BUILD_CONTEXT_PREFIX = "build-context/"' in source
    assert 'siteId === "build-context"' in source
    # deleteSite har defense-in-depth: vägrar om ett mål ligger under prefixet.
    assert "ingick i raderingsmålet" in source
    # build-context är aldrig ett sajt-prefix (klassificeras till siteId null).
    assert "build-context" not in (
        "".join(
            line
            for line in source.splitlines()
            if line.strip().startswith("export const SITE_PREFIXES")
        )
    )


@pytest.mark.tooling
def test_cli_reuses_shared_module_and_has_prune_subcommand() -> None:
    source = BLOB_ADMIN.read_text(encoding="utf-8")
    # Ingen duplicering: CLI:t importerar den delade kärnan i stället för att
    # bära sin egen del/list/scan-logik.
    assert 'from "../lib/blob-prune.mjs"' in source
    assert "pruneBlob" in source
    # Nytt subkommando med dry-run-default och --apply för riktig radering.
    assert 'command === "prune"' in source
    assert "--apply" in source
    # CLI:t får inte längre ha sin egen del/list-implementation (flyttad till lib).
    assert "import { del, list }" not in source


@pytest.mark.governance
def test_cron_route_is_auth_gated_and_supports_dryrun() -> None:
    assert ROUTE.exists(), "cron-routen saknas: app/api/cron/prune-blob/route.ts"
    source = ROUTE.read_text(encoding="utf-8")
    # Delad logik importeras (samma raderingskod som CLI).
    assert 'from "@/lib/blob-prune.mjs"' in source
    # Auth-grind: CRON_SECRET + 401 utan giltig secret.
    assert "isAuthorizedBearer(request, process.env.CRON_SECRET)" in source
    assert "status: 401" in source
    # Torrkörning + paus-flagga + retention.
    assert 'searchParams.get("dryRun")' in source
    assert "pruneEnabled(process.env.PRUNE_ENABLED)" in source
    assert "resolveRetentionDays(process.env.RETENTION_DAYS)" in source
    # Node-runtime (behövs för @vercel/blob + fs) och strukturerad logg.
    assert 'export const runtime = "nodejs"' in source
    assert '"blob-prune"' in source


@pytest.mark.governance
def test_vercel_json_registers_daily_cron() -> None:
    config = json.loads(VERCEL_JSON.read_text(encoding="utf-8"))
    crons = config.get("crons")
    assert isinstance(crons, list) and crons, "vercel.json saknar crons"
    entry = next(
        (c for c in crons if c.get("path") == "/api/cron/prune-blob"), None
    )
    assert entry is not None, "ingen cron för /api/cron/prune-blob"
    schedule = entry.get("schedule", "")
    # Daglig schedule: fält 3-5 (dom/mon/dow) ska vara wildcards -> en gång/dygn
    # (Hobby-planens gräns). 5 fält totalt.
    fields = schedule.split()
    assert len(fields) == 5, f"ogiltig cron-schedule: {schedule!r}"
    assert fields[2:] == ["*", "*", "*"], (
        f"schedule {schedule!r} är inte daglig (dom/mon/dow måste vara *)"
    )


@pytest.mark.tooling
def test_executable_test_covers_retention_and_protection() -> None:
    assert PRUNE_TEST_MJS.exists(), "saknar körbar enhetstäckning (blob-prune.test.mjs)"
    test_src = PRUNE_TEST_MJS.read_text(encoding="utf-8")
    assert "planPrune" in test_src
    assert "build-context" in test_src
    assert "isAuthorizedBearer" in test_src


@pytest.mark.governance
def test_env_example_documents_cron_env() -> None:
    env = ENV_EXAMPLE.read_text(encoding="utf-8")
    for name in ("CRON_SECRET", "RETENTION_DAYS", "PRUNE_ENABLED"):
        assert name in env, f"{name} odokumenterad i apps/viewser/.env.example"
