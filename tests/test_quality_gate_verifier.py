"""Tests for the kor-4b verifierModel critic (read-only taste lane).

Locks the kor-4b contract on top of the kor-4a deterministic critic:

- Without ``OPENAI_API_KEY`` the verifier critic returns EXACTLY the
  deterministic findings with ``source = "mock-no-key"`` (no regression).
- With a key, ``verifierModel`` findings are merged + deduped per
  ``(type, target)`` (deterministic wins on a collision), the score is
  recomputed over the merged set, and ``source = "verifierModel"``.
- An LLM/resolution error falls back to the deterministic findings with
  ``source = "mock-llm-error"``.
- The critic stays a warning lane: it NEVER changes ``QualityResult.status``.
- The deterministic default path (``use_verifier_critic=False``) is unchanged.

The real OpenAI call is monkeypatched so the suite never needs a key or the
network. Tests use ``tmp_path`` so they never touch ``data/runs/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.quality_gate import (
    CriticIssue,
    CriticResult,
    VerifierModelResolutionError,
    resolve_verifier_model,
    run_deterministic_critic,
    run_quality_gate,
    run_verifier_critic,
)
from packages.generation.quality_gate import verifier as verifier_module


def _issue_types(critic: CriticResult) -> set[str]:
    return {issue.type for issue in critic.issues}


def _write_page(target: Path, route: str, body: str = "<div>x</div>") -> None:
    if route == "/":
        path = target / "app" / "page.tsx"
    else:
        path = target / "app" / route.lstrip("/") / "page.tsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"export default function Page() {{ return ({body}); }}",
        encoding="utf-8",
    )


# A deliberately generic blueprint so the deterministic lane already fires
# (generic_copy on the hero, thin_offer on a one-item service list).
def _generic_blueprint() -> tuple[dict, dict]:
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Välkommen till vår hemsida",
                "subheadline": "Vi erbjuder tjänster av högsta kvalitet i Malmö.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "Tjänst", "summary": "x"},
            ],
        }
    }
    brief = {"locationHint": "Malmö", "conversion": {"primaryCta": "Be om offert"}}
    return gp, brief


@pytest.fixture
def _no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def _with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")


# ---------------------------------------------------------------------------
# Mock (no key) == kor-4a behaviour
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_no_key_returns_deterministic_findings_with_mock_source(_no_key):
    gp, brief = _generic_blueprint()
    deterministic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    verifier = run_verifier_critic(generation_package=gp, site_brief=brief)

    assert verifier.source == "mock-no-key"
    # Identical findings + score to kor-4a (no regression).
    assert verifier.issues == deterministic.issues
    assert verifier.score == deterministic.score


@pytest.mark.tooling
def test_no_key_clean_blueprint_matches_deterministic(_no_key):
    gp = {
        "contentBlocks": {
            "home.hero": {
                "headline": "Trygg elektriker i Malmö när jobbet måste bli rätt",
                "subheadline": "Vi hjälper föreningar och företag i Malmö.",
                "primaryCta": "Be om offert",
            },
            "services.service-list": [
                {"title": "Elinstallationer", "summary": "Säkra installationer."},
                {"title": "Felsökning", "summary": "Snabb felsökning på plats."},
                {"title": "Laddboxar", "summary": "Montering av laddbox hemma."},
            ],
        }
    }
    brief = {"locationHint": "Malmö", "conversion": {"primaryCta": "Be om offert"}}
    verifier = run_verifier_critic(generation_package=gp, site_brief=brief)
    assert verifier.source == "mock-no-key"
    assert verifier.issues == []
    assert verifier.score == 100


# ---------------------------------------------------------------------------
# Real-ish path (key present, model call monkeypatched)
# ---------------------------------------------------------------------------


def _patch_llm(monkeypatch, issues: list[CriticIssue]) -> None:
    monkeypatch.setattr(
        verifier_module, "_run_verifier_model", lambda **_: list(issues)
    )


@pytest.mark.tooling
def test_with_key_merges_llm_findings_and_sets_source(_with_key, monkeypatch):
    gp, brief = _generic_blueprint()
    llm = [
        CriticIssue(
            severity="medium",
            type="weak_hero",
            target="home.hero",
            message="Hero säger inte vad företaget gör.",
            repairHint="Säg vad ni gör och för vem i rubriken.",
        ),
        CriticIssue(
            severity="high",
            type="fake_or_ungrounded_trust",
            target="home.hero",
            message="'högsta kvalitet' är ogrundat.",
            repairHint="Ta bort superlativen eller grunda den i ett faktum.",
        ),
    ]
    _patch_llm(monkeypatch, llm)

    deterministic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    verifier = run_verifier_critic(generation_package=gp, site_brief=brief)

    assert verifier.source == "verifierModel"
    # Deterministic findings are preserved...
    for issue in deterministic.issues:
        assert issue in verifier.issues
    # ...and the new taste types are merged in.
    assert "weak_hero" in _issue_types(verifier)
    assert "fake_or_ungrounded_trust" in _issue_types(verifier)
    # Score is recomputed over the larger merged set, so it can only drop.
    assert verifier.score <= deterministic.score


@pytest.mark.tooling
def test_dedup_drops_llm_finding_colliding_with_deterministic(_with_key, monkeypatch):
    gp, brief = _generic_blueprint()
    # The deterministic lane already flags generic_copy on home.hero; the LLM
    # returns the same (type, target) plus a distinct weak_hero.
    llm = [
        CriticIssue(
            severity="medium",
            type="generic_copy",
            target="home.hero",
            message="LLM: generisk hero.",
            repairHint="Skärp copyn.",
        ),
        CriticIssue(
            severity="medium",
            type="weak_hero",
            target="home.hero",
            message="Svag hero.",
            repairHint="Säg vad ni gör.",
        ),
    ]
    _patch_llm(monkeypatch, llm)

    verifier = run_verifier_critic(generation_package=gp, site_brief=brief)
    generic_on_hero = [
        i for i in verifier.issues if i.type == "generic_copy" and i.target == "home.hero"
    ]
    # Exactly one generic_copy on home.hero, and it is the deterministic one
    # (deterministic wins the collision - its message is not the LLM message).
    assert len(generic_on_hero) == 1
    assert generic_on_hero[0].message != "LLM: generisk hero."
    # The distinct weak_hero finding survived dedup.
    assert any(
        i.type == "weak_hero" and i.target == "home.hero" for i in verifier.issues
    )


@pytest.mark.tooling
def test_llm_error_falls_back_to_deterministic(_with_key, monkeypatch):
    gp, brief = _generic_blueprint()

    def _boom(**_):
        raise RuntimeError("simulated OpenAI failure")

    monkeypatch.setattr(verifier_module, "_run_verifier_model", _boom)

    deterministic = run_deterministic_critic(generation_package=gp, site_brief=brief)
    verifier = run_verifier_critic(generation_package=gp, site_brief=brief)

    assert verifier.source == "mock-llm-error"
    assert verifier.issues == deterministic.issues
    assert verifier.score == deterministic.score


# ---------------------------------------------------------------------------
# Warning lane: never changes status, wired through run_quality_gate
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_run_quality_gate_verifier_opt_in_no_key_is_non_blocking(_no_key, tmp_path):
    _write_page(tmp_path, "/")
    gp, brief = _generic_blueprint()
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
        use_verifier_critic=True,
    )
    assert isinstance(result.critic, CriticResult)
    assert result.critic.source == "mock-no-key"
    # Status is decided solely by the blocking/warning checks.
    assert result.status == "ok"
    assert len(result.checks) == 6


@pytest.mark.tooling
def test_run_quality_gate_default_path_unchanged(_no_key, tmp_path):
    """Regression guard: without use_verifier_critic the source stays kor-4a."""
    _write_page(tmp_path, "/")
    gp, brief = _generic_blueprint()
    result = run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
    )
    assert result.critic is not None
    assert result.critic.source == "deterministic-v0"


@pytest.mark.tooling
def test_verifier_critic_trace_event_records_source(_with_key, monkeypatch, tmp_path):
    _write_page(tmp_path, "/")
    gp, brief = _generic_blueprint()
    _patch_llm(
        monkeypatch,
        [
            CriticIssue(
                severity="medium",
                type="too_template_like",
                target="home.hero",
                message="Mall-känsla.",
                repairHint="Gör copyn branschspecifik.",
            )
        ],
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run_quality_gate(
        target_dir=tmp_path,
        required_routes=["/"],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
        run_dir=run_dir,
        run_id="r1",
        use_verifier_critic=True,
    )
    lines = [
        json.loads(line)
        for line in (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    critic_events = [line for line in lines if line["event"] == "critic.evaluated"]
    assert len(critic_events) == 1
    assert critic_events[0]["status"] == "warning"
    assert "source=verifierModel" in critic_events[0]["message"]


# ---------------------------------------------------------------------------
# verifierModel resolver
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_resolve_verifier_model_returns_policy_model():
    assert resolve_verifier_model() == "gpt-5.5"


@pytest.mark.tooling
def test_resolve_verifier_model_raises_on_missing_role(tmp_path):
    policy = tmp_path / "llm-models.v1.json"
    policy.write_text(json.dumps({"roles": []}), encoding="utf-8")
    with pytest.raises(VerifierModelResolutionError):
        resolve_verifier_model(policy)


@pytest.mark.tooling
def test_resolve_verifier_model_raises_on_wrong_provider(tmp_path):
    policy = tmp_path / "llm-models.v1.json"
    policy.write_text(
        json.dumps(
            {"roles": [{"id": "verifierModel", "provider": "anthropic", "model": "x"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(VerifierModelResolutionError):
        resolve_verifier_model(policy)


# ---------------------------------------------------------------------------
# Merged result still validates against the schema (new types + source)
# ---------------------------------------------------------------------------


@pytest.mark.governance
def test_verifier_result_validates_against_schema(_with_key, monkeypatch):
    from packages.generation.artifacts import validate_quality_result

    gp, brief = _generic_blueprint()
    _patch_llm(
        monkeypatch,
        [
            CriticIssue(
                severity="high",
                type="fake_or_ungrounded_trust",
                target="home.hero",
                message="Ogrundat påstående.",
                repairHint="Grunda eller ta bort.",
            ),
            CriticIssue(
                severity="medium",
                type="weak_hero",
                target="home.hero",
                message="Svag hero.",
                repairHint="Var konkret.",
            ),
        ],
    )
    result = run_quality_gate(
        target_dir=Path("/this/path/does/not/exist"),
        required_routes=[],
        npm_steps=[],
        build_status="skipped",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
        use_verifier_critic=True,
    )
    payload = result.model_dump()
    assert payload["critic"]["source"] == "verifierModel"
    types = {issue["type"] for issue in payload["critic"]["issues"]}
    assert {"fake_or_ungrounded_trust", "weak_hero"} <= types
    validate_quality_result(payload)  # raises on drift


# ---------------------------------------------------------------------------
# Offline safety: no-key path never imports openai
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_no_key_path_does_not_import_openai(_no_key, monkeypatch):
    """The mock-no-key path must short-circuit before touching the OpenAI SDK."""

    def _fail(**_):
        raise AssertionError("_run_verifier_model must not be called without a key")

    monkeypatch.setattr(verifier_module, "_run_verifier_model", _fail)
    gp, brief = _generic_blueprint()
    result = run_verifier_critic(generation_package=gp, site_brief=brief)
    assert result.source == "mock-no-key"
