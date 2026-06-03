"""Resolve ``repairModel`` metadata from llm-models.v1.json (kor-5).

Boundary note (repo-boundaries.v1: ``packages/generation/repair`` may import
only ``packages/policies`` / ``packages/shared`` / ``packages/generation/
quality_gate``). The brief package already owns a near-identical resolver
(``packages/generation/brief/models.py``), but repair must NOT import brief.
So this module re-implements the tiny lookup locally - it reads the existing
``governance/policies/llm-models.v1.json`` policy and the existing
``OPENAI_API_KEY`` env var. It introduces **no new runtime contract**: same
policy file, same env var the rest of the pipeline already uses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

REPAIR_ROLE_ID = "repairModel"
EXPECTED_PROVIDER = "openai"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


def has_openai_api_key() -> bool:
    """True when OPENAI_API_KEY is set to a non-whitespace value.

    Whitespace-only values (e.g. ``"   "``, ``"\\n"``) are treated as missing -
    same semantics as ``packages/generation/brief/models.py:has_openai_api_key``
    (re-implemented here to keep repair boundary-clean). Without this guard a
    stray newline pasted into a shell profile would route through the real-LLM
    path and surface as a confusing OpenAI auth error instead of cleanly
    falling back to the no-fix-applied mock contract.
    """
    value = os.environ.get(OPENAI_API_KEY_ENV)
    if value is None:
        return False
    return bool(value.strip())


class RepairModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json does not declare a usable repairModel."""


def resolve_repair_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for ``repairModel`` in the policy.

    Strict: raises ``RepairModelResolutionError`` when the policy file is
    missing, malformed, missing the role, the provider is not openai, or the
    model field is empty. We prefer a hard failure over a silent default
    because the policy is the Model Role contract (ADR 0009 / llm-models.v1).
    """
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise RepairModelResolutionError(f"llm-models.v1.json missing at {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RepairModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != REPAIR_ROLE_ID:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise RepairModelResolutionError(
                f"{REPAIR_ROLE_ID} provider must be {EXPECTED_PROVIDER!r}, "
                f"got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise RepairModelResolutionError(
                f"{REPAIR_ROLE_ID} role is missing a non-empty model value"
            )
        return model

    raise RepairModelResolutionError(
        f"{REPAIR_ROLE_ID} role missing from {path.name}"
    )
