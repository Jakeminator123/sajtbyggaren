"""Honest reporting of compound follow-up parts no executor applied (B155 follow-up).

The operator finding (2026-06-10, snickesnackarn): a compound follow-up where
only ONE part can execute (e.g. the stylist takes the colour) used to drop the
rest SILENTLY in the KÖR-7 capability chain - the operator saw "Klart! v1→v2"
and believed everything was done. These tests lock that the unowned /
unmaterialized parts are now reported through the EXISTING
``unappliedFollowupIntents`` channel (bounded ``{target, reason}``, already
consumed by FloatingChat from ``build-result.json``).

Two layers:
  1. unit tests for the pure observer
     ``compute_unapplied_followup_chain_intents`` (no I/O, crafted decisions);
  2. integration tests through the real ``run_followup_chain`` (mock-safe, no
     ``OPENAI_API_KEY``, ``do_build=False``) that prove the post reaches the v2
     meta sidecar + ``build-result.json`` + the honest trace event, while the
     applied part still reports its visible effect.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from packages.generation.orchestration.openclaw import (
    compute_unapplied_followup_chain_intents,
)
from packages.generation.orchestration.router.models import (
    RouterDecision,
    RouterSubtask,
    RouterTarget,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"
INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö"


# ---------------------------------------------------------------------------
# Unit: the pure observer
# ---------------------------------------------------------------------------


def _multi(*subtasks: RouterSubtask) -> RouterDecision:
    return RouterDecision(messageKind="multi_intent", subtasks=list(subtasks))


@pytest.mark.tooling
def test_helper_reports_unowned_remove_when_style_applied() -> None:
    """visual_style applied + an unowned component_remove -> ONE honest post."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör färgen mörkblå"),
        RouterSubtask(editKind="component_remove", instruction="ta bort kontaktformuläret"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=True,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert [p["target"] for p in posts] == ["borttagning"]
    assert "ta bort kontaktformuläret" in posts[0]["reason"]
    assert "ingen utförare" in posts[0]["reason"]


@pytest.mark.tooling
def test_helper_reports_each_unowned_kind_once() -> None:
    """component_remove + layout_change are both unowned -> two grouped posts."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör färgen mörkblå"),
        RouterSubtask(editKind="component_remove", instruction="ta bort kontaktformuläret"),
        RouterSubtask(editKind="layout_change", instruction="centrera hero"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=True,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert {p["target"] for p in posts} == {"borttagning", "layout"}


@pytest.mark.tooling
def test_helper_reports_unparseable_visual_style() -> None:
    """A visual_style whose directive produced nothing is reported (stylist no-op)."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör den coolare"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=False,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert [p["target"] for p in posts] == ["stil"]
    assert "färg" in posts[0]["reason"]


@pytest.mark.tooling
def test_helper_reports_unsupported_section_add() -> None:
    """A section_add whose type did not resolve to a mounted capability is reported."""
    decision = _multi(
        RouterSubtask(editKind="visual_style", instruction="gör färgen mörkblå"),
        RouterSubtask(editKind="section_add", componentIntent="colors", instruction="en sektion om färger"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=True,
        applied_section_capabilities=["faq-section"],  # the colors section is NOT here
        section_capability_for_intent={"faq": "faq-section"},
    )
    assert [p["target"] for p in posts] == ["sektion"]


@pytest.mark.tooling
def test_helper_section_add_covered_when_capability_mounted() -> None:
    """A section_add whose type resolved to a mounted capability is NOT reported."""
    decision = _multi(
        RouterSubtask(editKind="section_add", componentIntent="faq", instruction="en FAQ-sektion"),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=False,
        applied_section_capabilities=["faq-section"],
        section_capability_for_intent={"faq": "faq-section"},
    )
    assert posts == []


@pytest.mark.tooling
def test_helper_component_add_targetless_vs_targeted() -> None:
    """A component_add with no target section is reported; one with a target is not."""
    targetless = _multi(
        RouterSubtask(editKind="component_add", componentIntent="contact_form", instruction="lägg till kontaktformulär"),
    )
    posts = compute_unapplied_followup_chain_intents(
        targetless,
        theme_applied=False,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert [p["target"] for p in posts] == ["komponent"]

    targeted = _multi(
        RouterSubtask(
            editKind="component_add",
            componentIntent="contact_form",
            instruction="lägg till kontaktformulär i sista sektionen",
            target=RouterTarget(routeId="home", sectionOrdinal=-1),
        ),
    )
    assert (
        compute_unapplied_followup_chain_intents(
            targeted,
            theme_applied=False,
            applied_section_capabilities=[],
            section_capability_for_intent={},
        )
        == []
    )


@pytest.mark.tooling
def test_helper_all_covered_is_empty() -> None:
    """A clean single applied intent yields no posts (no false positives)."""
    decision = RouterDecision(messageKind="edit_instruction", editKind="visual_style")
    assert (
        compute_unapplied_followup_chain_intents(
            decision,
            theme_applied=True,
            applied_section_capabilities=[],
            section_capability_for_intent={},
        )
        == []
    )


@pytest.mark.tooling
def test_helper_bounds_target_and_reason() -> None:
    """Posts are bounded (target <= 80, reason <= 400) even for a long instruction."""
    decision = _multi(
        RouterSubtask(editKind="component_remove", instruction="x" * 1000),
    )
    posts = compute_unapplied_followup_chain_intents(
        decision,
        theme_applied=False,
        applied_section_capabilities=[],
        section_capability_for_intent={},
    )
    assert len(posts) == 1
    assert len(posts[0]["target"]) <= 80
    assert len(posts[0]["reason"]) <= 400


# ---------------------------------------------------------------------------
# Integration: through the real run_followup_chain
# ---------------------------------------------------------------------------


def _seed_init_build(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"

    _pi, _meta, v1_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    _target, run_dir = build(
        v1_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )
    return prompt_inputs, runs_dir, generated_dir, run_dir.name


def _trace_events(run_dir: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (run_dir / "trace.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.mark.tooling
def test_chain_compound_restyle_plus_unowned_remove_is_honest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The operator-finding repro end-to-end: the colour lands (visible effect)
    AND the unowned 'ta bort kontaktformuläret' is reported honestly instead of
    vanishing behind a 'Klart!' success."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        "gör färgen mörkblå och ta bort kontaktformuläret",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    # The applied part materialised: v2 written, blue brand colour applied.
    assert result["stage"] == "built"
    assert result["applied"] is True
    assert result["version"] == 2
    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert v2_pi["brand"]["primaryColorHex"] == "#1e3a8a"

    # The dropped part is reported on the chain result.
    targets = {p["target"] for p in result["unappliedFollowupIntents"]}
    assert "borttagning" in targets

    # ...and persisted on the v2 meta sidecar (apply wrote it after the scrub).
    v2_meta = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.meta.json").read_text(encoding="utf-8")
    )
    assert any(
        p["target"] == "borttagning" for p in v2_meta["unappliedFollowupIntents"]
    )

    # ...and surfaced in build-result.json via the EXISTING channel + trace event.
    new_run = runs_dir / result["runId"]
    build_result = json.loads(
        (new_run / "build-result.json").read_text(encoding="utf-8")
    )
    assert any(
        p["target"] == "borttagning"
        for p in build_result["unappliedFollowupIntents"]
    )
    # The applied effect is still honestly reported (both coexist).
    assert build_result["appliedVisibleEffect"] is True

    events = _trace_events(new_run)
    names = [e["event"] for e in events]
    assert "followup.unapplied_intents_detected" in names
    assert names.index("followup.unapplied_intents_detected") < names.index(
        "build.result.written"
    )
    assert events[names.index("followup.unapplied_intents_detected")]["status"] == "warning"


@pytest.mark.tooling
def test_chain_clean_restyle_has_no_unapplied_intents(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A clean single-intent restyle reports NO unapplied intents (no false
    positives) - the field is absent from build-result.json."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        "ändra färgen till rosa",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built"
    assert result["editKind"] == "visual_style"
    assert result["unappliedFollowupIntents"] == []

    v2_meta = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.meta.json").read_text(encoding="utf-8")
    )
    assert "unappliedFollowupIntents" not in v2_meta

    build_result = json.loads(
        (runs_dir / result["runId"] / "build-result.json").read_text(encoding="utf-8")
    )
    assert "unappliedFollowupIntents" not in build_result
    events = _trace_events(runs_dir / result["runId"])
    assert "followup.unapplied_intents_detected" not in [e["event"] for e in events]
