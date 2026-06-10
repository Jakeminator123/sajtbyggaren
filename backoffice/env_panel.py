"""Read-only environment & preview-adapter diagnostics for the backoffice.

NEVER reads or echoes a secret VALUE — only whether a key is set. Mirrors the
Preview Runtime descriptor's mode->kind mapping (packages/preview-runtime/
src/descriptor.ts) in Python for a read-only summary; it does not re-implement
the TS runtime. See ADR 0033.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Env keys the operator cares about. Prefix entries (ending in ``*``) match any
# env var that starts with the prefix. Values are NEVER surfaced.
TRACKED_ENV_KEYS = (
    "OPENAI_API_KEY",
    "SAJTBYGGAREN_MAX_*",
    "SAJTBYGGAREN_GENERATED_DIR",
    "VIEWSER_PREVIEW_MODE",
)


@dataclass(frozen=True)
class EnvKeyState:
    """Whether a tracked env key is set — without its value."""

    name: str
    is_set: bool


def scan_env_keys(environ: dict[str, str] | None = None) -> list[EnvKeyState]:
    """Return set/missing state for each tracked key. Never returns values."""
    env = os.environ if environ is None else environ
    states: list[EnvKeyState] = []
    for key in TRACKED_ENV_KEYS:
        if key.endswith("*"):
            prefix = key[:-1]
            is_set = any(
                name.startswith(prefix) and bool((value or "").strip())
                for name, value in env.items()
            )
        else:
            value = env.get(key)
            is_set = bool(value and value.strip())
        states.append(EnvKeyState(name=key, is_set=is_set))
    return states


# Documented default preview mode when VIEWSER_PREVIEW_MODE is unset
# (apps/viewser/.env.example). A public token, not a secret.
DEFAULT_PREVIEW_MODE = "local-next"  # pragma: allowlist secret

# Canonical PreviewRuntimeKind mapping, mirroring descriptor.ts:descriptorKind.
# local, the default mode, auto, empty/unknown all collapse to canonical local.
_RAW_TO_KIND = {
    "stackblitz": "stackblitz",  # pragma: allowlist secret
    "vercel-sandbox": "vercel-sandbox",  # pragma: allowlist secret
    "fly": "fly",  # pragma: allowlist secret
}


def resolve_preview_adapter(
    raw_mode: str | None, policy: dict | None = None
) -> dict:
    """Resolve the active preview adapter from VIEWSER_PREVIEW_MODE + policy.

    Returns a read-only summary: the raw mode (defaulting to the documented
    mode when unset, per apps/viewser/.env.example), the canonical kind, and
    the per-runtime status read straight from ``preview-runtime-policy.v1.json``
    (the policy is the source for which runtime is primary/paused/etc.).
    """
    raw = (raw_mode or "").strip().lower() or DEFAULT_PREVIEW_MODE
    kind = _RAW_TO_KIND.get(raw, "local")

    runtime_statuses: dict[str, str] = {}
    policy_default: str | None = None
    if isinstance(policy, dict):
        policy_default = policy.get("default")
        for runtime in policy.get("runtimes", []) or []:
            if isinstance(runtime, dict) and "kind" in runtime:
                runtime_statuses[str(runtime["kind"])] = str(runtime.get("status", "—"))

    return {
        "rawMode": raw,
        "canonicalKind": kind,
        "isDefaultUnset": not (raw_mode or "").strip(),
        "policyDefault": policy_default,
        "activeRuntimeStatus": runtime_statuses.get(kind, "—"),
        "runtimeStatuses": runtime_statuses,
    }
