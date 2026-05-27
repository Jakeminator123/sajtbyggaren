"""LLM Golden Path v1 smoke test.

Locks the narrow vertical slice that turns a free prompt into a built site
and a follow-up prompt into a new immutable version of the same project:

    prompt -> Project Input v1 -> build() -> run_v1
    follow-up prompt -> Project Input v2 -> build() -> run_v2

The test does not introduce new contracts. It exercises the real
``scripts.prompt_to_project_input.generate`` /
``scripts.prompt_to_project_input.generate_followup`` helpers and the real
``scripts.build_site.build`` entry-point with ``do_build=False`` so it never
shells out to ``npm install`` or ``npm run build``. ``OPENAI_API_KEY`` is
unset so both ``briefModel`` and ``planningModel`` fall back to the
deterministic mock paths, which keeps the smoke test runnable on any
agent (cloud or local) without network access or secrets.

The complementary test ``tests/test_followup_versioning_regression.py``
asserts the fine-grained semantic merge contract (tone shift, project DNA,
discovery decision inheritance). This smoke test asserts the coarse
artefakt contract: every run writes the eight canonical Engine Run files
plus a generated-files snapshot, and the v1 -> v2 chain preserves
``projectId`` / ``version`` / ``previousVersion`` / ``followUpPrompt``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.build_site import build
from scripts.prompt_to_project_input import generate, generate_followup

INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö."
FOLLOWUP_PROMPT = "Gör tonen mer premium."
SITE_ID = "electrician-malmo"
PROJECT_ID = "golden-path-smoke"

# Multi-intent chain config for the deeper smoke test below.
# Each tuple: (prompt, expected classified intent, expected version after step).
# Prompts are chosen against the deterministic ``classify_followup_intent``
# keyword lists in ``scripts/prompt_to_project_input.py`` so the chain pins a
# specific intent id at every step. If the keyword lists move, update this
# table; do not weaken the assertion.
_MULTI_INTENT_STEPS: tuple[tuple[str, str, int], ...] = (
    ("Gör tonen mer premium.", "tone-shift", 2),
    ("Lyft fram vår historia tydligare.", "story-emphasize", 3),
    ("Uppdatera taglinen till 'Ditt trygga elval'.", "tagline-update", 4),
)

_MULTI_INTENT_INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö."
_MULTI_INTENT_SITE_ID = "electrician-malmo-multi"
_MULTI_INTENT_PROJECT_ID = "golden-path-multi-intent"

_REAL_BUILD_INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö."
_REAL_BUILD_SITE_ID = "electrician-malmo-real-build"
_REAL_BUILD_PROJECT_ID = "golden-path-real-build"

_REQUIRED_RUN_FILES = (
    "input.json",
    "site-brief.json",
    "site-plan.json",
    "generation-package.json",
    "quality-result.json",
    "repair-result.json",
    "build-result.json",
    "trace.ndjson",
)

_ACCEPTED_QUALITY_STATUSES = frozenset({"ok"})


def _assert_run_artefakts_present(run_dir: Path) -> None:
    """Every run must produce the eight canonical files + a snapshot."""

    for name in _REQUIRED_RUN_FILES:
        artefakt = run_dir / name
        assert artefakt.is_file(), (
            f"Missing canonical run artefakt {name!r} under {run_dir}. "
            "The LLM Golden Path contract requires all eight files plus "
            "the generated-files snapshot per build."
        )

    home_page = run_dir / "generated-files" / "app" / "page.tsx"
    assert home_page.is_file(), (
        f"Missing generated home page at {home_page}. The build snapshot "
        "must contain app/page.tsx so the preview can render the site."
    )


@pytest.mark.tooling
def test_llm_golden_path_init_and_followup_smoke(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Init prompt + follow-up prompt run end-to-end through the pipeline.

    The test pins the public contract of the Golden Path:

    1. ``generate`` writes an immutable ``.v1.project-input.json`` snapshot
       with the operator-supplied ``projectId`` and version 1.
    2. ``build`` consumes that snapshot and emits a complete Engine Run
       directory (eight canonical artefakts + generated-files snapshot).
    3. ``generate_followup`` inherits ``projectId`` / discovery decision,
       bumps to version 2, and records ``previousVersion`` +
       ``followUpPrompt`` on the new snapshot.
    4. A second ``build`` produces a distinct run directory whose
       ``build-result.json`` declares ``engineMode == "followup"``.
    """

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_pi_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )

    assert init_pi_path.name == f"{SITE_ID}.v1.project-input.json"

    _, run_dir_v1 = build(
        init_pi_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    _, _, followup_pi_path, _ = generate_followup(
        FOLLOWUP_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=SITE_ID,
    )

    assert followup_pi_path.name == f"{SITE_ID}.v2.project-input.json"

    _, run_dir_v2 = build(
        followup_pi_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    _assert_run_artefakts_present(run_dir_v1)
    _assert_run_artefakts_present(run_dir_v2)

    assert run_dir_v1 != run_dir_v2, (
        "Follow-up build must write to a new run directory; reusing "
        "run_v1 would break version provenance and trace history."
    )
    assert run_dir_v1.parent == run_dir_v2.parent == runs_dir

    input_v1 = json.loads((run_dir_v1 / "input.json").read_text(encoding="utf-8"))
    input_v2 = json.loads((run_dir_v2 / "input.json").read_text(encoding="utf-8"))
    build_result_v1 = json.loads(
        (run_dir_v1 / "build-result.json").read_text(encoding="utf-8")
    )
    build_result_v2 = json.loads(
        (run_dir_v2 / "build-result.json").read_text(encoding="utf-8")
    )
    quality_v1 = json.loads(
        (run_dir_v1 / "quality-result.json").read_text(encoding="utf-8")
    )
    quality_v2 = json.loads(
        (run_dir_v2 / "quality-result.json").read_text(encoding="utf-8")
    )

    assert input_v1["projectId"] == PROJECT_ID
    assert input_v2["projectId"] == PROJECT_ID
    assert input_v1["version"] == 1
    assert input_v2["version"] == 2
    assert input_v2["previousVersion"] == 1
    assert input_v2["followUpPrompt"] == FOLLOWUP_PROMPT

    assert build_result_v1["engineMode"] == "init"
    assert build_result_v2["engineMode"] == "followup"

    for run_label, quality_payload in (("v1", quality_v1), ("v2", quality_v2)):
        assert quality_payload["status"] in _ACCEPTED_QUALITY_STATUSES, (
            f"quality-result.json status for {run_label} was "
            f"{quality_payload['status']!r}; expected one of "
            f"{sorted(_ACCEPTED_QUALITY_STATUSES)}. The smoke test runs "
            "with do_build=False, which keeps the blocking typecheck +/- "
            "build-status checks skipped so the aggregate must stay "
            "non-failing."
        )


@pytest.mark.tooling
def test_llm_golden_path_multi_intent_followup_chain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Multi-step follow-up chain pins the deeper golden-path contract.

    The single-step smoke test above locks ``v1 -> v2`` for one intent.
    This test extends the chain to ``v1 -> v2 -> v3 -> v4`` across three
    distinct follow-up intents (``tone-shift``, ``story-emphasize``,
    ``tagline-update``). It pins:

    1. Each follow-up bumps ``version`` by exactly 1 and records the
       correct ``previousVersion``.
    2. ``projectId`` stays stable across the entire chain.
    3. ``classify_followup_intent`` records the correct intent id under
       ``projectDna.followUpIntent.id`` for every step.
    4. Each build produces a distinct run directory under the same
       ``runs_dir`` with all eight canonical artefacts.
    5. ``build-result.engineMode`` is ``"init"`` for v1 and ``"followup"``
       for v2/v3/v4.

    The complementary ``test_followup_versioning_regression`` covers the
    fine-grained semantic merge contract (which fields each intent
    actually modifies). This test pins the *chain* — proving multi-step
    follow-up does not regress version provenance after several rounds.
    """

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_pi_path, _ = generate(
        _MULTI_INTENT_INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=_MULTI_INTENT_SITE_ID,
        project_id=_MULTI_INTENT_PROJECT_ID,
    )
    assert init_pi_path.name == f"{_MULTI_INTENT_SITE_ID}.v1.project-input.json"

    _, run_dir_v1 = build(
        init_pi_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )
    _assert_run_artefakts_present(run_dir_v1)

    run_dirs: list[Path] = [run_dir_v1]
    followup_prompts: list[str] = []

    for prompt, expected_intent, expected_version in _MULTI_INTENT_STEPS:
        _, followup_meta, followup_pi_path, _ = generate_followup(
            prompt,
            output_dir=prompt_inputs_dir,
            site_id=_MULTI_INTENT_SITE_ID,
        )
        followup_prompts.append(prompt)

        assert (
            followup_pi_path.name
            == f"{_MULTI_INTENT_SITE_ID}.v{expected_version}.project-input.json"
        )
        assert followup_meta["version"] == expected_version
        assert followup_meta["previousVersion"] == expected_version - 1
        assert followup_meta["projectId"] == _MULTI_INTENT_PROJECT_ID
        assert followup_meta["followUpPrompt"] == prompt
        actual_intent = followup_meta["projectDna"]["followUpIntent"]["id"]
        assert actual_intent == expected_intent, (
            f"Follow-up step v{expected_version} prompt {prompt!r} "
            f"classified as {actual_intent!r}; expected {expected_intent!r}. "
            "If the deterministic classifier keyword lists in "
            "scripts/prompt_to_project_input.py change, update "
            "_MULTI_INTENT_STEPS rather than weakening this assertion."
        )

        _, run_dir = build(
            followup_pi_path,
            do_build=False,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
        )
        _assert_run_artefakts_present(run_dir)
        run_dirs.append(run_dir)

    assert len(set(run_dirs)) == len(run_dirs), (
        f"Expected 4 distinct run directories; got duplicates in {run_dirs}"
    )
    assert all(d.parent == runs_dir for d in run_dirs)

    for index, run_dir in enumerate(run_dirs):
        expected_version = index + 1
        expected_mode = "init" if index == 0 else "followup"
        input_payload = json.loads(
            (run_dir / "input.json").read_text(encoding="utf-8")
        )
        build_payload = json.loads(
            (run_dir / "build-result.json").read_text(encoding="utf-8")
        )
        assert input_payload["projectId"] == _MULTI_INTENT_PROJECT_ID
        assert input_payload["version"] == expected_version
        if index > 0:
            assert input_payload["previousVersion"] == expected_version - 1
            assert input_payload["followUpPrompt"] == followup_prompts[index - 1]
        assert build_payload["engineMode"] == expected_mode


@pytest.mark.tooling
@pytest.mark.slow
def test_llm_golden_path_real_build_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Real Next.js compilation proves the framework-level build works.

    The other smoke tests in this file use ``do_build=False`` so they stay
    fast and runnable on any agent without Node or network access. This
    test runs ``do_build=True`` so the builder actually shells out to
    ``npm install`` + ``next build`` against the generated site, which
    pins that:

    1. The pipeline does not just produce JSON artefakts — it produces a
       generated site that Next.js can compile cleanly.
    2. ``build-result.buildStatus`` reflects the real compilation
       outcome, not the skipped fallback.
    3. ``quality-result.status`` lands in ``ok`` once the blocking
       typecheck and build-status checks actually run.

    Marked ``slow`` because ``npm install`` + ``next build`` typically
    take 60-120 seconds and require network access. Skipped automatically
    when ``npm`` is not on PATH so contributors without Node tooling can
    still run the rest of the suite.
    """

    if shutil.which("npm") is None:
        pytest.skip("npm not available; real Next.js build cannot run.")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    prompt_inputs_dir = tmp_path / "prompt-inputs"
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "generated"

    _, _, init_pi_path, _ = generate(
        _REAL_BUILD_INIT_PROMPT,
        output_dir=prompt_inputs_dir,
        site_id=_REAL_BUILD_SITE_ID,
        project_id=_REAL_BUILD_PROJECT_ID,
    )

    _, run_dir = build(
        init_pi_path,
        do_build=True,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
    )

    _assert_run_artefakts_present(run_dir)

    build_payload = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    quality_payload = json.loads(
        (run_dir / "quality-result.json").read_text(encoding="utf-8")
    )

    assert build_payload["engineMode"] == "init"
    run_status = build_payload.get("status")
    assert run_status == "ok", (
        f"do_build=True produced run status={run_status!r}; expected 'ok'. "
        "The full Next.js build must succeed for the real-build smoke test "
        "to pass. Inspect build-result.json + trace.ndjson under "
        f"{run_dir} for details."
    )

    npm_steps = build_payload.get("npmSteps", [])
    assert npm_steps, (
        "Expected build-result.npmSteps to be populated when do_build=True; "
        "an empty list usually means the build path silently fell back to "
        "skipping npm install + next build."
    )
    failed_steps = [step for step in npm_steps if not step.get("ok")]
    assert not failed_steps, (
        f"Some npm steps failed: {failed_steps}. The real-build smoke test "
        "requires npm install + npm run build to both report ok=true."
    )

    assert quality_payload["status"] == "ok", (
        f"With do_build=True the Quality Gate aggregate must be 'ok'; "
        f"got {quality_payload['status']!r}. The blocking typecheck + "
        "build-status checks should now run instead of being skipped."
    )

    generated_site = generated_dir / _REAL_BUILD_SITE_ID
    assert generated_site.is_dir(), (
        f"Expected the builder to materialise a Next.js project under "
        f"{generated_site}. Without it Next.js had nothing to compile."
    )
    next_output = generated_site / ".next"
    assert next_output.is_dir(), (
        f"Expected Next.js to write its build output to {next_output}. "
        "Missing .next/ means `next build` did not actually run or "
        "succeed even though build-result claims ok."
    )
