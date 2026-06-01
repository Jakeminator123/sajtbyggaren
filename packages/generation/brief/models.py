"""Resolve briefModel metadata from llm-models.v1.json.

Single source of truth for "which OpenAI model does briefModel map to right
now?" plus a tiny helper for "is OPENAI_API_KEY actually usable?". Both
scripts/build_site.py and scripts/dev_generate.py used to keep their own
copy of these lookups, which guaranteed they would drift apart. This
module is the only place the policy file is read for briefModel and the
only place the env-var presence check is implemented.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

BRIEF_ROLE_ID = "briefModel"
COPY_DIRECTIVE_ROLE_ID = "copyDirectiveModel"
EXPECTED_PROVIDER = "openai"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


def has_openai_api_key() -> bool:
    """True when OPENAI_API_KEY is set to a non-whitespace value.

    Whitespace-only values (e.g. ``"   "``, ``"\\n"``) are treated as
    missing. Without this guard, a stray newline pasted into a shell
    profile would route through the real-LLM code path and surface as
    a confusing OpenAI auth error instead of cleanly falling back to
    the mock Site Brief with briefSource=mock-no-key.
    """
    value = os.environ.get(OPENAI_API_KEY_ENV)
    if value is None:
        return False
    return bool(value.strip())


class BriefModelResolutionError(RuntimeError):
    """Raised when llm-models.v1.json does not declare a usable Model Role.

    The name is historical (the first role resolved this way was briefModel);
    it is reused for every registered role (briefModel, copyDirectiveModel,
    ...) so callers have a single error type to catch. The message always
    names the specific role that failed to resolve.
    """


def _resolve_role_model(role_id: str, policy_path: Path | None = None) -> str:
    """Return the model string registered for ``role_id`` in llm-models.v1.json.

    Strict: raises ``BriefModelResolutionError`` when the policy file is
    missing, malformed, missing the role, the provider is not openai, or the
    model field is empty. We prefer a hard failure over a silent default
    because the policy is the Model Role contract Sprint 2A locked in.
    """
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise BriefModelResolutionError(
            f"llm-models.v1.json missing at {path}"
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BriefModelResolutionError(
            f"llm-models.v1.json is not valid JSON: {exc}"
        ) from exc

    for role in data.get("roles", []):
        if role.get("id") != role_id:
            continue
        provider = role.get("provider")
        if provider != EXPECTED_PROVIDER:
            raise BriefModelResolutionError(
                f"{role_id} provider must be {EXPECTED_PROVIDER!r}, got {provider!r}"
            )
        model = role.get("model")
        if not isinstance(model, str) or not model.strip():
            raise BriefModelResolutionError(
                f"{role_id} role is missing a non-empty model value"
            )
        return model

    raise BriefModelResolutionError(
        f"{role_id} role missing from {path.name}"
    )


def resolve_brief_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for briefModel in llm-models.v1.json."""
    return _resolve_role_model(BRIEF_ROLE_ID, policy_path)


def resolve_copy_directive_model(policy_path: Path | None = None) -> str:
    """Return the model string registered for copyDirectiveModel (ADR 0034)."""
    return _resolve_role_model(COPY_DIRECTIVE_ROLE_ID, policy_path)
