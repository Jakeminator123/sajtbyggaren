"""Follow-up target resolver (Target Resolver V1).

Turns a natural Swedish place expression ("lägg till en FAQ-sektion på
kontaktsidan", "längst ner på startsidan") into a confident, validated
structured target so a follow-up action lands on the RIGHT page/slot instead of
silently defaulting to the home route.

Pure, offline, deterministic: no LLM, no disk I/O, no new deps. It reads the
follow-up prompt, the router's already-parsed decision (for the coarse position
it resolved) and the site's OWN scaffold ``routes.json`` (to validate the page),
and returns a small dict::

    {
      "routeId": str | None,      # validated scaffold route, never invented
      "placement": str,           # "top" | "bottom" | "before-contact"
      "sectionId": str | None,    # carried from the decision / section_map
      "confidence": float,        # 0.0 - 1.0; below THRESHOLD -> caller falls back
      "rationale": str,           # honest Swedish explanation
    }

Behaviour-preserving by contract: a low-confidence result (no page named, a page
the scaffold does not declare, or only a coarse position) returns ``routeId =
None`` with ``confidence`` below ``CONFIDENCE_THRESHOLD`` so the caller keeps its
current default. Only an explicit, scaffold-validated page phrase raises the
confidence above the threshold, and the placement it reports is byte-identical to
what the router already computed - so wiring it in stays additive.

The page-phrase lexicon is a broader sibling of the router's private
``_ROUTE_LABEL_IDS`` (packages/generation/orchestration/router/classify.py): it
adds home/products/menu/booking phrasings the router never needed, and validates
every candidate against THIS site's ``defaultRoutes`` (exactly like
route_directives does for route_remove) so an unknown or off-scaffold page is
refused, not faked.

The schema's route-order placement enum is ["top", "bottom", "before-contact"]
(governance/schemas/project-input.schema.json directives.mountedSections); a
relative expression ("under tjänster", "efter X") cannot be expressed in it, so
it lowers confidence and falls back to the default slot rather than guessing.

Conventions: identifiers + comments in English (governance/rules/code-in-english.md);
operator-facing rationale strings in Swedish (AGENTS.md språk).
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["CONFIDENCE_THRESHOLD", "resolve_target"]

# Caller contract: treat a result at or above this confidence as actionable;
# below it, keep the current default behaviour (no change). The threshold sits
# between the "page validated" band (>= 0.75) and the "coarse signal only" band
# (<= 0.35), so only an explicit, scaffold-validated page can flip a consumer.
CONFIDENCE_THRESHOLD = 0.5

_CONFIDENCE_PAGE_AND_POSITION = 0.9
_CONFIDENCE_PAGE_ONLY = 0.75
_CONFIDENCE_COARSE = 0.35
_CONFIDENCE_NONE = 0.0

# Schema route-order placement enum (project-input.schema.json
# directives.mountedSections.position). "before-contact" == the default slot, so
# it is also the honest fallback when no coarse position was parsed.
_DEFAULT_PLACEMENT = "before-contact"

# Swedish (and a few English) page phrases -> canonical scaffold routeId. Every
# candidate is validated against the site's ACTUAL defaultRoutes before use, so a
# phrase that maps to a route this scaffold does not declare ("tjänstesidan" on
# an e-commerce site) resolves to None, never an invented page. Section-type
# words that double as a nav or component noun ("menyn" = nav, "galleri" =
# section) are deliberately listed ONLY in their explicit "-sida(n)" page form,
# so a placement INTO a section is never mistaken for a whole page.
_PAGE_PHRASE_TO_ROUTE = {
    # home
    "startsidan": "home", "startsida": "home", "förstasidan": "home",
    "förstasida": "home", "landningssidan": "home", "landningssida": "home",
    "hemsidan": "home", "hemsida": "home", "home": "home",
    # about
    "om oss-sidan": "about", "om-oss-sidan": "about", "om oss sidan": "about",
    "om-oss-sida": "about", "om oss sida": "about", "om oss": "about",
    "om-oss": "about", "about": "about",
    # contact
    "kontaktsidan": "contact", "kontaktsida": "contact",
    "kontakta oss": "contact", "kontakt": "contact", "contact": "contact",
    # services
    "tjänstesidan": "services", "tjänstesida": "services",
    "tjänsterna": "services", "tjänster": "services", "services": "services",
    # products
    "produktsidan": "products", "produktsida": "products",
    "produkterna": "products", "produkter": "products", "products": "products",
    # menu (restaurant) - only explicit page phrasings, never bare "menyn" (nav)
    "menysidan": "menu", "menysida": "menu", "matsedeln": "menu",
    "matsedel": "menu",
    # booking (restaurant)
    "bokningssidan": "booking", "bokningssida": "booking",
    "bokning": "booking", "booking": "booking",
}
# Longest-first so "kontaktsidan" wins over a bare "kontakt" and "tjänstesidan"
# over "tjänster" - specificity keeps the match deterministic.
_PAGE_PHRASES = tuple(sorted(_PAGE_PHRASE_TO_ROUTE, key=len, reverse=True))

# Relative-placement prepositions ("under tjänster", "efter galleriet"). They
# point at a slot RELATIVE to an existing section, which the schema's coarse
# top/bottom/before-contact enum cannot express, so a phrase that directly
# follows one is NOT read as a page selection (it would otherwise mis-resolve
# "under tjänster" to the services page).
_RELATIVE_CUES = (
    "under", "efter", "ovanför", "ovanpå", "nedanför", "före",
    "below", "above", "after", "before",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _word_present(text: str, phrase: str) -> bool:
    """Whole-phrase match so "kontakt" never matches inside "kontaktformulär"."""
    return (
        re.search(r"(?<![\wåäö])" + re.escape(phrase) + r"(?![\wåäö])", text)
        is not None
    )


def _relative_cue_before(text: str, phrase: str) -> bool:
    cues = "|".join(re.escape(cue) for cue in _RELATIVE_CUES)
    pattern = (
        r"(?<![\wåäö])(?:" + cues + r")\s+" + re.escape(phrase) + r"(?![\wåäö])"
    )
    return re.search(pattern, text) is not None


def _scaffold_route_ids(scaffold_routes: Any) -> set[str]:
    """Collect the routeIds the site's scaffold actually declares (defaultRoutes)."""
    default_routes = (
        scaffold_routes.get("defaultRoutes")
        if isinstance(scaffold_routes, dict)
        else None
    )
    ids: set[str] = set()
    if isinstance(default_routes, list):
        for route in default_routes:
            if isinstance(route, dict) and isinstance(route.get("id"), str):
                ids.add(route["id"])
    return ids


def _match_page_phrase(text: str) -> tuple[str | None, str | None]:
    """Return (phrase, candidate_route_id) for the first page phrase, else (None, None)."""
    for phrase in _PAGE_PHRASES:
        if _word_present(text, phrase):
            return phrase, _PAGE_PHRASE_TO_ROUTE[phrase]
    return None, None


def _placement_from_decision(decision: Any) -> tuple[str, str | None]:
    """Reuse the router's coarse position; map top/bottom, else the default slot.

    Returns ``(placement, raw_position)`` where ``placement`` is a schema-valid
    enum value and ``raw_position`` is the router's original position (so the
    caller can tell an explicit top/bottom from the implicit default). left/
    right/center are intra-section, not route-order, so they fall to the default.
    """
    target = getattr(decision, "target", None)
    position = getattr(target, "position", None) if target is not None else None
    if position in ("top", "bottom"):
        return position, position
    return _DEFAULT_PLACEMENT, position


def _resolve_section_id(
    decision: Any, route_id: str | None, section_map: dict[str, list[str]] | None
) -> str | None:
    """Carry the decision's sectionId, or resolve its ordinal via ``section_map``.

    Prefers a sectionId the router already resolved. Failing that, and only when
    a concrete page resolved, an optional ``section_map`` (``routeId -> ordered
    sectionIds``, the same shape as RouterContext.routeSections) lets a parsed
    ordinal ("andra sektionen") become a concrete sectionId - without the
    resolver ever touching disk. Returns None when nothing resolves.
    """
    target = getattr(decision, "target", None)
    section_id = getattr(target, "sectionId", None) if target is not None else None
    if isinstance(section_id, str) and section_id:
        return section_id
    ordinal = getattr(target, "sectionOrdinal", None) if target is not None else None
    if (
        route_id is not None
        and isinstance(section_map, dict)
        and isinstance(ordinal, int)
        and ordinal > 0
    ):
        sections = section_map.get(route_id)
        if isinstance(sections, list) and ordinal <= len(sections):
            candidate = sections[ordinal - 1]
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def resolve_target(
    prompt: str,
    decision: Any,
    scaffold_routes: Any,
    *,
    section_map: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Resolve a natural place expression to a validated structured target.

    ``prompt`` is the raw follow-up text; ``decision`` is the router's
    ``RouterDecision`` (only its ``target.position``/``sectionId`` are read);
    ``scaffold_routes`` is the loaded ``routes.json`` (validated against, like
    route_directives). ``section_map`` is optional and maps a routeId to its
    ordered sectionIds so a parsed ordinal can resolve to a concrete section.

    Returns a dict ``{routeId, placement, sectionId, confidence, rationale}``.
    Honest by construction: an unknown page, an off-scaffold page, or a relative
    expression the schema cannot express yields ``routeId = None`` with a
    confidence below ``CONFIDENCE_THRESHOLD``, so the caller keeps its current
    default and behaviour does not change. Deterministic, offline, no LLM.
    """
    text = _normalize(prompt)
    placement, raw_position = _placement_from_decision(decision)
    has_explicit_position = raw_position in ("top", "bottom")

    phrase, candidate = _match_page_phrase(text)
    scaffold_ids = _scaffold_route_ids(scaffold_routes)
    relative = phrase is not None and _relative_cue_before(text, phrase)

    route_id: str | None = None
    if phrase is not None and not relative and candidate in scaffold_ids:
        route_id = candidate

    section_id = _resolve_section_id(decision, route_id, section_map)

    if route_id is not None:
        if has_explicit_position:
            confidence = _CONFIDENCE_PAGE_AND_POSITION
            rationale = (
                f"Sidan {route_id!r} matchades mot scaffoldens routes och "
                f"placeringen {placement!r} lästes från prompten."
            )
        else:
            confidence = _CONFIDENCE_PAGE_ONLY
            rationale = (
                f"Sidan {route_id!r} matchades mot scaffoldens routes; ingen "
                f"explicit placering angavs, använder default-slot "
                f"({_DEFAULT_PLACEMENT})."
            )
    elif relative:
        confidence = _CONFIDENCE_COARSE
        rationale = (
            "En relativ placering ('under'/'efter' ...) känns igen men kan inte "
            "uttryckas i schemats top/bottom/before-contact; faller tillbaka "
            "till default-slot och nuvarande default-target."
        )
    elif phrase is not None:
        confidence = _CONFIDENCE_COARSE
        rationale = (
            f"Sidan för {phrase!r} ({candidate}) finns inte bland scaffoldens "
            "sidor; ingen route resolveras (aldrig en påhittad sida)."
        )
    elif has_explicit_position:
        confidence = _CONFIDENCE_COARSE
        rationale = (
            f"Ingen sida nämndes; endast en grov placering ({placement}) "
            "hittades, faller tillbaka till nuvarande default-target."
        )
    else:
        confidence = _CONFIDENCE_NONE
        rationale = (
            "Inget place-uttryck kändes igen; faller tillbaka till nuvarande "
            "default-target."
        )

    return {
        "routeId": route_id,
        "placement": placement,
        "sectionId": section_id,
        "confidence": confidence,
        "rationale": rationale,
    }
