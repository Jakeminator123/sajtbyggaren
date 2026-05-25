"""Builder regression for the restaurant-hospitality scaffold (Issue #90).

Before this change, a full build of a Project Input pinned to
``scaffoldId=restaurant-hospitality`` exited with a SystemExit from
``scripts/build_site.py:write_pages`` because the ``menu`` and
``booking`` route ids had no registered renderer. These tests verify
that the page files are now produced and that ``app/layout.tsx``
exposes them in the navigation. ``do_build=False`` keeps the suite
fast (no npm install / npm run build) — full build coverage lives in
the manual ``python scripts/run_eval_suite.py full`` flow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CAFE_BISTRO_INPUT = REPO_ROOT / "examples" / "cafe-bistro.project-input.json"


@pytest.mark.tooling
def test_restaurant_build_emits_menu_and_booking_routes(
    tmp_path: Path, monkeypatch
) -> None:
    """``write_pages`` must write the new ``menu`` and ``booking`` pages.

    Before Issue #90 the scaffold's route ids ``menu`` and ``booking``
    triggered the catch-all SystemExit branch in ``write_pages``.
    This test fails loudly if either of the two renderers is removed
    or unwired from the dispatcher.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert CAFE_BISTRO_INPUT.exists(), "cafe-bistro fixture must exist"

    target, _run_dir = build(
        CAFE_BISTRO_INPUT,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    # The five scaffold default routes (home / menu / booking / about / contact)
    # all need an emitted page file. The slugs come from
    # packages/generation/orchestration/scaffolds/restaurant-hospitality/routes.json
    # and must stay in sync with that file.
    expected_pages = [
        target / "app" / "page.tsx",
        target / "app" / "meny" / "page.tsx",
        target / "app" / "bokning" / "page.tsx",
        target / "app" / "om-oss" / "page.tsx",
        target / "app" / "hitta-hit" / "page.tsx",
    ]
    for page in expected_pages:
        assert page.exists(), f"Expected page missing: {page.relative_to(target)}"


@pytest.mark.tooling
def test_restaurant_build_writes_layout_with_menu_and_booking_nav(
    tmp_path: Path, monkeypatch
) -> None:
    """Layout nav must surface Swedish labels for the new routes.

    ``_NAV_LABEL_BY_ROUTE_ID`` is the canonical mapping; without
    entries for ``menu`` / ``booking`` the layout would fall back to
    title-cased slugs ("Meny" / "Bokning"). We assert the curated
    Swedish labels so a future change to the dictionary fails this
    test rather than silently regressing the nav copy.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target, _run_dir = build(
        CAFE_BISTRO_INPUT,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    layout = (target / "app" / "layout.tsx").read_text(encoding="utf-8")
    assert "Meny" in layout, "Layout nav must include the 'Meny' label"
    assert "Boka bord" in layout, "Layout nav must include the 'Boka bord' label"
    assert "/meny" in layout, "Layout nav must link to /meny"
    assert "/bokning" in layout, "Layout nav must link to /bokning"


@pytest.mark.tooling
def test_restaurant_menu_page_renders_service_items_as_menu_cards(
    tmp_path: Path, monkeypatch
) -> None:
    """Menu items come from the dossier's ``services`` array.

    The project-input schema's top-level ``additionalProperties: false``
    blocks a dedicated ``menu`` field, so the fixture reuses the
    ``services`` array as menu items. This test guards the mapping:
    every cafe-bistro service label must appear in the rendered
    ``app/meny/page.tsx`` so a future schema rename does not silently
    break the menu page.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target, _run_dir = build(
        CAFE_BISTRO_INPUT,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    menu_page = (target / "app" / "meny" / "page.tsx").read_text(encoding="utf-8")
    fixture = json.loads(CAFE_BISTRO_INPUT.read_text(encoding="utf-8"))
    for item in fixture["services"]:
        assert item["label"] in menu_page, (
            f"Menu page must surface the label {item['label']!r} from services[]"
        )


@pytest.mark.tooling
def test_restaurant_booking_page_renders_contact_fallbacks(
    tmp_path: Path, monkeypatch
) -> None:
    """Booking page must expose tel: + mailto: + opening hours.

    Per Issue #90 we do not embed a third-party booking widget; the
    page is a static reservation fallback. The dossier's
    ``contact.phone``, ``contact.email`` and ``contact.openingHours``
    must therefore land in the rendered page so a hungry visitor can
    actually book a table without a widget.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target, _run_dir = build(
        CAFE_BISTRO_INPUT,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    booking_page = (target / "app" / "bokning" / "page.tsx").read_text(encoding="utf-8")
    fixture = json.loads(CAFE_BISTRO_INPUT.read_text(encoding="utf-8"))
    contact = fixture["contact"]
    assert contact["phone"] in booking_page
    assert contact["email"] in booking_page
    # Opening hours appear verbatim in the rendered card; assert a stable
    # substring rather than the full string so trivial whitespace changes
    # do not break the test.
    assert "Tis–Tor 17:00–22:00" in booking_page


@pytest.mark.tooling
def test_restaurant_build_records_scaffold_and_variant_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    """``build-result.json`` must reflect the pinned scaffold/variant.

    Regression net so a future planner change cannot silently flip
    the cafe-bistro fixture off restaurant-hospitality without this
    test catching it.
    """
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _target, run_dir = build(
        CAFE_BISTRO_INPUT,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    result = json.loads((run_dir / "build-result.json").read_text(encoding="utf-8"))
    assert result["siteId"] == "cafe-bistro"
    assert result["scaffoldId"] == "restaurant-hospitality"
    assert result["variantId"] == "warm-bistro"
    assert result["status"] == "skipped", "do_build=False must record status=skipped"
