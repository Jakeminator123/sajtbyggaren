"""Versioning *invariants* for the real follow-up chain (``run_followup_chain``).

These tests lock the core-loop promise that a follow-up
(``prompt -> företagshemsida -> preview -> följdprompt -> ny version``) only ever
*evolves* an existing project - it must NEVER silently restart the project from a
fresh init. They complement, and deliberately do not duplicate, the existing
coverage:

* ``tests/test_followup_versioning_regression.py`` pins the
  ``generate`` / ``generate_followup`` helper path (the prompt-sidecar metadata
  contract, up to v2).
* ``tests/test_glue1_project_input_persistence.py`` pins that a fresh build
  persists a discoverable sidecar so the *first* follow-up can run at all.

The gap covered here: the *whole* deterministic chain
(``init build -> run_followup_chain -> apply -> new immutable version``) driven
across **several** follow-ups (v1 -> v2 -> v3), asserting the invariants that
guard against a regression where a follow-up resets identity / selections /
version lineage.

Mock-safe and Node-free: ``OPENAI_API_KEY`` is removed so brief/plan fall back to
the deterministic mock and the router/context/patch/apply modules never call an
LLM; ``do_build=False`` keeps the suite off npm. All artefacts live under
``tmp_path``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"
INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö"

# A capability-backed additive follow-up (mounts the contact-form capability).
CAPABILITY_FOLLOWUP = "lägg till ett kontaktformulär i sista sektionen"
# A second additive follow-up that adds a visible FAQ section/route.
SECTION_FOLLOWUP = "lägg till en FAQ-sektion"
# An *unrelated* follow-up: a pure restyle. It must not mount any capability and
# must not reset the project to a fresh init.
RESTYLE_FOLLOWUP = "ändra färgen till rosa"

# Identity + prior-selection fields that an additive follow-up must carry forward
# untouched from the initial Project Input.
STABLE_IDENTITY_FIELDS = ("siteId", "scaffoldId", "variantId", "language", "contact")


def _seed_init_build(tmp_path: Path) -> tuple[dict, Path, Path, Path, str]:
    """Generate v1 for the baseline prompt and run one init build (no npm).

    Returns ``(v1_project_input, prompt_inputs, runs_dir, generated_dir,
    base_run_id)``.
    """
    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"

    v1_pi, _meta, v1_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    _target, run_dir = build(
        v1_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )
    return v1_pi, prompt_inputs, runs_dir, generated_dir, run_dir.name


def _followup(
    site_id: str,
    prompt: str,
    *,
    runs_dir: Path,
    generated_dir: Path,
    prompt_inputs: Path,
) -> dict:
    from scripts.build_site import run_followup_chain

    return run_followup_chain(
        site_id,
        prompt,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )


def _read_meta(prompt_inputs: Path, version: int) -> dict:
    return json.loads(
        (prompt_inputs / f"{SITE_ID}.v{version}.meta.json").read_text(encoding="utf-8")
    )


def _read_input(prompt_inputs: Path, version: int) -> dict:
    return json.loads(
        (prompt_inputs / f"{SITE_ID}.v{version}.project-input.json").read_text(
            encoding="utf-8"
        )
    )


def test_followup_chain_bumps_versions_v1_v2_v3_with_one_run_per_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """INVARIANT 2 + 3: two additive follow-ups produce a strict v1->v2->v3
    lineage, each with its own previousVersion and its own distinct run dir
    (never an in-place overwrite or a single rolling run)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _v1, prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(
        tmp_path
    )

    r2 = _followup(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs=prompt_inputs,
    )
    r3 = _followup(
        SITE_ID,
        SECTION_FOLLOWUP,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs=prompt_inputs,
    )

    # Each follow-up applied and bumped exactly one version.
    assert r2["applied"] is True and r3["applied"] is True
    assert r2["version"] == 2 and r2["previousVersion"] == 1
    assert r3["version"] == 3 and r3["previousVersion"] == 2

    # A new immutable version snapshot exists per version (init wrote v1).
    assert (prompt_inputs / f"{SITE_ID}.v1.project-input.json").is_file()
    assert (prompt_inputs / f"{SITE_ID}.v2.project-input.json").is_file()
    assert (prompt_inputs / f"{SITE_ID}.v3.project-input.json").is_file()

    # A distinct run dir per version: init + 2 follow-ups => 3 unique run dirs.
    run_ids = {base_run_id, r2["runId"], r3["runId"]}
    assert len(run_ids) == 3
    for run_id in run_ids:
        assert (runs_dir / run_id).is_dir()

    # The run's own input.json records the matching version + lineage.
    init_input = json.loads(
        (runs_dir / base_run_id / "input.json").read_text(encoding="utf-8")
    )
    v2_input = json.loads(
        (runs_dir / r2["runId"] / "input.json").read_text(encoding="utf-8")
    )
    v3_input = json.loads(
        (runs_dir / r3["runId"] / "input.json").read_text(encoding="utf-8")
    )
    assert init_input["version"] == 1
    assert v2_input["version"] == 2 and v2_input["previousVersion"] == 1
    assert v3_input["version"] == 3 and v3_input["previousVersion"] == 2


def test_followup_chain_preserves_project_id_across_every_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """INVARIANT 1: the projectId is the stable spine of the whole lineage - the
    init build and every follow-up version (sidecar meta + run input.json) keep
    the exact same projectId. A regression that re-inits would mint a new id."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _v1, prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(
        tmp_path
    )

    r2 = _followup(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs=prompt_inputs,
    )
    r3 = _followup(
        SITE_ID,
        SECTION_FOLLOWUP,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs=prompt_inputs,
    )

    # Sidecar meta keeps the same projectId on v1, v2, v3.
    assert _read_meta(prompt_inputs, 1)["projectId"] == PROJECT_ID
    assert _read_meta(prompt_inputs, 2)["projectId"] == PROJECT_ID
    assert _read_meta(prompt_inputs, 3)["projectId"] == PROJECT_ID

    # And the run input.json snapshots agree (same id flows into each build).
    for run_id in (base_run_id, r2["runId"], r3["runId"]):
        run_input = json.loads(
            (runs_dir / run_id / "input.json").read_text(encoding="utf-8")
        )
        assert run_input["projectId"] == PROJECT_ID


def test_additive_followup_carries_forward_prior_selections_and_brief(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """INVARIANT 4: an additive follow-up evolves on top of the prior version -
    the prior identity/selection (scaffoldId, variantId, language, siteId,
    contact) carries forward unchanged, the brief-derived company DNA is kept,
    and the new capability is *appended* to the prior requestedCapabilities
    (never replacing them)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v1_pi, prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    v1_caps = list(v1_pi.get("requestedCapabilities", []))

    r2 = _followup(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs=prompt_inputs,
    )
    assert r2["applied"] is True
    assert r2["appliedCapabilities"], "the additive follow-up mounted a capability"
    assert r2["appliedCapabilities"][0]["capability"] == "contact-form"

    v2_pi = _read_input(prompt_inputs, 2)

    # Stable identity + prior selections carry forward untouched.
    for field in STABLE_IDENTITY_FIELDS:
        assert v2_pi[field] == v1_pi[field], field

    # Brief-derived company DNA is preserved (no re-brief / re-init).
    assert v2_pi["company"]["businessType"] == v1_pi["company"]["businessType"]
    assert v2_pi["company"]["story"] == v1_pi["company"]["story"]
    assert v2_pi["company"]["tagline"] == v1_pi["company"]["tagline"]

    # The new capability is appended on top of (a superset of) the prior set.
    v2_caps = v2_pi.get("requestedCapabilities", [])
    assert "contact-form" in v2_caps
    assert set(v1_caps).issubset(set(v2_caps)), (
        "an additive follow-up must keep prior capabilities, not replace them"
    )
    # Review hardening (2026-06-09): "mounted" must mean MOUNTED, not just
    # requested. Deterministic codegen only mounts ``selectedDossiers.required``
    # (build_site.py:selected_required_dossiers), and the historic bug class is
    # exactly "capability in requestedCapabilities but no implementing dossier
    # secured" - so this invariant asserts the dossier landed too.
    v2_required = (v2_pi.get("selectedDossiers") or {}).get("required") or []
    assert "mailto-contact-form" in v2_required, (
        "contact-form's implementing dossier (mailto-contact-form) must be "
        "secured in selectedDossiers.required - a capability that is only "
        f"requested is NOT mounted. Got required={v2_required!r}"
    )


def test_unrelated_followup_does_not_reset_to_fresh_init(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """INVARIANT 5: an *unrelated* follow-up (a pure restyle) must evolve the same
    project, not restart it. The version still bumps to v2 off v1, the projectId
    and originalPrompt are unchanged, NO capability is (re)mounted, and the prior
    selections (selectedDossiers + the stable identity fields) are carried
    forward verbatim - only the requested visual change lands."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v1_pi, prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(
        tmp_path
    )
    init_meta = _read_meta(prompt_inputs, 1)

    r2 = _followup(
        SITE_ID,
        RESTYLE_FOLLOWUP,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs=prompt_inputs,
    )

    # It is a restyle that evolved v1 -> v2 (lineage intact, not a fresh init).
    assert r2["applied"] is True
    assert r2["editKind"] == "visual_style"
    assert r2["version"] == 2 and r2["previousVersion"] == 1
    assert r2["runId"] != base_run_id

    # No capability was (re)mounted: a restyle is theme-only, not a re-init that
    # would re-seed the project's capabilities/selections.
    assert r2["appliedCapabilities"] == []

    v2_pi = _read_input(prompt_inputs, 2)
    v2_meta = _read_meta(prompt_inputs, 2)

    # Identity spine + the original prompt are preserved (no re-init / re-brief).
    assert v2_meta["projectId"] == PROJECT_ID == init_meta["projectId"]
    assert v2_meta["originalPrompt"] == init_meta["originalPrompt"]

    # Prior selections carry forward verbatim - selectedDossiers is untouched and
    # the stable identity fields are identical to v1.
    assert v2_pi["selectedDossiers"] == v1_pi["selectedDossiers"]
    for field in STABLE_IDENTITY_FIELDS:
        assert v2_pi[field] == v1_pi[field], field

    # Capabilities are not reset/re-seeded by an unrelated follow-up.
    assert v2_pi.get("requestedCapabilities", []) == v1_pi.get(
        "requestedCapabilities", []
    )

    # Only the requested visual change actually landed.
    assert v2_pi["brand"]["primaryColorHex"] == "#db2777"