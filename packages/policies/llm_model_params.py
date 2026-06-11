"""Delad defensiv läsare för per-roll modellparametrar (ADR 0052).

Enda sättet att läsa ``reasoningEffort`` + ``maxOutputTokens`` ur
llm-models.v1.json (v11) - samma princip som "ingen LLM utan registrerad
Model Role": ingen kod läser params utanför policyn och inga env-overrides
finns. Modulen delas av brief/planning/router/codegen/repair/quality_gate
(packages/policies/ är vitlistad i repo-boundaries för alla
packages/generation/*) så den defensiva logiken inte dupliceras på åtta
ställen.

Defensiv betyder här: saknad fil/roll, trasig JSON, okänt enum-värde eller
ogiltigt heltal ger ``None``-fält plus en varning till stderr - ALDRIG ett
kastat fel. Ett param-fel får inte degradera ett bygge till mock; frånvaro
av fält = exakt tidigare beteende (modellens defaults). Legacy-värdet
``minimal`` (äldre effort-skala) accepteras och mappas till ``low`` med
varning i stället för att felas bort.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = REPO_ROOT / "governance" / "policies" / "llm-models.v1.json"

# gpt-5.5-generationens effort-nivåer (ADR 0052); måste matcha enum:en i
# governance/schemas/llm-models.schema.json.
VALID_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh"})
LEGACY_EFFORT_ALIASES = {"minimal": "low"}


@dataclass(frozen=True)
class RoleModelParams:
    """Per-roll modellparametrar ur llm-models.v1.json.

    ``None`` i ett fält betyder "inte satt / kunde inte läsas" och ska ge
    exakt dagens API-anrop (inga extra kwargs).
    """

    role_id: str
    model: str | None = None
    reasoning_effort: str | None = None
    max_output_tokens: int | None = None


def _warn(message: str) -> None:
    sys.stderr.write(f"[llm-model-params] {message}\n")
    sys.stderr.flush()


def _validated_effort(role_id: str, raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        _warn(
            f"{role_id}: reasoningEffort {raw!r} är inte en sträng - ignoreras."
        )
        return None
    value = raw.strip()
    if value in LEGACY_EFFORT_ALIASES:
        mapped = LEGACY_EFFORT_ALIASES[value]
        _warn(
            f"{role_id}: legacy reasoningEffort {value!r} mappas till {mapped!r} "
            "(ADR 0052)."
        )
        return mapped
    if value not in VALID_REASONING_EFFORTS:
        _warn(
            f"{role_id}: okänt reasoningEffort {value!r} (giltiga: "
            f"{sorted(VALID_REASONING_EFFORTS)}) - ignoreras."
        )
        return None
    return value


def _validated_max_tokens(role_id: str, raw: object) -> int | None:
    if raw is None:
        return None
    # bool är en int-subklass i Python; True/False är aldrig ett giltigt tak.
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        _warn(
            f"{role_id}: ogiltigt maxOutputTokens {raw!r} (kräver heltal >= 1) "
            "- ignoreras."
        )
        return None
    return raw


def resolve_role_params(
    role_id: str, policy_path: Path | None = None
) -> RoleModelParams:
    """Läs per-roll-params för ``role_id`` ur llm-models.v1.json.

    Returnerar alltid ett ``RoleModelParams``-objekt; vid varje problem
    (saknad fil/roll, trasig JSON, ogiltiga fältvärden) blir fälten ``None``
    och en varning skrivs till stderr. Kastar aldrig.
    """
    empty = RoleModelParams(role_id=role_id)
    path = policy_path or DEFAULT_POLICY_PATH
    try:
        if not path.exists():
            _warn(f"{role_id}: policyfil saknas ({path}) - inga params.")
            return empty
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        _warn(f"{role_id}: kunde inte läsa {path.name}: {exc} - inga params.")
        return empty

    roles = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, list):
        _warn(f"{role_id}: {path.name} saknar roles-listan - inga params.")
        return empty

    for role in roles:
        if not isinstance(role, dict) or role.get("id") != role_id:
            continue
        raw_model = role.get("model")
        model = (
            raw_model.strip()
            if isinstance(raw_model, str) and raw_model.strip()
            else None
        )
        return RoleModelParams(
            role_id=role_id,
            model=model,
            reasoning_effort=_validated_effort(role_id, role.get("reasoningEffort")),
            max_output_tokens=_validated_max_tokens(
                role_id, role.get("maxOutputTokens")
            ),
        )

    _warn(f"{role_id}: rollen saknas i {path.name} - inga params.")
    return empty


def responses_kwargs(params: RoleModelParams) -> dict[str, object]:
    """Bygg extra kwargs för Responses-API:t (``client.responses.parse``).

    Tom dict när inget är satt = exakt dagens anrop. Observera att
    ``max_output_tokens`` i Responses-API:t räknar in reasoning-tokens
    (effort-först-principen, ADR 0052).
    """
    kwargs: dict[str, object] = {}
    if params.reasoning_effort is not None:
        kwargs["reasoning"] = {"effort": params.reasoning_effort}
    if params.max_output_tokens is not None:
        kwargs["max_output_tokens"] = params.max_output_tokens
    return kwargs


def chat_completions_kwargs(params: RoleModelParams) -> dict[str, object]:
    """Bygg extra kwargs för chat-completions-API:t.

    Tom dict när inget är satt. ``max_completion_tokens`` är ersättaren för
    det avvisade ``max_tokens`` på gpt-5.x (jfr B176 i apps/viewser).
    """
    kwargs: dict[str, object] = {}
    if params.reasoning_effort is not None:
        kwargs["reasoning_effort"] = params.reasoning_effort
    if params.max_output_tokens is not None:
        kwargs["max_completion_tokens"] = params.max_output_tokens
    return kwargs
