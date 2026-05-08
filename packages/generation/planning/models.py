"""Resolve planningModel metadata from llm-models.v1.json.

Mirror of ``packages.generation.brief.models`` for the planningModel role.
Single source of truth for "which OpenAI model does planningModel map to
right now?". Both ``scripts/build_site.py`` and ``scripts/dev_generate.py``
read this through ``packages.generation.planning`` so the lookup cannot
drift between callers (the bug ADR 0013 was written to prevent and
``docs/known-issues.md`` B19 tracked).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

PLANNING_ROLE_ID = "planningModel"
EXPECTED_PROVIDER = "openai"


class PlanningModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json does not declare a usable planningModel."""


def resolve_planning_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for planningModel in llm-models.v1.json.

    Strict: raises ``PlanningModelResolutionError`` when the policy file is
    missing the role, the provider is not openai, or the model field is
    empty. Mirrors ``resolve_brief_model`` so the two roles share the same
    contract surface.
    """
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise PlanningModelResolutionError(
            f"llm-models.v1.json missing at {path}"
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PlanningModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != PLANNING_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise PlanningModelResolutionError(
                f"planningModel provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise PlanningModelResolutionError(
                "planningModel role is missing a non-empty model value"
            )
        return model

    raise PlanningModelResolutionError(
        f"planningModel role missing from {path.name}"
    )
