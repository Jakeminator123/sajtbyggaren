"""Tests for the read-only env & preview-adapter panel.

The panel must report set/missing WITHOUT ever surfacing a secret value, and
must mirror the descriptor mode->kind mapping (ADR 0033).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backoffice.env_panel import (
    DEFAULT_PREVIEW_MODE,
    ROUTER_FALLBACK_ENV,
    resolve_preview_adapter,
    router_fallback_state,
    scan_env_keys,
    write_router_fallback,
)


@pytest.mark.tooling
def test_scan_env_keys_reports_set_without_value():
    env = {
        "OPENAI_API_KEY": "sk-supersecret-value",  # pragma: allowlist secret
        "VIEWSER_PREVIEW_MODE": DEFAULT_PREVIEW_MODE,
    }
    states = scan_env_keys(env)
    by_name = {s.name: s for s in states}
    assert by_name["OPENAI_API_KEY"].is_set is True
    assert by_name["VIEWSER_PREVIEW_MODE"].is_set is True
    assert by_name["SAJTBYGGAREN_GENERATED_DIR"].is_set is False
    # The secret value must never appear in the panel data.
    blob = json.dumps([s.__dict__ for s in states])
    assert "supersecret" not in blob
    assert "sk-" not in blob


@pytest.mark.tooling
def test_scan_env_keys_prefix_match():
    env = {"SAJTBYGGAREN_MAX_GOLDEN_PATH_EVALS": "5"}
    by_name = {s.name: s for s in scan_env_keys(env)}
    assert by_name["SAJTBYGGAREN_MAX_*"].is_set is True


@pytest.mark.tooling
def test_scan_env_keys_blank_value_is_not_set():
    env = {"OPENAI_API_KEY": "   "}
    by_name = {s.name: s for s in scan_env_keys(env)}
    assert by_name["OPENAI_API_KEY"].is_set is False


@pytest.mark.tooling
@pytest.mark.parametrize(
    "raw,expected_kind",
    [
        (DEFAULT_PREVIEW_MODE, "local"),
        ("local", "local"),
        ("auto", "local"),
        ("vercel-sandbox", "vercel-sandbox"),  # pragma: allowlist secret
        ("stackblitz", "stackblitz"),  # pragma: allowlist secret
        ("fly", "fly"),  # pragma: allowlist secret
        ("", "local"),
        (None, "local"),
    ],
)
def test_resolve_preview_adapter_kind_mapping(raw, expected_kind):
    adapter = resolve_preview_adapter(raw, policy=None)
    assert adapter["canonicalKind"] == expected_kind


@pytest.mark.tooling
def test_resolve_preview_adapter_unset_defaults_to_documented_mode():
    adapter = resolve_preview_adapter(None, policy=None)
    assert adapter["rawMode"] == DEFAULT_PREVIEW_MODE
    assert adapter["isDefaultUnset"] is True


# ---------------------------------------------------------------------------
# KÖR-6b-switchen: router_fallback_state + write_router_fallback (Dirigentpult
# flik B manövrerar bryggans LLM-fallback via repo-rotens .env).
# ---------------------------------------------------------------------------


@pytest.mark.tooling
@pytest.mark.parametrize(
    ("value", "expected_enabled"),
    [("1", True), ("true", True), ("0", False), ("off", False), ("FALSE", False)],
)
def test_router_fallback_state_reads_process_env_first(
    value: str, expected_enabled: bool
):
    enabled, source = router_fallback_state({ROUTER_FALLBACK_ENV: value})
    assert enabled is expected_enabled
    assert source == "process-env"


@pytest.mark.tooling
def test_write_router_fallback_appends_line_and_preserves_content(tmp_path: Path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENAI_MODEL=gpt-5.4\n", encoding="utf-8")
    write_router_fallback(False, dotenv_path=dotenv)
    text = dotenv.read_text(encoding="utf-8")
    # Befintligt innehåll bevarat, nya raden tillagd.
    assert "OPENAI_MODEL=gpt-5.4" in text
    assert f"{ROUTER_FALLBACK_ENV}=0" in text


@pytest.mark.tooling
def test_write_router_fallback_replaces_existing_line_and_duplicates(
    tmp_path: Path,
):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        f"{ROUTER_FALLBACK_ENV}=0\nOPENAI_MODEL=gpt-5.4\n{ROUTER_FALLBACK_ENV}=0\n",
        encoding="utf-8",
    )
    write_router_fallback(True, dotenv_path=dotenv)
    text = dotenv.read_text(encoding="utf-8")
    # Alla förekomster ersatta (dotenv: sista raden vinner — ingen dubblett
    # får ligga kvar och trumfa), övriga nycklar orörda.
    assert text.count(f"{ROUTER_FALLBACK_ENV}=1") == 2
    assert f"{ROUTER_FALLBACK_ENV}=0" not in text
    assert "OPENAI_MODEL=gpt-5.4" in text


@pytest.mark.tooling
def test_write_router_fallback_creates_missing_file(tmp_path: Path):
    dotenv = tmp_path / ".env"
    write_router_fallback(True, dotenv_path=dotenv)
    assert f"{ROUTER_FALLBACK_ENV}=1" in dotenv.read_text(encoding="utf-8")


@pytest.mark.tooling
def test_resolve_preview_adapter_uses_policy_statuses(repo_root: Path):
    policy = json.loads(
        (repo_root / "governance" / "policies" / "preview-runtime-policy.v1.json").read_text(
            encoding="utf-8"
        )
    )
    adapter = resolve_preview_adapter("vercel-sandbox", policy)  # pragma: allowlist secret
    assert adapter["activeRuntimeStatus"] == "primary"
    assert adapter["policyDefault"] == policy["default"]
    assert adapter["runtimeStatuses"].get("stackblitz") == "paused"  # pragma: allowlist secret
