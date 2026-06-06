"""Tests for the Artifact Patch apply step (KÖR-7c).

These lock the kor-7c "Definition of done":

- A *validated* patch (a capability-backed ``component_add``) -> a new
  ``<siteId>.v<N+1>`` snapshot carrying the change (the capability lands in
  ``requestedCapabilities`` via the existing directive mechanism); ``projectId``
  / ``siteId`` preserved; scaffold/variant frozen.
- **No previous ``vN`` snapshot and no ``data/runs/<älder runId>/`` artefakt is
  changed** (verified with a byte-diff before/after).
- A ``rejected`` / invalid plan is **never** applied (``PatchApplyError``).
- A valid plan whose patch has no existing Project Input home writes **nothing**
  and reports the gap (it never invents a new runtime contract).
- ``current.json`` is never written (no build in this slice).
- Deterministic + mock-safe: apply runs with no ``OPENAI_API_KEY`` (no LLM).

The version/merge/write spine is the existing follow-up logic in
``scripts/prompt_to_project_input.py``; these tests drive it through the new
``apply_patch_plan`` exactly as the orchestrator would. Run artefakts live under
``tmp_path``; the real scaffolds / capability-map are read read-only from the
repo, like the patch-planner tests do.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.apply import (  # noqa: E402
    AppliedCapability,
    ApplyResult,
    PatchApplyError,
    apply_patch_plan,
    classify_patch,
    log_patch_apply_to_existing_run,
)
from packages.generation.orchestration.patch import (  # noqa: E402
    ArtifactPatch,
    PatchPlan,
    RejectedPatch,
)

SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"
GENPKG = "generation-package.json"
SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate():
    """Import generate lazily so the module import chain matches the worktree."""
    from scripts.prompt_to_project_input import generate

    return generate


def _init_site(tmp_path: Path):
    """Create a v1 Project Input + meta in ``tmp_path`` (mock brief, no key)."""
    generate = _generate()
    return generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )


def _capability_patch(
    *,
    capability: str = "contact-form",
    field: str = "contentBlocks.home.service-summary.accessoryComponent",
) -> PatchPlan:
    """A valid plan with one capability-backed component_add patch."""
    return PatchPlan(
        patches=[
            ArtifactPatch(
                artifact=GENPKG,
                field=field,
                op="set",
                value={
                    "component": capability,
                    "variant": None,
                    "capability": capability,
                },
            )
        ],
        valid=True,
    )


def _inline_component_patch() -> PatchPlan:
    """A valid plan with an inline component (no capability) - has no PI home."""
    return PatchPlan(
        patches=[
            ArtifactPatch(
                artifact=GENPKG,
                field="contentBlocks.home.service-summary.accessoryComponent",
                op="set",
                value={"component": "clock-widget", "variant": None},
            )
        ],
        valid=True,
    )


def _copy_change_patch() -> PatchPlan:
    """A valid plan with a copy_change (deferred value) - has no PI home."""
    return PatchPlan(
        patches=[
            ArtifactPatch(
                artifact=GENPKG,
                field="contentBlocks.home.hero.headline",
                op="set",
                value=None,
            )
        ],
        valid=True,
    )


def _hash_tree(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to a content hash (for immutability diffs)."""
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digests[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return digests


# ---------------------------------------------------------------------------
# DoD 1: validated patch -> new v<N+1>, identity preserved, scaffold/variant frozen
# ---------------------------------------------------------------------------


def test_apply_creates_next_version_with_capability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v1_pi, v1_meta, v1_path, _v1_meta_path = _init_site(tmp_path)
    assert "contact-form" not in v1_pi["requestedCapabilities"]

    result = apply_patch_plan(
        _capability_patch(),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )

    assert isinstance(result, ApplyResult)
    assert result.applied is True
    assert result.version == 2
    assert result.previousVersion == 1
    assert result.projectId == PROJECT_ID
    assert result.appliedCapabilities == [
        AppliedCapability(
            patchField="contentBlocks.home.service-summary.accessoryComponent",
            capability="contact-form",
        )
    ]
    assert not result.unmapped

    v2_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    v2_meta = json.loads(
        (tmp_path / f"{SITE_ID}.v2.meta.json").read_text(encoding="utf-8")
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(v2_pi)

    # The change landed: capability added via the existing requestedCapabilities
    # field, not a new artefakt.
    assert "contact-form" in v2_pi["requestedCapabilities"]
    # Identity preserved; scaffold/variant frozen.
    assert v2_pi["siteId"] == v1_pi["siteId"] == SITE_ID
    assert v2_meta["projectId"] == v1_meta["projectId"] == PROJECT_ID
    assert v2_meta["version"] == 2
    assert v2_meta["previousVersion"] == 1
    assert v2_pi["scaffoldId"] == v1_pi["scaffoldId"]
    assert v2_pi["variantId"] == v1_pi["variantId"]
    # Apply provenance recorded on the sidecar (not the PI schema).
    assert v2_meta["appliedPatchPlan"]["source"] == "kor-7c-artifact-apply"
    assert v2_meta["appliedPatchPlan"]["appliedCapabilities"][0]["capability"] == (
        "contact-form"
    )
    # v1 snapshot byte-stable (immutable).
    assert v1_path.read_text(encoding="utf-8") == json.dumps(
        v1_pi, ensure_ascii=False, indent=2
    ) + "\n"


def test_apply_unions_capabilities_without_dropping_existing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A second apply adds to, never replaces, requestedCapabilities."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    apply_patch_plan(
        _capability_patch(capability="contact-form"),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    result = apply_patch_plan(
        _capability_patch(capability="gallery"),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    assert result.version == 3
    v3_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v3.project-input.json").read_text(encoding="utf-8")
    )
    assert "contact-form" in v3_pi["requestedCapabilities"]
    assert "gallery" in v3_pi["requestedCapabilities"]


# ---------------------------------------------------------------------------
# DoD 2: no previous vN or data/runs/<älder runId>/ artefakt changed
# ---------------------------------------------------------------------------


def test_apply_does_not_mutate_previous_version_or_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    old_run = runs_dir / "run-old-electrician"
    old_run.mkdir(parents=True)
    # A prior run's immutable artefakt chain.
    (old_run / "site-brief.json").write_text('{"runId": "run-old-electrician"}', encoding="utf-8")
    (old_run / "site-plan.json").write_text('{"phase": "plan"}', encoding="utf-8")
    (old_run / "generation-package.json").write_text('{"contentBlocks": {}}', encoding="utf-8")
    (old_run / "input.json").write_text('{"version": 1}', encoding="utf-8")

    generate = _generate()
    generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )

    # Snapshot the immutable v1 files + the whole runs tree.
    v1_files = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in prompt_inputs.glob(f"{SITE_ID}.v1.*")
    }
    assert v1_files  # guard: v1 snapshot exists
    runs_before = _hash_tree(runs_dir)

    apply_patch_plan(
        _capability_patch(),
        site_id=SITE_ID,
        output_dir=prompt_inputs,
        runs_dir=runs_dir,
    )

    # v1 snapshot byte-for-byte unchanged.
    for path, digest in v1_files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, path
    # The whole runs tree byte-for-byte unchanged (apply touched no run).
    assert _hash_tree(runs_dir) == runs_before
    # New v2 snapshot was created.
    assert (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_never_writes_current_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """current.json is the build pointer (kor-7d); apply must never write it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    apply_patch_plan(_capability_patch(), site_id=SITE_ID, output_dir=tmp_path)
    assert not list(tmp_path.rglob("current.json"))


# ---------------------------------------------------------------------------
# DoD 3: rejected/invalid plan is never applied
# ---------------------------------------------------------------------------


def test_apply_refuses_invalid_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    plan = PatchPlan(
        patches=[],
        valid=False,
        rejected=[
            RejectedPatch(
                artifact=GENPKG,
                field="contentBlocks.home.ghost.accessoryComponent",
                value={"component": "x"},
                reason="section not in rails",
            )
        ],
    )
    with pytest.raises(PatchApplyError):
        apply_patch_plan(plan, site_id=SITE_ID, output_dir=tmp_path)
    # No version written.
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_refuses_plan_with_rejected_even_if_valid_true(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Defensive: a hand-built plan with rejected entries is refused."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    plan = PatchPlan(
        patches=[],
        valid=True,
        rejected=[
            RejectedPatch(artifact=GENPKG, field="x", value=None, reason="r"),
        ],
    )
    with pytest.raises(PatchApplyError):
        apply_patch_plan(plan, site_id=SITE_ID, output_dir=tmp_path)
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


# ---------------------------------------------------------------------------
# Unmapped patches: valid plan, no existing Project Input home -> report, no write
# ---------------------------------------------------------------------------


def test_apply_reports_inline_component_as_unmapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(
        _inline_component_patch(), site_id=SITE_ID, output_dir=tmp_path
    )
    assert result.applied is False
    assert len(result.unmapped) == 1
    assert "inline-komponent" in result.unmapped[0].reason
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_reports_copy_change_as_unmapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(
        _copy_change_patch(), site_id=SITE_ID, output_dir=tmp_path
    )
    assert result.applied is False
    assert len(result.unmapped) == 1
    assert "copy_change" in result.unmapped[0].reason
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_is_all_or_nothing_for_mixed_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A plan mixing a mappable + an unmappable patch writes nothing."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    plan = PatchPlan(
        patches=[
            _capability_patch().patches[0],
            _inline_component_patch().patches[0],
        ],
        valid=True,
    )
    result = apply_patch_plan(plan, site_id=SITE_ID, output_dir=tmp_path)
    assert result.applied is False
    assert len(result.appliedCapabilities) == 1  # diagnostics only
    assert len(result.unmapped) == 1
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_empty_plan_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(PatchPlan(), site_id=SITE_ID, output_dir=tmp_path)
    assert result.applied is False
    assert result.notes
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_theme_directive_writes_version_on_empty_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A restyle (visual_style) has no capability patch, but an explicit theme
    directive still writes the next version with brand/tone set (the empty-plan
    no-op only fires when there is ALSO no theme)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from packages.generation.followup.theme_directives import ThemeDirective

    _init_site(tmp_path)
    result = apply_patch_plan(
        PatchPlan(),
        site_id=SITE_ID,
        output_dir=tmp_path,
        theme_directive=ThemeDirective(
            primaryColorHex="#db2777", toneVibe="editorial", colorWord="rosa"
        ),
    )
    assert result.applied is True
    assert result.version == 2
    v2 = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert v2["brand"]["primaryColorHex"] == "#db2777"
    assert v2["tone"]["primary"] == "editorial"


def test_apply_empty_plan_with_empty_theme_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A theme directive with no values set is not a change: still a no-op."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from packages.generation.followup.theme_directives import ThemeDirective

    _init_site(tmp_path)
    result = apply_patch_plan(
        PatchPlan(),
        site_id=SITE_ID,
        output_dir=tmp_path,
        theme_directive=ThemeDirective(),
    )
    assert result.applied is False
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


# ---------------------------------------------------------------------------
# Iterate from a historical version (base_run_id), like today's follow-up
# ---------------------------------------------------------------------------


def test_apply_with_base_run_id_iterates_from_historical_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    base_run = runs_dir / "run-v1-base"
    base_run.mkdir(parents=True)
    (base_run / "input.json").write_text('{"version": 1}', encoding="utf-8")

    generate = _generate()
    # v1, then a v2 so latest != base.
    generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    apply_patch_plan(
        _capability_patch(capability="gallery"),
        site_id=SITE_ID,
        output_dir=prompt_inputs,
    )

    runs_before = _hash_tree(runs_dir)
    # Fork from the historical v1 via base_run_id.
    result = apply_patch_plan(
        _capability_patch(capability="contact-form"),
        site_id=SITE_ID,
        output_dir=prompt_inputs,
        base_run_id="run-v1-base",
        runs_dir=runs_dir,
    )
    # next_version = max(latest=2, base=1) + 1 = 3.
    assert result.version == 3
    assert result.previousVersion == 1
    v3_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v3.project-input.json").read_text(encoding="utf-8")
    )
    # Forked from v1: it has contact-form but NOT the v2-only gallery.
    assert "contact-form" in v3_pi["requestedCapabilities"]
    assert "gallery" not in v3_pi["requestedCapabilities"]
    # base run trace/artefakts untouched.
    assert _hash_tree(runs_dir) == runs_before


# ---------------------------------------------------------------------------
# Trace logging: append-only, only into an existing run, never creates one
# ---------------------------------------------------------------------------


def test_apply_logs_into_supplied_run_trace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    new_run = tmp_path / "runs" / "run-new-version"
    new_run.mkdir(parents=True)
    result = apply_patch_plan(
        _capability_patch(),
        site_id=SITE_ID,
        output_dir=tmp_path,
        trace_run_dir=new_run,
    )
    assert result.applied is True
    trace_path = new_run / "trace.ndjson"
    assert trace_path.exists()
    events = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(events) == 1
    assert events[0]["phase"] == "apply"
    assert events[0]["event"] == "patch-apply"
    assert events[0]["status"] == "done"
    assert events[0]["apply"]["version"] == 2


def test_trace_logger_never_creates_a_run(tmp_path: Path) -> None:
    missing = tmp_path / "runs" / "does-not-exist"
    result = ApplyResult(applied=True, siteId=SITE_ID, version=2, previousVersion=1)
    assert log_patch_apply_to_existing_run(missing, result) is False
    assert not missing.exists()


# ---------------------------------------------------------------------------
# FYND1 (kor-7d trace-gap): skipped/unmapped/rejected outcomes are traced too
# ---------------------------------------------------------------------------


def _read_trace_events(run_dir: Path) -> list[dict]:
    trace_path = run_dir / "trace.ndjson"
    if not trace_path.exists():
        return []
    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_apply_traces_unmapped_outcome_when_run_dir_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unmapped (skipped) apply leaves an honest trace event, not silence."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    run_dir = tmp_path / "runs" / "run-unmapped"
    run_dir.mkdir(parents=True)
    result = apply_patch_plan(
        _inline_component_patch(),
        site_id=SITE_ID,
        output_dir=tmp_path,
        trace_run_dir=run_dir,
    )
    assert result.applied is False
    assert result.unmapped
    events = _read_trace_events(run_dir)
    assert len(events) == 1
    assert events[0]["event"] == "patch-apply"
    assert events[0]["status"] == "skipped"
    assert events[0]["apply"]["applied"] is False
    assert events[0]["apply"]["unmapped"]


def test_apply_traces_empty_plan_outcome_when_run_dir_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    run_dir = tmp_path / "runs" / "run-empty"
    run_dir.mkdir(parents=True)
    result = apply_patch_plan(
        PatchPlan(),
        site_id=SITE_ID,
        output_dir=tmp_path,
        trace_run_dir=run_dir,
    )
    assert result.applied is False
    events = _read_trace_events(run_dir)
    assert len(events) == 1
    assert events[0]["status"] == "skipped"


def test_apply_traces_rejected_outcome_before_raising(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A rejected/invalid plan is traced (FYND1) and still raises (kor-7c DoD)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    run_dir = tmp_path / "runs" / "run-rejected"
    run_dir.mkdir(parents=True)
    plan = PatchPlan(
        patches=[],
        valid=False,
        rejected=[
            RejectedPatch(artifact=GENPKG, field="x", value=None, reason="rail break"),
        ],
    )
    with pytest.raises(PatchApplyError):
        apply_patch_plan(
            plan,
            site_id=SITE_ID,
            output_dir=tmp_path,
            trace_run_dir=run_dir,
        )
    events = _read_trace_events(run_dir)
    assert len(events) == 1
    assert events[0]["event"] == "patch-apply"
    assert events[0]["status"] == "skipped"
    assert events[0]["apply"]["applied"] is False


# ---------------------------------------------------------------------------
# classify_patch unit (the blueprint-field -> Project Input-field mapping)
# ---------------------------------------------------------------------------


def test_classify_patch_maps_capability_component_add() -> None:
    capability, reason = classify_patch(
        ArtifactPatch(
            artifact=GENPKG,
            field="contentBlocks.home.service-summary.accessoryComponent",
            value={"component": "contact-form", "capability": "contact-form"},
        )
    )
    assert capability == "contact-form"
    assert reason is None


def test_classify_patch_rejects_inline_component() -> None:
    capability, reason = classify_patch(
        ArtifactPatch(
            artifact=GENPKG,
            field="contentBlocks.home.service-summary.accessoryComponent",
            value={"component": "clock-widget"},
        )
    )
    assert capability is None
    assert reason is not None and "inline-komponent" in reason


def test_classify_patch_rejects_copy_change() -> None:
    capability, reason = classify_patch(
        ArtifactPatch(artifact=GENPKG, field="contentBlocks.home.hero.headline", value=None)
    )
    assert capability is None
    assert reason is not None and "copy_change" in reason


def test_classify_patch_rejects_visual_direction() -> None:
    capability, reason = classify_patch(
        ArtifactPatch(artifact=GENPKG, field="visualDirection.mood", value="calm")
    )
    assert capability is None
    assert reason is not None


def test_classify_patch_deep_field_path_is_unmapped_not_misapplied() -> None:
    """KÖR-7-STAB #175 guard (deeper field-paths).

    classify_patch reads the leaf at segments[3]; the kor-7b planner only emits
    the 4-segment ``contentBlocks.<route>.<section>.<leaf>`` shape (enforced by
    patch/validate.py). A deeper path therefore has no Project Input home and is
    reported unmapped - never silently misapplied as a capability.
    """
    capability, reason = classify_patch(
        ArtifactPatch(
            artifact=GENPKG,
            field="contentBlocks.home.hero.cta.accessoryComponent",
            value={"component": "contact-form", "capability": "contact-form"},
        )
    )
    assert capability is None
    assert reason is not None


# ---------------------------------------------------------------------------
# KÖR-7-STAB #175 P1: applied capability also secures its implementing Dossier
# in selectedDossiers.required so deterministic codegen actually mounts it.
# ---------------------------------------------------------------------------


def _unapplied_intents(previous: dict, merged: dict) -> list[dict[str, str]]:
    from scripts.prompt_to_project_input import compute_unapplied_followup_intents

    return compute_unapplied_followup_intents(previous, merged, follow_up_prompt="")


def _required_dossiers(project_input: dict) -> list[str]:
    from scripts.build_site import selected_required_dossiers

    return selected_required_dossiers(project_input)


def test_apply_capability_secures_dossier_and_clears_unapplied_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P1 (E2E-ish): apply contact-form -> v2 mounts the Dossier, no flag.

    Before the fix the capability reached requestedCapabilities but its Dossier
    never reached selectedDossiers.required, so codegen would not mount it and
    the build's unapplied-follow-up observer would flag it. This locks the fix:
    the implementing Dossier (mailto-contact-form) lands in
    selectedDossiers.required, selected_required_dossiers (the codegen mount
    input) includes it, and compute_unapplied_followup_intents no longer flags
    contact-form.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v1_pi, _v1_meta, _v1_path, _ = _init_site(tmp_path)

    result = apply_patch_plan(
        _capability_patch(capability="contact-form"),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    assert result.applied is True

    v2_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(v2_pi)

    selected = v2_pi["selectedDossiers"]
    assert isinstance(selected, dict)
    assert "mailto-contact-form" in selected["required"]
    assert "mailto-contact-form" in _required_dossiers(v2_pi)

    # The build's observer no longer reports contact-form as unapplied.
    posts = _unapplied_intents(v1_pi, v2_pi)
    assert all(post["target"] != "contact-form" for post in posts), posts


def test_apply_gap_capability_left_unmounted_and_still_flagged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A capability with no implemented Dossier (gap) is applied honestly.

    It lands in requestedCapabilities but apply never invents a Dossier for it,
    so selectedDossiers.required is unchanged and the observer honestly keeps
    flagging the gap (no false 'mounted' claim).
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v1_pi, *_ = _init_site(tmp_path)

    result = apply_patch_plan(
        _capability_patch(capability="newsletter-subscribe"),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    assert result.applied is True

    v2_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert "newsletter-subscribe" in v2_pi["requestedCapabilities"]
    # No Dossier exists for the gap capability -> nothing extra mounted.
    assert _required_dossiers(v2_pi) == _required_dossiers(v1_pi)
    posts = _unapplied_intents(v1_pi, v2_pi)
    assert any(post["target"] == "newsletter-subscribe" for post in posts), posts


def test_apply_dedups_capability_and_dossier_on_repeat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Guard: re-applying the same capability never duplicates it.

    requestedCapabilities dedup is owned by merge_followup_project_input's
    _unique_strings (already correct); the Dossier-securing step is likewise
    idempotent so selectedDossiers.required never grows a duplicate.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    apply_patch_plan(
        _capability_patch(capability="contact-form"),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    apply_patch_plan(
        _capability_patch(capability="contact-form"),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    v3_pi = json.loads(
        (tmp_path / f"{SITE_ID}.v3.project-input.json").read_text(encoding="utf-8")
    )
    assert v3_pi["requestedCapabilities"].count("contact-form") == 1
    assert v3_pi["selectedDossiers"]["required"].count("mailto-contact-form") == 1


# ---------------------------------------------------------------------------
# KÖR-7-STAB #175: stale follow-up provenance never carries into a patch-driven
# version (apply is patch-driven, not prompt-driven).
# ---------------------------------------------------------------------------


def test_apply_drops_stale_followup_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    # Simulate a prior prompt-driven follow-up that left provenance on the meta
    # sidecar apply iterates from.
    meta_path = tmp_path / f"{SITE_ID}.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["followUpPrompt"] = "lägg till en gammal grej"
    meta["baseRunId"] = "run-old-followup"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    apply_patch_plan(_capability_patch(), site_id=SITE_ID, output_dir=tmp_path)

    v2_meta = json.loads(
        (tmp_path / f"{SITE_ID}.v2.meta.json").read_text(encoding="utf-8")
    )
    # Patch-driven apply did not supply either -> neither is inherited.
    assert "followUpPrompt" not in v2_meta
    assert "baseRunId" not in v2_meta


def test_apply_keeps_followup_prompt_when_supplied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The provenance scrub never drops a value THIS apply actually supplied."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    apply_patch_plan(
        _capability_patch(),
        site_id=SITE_ID,
        output_dir=tmp_path,
        follow_up_prompt="lägg till kontaktformulär",
    )
    v2_meta = json.loads(
        (tmp_path / f"{SITE_ID}.v2.meta.json").read_text(encoding="utf-8")
    )
    assert v2_meta["followUpPrompt"] == "lägg till kontaktformulär"


# ---------------------------------------------------------------------------
# Mock-safe + deterministic (no OPENAI_API_KEY)
# ---------------------------------------------------------------------------


def test_apply_is_mock_safe_and_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    generate = _generate()
    for out in (a, b):
        generate(
            "Skapa en hemsida för en elektriker i Malmö",
            output_dir=out,
            site_id=SITE_ID,
            project_id=PROJECT_ID,
        )
    r1 = apply_patch_plan(_capability_patch(), site_id=SITE_ID, output_dir=a)
    r2 = apply_patch_plan(_capability_patch(), site_id=SITE_ID, output_dir=b)
    pi_a = json.loads((a / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8"))
    pi_b = json.loads((b / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8"))
    assert r1.applied is r2.applied is True
    assert pi_a == pi_b  # deterministic Project Input across runs


# ---------------------------------------------------------------------------
# Integration: a plan built by the real kor-7b planner applies end-to-end
# ---------------------------------------------------------------------------


def test_apply_integrates_with_real_patch_planner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Build a validated plan via kor-7b's planner + real context, then apply it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from packages.generation.orchestration.context import (
        ContextPaths,
        assemble_artifacts_plus_sections,
        assemble_component_registry,
    )
    from packages.generation.orchestration.patch import plan_patches
    from packages.generation.orchestration.router import RouterDecision, RouterTarget

    fixture = json.loads(
        (
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "blueprints"
            / "elektriker-malmo.blueprint.json"
        ).read_text(encoding="utf-8")
    )
    runs = tmp_path / "runs"
    run_dir = runs / "run-elektriker-malmo"
    run_dir.mkdir(parents=True)
    (run_dir / "site-brief.json").write_text(json.dumps(fixture["siteBrief"]), encoding="utf-8")
    (run_dir / "site-plan.json").write_text(json.dumps(fixture["sitePlan"]), encoding="utf-8")
    (run_dir / "generation-package.json").write_text(
        json.dumps(fixture["generationPackage"]), encoding="utf-8"
    )
    paths = ContextPaths(repoRoot=REPO_ROOT, runsDir=runs)
    context = assemble_artifacts_plus_sections("run-elektriker-malmo", paths=paths)
    registry = assemble_component_registry(paths=paths)

    plan = plan_patches(
        RouterDecision(
            messageKind="edit_instruction",
            editKind="component_add",
            target=RouterTarget(routeId="home", sectionOrdinal=2),
            componentIntent="contact_form",
        ),
        context,
        registry=registry,
    )
    assert plan.valid is True
    assert plan.patches[0].value["capability"] == "contact-form"

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    _init = _generate()
    _init(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    result = apply_patch_plan(plan, site_id=SITE_ID, output_dir=prompt_inputs)
    assert result.applied is True
    assert result.version == 2
    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert "contact-form" in v2_pi["requestedCapabilities"]
