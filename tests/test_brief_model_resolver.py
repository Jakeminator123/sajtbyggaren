"""Tests for packages/generation/brief/models.py - the canonical briefModel resolver.

Both scripts/build_site.py and scripts/dev_generate.py used to keep their
own copy of this lookup. After the dedupe (Sprint 2A cleanup) they share
this resolver. These tests pin the contract: strict, fails loudly on
misconfiguration, returns whatever llm-models.v1.json declares for
briefModel today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.brief import (
    BriefModelResolutionError,
    has_openai_api_key,
    resolve_brief_model,
    resolve_copy_directive_model,
)
from packages.generation.brief.models import DEFAULT_POLICY_PATH, OPENAI_API_KEY_ENV


@pytest.mark.tooling
def test_resolves_brief_model_from_real_policy():
    """Against the actual repo policy: returns a non-empty model string."""
    model = resolve_brief_model()
    assert isinstance(model, str)
    assert model.strip() == model
    assert model, "briefModel.model must be non-empty"


@pytest.mark.tooling
def test_real_policy_declares_openai_provider():
    """The strict resolver enforces openai. Sanity-check the policy itself."""
    data = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    brief_role = next(
        (r for r in data.get("roles", []) if r.get("id") == "briefModel"),
        None,
    )
    assert brief_role is not None, "llm-models.v1.json missing briefModel role"
    assert brief_role.get("provider") == "openai"


@pytest.mark.tooling
def test_raises_when_policy_file_missing(tmp_path: Path):
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(BriefModelResolutionError, match="missing"):
        resolve_brief_model(policy_path=missing)


@pytest.mark.tooling
def test_raises_on_invalid_json(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(BriefModelResolutionError, match="not valid JSON"):
        resolve_brief_model(policy_path=bad)


@pytest.mark.tooling
def test_raises_when_role_missing(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps({"roles": [{"id": "planningModel", "provider": "openai", "model": "x"}]}),
        encoding="utf-8",
    )
    with pytest.raises(BriefModelResolutionError, match="briefModel role missing"):
        resolve_brief_model(policy_path=policy)


@pytest.mark.tooling
def test_raises_on_wrong_provider(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps(
            {"roles": [{"id": "briefModel", "provider": "anthropic", "model": "claude"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(BriefModelResolutionError, match="provider must be"):
        resolve_brief_model(policy_path=policy)


@pytest.mark.tooling
def test_raises_on_empty_model(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps({"roles": [{"id": "briefModel", "provider": "openai", "model": "   "}]}),
        encoding="utf-8",
    )
    with pytest.raises(BriefModelResolutionError, match="non-empty model"):
        resolve_brief_model(policy_path=policy)


@pytest.mark.tooling
def test_returns_declared_model_for_synthetic_policy(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps(
            {"roles": [{"id": "briefModel", "provider": "openai", "model": "gpt-test-4"}]}
        ),
        encoding="utf-8",
    )
    assert resolve_brief_model(policy_path=policy) == "gpt-test-4"


@pytest.mark.tooling
def test_resolves_copy_directive_model_from_real_policy():
    """ADR 0034 path A: copyDirectiveModel is a registered role (llm-models v5)."""
    model = resolve_copy_directive_model()
    assert isinstance(model, str) and model.strip() == model and model


@pytest.mark.tooling
def test_copy_directive_model_resolver_is_role_specific(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps(
            {
                "roles": [
                    {"id": "briefModel", "provider": "openai", "model": "gpt-brief"},
                    {"id": "copyDirectiveModel", "provider": "openai", "model": "gpt-copy"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert resolve_copy_directive_model(policy_path=policy) == "gpt-copy"
    assert resolve_brief_model(policy_path=policy) == "gpt-brief"


@pytest.mark.tooling
def test_copy_directive_model_raises_when_role_missing(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps({"roles": [{"id": "briefModel", "provider": "openai", "model": "x"}]}),
        encoding="utf-8",
    )
    with pytest.raises(BriefModelResolutionError, match="copyDirectiveModel role missing"):
        resolve_copy_directive_model(policy_path=policy)


@pytest.mark.tooling
def test_has_openai_api_key_treats_unset_as_missing(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    assert has_openai_api_key() is False


@pytest.mark.tooling
def test_has_openai_api_key_treats_empty_as_missing(monkeypatch):
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "")
    assert has_openai_api_key() is False


@pytest.mark.tooling
@pytest.mark.parametrize("whitespace", ["   ", "\n", "\t", "  \n  ", " \r\n\t "])
def test_has_openai_api_key_treats_whitespace_as_missing(monkeypatch, whitespace: str):
    """Stray newlines/spaces in the env var must not route to the real LLM path."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, whitespace)
    assert has_openai_api_key() is False, (
        f"Whitespace-only OPENAI_API_KEY ({whitespace!r}) must be treated as missing"
    )


@pytest.mark.tooling
def test_has_openai_api_key_accepts_real_looking_value(monkeypatch):
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-1234567890")
    assert has_openai_api_key() is True


@pytest.mark.tooling
def test_has_openai_api_key_accepts_value_with_surrounding_whitespace(monkeypatch):
    """A real key with stray surrounding whitespace must still count as set."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "  sk-test-1234567890\n")
    assert has_openai_api_key() is True
