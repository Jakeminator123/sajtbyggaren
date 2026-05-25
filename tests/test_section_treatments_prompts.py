"""Phase 3 (ADR 0032) — section-treatments awareness in LLM prompts.

These tests pin the Phase 3 prompt-side acceptance for
GAP-section-design-treatments-phase-3-backend:

1. The planning prompt's _SECTION_TREATMENTS_CATALOGUE matches the
   schema enum table in governance/schemas/project-input.schema.json
   (drift guard A).

2. The planning prompt's _SECTION_TREATMENTS_CATALOGUE matches the
   runtime tabellen scripts/build_site.py::_SECTION_TREATMENTS_BY_VARIANT
   (drift guard B — every runtime treatment must be representable).

3. The composed planning prompt actually contains the Section Design
   Treatments Catalogue block so the LLM sees the registered ids.

4. The system instructions mention directives.sectionTreatments and
   treat it as operator-authoritative.

5. The mock-fallback (_mock_plan_choice) and the pinned path
   (_resolve_pinned_choice) do not crash when a Project Input that
   carries directives.sectionTreatments is passed through. PlanningChoice
   never gains a sectionTreatments field — operator-pin lives on
   Project Input.directives, not on the plan output.

The brief layer is intentionally not exercised here. ADR 0032 explains
why: SiteBrief is pre-Project Input and has no directives slot, so
brief-side awareness would be a no-op that risks LLM hallucination of
treatment strings into notes_for_planner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.generation.planning.plan import (
    _PLANNING_SYSTEM_INSTRUCTIONS,
    _SECTION_TREATMENTS_CATALOGUE,
    _build_planning_prompt,
    _mock_plan_choice,
    _resolve_pinned_choice,
    load_capability_map,
    load_scaffold_registry,
)
from scripts.build_site import _SECTION_TREATMENTS_BY_VARIANT

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "schemas" / "project-input.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return load_scaffold_registry()


@pytest.fixture(scope="module")
def capability_map() -> dict:
    return load_capability_map()


# ---------------------------------------------------------------------------
# Drift guards: catalogue vs schema vs runtime
# ---------------------------------------------------------------------------


def test_planning_catalogue_matches_schema_enums(schema: dict) -> None:
    """Every section-id and treatment-id listed in the planning prompt
    catalogue must match the schema enum tabellen exactly. If a future
    commit adds a new section to the schema without bumping the
    catalogue, the LLM would silently lose visibility of that section.
    """
    schema_section_treatments = schema["properties"]["directives"][
        "properties"
    ]["sectionTreatments"]["properties"]

    for section_id, expected_enum in _SECTION_TREATMENTS_CATALOGUE.items():
        section_schema = schema_section_treatments.get(section_id)
        assert section_schema is not None, (
            f"Section {section_id!r} in planning catalogue missing from "
            f"schema. Update governance/schemas/project-input.schema.json "
            f"directives.sectionTreatments enums in the same commit."
        )
        actual_enum = section_schema.get("enum") or []
        assert sorted(actual_enum) == sorted(expected_enum), (
            f"Section {section_id!r} treatment-list drifted: "
            f"catalogue={sorted(expected_enum)} schema={sorted(actual_enum)}"
        )

    for section_id in schema_section_treatments.keys():
        assert section_id in _SECTION_TREATMENTS_CATALOGUE, (
            f"Schema declares section {section_id!r} but the planning "
            f"prompt catalogue does not. Add it to "
            f"_SECTION_TREATMENTS_CATALOGUE in plan.py."
        )


def test_planning_catalogue_covers_runtime_pairs() -> None:
    """Every (section_id, treatment_id) pair registered in the runtime
    tabellen scripts/build_site.py::_SECTION_TREATMENTS_BY_VARIANT must
    appear in the planning prompt catalogue. The inverse is not required
    — the catalogue may list a default treatment that no variant
    happens to register against (the section's own default).
    """
    runtime_pairs: set[tuple[str, str]] = set()
    for variant_bucket in _SECTION_TREATMENTS_BY_VARIANT.values():
        for section_id, treatment_id in variant_bucket.items():
            runtime_pairs.add((section_id, treatment_id))

    missing: list[str] = []
    for section_id, treatment_id in sorted(runtime_pairs):
        section_treatments = _SECTION_TREATMENTS_CATALOGUE.get(section_id)
        if section_treatments is None:
            missing.append(
                f"section {section_id!r} not in catalogue (runtime "
                f"registers treatment {treatment_id!r} for it)"
            )
            continue
        if treatment_id not in section_treatments:
            missing.append(
                f"section {section_id!r} treatment {treatment_id!r} "
                f"not in catalogue {section_treatments}"
            )

    assert not missing, (
        "_SECTION_TREATMENTS_CATALOGUE is missing runtime pairs:\n  - "
        + "\n  - ".join(missing)
    )


# ---------------------------------------------------------------------------
# Prompt content guards
# ---------------------------------------------------------------------------


def test_planning_system_prompt_mentions_section_treatments() -> None:
    """ADR 0032 mandates that planningModel knows directives.sectionTreatments
    is operator-authoritative. If a future prompt-cleanup removes the
    awareness clause the LLM may start to mutate the field.
    """
    text = _PLANNING_SYSTEM_INSTRUCTIONS
    assert "directives.sectionTreatments" in text, (
        "Planning system instructions must mention "
        "directives.sectionTreatments to keep operator-pin awareness."
    )
    assert "operator-authoritative" in text, (
        "Planning system instructions must label sectionTreatments as "
        "operator-authoritative so the LLM does not propose mutations."
    )


def test_planning_user_prompt_includes_treatment_catalogue(
    registry: list[dict],
    capability_map: dict,
) -> None:
    """The composed user message must include the Section Design
    Treatments Catalogue header plus at least one treatment-id per
    registered section. We use a minimal site_brief — the catalogue
    block does not depend on brief contents.
    """
    site_brief = {
        "language": "sv",
        "rawPrompt": "test",
        "businessTypeGuess": None,
        "tone": [],
        "targetAudience": [],
        "requestedCapabilities": [],
        "conversionGoals": [],
        "servicesMentioned": [],
    }
    prompt = _build_planning_prompt(site_brief, registry, capability_map)

    assert "Section Design Treatments Catalogue" in prompt
    for section_id, treatment_ids in _SECTION_TREATMENTS_CATALOGUE.items():
        assert section_id in prompt, (
            f"Treatment catalogue in planning prompt missing section "
            f"{section_id!r}"
        )
        for treatment_id in treatment_ids:
            assert treatment_id in prompt, (
                f"Treatment catalogue in planning prompt missing "
                f"treatment {treatment_id!r} for section {section_id!r}"
            )

    assert "operator-pin only" in prompt, (
        "Planning user message must end with the operator-pin reminder "
        "so the LLM does not invent new treatment ids."
    )


# ---------------------------------------------------------------------------
# Mock-fallback survival
# ---------------------------------------------------------------------------


def test_mock_plan_choice_unaffected_by_section_treatments(
    registry: list[dict],
    capability_map: dict,
) -> None:
    """The deterministic mock planner ignores Phase 3 directives and
    must not crash when the Site Brief carries directives.sectionTreatments
    in its raw prompt context (the mock path consumes only signals it
    knows about).
    """
    site_brief = {
        "language": "sv",
        "rawPrompt": "Vi vill ha en ren agency-studio med monochrome look.",
        "businessTypeGuess": "agency-studio",
        "tone": ["minimal", "monochrome"],
        "targetAudience": ["startups"],
        "requestedCapabilities": [],
        "conversionGoals": ["contact"],
        "servicesMentioned": [],
        # Operator-pin context (would normally live on Project Input,
        # but the mock-no-key path forwards the brief here verbatim).
        "directives": {
            "sectionTreatments": {
                "selected-work-preview": "asymmetric-grid",
            },
        },
    }
    choice, scaffold = _mock_plan_choice(site_brief, registry, capability_map)
    assert choice.scaffoldId in {entry["id"] for entry in registry}
    assert choice.variantId
    # PlanningChoice deliberately has no sectionTreatments field — Phase 3
    # keeps operator-pin on Project Input, not on the plan output.
    assert not hasattr(choice, "sectionTreatments"), (
        "PlanningChoice must NOT carry a sectionTreatments field; "
        "operator-pin lives on Project Input.directives only."
    )
    assert isinstance(scaffold, dict)


def test_resolve_pinned_choice_unaffected_by_section_treatments(
    registry: list[dict],
    capability_map: dict,
) -> None:
    """When the Project Input pins scaffold/variant the planner skips
    the LLM entirely. Adding directives.sectionTreatments to the brief
    must not change that path or its rationale shape.
    """
    pinned = {
        "scaffoldId": "local-service-business",
        "variantId": "nordic-trust",
    }
    site_brief = {
        "language": "sv",
        "rawPrompt": "elektriker i Stockholm",
        "businessTypeGuess": "electrician",
        "tone": [],
        "targetAudience": [],
        "requestedCapabilities": [],
        "conversionGoals": ["call"],
        "servicesMentioned": [],
        "directives": {
            "sectionTreatments": {"service-list": "tabular"},
        },
    }
    choice, scaffold = _resolve_pinned_choice(
        pinned, registry, site_brief, capability_map
    )
    assert choice.scaffoldId == "local-service-business"
    assert choice.variantId == "nordic-trust"
    assert isinstance(scaffold, dict)
    assert not hasattr(choice, "sectionTreatments")
