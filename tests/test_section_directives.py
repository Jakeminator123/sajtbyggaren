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
    resolve_section_capabilities,
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
