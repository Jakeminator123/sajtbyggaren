"""Regression tests for ADR 0023 enabled toggles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backoffice.maintenance import (
    set_collection_entry_enabled,
    set_top_level_enabled,
)


def test_toggle_helper_writes_collection_enabled(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps({"items": [{"id": "one", "enabled": True}]}),
        encoding="utf-8",
    )

    set_collection_entry_enabled(
        path,
        collection_key="items",
        item_id="one",
        enabled=False,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["items"][0]["enabled"] is False


def test_toggle_helper_writes_top_level_enabled(tmp_path: Path) -> None:
    path = tmp_path / "variant.json"
    path.write_text(json.dumps({"id": "nordic-trust"}), encoding="utf-8")

    set_top_level_enabled(path, False)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["enabled"] is False


def test_disabled_scaffold_is_not_returned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from packages.generation.planning import plan

    policy = tmp_path / "scaffold-contract.v1.json"
    policy.write_text(
        json.dumps(
            {
                "primaryScaffoldRegistry": [
                    {"id": "local-service-business", "enabled": False}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(plan, "DEFAULT_SCAFFOLD_CONTRACT_PATH", policy)

    registry = plan.load_scaffold_registry()

    assert "local-service-business" not in {entry["id"] for entry in registry}


def test_disabled_variant_is_not_selected() -> None:
    from packages.generation.planning.plan import _pick_variant

    scaffold = {
        "id": "demo",
        "variants": [
            {"id": "disabled", "enabled": False},
            {"id": "enabled", "enabled": True},
        ],
    }

    assert _pick_variant(scaffold) == "enabled"


def test_disabled_dossier_is_rejected_from_capability_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from packages.generation.planning import plan

    monkeypatch.setattr(plan, "dossier_is_enabled", lambda _dossier_id: False)
    selected, rejected = plan.filter_capabilities(
        ["interactive-game"],
        {
            "capabilities": {
                "interactive-game": {
                    "dossiers": ["interactive-game-loop"],
                    "default": "interactive-game-loop",
                }
            }
        },
    )

    assert selected == []
    assert rejected[0].id == "interactive-game"
    assert "disabled" in rejected[0].reason


def test_disabled_starter_blocks_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from packages.generation.planning import plan

    registry = tmp_path / "starter-registry.v1.json"
    registry.write_text(
        json.dumps(
            {
                "starters": [
                    {"id": "marketing-base", "enabled": False}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(plan, "DEFAULT_STARTER_REGISTRY_PATH", registry)

    with pytest.raises(RuntimeError, match="disabled"):
        plan._resolve_starter_id("local-service-business")


@pytest.mark.governance
def test_starter_registry_ids_match_known_starters(repo_root: Path) -> None:
    payload = json.loads(
        (repo_root / "governance" / "policies" / "starter-registry.v1.json").read_text(
            encoding="utf-8"
        )
    )
    ids = {entry["id"] for entry in payload["starters"]}

    assert ids == {
        "marketing-base",
        "commerce-base",
        "portfolio-base",
        "docs-base",
        "saas-base",
    }
    assert all(isinstance(entry["enabled"], bool) for entry in payload["starters"])
