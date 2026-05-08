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
    resolve_brief_model,
)
from packages.generation.brief.models import DEFAULT_POLICY_PATH


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
