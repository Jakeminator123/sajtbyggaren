"""Unit tests for the Generative Component V1 directive resolver (ADR 0061).

Locks the deterministic, offline contract of
``packages.generation.followup.generative_component_directives``:

- the recipe allowlist holds exactly the V1 recipe (image-placeholder-grid);
- a whitelisted recipe noun resolves to a spec with the parsed + clamped count
  and the default route;
- an unknown / non-whitelisted generative component is REFUSED (honest no-op),
  never invented;
- a non-generative component_add (a clock) resolves to nothing so the existing
  component_builder no-op is preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.generation.followup.generative_component_directives import (  # noqa: E402
    GENERATIVE_RECIPES,
    resolve_generative_component,
)
from packages.generation.orchestration.router import classify_message  # noqa: E402

pytestmark = pytest.mark.tooling


def test_recipe_allowlist_is_exactly_v1():
    """V1 ships exactly one whitelisted recipe (image-placeholder-grid)."""
    assert set(GENERATIVE_RECIPES) == {"image-placeholder-grid"}


@pytest.mark.parametrize(
    "prompt",
    [
        "lägg till 6 bildplatshållare",
        "lägg till en bildgrid",
        "lägg till ett bildrutnät",
    ],
)
def test_recipe_match_via_router_component_add(prompt: str):
    """The recipe nouns classify as component_add and resolve to one spec."""
    decision = classify_message(prompt)
    assert decision.editKind == "component_add"
    specs, refused = resolve_generative_component(prompt, decision)
    assert refused == []
    assert len(specs) == 1
    spec = specs[0]
    assert spec["recipe"] == "image-placeholder-grid"
    assert spec["routeId"] == "home"
    assert spec["id"] == "image-placeholder-grid"


@pytest.mark.parametrize(
    ("prompt", "expected_count"),
    [
        ("lägg till 6 bildplatshållare", 6),
        ("lägg till 3 bildplatshållare", 3),
        ("lägg till en bildgrid", 6),  # no digit -> default
        ("lägg till 99 bildplatshållare", 12),  # clamp high
        ("lägg till 0 bildplatshållare", 1),  # clamp low
        ("lägg till 12 bildplatshållare", 12),  # boundary
    ],
)
def test_count_parse_and_clamp(prompt: str, expected_count: int):
    specs, _refused = resolve_generative_component(prompt, classify_message(prompt))
    assert len(specs) == 1
    assert specs[0]["count"] == expected_count


def test_default_route_id_is_home():
    specs, _ = resolve_generative_component(
        "lägg till en bildgrid", classify_message("lägg till en bildgrid")
    )
    assert specs[0]["routeId"] == "home"


def test_indefinite_article_is_not_a_count():
    """"en bildgrid" is an article, not count=1 -> default grid size, not 1."""
    specs, _ = resolve_generative_component("lägg till en bildgrid")
    assert specs[0]["count"] == GENERATIVE_RECIPES["image-placeholder-grid"][
        "defaultCount"
    ]


class _IntentOnly:
    """Minimal stand-in for a RouterDecision carrying only componentIntent."""

    def __init__(self, component_intent: str | None) -> None:
        self.componentIntent = component_intent


@pytest.mark.parametrize(
    "prompt",
    ["lägg till en karusell med tre behandlingar", "lägg till en slider", "lägg till ett bildspel"],
)
def test_unsupported_generative_family_is_refused(prompt: str):
    """A recognised but unsupported generative component is an HONEST refusal,
    never an invented component."""
    # The router does not recognise these nouns, so drive the component_add path
    # via an injected intent (the conductor decision-injection path) to exercise
    # the refusal branch directly.
    specs, refused = resolve_generative_component(prompt, _IntentOnly("carousel"))
    assert specs == []
    assert len(refused) == 1
    assert "component" in refused[0] and "reason" in refused[0]


@pytest.mark.parametrize(
    "prompt",
    ["lägg till en klocka", "lägg till ett kontaktformulär", "lägg till en bild"],
)
def test_non_generative_component_add_resolves_to_nothing(prompt: str):
    """A plain widget add is not a generative request: ([], []) so the existing
    component_builder no-op handles it byte-for-byte (no false refusal)."""
    specs, refused = resolve_generative_component(prompt, classify_message(prompt))
    assert specs == []
    assert refused == []


def test_resolver_is_deterministic():
    first = resolve_generative_component("lägg till 6 bildplatshållare")
    second = resolve_generative_component("lägg till 6 bildplatshållare")
    assert first == second
