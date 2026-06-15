"""Follow-up generative-component directives: resolve a component_add to a recipe.

Generative Component V1 (ADR 0061, component_builder role). A ``component_add``
follow-up that names a WHITELISTED, DETERMINISTIC recipe ("lägg till 6
bildplatshållare", "lägg till en bildgrid") is resolved here into a structured
``directives.generativeComponents`` spec the deterministic builder materialises
as ONE new ``components/generated/<id>.tsx`` Server Component spliced into the
target route's ``page.tsx``. V1 ships a SINGLE recipe (``image-placeholder-grid``)
and NO LLM-generated free code + NO new npm deps: this proves the write-path
rails (write new tsx safely + Quality Gate + immutable rollback) before free
codegen lands in a later slice.

Honest by construction (mirrors ``route_directives``): a component_add that does
NOT name a whitelisted recipe but DOES name a recognised generative component
family we cannot fulfil yet (a carousel, a slider) is reported as ``refused`` so
the chain does an HONEST no-op with a reason - never an invented component. A
component_add that is not a generative request at all (a clock widget, a contact
form) resolves to ``([], [])`` so the existing component_builder no-op handles it
byte-for-byte. Deterministic, offline, no LLM.

Conventions: identifiers + comments in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "GENERATIVE_RECIPES",
    "resolve_generative_component",
]

# The route a generative component lands on when the prompt names none. V1 only
# supports the home route's page.tsx (``app/page.tsx``); other routes follow in a
# later slice. Kept here so the resolver and the materialiser agree on the default.
_DEFAULT_ROUTE_ID = "home"

# The V1 allowlist: recipe slug -> the deterministic recipe contract. ``componentIntent``
# is the router slug that maps to this recipe (``classify._COMPONENT_INTENTS``);
# ``cues`` are the prompt nouns that name it; the count bounds clamp the parsed
# tile count. Adding a recipe here (with its emit template in
# ``packages.generation.codegen.followup_emit``) is how V1 grows - never free code.
GENERATIVE_RECIPES: dict[str, dict[str, Any]] = {
    "image-placeholder-grid": {
        "componentIntent": "image_placeholder_grid",
        "cues": (
            "bildgrid",
            "bildrutnät",
            "bildrutnat",
            "bildplatshållare",
            "bildplatshållarna",
            "bildplatshallare",
            "platshållargrid",
            "platshallargrid",
            "image grid",
            "image-grid",
            "placeholder grid",
        ),
        "defaultCount": 6,
        "minCount": 1,
        "maxCount": 12,
    },
}

# Recognised generative-component families V1 cannot materialise yet. A
# component_add naming one of these is an HONEST refusal (generative_unsupported),
# never an invented component. Distinct from a plain widget add (clock/contact
# form) which is not a generative request and resolves to ([], []) so the existing
# component_builder no-op is preserved byte-for-byte.
_UNSUPPORTED_GENERATIVE_CUES: tuple[str, ...] = (
    "karusell",
    "karusellen",
    "bildkarusell",
    "carousel",
    "slider",
    "bildspel",
    "bildspelet",
)


def _word_present(text: str, phrase: str) -> bool:
    """True when ``phrase`` appears as a whole word/phrase in ``text``.

    Same word-boundary contract as the router's ``_word_present`` so a recipe
    cue ("bildgrid") never matches a substring of another word and a plain
    "bild" never matches "bildgrid".
    """
    return (
        re.search(r"(?<![\wåäö])" + re.escape(phrase) + r"(?![\wåäö])", text)
        is not None
    )


def _match_recipe(text: str, component_intent: str | None) -> str | None:
    """Return the whitelisted recipe slug the prompt/intent names, or None."""
    for recipe, contract in GENERATIVE_RECIPES.items():
        if component_intent and component_intent == contract.get("componentIntent"):
            return recipe
        for cue in contract.get("cues", ()):  # type: ignore[union-attr]
            if _word_present(text, cue):
                return recipe
    return None


def _first_unsupported_cue(text: str) -> str | None:
    """Return the first recognised but UNSUPPORTED generative cue, or None."""
    for cue in _UNSUPPORTED_GENERATIVE_CUES:
        if _word_present(text, cue):
            return cue
    return None


def _parse_count(text: str, recipe_contract: dict[str, Any]) -> int:
    """Parse the tile count from the prompt and clamp to the recipe bounds.

    "6 bildplatshållare" -> 6; a prompt with no explicit digit falls back to the
    recipe default; an out-of-range count is clamped to ``[minCount, maxCount]``
    (the schema enforces the same bounds, so the directive can never be invalid).
    Only explicit DIGITS are read - the Swedish article "en"/"ett" ("en bildgrid")
    is the indefinite article, NOT a count, so it never collapses the grid to 1.
    """
    default = int(recipe_contract.get("defaultCount", 6))
    low = int(recipe_contract.get("minCount", 1))
    high = int(recipe_contract.get("maxCount", 12))
    match = re.search(r"\d+", text or "")
    count = int(match.group()) if match else default
    return max(low, min(high, count))


def resolve_generative_component(
    prompt: str,
    decision: Any | None = None,
    context: Any | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Resolve a component_add follow-up to generative-component spec(s).

    Returns ``(specs, refused)`` where:

    - ``specs`` is the list of ``{recipe, count, routeId, id}`` directives a
      WHITELISTED recipe resolved to (V1: at most one, ``image-placeholder-grid``).
      Each is recorded STICKY on ``directives.generativeComponents`` by apply and
      materialised by the deterministic builder.
    - ``refused`` is ``[{"component", "reason"}]`` for a recognised but
      UNSUPPORTED generative family (a carousel/slider we cannot generate in V1) -
      the honest no-op signal (stage ``generative_unsupported``). NEVER an
      invented component.

    ``([], [])`` means the prompt is not a generative-component request at all (a
    clock/contact-form widget add), so the caller's existing component_builder
    no-op handles it byte-for-byte. ``decision`` (optional) carries the router's
    ``componentIntent`` (the recipe slug for a recognised recipe noun); the prompt
    is also scanned directly so an injected/conductor decision and a directly
    parsed prompt agree. ``context`` is accepted for parity with the other
    resolvers and is unused in V1 (the route defaults to home). Deterministic,
    offline, no LLM.
    """
    text = (prompt or "").strip().lower()
    component_intent = getattr(decision, "componentIntent", None) if decision else None

    recipe = _match_recipe(text, component_intent)
    if recipe is not None:
        contract = GENERATIVE_RECIPES[recipe]
        count = _parse_count(text, contract)
        spec = {
            "recipe": recipe,
            "count": count,
            "routeId": _DEFAULT_ROUTE_ID,
            "id": recipe,
        }
        return [spec], []

    unsupported = _first_unsupported_cue(text)
    if unsupported is not None:
        return [], [
            {
                "component": unsupported,
                "reason": (
                    f"Komponenttypen {unsupported!r} kan inte genereras ännu. "
                    "Generative Component V1 stödjer bara ett vitlistat recept: "
                    "bildplatshållargrid (image-placeholder-grid). Ingen komponent "
                    "skapades (aldrig en påhittad komponent)."
                ),
            }
        ]

    return [], []
