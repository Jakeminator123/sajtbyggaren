"""Minimal end-to-end test for the kor-7 CLI follow-up chain + critic wiring.

This is the integration-gap proof for the heavy-LLM follow-up bridge: it shows
that a single follow-up prompt, run through the *real* user path
(``run_followup_chain`` / ``scripts/build_site.py --followup``), drives the whole
capability chain end-to-end:

    prompt -> init build -> capability-backed follow-up prompt
    -> router -> context -> patch plan -> apply (new immutable v2)
    -> targeted render -> honest appliedVisibleEffect

and that the kor-4a deterministic critic is now actually filled in
``quality-result.json`` on a real build (it was always ``None`` before the
gate-wiring fix because the build path never passed the blueprint).

Mock-safe: ``OPENAI_API_KEY`` is removed so brief/plan fall back to the mock and
the router/context/patch/apply modules (all deterministic) never call an LLM.
The build runs with ``do_build=False`` (no npm), exactly like
``tests/test_targeted_render.py``'s real-chain test, so the suite stays Node-free.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Core-lane (docs/testing.md): kärnflödet prompt -> bygge -> följdprompt.
pytestmark = pytest.mark.core

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SITE_ID = "electrician-malmo"
PROJECT_ID = "stable-project-id"
INIT_PROMPT = "Skapa en hemsida för en elektriker i Malmö"
# A capability-backed follow-up: "add a contact form in the last section".
# "sista sektionen" resolves via the assembled routeSections to a concrete
# section, and contact_form maps to the contact-form capability (has a dossier),
# so the planner emits a valid named-field patch.
CAPABILITY_FOLLOWUP = "lägg till ett kontaktformulär i sista sektionen"


def _seed_init_build(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """Generate v1 for the baseline prompt and run one init build (no npm).

    Returns (prompt_inputs, runs_dir, generated_dir, base_run_id).
    """
    from scripts.build_site import build
    from scripts.prompt_to_project_input import generate

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"

    _pi, _meta, v1_path, _ = generate(
        INIT_PROMPT,
        output_dir=prompt_inputs,
        site_id=SITE_ID,
        project_id=PROJECT_ID,
    )
    _target, run_dir = build(
        v1_path, do_build=False, runs_dir=runs_dir, generated_dir=generated_dir
    )
    return prompt_inputs, runs_dir, generated_dir, run_dir.name


def _critic_of(run_dir: Path) -> dict | None:
    payload = json.loads((run_dir / "quality-result.json").read_text(encoding="utf-8"))
    return payload.get("critic")


def test_init_build_fills_critic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Gate-wiring: a real build now fills quality-result.json:critic (was None)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _pin, runs_dir, _gen, base_run_id = _seed_init_build(tmp_path)

    critic = _critic_of(runs_dir / base_run_id)
    assert critic is not None, "critic must be filled in a real build (kor-4a wiring)"
    assert critic["source"] == "deterministic-v0"
    assert isinstance(critic["score"], int)
    assert 0 <= critic["score"] <= 100

    # The critic is a non-blocking warning lane: it logs exactly one event and
    # never changes the gate status aggregation.
    events = [
        json.loads(line)
        for line in (runs_dir / base_run_id / "trace.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    critic_events = [e for e in events if e.get("event") == "critic.evaluated"]
    assert len(critic_events) == 1
    assert critic_events[0]["status"] == "warning"


def test_followup_chain_applies_capability_and_creates_new_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A capability follow-up goes router->context->patch->apply->targeted build."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(tmp_path)
    v1_run_before = sorted((runs_dir / base_run_id).rglob("*"))
    v1_hashes = {
        str(p.relative_to(runs_dir / base_run_id)): p.read_bytes()
        for p in v1_run_before
        if p.is_file()
    }

    result = run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    # Chain ran all the way to the targeted build.
    assert result["stage"] == "built"
    assert result["applied"] is True
    assert result["messageKind"] == "edit_instruction"
    assert result["editKind"] == "component_add"

    # Apply created the next immutable version, identity preserved.
    assert result["version"] == 2
    assert result["previousVersion"] == 1
    assert result["appliedCapabilities"], "a capability was applied"
    assert result["appliedCapabilities"][0]["capability"] == "contact-form"
    v2_path = prompt_inputs / f"{SITE_ID}.v2.project-input.json"
    assert v2_path.exists()
    assert Path(result["projectInputPath"]) == v2_path

    v2_pi = json.loads(v2_path.read_text(encoding="utf-8"))
    assert "contact-form" in v2_pi.get("requestedCapabilities", [])

    # Targeted render produced an HONEST signal. do_build=False -> status
    # skipped -> no preview refresh, no false success (same contract as
    # test_targeted_render's real-chain test).
    assert result["affectedRoutes"] == ["home"]
    assert result["buildStatus"] == "skipped"
    assert result["outcome"] == "skipped"
    assert result["appliedVisibleEffect"] is False
    assert result["previewShouldRefresh"] is False

    # A distinct new run was created and the v1 run is byte-for-byte untouched.
    new_run = runs_dir / result["runId"]
    assert new_run.is_dir()
    assert result["runId"] != base_run_id
    for rel, raw in v1_hashes.items():
        assert (runs_dir / base_run_id / rel).read_bytes() == raw

    # The new version's build also fills the critic (gate-wiring on the v2 build).
    assert _critic_of(new_run) is not None


def test_followup_chain_restyle_applies_theme_and_creates_new_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A visual_style restyle goes router->(empty plan + theme)->apply->build.

    The router classifies "ändra färgen till rosa" as visual_style/edit_instruction;
    the patch planner has no capability patch, but the chain extracts an explicit
    theme directive and routes it through apply so brand.primaryColorHex lands in
    the next immutable version (rendered by patch_globals_css on rebuild)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        "ändra färgen till rosa",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built"
    assert result["applied"] is True
    assert result["editKind"] == "visual_style"
    assert result["version"] == 2

    v2_path = prompt_inputs / f"{SITE_ID}.v2.project-input.json"
    assert v2_path.exists()
    v2_pi = json.loads(v2_path.read_text(encoding="utf-8"))
    assert v2_pi["brand"]["primaryColorHex"] == "#db2777"
    # No capability was applied (restyle is theme-only).
    assert result["appliedCapabilities"] == []


def test_followup_chain_capability_followup_does_not_restyle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Gate: a non-visual_style edit never restyles. A component_add follow-up
    (no restyle intent) must leave brand untouched even if it mentioned a colour
    incidentally - the theme is applied only for a router visual_style intent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["editKind"] == "component_add"
    assert result["applied"] is True
    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    # The capability landed, but no brand restyle leaked in.
    assert "contact-form" in v2_pi.get("requestedCapabilities", [])
    assert "primaryColorHex" not in (v2_pi.get("brand") or {})


@pytest.mark.parametrize(
    "prompt,capability,dossier",
    [
        ("lägg till en sektion om garantier", "guarantees", "trust-guarantees"),
        ("lägg till en FAQ-sektion", "faq-section", "faq-accordion"),
        ("lägg till en team-sektion", "team-section", "team-roster"),
        ("lägg till en sektion med recensioner", "reviews", "reviews-display"),
        # section_builder broadening (2026-06-08): the module-drag-and-drop types
        # that REUSE an existing Dossier + renderer. The slug the router emits maps
        # to a capability-map.v1.json capability with a default Dossier; map->location.
        ("lägg till en galleri-sektion", "gallery", "image-gallery"),
        ("lägg till en sektion med priser", "pricing", "pricing-table"),
        ("lägg till en öppettider-sektion", "hours", "opening-hours"),
        ("lägg till en sektion med en karta", "location", "map-embed"),
        ("lägg till en kontaktformulär-sektion", "contact-form", "mailto-contact-form"),
    ],
)
def test_followup_chain_section_add_mounts_dossier_and_creates_new_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    prompt: str,
    capability: str,
    dossier: str,
) -> None:
    """A sanctioned section_add goes router -> (section capability) -> apply ->
    targeted build: the capability lands in requestedCapabilities and its
    implementing dossier is secured in selectedDossiers.required (the SAME apply
    machinery component_add uses), creating the next immutable version.

    Visible-render slice (faq/team on the local-service-business scaffold): a
    section type with a dedicated, grounded visible route is surfaced as a NEW
    page, so the honest file-diff reports appliedVisibleEffect=true and the
    affected route is the surfaced page. Every other type stays mount-only
    (appliedVisibleEffect=false, home-defaulted) - the honest contract."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        prompt,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["applied"] is True
    assert result["editKind"] == "section_add"
    assert result["version"] == 2
    applied = [c["capability"] for c in result["appliedCapabilities"]]
    assert capability in applied

    v2_pi = json.loads(
        (prompt_inputs / f"{SITE_ID}.v2.project-input.json").read_text(encoding="utf-8")
    )
    assert capability in v2_pi.get("requestedCapabilities", [])
    required = (v2_pi.get("selectedDossiers") or {}).get("required") or []
    assert dossier in required, f"{dossier} must be mounted in selectedDossiers.required"

    # do_build=False -> never a preview refresh (skipped is not shippable),
    # regardless of whether the section became visible.
    assert result["previewShouldRefresh"] is False

    # Visible iff the capability has a dedicated route AND that route's grounded
    # content exists in the built version AND the scaffold emits wizard routes.
    visible_route = {"faq-section": "faq", "team-section": "team"}.get(capability)
    scaffold_is_route_capable = v2_pi.get("scaffoldId") == "local-service-business"
    team = ((v2_pi.get("company") or {}).get("team")) or []
    team_grounded = any(
        isinstance(m, dict) and str(m.get("name") or "").strip() for m in team
    )
    is_grounded = capability != "team-section" or team_grounded
    if visible_route and scaffold_is_route_capable and is_grounded:
        assert result["appliedVisibleEffect"] is True, result
        assert result["affectedRoutes"] == [visible_route]
    else:
        # Mount-only: no dedicated visible route (or no grounded content / a
        # scaffold that does not emit the route) -> honest no visible effect,
        # affected route defaults to home.
        assert result["appliedVisibleEffect"] is False, result
        assert result["affectedRoutes"] == ["home"]


def _seed_example_init_build(
    tmp_path: Path, example_filename: str, site_id: str
) -> tuple[Path, Path, Path]:
    """Init-build a committed example into isolated dirs, persisting the
    prompt-inputs sidecar so a follow-up can find it on disk.

    Returns (prompt_inputs, runs_dir, generated_dir). Mock-safe (no npm).
    """
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"
    example = REPO_ROOT / "examples" / example_filename
    build(
        example,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir


def _newest_build_app_pages(generated_dir: Path, site_id: str) -> list[str]:
    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    assert builds, "expected at least one build directory"
    app = builds[-1] / "app"
    return sorted(
        p.relative_to(app).as_posix() for p in app.rglob("page.tsx")
    )


def test_followup_chain_section_add_faq_and_team_render_visibly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end visible-render proof: on the local-service-business scaffold a
    "lägg till en FAQ-sektion" / "lägg till en team-sektion" follow-up surfaces a
    NEW grounded dedicated page, so the honest file-diff reports
    appliedVisibleEffect=true and the affected route is the surfaced page.

    Uses the painter-palma example because it is LSB and carries grounded
    company.team (so /team is honest, not a placeholder)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_example_init_build(
        tmp_path, "painter-palma.project-input.json", site_id
    )
    # Baseline: no /faq, no /team yet.
    base_pages = _newest_build_app_pages(generated_dir, site_id)
    assert "faq/page.tsx" not in base_pages
    assert "team/page.tsx" not in base_pages

    faq = run_followup_chain(
        site_id,
        "lägg till en FAQ-sektion",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert faq["stage"] == "built"
    assert faq["editKind"] == "section_add"
    assert faq["appliedVisibleEffect"] is True, faq
    assert faq["affectedRoutes"] == ["faq"]
    assert "faq/page.tsx" in _newest_build_app_pages(generated_dir, site_id)

    team = run_followup_chain(
        site_id,
        "lägg till en team-sektion",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert team["appliedVisibleEffect"] is True, team
    assert team["affectedRoutes"] == ["team"]
    team_page = (
        generated_dir
        / site_id
        / "builds"
    )
    newest = sorted(team_page.glob("*"))[-1] / "app" / "team" / "page.tsx"
    markup = newest.read_text(encoding="utf-8")
    # Grounded in company.team from the example - no invented people.
    assert "Anders Holm" in markup
    assert "Lina Sjöberg" in markup


def test_followup_chain_section_add_guarantees_stays_mount_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """guarantees has no dedicated visible route, so a "lägg till garantier"
    follow-up mounts the capability + dossier but renders no new page: honest
    appliedVisibleEffect=false, no preview refresh (mount-only kept)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_example_init_build(
        tmp_path, "painter-palma.project-input.json", site_id
    )
    base_pages = _newest_build_app_pages(generated_dir, site_id)

    result = run_followup_chain(
        site_id,
        "lägg till en sektion om garantier",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert result["applied"] is True
    assert result["editKind"] == "section_add"
    assert "guarantees" in [c["capability"] for c in result["appliedCapabilities"]]
    # Mount-only: capability mounted, but no new page and no visible effect.
    assert result["appliedVisibleEffect"] is False
    assert result["previewShouldRefresh"] is False
    assert _newest_build_app_pages(generated_dir, site_id) == base_pages


def test_followup_chain_section_add_hours_renders_inline_on_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR 0038 inline-render proof: a "lägg till en öppettider-sektion"
    follow-up on the local-service-business scaffold injects the opening-hours
    section INLINE as a block on the home page (no new page), so the honest
    file-diff reports appliedVisibleEffect=true with affectedRoutes=["home"].

    Uses painter-palma because it is LSB and carries REAL grounded
    contact.openingHours ("Mån–Fre 08:00–17:00"), so the grounded-content gate
    passes and the section is not a placeholder."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_example_init_build(
        tmp_path, "painter-palma.project-input.json", site_id
    )
    base_pages = _newest_build_app_pages(generated_dir, site_id)

    result = run_followup_chain(
        site_id,
        "lägg till en öppettider-sektion",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["editKind"] == "section_add"
    assert "hours" in [c["capability"] for c in result["appliedCapabilities"]]
    # Inline render: visible effect on home, no new dedicated page.
    assert result["appliedVisibleEffect"] is True, result
    assert result["affectedRoutes"] == ["home"]
    assert _newest_build_app_pages(generated_dir, site_id) == base_pages, (
        "hours renders inline on home, so the page LIST must be unchanged "
        "(no /oppettider page created)."
    )

    # The directive landed on v2's Project Input and the home body shows the
    # grounded opening-hours card.
    v2_pi = json.loads(
        (prompt_inputs / f"{site_id}.v2.project-input.json").read_text(encoding="utf-8")
    )
    mounted = (v2_pi.get("directives") or {}).get("mountedSections") or []
    assert any(
        m.get("sectionId") == "hours-summary" and m.get("routeId") == "home"
        for m in mounted
    ), mounted
    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    home_markup = (builds[-1] / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "Öppettider" in home_markup
    assert "Mån–Fre 08:00–17:00" in home_markup


def test_followup_chain_inline_section_survives_later_unrelated_followup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR 0038 compose-across-versions: an inline section mounted in v2 must
    STILL render in a v3 that does an unrelated follow-up (e.g. a restyle).

    Regression guard for the apply reconciliation bug: ``mountedSections`` is
    rebuilt from the MERGED version's full ``requestedCapabilities`` (the hours
    capability is still requested in v3), so the hours block is not silently
    dropped just because the v3 apply call resolved no NEW section capability."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_example_init_build(
        tmp_path, "painter-palma.project-input.json", site_id
    )

    # v2: add the hours section inline.
    v2 = run_followup_chain(
        site_id,
        "lägg till en öppettider-sektion",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert v2["appliedVisibleEffect"] is True, v2

    # v3: an unrelated restyle that resolves NO new section capability.
    v3 = run_followup_chain(
        site_id,
        "gör färgen mörkblå",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert v3["stage"] == "built", v3
    assert v3["version"] == 3

    v3_pi = json.loads(
        (prompt_inputs / f"{site_id}.v3.project-input.json").read_text(encoding="utf-8")
    )
    mounted = (v3_pi.get("directives") or {}).get("mountedSections") or []
    assert any(
        m.get("sectionId") == "hours-summary" for m in mounted
    ), f"hours-summary must persist into v3, got {mounted}"

    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    home_markup = (builds[-1] / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "Öppettider" in home_markup, (
        "the inline hours section must still render on v3's home page (it was "
        "not silently dropped by the unrelated restyle follow-up)."
    )


def test_followup_chain_section_add_hours_position_top(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR 0038 slice 2: "lägg till en öppettider-sektion överst" places the
    injected hours block at the TOP of the home order (right after the hero),
    not the default before-contact slot. Proven by the hours card rendering
    before the services-summary block in app/page.tsx."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_example_init_build(
        tmp_path, "painter-palma.project-input.json", site_id
    )

    result = run_followup_chain(
        site_id,
        "lägg till en öppettider-sektion överst",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert result["stage"] == "built", result
    assert result["appliedVisibleEffect"] is True, result

    v2_pi = json.loads(
        (prompt_inputs / f"{site_id}.v2.project-input.json").read_text(encoding="utf-8")
    )
    mounted = (v2_pi.get("directives") or {}).get("mountedSections") or []
    assert mounted and mounted[0].get("position") == "top", mounted

    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    home_markup = (builds[-1] / "app" / "page.tsx").read_text(encoding="utf-8")
    hours_idx = home_markup.find("Öppettider")
    # service-summary renders the services grid; the hours block must precede it.
    services_idx = home_markup.find("Inomhusmålning")
    assert 0 < hours_idx < services_idx, (
        "position=top must place the hours block right after the hero, before "
        "the services summary."
    )


def _seed_example_with_gallery_init_build(
    tmp_path: Path, example_filename: str, site_id: str
) -> tuple[Path, Path, Path]:
    """Like ``_seed_example_init_build`` but with two gallery assetRefs added,
    so the home gallery section is grounded (ADR 0042 move tests). Two images
    because a non-empty company.story consumes the first one (the home gallery
    renderer skips it), and a single image would suppress the section. The
    physical bytes are absent on purpose — ``copy_operator_uploads`` skips a
    missing asset without aborting, and the renderer still emits the section
    markup the move assertions need."""
    from scripts.build_site import build

    prompt_inputs = tmp_path / "prompt-inputs"
    prompt_inputs.mkdir()
    runs_dir = tmp_path / "runs"
    generated_dir = tmp_path / "gen"
    example = json.loads(
        (REPO_ROOT / "examples" / example_filename).read_text(encoding="utf-8")
    )
    example["gallery"] = [
        {
            "assetId": f"TESTGALLERY{index}",
            "filename": f"galleri-{index}.webp",
            "mimeType": "image/webp",
            "sizeBytes": 1000,
            "role": "gallery",
            "alt": f"Galleribild {index}",
        }
        for index in (1, 2)
    ]
    dossier_path = tmp_path / example_filename
    dossier_path.write_text(
        json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    build(
        dossier_path,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        prompt_inputs_dir=prompt_inputs,
    )
    return prompt_inputs, runs_dir, generated_dir


def test_followup_chain_section_add_gallery_moves_to_top(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR 0042 (slice 4) move-proof: "lägg till en galleri-sektion överst" on
    a site whose home ALREADY renders the gallery mid-page (grounded images)
    must MOVE the section to right after the hero — rendered exactly once —
    and report an honest appliedVisibleEffect=true on home."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "painter-palma"
    prompt_inputs, runs_dir, generated_dir = _seed_example_with_gallery_init_build(
        tmp_path, "painter-palma.project-input.json", site_id
    )
    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    base_home = (builds[-1] / "app" / "page.tsx").read_text(encoding="utf-8")
    # Baseline: gallery renders at its default mid-page slot (after services).
    assert 0 < base_home.find("Inomhusmålning") < base_home.find(
        "Ett urval från projekten"
    )
    base_pages = _newest_build_app_pages(generated_dir, site_id)

    result = run_followup_chain(
        site_id,
        "lägg till en galleri-sektion överst",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["editKind"] == "section_add"
    assert "gallery" in [c["capability"] for c in result["appliedCapabilities"]]
    # The move changes home bytes -> honest visible effect, no new page.
    assert result["appliedVisibleEffect"] is True, result
    assert result["affectedRoutes"] == ["home"]
    assert _newest_build_app_pages(generated_dir, site_id) == base_pages

    v2_pi = json.loads(
        (prompt_inputs / f"{site_id}.v2.project-input.json").read_text(encoding="utf-8")
    )
    mounted = (v2_pi.get("directives") or {}).get("mountedSections") or []
    assert any(
        m.get("sectionId") == "gallery"
        and m.get("routeId") == "home"
        and m.get("position") == "top"
        for m in mounted
    ), mounted

    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    home_markup = (builds[-1] / "app" / "page.tsx").read_text(encoding="utf-8")
    gallery_idx = home_markup.find("Ett urval från projekten")
    services_idx = home_markup.find("Inomhusmålning")
    assert 0 < gallery_idx < services_idx, (
        "position=top must MOVE the gallery section above the services summary."
    )
    assert home_markup.count("Ett urval från projekten") == 1, (
        "the moved gallery must render exactly once (move, not duplicate)."
    )


def test_followup_chain_section_add_gallery_moves_on_ecommerce_lite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """ADR 0042 scaffold gate, E2E: the same gallery move works on the
    ecommerce-lite scaffold (operator scenario 2026-06-10: drag-and-drop
    "galleri överst" on the 1753-skincare site changed nothing because gallery
    was mount-only outside local-service-business)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    site_id = "atelje-bird"
    prompt_inputs, runs_dir, generated_dir = _seed_example_with_gallery_init_build(
        tmp_path, "atelje-bird.project-input.json", site_id
    )

    result = run_followup_chain(
        site_id,
        "lägg till en galleri-sektion överst",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["stage"] == "built", result
    assert result["appliedVisibleEffect"] is True, result
    assert result["affectedRoutes"] == ["home"]

    builds = sorted((generated_dir / site_id / "builds").glob("*"))
    home_markup = (builds[-1] / "app" / "page.tsx").read_text(encoding="utf-8")
    gallery_idx = home_markup.find("Ett urval från projekten")
    assert gallery_idx > 0, "gallery must render on the ecommerce-lite home"
    # The injected gallery image markup must precede the listing section.
    listing_idx = home_markup.find("Vårt sortiment")
    assert listing_idx > 0, "ecommerce-lite home must keep its listing section"
    assert gallery_idx < listing_idx, (
        "position=top must land the gallery before the product listing."
    )
    assert home_markup.count("Ett urval från projekten") == 1


def test_followup_chain_section_add_unsupported_type_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unsupported/unknown section type is an HONEST no-op: section_add is
    classified, but no capability mounts, so no version is written and the stage
    explains why (never a faked section)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    result = run_followup_chain(
        SITE_ID,
        "lägg till en sektion om färger",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False
    assert result["stage"] == "section_unsupported"
    assert result["editKind"] == "section_add"
    assert not (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()
    assert any("sektionstyp" in note.lower() for note in result["notes"])


def test_followup_chain_section_dispatch_is_role_driven() -> None:
    """F1 slice 3: the section_add dispatch in run_followup_chain is selected by
    the CLASSIFIED ROLE's skill (skill_for_edit_kind == SECTION_ADD_SKILL), not
    the raw editKind. Source-lock so a refactor can't silently revert to
    editKind-branching (which would stop the role from driving dispatch).
    """
    build_site_src = (
        REPO_ROOT / "scripts" / "build_site.py"
    ).read_text(encoding="utf-8")
    assert "skill_for_edit_kind" in build_site_src, (
        "run_followup_chain must select section_add via skill_for_edit_kind "
        "(role-driven), reading RoleContract.skill."
    )
    assert "SECTION_ADD_SKILL" in build_site_src, (
        "The section_add gate must compare against SECTION_ADD_SKILL "
        "(the section_builder role's contract skill)."
    )
    assert (
        'is_section_add = decision.editKind == "section_add"' not in build_site_src
    ), (
        "The old editKind-only section_add gate must be gone — dispatch is "
        "role/skill-driven now (F1 slice 3)."
    )


def test_followup_question_is_honest_no_op(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A pure question never applies a patch, never creates a version, never builds."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    runs_before = {d.name for d in runs_dir.iterdir() if d.is_dir()}

    result = run_followup_chain(
        SITE_ID,
        "vad kostar en logga?",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )

    assert result["applied"] is False
    assert result["stage"] == "router_no_edit"
    assert not (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()
    # No new run created (no build happened).
    assert {d.name for d in runs_dir.iterdir() if d.is_dir()} == runs_before


def test_followup_without_prior_build_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A follow-up for a site with no prior run fails loud (nothing to build on)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    with pytest.raises(SystemExit, match="ingen tidigare run"):
        run_followup_chain(
            "nonexistent-site",
            CAPABILITY_FOLLOWUP,
            do_build=False,
            runs_dir=tmp_path / "runs",
            generated_dir=tmp_path / "gen",
            output_dir=tmp_path / "prompt-inputs",
        )


def test_cli_followup_entrypoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The argv CLI (--followup --site-id) drives the same chain and prints JSON."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import scripts.build_site as build_site

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    argv = [
        "build_site.py",
        "--followup",
        CAPABILITY_FOLLOWUP,
        "--site-id",
        SITE_ID,
        "--skip-build",
        "--runs-dir",
        str(runs_dir),
        "--generated-dir",
        str(generated_dir),
    ]
    # The CLI resolves prompt-inputs from PROMPT_INPUTS_DIR; point it at the
    # sandbox so the argv path is exercised without touching the repo's data/.
    monkeypatch.setattr(build_site, "PROMPT_INPUTS_DIR", prompt_inputs)
    monkeypatch.setattr(sys, "argv", argv)

    rc = build_site.main()
    assert rc == 0
    assert (prompt_inputs / f"{SITE_ID}.v2.project-input.json").exists()


def test_followup_chain_routes_via_llm_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The chain classifies via classify_message_with_llm_fallback (KÖR-6b), not
    the bare KÖR-6a heuristic, so ambiguous/long follow-ups can escalate to
    routerModel when a key is present. Without a key it stays heuristic-identical;
    here we only assert the fallback entrypoint is the one invoked."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import packages.generation.orchestration.router as router_pkg
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)

    calls = {"n": 0}
    real = router_pkg.classify_message_with_llm_fallback

    def _spy(message, **kwargs):
        calls["n"] += 1
        return real(message, **kwargs)

    monkeypatch.setattr(router_pkg, "classify_message_with_llm_fallback", _spy)

    run_followup_chain(
        SITE_ID,
        "vad kostar en logga?",
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert calls["n"] == 1, "follow-up chain must classify via the KÖR-6b fallback"


def test_followup_chain_forwards_base_run_id_to_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """run_followup_chain passes base_run_id through to apply_patch_plan so apply
    iterates from the same historical version the context was read from, instead
    of the rolling latest (kör-7 base-run consistency)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import packages.generation.orchestration.apply as apply_mod
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(tmp_path)

    captured: dict = {}
    real_apply = apply_mod.apply_patch_plan

    def _spy(plan, **kwargs):
        captured["base_run_id"] = kwargs.get("base_run_id")
        return real_apply(plan, **kwargs)

    monkeypatch.setattr(apply_mod, "apply_patch_plan", _spy)

    run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        base_run_id=base_run_id,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    assert captured["base_run_id"] == base_run_id


def test_followup_chain_rejects_cross_site_base_run_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An EXPLICIT baseRunId that belongs to ANOTHER site is rejected before any
    build: iterating a follow-up from a foreign run would read the wrong
    artefakts and pin the wrong hero headline (cross-site guard)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, base_run_id = _seed_init_build(tmp_path)
    # base_run_id belongs to SITE_ID; passing it for another site must STOP.
    with pytest.raises(SystemExit, match="cross-site"):
        run_followup_chain(
            "some-other-site",
            CAPABILITY_FOLLOWUP,
            base_run_id=base_run_id,
            do_build=False,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
            output_dir=prompt_inputs,
        )


def test_followup_chain_rejects_unverifiable_base_run_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Extern granskning 2026-06-10 (F2): en explicit baseRunId vars
    build-result.json saknas/är oläsbar fick tidigare PASSERA cross-site-
    guarden (None hoppade över kontrollen). Nu vägras en overifierbar bas
    ärligt i stället för att tyst lita på en trasig/främmande run-dir."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    # En run-dir utan build-result.json = overifierbart ägarskap.
    broken_run = runs_dir / "20990101T000000.000Z-deadbeef"
    broken_run.mkdir()
    with pytest.raises(SystemExit, match="overifierbar"):
        run_followup_chain(
            SITE_ID,
            CAPABILITY_FOLLOWUP,
            base_run_id=broken_run.name,
            do_build=False,
            runs_dir=runs_dir,
            generated_dir=generated_dir,
            output_dir=prompt_inputs,
        )


def test_followup_chain_is_mock_safe_without_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No OPENAI_API_KEY -> no crash, honest degrade through the whole chain."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert os.environ.get("OPENAI_API_KEY") is None
    from scripts.build_site import run_followup_chain

    prompt_inputs, runs_dir, generated_dir, _base = _seed_init_build(tmp_path)
    result = run_followup_chain(
        SITE_ID,
        CAPABILITY_FOLLOWUP,
        do_build=False,
        runs_dir=runs_dir,
        generated_dir=generated_dir,
        output_dir=prompt_inputs,
    )
    # The mock path still applies the capability and creates v2 deterministically.
    assert result["applied"] is True
    assert result["version"] == 2
