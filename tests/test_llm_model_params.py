"""Tests for packages/policies/llm_model_params.py (ADR 0052).

Låser tre saker:

1. Den delade defensiva läsaren: rätt värden ur riktiga policyn (v11),
   None-fält + stderr-varning (aldrig kastat fel) vid saknad fil/roll,
   trasig JSON, okänt enum-värde eller ogiltigt heltal, samt
   legacy-mappningen ``minimal -> low``.
2. Governance-vakten: embeddingModel får ALDRIG chat-params
   (reasoningEffort/maxOutputTokens) i llm-models.v1.json.
3. Source-lock: de åtta riktiga call-sites trådar
   ``**responses_kwargs(resolve_role_params("<roll>"))`` så en refactor
   inte tyst tappar per-roll-parametrarna.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.policies.llm_model_params import (
    DEFAULT_POLICY_PATH,
    RoleModelParams,
    chat_completions_kwargs,
    resolve_role_params,
    responses_kwargs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_policy(tmp_path: Path, roles: list[dict]) -> Path:
    policy = tmp_path / "llm-models.v1.json"
    policy.write_text(json.dumps({"roles": roles}), encoding="utf-8")
    return policy


# ---------------------------------------------------------------------------
# Läsaren - happy path mot riktiga policyn
# ---------------------------------------------------------------------------


def test_resolves_brief_model_params_from_real_policy():
    """briefModel = gpt-5.5 / medium / 16000 (v14 model routing v2: hela
    chat-/generationskedjan på gpt-5.5, höjt tak så reasoning inte svälter
    utdata i Responses-API:t)."""
    params = resolve_role_params("briefModel")
    assert params.role_id == "briefModel"
    assert params.model == "gpt-5.5"
    assert params.reasoning_effort == "medium"
    assert params.max_output_tokens == 16000


def test_real_policy_declares_adr_0052_start_values():
    """Hela ADR-tabellen, så en framtida policy-bump som tappar ett värde syns."""
    # v14 (model routing v2, operatörsbeslut 2026-06-16): gpt-5.5 på alla
    # chat-/generationsroller och rejält höjda maxOutputTokens eftersom
    # Responses-API:t räknar reasoning-tokens inne i utdatataket (ett för lågt
    # tak gav <no output> -> tyst mock-fallback). xhigh används aldrig.
    expected = {
        "briefModel": ("medium", 16000),
        "planningModel": ("high", 24000),
        "routerModel": ("high", 16000),
        "copyDirectiveModel": ("low", 12000),
        "styleDirectiveModel": ("none", 8000),
        "rerankModel": ("low", 8000),
        "codegenModel": ("medium", 16000),
        "repairModel": ("medium", 16000),
        "verifierModel": ("high", 16000),
        "variantModel": ("medium", 16000),
        "dossierModel": ("medium", 16000),
    }
    for role_id, (effort, tokens) in expected.items():
        params = resolve_role_params(role_id)
        assert params.reasoning_effort == effort, role_id
        assert params.max_output_tokens == tokens, role_id


# ---------------------------------------------------------------------------
# Läsaren - defensiva grenar (aldrig kastat fel)
# ---------------------------------------------------------------------------


def test_missing_role_returns_none_fields_with_warning(capsys):
    params = resolve_role_params("doesNotExistModel")
    assert params == RoleModelParams(role_id="doesNotExistModel")
    assert params.model is None
    assert params.reasoning_effort is None
    assert params.max_output_tokens is None
    assert "doesNotExistModel" in capsys.readouterr().err


def test_missing_file_returns_none_fields_with_warning(tmp_path: Path, capsys):
    missing = tmp_path / "does-not-exist.json"
    params = resolve_role_params("briefModel", policy_path=missing)
    assert params == RoleModelParams(role_id="briefModel")
    assert "saknas" in capsys.readouterr().err


def test_broken_json_returns_none_fields_with_warning(tmp_path: Path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    params = resolve_role_params("briefModel", policy_path=bad)
    assert params == RoleModelParams(role_id="briefModel")
    assert "kunde inte läsa" in capsys.readouterr().err


def test_non_dict_policy_returns_none_fields(tmp_path: Path, capsys):
    weird = tmp_path / "weird.json"
    weird.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    params = resolve_role_params("briefModel", policy_path=weird)
    assert params == RoleModelParams(role_id="briefModel")
    assert "roles" in capsys.readouterr().err


def test_legacy_minimal_maps_to_low_with_warning(tmp_path: Path, capsys):
    policy = _write_policy(
        tmp_path,
        [
            {
                "id": "briefModel",
                "provider": "openai",
                "model": "gpt-test",
                "reasoningEffort": "minimal",
                "maxOutputTokens": 1234,
            }
        ],
    )
    params = resolve_role_params("briefModel", policy_path=policy)
    assert params.reasoning_effort == "low"
    assert params.max_output_tokens == 1234
    err = capsys.readouterr().err
    assert "minimal" in err and "low" in err


def test_unknown_effort_enum_gives_none_with_warning(tmp_path: Path, capsys):
    policy = _write_policy(
        tmp_path,
        [
            {
                "id": "briefModel",
                "provider": "openai",
                "model": "gpt-test",
                "reasoningEffort": "ultrathink",
                "maxOutputTokens": 4000,
            }
        ],
    )
    params = resolve_role_params("briefModel", policy_path=policy)
    assert params.reasoning_effort is None
    # Taket läses fortfarande - ett trasigt fält fäller inte det andra.
    assert params.max_output_tokens == 4000
    assert "ultrathink" in capsys.readouterr().err


@pytest.mark.parametrize("bad_tokens", [0, -5, "4000", 12.5, True, False])
def test_invalid_max_tokens_gives_none_with_warning(
    tmp_path: Path, capsys, bad_tokens
):
    policy = _write_policy(
        tmp_path,
        [
            {
                "id": "briefModel",
                "provider": "openai",
                "model": "gpt-test",
                "reasoningEffort": "low",
                "maxOutputTokens": bad_tokens,
            }
        ],
    )
    params = resolve_role_params("briefModel", policy_path=policy)
    assert params.max_output_tokens is None, repr(bad_tokens)
    assert params.reasoning_effort == "low"
    assert "maxOutputTokens" in capsys.readouterr().err


def test_role_without_params_gives_none_fields_without_warning(
    tmp_path: Path, capsys
):
    """Frånvarande fält = dagens beteende, ingen varning (det är inte ett fel)."""
    policy = _write_policy(
        tmp_path,
        [{"id": "briefModel", "provider": "openai", "model": "gpt-test"}],
    )
    params = resolve_role_params("briefModel", policy_path=policy)
    assert params.model == "gpt-test"
    assert params.reasoning_effort is None
    assert params.max_output_tokens is None
    assert capsys.readouterr().err == ""


# ---------------------------------------------------------------------------
# kwargs-builders
# ---------------------------------------------------------------------------


def test_responses_kwargs_empty_when_nothing_set():
    assert responses_kwargs(RoleModelParams(role_id="x")) == {}


def test_chat_completions_kwargs_empty_when_nothing_set():
    assert chat_completions_kwargs(RoleModelParams(role_id="x")) == {}


def test_responses_kwargs_full_shape():
    params = RoleModelParams(
        role_id="x", model="m", reasoning_effort="medium", max_output_tokens=6000
    )
    assert responses_kwargs(params) == {
        "reasoning": {"effort": "medium"},
        "max_output_tokens": 6000,
    }


def test_responses_kwargs_effort_only():
    params = RoleModelParams(role_id="x", reasoning_effort="none")
    assert responses_kwargs(params) == {"reasoning": {"effort": "none"}}


def test_responses_kwargs_tokens_only():
    params = RoleModelParams(role_id="x", max_output_tokens=2000)
    assert responses_kwargs(params) == {"max_output_tokens": 2000}


def test_chat_completions_kwargs_full_shape():
    params = RoleModelParams(
        role_id="x", reasoning_effort="high", max_output_tokens=1500
    )
    assert chat_completions_kwargs(params) == {
        "reasoning_effort": "high",
        "max_completion_tokens": 1500,
    }


# ---------------------------------------------------------------------------
# Governance-vakt: embeddingModel får aldrig chat-params
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_embedding_model_never_has_chat_params():
    """ADR 0052: embeddings är ingen chat-modell - chat-params är förbjudna."""
    data = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    embedding = next(
        (r for r in data.get("roles", []) if r.get("id") == "embeddingModel"),
        None,
    )
    assert embedding is not None, "llm-models.v1.json saknar embeddingModel"
    assert "reasoningEffort" not in embedding, (
        "embeddingModel får aldrig reasoningEffort (ADR 0052)"
    )
    assert "maxOutputTokens" not in embedding, (
        "embeddingModel får aldrig maxOutputTokens (ADR 0052)"
    )


# ---------------------------------------------------------------------------
# Source-lock: de åtta call-sites trådar per-roll-params
# ---------------------------------------------------------------------------

# (källfil, roll-id, förväntat antal trådade anrop i filen)
_CALL_SITES = [
    ("packages/generation/brief/extract.py", "briefModel", 1),
    ("packages/generation/brief/extract.py", "copyDirectiveModel", 2),
    ("packages/generation/brief/extract.py", "styleDirectiveModel", 1),
    ("packages/generation/planning/plan.py", "planningModel", 1),
    ("packages/generation/orchestration/router/llm_fallback.py", "routerModel", 1),
    ("packages/generation/codegen/codegen.py", "codegenModel", 1),
    ("packages/generation/repair/blueprint_repair.py", "repairModel", 1),
    ("packages/generation/quality_gate/verifier.py", "verifierModel", 1),
]


@pytest.mark.parametrize(
    "rel_path, role_id, expected_count",
    _CALL_SITES,
    ids=[f"{p.rsplit('/', 1)[-1]}-{r}" for p, r, _ in _CALL_SITES],
)
def test_call_site_threads_role_params(
    rel_path: str, role_id: str, expected_count: int
):
    """Source-lock: varje riktigt responses.parse-anrop bär per-roll-params.

    En refactor som tappar ``**responses_kwargs(resolve_role_params(...))``
    återinför tyst modellens defaults (ostyrd effort/kostnad) utan att
    något funktionellt test fäller den - därav källkodslåset.
    """
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    needle = f'responses_kwargs(resolve_role_params("{role_id}"))'
    assert source.count(needle) == expected_count, (
        f"{rel_path}: förväntade {expected_count}x {needle!r} "
        f"men hittade {source.count(needle)} (ADR 0052)"
    )


def test_call_site_files_import_the_shared_reader():
    """Alla trådade filer importerar den delade läsaren - inga lokala kopior."""
    for rel_path in sorted({p for p, _, _ in _CALL_SITES}):
        source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert (
            "from packages.policies.llm_model_params import" in source
        ), f"{rel_path} måste importera packages.policies.llm_model_params"
