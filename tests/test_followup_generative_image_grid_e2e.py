"""E2E proof for Generative Component V1 (ADR 0061, component_builder).

Via the REAL user path (``run_followup_chain``) on the local-service-business
example (painter-palma):

- "lägg till 6 bildplatshållare" produces a NEW version that MATERIALISES a new
  components/generated/image-placeholder-grid.tsx and splices it into
  app/page.tsx (import + usage), with an honest appliedVisibleEffect;
- an unrecognised "lägg till en karusell med tre behandlingar" (not in the recipe
  allowlist) is an HONEST no-op (applied False), never a faked component file.

Mock-safe: ``OPENAI_API_KEY`` is removed so the chain is deterministic; the build
runs with ``do_build=False`` (no npm), like the other follow-up E2Es.
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


def _seed_painter_palma(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Init-build the LSB painter-palma example (no npm), isolated dirs."""
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"
    build(
        REPO_ROOT / "examples" / "painter-palma.project-input.json",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir


def _newest_build_dir(generated_dir: Path, site_id: str) -> Path:
    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    assert builds, "expected at least one build directory"
    return builds[-1]


def test_add_image_placeholder_grid_materialises_and_splices(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"lägg till 6 bildplatshållare" -> new version, materialised component file
    + import/usage spliced into app/page.tsx, honest appliedVisibleEffect."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "lägg till 6 bildplatshållare",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["editKind"] == "component_add", result
    assert result["applied"] is True, result
    assert result["appliedVisibleEffect"] is True, result
    # The generative component was NOT falsely reported as unapplied.
    targets = {item.get("target") for item in result.get("unappliedFollowupIntents", [])}
    assert "komponent" not in targets, result

    build_dir = _newest_build_dir(generated_dir, site_id)
    component = (
        build_dir / "components" / "generated" / "image-placeholder-grid.tsx"
    )
    assert component.exists(), "the generative component .tsx must be materialised"
    source = component.read_text(encoding="utf-8")
    assert "GeneratedImagePlaceholderGrid" in source
    assert "Array.from({ length: 6 }" in source

    page = (build_dir / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "@/components/generated/image-placeholder-grid" in page
    assert "<GeneratedImagePlaceholderGrid />" in page


def test_add_image_placeholder_grid_at_top_lands_after_main_before_hero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Placement reuse (full user path): "lägg till 6 bildplatshållare högst upp"
    lands the grid at the TOP of home - after the opening <main> and BEFORE the
    hero section - instead of the default before-</main> slot. Proves the router
    position -> resolver spec -> emit splice wiring end-to-end."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "lägg till 6 bildplatshållare högst upp",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert result["stage"] == "built", result
    assert result["editKind"] == "component_add", result
    assert result["applied"] is True, result

    build_dir = _newest_build_dir(generated_dir, site_id)
    page = (build_dir / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "<GeneratedImagePlaceholderGrid />" in page
    usage = page.index("<GeneratedImagePlaceholderGrid />")
    opening_main = page.index("<main")
    hero = page.index('data-section-id="hero"')
    closing_main = page.index("</main>")
    # The grid is the first child of <main>, before the hero section.
    assert opening_main < usage < hero < closing_main


def test_image_grid_directive_is_sticky_across_a_later_restyle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A grid added in v2 survives an unrelated v3 restyle (sticky directive)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    add = run_followup_chain(
        site_id,
        "lägg till en bildgrid",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert add["stage"] == "built", add

    restyle = run_followup_chain(
        site_id,
        "gör sajten blå",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert restyle["stage"] == "built", restyle

    build_dir = _newest_build_dir(generated_dir, site_id)
    # The component survives the restyle (sticky directive re-materialised).
    assert (
        build_dir / "components" / "generated" / "image-placeholder-grid.tsx"
    ).exists()
    page = (build_dir / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "<GeneratedImagePlaceholderGrid />" in page


def test_repeat_grid_prompt_updates_count_in_place_last_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Matris #1 fix: a second 'lägg till N bildplatshållare' UPDATES the existing
    grid's count in place (last-wins sticky union) - it used to be silently dropped
    by a first-wins union. One grid, count updated 6 -> 8 (no second stacked grid)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    first = run_followup_chain(
        site_id, "lägg till 6 bildplatshållare", do_build=False,
        runs_dir=runs_dir, generated_dir=generated_dir, output_dir=prompt_inputs,
    )
    assert first["stage"] == "built", first
    second = run_followup_chain(
        site_id, "lägg till 8 bildplatshållare", do_build=False,
        runs_dir=runs_dir, generated_dir=generated_dir, output_dir=prompt_inputs,
    )
    assert second["stage"] == "built", second

    build_dir = _newest_build_dir(generated_dir, site_id)
    generated = build_dir / "components" / "generated"
    # Exactly one grid file (stable id) - no second stacked grid.
    assert sorted(p.name for p in generated.glob("*.tsx")) == [
        "image-placeholder-grid.tsx"
    ]
    # Its count was updated in place to 8 (last wins), not stuck at 6.
    source = (generated / "image-placeholder-grid.tsx").read_text(encoding="utf-8")
    assert "Array.from({ length: 8 }" in source
    assert "Array.from({ length: 6 }" not in source


def test_unrecognised_component_add_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unrecognised generative request is an HONEST no-op, never a faked file."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "lägg till en karusell med tre behandlingar",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False, result
    # No component .tsx was faked for an unsupported recipe.
    build_dir = _newest_build_dir(generated_dir, site_id)
    generated = build_dir / "components" / "generated"
    assert not generated.exists() or not list(generated.glob("*.tsx")), result


def test_unsupported_generative_add_emits_generative_unsupported_stage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Stage-kontrakt (C1): när prompten KLASSAS som component_add och namnger en
    igenkänd-men-ostödd generativ familj (en karusell) är utfallet en TERMINAL
    honest no-op med stagen ``generative_unsupported`` (applied False).

    Detta är exakt strängen Viewser-seamen (``TERMINAL_EDIT_NOOP_STAGES`` i
    apps/viewser/app/api/prompt/route.ts) litar på för att rapportera no-op:en
    UTAN att falla igenom till legacy och mynta en meningslös ny version. En
    section-target ("i andra sektionen") gör att den deterministiska routern
    klassar component_add trots att "karusell" inte är ett känt komponent-substantiv
    — samma component_add-väg som konduktorn driver i prod. Lås strängen så en
    omdöpning i build_site.py inte tyst kopplar bort den terminala seamen."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "lägg en karusell i andra sektionen",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["editKind"] == "component_add", result
    assert result["applied"] is False, result
    assert result["stage"] == "generative_unsupported", result
    # No component .tsx was faked for the refused generative family.
    build_dir = _newest_build_dir(generated_dir, site_id)
    generated = build_dir / "components" / "generated"
    assert not generated.exists() or not list(generated.glob("*.tsx")), result
