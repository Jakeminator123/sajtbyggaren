"""Tests for the Artifact Patch Planner dry-run (KÖR-7b).

These lock the kor-7b "Definition of done":
- "lägg en klocka i andra sektionen" (a router decision with
  ``sectionOrdinal=2``) -> a *valid* patch against the right
  ``contentBlocks.home.<section>`` field.
- A patch against an unknown section / dossier -> lands in ``rejected`` with
  ``valid=False``.
- No writes happen (dry-run): the planner creates/changes no files.
- Deterministic + mock-safe: the planner runs with no ``OPENAI_API_KEY``.

The rails (sections.json + capability-map projections) are read from a real
``AssembledContext`` (KÖR-7a) so the planner is exercised end-to-end with the
context assembler, exactly as the orchestrator would wire them. Run artefakts
live under ``tmp_path``; the real scaffolds / capability-map are read read-only
from the repo, like the context-assembler tests do.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.orchestration.context import (  # noqa: E402
    AssembledContext,
    ContextPaths,
    assemble_artifacts_plus_sections,
    assemble_component_registry,
)
from packages.generation.orchestration.patch import (  # noqa: E402
    ArtifactPatch,
    PatchPlan,
    PatchRails,
    plan_patches,
    rails_from_context,
    validate_patch,
)
from packages.generation.orchestration.router import (  # noqa: E402
    RouterDecision,
    RouterSubtask,
    RouterTarget,
    classify_message,
)

FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "blueprints" / "elektriker-malmo.blueprint.json"
)
RUN_ID = "run-elektriker-malmo"
SITE_ID = "elektriker-malmo"
SCAFFOLD_ID = "local-service-business"

GENPKG = "generation-package.json"


@pytest.fixture
def env(tmp_path: Path):
    """Write the run artefakts into a tmp sandbox; return ``(paths, tmp_path)``.

    Scaffolds / dossiers / capability-map default to the repo (static, read
    read-only), mirroring the context-assembler test fixture.
    """
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    runs = tmp_path / "runs"
    run_dir = runs / RUN_ID
    run_dir.mkdir(parents=True)
    (run_dir / "site-brief.json").write_text(json.dumps(fixture["siteBrief"]), encoding="utf-8")
    (run_dir / "site-plan.json").write_text(json.dumps(fixture["sitePlan"]), encoding="utf-8")
    (run_dir / "generation-package.json").write_text(
        json.dumps(fixture["generationPackage"]), encoding="utf-8"
    )
    paths = ContextPaths(repoRoot=REPO_ROOT, runsDir=runs)
    return paths, tmp_path


def _contexts(paths: ContextPaths) -> tuple[AssembledContext, AssembledContext]:
    """Assemble the two read-only contexts the planner consumes."""
    context = assemble_artifacts_plus_sections(RUN_ID, paths=paths)
    registry = assemble_component_registry(paths=paths)
    return context, registry


def _all_paths(root: Path) -> set[Path]:
    return set(root.rglob("*"))


# ---------------------------------------------------------------------------
# DoD 1: "lägg en klocka i andra sektionen" -> valid patch, right field
# ---------------------------------------------------------------------------


def test_clock_in_second_section_is_valid_patch(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)

    # The router decision carries sectionOrdinal=2 (no sectionId): the planner
    # must resolve the ordinal to a concrete section from the assembled context.
    decision = classify_message("lägg en klocka i andra sektionen")
    assert decision.editKind == "component_add"
    assert decision.target is not None
    assert decision.target.sectionOrdinal == 2
    assert decision.target.sectionId is None
    assert decision.componentIntent == "clock_widget"

    plan = plan_patches(decision, context)

    assert isinstance(plan, PatchPlan)
    assert plan.valid is True
    assert plan.rejected == []
    assert len(plan.patches) == 1

    patch = plan.patches[0]
    assert patch.artifact == GENPKG
    # ordinal 2 -> the route's 2nd section (hero, *service-summary*, ...).
    assert patch.field == "contentBlocks.home.service-summary.accessoryComponent"
    assert patch.op == "set"
    assert patch.value["component"] == "clock-widget"
    # A clock is an inline component (no registered capability) -> no dossier
    # rail to satisfy, so the patch is valid without the registry context.
    assert "capability" not in patch.value


def test_clock_resolution_uses_context_route_sections(env):
    """The ordinal->sectionId mapping comes from the assembled context, not a guess."""
    paths, _tmp = env
    context, _registry = _contexts(paths)
    # ordinal 1 -> hero, ordinal 3 -> trust-proof (required+optional order).
    first = plan_patches(
        RouterDecision(
            messageKind="edit_instruction",
            editKind="component_add",
            target=RouterTarget(routeId="home", sectionOrdinal=1),
            componentIntent="clock_widget",
        ),
        context,
    )
    third = plan_patches(
        RouterDecision(
            messageKind="edit_instruction",
            editKind="component_add",
            target=RouterTarget(routeId="home", sectionOrdinal=3),
            componentIntent="clock_widget",
        ),
        context,
    )
    assert first.patches[0].field == "contentBlocks.home.hero.accessoryComponent"
    assert third.patches[0].field == "contentBlocks.home.trust-proof.accessoryComponent"


# ---------------------------------------------------------------------------
# DoD 2: unknown section / dossier -> rejected, valid:false
# ---------------------------------------------------------------------------


def test_out_of_range_ordinal_is_rejected(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    decision = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        target=RouterTarget(routeId="home", sectionOrdinal=99),
        componentIntent="clock_widget",
    )
    plan = plan_patches(decision, context)
    assert plan.valid is False
    assert plan.patches == []
    assert len(plan.rejected) == 1
    assert "out of range" in plan.rejected[0].reason


def test_unknown_section_id_is_rejected(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    decision = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        target=RouterTarget(routeId="home", sectionId="ghost-section"),
        componentIntent="clock_widget",
    )
    plan = plan_patches(decision, context)
    assert plan.valid is False
    assert len(plan.rejected) == 1
    rejected = plan.rejected[0]
    assert rejected.field == "contentBlocks.home.ghost-section.accessoryComponent"
    assert "ghost-section" in rejected.reason
    assert "sections.json" in rejected.reason


def test_unknown_route_is_rejected(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    decision = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        target=RouterTarget(routeId="blog", sectionId="post"),
        componentIntent="clock_widget",
    )
    plan = plan_patches(decision, context)
    assert plan.valid is False
    assert "route 'blog'" in plan.rejected[0].reason


def test_unknown_dossier_gap_is_rejected(env):
    """A component mapping to a capability with no dossier (gap) is rejected."""
    paths, _tmp = env
    context, registry = _contexts(paths)
    # newsletter_signup -> capability 'newsletter-subscribe', which exists in
    # the capability-map but has an empty dossiers list (a gap, not a feature).
    decision = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        target=RouterTarget(routeId="home", sectionOrdinal=2),
        componentIntent="newsletter_signup",
    )
    plan = plan_patches(decision, context, registry=registry)
    assert plan.valid is False
    assert len(plan.rejected) == 1
    assert "newsletter-subscribe" in plan.rejected[0].reason


def test_known_capability_with_dossier_is_valid(env):
    """A component mapping to an implemented capability validates against its rail."""
    paths, _tmp = env
    context, registry = _contexts(paths)
    decision = RouterDecision(
        messageKind="edit_instruction",
        editKind="component_add",
        target=RouterTarget(routeId="home", sectionOrdinal=2),
        componentIntent="contact_form",
    )
    plan = plan_patches(decision, context, registry=registry)
    assert plan.valid is True
    assert len(plan.patches) == 1
    assert plan.patches[0].value["capability"] == "contact-form"


# ---------------------------------------------------------------------------
# copy_change + non-patchable decisions
# ---------------------------------------------------------------------------


def test_copy_change_emits_target_with_deferred_value(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    decision = RouterDecision(
        messageKind="edit_instruction",
        editKind="copy_change",
        target=RouterTarget(routeId="home", sectionOrdinal=1),
    )
    plan = plan_patches(decision, context)
    assert plan.valid is True
    assert len(plan.patches) == 1
    patch = plan.patches[0]
    assert patch.field == "contentBlocks.home.hero.headline"
    # The new copy is produced downstream (kor-1c), never invented here.
    assert patch.value is None
    assert any("copy_change" in note for note in plan.notes)


def test_non_patchable_decision_yields_empty_valid_plan(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    # A pure question is not an edit at all -> nothing to propose.
    decision = classify_message("vad är klockan?")
    assert decision.editKind == "none"
    plan = plan_patches(decision, context)
    assert plan.valid is True
    assert plan.patches == []
    assert plan.rejected == []
    assert plan.notes  # explains why nothing was proposed


def test_multi_intent_subtasks_are_planned(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    decision = RouterDecision(
        messageKind="multi_intent",
        editKind="none",
        subtasks=[
            RouterSubtask(
                editKind="component_add",
                componentIntent="clock_widget",
                target=RouterTarget(routeId="home", sectionOrdinal=2),
            ),
            RouterSubtask(editKind="visual_style", instruction="more premium"),
        ],
    )
    plan = plan_patches(decision, context)
    # Only the component_add subtask is patchable; visual_style is out of scope.
    assert plan.valid is True
    assert len(plan.patches) == 1
    assert plan.patches[0].field == "contentBlocks.home.service-summary.accessoryComponent"


# ---------------------------------------------------------------------------
# Dry-run: no writes
# ---------------------------------------------------------------------------


def test_plan_is_dry_run_and_writes_nothing(env):
    paths, tmp_path = env
    context, registry = _contexts(paths)
    before = _all_paths(tmp_path)

    decision = classify_message("lägg en klocka i andra sektionen")
    plan = plan_patches(decision, context, registry=registry)
    assert isinstance(plan, PatchPlan)

    # No file created, changed or removed; no run directory invented.
    assert _all_paths(tmp_path) == before
    # The fixture generation-package is byte-for-byte untouched.
    genpkg = paths.runs / RUN_ID / "generation-package.json"
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert json.loads(genpkg.read_text(encoding="utf-8")) == fixture["generationPackage"]


def test_planner_is_mock_safe_without_openai_key(env, monkeypatch):
    """The planner is deterministic and needs no OPENAI_API_KEY (no LLM)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    paths, _tmp = env
    context, _registry = _contexts(paths)
    decision = classify_message("lägg en klocka i andra sektionen")
    first = plan_patches(decision, context)
    second = plan_patches(decision, context)
    assert first.valid is True
    assert first.model_dump() == second.model_dump()  # deterministic


# ---------------------------------------------------------------------------
# validate_patch + rails_from_context (the rail unit, read from context)
# ---------------------------------------------------------------------------


def test_rails_from_context_reads_section_rails(env):
    paths, _tmp = env
    context, registry = _contexts(paths)
    rails = rails_from_context(context, registry=registry)
    assert isinstance(rails, PatchRails)
    assert rails.allowed_sections("home")[0] == "hero"
    assert rails.allowed_sections("home")[1] == "service-summary"
    assert rails.knows_route("home")
    assert not rails.knows_route("blog")
    assert rails.capabilitiesAvailable is True
    assert "contact-form" in rails.capabilities


def test_validate_patch_accepts_known_section(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    rails = rails_from_context(context)
    patch = ArtifactPatch(
        artifact=GENPKG,
        field="contentBlocks.home.hero.accessoryComponent",
        value={"component": "clock-widget", "variant": None},
    )
    assert validate_patch(patch, rails) is None


def test_validate_patch_rejects_unknown_artifact(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    rails = rails_from_context(context)
    patch = ArtifactPatch(artifact="site-plan.json", field="contentBlocks.home.hero.headline")
    reason = validate_patch(patch, rails)
    assert reason is not None and "not patchable" in reason


def test_validate_patch_rejects_non_blueprint_root(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    rails = rails_from_context(context)
    # runId is a real schema field but identity, never patched by the planner.
    patch = ArtifactPatch(artifact=GENPKG, field="runId")
    reason = validate_patch(patch, rails)
    assert reason is not None and "not a patchable blueprint field" in reason


def test_validate_patch_rejects_unknown_section(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    rails = rails_from_context(context)
    patch = ArtifactPatch(artifact=GENPKG, field="contentBlocks.home.no-such-section.headline")
    reason = validate_patch(patch, rails)
    assert reason is not None and "no-such-section" in reason


def test_validate_patch_capability_without_registry_is_rejected(env):
    paths, _tmp = env
    context, _registry = _contexts(paths)
    # rails built WITHOUT a registry context -> capability rail unavailable.
    rails = rails_from_context(context)
    patch = ArtifactPatch(
        artifact=GENPKG,
        field="contentBlocks.home.hero.accessoryComponent",
        value={"component": "contact-form", "capability": "contact-form"},
    )
    reason = validate_patch(patch, rails)
    assert reason is not None and "registry" in reason


def test_validate_patch_rejects_unknown_capability(env):
    paths, _tmp = env
    context, registry = _contexts(paths)
    rails = rails_from_context(context, registry=registry)
    patch = ArtifactPatch(
        artifact=GENPKG,
        field="contentBlocks.home.hero.accessoryComponent",
        value={"component": "x", "capability": "totally-made-up"},
    )
    reason = validate_patch(patch, rails)
    assert reason is not None and "totally-made-up" in reason
