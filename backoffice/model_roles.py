"""Shared edit helpers for Model Roles in ``llm-models.v1.json``.

Single source of truth for the save path that both the LLM Engine view
(``backoffice/views/llm_engine.py:view_model_roles``) and the Dirigentpult
cockpit (``backoffice/views/control_room.py``) use: validate the edit,
write atomically, run ``governance_validate`` and roll back on failure.
Extracted so the two views can never drift apart (same rule as the shared
``produce_site_plan`` helper closed B19 for the engine drivers).

Pure logic - no Streamlit imports - so it is fully unit-testable. The view
layer renders the returned ``(ok, message)`` as st.success/st.error.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .io import atomic_write_json
from .paths import POLICIES_DIR
from .views._editor import commit_edit

LLM_MODELS_POLICY_NAME = "llm-models.v1.json"


def llm_models_policy_path() -> Path:
    """Canonical on-disk path for the Model Roles policy."""
    return POLICIES_DIR / LLM_MODELS_POLICY_NAME


def role_group_map(models: dict[str, Any]) -> dict[str, str]:
    """Map role id -> sharedModelGroup groupId (or absent when ungrouped)."""
    mapping: dict[str, str] = {}
    for group in models.get("sharedModelGroups", []) or []:
        for role_id in group.get("roles", []) or []:
            mapping[role_id] = group.get("groupId", "?")
    return mapping


def validate_role_edit(
    models: dict[str, Any], new_model: str, new_provider: str
) -> list[str]:
    """Return Swedish validation errors for a proposed model/provider edit.

    Same rules the Model Roles view has always enforced: non-empty fields and
    no value from ``forbiddenLegacyTierNames`` (the policy's own anti-pattern
    list). An empty list means the edit may be saved.
    """
    forbidden_tier = {
        str(name).lower()
        for name in models.get("forbiddenLegacyTierNames", []) or []
    }
    errors: list[str] = []
    if not new_model:
        errors.append("Modellnamn får inte vara tomt.")
    if not new_provider:
        errors.append("Provider får inte vara tom.")
    if new_model.lower() in forbidden_tier or new_provider.lower() in forbidden_tier:
        errors.append(
            f"Värde står i forbiddenLegacyTierNames: {sorted(forbidden_tier)}"
        )
    return errors


def save_role_edit(
    models: dict[str, Any],
    role_id: str,
    new_model: str,
    new_provider: str,
    *,
    policy_path: Path | None = None,
    run_validate: Callable[[], Any] | None = None,
) -> tuple[bool, str]:
    """Persist a model/provider edit for one role, with validate + rollback.

    Flow (identical to the historical view_model_roles behaviour, now routed
    through the shared safe-save helper ``backoffice.views._editor.commit_edit``
    so this surface can never drift from the others):

    1. re-run :func:`validate_role_edit` defensively,
    2. mutate a deep copy of ``models`` (caller's dict stays untouched on fail),
    3. atomic write to the policy file,
    4. run ``governance_validate`` (injectable for tests via ``run_validate``,
       which must return an object with ``ok`` + ``output`` attributes),
    5. roll back to the pre-edit file contents when validation fails.

    Returns ``(ok, message)``; the message is operator-facing Swedish. The
    caller is responsible for clearing Streamlit loader caches afterwards.
    """
    errors = validate_role_edit(models, new_model, new_provider)
    if errors:
        return False, " ".join(errors)

    updated = copy.deepcopy(models)
    role = next((r for r in updated.get("roles", []) if r.get("id") == role_id), None)
    if role is None:
        return False, f"Rollen '{role_id}' finns inte i {LLM_MODELS_POLICY_NAME}."
    role["model"] = new_model
    role["provider"] = new_provider

    path = policy_path or llm_models_policy_path()
    if run_validate is None:
        from . import health

        run_validate = health.run_governance_validate

    result = commit_edit(
        target=path,
        write=lambda: atomic_write_json(path, updated),
        verify=run_validate,
        success_message=(
            f"Sparade {role_id} -> {new_model} ({new_provider}). governance_validate OK."
        ),
        write_error_message=lambda exc: (
            f"Kunde inte skriva {path.name}: {exc}. Inget har ändrats."
        ),
        rollback_message=lambda output: (
            "governance_validate failade efter spara - rollback genomfört. "
            f"Output:\n{output}"
        ),
    )
    return result.ok, result.message
