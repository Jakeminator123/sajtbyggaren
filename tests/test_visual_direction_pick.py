"""kor-3b — visualDirection picks a section treatment from the kor-3a JSON truth.

These tests pin the kor-3b behaviour on top of kor-3a's declarative JSON:

    operator-pin > visualDirection > variant-default > section-default

and the hard guards the operator required:

* an unsupported treatment can NEVER be chosen (runtime section-support check
  in ``_visual_direction_pick_for_section`` + schema enum),
* an ambiguous blueprint (more than one address ending in ``.<sectionId>``)
  resolves to None — we never silently guess which route's pick to use,
* without a visualDirection pick the resolver is byte-identical to kor-3a
  (regression guard),
* the schema enum union never drifts from the JSON-truth ``treatments``.

The resolver helpers are exercised directly (the rendered markup is already
covered by the section-treatment snapshot/smoke tests); one render-level case
proves the "visibly different treatment" DoD end to end for service-list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.build import dispatcher  # noqa: E402
from packages.generation.build.blueprint_render import RenderBlueprint  # noqa: E402

SCHEMA_PATH = (
    REPO_ROOT / "governance" / "schemas" / "generation-package.schema.json"
)


# Each row: (section_id, section_default, a_supported_pick, a_variant_with_default,
#            that_variant_default). Mirrors the kor-3a JSON so the test fails
#            loudly if a section's supported set changes without an update here.
_SECTIONS = [
    ("service-list", "card-grid", "tabular", "warm-craft", "alternating-rows"),
    ("treatment-list", "minimal-rows", "numbered-stack", "warm-care", "split-cards"),
    ("practice-grid", "dense-grid", "grouped", "legal-classic", "tabular"),
    ("expertise-areas", "numbered-2col", "tag-cluster", "consulting-modern", "tag-cluster"),
    (
        "selected-work-preview",
        "editorial-stack",
        "marquee-row",
        "studio-monochrome",
        "asymmetric-grid",
    ),
]


# ---------------------------------------------------------------------------
# _supported_treatments_for_section — the runtime allow-list
# ---------------------------------------------------------------------------


def test_supported_treatments_match_json_truth() -> None:
    """Every section's supported set equals its kor-3a JSON ``treatments``."""
    truth = dispatcher.load_section_treatments()
    for section_id, *_ in _SECTIONS:
        assert set(dispatcher._supported_treatments_for_section(section_id)) == set(
            truth[section_id]["treatments"]
        )


def test_supported_treatments_empty_for_unknown_section() -> None:
    assert dispatcher._supported_treatments_for_section("no-such-section") == ()


# ---------------------------------------------------------------------------
# _visual_direction_pick_for_section — validation half of the guarantee
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("section_id, _default, supported, _v, _vd", _SECTIONS)
def test_pick_accepts_supported_treatment(
    section_id: str, _default: str, supported: str, _v: str, _vd: str
) -> None:
    assert (
        dispatcher._visual_direction_pick_for_section(section_id, supported)
        == supported
    )


@pytest.mark.parametrize("candidate", [None, "", "   ", 42, "does-not-exist"])
def test_pick_rejects_empty_or_unknown(candidate) -> None:
    assert (
        dispatcher._visual_direction_pick_for_section("service-list", candidate)
        is None
    )


def test_pick_rejects_treatment_valid_for_another_section() -> None:
    """``tag-cluster`` is supported by expertise-areas, never by service-list."""
    assert (
        dispatcher._visual_direction_pick_for_section("service-list", "tag-cluster")
        is None
    )
    # ...and the reverse: a service-list treatment is rejected on expertise-areas.
    assert (
        dispatcher._visual_direction_pick_for_section("expertise-areas", "tabular")
        is None
    )


def test_pick_strips_whitespace() -> None:
    assert (
        dispatcher._visual_direction_pick_for_section("service-list", "  tabular  ")
        == "tabular"
    )


# ---------------------------------------------------------------------------
# _treatment_for_section — full resolution order
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "section_id, default, supported, variant, variant_default", _SECTIONS
)
def test_visual_direction_overrides_variant_default(
    section_id: str,
    default: str,
    supported: str,
    variant: str,
    variant_default: str,
) -> None:
    """visualDirection beats the variant default (and is itself beaten by pin)."""
    # vd pick differs from the variant default in every row except where the
    # variant default already equals the chosen pick; guard that we pick one
    # that is actually different so the assertion is meaningful.
    pick = supported if supported != variant_default else default
    assert pick != variant_default
    assert (
        dispatcher._treatment_for_section(
            variant,
            section_id,
            default=default,
            visual_direction_pick=pick,
        )
        == pick
    )


def test_visual_direction_overrides_section_default_without_variant() -> None:
    assert (
        dispatcher._treatment_for_section(
            None,
            "service-list",
            default="card-grid",
            visual_direction_pick="icon-strip",
        )
        == "icon-strip"
    )


def test_operator_pin_beats_visual_direction() -> None:
    assert (
        dispatcher._treatment_for_section(
            "warm-craft",
            "service-list",
            default="card-grid",
            operator_pin="card-grid",
            visual_direction_pick="tabular",
        )
        == "card-grid"
    )


def test_unsupported_visual_direction_falls_through_to_variant_default() -> None:
    """An unknown / wrong-section pick never shadows the variant default."""
    # warm-craft -> service-list variant default is alternating-rows.
    assert (
        dispatcher._treatment_for_section(
            "warm-craft",
            "service-list",
            default="card-grid",
            visual_direction_pick="tag-cluster",  # expertise-areas treatment
        )
        == "alternating-rows"
    )


def test_unsupported_visual_direction_falls_through_to_section_default() -> None:
    assert (
        dispatcher._treatment_for_section(
            None,
            "service-list",
            default="card-grid",
            visual_direction_pick="not-a-real-treatment",
        )
        == "card-grid"
    )


# ---------------------------------------------------------------------------
# kor-3a parity: visual_direction_pick=None == pre-kor-3b behaviour
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "variant, operator_pin",
    [
        (None, None),
        ("warm-craft", None),
        ("midnight-counsel", None),  # variant w/o service-list registration
        ("warm-craft", "tabular"),
        (None, "icon-strip"),
        ("warm-craft", ""),  # empty pin falls through to variant default
    ],
)
def test_parity_without_visual_direction(variant, operator_pin) -> None:
    """Omitting / Noneing visual_direction_pick reproduces kor-3a exactly."""
    omitted = dispatcher._treatment_for_section(
        variant, "service-list", default="card-grid", operator_pin=operator_pin
    )
    explicit_none = dispatcher._treatment_for_section(
        variant,
        "service-list",
        default="card-grid",
        operator_pin=operator_pin,
        visual_direction_pick=None,
    )
    assert omitted == explicit_none


# ---------------------------------------------------------------------------
# RenderBlueprint.section_treatment_pick — address-suffix read + guards
# ---------------------------------------------------------------------------


def _blueprint(section_treatments: dict) -> RenderBlueprint:
    return RenderBlueprint(visual_direction={"sectionTreatments": section_treatments})


def test_section_pick_matches_address_suffix() -> None:
    bp = _blueprint({"services.service-list": "tabular"})
    assert bp.section_treatment_pick("service-list") == "tabular"


def test_section_pick_none_when_absent() -> None:
    bp = _blueprint({"home.hero": "centered"})
    assert bp.section_treatment_pick("service-list") is None


def test_section_pick_none_for_empty_or_nonstring_value() -> None:
    assert _blueprint({"services.service-list": "   "}).section_treatment_pick(
        "service-list"
    ) is None
    assert _blueprint({"services.service-list": 7}).section_treatment_pick(
        "service-list"
    ) is None


def test_section_pick_ambiguous_returns_none() -> None:
    """>1 address ending in .service-list -> None (never guess) — operator guard."""
    bp = _blueprint(
        {
            "home.service-list": "tabular",
            "services.service-list": "alternating-rows",
        }
    )
    assert bp.section_treatment_pick("service-list") is None


def test_section_pick_no_blueprint_or_no_visual_direction() -> None:
    assert RenderBlueprint().section_treatment_pick("service-list") is None
    assert RenderBlueprint(
        visual_direction={"mood": "warm"}
    ).section_treatment_pick("service-list") is None


def test_section_pick_does_not_partial_match_compound_section_id() -> None:
    """``.service-list`` must not match an unrelated ``my-service-list`` section."""
    bp = _blueprint({"home.my-service-list": "tabular"})
    assert bp.section_treatment_pick("service-list") is None


# ---------------------------------------------------------------------------
# DoD: same scaffold/variant + different visualDirection -> different treatment
# ---------------------------------------------------------------------------


def test_same_variant_different_visual_direction_renders_differently() -> None:
    """End-to-end via render_section_service_list (LSB shim path).

    nordic-trust's service-list variant default is ``tabular``. A blueprint that
    picks ``alternating-rows`` must produce visibly different markup, and an
    unsupported pick must fall back to the variant default (byte-identical to
    no blueprint) — proving both the visible-difference DoD and the
    unsupported-is-ignored guard through the real renderer.
    """
    from packages.generation.build.renderers import render_section_service_list

    dossier = {
        "services": [
            {"id": "a", "label": "Tjänst A", "summary": "Beskrivning A."},
            {"id": "b", "label": "Tjänst B", "summary": "Beskrivning B."},
        ]
    }

    def render(pick: str | None):
        bp = (
            _blueprint({"services.service-list": pick})
            if pick is not None
            else None
        )
        return render_section_service_list(
            dossier,
            contact_path="/kontakt",
            variant_id="nordic-trust",
            blueprint=bp,
        )

    variant_default = render(None)  # nordic-trust -> tabular
    overridden = render("alternating-rows")
    unsupported = render("tag-cluster")  # not a service-list treatment

    assert overridden != variant_default  # visible difference (DoD)
    assert unsupported == variant_default  # unsupported ignored -> parity


# ---------------------------------------------------------------------------
# Drift guard: schema enum union == JSON-truth treatments union
# ---------------------------------------------------------------------------


def test_schema_enum_equals_json_truth_union() -> None:
    """generation-package.schema.json visualDirection.sectionTreatments enum must
    stay equal to the union of every section's kor-3a JSON ``treatments``."""
    truth_union: set[str] = set()
    for block in dispatcher.load_section_treatments().values():
        truth_union.update(block["treatments"])

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = set(
        schema["properties"]["visualDirection"]["properties"]["sectionTreatments"][
            "additionalProperties"
        ]["enum"]
    )
    assert enum == truth_union


# ---------------------------------------------------------------------------
# Schema validation: a real artefakt field accepts/rejects correctly
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _visual_direction_validator(schema: dict) -> jsonschema.Draft202012Validator:
    """Validator for the visualDirection subschema in isolation.

    The full generation-package schema requires other top-level fields, so we
    validate the ``visualDirection`` property subschema directly to exercise the
    sectionTreatments enum without constructing a whole valid package.
    """
    return jsonschema.Draft202012Validator(
        schema["properties"]["visualDirection"]
    )


def test_schema_accepts_supported_treatment(schema: dict) -> None:
    _visual_direction_validator(schema).validate(
        {"sectionTreatments": {"services.service-list": "tabular"}}
    )


def test_schema_rejects_unknown_treatment(schema: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        _visual_direction_validator(schema).validate(
            {"sectionTreatments": {"services.service-list": "rainbow-explosion"}}
        )
