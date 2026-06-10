"""Sektionsmarkering som följdprompt-signal (ADR 0046).

Låser hela kedjan för "Markera modul i preview":

1. Markörinjektionen: byggda sidor innehåller ``data-section-id`` och
   ``emittedSections`` i build-result.json matchar exakt vad som skrevs
   till snapshoten (suppression-aware facit).
2. Valideringsgrindarna i ``packages/generation/followup/marked_sections``:
   okänd route/sektion droppas med varning — aldrig gissning.
3. CLI-flaggan ``--marked-sections`` + meta-sidecar-spårbarheten
   (``appliedFocusSections``/``droppedFocusSections``).
4. build_site:s defensiva spegling till build-result.json.
5. Viewser-kontraktet (source-locks): zod-fältet i /api/prompt,
   CLI-flaggan i prompt-runner, RouterContext-kontexten i
   router-classify-runner och changeSet-spårbarheten.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.followup.marked_sections import (  # noqa: E402
    MAX_MARKED_SECTIONS,
    focus_note_for_llm,
    parse_marked_sections,
    route_sections_context,
    validate_marked_sections,
)
from tests.support.viewser import VIEWSER_DIR  # noqa: E402

CAFE_BISTRO_INPUT = REPO_ROOT / "examples" / "cafe-bistro.project-input.json"
_SECTION_MARKER = re.compile(r'data-section-id="([a-z0-9-]+)"')

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core


# ---------------------------------------------------------------------------
# 1. Markörinjektion + emittedSections-facit (slice 1-kontraktet)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_build_emits_section_markers_and_emitted_sections_matches_dom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Varje route med sektioner bär data-section-id, och build-result:s
    ``emittedSections`` är exakt de markörer som skrevs till snapshoten."""
    from scripts.build_site import build

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target, run_dir = build(
        CAFE_BISTRO_INPUT,
        do_build=False,
        runs_dir=tmp_path / "runs",
        generated_dir=tmp_path / "generated",
    )

    build_result = json.loads(
        (run_dir / "build-result.json").read_text(encoding="utf-8")
    )
    emitted = build_result.get("emittedSections")
    assert isinstance(emitted, dict) and emitted, (
        "build-result.json saknar emittedSections trots markörinjektion."
    )

    snapshot_app = run_dir / "generated-files" / "app"
    found: dict[str, list[str]] = {}
    for page_file in sorted(snapshot_app.rglob("page.tsx")):
        source = page_file.read_text(encoding="utf-8")
        section_ids: list[str] = []
        for match in _SECTION_MARKER.finditer(source):
            if match.group(1) not in section_ids:
                section_ids.append(match.group(1))
        if section_ids:
            found[page_file.parent.relative_to(snapshot_app).as_posix()] = (
                section_ids
            )
    assert found, "Snapshoten saknar data-section-id-markörer helt."

    # Facit-jämförelse: summan av alla markörer i DOM:en == summan i
    # emittedSections (routeId-mappningen testas via att antalet routes
    # och varje sektionslista matchar någon route i build-result).
    emitted_lists = sorted(tuple(v) for v in emitted.values())
    found_lists = sorted(tuple(v) for v in found.values())
    assert emitted_lists == found_lists, (
        f"emittedSections {emitted_lists} matchar inte DOM-markörerna "
        f"{found_lists}."
    )
    # Hemroutens hero måste alltid vara markerad.
    assert "hero" in emitted.get("home", []), (
        f"home-routens hero saknas i emittedSections: {emitted}"
    )


# ---------------------------------------------------------------------------
# 2. parse_marked_sections — shape-grindarna
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_parse_marked_sections_accepts_valid_payload_and_truncates_note() -> None:
    raw = json.dumps(
        [
            {"routeId": "home", "sectionId": "hero", "note": "X" * 500},
            {"routeId": "services", "sectionId": "service-list"},
        ]
    )
    parsed = parse_marked_sections(raw)
    assert parsed[0]["routeId"] == "home"
    assert parsed[0]["sectionId"] == "hero"
    assert len(parsed[0]["note"]) == 200
    assert "note" not in parsed[1]


@pytest.mark.tooling
def test_parse_marked_sections_dedupes_and_caps_at_max() -> None:
    entries = [{"routeId": "home", "sectionId": "hero"}] * 3 + [
        {"routeId": "home", "sectionId": f"section-{index}"}
        for index in range(10)
    ]
    parsed = parse_marked_sections(json.dumps(entries))
    assert len(parsed) == MAX_MARKED_SECTIONS
    keys = [(entry["routeId"], entry["sectionId"]) for entry in parsed]
    assert len(keys) == len(set(keys)), "Dubbletter ska deduperas."


@pytest.mark.tooling
@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        '{"routeId": "home"}',
        '[{"routeId": "Home!", "sectionId": "hero"}]',
        '[{"routeId": "home", "sectionId": "../escape"}]',
        '[["home", "hero"]]',
    ],
)
def test_parse_marked_sections_rejects_malformed_payloads(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_marked_sections(raw)


# ---------------------------------------------------------------------------
# 3. validate_marked_sections — ärlighetsgrindarna
# ---------------------------------------------------------------------------


def _write_base_run(
    run_dir: Path,
    *,
    emitted_sections: dict[str, list[str]] | None,
    site_plan: dict | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    build_result: dict = {"siteId": "marked-site", "status": "ok"}
    if emitted_sections is not None:
        build_result["emittedSections"] = emitted_sections
    (run_dir / "build-result.json").write_text(
        json.dumps(build_result), encoding="utf-8"
    )
    if site_plan is not None:
        (run_dir / "site-plan.json").write_text(
            json.dumps(site_plan), encoding="utf-8"
        )


@pytest.mark.tooling
def test_validate_against_emitted_sections_facit(tmp_path: Path) -> None:
    """Primärfacit: emittedSections. Okänd route/sektion droppas med skäl."""
    run_dir = tmp_path / "run"
    _write_base_run(
        run_dir,
        emitted_sections={"home": ["hero", "trust-proof"], "services": ["service-list"]},
    )
    applied, dropped = validate_marked_sections(
        [
            {"routeId": "home", "sectionId": "hero"},
            {"routeId": "home", "sectionId": "gallery"},
            {"routeId": "missing-route", "sectionId": "hero"},
        ],
        base_run_dir=run_dir,
    )
    assert applied == [{"routeId": "home", "sectionId": "hero"}]
    assert len(dropped) == 2
    assert all("reason" in entry for entry in dropped)
    assert "renderades inte" in dropped[0]["reason"]
    assert "routePlan" in dropped[1]["reason"]


@pytest.mark.tooling
def test_validate_falls_back_to_site_plan_and_scaffold_sections(
    tmp_path: Path,
) -> None:
    """Äldre base-runs utan emittedSections valideras mot routePlan +
    scaffoldens deklarerade sections.json-vokabulär."""
    run_dir = tmp_path / "run"
    _write_base_run(
        run_dir,
        emitted_sections=None,
        site_plan={
            "scaffoldId": "local-service-business",
            "routePlan": [
                {"id": "home", "path": "/"},
                {"id": "services", "path": "/tjanster"},
            ],
        },
    )
    applied, dropped = validate_marked_sections(
        [
            {"routeId": "home", "sectionId": "hero"},
            {"routeId": "services", "sectionId": "service-list"},
            {"routeId": "services", "sectionId": "not-a-section"},
            {"routeId": "about", "sectionId": "about-story"},
        ],
        base_run_dir=run_dir,
    )
    assert {entry["sectionId"] for entry in applied} == {"hero", "service-list"}
    assert {entry["sectionId"] for entry in dropped} == {
        "not-a-section",
        "about-story",
    }


@pytest.mark.tooling
def test_validate_drops_everything_without_facit(tmp_path: Path) -> None:
    """Inget läsbart facit ⇒ alla markeringar droppas — aldrig gissning."""
    applied, dropped = validate_marked_sections(
        [{"routeId": "home", "sectionId": "hero"}],
        base_run_dir=tmp_path / "does-not-exist",
    )
    assert applied == []
    assert len(dropped) == 1
    assert "verifieras" in dropped[0]["reason"]

    # En run-dir som finns men saknar både build-result och site-plan
    # ger samma ärliga utfall.
    empty_run = tmp_path / "empty-run"
    empty_run.mkdir()
    applied, dropped = validate_marked_sections(
        [{"routeId": "home", "sectionId": "hero"}],
        base_run_dir=empty_run,
    )
    assert applied == [] and len(dropped) == 1


@pytest.mark.tooling
def test_focus_note_and_route_sections_context_render_validated_markings() -> None:
    marked = [
        {"routeId": "home", "sectionId": "hero", "note": "Välkommen till oss"},
        {"routeId": "home", "sectionId": "trust-proof"},
        {"routeId": "services", "sectionId": "service-list"},
    ]
    note = focus_note_for_llm(marked)
    assert note is not None
    assert "Välkommen till oss" in note
    assert "service-list" in note
    assert focus_note_for_llm([]) is None

    grouped = route_sections_context(marked)
    assert grouped == {
        "home": ["hero", "trust-proof"],
        "services": ["service-list"],
    }


# ---------------------------------------------------------------------------
# 4. generate_followup + CLI — meta-spårbarheten
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_generate_followup_writes_applied_and_dropped_focus_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validerade markeringar landar som appliedFocusSections på meta-
    sidecaren; okända droppas till droppedFocusSections med skäl."""
    from scripts.prompt_to_project_input import generate, generate_followup

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en elektriker i Malmö",
        output_dir=tmp_path,
        site_id="marked-site",
        project_id="stable-project-id",
    )
    runs_dir = tmp_path / "runs"
    _write_base_run(
        runs_dir / "20260610T000000.000Z-base-run",
        emitted_sections={"home": ["hero", "trust-proof"]},
    )

    _, meta, _, meta_path = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="marked-site",
        runs_dir=runs_dir,
        marked_sections=[
            {"routeId": "home", "sectionId": "hero", "note": "Rubriken"},
            {"routeId": "home", "sectionId": "gallery"},
        ],
    )

    assert meta["appliedFocusSections"] == [
        {"routeId": "home", "sectionId": "hero", "note": "Rubriken"}
    ]
    assert len(meta["droppedFocusSections"]) == 1
    assert meta["droppedFocusSections"][0]["sectionId"] == "gallery"
    assert "reason" in meta["droppedFocusSections"][0]
    written = json.loads(meta_path.read_text(encoding="utf-8"))
    assert written["appliedFocusSections"] == meta["appliedFocusSections"]


@pytest.mark.tooling
def test_generate_followup_without_markings_keeps_meta_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Utan markeringar är flödet oförändrat — inga nya meta-fält."""
    from scripts.prompt_to_project_input import generate, generate_followup

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    generate(
        "Skapa en hemsida för en målare",
        output_dir=tmp_path,
        site_id="unmarked-site",
        project_id="stable-project-id",
    )
    _, meta, _, _ = generate_followup(
        "Gör tonen varmare.",
        output_dir=tmp_path,
        site_id="unmarked-site",
        runs_dir=tmp_path / "runs",
    )
    assert "appliedFocusSections" not in meta
    assert "droppedFocusSections" not in meta


@pytest.mark.tooling
def test_cli_marked_sections_requires_followup_site_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--marked-sections utan --followup-site-id ska avvisas vid argparse-
    grindarna, före någon disk-/LLM-aktivitet."""
    from scripts.prompt_to_project_input import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prompt_to_project_input.py",
            "--marked-sections",
            '[{"routeId": "home", "sectionId": "hero"}]',
            "--",
            "Skapa en hemsida",
        ],
    )
    with pytest.raises(SystemExit, match="followup-site-id"):
        main()


@pytest.mark.tooling
def test_cli_rejects_malformed_marked_sections_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.prompt_to_project_input import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prompt_to_project_input.py",
            "--followup-site-id",
            "some-site",
            "--marked-sections",
            "not-json",
            "--",
            "Gör tonen varmare.",
        ],
    )
    with pytest.raises(SystemExit, match="marked-sections"):
        main()


# ---------------------------------------------------------------------------
# 5. build_site — defensiv spegling till build-result.json
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_prompt_meta_focus_sections_parses_defensively() -> None:
    """Trasiga sidecar-poster skippas, dubbletter dedupas, strängar cappas
    och listan är bunden — Viewser läser fältet verbatim."""
    from scripts.build_site import _prompt_meta_focus_sections

    meta = {
        "appliedFocusSections": [
            {"routeId": "home", "sectionId": "hero", "note": "N" * 500},
            {"routeId": "home", "sectionId": "hero"},
            {"routeId": "home"},
            "not-a-dict",
            {"routeId": 7, "sectionId": "hero"},
        ]
        + [
            {"routeId": "home", "sectionId": f"s{index}"}
            for index in range(10)
        ]
    }
    posts = _prompt_meta_focus_sections(meta, "appliedFocusSections")
    assert len(posts) == 5, "Listan ska vara bunden till max 5 poster."
    assert posts[0]["routeId"] == "home"
    assert len(posts[0]["note"]) == 200
    keys = [(post["routeId"], post["sectionId"]) for post in posts]
    assert len(keys) == len(set(keys))

    assert _prompt_meta_focus_sections(None, "appliedFocusSections") == []
    assert _prompt_meta_focus_sections({}, "appliedFocusSections") == []
    assert (
        _prompt_meta_focus_sections(
            {"appliedFocusSections": "not-a-list"}, "appliedFocusSections"
        )
        == []
    )


# ---------------------------------------------------------------------------
# 6. classify_message --route-sections (RouterContext-kontexten)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_classify_message_parses_route_sections_defensively() -> None:
    """Trasig payload degraderar till {} — klassificeringen får aldrig
    fällas av prioriteringskontexten."""
    from scripts.classify_message import _parse_route_sections

    assert _parse_route_sections(None) == {}
    assert _parse_route_sections("not-json") == {}
    assert _parse_route_sections('["list"]') == {}
    assert _parse_route_sections('{"home": "hero"}') == {}
    assert _parse_route_sections('{"home": ["hero", 7]}') == {"home": ["hero"]}


# ---------------------------------------------------------------------------
# 7. Viewser-kontraktet (source-locks, samma mönster som test_viewser_*)
# ---------------------------------------------------------------------------


@pytest.mark.tooling
def test_api_prompt_route_validates_marked_sections() -> None:
    """/api/prompt: zod-fältet finns, är cappat till 5 och follow-up-only."""
    text = (VIEWSER_DIR / "app" / "api" / "prompt" / "route.ts").read_text(
        encoding="utf-8"
    )
    assert "MarkedSectionSchema" in text
    assert "markedSections: z.array(MarkedSectionSchema).max(5).optional()" in text
    assert "markedSections kan bara anges i follow-up-läge." in text
    # Markeringarna ska nå BÅDE Python-helpern och router-klassificeringen.
    assert "markedSections: payload.markedSections" in text
    assert "markedSectionsAsRouteSections(payload.markedSections)" in text


@pytest.mark.tooling
def test_prompt_runner_forwards_marked_sections_with_revalidation() -> None:
    """prompt-runner.ts: --marked-sections skickas bara i follow-up-läge
    och id:na re-valideras före spawn (defense-in-depth)."""
    text = (VIEWSER_DIR / "lib" / "prompt-runner.ts").read_text(encoding="utf-8")
    assert '"--marked-sections"' in text
    assert "SECTION_REF_PATTERN" in text
    assert "markedSections" in text


@pytest.mark.tooling
def test_router_classify_runner_forwards_route_sections() -> None:
    text = (VIEWSER_DIR / "lib" / "router-classify-runner.ts").read_text(
        encoding="utf-8"
    )
    assert '"--route-sections"' in text
    assert "routeSections" in text


@pytest.mark.tooling
def test_change_set_carries_applied_focus_sections() -> None:
    """changeSet-spårbarheten: run-change-set läser appliedFocusSections ur
    build-result och RunChangeSet-typen + summarizeChangeSet exponerar dem."""
    change_set_text = (VIEWSER_DIR / "lib" / "run-change-set.ts").read_text(
        encoding="utf-8"
    )
    assert "appliedFocusSections" in change_set_text
    assert "readAppliedFocusSections" in change_set_text
    build_changes_text = (VIEWSER_DIR / "lib" / "build-changes.ts").read_text(
        encoding="utf-8"
    )
    assert "appliedFocusSections" in build_changes_text
    assert "Markerad modul" in build_changes_text
