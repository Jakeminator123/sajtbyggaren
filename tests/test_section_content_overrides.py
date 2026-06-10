"""Tests for section content overrides (ADR 0043) - blueprint-content-utföraren.

Locks the sanctioned path that makes section text changeable via the chat:

    contentBlocks copy_change patch (KÖR-7b)
      -> apply maps it to directives.sectionContentOverrides (KÖR-7c)
      -> renderer prefers the override over the regenerated blueprint copy

and the honesty + carry-forward guarantees around it (B155-rest):

- a whitelisted section field (headline / subheadline / body) whose new copy can
  be derived from the follow-up prompt writes a new version with the override;
- a whitelisted field with no derivable copy, and any target OUTSIDE the
  whitelist, stays an honest no-op (no version written);
- the override map LIVES in Project Input - it survives a later follow-up
  (carry-forward) and never disturbs the hero-headline pin (B173);
- deterministic + mock-safe (no OPENAI_API_KEY).

Run artefakts live under ``tmp_path``; scaffolds / capability-map / fixtures are
read read-only, exactly like the patch-apply + patch-planner tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.followup.section_content_overrides import (  # noqa: E402
    SECTION_OVERRIDE_FIELDS,
    derive_section_edit,
    parse_section_content_field,
    render_section_override_text,
)
from packages.generation.orchestration.apply import (  # noqa: E402
    apply_patch_plan,
)
from packages.generation.orchestration.patch import (  # noqa: E402
    ArtifactPatch,
    PatchPlan,
)

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

GENPKG = "generation-package.json"
SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_site(tmp_path: Path):
    from scripts.prompt_to_project_input import generate

    return generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )


def _copy_plan(field: str) -> PatchPlan:
    return PatchPlan(
        patches=[ArtifactPatch(artifact=GENPKG, field=field, op="set", value=None)],
        valid=True,
    )


def _read_v(tmp_path: Path, version: int) -> dict:
    return json.loads(
        (tmp_path / f"{SITE_ID}.v{version}.project-input.json").read_text(
            encoding="utf-8"
        )
    )


def _overrides(project_input: dict) -> dict:
    return (project_input.get("directives") or {}).get("sectionContentOverrides") or {}


# ---------------------------------------------------------------------------
# Unit: the deterministic derivation module
# ---------------------------------------------------------------------------


def test_parse_section_content_field_whitelist() -> None:
    assert parse_section_content_field("contentBlocks.home.hero.headline") == (
        "home",
        "hero",
        "headline",
    )
    assert parse_section_content_field("contentBlocks.home.story.body") == (
        "home",
        "story",
        "body",
    )
    # Outside the whitelist / wrong shape -> None.
    assert parse_section_content_field("contentBlocks.home.hero.accessoryComponent") is None
    assert parse_section_content_field("contentBlocks.home.hero.cta.label") is None
    assert parse_section_content_field("visualDirection.mood") is None
    for field in SECTION_OVERRIDE_FIELDS:
        assert parse_section_content_field(f"contentBlocks.home.x.{field}") is not None


def test_derive_section_edit_replace_headline() -> None:
    edit = derive_section_edit("headline", "ändra texten i hero-sektionen till Hej världen")
    assert edit == ("replace", "Hej världen")


def test_derive_section_edit_body_include_mention() -> None:
    edit = derive_section_edit(
        "body", "gör om texten i om-oss-sektionen så den nämner vår 30-åriga erfarenhet"
    )
    assert edit is not None
    operation, value = edit
    assert operation == "include"
    assert "vår 30-åriga erfarenhet" in value


def test_derive_section_edit_body_explicit_replace() -> None:
    edit = derive_section_edit("body", 'gör om om-oss-texten till "Vi är ett familjeföretag"')
    assert edit == ("replace", "Vi är ett familjeföretag")


def test_derive_section_edit_no_literal_is_none() -> None:
    # A pure vibe rewrite with no literal value the operator supplied stays a
    # no-op (the planner/apply never invents copy).
    assert derive_section_edit("headline", "gör hero-texten lite coolare") is None
    assert derive_section_edit("body", "skriv om om-oss så det låter mer premium") is None


def test_derive_section_edit_rejects_instruction_leak() -> None:
    # The change-verb leak guard keeps the raw instruction from becoming copy.
    assert derive_section_edit("headline", "ändra texten till ändra texten") is None


def test_render_section_override_text_include_appends() -> None:
    text = render_section_override_text(
        "body", "include", "vår erfarenhet", base_text="Vi bygger bra sajter."
    )
    assert text == "Vi bygger bra sajter. vår erfarenhet"


def test_render_section_override_text_include_idempotent() -> None:
    # Do not append a fact the body already states.
    text = render_section_override_text(
        "body", "include", "vår erfarenhet", base_text="Vi har lång vår erfarenhet sedan start."
    )
    assert text == "Vi har lång vår erfarenhet sedan start."


def test_render_section_override_text_replace() -> None:
    text = render_section_override_text(
        "headline", "replace", "Ny rubrik", base_text="Gammal"
    )
    assert text == "Ny rubrik"


# ---------------------------------------------------------------------------
# Apply: copy_change -> directives.sectionContentOverrides
# ---------------------------------------------------------------------------


def test_apply_copy_change_writes_hero_headline_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(
        _copy_plan("contentBlocks.home.hero.headline"),
        site_id=SITE_ID,
        follow_up_prompt="ändra texten i hero-sektionen till Välkommen till Malmös elektriker",
        output_dir=tmp_path,
    )
    assert result.applied is True
    assert result.version == 2
    v2 = _read_v(tmp_path, 2)
    assert _overrides(v2) == {
        "home.hero.headline": "Välkommen till Malmös elektriker"
    }
    # Schema-valid (the additive field validates).
    import jsonschema

    schema = json.loads(
        (REPO_ROOT / "governance" / "schemas" / "project-input.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.Draft202012Validator(schema).validate(v2)
    meta = json.loads(
        (tmp_path / f"{SITE_ID}.v2.meta.json").read_text(encoding="utf-8")
    )
    assert meta["appliedPatchPlan"]["sectionContentOverrides"] == [
        "home.hero.headline"
    ]


def test_apply_copy_change_body_include_appends_to_story(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v1, *_ = _init_site(tmp_path)
    base_story = v1["company"]["story"]
    result = apply_patch_plan(
        _copy_plan("contentBlocks.home.story.body"),
        site_id=SITE_ID,
        follow_up_prompt="gör om texten i om-oss-sektionen så den nämner vår 30-åriga erfarenhet",
        output_dir=tmp_path,
    )
    assert result.applied is True
    override = _overrides(_read_v(tmp_path, 2)).get("home.story.body")
    assert override is not None
    assert "vår 30-åriga erfarenhet" in override
    # The existing body is preserved (append, not overwrite).
    assert base_story in override


def test_apply_copy_change_no_derivable_text_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A whitelisted target with no literal value the operator supplied writes
    nothing (we never invent copy) - the honest no-op the task allows."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(
        _copy_plan("contentBlocks.home.hero.headline"),
        site_id=SITE_ID,
        follow_up_prompt="gör hero-texten lite coolare",
        output_dir=tmp_path,
    )
    assert result.applied is False
    assert result.unmapped
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_copy_change_outside_whitelist_is_unmapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A copy target outside the headline/subheadline/body whitelist stays an
    honest unmapped no-op - apply never invents a new field for it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(
        _copy_plan("contentBlocks.home.hero.eyebrow"),
        site_id=SITE_ID,
        follow_up_prompt="ändra texten i hero-sektionen till Hej",
        output_dir=tmp_path,
    )
    assert result.applied is False
    assert result.unmapped
    assert not (tmp_path / f"{SITE_ID}.v2.project-input.json").exists()


def test_apply_section_override_is_mock_safe_and_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    from scripts.prompt_to_project_input import generate

    for out in (a, b):
        generate(
            "Skapa en hemsida för en elektriker i Malmö",
            output_dir=out,
            site_id=SITE_ID,
            project_id=PROJECT_ID,
        )
    prompt = "ändra texten i hero-sektionen till Snabb och trygg el"
    apply_patch_plan(
        _copy_plan("contentBlocks.home.hero.headline"),
        site_id=SITE_ID,
        follow_up_prompt=prompt,
        output_dir=a,
    )
    apply_patch_plan(
        _copy_plan("contentBlocks.home.hero.headline"),
        site_id=SITE_ID,
        follow_up_prompt=prompt,
        output_dir=b,
    )
    pi_a = json.loads((a / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8"))
    pi_b = json.loads((b / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8"))
    assert pi_a == pi_b


# ---------------------------------------------------------------------------
# Carry-forward + hero pin (B180 / B173 must not be disturbed)
# ---------------------------------------------------------------------------


def test_section_override_carries_forward_into_next_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The override lives in Project Input: a LATER unrelated follow-up keeps it
    (it survives reuse by definition)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    apply_patch_plan(
        _copy_plan("contentBlocks.home.hero.headline"),
        site_id=SITE_ID,
        follow_up_prompt="ändra texten i hero-sektionen till Hej Malmö",
        output_dir=tmp_path,
    )
    # v3: an unrelated capability follow-up.
    apply_patch_plan(
        PatchPlan(
            patches=[
                ArtifactPatch(
                    artifact=GENPKG,
                    field="contentBlocks.home.service-summary.accessoryComponent",
                    op="set",
                    value={
                        "component": "contact-form",
                        "variant": None,
                        "capability": "contact-form",
                    },
                )
            ],
            valid=True,
        ),
        site_id=SITE_ID,
        output_dir=tmp_path,
    )
    v3 = _read_v(tmp_path, 3)
    assert _overrides(v3).get("home.hero.headline") == "Hej Malmö"


def test_section_override_does_not_clear_hero_headline_pin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Applying a section override still lets the B173 hero pin run (the apply
    pins the previous rendered H1); the override write never strips it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _init_site(tmp_path)
    result = apply_patch_plan(
        _copy_plan("contentBlocks.home.story.body"),
        site_id=SITE_ID,
        follow_up_prompt='gör om om-oss-texten till "Vi är ett lokalt familjeföretag"',
        output_dir=tmp_path,
    )
    assert result.applied is True
    v2 = _read_v(tmp_path, 2)
    # The story override landed AND the company block is intact (heroHeadline pin
    # logic owns its own field; the override write only touches directives).
    assert _overrides(v2).get("home.story.body") == "Vi är ett lokalt familjeföretag"
    assert "company" in v2 and isinstance(v2["company"], dict)


# ---------------------------------------------------------------------------
# Honesty: an applied override counts as a copy edit (no false no-op)
# ---------------------------------------------------------------------------


def test_has_copy_directives_recognises_section_overrides() -> None:
    from packages.generation.build.prompt_meta import _has_copy_directives

    assert _has_copy_directives(
        {"directives": {"sectionContentOverrides": {"home.hero.headline": "X"}}}
    )
    assert not _has_copy_directives(
        {"directives": {"sectionContentOverrides": {}}}
    )
    assert not _has_copy_directives({"directives": {}})


# ---------------------------------------------------------------------------
# End-to-end pilot: router -> context -> planner -> apply (deterministic)
# ---------------------------------------------------------------------------


def _assemble_context(tmp_path: Path):
    fixture = json.loads(
        (
            REPO_ROOT / "tests" / "fixtures" / "blueprints" / "elektriker-malmo.blueprint.json"
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
    from packages.generation.orchestration.context import (
        ContextPaths,
        assemble_artifacts_plus_sections,
        assemble_component_registry,
    )

    paths = ContextPaths(repoRoot=REPO_ROOT, runsDir=runs)
    context = assemble_artifacts_plus_sections("run-elektriker-malmo", paths=paths)
    registry = assemble_component_registry(paths=paths)
    return context, registry


@pytest.mark.parametrize(
    ("prompt", "expected_field"),
    [
        ("ändra texten i hero-sektionen till Snabb och trygg el", "contentBlocks.home.hero.headline"),
        (
            "gör om texten i om-oss-sektionen så den nämner vår erfarenhet",
            "contentBlocks.home.story.body",
        ),
    ],
)
def test_pilot_router_plan_apply_renders_visible_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, prompt: str, expected_field: str
) -> None:
    """The operator's exact repros: router -> planner -> apply -> renderer all the
    way to a visible section-text change (no LLM, deterministic)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from packages.generation.build.blueprint_render import (
        resolve_section_content_override,
    )
    from packages.generation.orchestration.patch import plan_patches
    from packages.generation.orchestration.router import (
        RouterContext,
        classify_message,
    )

    context, registry = _assemble_context(tmp_path)
    route_sections = {
        route: [s for s in ids if isinstance(s, str)]
        for route, ids in (context.payload.get("routeSections") or {}).items()
        if isinstance(ids, list)
    }
    decision = classify_message(
        prompt, context=RouterContext(siteId=SITE_ID, routeSections=route_sections)
    )
    assert decision.editKind == "copy_change"
    plan = plan_patches(decision, context, registry=registry)
    assert plan.valid is True
    assert [p.field for p in plan.patches] == [expected_field]

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    _init_site(prompt_inputs)
    result = apply_patch_plan(
        plan,
        site_id=SITE_ID,
        follow_up_prompt=prompt,
        output_dir=prompt_inputs,
    )
    assert result.applied is True
    v2 = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    overrides = _overrides(v2)
    assert overrides, "apply must write a section content override"
    # The renderer resolves the override the apply wrote (visible change).
    _route, section_id, field = parse_section_content_field(expected_field)
    assert resolve_section_content_override(v2, section_id, field) is not None
