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


# Hård whitelist för env-nycklar vars VÄRDEN får visas i backoffice (modell-
# namn och token-budgetar - aldrig nycklar/secrets). Allt utanför listan
# behandlas som hemligt och får aldrig läsas ut via read_non_secret_env.
NON_SECRET_ENV_KEYS = (
    "OPENAI_MODEL",
    "OPENAI_VISION_MODEL",
    "SAJTBYGGAREN_DISCOVERY_MODEL",
    "VIEWSER_MAX_CHAT_TOKENS",
    "OPENCLAW_ROUTER_LLM_FALLBACK",
)

# KÖR-6b-switchen: routerns LLM-fallback i OpenClaw-bryggan
# (scripts/run_openclaw_followup.py). Default PÅ; off-tokens speglar
# bryggans _ENV_OFF_VALUES. Bryggan läser process-env först och faller
# sedan tillbaka på repo-rotens .env - exakt samma ordning som
# read_non_secret_env - så Dirigentpultens toggle (som skriver .env-raden)
# tar effekt på nästa följdprompt-spawn.
ROUTER_FALLBACK_ENV = "OPENCLAW_ROUTER_LLM_FALLBACK"
_ROUTER_FALLBACK_OFF_VALUES = frozenset({"0", "false", "no", "off"})

_ENV_LINE_RE = None  # lazy-compiled in _read_repo_dotenv_value


def _read_repo_dotenv_value(name: str) -> str | None:
    """Minimal parse av repo-rotens .env för EN whitelistad nyckel.

    Speglar resolutionsordningen i apps/viewser (process.env vinner, annars
    repo-rotens .env). Ingen dotenv-dependency: enkel KEY=VALUE-rad, '#'
    kommentarer ignoreras, omgivande citattecken strippas.
    """
    global _ENV_LINE_RE
    import re

    from .paths import REPO_ROOT

    if _ENV_LINE_RE is None:
        _ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Z0-9_]+)\s*=\s*(.*)\s*$")

    dotenv = REPO_ROOT / ".env"
    try:
        text = dotenv.read_text(encoding="utf-8")
    except OSError:
        return None
    value: str | None = None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if match and match.group(1) == name:
            raw = match.group(2).strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
                raw = raw[1:-1]
            value = raw or None  # last assignment wins, like dotenv
    return value


def read_non_secret_env(name: str, environ: dict[str, str] | None = None) -> str | None:
    """Läs VÄRDET för en whitelistad icke-hemlig env-nyckel.

    Resolutionsordning som apps/viewser/lib/openai.ts:openaiEnv: process-env
    först, sedan repo-rotens .env. För nycklar utanför NON_SECRET_ENV_KEYS
    kastas ValueError - ett anrop med fel nyckel är en bugg, inte ett
    tillåtet sätt att läcka ett värde.
    """
    if name not in NON_SECRET_ENV_KEYS:
        raise ValueError(
            f"'{name}' står inte i NON_SECRET_ENV_KEYS - värden utanför "
            "whitelisten får aldrig läsas ut."
        )
    env = os.environ if environ is None else environ
    from_process = (env.get(name) or "").strip()
    if from_process:
        return from_process
    return _read_repo_dotenv_value(name)


def router_fallback_state(
    environ: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Effektivt läge för routerns LLM-fallback: (enabled, källa).

    Källa är "process-env", ".env" eller "default (på)" - samma resolutions-
    ordning som bryggan (scripts/run_openclaw_followup.py:_router_fallback_
    enabled): process-env vinner, sedan repo-rotens .env, annars default på.
    """
    env = os.environ if environ is None else environ
    value = env.get(ROUTER_FALLBACK_ENV)
    if value is not None:
        source = "process-env"
    else:
        value = _read_repo_dotenv_value(ROUTER_FALLBACK_ENV)
        source = ".env" if value is not None else "default (på)"
    enabled = (value or "").strip().lower() not in _ROUTER_FALLBACK_OFF_VALUES
    return enabled, source


def write_router_fallback(enabled: bool, dotenv_path=None) -> None:  # noqa: FBT001
    """Skriv ``OPENCLAW_ROUTER_LLM_FALLBACK=<1|0>`` till repo-rotens .env.

    Path-låst till repo-rotens .env (eller ett explicit test-path). Bevarar
    filens övriga innehåll byte-för-byte: den befintliga raden för nyckeln
    ersätts (kommentarsrader rörs aldrig), annars appendas raden sist med en
    kort förklarande kommentar. Atomisk skrivning via backoffice.io så en
    krasch aldrig korrumperar operatörens .env. Värden för andra nycklar
    läses eller loggas aldrig.
    """
    import re

    from .io import atomic_write_text
    from .paths import REPO_ROOT

    path = dotenv_path if dotenv_path is not None else REPO_ROOT / ".env"
    new_line = f"{ROUTER_FALLBACK_ENV}={'1' if enabled else '0'}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    pattern = re.compile(
        rf"^\s*(?:export\s+)?{ROUTER_FALLBACK_ENV}\s*=.*$", re.MULTILINE
    )
    if pattern.search(text):
        # Ersätt ALLA förekomster (dotenv: sista raden vinner vid parse, så en
        # kvarlämnad dubblett skulle kunna trumfa den nya raden).
        updated = pattern.sub(new_line, text)
    else:
        comment = (
            "# KÖR-6b: routerns LLM-fallback i OpenClaw-bryggan "
            "(1 = på/default, 0 = av; styrs från Dirigentpulten)."
        )
        suffix = "" if (not text or text.endswith("\n")) else "\n"
        updated = f"{text}{suffix}\n{comment}\n{new_line}\n"
    atomic_write_text(path, updated)


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
