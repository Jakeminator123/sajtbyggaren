"""Phase 3 (ADR 0031) — operator-pin resolve order for section treatments.

These tests pin the Phase 3 implementation acceptance for
``GAP-section-design-treatments-phase-3-backend``: the new resolve
order ``operator-pin > variant-default > section-default`` in
``scripts/build_site.py::_treatment_for_section`` must hold for every
combination of operator pin, variant registration and section
fall-back.

The tests intentionally exercise the public helpers
(``_treatment_for_section``, ``_operator_pin_for_section``) directly
rather than going through the section renderers because the renderer
output is verified by snapshot tests (e.g. the run-builder smoke tests
in ``tests/test_builder_smoke.py``); we only need to prove that the
resolve helper returns the right id for each layer.

Drift guards:

* ``_SECTION_TREATMENTS_BY_VARIANT`` (runtime table) is treated as the
  authoritative source for variant-defaults. The schema enum and the
  TS mirror in ``apps/viewser/components/discovery-wizard/treatment-
  options.ts`` must list every treatment id used here, but enum drift
  is verified by ``tests/test_project_input_schema.py``; we do not
  re-prove it.

* The propagation path ``payload.directives.sectionTreatments →
  project_input.directives.sectionTreatments`` is verified separately
  in ``tests/test_section_treatments_propagation.py`` (this file).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SITE_PATH = REPO_ROOT / "scripts" / "build_site.py"


def _load_build_site_module():
    """Load ``scripts/build_site.py`` as a module without invoking its CLI.

    ``build_site.py`` is a large script with side-effect-free helpers
    intermingled with a CLI ``main()``. We load it via ``importlib.util``
    so we can call ``_treatment_for_section`` and
    ``_operator_pin_for_section`` directly without paying the build
    cost or depending on a ``__main__``-style invocation.
    """
    if "_build_site_module_for_treatment_tests" in sys.modules:
        return sys.modules["_build_site_module_for_treatment_tests"]
    spec = importlib.util.spec_from_file_location(
        "_build_site_module_for_treatment_tests",
        BUILD_SITE_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_build_site_module_for_treatment_tests"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_site():
    return _load_build_site_module()


# ---------------------------------------------------------------------------
# _operator_pin_for_section — extraction layer
# ---------------------------------------------------------------------------


def test_operator_pin_returns_none_for_empty_dossier(build_site) -> None:
    assert build_site._operator_pin_for_section({}, "service-list") is None


def test_operator_pin_returns_none_when_directives_missing(build_site) -> None:
    dossier = {"siteId": "demo"}
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


def test_operator_pin_returns_none_when_section_treatments_missing(
    build_site,
) -> None:
    dossier = {"directives": {"layoutHint": "centered"}}
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


def test_operator_pin_returns_none_when_section_not_pinned(build_site) -> None:
    dossier = {
        "directives": {
            "sectionTreatments": {"treatment-list": "split-cards"},
        },
    }
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


def test_operator_pin_returns_pinned_value(build_site) -> None:
    dossier = {
        "directives": {
            "sectionTreatments": {"service-list": "tabular"},
        },
    }
    assert (
        build_site._operator_pin_for_section(dossier, "service-list")
        == "tabular"
    )


def test_operator_pin_strips_whitespace(build_site) -> None:
    dossier = {
        "directives": {
            "sectionTreatments": {"service-list": "  alternating-rows  "},
        },
    }
    assert (
        build_site._operator_pin_for_section(dossier, "service-list")
        == "alternating-rows"
    )


def test_operator_pin_treats_blank_string_as_no_pin(build_site) -> None:
    dossier = {
        "directives": {
            "sectionTreatments": {"service-list": "   "},
        },
    }
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


def test_operator_pin_ignores_non_string_values(build_site) -> None:
    dossier = {
        "directives": {
            "sectionTreatments": {"service-list": 42},
        },
    }
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


def test_operator_pin_ignores_non_dict_dossier(build_site) -> None:
    assert build_site._operator_pin_for_section(None, "service-list") is None
    assert build_site._operator_pin_for_section("not-a-dict", "service-list") is None


def test_operator_pin_ignores_non_dict_directives(build_site) -> None:
    dossier = {"directives": "not-a-dict"}
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


def test_operator_pin_ignores_non_dict_section_treatments(build_site) -> None:
    dossier = {"directives": {"sectionTreatments": ["service-list"]}}
    assert build_site._operator_pin_for_section(dossier, "service-list") is None


# ---------------------------------------------------------------------------
# _treatment_for_section — resolve order
# ---------------------------------------------------------------------------


def test_resolve_returns_section_default_when_no_variant_no_pin(
    build_site,
) -> None:
    """Layer 3: section-default when no signal is present."""
    assert (
        build_site._treatment_for_section(
            None,
            "service-list",
            default="card-grid",
        )
        == "card-grid"
    )


def test_resolve_returns_section_default_for_unknown_variant(build_site) -> None:
    """Unknown variant → section-default (forward-compatible)."""
    assert (
        build_site._treatment_for_section(
            "future-variant-not-yet-registered",
            "service-list",
            default="card-grid",
        )
        == "card-grid"
    )


def test_resolve_returns_section_default_when_variant_does_not_register_section(
    build_site,
) -> None:
    """Variant exists but doesn't pin this section → section-default.

    ``midnight-counsel`` is registered in
    ``_SECTION_TREATMENTS_BY_VARIANT`` for its ``selected-work-preview``
    treatment, NOT for ``service-list``. Asking for ``service-list``
    should fall through to the section default.
    """
    assert (
        build_site._treatment_for_section(
            "midnight-counsel",
            "service-list",
            default="card-grid",
        )
        == "card-grid"
    )


def test_resolve_returns_variant_default_when_registered(build_site) -> None:
    """Layer 2: variant-default wins over section-default.

    ``warm-craft`` registers ``service-list`` → ``alternating-rows``
    in the runtime table. Without an operator pin, the variant
    default wins.
    """
    assert (
        build_site._treatment_for_section(
            "warm-craft",
            "service-list",
            default="card-grid",
        )
        == "alternating-rows"
    )


def test_resolve_operator_pin_overrides_variant_default(build_site) -> None:
    """Layer 1: operator-pin wins over variant-default (the core ADR 0031 rule).

    ``warm-craft`` would normally produce ``alternating-rows`` for
    service-list. An operator who pins ``tabular`` must override that.
    """
    assert (
        build_site._treatment_for_section(
            "warm-craft",
            "service-list",
            default="card-grid",
            operator_pin="tabular",
        )
        == "tabular"
    )


def test_resolve_operator_pin_overrides_when_no_variant_default(
    build_site,
) -> None:
    """Operator pin wins even when the variant has no registration."""
    assert (
        build_site._treatment_for_section(
            "midnight-counsel",
            "service-list",
            default="card-grid",
            operator_pin="icon-strip",
        )
        == "icon-strip"
    )


def test_resolve_operator_pin_overrides_when_no_variant_at_all(
    build_site,
) -> None:
    """Operator pin wins even when no variant is supplied."""
    assert (
        build_site._treatment_for_section(
            None,
            "service-list",
            default="card-grid",
            operator_pin="alternating-rows",
        )
        == "alternating-rows"
    )


def test_resolve_empty_pin_falls_through_to_variant_default(build_site) -> None:
    """Empty-string pin must NOT shadow the variant default.

    Empty / falsy pins are treated as "no pin" so a defensive caller
    that did ``operator_pin=""`` does not accidentally lose the
    variant default. The contract matches
    ``_operator_pin_for_section`` which returns ``None`` for blank
    strings.
    """
    assert (
        build_site._treatment_for_section(
            "warm-craft",
            "service-list",
            default="card-grid",
            operator_pin="",
        )
        == "alternating-rows"
    )


def test_resolve_empty_pin_falls_through_to_section_default(build_site) -> None:
    assert (
        build_site._treatment_for_section(
            None,
            "service-list",
            default="card-grid",
            operator_pin="",
        )
        == "card-grid"
    )


# ---------------------------------------------------------------------------
# Smoke: every Phase 1+2 section is reachable through operator-pin path.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "section_id, default, pin",
    [
        ("service-list", "card-grid", "tabular"),
        ("treatment-list", "minimal-rows", "split-cards"),
        ("expertise-areas", "numbered-2col", "tag-cluster"),
        ("practice-grid", "dense-grid", "grouped"),
        ("selected-work-preview", "editorial-stack", "marquee-row"),
    ],
)
def test_operator_pin_routes_for_every_phase_1_and_2_section(
    build_site, section_id: str, default: str, pin: str
) -> None:
    """Every section that Phase 1+2 wired through the dispatcher must
    accept an operator pin and return it verbatim.

    Drift guard: this list MUST stay in sync with
    ``apps/viewser/components/discovery-wizard/treatment-options.ts``
    and ``governance/schemas/project-input.schema.json``
    ``directives.sectionTreatments``. If a future phase registers a
    new section, add a row here so the operator-pin path is exercised
    for that section too.
    """
    assert (
        build_site._treatment_for_section(
            None,
            section_id,
            default=default,
            operator_pin=pin,
        )
        == pin
    )
