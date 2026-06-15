"""E2E proof for Route/Nav Mutation V1 (route_remove, ADR 0060).

Via the REAL user path (``run_followup_chain``) on the local-service-business
example (painter-palma):

- "ta bort sidan Om oss" produces a NEW version WITHOUT ``app/om-oss/page.tsx``
  and WITHOUT the "Om oss" nav link (appliedVisibleEffect True);
- "ta bort sidan Banana" (unknown page) is an HONEST no-op (no new version,
  stage ``route_remove_unsupported``);
- "ta bort sidan Kontakt" (required page in Slice A) is an HONEST no-op - the
  contact page and its site-wide CTAs stay intact;
- ``directives.disabledRoutes`` is STICKY: a later unrelated restyle keeps the
  page removed (it never reappears).

Mock-safe: ``OPENAI_API_KEY`` is removed so brief/plan fall back to the mock and
the router/context/patch/apply chain is deterministic; the build runs with
``do_build=False`` (no npm), like the other follow-up chain E2Es.
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


def test_init_build_has_about_page() -> None:
    """Guard: painter-palma's init build emits /om-oss (so the removal below is a
    real change, not a vacuous pass)."""
    import tempfile

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _prompt_inputs, _runs, generated_dir = _seed_painter_palma(tmp)
        build_dir = _newest_build_dir(generated_dir, "painter-palma")
        assert (build_dir / "app" / "om-oss" / "page.tsx").exists()


def test_remove_about_page_drops_file_and_nav(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"ta bort sidan Om oss" -> new version without /om-oss + without the nav
    link, appliedVisibleEffect True."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "ta bort sidan Om oss och länken i headern",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["editKind"] == "route_remove"
    assert result["appliedVisibleEffect"] is True, result

    build_dir = _newest_build_dir(generated_dir, site_id)
    assert not (build_dir / "app" / "om-oss" / "page.tsx").exists()
    # The other pages still exist.
    assert (build_dir / "app" / "page.tsx").exists()
    assert (build_dir / "app" / "kontakt" / "page.tsx").exists()
    # The nav (shared layout) no longer links to the removed page.
    layout = (build_dir / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "/om-oss" not in layout
    assert "Om oss" not in layout


def test_unknown_page_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"ta bort sidan Banana" -> honest no-op, no new version, no false success."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "ta bort sidan Banana",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False, result
    assert result["stage"] == "route_remove_unsupported", result
    assert result["editKind"] == "route_remove"


def test_required_contact_page_is_kept_in_slice_a(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """"ta bort sidan Kontakt" -> honest no-op in Slice A (required page kept).

    The contact page + its site-wide CTAs stay intact; removing it + retargeting
    the CTAs is Slice B."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "ta bort sidan Kontakt",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False, result
    assert result["stage"] == "route_remove_unsupported", result
    build_dir = _newest_build_dir(generated_dir, site_id)
    # The contact page is still there (init build, untouched by the no-op).
    assert (build_dir / "app" / "kontakt" / "page.tsx").exists()


def test_disabled_route_is_sticky_across_a_later_restyle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A page removed in v2 stays removed after an unrelated restyle (v3): the
    disabledRoutes directive is sticky, so the page never reappears."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    remove = run_followup_chain(
        site_id,
        "ta bort sidan Om oss",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert remove["stage"] == "built", remove

    restyle = run_followup_chain(
        site_id,
        "gör sajten blå",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert restyle["stage"] == "built", restyle
    # The restyle minted a fresh version, and /om-oss is STILL gone (sticky).
    build_dir = _newest_build_dir(generated_dir, site_id)
    assert not (build_dir / "app" / "om-oss" / "page.tsx").exists()
