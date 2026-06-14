"""Spår A: restyle landar via tema-utföraren (utbruten ur test_followup_chain_cli.py).

Ämnesfokuserad split ur ``test_followup_chain_cli.py`` (test-hygienens
1200-radstak, tests/test_test_hygiene.py): restyle-landnings- och
tema-fallback-bevisen för ``run_followup_chain`` -

- en vag restyle ("gör om så sajten får mer färger") som missar den
  deterministiska färg-/vibe-lexikonen landar nu via stylist-LLM-fallbacken
  (inkopplad i kedjan bakom den delade eligibilitetsgrinden),
- SAMMA vaga restyle UTAN ett användbart modellresultat förblir en ärlig
  no-op (PR #313:s no-false-success-kontrakt; ÄNDRING 3: effekter förblir
  oapplicerade), och
- stylist-eligibilitetsgrinden är en enda delad sanning (lockstep med den
  äldre prompt-vägen).

Delar helpers (``_seed_init_build`` m.fl.) med tests/test_followup_chain_cli.py
i stället för att duplicera dem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.test_followup_chain_cli import SITE_ID, _seed_init_build  # noqa: E402

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core


def test_followup_chain_vague_restyle_lands_via_llm_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Spår A (the real "land it" fix): the operator's exact vague restyle ("gör
    om så sajten får mer färger") misses the deterministic colour/vibe lexicon,
    but the stylist LLM fallback - NOW wired into run_followup_chain behind the
    shared eligibility gate - interprets it into a validated theme directive that
    apply routes onto the next immutable version (the SAME apply path the
    deterministic restyle uses). Proven with the styleDirectiveModel seam stubbed
    so no network/key is needed; the directive-kind signal contains "theme"."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Stub the stylist model seam to return a validatable palette + vibe.
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_style_directive_llm",
        lambda *a, **k: {"primaryColorHex": "#7c3aed", "toneVibe": "playful"},
    )
    from scripts.build_site import run_followup_chain
    from scripts.prompt_to_project_input import (
        compute_applied_followup_directive_kinds,
    )

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    # The pointer file is v1 at this point (the merge base for the follow-up).
    v1_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.project-input.json").read_text(encoding="utf-8")
    )

    result = run_followup_chain(
        SITE_ID,
        "gör om så sajten får mer färger",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built"
    assert result["applied"] is True
    assert result["editKind"] == "visual_style"
    assert result["version"] == 2

    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert v2_pi["brand"]["primaryColorHex"] == "#7c3aed"
    assert v2_pi["tone"]["primary"] == "playful"
    # The honest directive-kind signal for this version contains "theme".
    assert "theme" in compute_applied_followup_directive_kinds(v1_pi, v2_pi)


def test_followup_chain_vague_restyle_without_model_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Spår A honesty contract (PR #313): the SAME vague restyle WITHOUT a usable
    model result (no key, or the model declines) stays an honest no-op - the
    stylist fallback returns None, so the deterministic-miss + is_restyle path
    writes NO new version and reports plan_empty (intent_not_executable
    territory). Never a false "Klart!". Also covers ÄNDRING 3: a restyle whose
    only un-landable part is effect-like is reported as un-applied, not applied."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # No usable model result (deterministic regardless of a keyed dev machine).
    monkeypatch.setattr(
        "packages.generation.brief.extract.extract_style_directive_llm",
        lambda *a, **k: None,
    )
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    runs_before = {d.name for d in runs_dir.iterdir() if d.is_dir()}

    result = run_followup_chain(
        SITE_ID,
        "gör om så sajten får mer färger",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False
    assert result["stage"] == "plan_empty"
    assert result["editKind"] == "visual_style"
    # No new version written and no new build run created (honest no-op).
    assert not (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()
    assert {d.name for d in runs_dir.iterdir() if d.is_dir()} == runs_before


def test_stylist_eligibility_gate_is_shared_one_truth() -> None:
    """Spår A: the stylist LLM eligibility gate is a SINGLE source of truth. The
    legacy prompt path (scripts.prompt_to_project_input) re-exports the shared
    packages.generation.followup.theme_directives.theme_directive_llm_eligible
    verbatim, and the OpenClaw chain (scripts.build_site.run_followup_chain)
    imports the SAME shared symbol - so the gate can never drift between paths
    (same lockstep posture as _ANSWER_ONLY_CONVERSATION_KINDS)."""
    from packages.generation.followup.theme_directives import (
        theme_directive_llm_eligible,
    )
    from scripts.prompt_to_project_input import _theme_directive_llm_eligible

    # Identity, not a copy: legacy is the shared gate.
    assert _theme_directive_llm_eligible is theme_directive_llm_eligible
    # Source-lock: the chain wires in the SHARED gate + the LLM fallback (a
    # refactor must not silently fork a second gate into run_followup_chain).
    build_site_src = (REPO_ROOT / "scripts" / "build_site.py").read_text(
        encoding="utf-8"
    )
    assert "theme_directive_llm_eligible" in build_site_src
    assert "extract_theme_directive_via_llm" in build_site_src
