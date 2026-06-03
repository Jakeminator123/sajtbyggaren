"""kor-3a — declarative section-treatments JSON byte-parity.

KÖR 3a moved the section-treatment truth out of two hand-maintained
Python tables — ``packages/generation/build/dispatcher.py``
``_SECTION_TREATMENTS_BY_VARIANT`` and
``packages/generation/planning/plan.py``
``_SECTION_TREATMENTS_CATALOGUE`` — into one declarative source on disk:
``scaffolds/<id>/section-treatments.json``.

This module proves the migration is behaviour-preserving:

1. The JSON-backed variant→treatment table reconstructs the exact
   pre-migration ``_SECTION_TREATMENTS_BY_VARIANT`` literal, frozen here
   as the golden truth.
2. The JSON-backed planning catalogue reconstructs the exact
   pre-migration ``_SECTION_TREATMENTS_CATALOGUE`` literal.
3. The dispatcher and the planning module read the SAME JSON files (one
   truth, not two mirrors).
4. Byte-for-byte render parity for ALL variants: for every registered
   (variant, section) pair, rendering the section through the
   JSON-backed variant tier produces output identical to rendering it
   with the frozen treatment forced through the operator-pin tier. If
   the JSON ever drifts from the frozen mapping the two render paths
   diverge and this test fails.

The frozen literals below are copied verbatim from the pre-kor-3a code
(commit before this branch). They are intentionally NOT imported from
runtime so a regression in the JSON cannot also silently rewrite the
expectation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.generation.build import renderers
from packages.generation.build.dispatcher import (
    _SECTION_TREATMENTS_BY_VARIANT,
    load_section_treatments,
    load_section_treatments_catalogue,
)
from packages.generation.planning.plan import _SECTION_TREATMENTS_CATALOGUE

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLDS_DIR = REPO_ROOT / "packages" / "generation" / "orchestration" / "scaffolds"


# Frozen pre-migration truth (verbatim from dispatcher.py before kor-3a).
_FROZEN_BY_VARIANT: dict[str, dict[str, str]] = {
    "studio-monochrome": {"selected-work-preview": "asymmetric-grid"},
    "bold-electric": {"selected-work-preview": "marquee-row"},
    "warm-care": {"treatment-list": "split-cards"},
    "modern-precision": {"treatment-list": "numbered-stack"},
    "legal-classic": {"practice-grid": "tabular"},
    "accounting-trust": {"practice-grid": "grouped"},
    "consulting-modern": {"expertise-areas": "tag-cluster"},
    "nordic-trust": {"service-list": "tabular"},
    "warm-craft": {"service-list": "alternating-rows"},
    "clinical-calm": {"service-list": "icon-strip"},
}

# Frozen pre-migration truth (verbatim from plan.py before kor-3a).
_FROZEN_CATALOGUE: dict[str, list[str]] = {
    "selected-work-preview": ["editorial-stack", "asymmetric-grid", "marquee-row"],
    "treatment-list": ["minimal-rows", "split-cards", "numbered-stack"],
    "practice-grid": ["dense-grid", "tabular", "grouped"],
    "expertise-areas": ["numbered-2col", "tag-cluster"],
    "service-list": ["card-grid", "alternating-rows", "icon-strip", "tabular"],
}

# section-id → (section renderer, section default) so the render-parity
# test can exercise every treatment-aware section. The default mirrors
# ``treatments[0]`` in each scaffold's section-treatments.json.
_SECTION_RENDER_TABLE: dict[str, tuple[object, str]] = {
    "selected-work-preview": (
        renderers.render_section_selected_work_preview,
        "editorial-stack",
    ),
    "treatment-list": (renderers.render_section_treatment_list, "minimal-rows"),
    "practice-grid": (renderers.render_section_practice_grid, "dense-grid"),
    "expertise-areas": (renderers.render_section_expertise_areas, "numbered-2col"),
    "service-list": (renderers.render_section_service_list, "card-grid"),
}


def _fixture_dossier() -> dict:
    """A dossier with enough services to exercise every treatment branch."""
    return {
        "services": [
            {"id": f"svc-{i}", "label": f"Tjänst {i}", "summary": f"Sammanfattning {i}."}
            for i in range(1, 6)
        ]
    }


# ---------------------------------------------------------------------------
# Data-level parity
# ---------------------------------------------------------------------------


def test_by_variant_reconstructs_frozen_literal() -> None:
    """JSON-backed variant table equals the pre-migration dict exactly."""
    assert _SECTION_TREATMENTS_BY_VARIANT == _FROZEN_BY_VARIANT


def test_catalogue_reconstructs_frozen_literal() -> None:
    """JSON-backed planning catalogue equals the pre-migration dict exactly."""
    assert load_section_treatments_catalogue() == _FROZEN_CATALOGUE
    # plan.py must expose the same value it reads from the dispatcher loader.
    assert _SECTION_TREATMENTS_CATALOGUE == _FROZEN_CATALOGUE


def test_dispatcher_and_planning_read_same_json_source() -> None:
    """One truth: the planning catalogue is derived from the dispatcher loader,
    which is derived from the on-disk JSON the variant table also uses.
    """
    raw = load_section_treatments()
    # Variant table derives from the same raw blocks.
    derived_by_variant: dict[str, dict[str, str]] = {}
    for section_id, block in raw.items():
        for variant_id, treatment_id in block["byVariant"].items():
            derived_by_variant.setdefault(variant_id, {})[section_id] = treatment_id
    assert derived_by_variant == _SECTION_TREATMENTS_BY_VARIANT
    # Catalogue derives from the same raw blocks.
    derived_catalogue = {
        section_id: list(block["treatments"]) for section_id, block in raw.items()
    }
    assert derived_catalogue == _SECTION_TREATMENTS_CATALOGUE


def test_catalogue_default_is_first_treatment() -> None:
    """The section default (used by planning blueprint ``options[0]`` and the
    renderers) must be the first entry of each treatments list.
    """
    catalogue = load_section_treatments_catalogue()
    for section_id, (_, default) in _SECTION_RENDER_TABLE.items():
        assert catalogue[section_id][0] == default


def test_every_byvariant_treatment_is_listed_in_catalogue() -> None:
    """No variant may pin a treatment that the section catalogue does not list."""
    catalogue = load_section_treatments_catalogue()
    for variant_id, sections in _SECTION_TREATMENTS_BY_VARIANT.items():
        for section_id, treatment_id in sections.items():
            assert treatment_id in catalogue[section_id], (
                f"variant {variant_id!r} pins {treatment_id!r} for "
                f"{section_id!r} but it is not in the catalogue"
            )


# ---------------------------------------------------------------------------
# Render-level byte parity (all variants)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("variant_id", "section_id", "treatment_id"),
    [
        (variant_id, section_id, treatment_id)
        for variant_id, sections in sorted(_FROZEN_BY_VARIANT.items())
        for section_id, treatment_id in sorted(sections.items())
    ],
)
def test_variant_render_matches_frozen_treatment(
    variant_id: str, section_id: str, treatment_id: str
) -> None:
    """For every registered (variant, section) pair, the JSON-backed variant
    tier must render byte-identically to the frozen treatment forced via the
    operator-pin tier.

    The variant path resolves its treatment from the on-disk JSON; the pin
    path forces the frozen treatment id regardless of the JSON (operator-pin
    wins). If the JSON drifted from the frozen value the two strings differ.
    """
    renderer, _default = _SECTION_RENDER_TABLE[section_id]
    dossier = _fixture_dossier()
    pinned_dossier = {
        **dossier,
        "directives": {"sectionTreatments": {section_id: treatment_id}},
    }

    via_variant = renderer(
        dossier, contact_path="/kontakt", variant_id=variant_id
    )
    via_pin = renderer(
        pinned_dossier, contact_path="/kontakt", variant_id="unmapped-variant-xyz"
    )

    assert via_variant != ""
    assert via_variant == via_pin


def test_default_inheriting_variants_render_as_section_default() -> None:
    """Variants deliberately absent from byVariant must render the section
    default — byte-identical to passing no variant at all.
    """
    default_inheriting = {
        "selected-work-preview": ["editorial-warm"],
        "treatment-list": ["clinic-calm"],
        "service-list": ["midnight-counsel", "pulse-fit"],
        "expertise-areas": ["legal-classic", "accounting-trust"],
    }
    dossier = _fixture_dossier()
    for section_id, variants in default_inheriting.items():
        renderer, _default = _SECTION_RENDER_TABLE[section_id]
        baseline = renderer(dossier, contact_path="/kontakt", variant_id=None)
        for variant_id in variants:
            assert (
                renderer(dossier, contact_path="/kontakt", variant_id=variant_id)
                == baseline
            ), f"{variant_id!r} must inherit the {section_id!r} default"
