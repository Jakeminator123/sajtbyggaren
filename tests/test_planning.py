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
import re
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
    merge_operator_selected_with_helper,
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
    """auth, payments etc. are registered as gaps in the real
    capability-map.v1.json. Asking for them must surface them in rejected[]
    rather than silently including a non-existent Dossier.

    Note: contact-form was previously the example here, but the Week 1
    "fantastic sites" roadmap (2026-05-24) closed that gap by registering
    mailto-contact-form. auth + payments remain canonical gap examples
    until clerk-auth / stripe-checkout are imported from MIN_IDE.
    """
    cap_map = load_capability_map()
    selected, rejected = filter_capabilities(
        ["auth", "payments"], cap_map
    )
    assert selected == []
    rejected_ids = {entry.id for entry in rejected}
    assert {"auth", "payments"} <= rejected_ids
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


@pytest.mark.tooling
def test_filter_capabilities_dedupes_input():
    cap_map = load_capability_map()
    selected, rejected = filter_capabilities(
        ["auth", "auth", "auth"], cap_map
    )
    assert selected == []
    assert len(rejected) == 1
    assert rejected[0].id == "auth"


@pytest.mark.tooling
def test_filter_capabilities_raises_when_default_not_in_dossiers():
    cap_map = {
        "capabilities": {
            "demo-capability": {
                "dossiers": ["one-dossier"],
                "default": "some-other-dossier",
            }
        }
    }
    with pytest.raises(RuntimeError, match="not listed in dossiers"):
        filter_capabilities(["demo-capability"], cap_map)


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
    assert result.site_plan["starterId"] == "commerce-base", (
        "B20 step 2 activated ecommerce-lite -> commerce-base routing; the "
        "vendored commerce-base starter (PR #16) is now the runtime target."
    )


# ---------------------------------------------------------------------------
# Mock heuristic — clinic-healthcare routing (closes Lane 3 embeddings-gate
# blocker for naprapat-stockholm baseline case in
# scripts/run_golden_path_eval.py). Regression tests pin that sharp medical
# terms route to clinic-healthcare/clinic-calm/marketing-base while wellness/
# salon/ecommerce briefs keep their existing routing.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_produce_site_plan_picks_clinic_healthcare_on_naprapat_signal(monkeypatch):
    """Mock heuristic: ``naprapatklinik`` in the prompt routes to clinic-healthcare.

    This is the exact ``naprapat-stockholm`` case from
    ``scripts/run_golden_path_eval.py``. Pre-fix the deterministic mock
    fallback only knew about ecommerce-lite vs local-service-business and
    therefore routed naprapat to local-service-business/nordic-trust,
    scoring 5.83 (below PASS_CASE_THRESHOLD=6.5) and dragging the whole
    Lane 3 embeddings-readiness gate to no-go.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    brief = _baseline_brief(
        rawPrompt="Skapa en hemsida för en naprapatklinik i Stockholm.",
        businessTypeGuess="naprapatklinik",
    )
    result = produce_site_plan(brief, run_id="test-clinic-naprapat")

    assert result.site_plan["scaffoldId"] == "clinic-healthcare"
    assert result.site_plan["variantId"] == "clinic-calm", (
        "_DEFAULT_VARIANT_BY_SCAFFOLD pins clinic-calm as the safest "
        "clinic-healthcare default; warm-care suits chiropractor / "
        "naprapath / holistic, and modern-precision suits specialist / "
        "fertility / aesthetic."
    )
    assert result.site_plan["starterId"] == "marketing-base", (
        "clinic-healthcare reuses marketing-base via SCAFFOLD_TO_STARTER "
        "(Path B step 12). No new starter was vendored."
    )


@pytest.mark.tooling
@pytest.mark.parametrize(
    "raw_prompt,business_type,case_label",
    [
        (
            "Skapa en hemsida för en tandläkarmottagning i Uppsala.",
            "dentist",
            "dentist (tandläkare)",
        ),
        (
            "Skapa en hemsida för en kiropraktor i Lund.",
            "kiropraktor",
            "chiropractor (kiropraktor)",
        ),
        (
            "Skapa en hemsida för en fysioterapeut i Borås.",
            "fysioterapeut",
            "physiotherapist (fysioterapeut)",
        ),
        (
            "Skapa en hemsida för en psykolog i Linköping.",
            "psykolog",
            "psychologist (psykolog)",
        ),
        (
            "Skapa en hemsida för en veterinärklinik i Skövde.",
            "veterinärklinik",
            "veterinary (veterinärklinik)",
        ),
    ],
)
def test_produce_site_plan_picks_clinic_healthcare_on_sharp_medical_signal(
    monkeypatch, raw_prompt, business_type, case_label
):
    """Mock heuristic: sharp medical terms in the brief route to clinic-healthcare.

    Mirrors the regulated-clinician subset of
    ``packages/generation/orchestration/scaffolds/clinic-healthcare/selection-profile.json``
    semanticSignals while staying conservative against false positives on
    wellness/salon briefs.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    brief = _baseline_brief(
        rawPrompt=raw_prompt,
        businessTypeGuess=business_type,
    )
    result = produce_site_plan(brief, run_id=f"test-clinic-{business_type}")

    assert result.site_plan["scaffoldId"] == "clinic-healthcare", (
        f"{case_label} should route to clinic-healthcare "
        f"(prompt={raw_prompt!r}, businessTypeGuess={business_type!r})."
    )
    assert result.site_plan["variantId"] == "clinic-calm"
    assert result.site_plan["starterId"] == "marketing-base"


@pytest.mark.tooling
def test_produce_site_plan_skips_clinic_for_salon_brief(monkeypatch):
    """Negative: hairsalon prompt must keep routing to local-service-business.

    Bare ``klinik`` / ``clinic`` is intentionally NOT in _CLINIC_SIGNALS
    because beauty-klinik / hair-klinik / wellness-klinik are scaffold's
    explicit negative-signals (selection-profile.json
    llmClassificationHints rad 31-32) and belong to local-service-business.
    Mirrors the salon-goteborg baseline case in run_golden_path_eval.py.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    brief = _baseline_brief(
        rawPrompt="Skapa en hemsida för en frisörsalong i Göteborg.",
        businessTypeGuess="frisor-salong",
        servicesMentioned=["klippning", "färg", "styling"],
    )
    result = produce_site_plan(brief, run_id="test-salon-neg")

    assert result.site_plan["scaffoldId"] == "local-service-business", (
        "frisörsalong must remain on local-service-business — beauty/"
        "salon is the scaffold's negative-signal per selection-profile.json."
    )


@pytest.mark.tooling
def test_produce_site_plan_picks_ecommerce_over_clinic_when_both_signal(monkeypatch):
    """Order-of-operations: commerce signals beat clinic signals.

    A "tandvårdsbutik som säljer munhygienprodukter" has both
    ``tandvård`` (loose clinic-adjacent) and ``produkt`` + ``butik``
    (commerce) in the haystack. The mock fallback must pick ecommerce-lite,
    not clinic-healthcare — otherwise an obvious ecommerce shop would
    silently inherit clinic chrome (treatments page, credentials row, etc).
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    brief = _baseline_brief(
        rawPrompt=(
            "Bygg en webshop för en tandvårdsbutik som säljer "
            "munhygienprodukter i Stockholm."
        ),
        businessTypeGuess="dental-supplies-shop",
        servicesMentioned=["tandborstar", "tandkräm", "produkter"],
    )
    result = produce_site_plan(brief, run_id="test-clinic-vs-commerce")

    assert result.site_plan["scaffoldId"] == "ecommerce-lite", (
        "Commerce signals must win over clinic signals — otherwise an "
        "obvious shop would silently inherit clinic chrome."
    )


@pytest.mark.tooling
def test_produce_site_plan_clinic_routing_via_business_type_only(monkeypatch):
    """businessTypeGuess alone (no rawPrompt match) must drive clinic-routing.

    briefModel sometimes produces a precise ``businessTypeGuess`` while
    ``rawPrompt`` reuses the operator's ad-hoc prompt that happens not
    to mention the medical term. The fallback must still see the signal.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)

    brief = _baseline_brief(
        rawPrompt="Hjälp med ryggsmärta — lugn och bekväm mottagning.",
        businessTypeGuess="naprapath-clinic",
    )
    result = produce_site_plan(brief, run_id="test-clinic-via-bizt")

    assert result.site_plan["scaffoldId"] == "clinic-healthcare"
    assert result.site_plan["variantId"] == "clinic-calm"


@pytest.mark.tooling
def test_produce_site_plan_records_rejected_capabilities_in_object_form(monkeypatch):
    """When mock filter rejects capabilities, selectedDossiers must be the
    object form so rationale + rejected[] survive into the artefakt.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(requestedCapabilities=["auth", "payments"])
    result = produce_site_plan(brief, run_id="test-run-3")

    selected = result.site_plan["selectedDossiers"]
    assert isinstance(selected, dict), (
        "Rejected capabilities must trigger the object form so rationale "
        "and rejected[] are not silently dropped."
    )
    assert selected["recommended"] == []
    rejected_ids = {entry["id"] for entry in selected["rejected"]}
    assert {"auth", "payments"} <= rejected_ids
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


@pytest.mark.tooling
def test_produce_site_plan_pinned_rejects_nonexistent_starter(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match="no starter exists"):
        produce_site_plan(
            _baseline_brief(),
            run_id="test-pin-4",
            pinned={
                "scaffoldId": "local-service-business",
                "variantId": "nordic-trust",
                "starterId": "starter-that-does-not-exist",
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


@pytest.mark.tooling
def test_site_plan_and_generation_package_share_createdAt_within_run(monkeypatch):
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    result = produce_site_plan(_baseline_brief(), run_id="test-createdAt-1")
    assert result.site_plan["createdAt"] == result.generation_package["createdAt"]


@pytest.mark.tooling
def test_generation_package_keeps_site_brief_by_ref_contract(monkeypatch):
    """B141 fix chooses the existing by-reference contract.

    Generation Package should keep pointing at the canonical Site Brief
    artefact instead of duplicating the full brief inline.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    result = produce_site_plan(
        _baseline_brief(
            businessTypeGuess="electrician",
            tone=["trustworthy", "local"],
        ),
        run_id="test-generation-package-brief-ref",
    )

    assert result.generation_package["siteBriefRef"] == "site-brief.json"
    assert "siteBrief" not in result.generation_package
    validate_generation_package(result.generation_package)


@pytest.mark.tooling
def test_merge_preserves_helper_rejected_when_operator_object_has_no_rejected():
    operator = {
        "required": ["interactive-game-loop"],
        "recommended": [],
        "conditional": [],
        "rationale": "Operator-picked dossiers.",
    }
    helper_payload = {
        "required": [],
        "recommended": ["interactive-game-loop"],
        "conditional": [],
        "rationale": "Helper rationale",
        "rejected": [{"id": "payments", "reason": "No Dossier implemented yet."}],
    }
    merged = merge_operator_selected_with_helper(operator, helper_payload)
    assert isinstance(merged, dict)
    assert merged["required"] == ["interactive-game-loop"]
    assert merged["rejected"] == [{"id": "payments", "reason": "No Dossier implemented yet."}]
    assert merged["rationale"] == "Operator-picked dossiers."


@pytest.mark.tooling
def test_merge_keeps_operator_required_and_appends_helper_rejected():
    operator = {
        "required": ["interactive-game-loop"],
        "recommended": [],
        "conditional": [],
        "rejected": [{"id": "contact-form", "reason": "Operator note"}],
    }
    helper_payload = {
        "required": [],
        "recommended": ["interactive-game-loop"],
        "conditional": [],
        "rationale": "Helper rationale",
        "rejected": [
            {"id": "contact-form", "reason": "Duplicate should not be added"},
            {"id": "payments", "reason": "No Dossier implemented yet."},
        ],
    }
    merged = merge_operator_selected_with_helper(operator, helper_payload)
    assert isinstance(merged, dict)
    assert merged["required"] == ["interactive-game-loop"]
    rejected_ids = {item["id"] for item in merged["rejected"]}
    assert rejected_ids == {"contact-form", "payments"}
    assert merged["rationale"] == "Helper rationale"


# ---------------------------------------------------------------------------
# B24 closure: merge_operator_selected_with_helper(operator=list) path
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_merge_operator_list_with_no_helper_signal_returns_plain_list():
    """When operator passes selectedDossiers as a flat list AND helper has
    no rejected/rationale to report, the merge stays in the simple list form.
    The site-plan schema accepts both shapes via oneOf.
    """
    operator = ["interactive-game-loop"]
    helper_payload = {
        "required": [],
        "recommended": ["interactive-game-loop"],
        "conditional": [],
    }
    merged = merge_operator_selected_with_helper(operator, helper_payload)
    assert merged == ["interactive-game-loop"]


@pytest.mark.tooling
def test_merge_operator_list_with_helper_gap_promotes_to_object_form():
    """When operator passes selectedDossiers as a list but the helper has
    a rejected[] gap report, the merge MUST upgrade to object form so the
    gap survives. Dropping it would silently erase the operator's view of
    which capabilities are still missing - exactly what Bug A guarded.
    """
    operator = ["interactive-game-loop"]
    helper_payload = {
        "required": [],
        "recommended": ["interactive-game-loop"],
        "conditional": [],
        "rationale": "Helper rationale",
        "rejected": [{"id": "payments", "reason": "No Dossier implemented yet."}],
    }
    merged = merge_operator_selected_with_helper(operator, helper_payload)
    assert isinstance(merged, dict), (
        "Helper-reported gaps require object-form selectedDossiers so the "
        "rejected[] survives. List form would silently drop the gap report."
    )
    assert merged["recommended"] == ["interactive-game-loop"]
    assert merged["rejected"] == [
        {"id": "payments", "reason": "No Dossier implemented yet."}
    ]
    assert merged["rationale"] == "Helper rationale"


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
    assert re.search(
        r"from packages\.generation\.planning import[\s\S]*produce_site_plan",
        source,
    ), (
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
    assert re.search(r"def\s+build_site_plan_mock\s*\(", build_source) is None, (
        "build_site_plan_mock was removed in Sprint 2B - reintroducing it "
        "reopens B19. Use packages.generation.planning.produce_site_plan instead."
    )
    assert re.search(
        r"site_plan\s*=\s*\{[\s\S]*?\"planSource\"\s*:\s*\"mock-pre-sprint-2b\"",
        dev_source,
    ) is None, (
        "The inline pre-Sprint-2B mock plan literal was removed in Sprint 2B. "
        "Plan construction must go through produce_site_plan."
    )


# ---------------------------------------------------------------------------
# B23 closure: build_plan_artefakts must revalidate the site plan AFTER
# the operator-merge step. produce_site_plan validates internally, but the
# subsequent merge_operator_selected_with_helper call mutates
# selectedDossiers, which means the post-merge plan is a NEW object that
# has not been schema-validated yet. Bug C tracked this gap.
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_b23_build_site_revalidates_site_plan_after_operator_merge():
    """If a future refactor removes the post-merge ``validate_site_plan(site_plan)``
    call from ``build_plan_artefakts``, this guard fails loudly. The
    validation must come AFTER the merge - validating the helper output
    before merging is not enough because the merge can introduce shapes
    that the schema rejects (or, worse, drop required fields).
    """
    source = (SCRIPTS_DIR / "build_site.py").read_text(encoding="utf-8")

    func_match = re.search(
        r"def\s+build_plan_artefakts\s*\([\s\S]*?(?=\ndef\s|\Z)",
        source,
    )
    assert func_match is not None, (
        "build_plan_artefakts function not found in scripts/build_site.py. "
        "If it was renamed, update this test to point at the new symbol."
    )
    body = func_match.group(0)

    merge_pos = body.find("merge_operator_selected_with_helper(")
    revalidate_pos = body.find("validate_site_plan(site_plan)")

    assert merge_pos != -1, (
        "build_plan_artefakts must call merge_operator_selected_with_helper "
        "to fold operator-selected dossiers into the helper output. Bug A "
        "tracked the regression where this merge was skipped."
    )
    assert revalidate_pos != -1, (
        "build_plan_artefakts must call validate_site_plan(site_plan) AFTER "
        "the merge. Bug C tracked the regression where the post-merge plan "
        "was written to disk without re-validation."
    )
    assert revalidate_pos > merge_pos, (
        "validate_site_plan(site_plan) must come AFTER "
        "merge_operator_selected_with_helper. If you reversed them, the "
        "validation runs against the pre-merge plan and the merge can "
        "smuggle in a payload that violates site-plan.schema.json."
    )


# ---------------------------------------------------------------------------
# B138 - brief.pageCount must be respected when emitting routePlan
# ---------------------------------------------------------------------------
#
# Operatörens explicita sidantal i fri-prompten ("2 sidor") fångades av
# briefModel som ``site_brief.pageCount`` men ignorerades sedan i
# ``produce_site_plan`` — route_plan emitterades alltid med scaffold-
# defaults oavsett. Verifierat i sköldpaddssoppa-runen.
# Fixen: ``_trim_route_plan`` skär ner route_plan till brief.pageCount
# med prioritetslistan (home + contact aldrig borta), minsta körbara
# set = 2 routes, och ``pageCountWarning`` emittas när trim eller
# minimum-klamp händer.


@pytest.mark.tooling
def test_page_count_2_trims_route_plan_to_home_and_contact(monkeypatch):
    """sköldpaddssoppa-case: pageCount=2 + local-service-business (4 defaults)
    → 2 routes (home + contact) + warning ``trimmed-to-brief-page-count``."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=2)
    result = produce_site_plan(brief, run_id="test-page-count-2")
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    route_plan = site_plan["routePlan"]
    assert len(route_plan) == 2, (
        f"pageCount=2 ska ge 2 routes, fick {len(route_plan)}: {route_plan}"
    )
    route_ids = {r["id"] for r in route_plan}
    assert route_ids == {"home", "contact"}, (
        f"pageCount=2 ska behålla home+contact, fick {route_ids}"
    )

    warning = site_plan.get("pageCountWarning")
    assert warning is not None, "pageCountWarning ska emittas när trim sker."
    assert warning["requestedPageCount"] == 2
    assert warning["scaffoldDefaultCount"] == 4
    assert warning["emittedRouteCount"] == 2
    assert warning["reason"] == "trimmed-to-brief-page-count"


@pytest.mark.tooling
def test_page_count_6_keeps_default_route_plan_without_warning(monkeypatch):
    """pageCount=6 > scaffold-defaults (4): ingen trim, ingen warning.

    Bekräftar att operatörens "stora siffror" inte uppfinner extra
    routes; vi har bara scaffoldens defaults att emittera.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=6)
    result = produce_site_plan(brief, run_id="test-page-count-6")
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    assert len(site_plan["routePlan"]) == 4, (
        "pageCount=6 ska behålla alla 4 scaffold-defaults oförändrat."
    )
    assert "pageCountWarning" not in site_plan, (
        "Ingen warning när pageCount >= scaffold-defaults."
    )


@pytest.mark.tooling
def test_page_count_1_clamps_to_minimum_with_below_minimum_warning(monkeypatch):
    """pageCount=1 är under körbart minimum (home+contact = 2). Klampas
    till 2 + emit warning ``below-minimum-keeping-default``."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=1)
    result = produce_site_plan(brief, run_id="test-page-count-1")
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    route_plan = site_plan["routePlan"]
    assert len(route_plan) == 2, (
        "pageCount=1 ska klampas till minsta körbara set (2 routes)."
    )
    route_ids = {r["id"] for r in route_plan}
    assert route_ids == {"home", "contact"}

    warning = site_plan.get("pageCountWarning")
    assert warning is not None
    assert warning["requestedPageCount"] == 1
    assert warning["emittedRouteCount"] == 2
    assert warning["reason"] == "below-minimum-keeping-default"


@pytest.mark.tooling
def test_page_count_null_keeps_default_route_plan_without_warning(monkeypatch):
    """pageCount=None (defaultläget): scaffold-defaults oförändrat,
    ingen warning. Garanterar att helpern inte är intrusive när briefen
    inte hade information om sidantal."""
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=None)
    result = produce_site_plan(brief, run_id="test-page-count-null")
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    assert len(site_plan["routePlan"]) == 4, (
        "pageCount=None ska inte röra route_plan alls."
    )
    assert "pageCountWarning" not in site_plan


@pytest.mark.tooling
def test_page_count_3_fills_middle_in_scaffold_default_order(monkeypatch):
    """pageCount=3: home + contact + 1 mitt-route i scaffold-defaultordning.

    Lokal-tjänsteföretagets default-ordning är home, services, about,
    contact. Vid trim till 3 ska services vinna mitt-platsen (kommer
    före about i defaultordningen).
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=3)
    result = produce_site_plan(brief, run_id="test-page-count-3")
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    route_plan = site_plan["routePlan"]
    assert len(route_plan) == 3
    ids_in_order = [r["id"] for r in route_plan]
    assert ids_in_order == ["home", "services", "contact"], (
        f"pageCount=3 ska ge [home, services, contact] i den ordningen, "
        f"fick {ids_in_order}."
    )

    warning = site_plan["pageCountWarning"]
    assert warning["requestedPageCount"] == 3
    assert warning["emittedRouteCount"] == 3
    assert warning["reason"] == "trimmed-to-brief-page-count"


@pytest.mark.tooling
def test_page_count_trim_works_for_pinned_path(monkeypatch):
    """B138 ska gälla även pinned-flödet (build_site.py-vägen).

    ``build_plan_artefakts`` går alltid pinned-grenen eftersom operatören
    har valt scaffold+variant i Project Input. Trim-helpern måste
    fungera oavsett vilken plan-källa som vann.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=2)
    pinned = {
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
        "starterId": "marketing-base",
    }
    result = produce_site_plan(
        brief,
        run_id="test-page-count-pinned",
        pinned=pinned,
    )
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    assert result.source == "pinned"
    assert len(site_plan["routePlan"]) == 2
    warning = site_plan.get("pageCountWarning")
    assert warning is not None
    assert warning["reason"] == "trimmed-to-brief-page-count"


@pytest.mark.tooling
def test_page_count_out_of_range_does_not_trim(monkeypatch):
    """pageCount > 10 räknas inte som operatör-uttryck i fri prompt.

    Helpern lämnar route_plan orörd för pageCount utanför 1-10 så att
    framtida briefModel-buggar (t.ex. pageCount=42 från en LLM-
    halucination) inte kraschar trim-vägen.
    """
    monkeypatch.delenv(OPENAI_API_KEY_ENV, raising=False)
    brief = _baseline_brief(pageCount=42)
    result = produce_site_plan(brief, run_id="test-page-count-oor")
    site_plan = result.site_plan
    validate_site_plan(site_plan)

    assert len(site_plan["routePlan"]) == 4
    assert "pageCountWarning" not in site_plan
