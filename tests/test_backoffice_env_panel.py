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
    resolve_preview_adapter,
    scan_env_keys,
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
