"""Fas 1 (beslutsenhet): run_followup_chain CONSUMES the conductor's decision.

Before Fas 1 a follow-up was classified TWICE per ``--apply`` invocation: the
OpenClaw bridge (``run_openclaw_followup._classify_router``) produced a
``RouterDecision``, and ``build_site.run_followup_chain`` re-classified the same
message internally. Two decision surfaces (they can disagree on ambiguous
prompts) and up to two routerModel calls.

Fas 1 makes the chain CONSUME an injected ``decision`` instead of
re-classifying. These tests prove the seam is BEHAVIOR-PRESERVING:

- PARITY: for a representative set of follow-ups (restyle, copy_change,
  section_add, route_remove, nav_hide, multi_intent, and an ORDINAL target),
  ``run_followup_chain(...)`` (internal classification) and
  ``run_followup_chain(..., decision=<conductor decision>)`` produce IDENTICAL
  results. The conductor decision is built EXACTLY as the bridge builds it -
  ``RouterContext(siteId=...)`` WITHOUT ``routeSections`` - so the parity proof
  also covers the routeSections nuance below.
- NUANCE: the conductor's ordinal target carries ``sectionOrdinal`` but a
  ``None`` ``sectionId`` (no routeSections); the chain re-resolves it to the
  IDENTICAL ``sectionId`` the internal classification produces.
- NO RE-CLASSIFICATION: with a decision injected the chain never calls
  ``classify_message_with_llm_fallback``.
- DEFAULT PATH UNCHANGED: with ``decision=None`` the chain still classifies and
  behaves as before.

Mock-safe: ``OPENAI_API_KEY`` is removed so the router is the deterministic
heuristic; builds run with ``do_build=False`` (no npm), like the other
follow-up E2Es (tests/test_followup_nav_hide.py / test_followup_route_remove.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SITE_ID = "painter-palma"

# The representative follow-up set the parity proof covers (one per executor
# path + a multi_intent + an ORDINAL-target prompt that exercises the
# routeSections nuance: "andra sektionen" -> the home route's 2nd section).
PARITY_PROMPTS = [
    "gör sajten blå",  # restyle (visual_style)
    "ändra rubriken till Välkommen hem",  # copy_change
    "lägg till en FAQ-sektion",  # section_add
    "ta bort sidan Om oss",  # route_remove
    "dölj Om oss i menyn",  # nav_hide
    "gör sajten blå och ta bort sidan Om oss",  # multi_intent
    "lägg en klocka i andra sektionen till vänster",  # ordinal target
]

# Result fields that MUST match between the internal-classification path and the
# injected-decision path. runId/projectInputPath/baseRunId/notes legitimately
# differ (timestamps, uuids, isolated tmp paths) and are excluded.
_COMPARABLE_KEYS = (
    "stage",
    "applied",
    "messageKind",
    "editKind",
    "affectedRoutes",
    "changedRoutes",
    "outcome",
    "buildStatus",
    "appliedVisibleEffect",
    "previewShouldRefresh",
    "version",
    "previousVersion",
    "unappliedFollowupIntents",
)


def _seed_painter_palma(base_dir: Path) -> tuple[Path, Path, Path]:
    """Init-build the LSB painter-palma example (no npm) into isolated dirs."""
    from scripts.build_site import build

    base_dir.mkdir(parents=True, exist_ok=True)
    prompt_inputs = base_dir / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = base_dir / "runs"
    generated_dir = base_dir / "gen"
    build(
        REPO_ROOT / "examples" / "painter-palma.project-input.json",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir


def _route_sections(runs_dir: Path, prompt_inputs: Path) -> dict[str, list[str]]:
    """Assemble the same routeSections map the chain builds from pre_ctx."""
    from packages.generation.orchestration.context import (
        ContextPaths,
        assemble_context,
    )

    run_ids = sorted(p.name for p in runs_dir.iterdir() if p.is_dir())
    assert run_ids, "expected at least one seeded run"
    paths = ContextPaths(runsDir=runs_dir, promptInputsDir=prompt_inputs)
    pre = assemble_context("artifacts_plus_sections", run_id=run_ids[-1], paths=paths)
    payload = pre.payload.get("routeSections") or {}
    return {
        route: [s for s in ids if isinstance(s, str)]
        for route, ids in payload.items()
        if isinstance(ids, list)
    }


def _comparable(result: dict) -> dict:
    return {key: result.get(key) for key in _COMPARABLE_KEYS}


@pytest.mark.parametrize("prompt", PARITY_PROMPTS)
def test_injected_decision_matches_internal_classification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, prompt: str
) -> None:
    """PARITY: the chain produces IDENTICAL results whether it classifies the
    message itself (decision=None) or consumes the conductor's decision."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain
    from scripts.run_openclaw_followup import _classify_router

    # Two byte-identical seeds: run_followup_chain mutates state (new version +
    # current.json swap), so the two paths must run on independent sites.
    pi_a, runs_a, gen_a = _seed_painter_palma(tmp_path / "internal")
    pi_b, runs_b, gen_b = _seed_painter_palma(tmp_path / "injected")

    internal = run_followup_chain(
        SITE_ID,
        prompt,
        do_build=False,
        runs_dir=runs_a,
        generated_dir=gen_a,
        output_dir=pi_a,
    )

    # Build the conductor decision EXACTLY as the bridge does: RouterContext with
    # siteId only, NO routeSections (so an ordinal target lacks the sectionId
    # resolution the internal classification produces). This is what proves the
    # nuance is handled - parity must hold despite the missing resolution.
    conductor_decision = _classify_router(prompt, site_id=SITE_ID)
    injected = run_followup_chain(
        SITE_ID,
        prompt,
        do_build=False,
        runs_dir=runs_b,
        generated_dir=gen_b,
        output_dir=pi_b,
        decision=conductor_decision,
    )

    assert _comparable(injected) == _comparable(internal), {
        "prompt": prompt,
        "internal": _comparable(internal),
        "injected": _comparable(injected),
    }


def test_injected_ordinal_decision_resolves_identical_section_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """NUANCE: the conductor's ordinal target has sectionOrdinal but no sectionId
    (no routeSections). The chain's section-resolution seam fills in the SAME
    sectionId the internal classification (with routeSections) would produce."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from packages.generation.orchestration.router import (
        RouterContext,
        classify_message_with_llm_fallback,
    )
    from scripts.build_site import _resolve_injected_decision_sections
    from scripts.run_openclaw_followup import _classify_router

    prompt = "lägg en klocka i andra sektionen till vänster"
    prompt_inputs, runs_dir, _gen = _seed_painter_palma(tmp_path)
    route_sections = _route_sections(runs_dir, prompt_inputs)

    # The conductor decision (no routeSections): ordinal known, sectionId unknown.
    conductor = _classify_router(prompt, site_id=SITE_ID)
    assert conductor.target is not None
    assert conductor.target.sectionOrdinal == 2
    assert conductor.target.sectionId is None

    # The chain's internal decision (with routeSections) resolves the sectionId.
    internal = classify_message_with_llm_fallback(
        prompt,
        context=RouterContext(siteId=SITE_ID, routeSections=route_sections),
    )
    assert internal.target is not None
    assert internal.target.sectionId is not None

    # The injected-decision section-resolution seam yields the IDENTICAL sectionId
    # without re-classifying, and never mutates the conductor's own decision.
    resolved = _resolve_injected_decision_sections(
        conductor,
        route_sections,
        default_route_id=RouterContext().defaultRouteId,
    )
    assert resolved.target is not None
    assert resolved.target.sectionId == internal.target.sectionId
    assert conductor.target.sectionId is None  # original untouched (deep copy)


def test_injected_decision_does_not_reclassify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """NO RE-CLASSIFICATION: with a decision injected the chain never calls the
    router classifier. Mirrors tests/test_openclaw_roles.py
    ::test_classify_conversation_accepts_injected_router.

    run_followup_chain imports classify_message_with_llm_fallback LOCALLY from
    the router PACKAGE (build_site keeps no module-level binding by design), so
    the effective patch target is the package attribute the local
    ``from ... import`` resolves at call time. Patching it to explode proves the
    DEFAULT path classifies (it raises) while the INJECTED path does not (no
    raise) - the strong, non-vacuous form of the proof.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import packages.generation.orchestration.router as router_pkg
    from scripts.build_site import run_followup_chain
    from scripts.run_openclaw_followup import _classify_router

    prompt = "gör sajten blå"
    conductor_decision = _classify_router(prompt, site_id=SITE_ID)

    def _explode(*_args: object, **_kwargs: object):  # pragma: no cover - raising IS the proof
        raise AssertionError(
            "run_followup_chain must NOT re-classify when a decision is injected"
        )

    monkeypatch.setattr(
        router_pkg, "classify_message_with_llm_fallback", _explode
    )

    # Injected decision -> the classifier is never reached.
    pi_inj, runs_inj, gen_inj = _seed_painter_palma(tmp_path / "injected")
    injected = run_followup_chain(
        SITE_ID,
        prompt,
        do_build=False,
        runs_dir=runs_inj,
        generated_dir=gen_inj,
        output_dir=pi_inj,
        decision=conductor_decision,
    )
    assert injected["stage"] == "built", injected
    assert injected["editKind"] == "visual_style", injected

    # Control: the DEFAULT path (decision=None) DOES classify, so the same patch
    # makes it raise - proving the patch is effective and the proof above is real.
    pi_def, runs_def, gen_def = _seed_painter_palma(tmp_path / "default")
    with pytest.raises(AssertionError):
        run_followup_chain(
            SITE_ID,
            prompt,
            do_build=False,
            runs_dir=runs_def,
            generated_dir=gen_def,
            output_dir=pi_def,
        )


def test_default_path_classifies_and_behaves_as_before(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """DEFAULT PATH UNCHANGED: with decision=None the chain classifies itself and
    a restyle still lands as v2 (byte-for-byte the pre-Fas-1 behaviour)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        "gör sajten blå",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["applied"] is True, result
    assert result["editKind"] == "visual_style", result
    assert result["version"] == 2, result
