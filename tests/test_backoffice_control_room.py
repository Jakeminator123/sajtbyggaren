"""Locks for the Dirigentpult cockpit (backoffice/views/control_room.py).

Four families of guarantees, mirroring how test_backoffice_identity.py locks
the SOUL view:

1. Registration - the view exists in the module, the section is FIRST in both
   the code registry and the governance policy, and the policy entry is
   correct.
2. Path locks - the only writable surfaces outside the shared helpers are the
   action registry and SKILL.md files discovered under the skills dir; the
   write calls go through the locked constants, and a skill name that did not
   come from the directory scan is refused.
3. Honesty text - the cockpit must keep saying that action status mirrors
   code support (toggling enables nothing), that a skill is text rather than
   permission, and that conductor roles are read-only.
4. Source-of-truth dynamics - chat limits shown in the cockpit come from the
   live parse of apps/viewser/lib/openai.ts (1500/8000/40 today) and model
   defaults are never hardcoded (the gpt-4o -> gpt-5.5 bump must need no
   change here).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_ROOM_PY = REPO_ROOT / "backoffice" / "views" / "control_room.py"
POLICY_PATH = REPO_ROOT / "governance" / "policies" / "backoffice-views.v1.json"


# ----- 1. registration --------------------------------------------------------


@pytest.mark.tooling
def test_control_room_view_is_registered_in_module() -> None:
    from backoffice.views import control_room

    assert "Dirigentpult" in control_room.VIEWS
    assert callable(control_room.VIEWS["Dirigentpult"])


@pytest.mark.tooling
def test_dirigentpult_section_is_first_in_code_registry() -> None:
    from backoffice.view_registry import SECTION_MODULES
    from backoffice.views import control_room

    assert next(iter(SECTION_MODULES)) == "Dirigentpult"
    assert SECTION_MODULES["Dirigentpult"] is control_room


@pytest.mark.governance
def test_dirigentpult_registered_first_in_policy() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["sections"][0] == "Dirigentpult"

    entry = next((e for e in policy["views"] if e["view"] == "Dirigentpult"), None)
    assert entry is not None, "Dirigentpult must be registered in backoffice-views.v1.json"
    assert entry["section"] == "Dirigentpult"
    assert entry["ownerSource"] == "backoffice.views.control_room"
    assert entry["status"] == "active"
    assert "data/model-pricing.json" in entry["readsFrom"]
    assert "docs/openclaw-workspace" in entry["readsFrom"]


# ----- 2. path locks -----------------------------------------------------------


@pytest.mark.tooling
def test_write_targets_are_locked_to_openclaw_workspace() -> None:
    from backoffice.views import control_room

    workspace = REPO_ROOT / "docs" / "openclaw-workspace"
    assert control_room.ACTION_REGISTRY_PATH == workspace / "action-registry.json"
    assert control_room.SKILLS_DIR == workspace / "skills"
    assert control_room.PRICING_SNAPSHOT_PATH == REPO_ROOT / "data" / "model-pricing.json"


@pytest.mark.tooling
def test_writes_go_through_locked_constants() -> None:
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")

    assert "atomic_write_json(ACTION_REGISTRY_PATH" in text, (
        "the action-registry write must use the path-locked constant"
    )
    # The skill write target must come from skill_path() (scan-validated),
    # never from free-form operator input.
    assert "atomic_write_text(target" in text and "skill_path(" in text
    # The pricing snapshot is read-only in the cockpit: no write call may
    # target it (only scripts/fetch_model_prices.py writes it).
    assert "atomic_write_json(PRICING_SNAPSHOT_PATH" not in text
    assert "atomic_write_text(PRICING_SNAPSHOT_PATH" not in text


@pytest.mark.tooling
def test_skill_path_refuses_names_outside_the_scan() -> None:
    from backoffice.views import control_room

    skills = control_room.list_skills()
    assert skills, "expected at least one skill under docs/openclaw-workspace/skills/"
    # A scanned name resolves inside the locked dir.
    resolved = control_room.skill_path(skills[0])
    assert resolved == control_room.SKILLS_DIR / skills[0] / "SKILL.md"

    # Traversal / unknown names are refused outright.
    for bogus in ("../SOUL", "nope", "restyle/../../x"):
        with pytest.raises(ValueError):
            control_room.skill_path(bogus)


@pytest.mark.tooling
def test_role_contracts_are_not_written_anywhere() -> None:
    """Conductor role contracts are frozen dataclasses - the cockpit may only
    read them. No assignment/mutation of ROLE_CONTRACTS may appear."""
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")
    assert "ROLE_CONTRACTS[" not in text.replace(
        "ROLE_CONTRACTS[role]", ""
    ), "no subscript-assignment surface on ROLE_CONTRACTS"
    assert "ROLE_CONTRACTS =" not in text


# ----- 3. honesty text ----------------------------------------------------------


@pytest.mark.tooling
def test_action_status_honesty_banner_present() -> None:
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")
    assert "togglar inte" in text, (
        "the actions tab must say status mirrors code support and toggles nothing"
    )
    assert "kräver kodstöd" in text.lower() or "kräver kodstöd" in text, (
        "flipping an action to supported must be marked as requiring code support"
    )


@pytest.mark.tooling
def test_skills_are_described_as_text_not_permission() -> None:
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")
    assert "inte behörighet" in text, (
        "the skills tab must explain that a skill is text, not permission"
    )


@pytest.mark.tooling
def test_conductor_roles_tab_is_read_only() -> None:
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")
    assert "read-only" in text
    assert "FRYSTA dataclasses" in text or "frysta dataclasses" in text.lower()


@pytest.mark.tooling
def test_no_git_commit_happens_from_the_cockpit() -> None:
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")
    assert "Ingen git-commit" in text
    assert "subprocess" not in text.split("health.run_fetch_model_prices")[0].split(
        "import"
    )[0], "no raw subprocess plumbing in the cockpit - reuse health helpers"


# ----- 4. dynamics (no hardcoded model defaults) --------------------------------


@pytest.mark.tooling
def test_cockpit_does_not_hardcode_env_model_defaults() -> None:
    """The ENV-driven model defaults must come from the live source parse -
    never from a literal model name in the cockpit. This is what makes the
    parallel gpt-4o -> gpt-5.5 fallback bump a no-op here."""
    text = CONTROL_ROOM_PY.read_text(encoding="utf-8")
    for hardcoded in ('"gpt-4o"', '"gpt-5.5"', '"gpt-5.4"'):
        assert hardcoded not in text, (
            f"control_room.py must not hardcode {hardcoded} - parse the source "
            "via backoffice.runtime_models instead"
        )
    assert "runtime_models.chat_model_default" in text
    assert "runtime_models.vision_model_default" in text
    assert "runtime_models.discovery_model_default" in text


@pytest.mark.tooling
def test_action_statuses_match_registry_enum() -> None:
    from backoffice.views import control_room

    assert control_room.ACTION_STATUSES == ("supported", "partial", "planned")
    registry = json.loads(
        control_room.ACTION_REGISTRY_PATH.read_text(encoding="utf-8")
    )
    for action in registry["actions"]:
        assert action["status"] in control_room.ACTION_STATUSES


@pytest.mark.tooling
def test_chat_limits_shown_match_viewser_source() -> None:
    """The limits the cockpit displays are parsed live from openai.ts; today's
    contract values are pinned here (the parallel model-bump PR does not touch
    them)."""
    from backoffice import runtime_models

    limits = runtime_models.chat_limits()
    assert limits == {
        "maxOutputTokensDefault": 1500,
        "maxInputCharsPerMessage": 8000,
        "maxMessagesPerRequest": 40,
    }
