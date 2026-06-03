"""kor-5: tests for the repairModel blueprint-only repair pass.

Locks the public contract of:

- ``packages/generation/repair/blueprint_repair.py``
  (``apply_blueprint_repairs`` + grounding guard + rails + no-key/invalid
  contract + bounded loop + trace)
- ``packages/generation/repair/model_resolver.py`` (``resolve_repair_model``)
- ``execute_phase3_quality_and_repair`` blueprint integration
- parity of the in-code blueprint-repair policy loader with
  ``governance/policies/fix-registry.v1.json:blueprintRepair``.

Every filesystem mutation stays under ``tmp_path``. The repairModel call is
stubbed (``model_call=...`` / monkeypatched module symbol) so the matrix runs
without a real OpenAI key; tests that exercise the *apply* path set a dummy
``OPENAI_API_KEY`` so ``has_openai_api_key()`` is True while no real network call
is ever made.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.artifacts import validate_repair_result
from packages.generation.quality_gate import run_deterministic_critic
from packages.generation.repair import (
    RepairResult,
    apply_blueprint_repairs,
    execute_phase3_quality_and_repair,
    resolve_repair_model,
)
from packages.generation.repair.blueprint_repair import (
    HeroCopyPatch,
    OfferItemPatch,
    OfferListPatch,
)
from packages.generation.repair.orchestration import _blueprint_repair_policy

REPO_ROOT = Path(__file__).resolve().parents[1]
FIX_REGISTRY = REPO_ROOT / "governance" / "policies" / "fix-registry.v1.json"

_TRIGGER = frozenset({"generic_copy", "thin_offer", "missing_cta"})


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _gen_pkg(content_blocks: dict) -> dict:
    """A schema-complete Generation Package carrying ``content_blocks``.

    Schema-complete because the repair pass revalidates the WHOLE patched
    package against generation-package.schema.json before keeping a patch.
    """
    return {
        "runId": "kor5-test",
        "policyVersions": {"engineRun": "engine-run.v1"},
        "siteBriefRef": "site-brief.json",
        "sitePlanRef": "site-plan.json",
        "scaffoldId": "local-service-business",
        "variantId": "trygg-lokal",
        "starterId": "marketing-base",
        "language": "sv",
        "engineMode": "init",
        "createdAt": "2026-06-03T00:00:00Z",
        "contentBlocks": content_blocks,
    }


def _brief(**overrides) -> dict:
    """A grounded Site Brief slice (the repair never schema-validates this)."""
    brief = {
        "language": "sv",
        "businessTypeGuess": "electrician",
        "locationHint": "Malmö",
        "businessFacts": {
            "facts": ["elektriker", "verksam i Malmö"],
            "unknowns": ["telefonnummer"],
        },
        "positioning": {
            "oneLiner": "Trygg elektriker i Malmö när elen måste bli rätt.",
            "differentiator": "lokal och rak kommunikation utan krångliga offerter",
        },
        "servicesMentioned": ["elinstallation", "felsökning", "laddbox"],
        "conversion": {"primaryCta": "Be om offert"},
    }
    brief.update(overrides)
    return brief


def _grounded_hero_stub(issue, gp, brief):
    """repairModel stub: grounded, non-generic hero copy."""
    return HeroCopyPatch(
        headline="Erfaren elektriker i Malmö för trygg elservice"
    )


def _grounded_offer_stub(issue, gp, brief):
    """repairModel stub: 3 grounded offer items."""
    return OfferListPatch(
        items=[
            OfferItemPatch(title="Elinstallation", summary="Säkra installationer för hem och företag."),
            OfferItemPatch(title="Felsökning", summary="Snabb felsökning när något slutar fungera."),
            OfferItemPatch(title="Laddbox", summary="Installation av laddbox för elbil."),
        ]
    )


def _dispatch_stub(issue, gp, brief):
    """Route to the right grounded stub by issue type."""
    if issue.type == "thin_offer":
        return _grounded_offer_stub(issue, gp, brief)
    if issue.type == "missing_cta":
        return HeroCopyPatch(primaryCta="Be om offert")
    return _grounded_hero_stub(issue, gp, brief)


def _critic(gp, brief):
    return run_deterministic_critic(generation_package=gp, site_brief=brief)


# ---------------------------------------------------------------------------
# resolver
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_resolve_repair_model_returns_registered_model():
    assert resolve_repair_model() == "gpt-5.4"


# ---------------------------------------------------------------------------
# 1. generic_copy repaired
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generic_copy_repaired_via_hero_patch(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()  # conversion.primaryCta set -> no missing_cta noise

    critic = _critic(gp, brief)
    assert any(i.type == "generic_copy" for i in critic.issues)

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=critic,
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )

    assert outcome.status == "fixed"
    assert outcome.passes == 1
    applied = [r for r in outcome.repairs if r.success]
    assert len(applied) == 1
    entry = applied[0]
    assert entry.issueType == "generic_copy"
    assert entry.field == "contentBlocks.home.hero.headline"
    assert entry.before == "Välkommen till vår hemsida"
    assert entry.after == "Erfaren elektriker i Malmö för trygg elservice"
    # Originals untouched (deep-copied internally).
    assert gp["contentBlocks"]["home.hero"]["headline"] == "Välkommen till vår hemsida"
    # Post-repair critic has no generic_copy.
    assert outcome.final_critic is not None
    assert not any(i.type == "generic_copy" for i in outcome.final_critic.issues)


# ---------------------------------------------------------------------------
# 2. thin_offer repaired
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_thin_offer_repaired_via_offer_patch(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg(
        {"home.service-list": [{"title": "Elinstallation", "summary": "..."}]}
    )
    brief = _brief()

    critic = _critic(gp, brief)
    assert any(i.type == "thin_offer" for i in critic.issues)

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=critic,
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )

    assert outcome.status == "fixed"
    assert outcome.passes == 1
    applied = [r for r in outcome.repairs if r.success]
    assert len(applied) == 1 and applied[0].issueType == "thin_offer"
    patched_offer = outcome.patched_generation_package["contentBlocks"]["home.service-list"]
    assert len(patched_offer) == 3
    assert not any(i.type == "thin_offer" for i in outcome.final_critic.issues)
    # Original 1-item list untouched.
    assert len(gp["contentBlocks"]["home.service-list"]) == 1


# ---------------------------------------------------------------------------
# 3. grounding guard rejects ungrounded proposal during a real run
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_grounding_guard_rejects_ungrounded_number(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    def ungrounded(issue, g, b):
        return HeroCopyPatch(headline="Elektriker med 25 års erfarenhet i Malmö")

    critic = _critic(gp, brief)
    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=critic,
        trigger_types=_TRIGGER, max_passes=1, model_call=ungrounded,
    )

    assert outcome.status == "no-fix-applied"
    assert outcome.passes == 0
    assert outcome.repairs and all(not r.success for r in outcome.repairs)
    assert "ungrounded number" in outcome.repairs[0].detail
    # generic_copy still present (nothing applied).
    assert any(i.type == "generic_copy" for i in critic.issues)


@pytest.mark.tooling
def test_grounding_guard_rejects_ungrounded_place(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    def ungrounded(issue, g, b):
        # "Stockholm" is a proper noun not present anywhere in the grounding.
        return HeroCopyPatch(headline="Erfaren elektriker nära dig i Stockholm")

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, model_call=ungrounded,
    )
    assert outcome.status == "no-fix-applied"
    assert outcome.repairs and not outcome.repairs[0].success
    assert "ungrounded proper noun" in outcome.repairs[0].detail


# ---------------------------------------------------------------------------
# 4. rails: never create an unknown address
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_thin_offer_rejected_when_target_not_existing_offer_block(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # An offer-list block exists at home.service-list, but we simulate a stray
    # critic issue whose target is a NON-existent address; the handler must
    # refuse to create it.
    gp = _gen_pkg({"home.service-list": [{"title": "x", "summary": "y"}]})
    brief = _brief()
    from packages.generation.quality_gate import CriticIssue, CriticResult

    bad_issue = CriticIssue(
        severity="medium", type="thin_offer", target="ghost.service-list",
        message="thin", repairHint="hint",
    )
    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief,
        critic=CriticResult(score=80, issues=[bad_issue]),
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )
    assert outcome.status == "no-fix-applied"
    assert outcome.repairs and not outcome.repairs[0].success
    assert "not an existing offer-list block" in outcome.repairs[0].detail
    assert "ghost.service-list" not in gp["contentBlocks"]


# ---------------------------------------------------------------------------
# 5. bounded passes (no infinite loop)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_bounded_passes_stops_even_when_issue_persists(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    def persistent(issue, g, b):
        # Grounded, but STILL a generic phrase -> critic keeps flagging it.
        return HeroCopyPatch(headline="Vi sätter kunden i fokus i Malmö")

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, model_call=persistent,
    )
    # Applied once, issue remains -> partial-fix, passes capped at 1.
    assert outcome.status == "partial-fix"
    assert outcome.passes == 1
    assert any(r.success for r in outcome.repairs)
    assert any(i.type == "generic_copy" for i in outcome.final_critic.issues)


# ---------------------------------------------------------------------------
# 6. mock / no key -> no-fix-applied, skipped (DoD)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_no_key_skips_without_synthetic_failures(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )

    assert outcome.status == "no-fix-applied"
    assert outcome.passes == 0
    assert outcome.repairs == []  # NO synthetic success=False for a missing key
    assert outcome.skipped is True
    assert outcome.skipped_reason == "no-openai-api-key"


# ---------------------------------------------------------------------------
# 6b. model unavailable mid-run -> skip semantics
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_model_unavailable_midrun_is_skip_not_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    def unavailable(issue, g, b):
        return None  # simulate LLM error / no structured output

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, model_call=unavailable,
    )
    assert outcome.status == "no-fix-applied"
    assert outcome.passes == 0
    assert outcome.repairs == []  # skip, not a success=False entry
    assert outcome.skipped is True
    assert outcome.skipped_reason == "model-unavailable"


# ---------------------------------------------------------------------------
# 7. no eligible issue -> not-needed
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_no_eligible_issue_is_not_needed(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # Clean hero (grounded headline + CTA) + a 3-item offer -> no trigger issue.
    gp = _gen_pkg(
        {
            "home.hero": {
                "headline": "Erfaren elektriker i Malmö",
                "primaryCta": "Be om offert",
            },
            "home.service-list": [
                {"title": "Elinstallation", "summary": "Säkra installationer."},
                {"title": "Felsökning", "summary": "Snabb felsökning."},
                {"title": "Laddbox", "summary": "Installation av laddbox."},
            ],
        }
    )
    brief = _brief()
    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )
    assert outcome.status == "not-needed"
    assert outcome.passes == 0
    assert outcome.repairs == []
    assert outcome.skipped is False


# ---------------------------------------------------------------------------
# 8. no free files written (rerender=None leaves target_dir untouched)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_blueprint_repair_writes_no_free_files(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    target = tmp_path / "target"
    target.mkdir()
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, target_dir=target,
        rerender=None, model_call=_dispatch_stub,
    )
    assert outcome.status == "fixed"
    # The repair pass itself never touches the filesystem; only an injected
    # rerender callback may. With rerender=None the target dir stays empty.
    assert list(target.iterdir()) == []


@pytest.mark.tooling
def test_rerender_callback_invoked_on_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()
    calls: list[tuple[dict, dict]] = []

    def spy(patched_gp, patched_brief):
        calls.append((patched_gp, patched_brief))

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, rerender=spy,
        model_call=_dispatch_stub,
    )
    assert outcome.status == "fixed"
    assert len(calls) == 1
    # The renderer received the PATCHED blueprint, not the original.
    assert (
        calls[0][0]["contentBlocks"]["home.hero"]["headline"]
        == "Erfaren elektriker i Malmö för trygg elservice"
    )


# ---------------------------------------------------------------------------
# 9. execute_phase3 integration (central gate)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_execute_phase3_runs_blueprint_repair(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # Monkeypatch the module-level repairModel call (execute_phase3 does not
    # forward a model_call), returning a grounded patch.
    import packages.generation.repair.blueprint_repair as bp

    monkeypatch.setattr(bp, "run_repair_model", _dispatch_stub)

    target = tmp_path / "target"
    (target / "app").mkdir(parents=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    rerender_calls: list = []

    def spy(patched_gp, patched_brief):
        rerender_calls.append(patched_gp)

    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=target,
        required_routes=[],
        npm_steps=[],
        build_status="ok",
        do_typecheck=False,
        generation_package=gp,
        site_brief=brief,
        run_dir=run_dir,
        run_id="kor5-int",
        rerender=spy,
    )

    assert isinstance(repair_result, RepairResult)
    assert repair_result.blueprintPasses == 1
    assert any(r.success for r in repair_result.blueprintRepairs)
    assert len(rerender_calls) == 1
    # repair-result.json payload validates against the schema.
    validate_repair_result(repair_result.model_dump())
    # Final critic surfaced on quality result has no generic_copy.
    assert final_quality.critic is not None
    assert not any(i.type == "generic_copy" for i in final_quality.critic.issues)
    # trace.ndjson carries a repair.blueprint_patched event.
    trace = (run_dir / "trace.ndjson").read_text(encoding="utf-8")
    assert "repair.blueprint_patched" in trace


@pytest.mark.tooling
def test_execute_phase3_no_key_emits_blueprint_skipped_trace(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target = tmp_path / "target"
    (target / "app").mkdir(parents=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    # A rerender callback is required to reach the blueprint-repair pass; with no
    # key the pass itself short-circuits to skipped (no synthetic failures).
    _, repair_result = execute_phase3_quality_and_repair(
        target_dir=target, required_routes=[], npm_steps=[],
        build_status="ok", do_typecheck=False,
        generation_package=gp, site_brief=brief,
        run_dir=run_dir, run_id="kor5-nokey",
        rerender=lambda patched_gp, patched_brief: None,
    )
    assert repair_result.status == "no-fix-applied"
    assert repair_result.blueprintPasses == 0
    assert repair_result.blueprintRepairs == []
    trace = (run_dir / "trace.ndjson").read_text(encoding="utf-8")
    assert "repair.blueprint_skipped" in trace


@pytest.mark.tooling
def test_execute_phase3_blueprint_dormant_without_rerender(tmp_path, monkeypatch):
    """Blueprint-repair is rerender-gated: build_site passes the blueprint for
    the kor-4a critic (#186) but no rerender, so the pass stays dormant and
    never claims an improvement it cannot materialise."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    import packages.generation.repair.blueprint_repair as bp

    monkeypatch.setattr(bp, "run_repair_model", _dispatch_stub)
    target = tmp_path / "target"
    (target / "app").mkdir(parents=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})

    _, repair_result = execute_phase3_quality_and_repair(
        target_dir=target, required_routes=[], npm_steps=[],
        build_status="ok", do_typecheck=False,
        generation_package=gp, site_brief=_brief(),
        run_dir=run_dir, run_id="kor5-dormant",
        # rerender omitted -> dormant
    )
    assert repair_result.blueprintRepairs == []
    assert repair_result.blueprintPasses == 0
    trace = (run_dir / "trace.ndjson").read_text(encoding="utf-8")
    assert "repair.blueprint_patched" not in trace
    assert "repair.blueprint_skipped" not in trace


# ---------------------------------------------------------------------------
# 10. backward compatibility (no blueprint params -> mechanical-only, no critic)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_execute_phase3_without_blueprint_is_unchanged(tmp_path):
    """Without generation_package the gate behaves exactly as before kor-5:
    critic=None, no blueprint fields populated."""
    page = tmp_path / "app" / "page.tsx"
    page.parent.mkdir(parents=True)
    page.write_text(
        "export default function Page() { return <div>x</div>; }\n",
        encoding="utf-8",
    )
    final_quality, repair_result = execute_phase3_quality_and_repair(
        target_dir=tmp_path, required_routes=["/"], npm_steps=[],
        build_status="ok", do_typecheck=False,
    )
    assert final_quality.critic is None
    assert repair_result.blueprintRepairs == []
    assert repair_result.blueprintPasses == 0


# ---------------------------------------------------------------------------
# 12. contract: only rewrite EXISTING hero fields (never create new keys)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generic_copy_never_creates_new_hero_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    # Hero has ONLY a headline; the model also proposes a proofLine.
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    def stub(issue, g, b):
        return HeroCopyPatch(
            headline="Erfaren elektriker i Malmö",
            proofLine="Snabb och trygg elservice",  # key absent -> must be ignored
        )

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, model_call=stub,
    )
    patched_hero = outcome.patched_generation_package["contentBlocks"]["home.hero"]
    assert "proofLine" not in patched_hero  # contract: no new key created
    assert patched_hero["headline"] == "Erfaren elektriker i Malmö"
    # Only the existing headline produced a success entry.
    successes = [r for r in outcome.repairs if r.success]
    assert len(successes) == 1 and successes[0].field.endswith(".headline")


# ---------------------------------------------------------------------------
# 13. missing_cta via the EXISTING conversion group only
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_missing_cta_fills_existing_conversion_group(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Trygg elektriker i Malmö"}})
    # conversion EXISTS but carries no CTA -> missing_cta fires; repair fills it.
    brief = _brief(conversion={})

    critic = _critic(gp, brief)
    assert any(i.type == "missing_cta" for i in critic.issues)

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=critic,
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )
    assert outcome.status == "fixed"
    applied = [r for r in outcome.repairs if r.success]
    assert len(applied) == 1 and applied[0].field == "conversion.primaryCta"
    assert outcome.patched_site_brief["conversion"]["primaryCta"] == "Be om offert"
    assert not any(i.type == "missing_cta" for i in outcome.final_critic.issues)


@pytest.mark.tooling
def test_missing_cta_does_not_invent_conversion_group(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Trygg elektriker i Malmö"}})
    # No conversion group at all -> repair must NOT invent it.
    brief = _brief()
    del brief["conversion"]

    critic = _critic(gp, brief)
    assert any(i.type == "missing_cta" for i in critic.issues)

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=critic,
        trigger_types=_TRIGGER, max_passes=1, model_call=_dispatch_stub,
    )
    assert outcome.status == "no-fix-applied"
    assert outcome.repairs and not outcome.repairs[0].success
    assert "will not invent one" in outcome.repairs[0].detail
    # No conversion group was created.
    assert outcome.patched_site_brief is None


# ---------------------------------------------------------------------------
# 14. rerender failure never crashes; honest downgrade
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_rerender_failure_is_non_blocking_downgrade(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    gp = _gen_pkg({"home.hero": {"headline": "Välkommen till vår hemsida"}})
    brief = _brief()

    def boom(patched_gp, patched_brief):
        raise RuntimeError("renderer exploded")

    outcome = apply_blueprint_repairs(
        generation_package=gp, site_brief=brief, critic=_critic(gp, brief),
        trigger_types=_TRIGGER, max_passes=1, rerender=boom,
        model_call=_dispatch_stub,
    )
    # Never raised; downgraded to partial-fix with the render error recorded.
    assert outcome.status == "partial-fix"
    assert "RuntimeError" in outcome.rerender_error
    # Patched artefakts/critic are NOT surfaced (the site was not updated).
    assert outcome.patched_generation_package is None
    assert outcome.final_critic is None


# ---------------------------------------------------------------------------
# 11. policy parity
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_blueprint_repair_policy_matches_registry():
    registry = json.loads(FIX_REGISTRY.read_text(encoding="utf-8"))
    block = registry["blueprintRepair"]
    max_passes, trigger_types = _blueprint_repair_policy.__wrapped__()
    assert max_passes == block["maxPasses"]
    assert trigger_types == frozenset(block["triggerIssueTypes"])
    assert block["modelRole"] == "repairModel"
