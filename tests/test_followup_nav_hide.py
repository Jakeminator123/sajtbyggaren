"""E2E proof for nav_hide (Route/Nav Mutation V1, ADR 0060, route_editor).

The NON-DESTRUCTIVE sibling of route_remove, via the REAL user path
(``run_followup_chain``) on the local-service-business example (painter-palma):

- "dölj Om oss i menyn" produces a NEW version where the "Om oss" NAV LINK is
  gone but ``app/om-oss/page.tsx`` STILL exists (the page is kept);
- "dölj Banana i menyn" (unknown page) is an HONEST no-op (no new version,
  stage ``nav_hide_unsupported``);
- repeating an already-hidden nav link is an HONEST no-op;
- ``directives.hiddenNavRoutes`` is STICKY across a later unrelated restyle;
- ``_base_hidden_nav_route_ids`` is non-fatal on a SystemExit (pruned base
  snapshot), exactly like its route_remove sibling.

Mock-safe: ``OPENAI_API_KEY`` is removed so the chain is deterministic; the
build runs with ``do_build=False`` (no npm), like the other follow-up E2Es.
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


def test_hide_about_nav_link_keeps_page_drops_nav(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"dölj Om oss i menyn" -> new version WITHOUT the nav link but WITH the
    page (the key difference from route_remove)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "dölj Om oss i menyn",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["editKind"] == "nav_hide", result

    build_dir = _newest_build_dir(generated_dir, site_id)
    # The page is KEPT (the non-destructive guarantee).
    assert (build_dir / "app" / "om-oss" / "page.tsx").exists()
    assert (build_dir / "app" / "page.tsx").exists()
    # The shared layout nav no longer links to the hidden page.
    layout = (build_dir / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "/om-oss" not in layout
    assert "Om oss" not in layout


def test_unknown_page_nav_hide_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"dölj Banana i menyn" names no resolvable page, so there is no nav link to
    hide: an HONEST no-op (applied False), never a faked nav_hide and never a
    destructive change. (A resolved-but-refused nav_hide -> nav_hide_unsupported
    is covered by the already-hidden repeat test below.)"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "dölj Banana i menyn",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False, result
    # No nav_hide was faked for an unresolvable page, and no page was harmed.
    build_dir = _newest_build_dir(generated_dir, site_id)
    assert (build_dir / "app" / "om-oss" / "page.tsx").exists()


def test_repeat_hide_of_already_hidden_nav_link_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Hiding a nav link that is ALREADY hidden is an HONEST no-op (stage
    nav_hide_unsupported), not a new byte-identical version."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    first = run_followup_chain(
        site_id,
        "dölj Om oss i menyn",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert first["stage"] == "built", first

    second = run_followup_chain(
        site_id,
        "dölj Om oss i menyn",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert second["applied"] is False, second
    assert second["stage"] == "nav_hide_unsupported", second


def test_hidden_nav_route_is_sticky_across_a_later_restyle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A nav link hidden in v2 stays hidden after an unrelated restyle (v3): the
    hiddenNavRoutes directive is sticky, so the link never reappears while the
    page stays present."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    hide = run_followup_chain(
        site_id,
        "dölj Om oss i menyn",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert hide["stage"] == "built", hide

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
    # The page is still present, but its nav link is still hidden (sticky).
    assert (build_dir / "app" / "om-oss" / "page.tsx").exists()
    layout = (build_dir / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "/om-oss" not in layout


def test_base_hidden_nav_route_ids_is_non_fatal_on_systemexit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """read_base_run_snapshot raises SystemExit (a base exception, not Exception)
    for a pruned/missing base snapshot. The already-hidden lookup is a non-fatal
    optimization, so it must swallow that and return an empty set instead of
    crashing the nav_hide build (mirrors _base_disabled_route_ids)."""
    import scripts.prompt_to_project_input as ptpi
    from scripts.build_site import _base_hidden_nav_route_ids

    def _raise_system_exit(*_args: object, **_kwargs: object) -> None:
        raise SystemExit("baseRunId Project Input-snapshot saknas (pruned)")

    monkeypatch.setattr(ptpi, "read_base_run_snapshot", _raise_system_exit)

    result = _base_hidden_nav_route_ids(
        "painter-palma",
        "some-run-id",
        prompt_inputs_dir=tmp_path,
        runs_root=tmp_path,
    )
    assert result == frozenset()
