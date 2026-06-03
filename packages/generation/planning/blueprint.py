"""kor-1c: derive the planning blueprint that the renderer consumes in kor-2.

The Site Plan gains ``sectionPlan`` (section-level intent) and the Generation
Package gains ``contentBlocks`` / ``visualDirection`` / ``qualityRisks`` (the
actual work order). All of it is **derived deterministically** from the
kor-1b Site Brief blueprint (``positioning`` / ``contentStrategy`` /
``businessFacts`` / ``conversion``) plus the chosen scaffold's
``sections.json``:

* When ``OPENAI_API_KEY`` is set the Site Brief carries real ``briefModel``
  intelligence and the derived blueprint reflects it; planningModel may also
  enrich ``sectionPlan`` directly (see ``PlanningChoice`` in plan.py).
* Without a key the brief is the honest kor-1b mock and the blueprint is the
  mock-default. The contract is identical either way — the additive blueprint
  rule from ``docs/heavy-llm-flow/01`` §7.

Honesty is structural, not decorative: ``businessFacts.unknowns`` and
``positioning.avoid`` drive ``qualityRisks`` (so a missing phone becomes
"Do not show phone if missing"), and nothing the prompt did not state is ever
turned into customer copy. Every ``<routeId>.<sectionId>`` address is validated
against the scaffold's ``sections.json`` (the same rail the resolver uses for
dossiers); an invalid section is rejected, never written.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Section ids that carry the primary "offer" list per scaffold, in the order
# we prefer to address them. Mirrors the listing sections declared in each
# scaffold's sections.json (service-list / product-grid / treatment-list /
# practice-grid / selected-work-grid / menu-list). Used to find ONE concrete
# content-block list per site; the renderer (kor-2) reads it for the
# services/products grid.
_OFFER_SECTION_IDS: tuple[str, ...] = (
    "service-list",
    "product-grid",
    "treatment-list",
    "practice-grid",
    "selected-work-grid",
    "menu-list",
)

# Story section ids across scaffolds (about-story / about-story-block).
_ABOUT_STORY_SECTION_IDS: tuple[str, ...] = ("about-story", "about-story-block")

# Primary-CTA fallback when the brief carries no ``conversion.primaryCta``.
# Keyed by conversion slug (primaryAction or a conversionGoals entry). Values
# are customer copy in the brief language; English mirror used for non-sv.
_CTA_BY_SLUG_SV: dict[str, str] = {
    "request_quote": "Be om offert",
    "quote-request": "Be om offert",
    "book": "Boka tid",
    "booking": "Boka tid",
    "call": "Ring oss",
    "purchase": "Handla nu",
    "newsletter-signup": "Prenumerera",
    "contact": "Kontakta oss",
}
_CTA_BY_SLUG_EN: dict[str, str] = {
    "request_quote": "Request a quote",
    "quote-request": "Request a quote",
    "book": "Book a time",
    "booking": "Book a time",
    "call": "Call us",
    "purchase": "Shop now",
    "newsletter-signup": "Subscribe",
    "contact": "Contact us",
}


class SectionPlanEntry(BaseModel):
    """One section-level intent line for the Site Plan ``sectionPlan`` (kor-1c).

    Addressed by ``<routeId>.<sectionId>`` so router, planner, renderer and
    verifier share one address (``docs/heavy-llm-flow/01`` §5). Modelled as a
    list entry (not an open-ended dict) on ``PlanningChoice`` so planningModel
    emits it as well-supported nested structured output — the kor-1b lesson
    about keeping nested structured output shallow and explicit.
    """

    section: str = Field(
        description=(
            "'<routeId>.<sectionId>' address. routeId comes from the Site Plan "
            "routePlan; sectionId must be a section the chosen scaffold declares "
            "in sections.json. Unknown sections are rejected by the resolver."
        )
    )
    goal: str | None = Field(default=None, description="What this section should achieve.")
    copyIntent: str | None = Field(
        default=None, description="Intent for the copy in this section (not the copy itself)."
    )
    visualTreatment: str | None = Field(
        default=None, description="Hint for the visual treatment of the section."
    )
    ctaRole: str | None = Field(
        default=None, description="Role of any CTA here: 'primary', 'secondary' or 'none'."
    )
    proofSources: list[str] = Field(
        default_factory=list,
        description="Where credibility for this section may come from (e.g. 'prompt', 'wizard').",
    )


# ---------------------------------------------------------------------------
# Address rail: valid "<routeId>.<sectionId>" set from the scaffold sections
# ---------------------------------------------------------------------------


def section_addresses(scaffold: dict[str, Any]) -> set[str]:
    """Return every valid ``<routeId>.<sectionId>`` for a scaffold.

    Reads the scaffold's ``sections.json`` (required + optional sections per
    route). This is the rail: any sectionPlan/contentBlocks/sectionTreatments
    address must be in this set or it is rejected.
    """
    sections = scaffold.get("sections") or {}
    addresses: set[str] = set()
    for route_id, spec in sections.items():
        if not isinstance(spec, dict):
            continue
        section_ids = list(spec.get("requiredSections") or []) + list(
            spec.get("optionalSections") or []
        )
        for section_id in section_ids:
            if isinstance(section_id, str) and section_id:
                addresses.add(f"{route_id}.{section_id}")
    return addresses


def resolve_section_plan(
    entries: list[SectionPlanEntry] | list[dict[str, Any]],
    scaffold: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Validate model-proposed section intent against the scaffold rail.

    Returns ``(valid_section_plan, rejected_addresses)``. An entry whose
    ``section`` is not a real ``<routeId>.<sectionId>`` for this scaffold is
    rejected (dropped) rather than written — the same rail the planner uses to
    reject hallucinated dossiers. Empty leaf fields are omitted so the entry
    stays minimal and schema-clean.
    """
    valid = section_addresses(scaffold)
    resolved: dict[str, dict[str, Any]] = {}
    rejected: list[str] = []
    for raw in entries:
        entry = raw if isinstance(raw, dict) else raw.model_dump()
        address = entry.get("section")
        if not isinstance(address, str) or address not in valid:
            if isinstance(address, str) and address:
                rejected.append(address)
            continue
        resolved[address] = _section_intent_fields(entry)
    return resolved, rejected


def _section_intent_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Drop the address + empty leaves from a section-plan entry."""
    fields: dict[str, Any] = {}
    for key in ("goal", "copyIntent", "visualTreatment", "ctaRole"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            fields[key] = value
    proof = entry.get("proofSources")
    if isinstance(proof, list):
        proof_clean = [p for p in proof if isinstance(p, str) and p.strip()]
        if proof_clean:
            fields["proofSources"] = proof_clean
    return fields


def merge_section_plans(
    base: dict[str, dict[str, Any]],
    overlay: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Overlay model section intent on top of the deterministic baseline.

    The deterministic baseline guarantees a usable sectionPlan in every path
    (mock, pinned, real). When planningModel proposed valid section intent it
    augments/overrides the baseline per address so its richer intent wins
    without ever dropping the floor.
    """
    merged: dict[str, dict[str, Any]] = {key: dict(value) for key, value in base.items()}
    for address, fields in overlay.items():
        if address in merged:
            merged[address].update(fields)
        else:
            merged[address] = dict(fields)
    return merged


# ---------------------------------------------------------------------------
# Small brief-reading helpers
# ---------------------------------------------------------------------------


def _obj(brief: dict[str, Any], key: str) -> dict[str, Any]:
    value = brief.get(key)
    return value if isinstance(value, dict) else {}


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _capitalise(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def _is_swedish(brief: dict[str, Any]) -> bool:
    return (brief.get("language") or "sv") == "sv"


def _offer_section(scaffold: dict[str, Any], route_plan: list[dict[str, Any]]) -> str | None:
    """Find the primary offer-list ``<routeId>.<sectionId>`` for this site.

    Prefers a dedicated listing route (services/products/treatments/…) over the
    home route so an ecommerce site lists products on ``products.product-grid``
    rather than the home teaser. Only routes that are actually in the route
    plan and sections that exist in sections.json are considered.
    """
    valid = section_addresses(scaffold)
    route_ids = [r.get("id") for r in route_plan if isinstance(r, dict)]
    ordered = [rid for rid in route_ids if rid != "home"] + [
        rid for rid in route_ids if rid == "home"
    ]
    for route_id in ordered:
        for section_id in _OFFER_SECTION_IDS:
            address = f"{route_id}.{section_id}"
            if address in valid:
                return address
    return None


def _about_story_section(
    scaffold: dict[str, Any], route_plan: list[dict[str, Any]]
) -> str | None:
    valid = section_addresses(scaffold)
    route_ids = {r.get("id") for r in route_plan if isinstance(r, dict)}
    for route_id in route_ids:
        for section_id in _ABOUT_STORY_SECTION_IDS:
            address = f"{route_id}.{section_id}"
            if address in valid:
                return address
    return None


def _primary_cta(brief: dict[str, Any]) -> str:
    conversion = _obj(brief, "conversion")
    explicit = _str(conversion.get("primaryCta"))
    if explicit:
        return explicit
    table = _CTA_BY_SLUG_SV if _is_swedish(brief) else _CTA_BY_SLUG_EN
    action = _str(conversion.get("primaryAction"))
    if action and action in table:
        return table[action]
    for goal in _list_str(brief.get("conversionGoals")):
        if goal in table:
            return table[goal]
    return table["contact"]


def _hero_headline(brief: dict[str, Any]) -> str | None:
    """Honest hero headline source order: positioning angle, then company name.

    Never the raw prompt (rå prompt blir aldrig kundcopy) and never a fabricated
    fact. Returns None when no honest source exists so the hero block is omitted
    rather than invented.
    """
    positioning = _obj(brief, "positioning")
    one_liner = _str(positioning.get("oneLiner"))
    if one_liner:
        return one_liner
    content_strategy = _obj(brief, "contentStrategy")
    hero_angle = _str(content_strategy.get("heroAngle"))
    if hero_angle:
        return _capitalise(hero_angle)
    company = _str(brief.get("companyName"))
    if company:
        return company
    return None


def _hero_subheadline(brief: dict[str, Any]) -> str | None:
    positioning = _obj(brief, "positioning")
    for key in ("differentiator", "audienceNeed", "localAngle"):
        value = _str(positioning.get(key))
        if value:
            return _capitalise(value)
    content_strategy = _obj(brief, "contentStrategy")
    return _str(content_strategy.get("offerStrategy"))


# ---------------------------------------------------------------------------
# Deterministic blueprint derivation
# ---------------------------------------------------------------------------


def derive_section_plan(
    brief: dict[str, Any],
    scaffold: dict[str, Any],
    route_plan: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Deterministic section-level intent for the key sections of the site.

    Always covers the hero; adds the offer-list section, a trust-proof intent
    and an about-story intent when the chosen scaffold + route plan declare
    them. Every key is guaranteed valid against sections.json.
    """
    valid = section_addresses(scaffold)
    plan: dict[str, dict[str, Any]] = {}

    if "home.hero" in valid:
        positioning = _obj(brief, "positioning")
        content_strategy = _obj(brief, "contentStrategy")
        plan["home.hero"] = _drop_empty(
            {
                "goal": "position the business fast",
                "copyIntent": _str(positioning.get("oneLiner"))
                or _str(content_strategy.get("heroAngle")),
                "ctaRole": "primary",
            }
        )

    offer = _offer_section(scaffold, route_plan)
    if offer is not None:
        content_strategy = _obj(brief, "contentStrategy")
        plan[offer] = _drop_empty(
            {
                "goal": "show concrete services without generic filler",
                "copyIntent": _str(content_strategy.get("offerStrategy")),
                "ctaRole": "secondary",
            }
        )

    if "home.trust-proof" in valid:
        plan["home.trust-proof"] = {
            "goal": "build credibility without fake claims",
            "proofSources": ["prompt", "wizard"],
        }

    about = _about_story_section(scaffold, route_plan)
    if about is not None:
        positioning = _obj(brief, "positioning")
        plan[about] = _drop_empty(
            {
                "goal": "build trust through a specific, human story",
                "copyIntent": _str(positioning.get("differentiator"))
                or _str(positioning.get("audienceNeed")),
                "ctaRole": "none",
            }
        )

    return plan


def derive_content_blocks(
    brief: dict[str, Any],
    scaffold: dict[str, Any],
    route_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-section copy keyed by ``<routeId>.<sectionId>`` (the kor-2 work order).

    Emits a hero block (only with an honest headline source) and an offer-list
    block built from ``servicesMentioned`` (the concrete services the prompt
    stated). No services stated -> no fabricated list. Always schema-valid and
    every key validated against sections.json.
    """
    valid = section_addresses(scaffold)
    blocks: dict[str, Any] = {}

    headline = _hero_headline(brief)
    if "home.hero" in valid and headline is not None:
        hero = _drop_empty(
            {
                "headline": headline,
                "subheadline": _hero_subheadline(brief),
                "primaryCta": _primary_cta(brief),
            }
        )
        blocks["home.hero"] = hero

    offer = _offer_section(scaffold, route_plan)
    services = _list_str(brief.get("servicesMentioned"))
    if offer is not None and services:
        blocks[offer] = [{"title": _capitalise(service)} for service in services]

    return blocks


def derive_visual_direction(
    brief: dict[str, Any],
    scaffold: dict[str, Any],
    route_plan: list[dict[str, Any]],
    *,
    section_treatments_catalogue: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Per-industry visual direction grounded in the brief's positioning tone.

    ``mood`` mirrors ``positioning.tone``; ``heroStyle`` / ``colorIntent`` are
    chosen from tone keywords (falling back to the conversion action) so four
    industries read clearly differently. ``sectionTreatments`` only references
    a treatment id the catalogue actually registers (kor-3b tightens these to
    enums); unknown sections are skipped.
    """
    positioning = _obj(brief, "positioning")
    tone = _str(positioning.get("tone")) or ", ".join(_list_str(brief.get("tone")))
    low = tone.lower()
    is_sv = _is_swedish(brief)
    conversion = _obj(brief, "conversion")
    action = _str(conversion.get("primaryAction")) or ""

    direction: dict[str, Any] = {
        "mood": tone or ("tydlig och trovärdig" if is_sv else "clear and trustworthy"),
        "density": _density(low, action, scaffold),
        "heroStyle": _hero_style(low, action),
        "colorIntent": _color_intent(low),
    }

    treatment = _section_treatment(scaffold, route_plan, section_treatments_catalogue)
    if treatment is not None:
        direction["sectionTreatments"] = treatment

    image_brief = _image_brief(brief)
    if image_brief is not None:
        direction["imageBriefs"] = [image_brief]

    direction["layoutSignals"] = _layout_signals(low, scaffold)
    return direction


def derive_quality_risks(brief: dict[str, Any]) -> list[str]:
    """Honesty guardrails derived (partly) from ``businessFacts.unknowns``.

    Maps each unknown / ``positioning.avoid`` phrase to a canonical risk string
    (missing phone -> "Do not show phone if missing"; "påhittade certifieringar"
    -> "No fake certifications"). Adds a booking guardrail when the conversion
    is booking-driven, and reinforces missing contact channels. Never invents a
    risk the brief does not signal; falls back to a minimal honesty floor only
    when the brief carries no signals at all.
    """
    business_facts = _obj(brief, "business_facts") or _obj(brief, "businessFacts")
    positioning = _obj(brief, "positioning")
    phrases = _list_str(business_facts.get("unknowns")) + _list_str(positioning.get("avoid"))

    found: set[str] = set()
    for phrase in phrases:
        risk = _classify_risk(phrase)
        if risk is not None:
            found.add(risk)

    if not _str(brief.get("contactPhone")) and _mentions(phrases, ("telefon", "phone")):
        found.add("Do not show phone if missing")
    if not _str(brief.get("contactEmail")) and _mentions(phrases, ("e-post", "epost", "email", "mejl")):
        found.add("Do not show email if missing")

    conversion = _obj(brief, "conversion")
    goals = _list_str(brief.get("conversionGoals"))
    if (_str(conversion.get("primaryAction")) in {"book", "booking"}) or (
        {"book", "booking"} & set(goals)
    ):
        found.add("Do not offer booking unless booking exists")

    ordered = [risk for risk in _RISK_ORDER if risk in found]
    if ordered:
        return ordered

    # No blueprint signals at all (legacy brief): reinforce from missing
    # contact scalars, then a minimal honesty floor that never fabricates.
    fallback: list[str] = []
    if not _str(brief.get("contactPhone")):
        fallback.append("Do not show phone if missing")
    if not _str(brief.get("contactEmail")):
        fallback.append("Do not show email if missing")
    fallback.extend(["No fake certifications", "No invented reviews"])
    return [risk for risk in _RISK_ORDER if risk in set(fallback)]


def build_generation_blueprint(
    brief: dict[str, Any],
    scaffold: dict[str, Any],
    route_plan: list[dict[str, Any]],
    *,
    section_treatments_catalogue: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Convenience: derive the three Generation Package blueprint fields.

    Returns a dict with only the keys that have content so the caller can
    splat them into the package without emitting empty objects.
    """
    blueprint: dict[str, Any] = {}
    content_blocks = derive_content_blocks(brief, scaffold, route_plan)
    if content_blocks:
        blueprint["contentBlocks"] = content_blocks
    visual_direction = derive_visual_direction(
        brief,
        scaffold,
        route_plan,
        section_treatments_catalogue=section_treatments_catalogue,
    )
    if visual_direction:
        blueprint["visualDirection"] = visual_direction
    quality_risks = derive_quality_risks(brief)
    if quality_risks:
        blueprint["qualityRisks"] = quality_risks
    return blueprint


# ---------------------------------------------------------------------------
# visualDirection / qualityRisks internals
# ---------------------------------------------------------------------------


def _density(tone_low: str, action: str, scaffold: dict[str, Any]) -> str:
    scaffold_id = scaffold.get("id")
    if scaffold_id in {"ecommerce-lite", "agency-studio"} or action == "purchase":
        return "spacious"
    if any(word in tone_low for word in ("varm", "personlig", "stilren", "warm")):
        return "spacious"
    return "medium"


def _hero_style(tone_low: str, action: str) -> str:
    if any(word in tone_low for word in ("lugn", "calm")):
        return "portrait_with_text"
    if any(word in tone_low for word in ("jordnära", "jordnara", "hantverk", "craft")):
        return "image_led_gallery"
    if any(word in tone_low for word in ("varm", "warm")):
        return "full_bleed_image"
    if action == "purchase":
        return "image_led_gallery"
    if action in {"book", "booking"}:
        return "full_bleed_image"
    if action in {"request_quote", "quote-request", "call"}:
        return "split_with_image"
    return "centered_statement"


def _color_intent(tone_low: str) -> str:
    if any(word in tone_low for word in ("varm", "warm")):
        return "soft_warm_neutral"
    if any(word in tone_low for word in ("lugn", "calm", "professionell", "professional")):
        return "cool_calm_neutral"
    if any(word in tone_low for word in ("jordnära", "jordnara", "hantverk", "earth")):
        return "earthy_neutral_with_clay_accent"
    if any(word in tone_low for word in ("trygg", "kunnig", "rak", "trust")):
        return "warm_neutral_with_electric_accent"
    return "neutral_professional"


def _section_treatment(
    scaffold: dict[str, Any],
    route_plan: list[dict[str, Any]],
    catalogue: dict[str, list[str]] | None,
) -> dict[str, str] | None:
    if not catalogue:
        return None
    offer = _offer_section(scaffold, route_plan)
    if offer is None:
        return None
    _, _, section_id = offer.partition(".")
    options = catalogue.get(section_id)
    if not options:
        return None
    return {offer: options[0]}


def _image_brief(brief: dict[str, Any]) -> str | None:
    subject = _str(brief.get("businessTypeGuess"))
    location = _str(brief.get("locationHint"))
    is_sv = _is_swedish(brief)
    if not subject and not location:
        return None
    if is_sv:
        base = subject or "verksamheten"
        where = f" i {location}" if location else ""
        return f"{_capitalise(base)}{where}, naturligt ljus, trovärdigt och tryggt intryck"
    base = subject or "the business"
    where = f" in {location}" if location else ""
    return f"{_capitalise(base)}{where}, natural light, credible and trustworthy feel"


def _layout_signals(tone_low: str, scaffold: dict[str, Any]) -> dict[str, bool]:
    scaffold_id = scaffold.get("id")
    trust_heavy = scaffold_id in {"local-service-business", "clinic-healthcare", "professional-services"}
    calm = any(word in tone_low for word in ("trygg", "lugn", "professionell", "trust", "calm"))
    return {
        "useTrustBandNearHero": bool(trust_heavy or calm),
        "avoidOverlyPlayfulShapes": scaffold_id != "agency-studio",
    }


def _drop_empty(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value not in (None, "", [])}


def _mentions(phrases: list[str], tokens: tuple[str, ...]) -> bool:
    joined = " ".join(phrases).lower()
    return any(token in joined for token in tokens)


# Canonical risk strings in a stable display order. derive_quality_risks emits
# the subset the brief actually signals, in this order, so output is
# deterministic.
_RISK_ORDER: tuple[str, ...] = (
    "Do not show phone if missing",
    "Do not show email if missing",
    "Do not show opening hours if missing",
    "No fake certifications",
    "No invented reviews",
    "No fake prices",
    "No promised delivery times unless known",
    "Do not show stock levels if missing",
    "No medical guarantees",
    "Do not offer booking unless booking exists",
)


def _classify_risk(phrase: str) -> str | None:
    """Map one unknown / avoid phrase to a canonical honesty risk string.

    First match wins per phrase, with shipping/stock checked before the generic
    price token so 'fraktpriser' reads as a delivery risk, not a price risk.
    """
    p = phrase.lower()
    if any(token in p for token in ("frakt", "shipping", "leverans", "delivery")):
        return "No promised delivery times unless known"
    if any(token in p for token in ("lager", "stock", "saldo")):
        return "Do not show stock levels if missing"
    if any(token in p for token in ("telefon", "phone")):
        return "Do not show phone if missing"
    if any(token in p for token in ("e-post", "epost", "email", "mejl")):
        return "Do not show email if missing"
    if any(token in p for token in ("öppettid", "oppettid", "opening", "hours")):
        return "Do not show opening hours if missing"
    if any(token in p for token in ("cert", "legitimation", "licens", "license")):
        return "No fake certifications"
    if any(token in p for token in ("recension", "omdöme", "omdome", "review")):
        return "No invented reviews"
    if any(token in p for token in ("medicin", "medical")):
        return "No medical guarantees"
    if any(token in p for token in ("pris", "price")):
        return "No fake prices"
    return None
