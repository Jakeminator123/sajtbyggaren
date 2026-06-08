"""Minimal end-to-end test for the kor-7 CLI follow-up chain + critic wiring.

This is the integration-gap proof for the heavy-LLM follow-up bridge: it shows
that a single follow-up prompt, run through the *real* user path
(``run_followup_chain`` / ``scripts/build_site.py --followup``), drives the whole
capability chain end-to-end:

    prompt -> init build -> capability-backed follow-up prompt
    -> router -> context -> patch plan -> apply (new immutable v2)
    -> targeted render -> honest appliedVisibleEffect

and that the kor-4a deterministic critic is now actually filled in
``quality-result.json`` on a real build (it was always ``None`` before the
gate-wiring fix because the build path never passed the blueprint).

Mock-safe: ``OPENAI_API_KEY`` is removed so brief/plan fall back to the mock and
the router/context/patch/apply modules (all deterministic) never call an LLM.
The build runs with ``do_build=False`` (no npm), exactly like
``tests/test_targeted_render.py``'s real-chain test, so the suite stays Node-free.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"
INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö"
# A capability-backed follow-up: "add a contact form in the last section".
# "sista sektionen" resolves via the assembled routeSections to a concrete
# section, and contact_form maps to the contact-form capability (has a dossier),
# so the planner emits a valid named-field patch.
CAPABILITY_FOLLOWUP = "lägg till ett kontaktformulär i sista sektionen"


def _seed_init_build(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """Generate v1 for the baseline prompt and run one init build (no npm).

    Returns (prompt_inputs, runs_dir, generated_dir, base_run_id).
    """
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


def _critic_of(run_dir: Path) -> dict | None:
    payload = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))
    return payload.get("critic")


def test_init_build_fills_critic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Gate-wiring: a real build now fills quality-result.json:critic (was None)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _pin, runs_dir, _gen, base_run_id = _seed_init_build(tmp_path)

    critic = _critic_of(runs_dir / base_run_id)
    assert critic is not None, "critic must be filled in a real build (kor-4a wiring)"
    assert critic["source"] == "deterministic-v0"
    assert isinstance(critic["score"], int)
    assert 0 <= critic["score"] <= 100

    # The critic is a non-blocking warning lane: it logs exactly one event and
    # never changes the gate status aggregation.
    events = [
        json.loads(line)
        for line in (runs_dir / base_run_id / "trace.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    critic_events = [e for e in events if e.get("event") == "critic.evaluated"]
    assert len(critic_events) == 1
    assert critic_events[0]["status"] == "warning"


def test_followup_chain_applies_capability_and_creates_new_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A capability follow-up goes router->context->patch->apply->targeted build."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(tmp_path)
    v1_run_before = sorted((runs_dir / base_run_id).rglob("*"))
    v1_hashes = {
        str(p.relative_to(runs_dir / base_run_id)): p.read_bytes()
        for p in v1_run_before
        if p.is_file()
    }

    result = run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    # Chain ran all the way to the targeted build.
    assert result["stage"] == "built"
    assert result["applied"] is True
    assert result["messageKind"] == "edit_instruction"
    assert result["editKind"] == "component_add"

    # Apply created the next immutable version, identity preserved.
    assert result["version"] == 2
    assert result["previousVersion"] == 1
    assert result["appliedCapabilities"], "a capability was applied"
    assert result["appliedCapabilities"][0]["capability"] == "contact-form"
    v2_path = prompt_inputs / f"{SITE_ID}.v2.project-input.json"
    assert v2_path.exists()
    assert Path(result["projectInputPath"]) == v2_path

    v2_pi = json.loads(v2_path.read_text(encoding="utf-8"))
    assert "contact-form" in v2_pi.get("requestedCapabilities", [])

    # Targeted render produced an HONEST signal. do_build=False -> status
    # skipped -> no preview refresh, no false success (same contract as
    # test_targeted_render's real-chain test).
    assert result["affectedRoutes"] == ["home"]
    assert result["buildStatus"] == "skipped"
    assert result["outcome"] == "skipped"
    assert result["appliedVisibleEffect"] is False
    assert result["previewShouldRefresh"] is False

    # A distinct new run was created and the v1 run is byte-for-byte untouched.
    new_run = runs_dir / result["runId"]
    assert new_run.is_dir()
    assert result["runId"] != base_run_id
    for rel, raw in v1_hashes.items():
        assert (runs_dir / base_run_id / rel).read_bytes() == raw

    # The new version's build also fills the critic (gate-wiring on the v2 build).
    assert _critic_of(new_run) is not None


def test_followup_chain_restyle_applies_theme_and_creates_new_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A visual_style restyle goes router->(empty plan + theme)->apply->build.

    The router classifies "ändra färgen till rosa" as visual_style/edit_instruction;
    the patch planner has no capability patch, but the chain extracts an explicit
    theme directive and routes it through apply so brand.primaryColorHex lands in
    the next immutable version (rendered by patch_globals_css on rebuild)."""
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
    assert result["applied"] is True
    assert result["editKind"] == "visual_style"
    assert result["version"] == 2

    v2_path = prompt_inputs / f"{SITE_ID}.v2.project-input.json"
    assert v2_path.exists()
    v2_pi = json.loads(v2_path.read_text(encoding="utf-8"))
    assert v2_pi["brand"]["primaryColorHex"] == "#db2777"
    # No capability was applied (restyle is theme-only).
    assert result["appliedCapabilities"] == []


def test_followup_chain_capability_followup_does_not_restyle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gate: a non-visual_style edit never restyles. A component_add follow-up
    (no restyle intent) must leave brand untouched even if it mentioned a colour
    incidentally - the theme is applied only for a router visual_style intent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["editKind"] == "component_add"
    assert result["applied"] is True
    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    # The capability landed, but no brand restyle leaked in.
    assert "contact-form" in v2_pi.get("requestedCapabilities", [])
    assert "primaryColorHex" not in (v2_pi.get("brand") or {})


@pytest.mark.parametrize(
    "prompt,capability,dossier",
    [
        ("lägg till en sektion om garantier", "guarantees", "trust-guarantees"),
        ("lägg till en FAQ-sektion", "faq-section", "faq-accordion"),
        ("lägg till en team-sektion", "team-section", "team-roster"),
        ("lägg till en sektion med recensioner", "reviews", "reviews-display"),
    ],
)
def test_followup_chain_section_add_mounts_dossier_and_creates_new_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
    capability: str,
    dossier: str,
) -> None:
    """A sanctioned section_add goes router -> (section capability) -> apply ->
    targeted build: the capability lands in requestedCapabilities and its
    implementing dossier is secured in selectedDossiers.required (the SAME apply
    machinery component_add uses), creating the next immutable version."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        prompt,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["applied"] is True
    assert result["editKind"] == "section_add"
    assert result["version"] == 2
    applied = [c["capability"] for c in result["appliedCapabilities"]]
    assert capability in applied

    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert capability in v2_pi.get("requestedCapabilities", [])
    required = (v2_pi.get("selectedDossiers") or {}).get("required") or []
    assert dossier in required, f"{dossier} must be mounted in selectedDossiers.required"

    # Honest signal with do_build=False (skipped, no false preview refresh) and
    # the section lands on the root/home route by default.
    assert result["affectedRoutes"] == ["home"]
    assert result["appliedVisibleEffect"] is False
    assert result["previewShouldRefresh"] is False


def test_followup_chain_section_add_unsupported_type_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unsupported/unknown section type is an HONEST no-op: section_add is
    classified, but no capability mounts, so no version is written and the stage
    explains why (never a faked section)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        "lägg till en sektion om färger",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False
    assert result["stage"] == "section_unsupported"
    assert result["editKind"] == "section_add"
    assert not (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()
    assert any("sektionstyp" in note.lower() for note in result["notes"])


def test_followup_question_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pure question never applies a patch, never creates a version, never builds."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    runs_before = {d.name for d in runs_dir.iterdir() if d.is_dir()}

    result = run_followup_chain(
        SITE_ID,
        "vad kostar en logga?",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False
    assert result["stage"] == "router_no_edit"
    assert not (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()
    # No new run created (no build happened).
    assert {d.name for d in runs_dir.iterdir() if d.is_dir()} == runs_before


def test_followup_without_prior_build_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A follow-up for a site with no prior run fails loud (nothing to build on)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    with pytest.raises(SystemExit, match="ingen tidigare run"):
        run_followup_chain(
            "nonexistent-site",
            CAPABILITY_FOLLOWUP,
            do_build=False,
            runs_dir=tmp_path / "runs",
            generated_dir=tmp_path / "gen",
            output_dir=tmp_path / "prompt-inputs",
        )


def test_cli_followup_entrypoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The argv CLI (--followup --site-id) drives the same chain and prints JSON."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import scripts.build_site as build_site

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    argv = [
        "build_site.py",
        "--followup",
        CAPABILITY_FOLLOWUP,
        "--site-id",
        SITE_ID,
        "--skip-build",
        "--runs-dir",
        str(runs_dir),
        "--generated-dir",
        str(generated_dir),
    ]
    # The CLI resolves prompt-inputs from PROMPT_INPUTS_DIR; point it at the
    # sandbox so the argv path is exercised without touching the repo's data/.
    monkeypatch.setattr(build_site, "PROMPT_INPUTS_DIR", prompt_inputs)
    monkeypatch.setattr(sys, "argv", argv)

    rc = build_site.main()
    assert rc == 0
    assert (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()


def test_followup_chain_routes_via_llm_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The chain classifies via classify_message_with_llm_fallback (KÖR-6b), not
    the bare KÖR-6a heuristic, so ambiguous/long follow-ups can escalate to
    routerModel when a key is present. Without a key it stays heuristic-identical;
    here we only assert the fallback entrypoint is the one invoked."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import packages.generation.orchestration.router as router_pkg
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    calls = {"n": 0}
    real = router_pkg.classify_message_with_llm_fallback

    def _spy(message, **kwargs):
        calls["n"] += 1
        return real(message, **kwargs)

    monkeypatch.setattr(router_pkg, "classify_message_with_llm_fallback", _spy)

    run_followup_chain(
        SITE_ID,
        "vad kostar en logga?",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert calls["n"] == 1, "follow-up chain must classify via the KÖR-6b fallback"


def test_followup_chain_forwards_base_run_id_to_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """run_followup_chain passes base_run_id through to apply_patch_plan so apply
    iterates from the same historical version the context was read from, instead
    of the rolling latest (kör-7 base-run consistency)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import packages.generation.orchestration.apply as apply_mod
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(tmp_path)

    captured: dict = {}
    real_apply = apply_mod.apply_patch_plan

    def _spy(plan, **kwargs):
        captured["base_run_id"] = kwargs.get("base_run_id")
        return real_apply(plan, **kwargs)

    monkeypatch.setattr(apply_mod, "apply_patch_plan", _spy)

    run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        base_run_id=base_run_id,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert captured["base_run_id"] == base_run_id


def test_followup_chain_is_mock_safe_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No OPENAI_API_KEY -> no crash, honest degrade through the whole chain."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert os.environ.get("OPENAI_API_KEY") is None
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    result = run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    # The mock path still applies the capability and creates v2 deterministically.
    assert result["applied"] is True
    assert result["version"] == 2
