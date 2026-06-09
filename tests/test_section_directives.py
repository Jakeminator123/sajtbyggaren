"""Unit tests for the section_builder capability resolver.

Covers ``packages.generation.followup.section_directives``: every sanctioned
section-type slug must resolve to a capability that HAS an implementing Dossier
in ``capability-map.v1.json`` (the two-gate contract — a Dossier + a renderer —
that a type must clear to be listed in ``SECTION_TYPE_CAPABILITY``), and an
unknown/empty type must be reported as an HONEST no-op (``unsupported``) rather
than mounting a phantom section.

Deterministic, offline, no LLM, no build — the resolver only reads the
capability map. Conventions: identifiers + comments in English
(governance/rules/code-in-english.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.followup.section_directives import (  # noqa: E402
    INLINE_SECTION_PLACEMENTS,
    INLINE_SECTION_ROUTES,
    SECTION_TYPE_CAPABILITY,
    VISIBLE_SECTION_ROUTES,
    resolve_inline_section_placements,
    resolve_section_capabilities,
    resolve_visible_section_pages,
)

# Each sanctioned type slug -> (capability, default Dossier it must mount). The
# new section_builder broadening (gallery/pricing/hours/map/contact-form) reuses
# the existing soft Dossiers; map's slug resolves to the ``location`` capability.
_TYPE_TO_CAPABILITY_AND_DOSSIER = {
    "faq": ("faq-section", "faq-accordion"),
    "reviews": ("reviews", "reviews-display"),
    "team": ("team-section", "team-roster"),
    "trust": ("guarantees", "trust-guarantees"),
    "gallery": ("gallery", "image-gallery"),
    "pricing": ("pricing", "pricing-table"),
    "hours": ("hours", "opening-hours"),
    "map": ("location", "map-embed"),
    "contact-form": ("contact-form", "mailto-contact-form"),
}


def test_mapping_covers_exactly_the_sanctioned_types() -> None:
    """Guard: the resolver's mapping and this test's expectation stay in sync,
    so a future edit to ``SECTION_TYPE_CAPABILITY`` can't silently bypass the
    per-type capability/Dossier assertions below."""
    assert set(SECTION_TYPE_CAPABILITY) == set(_TYPE_TO_CAPABILITY_AND_DOSSIER)


@pytest.mark.parametrize("section_type", sorted(_TYPE_TO_CAPABILITY_AND_DOSSIER))
def test_sanctioned_type_resolves_to_its_capability(section_type: str) -> None:
    """Every sanctioned type resolves to the expected capability with NO
    ``unsupported`` entry (its capability has an implementing Dossier)."""
    expected_capability, _dossier = _TYPE_TO_CAPABILITY_AND_DOSSIER[section_type]
    assert SECTION_TYPE_CAPABILITY[section_type] == expected_capability

    capabilities, unsupported = resolve_section_capabilities([section_type])
    assert capabilities == [expected_capability]
    assert unsupported == []


@pytest.mark.parametrize("section_type", sorted(_TYPE_TO_CAPABILITY_AND_DOSSIER))
def test_sanctioned_capability_has_an_implementing_dossier(section_type: str) -> None:
    """The two-gate contract: a listed type's capability MUST resolve to its
    default Dossier via the canonical planning filter (so apply can mount it).
    A type whose capability had an empty ``dossiers`` list would be rejected
    here — exactly the no-op the resolver must produce instead of mounting."""
    from packages.generation.planning import filter_capabilities, load_capability_map

    _slug, expected_dossier = _TYPE_TO_CAPABILITY_AND_DOSSIER[section_type]
    capability = SECTION_TYPE_CAPABILITY[section_type]
    selected, _rejected = filter_capabilities([capability], load_capability_map())
    assert expected_dossier in selected


def test_unknown_section_type_is_honest_no_op() -> None:
    """An unrecognised type mounts NOTHING and is reported as ``unsupported``
    with a reason — the resolver never invents a section."""
    capabilities, unsupported = resolve_section_capabilities(["färger"])
    assert capabilities == []
    assert len(unsupported) == 1
    assert unsupported[0]["type"] == "färger"
    assert unsupported[0]["reason"]


def test_none_section_type_is_honest_no_op() -> None:
    """A missing type slug (router could not name one) is an honest no-op."""
    capabilities, unsupported = resolve_section_capabilities([None])
    assert capabilities == []
    assert len(unsupported) == 1
    assert unsupported[0]["type"] == "(okänd)"


def test_resolution_dedupes_repeated_and_mixed_types() -> None:
    """Repeated types collapse to one capability; a mix of supported +
    unsupported keeps both lanes honest (supported mounts, unknown no-ops)."""
    capabilities, unsupported = resolve_section_capabilities(
        ["gallery", "gallery", "pricing", "färger"]
    )
    assert capabilities == ["gallery", "pricing"]
    assert [item["type"] for item in unsupported] == ["färger"]


# ---------------------------------------------------------------------------
# Visible section route resolution (faq/team visible-render slice).
# ---------------------------------------------------------------------------

_GROUNDED_PI = {
    # local-service-business is the only scaffold that emits the faq/team wizard
    # routes today, so the visible-route assertions below run on it (#221 P2).
    "scaffoldId": "local-service-business",
    "company": {"team": [{"name": "Anna Ek", "role": "Grundare"}]},
}


def test_visible_routes_map_to_known_wizard_labels() -> None:
    """The visible-route map only carries capabilities with a real wizard route
    label + route id, so apply can record the label on the next version's meta.
    """
    assert VISIBLE_SECTION_ROUTES["faq-section"] == {
        "wizardLabel": "FAQ",
        "routeId": "faq",
    }
    assert VISIBLE_SECTION_ROUTES["team-section"] == {
        "wizardLabel": "Vårt team",
        "routeId": "team",
    }


def test_faq_section_surfaces_a_visible_route() -> None:
    """faq-section is grounded by construction (render_faq answers generic
    questions with the dossier's own areas/hours), so it surfaces /faq on a
    wizard-route scaffold (local-service-business)."""
    visible, mount_only = resolve_visible_section_pages(
        ["faq-section"], {"scaffoldId": "local-service-business"}
    )
    assert visible == [
        {"capability": "faq-section", "wizardLabel": "FAQ", "routeId": "faq"}
    ]
    assert mount_only == []


def test_team_section_visible_only_with_grounded_team() -> None:
    """team-section surfaces /team only when company.team has a named member;
    an empty team stays mount-only (mounted-but-no-content), never a placeholder.
    """
    visible, mount_only = resolve_visible_section_pages(["team-section"], _GROUNDED_PI)
    assert visible == [
        {"capability": "team-section", "wizardLabel": "Vårt team", "routeId": "team"}
    ]
    assert mount_only == []

    visible_empty, mount_only_empty = resolve_visible_section_pages(
        ["team-section"],
        {"scaffoldId": "local-service-business", "company": {"team": []}},
    )
    assert visible_empty == []
    assert len(mount_only_empty) == 1
    assert mount_only_empty[0]["capability"] == "team-section"
    assert mount_only_empty[0]["reason"]


def test_route_less_capability_stays_mount_only() -> None:
    """A mounted capability with no dedicated visible route (e.g. guarantees)
    is reported as mount-only with a reason - never surfaced as a phantom page.
    """
    visible, mount_only = resolve_visible_section_pages(["guarantees"], {})
    assert visible == []
    assert len(mount_only) == 1
    assert mount_only[0]["capability"] == "guarantees"
    assert mount_only[0]["reason"]


def test_visible_pages_dedupe_and_split_mixed_input() -> None:
    """A mix surfaces only the grounded route-capable types once; the rest stay
    mount-only honestly."""
    visible, mount_only = resolve_visible_section_pages(
        ["faq-section", "faq-section", "team-section", "guarantees"],
        _GROUNDED_PI,
    )
    assert [page["routeId"] for page in visible] == ["faq", "team"]
    assert [entry["capability"] for entry in mount_only] == ["guarantees"]


# ---------------------------------------------------------------------------
# Scaffold gate (#221 P2): a route-capable capability only surfaces a visible
# route on a scaffold that actually emits the wizard routes. On any other
# scaffold (agency-studio, ...) it must be an HONEST mount-only no-op, never a
# phantom visible route the build cannot render.
# ---------------------------------------------------------------------------

_AGENCY_GROUNDED_PI = {
    "scaffoldId": "agency-studio",
    "company": {"team": [{"name": "Hanna Björk", "role": "Creative Director"}]},
}


def test_faq_section_mount_only_on_non_wizard_scaffold() -> None:
    """faq-section is grounded by construction, but on a non-wizard scaffold
    (agency-studio) no /faq renders, so it must stay mount-only - never a
    phantom visible route (the honesty contract)."""
    visible, mount_only = resolve_visible_section_pages(
        ["faq-section"], {"scaffoldId": "agency-studio"}
    )
    assert visible == []
    assert len(mount_only) == 1
    assert mount_only[0]["capability"] == "faq-section"
    assert mount_only[0]["reason"]


def test_team_section_mount_only_on_non_wizard_scaffold_even_when_grounded() -> None:
    """Even WITH a grounded team, team-section stays mount-only on a non-wizard
    scaffold: the scaffold gate is the honest reason no visible route surfaces."""
    visible, mount_only = resolve_visible_section_pages(
        ["team-section"], _AGENCY_GROUNDED_PI
    )
    assert visible == []
    assert [entry["capability"] for entry in mount_only] == ["team-section"]


def test_missing_scaffold_id_is_mount_only() -> None:
    """A project_input with no scaffoldId cannot prove the route renders, so a
    route-capable capability stays mount-only (honest default)."""
    visible, mount_only = resolve_visible_section_pages(["faq-section"], {})
    assert visible == []
    assert len(mount_only) == 1
    assert mount_only[0]["capability"] == "faq-section"


def test_scaffold_gate_matches_canonical_wizard_scaffold_set() -> None:
    """The gate must use the SAME scaffold set planning uses to emit wizard
    routes, so surfacing never drifts from what the build actually renders."""
    from packages.generation.planning.plan import get_wizard_route_scaffolds

    wizard_scaffolds = get_wizard_route_scaffolds()
    assert "local-service-business" in wizard_scaffolds
    # Every wizard-route scaffold surfaces faq; a scaffold outside the set does
    # not. (If a new scaffold opts in upstream, this stays in lock-step.)
    for scaffold_id in wizard_scaffolds:
        visible, _ = resolve_visible_section_pages(
            ["faq-section"], {"scaffoldId": scaffold_id}
        )
        assert [page["routeId"] for page in visible] == ["faq"]
    visible_off, _ = resolve_visible_section_pages(
        ["faq-section"], {"scaffoldId": "definitely-not-a-wizard-scaffold"}
    )
    assert visible_off == []


# ---------------------------------------------------------------------------
# Inline section placements (ADR 0038): a mounted capability that maps to an
# inline section on a supported scaffold becomes a directives.mountedSections
# entry so the renderer injects it as a block on a route. The resolver only
# declares WHERE a section can go; render-time owns the renderer/grounded gates.
# ---------------------------------------------------------------------------

_LSB_PI = {"scaffoldId": "local-service-business"}


def test_inline_placement_for_hours_on_lsb() -> None:
    """``hours`` maps to an inline hours-summary block on the LSB home route."""
    placements = resolve_inline_section_placements(["hours"], _LSB_PI)
    assert placements == [
        {"capability": "hours", "sectionId": "hours-summary", "routeId": "home"}
    ]


def test_inline_placement_empty_on_non_inline_scaffold() -> None:
    """A non-allowlisted scaffold gets no inline placements (honest mount-only)."""
    assert resolve_inline_section_placements(["hours"], {"scaffoldId": "agency-studio"}) == []
    assert resolve_inline_section_placements(["hours"], {}) == []


def test_inline_placement_skips_capabilities_without_inline_section() -> None:
    """A capability with no inline mapping (e.g. guarantees) yields nothing,
    so it stays mount-only / dedicated-route-only - never double-surfaced."""
    assert resolve_inline_section_placements(["guarantees"], _LSB_PI) == []
    # faq/team keep their dedicated-route path and are NOT inline-placed.
    assert resolve_inline_section_placements(["faq-section", "team-section"], _LSB_PI) == []


def test_inline_placement_dedupes() -> None:
    """A capability requested twice is placed at most once (order-preserving)."""
    placements = resolve_inline_section_placements(["hours", "hours"], _LSB_PI)
    assert [p["capability"] for p in placements] == ["hours"]


def test_inline_placement_map_targets_registered_renderers() -> None:
    """Every inline placement target must be a section id with a registered
    renderer, so an injection can never SystemExit the dispatcher."""
    # Importing renderers populates dispatcher._SECTION_RENDERERS at import time.
    import packages.generation.build.renderers  # noqa: F401
    from packages.generation.build.dispatcher import _SECTION_RENDERERS

    for capability, placement in INLINE_SECTION_PLACEMENTS.items():
        assert placement["sectionId"] in _SECTION_RENDERERS, (
            f"{capability!r} inline placement targets unregistered section "
            f"{placement['sectionId']!r}"
        )


def test_inline_placement_map_targets_wired_routes() -> None:
    """Every inline placement must target a route whose renderer threads the
    injection seam (``INLINE_SECTION_ROUTES``), so the resolver never persists a
    directive a build cannot render (honesty contract for future routes)."""
    for capability, placement in INLINE_SECTION_PLACEMENTS.items():
        assert placement["routeId"] in INLINE_SECTION_ROUTES, (
            f"{capability!r} inline placement targets unwired route "
            f"{placement['routeId']!r}"
        )


def test_render_time_allowlist_mirrors_resolver_allowlists() -> None:
    """Parity lock (Codex review fix): the render-time defense-in-depth
    allowlist in ``renderers.py`` is a DUPLICATE of the resolver's canonical
    allowlists (build must not import followup), so the two must be derivable
    from each other exactly - a new inline placement added on one side without
    the other fails here."""
    import packages.generation.build.renderers as renderers
    from packages.generation.followup.section_directives import (
        INLINE_SECTION_SCAFFOLDS,
    )

    expected: dict[tuple[str, str], set[str]] = {}
    for placement in INLINE_SECTION_PLACEMENTS.values():
        route_id = placement["routeId"]
        if route_id not in INLINE_SECTION_ROUTES:
            continue
        for scaffold_id in INLINE_SECTION_SCAFFOLDS:
            expected.setdefault((scaffold_id, route_id), set()).add(
                placement["sectionId"]
            )
    actual = {
        key: set(value)
        for key, value in renderers._INLINE_SECTION_ALLOWLIST.items()
    }
    assert actual == expected, (
        "renderers._INLINE_SECTION_ALLOWLIST has drifted from the resolver's "
        f"INLINE_SECTION_* allowlists: actual={actual!r} expected={expected!r}"
    )
