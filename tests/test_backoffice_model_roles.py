"""Unit tests for the shared Model Roles edit helpers (backoffice/model_roles.py).

The save path (validate -> atomic write -> governance_validate -> rollback)
used to live inline in the LLM Engine view. It is now shared between that view
and the Dirigentpult cockpit, so these tests pin the behaviour once for both:
validation rules, happy-path persistence and the rollback guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backoffice import model_roles

pytestmark = pytest.mark.tooling


def _models_fixture() -> dict:
    return {
        "roles": [
            {"id": "briefModel", "purpose": "x", "model": "gpt-5.4", "provider": "openai"},
            {"id": "embeddingModel", "purpose": "y", "model": "text-embedding-3-small", "provider": "openai"},
        ],
        "sharedModelGroups": [
            {"groupId": "smallReasoning", "purpose": "p", "roles": ["briefModel"]},
            {"groupId": "embedding", "purpose": "p", "roles": ["embeddingModel"]},
        ],
        # Subset of the real policy's anti-pattern list. Deliberately excludes
        # entries that are also naming-dictionary globallyForbidden terms -
        # tests/test_no_legacy_terms.py scans this file as product source.
        "forbiddenLegacyTierNames": ["fast", "pro"],
    }


@pytest.mark.tooling
def test_role_group_map_maps_each_role_to_its_group() -> None:
    mapping = model_roles.role_group_map(_models_fixture())
    assert mapping == {"briefModel": "smallReasoning", "embeddingModel": "embedding"}


@pytest.mark.tooling
def test_validate_role_edit_accepts_a_clean_edit() -> None:
    assert model_roles.validate_role_edit(_models_fixture(), "gpt-5.5", "openai") == []


@pytest.mark.tooling
def test_validate_role_edit_rejects_empty_and_forbidden_values() -> None:
    models = _models_fixture()

    errors = model_roles.validate_role_edit(models, "", "")
    assert any("Modellnamn" in e for e in errors)
    assert any("Provider" in e for e in errors)

    # forbiddenLegacyTierNames must block both fields, case-insensitively.
    assert model_roles.validate_role_edit(models, "Pro", "openai")
    assert model_roles.validate_role_edit(models, "gpt-5.5", "FAST")


@pytest.mark.tooling
def test_save_role_edit_persists_and_reports_success(tmp_path: Path) -> None:
    models = _models_fixture()
    policy_path = tmp_path / "llm-models.v1.json"
    policy_path.write_text(json.dumps(models), encoding="utf-8")

    ok, message = model_roles.save_role_edit(
        models,
        "briefModel",
        "gpt-5.5",
        "openai",
        policy_path=policy_path,
        run_validate=lambda: SimpleNamespace(ok=True, output=""),
    )

    assert ok, message
    assert "briefModel" in message and "gpt-5.5" in message
    on_disk = json.loads(policy_path.read_text(encoding="utf-8"))
    role = next(r for r in on_disk["roles"] if r["id"] == "briefModel")
    assert role["model"] == "gpt-5.5"
    # The caller's in-memory dict must stay untouched (deep copy semantics).
    assert models["roles"][0]["model"] == "gpt-5.4"


@pytest.mark.tooling
def test_save_role_edit_rolls_back_when_governance_validate_fails(tmp_path: Path) -> None:
    models = _models_fixture()
    policy_path = tmp_path / "llm-models.v1.json"
    original_text = json.dumps(models)
    policy_path.write_text(original_text, encoding="utf-8")

    ok, message = model_roles.save_role_edit(
        models,
        "briefModel",
        "gpt-5.5",
        "openai",
        policy_path=policy_path,
        run_validate=lambda: SimpleNamespace(ok=False, output="boom"),
    )

    assert not ok
    assert "rollback" in message
    assert "boom" in message
    assert policy_path.read_text(encoding="utf-8") == original_text


@pytest.mark.tooling
def test_save_role_edit_refuses_unknown_role_and_invalid_values(tmp_path: Path) -> None:
    models = _models_fixture()
    policy_path = tmp_path / "llm-models.v1.json"
    original_text = json.dumps(models)
    policy_path.write_text(original_text, encoding="utf-8")

    ok, message = model_roles.save_role_edit(
        models, "nopeModel", "gpt-5.5", "openai", policy_path=policy_path,
        run_validate=lambda: SimpleNamespace(ok=True, output=""),
    )
    assert not ok and "nopeModel" in message

    ok, message = model_roles.save_role_edit(
        models, "briefModel", "pro", "openai", policy_path=policy_path,
        run_validate=lambda: SimpleNamespace(ok=True, output=""),
    )
    assert not ok and "forbiddenLegacyTierNames" in message

    # Nothing was written in either refusal.
    assert policy_path.read_text(encoding="utf-8") == original_text
