"""Cross-validation: docs/openclaw-workspace/action-registry.json <-> code.

The audit (2026-06-11) found a drift class with no guard: the registry's
section_add gained visibleTypes ["faq", "team"] (flipped 2026-06-09) while
ROLE_CONTRACTS["section_builder"] only carried the coarse mountOnly boolean.
Nothing went red, because no test compared the two surfaces -
tests/test_openclaw_roles.py locks the code side (skill <-> contract) and
scripts/verify_openclaw.py checks wiring, but neither reads the registry.

This module is that missing guard. For every action whose routerEditKind is
owned by a conductor role, the registry and the frozen RoleContract must agree
on skill, status, mountOnly and visibleTypes. An action may only claim status
"supported" when a role in the code actually owns its edit kind (so nobody can
flip layout_change to supported without code). TOOLS.md must list every action
id so the human-facing surface cannot silently fall behind the registry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.openclaw import (  # noqa: E402
    ROLE_CONTRACTS,
    role_for_edit_kind,
)

pytestmark = pytest.mark.governance

REGISTRY_PATH = REPO_ROOT / "docs" / "openclaw-workspace" / "action-registry.json"
TOOLS_PATH = REPO_ROOT / "docs" / "openclaw-workspace" / "TOOLS.md"

_VALID_STATUSES = {"supported", "partial", "planned"}


def _load_actions() -> list[dict]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    actions = data.get("actions", [])
    assert actions, "action-registry.json must declare at least one action"
    return actions


def _owned_actions() -> list[tuple[dict, object]]:
    """(action, owning RoleContract) for every role-owned registry action."""
    pairs = []
    for action in _load_actions():
        role = role_for_edit_kind(action.get("routerEditKind", ""))
        if role is not None:
            pairs.append((action, ROLE_CONTRACTS[role]))
    return pairs


def test_every_action_has_id_skill_kind_and_valid_status():
    for action in _load_actions():
        assert action.get("id"), action
        assert action.get("skill"), action.get("id")
        assert action.get("routerEditKind"), action.get("id")
        assert action.get("status") in _VALID_STATUSES, action.get("id")


def test_registry_covers_every_editing_role_directive_exactly_once():
    """Each directive a role produces maps to exactly one registry action."""
    edit_kinds = [a.get("routerEditKind") for a in _load_actions()]
    for role, contract in ROLE_CONTRACTS.items():
        for directive in contract.producesDirectives:
            assert edit_kinds.count(directive) == 1, (role, directive)


def test_owned_action_skill_matches_contract():
    pairs = _owned_actions()
    assert pairs, "expected at least one role-owned action"
    for action, contract in pairs:
        assert action.get("skill") == contract.skill, action["id"]


def test_owned_action_status_matches_contract():
    for action, contract in _owned_actions():
        assert action.get("status") == contract.status, action["id"]


def test_owned_action_mount_only_matches_contract():
    """mountOnly means mount-only by default; absent in JSON reads as False."""
    for action, contract in _owned_actions():
        assert bool(action.get("mountOnly", False)) == contract.mountOnly, (
            action["id"]
        )


def test_owned_action_visible_types_match_contract():
    """The exact drift the audit found: registry visibleTypes vs contract."""
    for action, contract in _owned_actions():
        registry_visible = tuple(action.get("visibleTypes", []))
        assert registry_visible == contract.visibleTypes, action["id"]


def test_visible_types_require_mount_only_semantics():
    """visibleTypes only makes sense as exceptions to a mount-only default."""
    for action in _load_actions():
        if action.get("visibleTypes"):
            assert action.get("mountOnly") is True, action["id"]


def test_supported_status_requires_an_owning_role():
    """No action may claim supported unless a code role owns its edit kind.

    This is the gate that keeps the registry honest: flipping layout_change
    (or any future action) to "supported" without shipping the owning role
    in roles.py goes red here. site_review is deliberately role-less and
    therefore stays partial (the dispatcher answers it, no directive).
    """
    for action in _load_actions():
        if action.get("status") == "supported":
            assert role_for_edit_kind(action.get("routerEditKind", "")) is not None, (
                f"{action['id']} claims supported but no role owns "
                f"{action.get('routerEditKind')!r}"
            )


def test_tools_md_lists_every_action_id():
    text = TOOLS_PATH.read_text(encoding="utf-8")
    for action in _load_actions():
        assert action["id"] in text, (
            f"TOOLS.md does not mention action {action['id']!r}"
        )


def test_component_add_is_supported_with_generative_recipe():
    """ADR 0061: the component_add action is supported, mount-only by default,
    with the whitelisted deterministic recipes as visible exceptions.
    Locks the registry side of the flip alongside the contract lock in
    tests/test_openclaw_roles.py (the dynamic consistency tests above keep the
    two surfaces in agreement)."""
    actions = {action["id"]: action for action in _load_actions()}
    component_add = actions["component_add"]
    assert component_add["status"] == "supported"
    assert component_add["mountOnly"] is True
    assert component_add["visibleTypes"] == [
        "image-placeholder-grid",
        "cta-contact-block",
    ]
    # supported requires an owning code role (the gate above), and it is owned.
    assert role_for_edit_kind(component_add["routerEditKind"]) == "component_builder"
