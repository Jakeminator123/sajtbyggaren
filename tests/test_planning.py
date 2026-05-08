"""Tests for packages/generation/planning - the canonical planningModel helper.

Sprint 2B introduces ``produce_site_plan`` as the single source of truth
for Phase 2 Plan. Both ``scripts/build_site.py`` and
``scripts/dev_generate.py`` go through it. These tests pin:

1. The deterministic mock fallback runs when no OPENAI_API_KEY is set
   and writes ``planSource = 'mock-no-key'``.
2. The mock-llm-error path triggers when the LLM call raises and writes
   ``planSource = 'mock-llm-error'`` plus ``planError`` text.
3. The pinned path (Project Input pre-selects scaffold/variant) writes
   ``planSource = 'pinned'`` and skips the LLM even when a key exists.
4. The capability filter honours capability-map.v1's "empty list = gap"
   rule: capabilities without a Dossier surface as ``rejected[]``,
   never as silently-included selectedDossiers.
5. The Site Plan + Generation Package returned by the helper validate
   against their canonical schemas.
6. The on-disk scaffold registry now contains at least two scaffolds
   with content (local-service-business + ecommerce-lite) so the
   planner has a real choice. This is the artefact part of B19 closure
   - a single-choice "selector" is not a selector.
7. B19 source-code regression: both scripts import produce_site_plan
   and neither contains its own inline plan-construction. If a future
   refactor reintroduces parallel plan logic, this test fails.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from packages.generation.artifacts import (
    validate_generation_package,
    validate_site_plan,
)
from packages.generation.brief.models import OPENAI_API_KEY_ENV
from packages.generation.planning import (
    PlanningChoice,
    PlanningModelResolutionError,
    PlanResult,
    RejectedCapability,
    filter_capabilities,
    load_capability_map,
    load_scaffold_registry,
    produce_site_plan,
    resolve_planning_model,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _baseline_brief(**overrides: Any) -> dict[str, Any]:
    brief: dict[str, Any] = {
        "runId": "test-run-1",
        "language": "sv",
        "rawPrompt": "Skapa hemsida för en elektriker i Malmö",
        "tone": ["trustworthy"],
        "targetAudience": ["lokala fastighetsägare"],
        "requestedCapabilities": [],
        "conversionGoals": ["call"],
        "servicesMentioned": [],
        "sourceModelRole": "briefModel",
        "modelUsed": "mock",
        "briefSource": "mock-no-key",
        "createdAt": "2026-05-08T12:00:00+00:00",
    }
    brief.update(overrides)
    return brief


# ---------------------------------------------------------------------------
# resolve_planning_model
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_resolves_planning_model_from_real_policy():
    """The committed llm-models.v1.json must declare a usable planningModel."""
    model = resolve_planning_model()
    assert isinstance(model, str)
    assert model.strip() == model
    assert model, "planningModel.model must be non-empty"


@pytest.mark.tooling
def test_resolve_planning_model_raises_when_role_missing(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps(
            {"roles": [{"id": "briefModel", "provider": "openai", "model": "x"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(PlanningModelResolutionError, match="planningModel role missing"):
        resolve_planning_model(policy_path=policy)


@pytest.mark.tooling
def test_resolve_planning_model_raises_on_wrong_provider(tmp_path: Path):
    policy = tmp_path / "models.json"
    policy.write_text(
        json.dumps(
            {"roles": [{"id": "planningModel", "provider": "anthropic", "model": "claude"}]}
        ),
        encoding="utf-8",
    )
    with pytest.raises(PlanningModelResolutionError, match="provider must be"):
        resolve_planning_model(policy_path=policy)


# ---------------------------------------------------------------------------
# Scaffold registry (Sprint 2B requires at least two scaffolds with content)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_registry_contains_at_least_two_scaffolds_with_content():
    """B19 closure requires a real selector. A selector with one option is
    not a selector - planningModel must have something to choose between.
    """
    registry = load_scaffold_registry()
    ids = sorted(entry["id"] for entry in registry)
    assert "local-service-business" in ids, (
        "local-service-business must remain in the registry"
    )
    assert "ecommerce-lite" in ids, (
        "ecommerce-lite scaffold must exist on disk so planningModel has at "
        "least two real candidates after Sprint 2B."
    )
    assert len(registry) >= 2


@pytest.mark.tooling
def test_each_registered_scaffold_has_at_least_one_variant():
    """A scaffold without a variant cannot be planned against - the planner
    has nothing to put in site-plan.variantId. Guard at registry load time.
    """
    registry = load_scaffold_registry()
    missing = [entry["id"] for entry in registry if not entry["variants"]]
    assert not missing, (
        f"Scaffolds with no variants: {missing}. Add a variant under "
        f"variants/ before the registry load can succeed."
    )


# ---------------------------------------------------------------------------
# Capability filter (the "empty list = gap" rule from capability-map.v1)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_filter_capabilities_passes_through_implemented_capabilities():
    """Real capability-map.v1.json has interactive-game backed by a Dossier.
    Asking for it should select the Dossier and leave rejected[] empty.
    """
    cap_map = load_capability_map()
    selected, rejected = filter_capabilities(["interactive-game"], cap_map)
    assert "interactive-game-loop" in selected
    assert rejected == []


@pytest.mark.tooling
def test_filter_capabilities_rejects_capabilities_with_empty_dossier_list():
    """contact-form, payments, auth etc. are registered as gaps in the real
    capability-map.v1.json. Asking for them must surface them in rejected[]
    rather than silently including a non-existent Dossier.
    """
    cap_map = load_capability_map()
    selected, rejected = filter_capabilities(
        ["contact-form", "payments"], cap_map
    )
    assert selected == []
    rejected_ids = {entry.id for entry in rejected}
    assert {"contact-form", "payments"} <= rejected_ids
    for entry in rejected:
        assert entry.reason, "Every rejected entry must carry a reason"


@pytest.mark.tooling
def test_filter_capabilities_rejects_unknown_capability():
    cap_map = load_capability_map()
    selected, rejected = filter_capabilities(
        ["this-is-not-a-real-capability-slug"], cap_map
    )
    assert selected == []
    assert len(rejected) == 1
    assert rejected[0].id == "this-is-not-a-real-capability-slug"
    assert "not registered" in rejected[0].reason.lower()


# ---------------------------------------------------------------------------
# produce_site_plan: mock-no-key path
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_produce_site_plan_without_api_key_uses_mock_no_key(monkeypatch):
    """No OPENAI_API_KEY -> deterministic mock + planSource = mock-no-key."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    result = produce_site_plan(_baseline_brief(), run_id="test-run-1")

    assert isinstance(result, PlanResult)
    assert result.source == "mock-no-key"
    assert result.error is None
    assert result.site_plan["planSource"] == "mock-no-key"
    assert result.site_plan["modelUsed"] == "mock"
    assert result.site_plan["scaffoldId"] == "local-service-business"
    # The default scaffold's variant is whatever load_scaffold_registry
    # finds first. Don't pin to nordic-trust - just sanity check.
    assert result.site_plan["variantId"]
    assert result.site_plan["starterId"] == "marketing-base"
    validate_site_plan(result.site_plan)
    validate_generation_package(result.generation_package)


@pytest.mark.tooling
def test_produce_site_plan_picks_ecommerce_lite_on_commerce_signal(monkeypatch):
    """Mock heuristic: commerce keywords in the brief route to ecommerce-lite."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    brief = _baseline_brief(
        rawPrompt="Bygg en webshop för premium-kaffe från Mallorca",
        businessTypeGuess="coffee-store",
    )
    result = produce_site_plan(brief, run_id="test-run-2")

    assert result.site_plan["scaffoldId"] == "ecommerce-lite"
    assert result.site_plan["starterId"] == "marketing-base", (
        "Sprint 2B uses marketing-base as ecommerce-lite's starter until "
        "commerce-base harmonisation lands."
    )


@pytest.mark.tooling
def test_produce_site_plan_records_rejected_capabilities_in_object_form(monkeypatch):
    """When mock filter rejects capabilities, selectedDossiers must be the
    object form so rationale + rejected[] survive into the artefakt.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(requestedCapabilities=["contact-form", "payments"])
    result = produce_site_plan(brief, run_id="test-run-3")

    selected = result.site_plan["selectedDossiers"]
    assert isinstance(selected, dict), (
        "Rejected capabilities must trigger the object form so rationale "
        "and rejected[] are not silently dropped."
    )
    assert selected["recommended"] == []
    rejected_ids = {entry["id"] for entry in selected["rejected"]}
    assert {"contact-form", "payments"} <= rejected_ids
    assert "Mock plan" in selected["rationale"]


# ---------------------------------------------------------------------------
# produce_site_plan: pinned (builder) path
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_produce_site_plan_pinned_skips_llm_even_with_key(monkeypatch):
    """Project Input pin -> planningModel is NOT called even with API key set."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "planningModel must not be called on the pinned path"
        )

    monkeypatch.setattr(
        "packages.generation.planning.plan._real_plan_choice",
        fail_if_called,
    )

    brief = _baseline_brief(requestedCapabilities=["interactive-game"])
    result = produce_site_plan(
        brief,
        run_id="test-pin-1",
        pinned={"scaffoldId": "local-service-business", "variantId": "nordic-trust"},
    )

    assert result.source == "pinned"
    assert result.site_plan["planSource"] == "pinned"
    assert result.site_plan["scaffoldId"] == "local-service-business"
    assert result.site_plan["variantId"] == "nordic-trust"
    assert result.site_plan["starterId"] == "marketing-base"
    selected = result.site_plan["selectedDossiers"]
    assert isinstance(selected, dict)
    assert "interactive-game-loop" in selected["recommended"]


@pytest.mark.tooling
def test_produce_site_plan_pinned_rejects_unknown_scaffold(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match="no scaffold with that id"):
        produce_site_plan(
            _baseline_brief(),
            run_id="test-pin-2",
            pinned={"scaffoldId": "totally-fake", "variantId": "x"},
        )


@pytest.mark.tooling
def test_produce_site_plan_pinned_rejects_unknown_variant(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match="only declares variants"):
        produce_site_plan(
            _baseline_brief(),
            run_id="test-pin-3",
            pinned={
                "scaffoldId": "local-service-business",
                "variantId": "not-a-real-variant",
            },
        )


# ---------------------------------------------------------------------------
# produce_site_plan: mock-llm-error path
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_produce_site_plan_falls_back_when_llm_raises(monkeypatch, capsys):
    """planningModel exception -> mock fallback + planSource=mock-llm-error."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic planning failure")

    monkeypatch.setattr(
        "packages.generation.planning.plan._real_plan_choice",
        boom,
    )

    result = produce_site_plan(_baseline_brief(), run_id="test-llm-err")

    assert result.source == "mock-llm-error"
    assert result.error is not None
    assert "synthetic planning failure" in result.error
    assert result.site_plan["planSource"] == "mock-llm-error"
    assert result.site_plan["modelUsed"] == "mock"
    assert result.site_plan["planError"] is not None
    assert result.attemptedModel  # the resolver returned the configured model
    captured = capsys.readouterr()
    assert "planningModel" in captured.err


# ---------------------------------------------------------------------------
# Real LLM happy path (with monkeypatched _real_plan_choice)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_produce_site_plan_real_path_returns_validated_artefakts(monkeypatch):
    """Successful planningModel call -> planSource=real and validated artefakts."""
    monkeypatch.setenv(OPENAI_API_KEY_ENV, "sk-test-fake")

    captured_inputs: dict[str, Any] = {}

    def fake_real_plan_choice(site_brief, registry, capability_map, *, model):
        captured_inputs["model"] = model
        captured_inputs["registry_ids"] = [s["id"] for s in registry]
        scaffold = next(s for s in registry if s["id"] == "local-service-business")
        return (
            PlanningChoice(
                scaffoldId="local-service-business",
                variantId="nordic-trust",
                selectedDossiers=["interactive-game-loop"],
                rejectedCapabilities=[
                    RejectedCapability(
                        id="contact-form",
                        reason="No Dossier in repo yet (planned).",
                    )
                ],
                rationale="Fake real plan: chose local-service-business.",
            ),
            scaffold,
        )

    monkeypatch.setattr(
        "packages.generation.planning.plan._real_plan_choice",
        fake_real_plan_choice,
    )

    brief = _baseline_brief(
        businessTypeGuess="electrician",
        requestedCapabilities=["interactive-game", "contact-form"],
    )
    result = produce_site_plan(brief, run_id="test-real-1")

    assert result.source == "real"
    assert result.error is None
    assert result.site_plan["planSource"] == "real"
    assert result.site_plan["modelUsed"] != "mock"
    assert captured_inputs["model"]  # whatever resolve_planning_model returned
    assert "local-service-business" in captured_inputs["registry_ids"]

    # Object form with rationale + rejected[] preserved into the artefakt.
    selected = result.site_plan["selectedDossiers"]
    assert isinstance(selected, dict)
    assert selected["recommended"] == ["interactive-game-loop"]
    assert selected["rejected"][0]["id"] == "contact-form"


# ---------------------------------------------------------------------------
# B19 closure: source-code regression on the two scripts
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b19_dev_generate_imports_produce_site_plan():
    """If a future refactor reintroduces inline plan-construction in
    dev_generate.py, this guard catches it before B19 reopens.
    """
    source = (SCRIPTS_DIR / "dev_generate.py").read_text(encoding="utf-8")
    assert "from packages.generation.planning import produce_site_plan" in source, (
        "scripts/dev_generate.py must call into the shared planning helper. "
        "Removing this import means dev_generate.py is building plans on its own "
        "again - that is the B19 drift this sprint closed."
    )


@pytest.mark.tooling
def test_b19_build_site_imports_produce_site_plan():
    source = (SCRIPTS_DIR / "build_site.py").read_text(encoding="utf-8")
    assert "from packages.generation.planning import produce_site_plan" in source, (
        "scripts/build_site.py must call into the shared planning helper."
    )


@pytest.mark.tooling
def test_b19_neither_script_keeps_legacy_local_planner_function():
    """The pre-Sprint-2B helpers ``build_site_plan_mock`` and the ad-hoc
    site_plan dict literal in dev_generate.py:run_phase_plan are gone. If
    a future commit re-adds either, this test fails loudly.
    """
    build_source = (SCRIPTS_DIR / "build_site.py").read_text(encoding="utf-8")
    dev_source = (SCRIPTS_DIR / "dev_generate.py").read_text(encoding="utf-8")
    assert "def build_site_plan_mock" not in build_source, (
        "build_site_plan_mock was removed in Sprint 2B - reintroducing it "
        "reopens B19. Use packages.generation.planning.produce_site_plan instead."
    )
    assert '"planSource": "mock-pre-sprint-2b"' not in dev_source, (
        "The inline pre-Sprint-2B mock plan literal was removed in Sprint 2B. "
        "Plan construction must go through produce_site_plan."
    )
