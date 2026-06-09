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
    SECTION_TYPE_CAPABILITY,
    VISIBLE_SECTION_ROUTES,
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
    questions with the dossier's own areas/hours), so it surfaces /faq."""
    visible, mount_only = resolve_visible_section_pages(["faq-section"], {})
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
        ["team-section"], {"company": {"team": []}}
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
