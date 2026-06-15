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


def _route_plan_ids_and_paths(site_plan: dict) -> tuple[list[str], list[str]]:
    """Return (ids, paths) listed on a site-plan's routePlan."""
    route_plan = site_plan.get("routePlan") or []
    ids = [r.get("id") for r in route_plan if isinstance(r, dict)]
    paths = [r.get("path") for r in route_plan if isinstance(r, dict)]
    return ids, paths


def _only_run_site_plan(runs_dir: Path) -> dict:
    """Read the site-plan.json of the single run present after an init seed."""
    import json

    run_dirs = [p for p in runs_dir.iterdir() if (p / "site-plan.json").is_file()]
    assert len(run_dirs) == 1, f"expected exactly one seeded run, got {run_dirs}"
    return json.loads(
        (run_dirs[0] / "site-plan.json").read_text(encoding="utf-8")
    )


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


def _internal_route_hrefs(text: str) -> list[str]:
    """Return the in-site (``/``-prefixed) hrefs of <a>/<Link> tags in TSX."""
    import re

    link_re = re.compile(
        r"<(?:a|Link)\b[^>]*?\bhref=(?:\"([^\"]+)\"|\{\"([^\"]+)\"\})",
        flags=re.IGNORECASE | re.DOTALL,
    )
    hrefs: list[str] = []
    for match in link_re.finditer(text):
        href = match.group(1) or match.group(2) or ""
        if href.startswith("/"):
            hrefs.append(href)
    return hrefs


def test_remove_contact_page_retargets_ctas_and_drops_dead_links(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Slice B (ADR 0060): "ta bort sidan Kontakt och länkar dit" removes the
    contact page, retargets the site-wide CTAs to mailto:/tel:, and leaves NO
    dead /kontakt link anywhere (the build stays shippable, not degraded)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "ta bort sidan Kontakt och länkar dit",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["editKind"] == "route_remove"
    assert result["appliedVisibleEffect"] is True, result

    build_dir = _newest_build_dir(generated_dir, site_id)
    # The contact page is gone, the other pages stay.
    assert not (build_dir / "app" / "kontakt" / "page.tsx").exists()
    assert (build_dir / "app" / "page.tsx").exists()
    assert (build_dir / "app" / "tjanster" / "page.tsx").exists()

    # No page (incl. the shared layout nav) keeps a dead internal /kontakt link.
    for page in (build_dir / "app").rglob("*.tsx"):
        text = page.read_text(encoding="utf-8")
        assert "/kontakt" not in _internal_route_hrefs(text), (
            f"{page.relative_to(build_dir)} still links to a removed /kontakt route"
        )

    # The home page now retargets its contact CTA to a real channel (mailto:),
    # since painter-palma has a real email - an honest fallback, not a dead link.
    home = (build_dir / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "mailto:hej@malareipalma.es" in home


def test_remove_services_page_is_still_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Slice B keeps home/services protected: "ta bort sidan Tjänster" is an
    honest no-op (only contact is a removable required page)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "ta bort sidan Tjänster",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False, result
    assert result["stage"] == "route_remove_unsupported", result
    build_dir = _newest_build_dir(generated_dir, site_id)
    assert (build_dir / "app" / "tjanster" / "page.tsx").exists()


def test_repeat_removal_of_disabled_page_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#328 finding 7: removing a page that is ALREADY removed is an HONEST no-op
    (stage route_remove_unsupported), not a new byte-identical version. The
    base version's directives.disabledRoutes is consulted so the resolver refuses
    the already-disabled route instead of re-disabling it."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    first = run_followup_chain(
        site_id,
        "ta bort sidan Om oss",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert first["stage"] == "built", first

    second = run_followup_chain(
        site_id,
        "ta bort sidan Om oss",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert second["applied"] is False, second
    assert second["stage"] == "route_remove_unsupported", second


def test_compound_refused_route_is_reported_not_silently_dropped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#328 finding 2: a refused route_remove in a COMPOUND follow-up (where
    another part applies) must NOT be dropped silently. "gör sajten blå och ta
    bort sidan Tjänster" applies the restyle (built) but reports the refused
    services removal on the honest unappliedFollowupIntents channel."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    result = run_followup_chain(
        site_id,
        "gör sajten blå och ta bort sidan Tjänster",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    intents = result.get("unappliedFollowupIntents") or []
    assert any(
        item.get("target") == "sidborttagning"
        and "obligatorisk" in item.get("reason", "").lower()
        for item in intents
    ), intents


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


def test_base_disabled_route_ids_is_non_fatal_on_systemexit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#333 review: read_base_run_snapshot raises SystemExit (a base exception
    that does NOT subclass Exception) for a pruned/missing base snapshot - a real
    retention scenario. The already-disabled lookup (finding 7) is a non-fatal
    optimization, so it must swallow that and return an empty set instead of
    crashing the route_remove build. Guards the explicit (SystemExit, Exception)
    catch in _base_disabled_route_ids."""
    import scripts.prompt_to_project_input as ptpi
    from scripts.build_site import _base_disabled_route_ids

    def _raise_system_exit(*_args: object, **_kwargs: object) -> None:
        raise SystemExit("baseRunId Project Input-snapshot saknas (pruned)")

    monkeypatch.setattr(ptpi, "read_base_run_snapshot", _raise_system_exit)

    result = _base_disabled_route_ids(
        "painter-palma",
        "some-run-id",
        prompt_inputs_dir=tmp_path,
        runs_root=tmp_path,
    )
    assert result == frozenset()


def test_site_plan_artifact_drops_removed_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#332 finding 1 (artifact honesty): after "ta bort sidan Om oss" the NEW
    version's site-plan.json must NOT list the removed /om-oss route. The build
    re-filters defaultRoutes through the single _filter_disabled_routes seam, so
    the rendered site already drops the page (the other tests prove that); this
    guards that the site-plan ARTIFACT reflects the SAME activeRoutes instead of
    claiming a route the site no longer ships."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_painter_palma(tmp_path)

    # Guard: the init build's site-plan lists /om-oss, so the removal below is a
    # real artifact change (not a vacuous pass).
    init_plan = _only_run_site_plan(runs_dir)
    init_ids, init_paths = _route_plan_ids_and_paths(init_plan)
    assert "about" in init_ids
    assert "/om-oss" in init_paths

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

    import json

    new_run_dir = runs_dir / result["runId"]
    new_plan = json.loads(
        (new_run_dir / "site-plan.json").read_text(encoding="utf-8")
    )
    new_ids, new_paths = _route_plan_ids_and_paths(new_plan)
    # The removed route is gone from the artifact...
    assert "about" not in new_ids, new_plan["routePlan"]
    assert "/om-oss" not in new_paths, new_plan["routePlan"]
    # ...and the surviving routes still stand (no over-pruning).
    assert "/" in new_paths
    assert "/tjanster" in new_paths
    assert "/kontakt" in new_paths
