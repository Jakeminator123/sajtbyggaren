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

kor-1c-copy closes the visible copy gap left after kor-2: the renderer already
consumes ``contentBlocks.<route>.story``, ``faq[]`` and the offer service
summaries, but kor-1c emitted only structure + hero + offer *titles*. This
module now also composes, for the Swedish baseline industries, a grounded
company ``story`` (from positioning), branschrelevanta ``faq`` pairs and honest
per-service ``summary``/``bullets`` - so the four live branches render as four
clearly different companies instead of the generic template.

Honesty is structural, not decorative: ``businessFacts.unknowns`` and
``positioning.avoid`` drive ``qualityRisks`` (so a missing phone becomes
"Do not show phone if missing"), and nothing the prompt did not state is ever
turned into customer copy (the story is composed from the brief's own
positioning angle, never a fabricated fact or the raw prompt). Every
``<routeId>.<sectionId>`` address is validated against the scaffold's
``sections.json`` (the same rail the resolver uses for dossiers); an invalid
section is rejected, never written.
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

# Section ids (in preference order) that may carry the company story content
# block. Mirrors ``build.blueprint_render._STORY_SECTION_IDS`` so the renderer
# reads the same block the planner writes. about-story is preferred over the
# home story teaser so the block lands on the canonical "story" section.
_STORY_BLOCK_SECTION_IDS: tuple[str, ...] = ("about-story", "about-story-block", "story")

# Section ids that may carry an FAQ list. Mirrors
# ``build.blueprint_render._FAQ_SECTION_IDS``. The renderer only reads an FAQ
# block on the ``home`` or ``faq`` route, so an offer scaffold without a home
# FAQ section (ecommerce-lite) honestly carries no blueprint FAQ.
_FAQ_BLOCK_SECTION_IDS: tuple[str, ...] = ("faq", "faq-accordion")
_FAQ_BLOCK_ROUTE_IDS: tuple[str, ...] = ("home", "faq")

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


# ---------------------------------------------------------------------------
# kor-1c-copy: deterministic, honest, industry-near copy library
# ---------------------------------------------------------------------------
#
# kor-2 made the renderer consume contentBlocks.<route>.story, .faq[] and the
# offer service-summaries, but kor-1c only emitted structure + hero + offer
# *titles*, so the four live branches fell back to the generic template for
# story/FAQ/service descriptions. This library closes that gap: it lets the
# deterministic planning path compose rich, branschnära copy from what the Site
# Brief already states.
#
# Honesty (docs/heavy-llm-flow/04 §9, non-negotiable):
#   * The story is COMPOSED FROM the Site Brief's own positioning fields
#     (oneLiner / differentiator / localAngle) - never a fabricated fact and
#     never the raw prompt.
#   * Service summaries describe the *service category* the brief listed in
#     ``servicesMentioned``; they assert no certification, review, price or
#     contact detail about the specific business.
#   * FAQ answers are grounded in the brief's services / conversion intent /
#     differentiator. No phone, e-post, opening hours, price or cert is ever
#     invented (those stay in businessFacts.unknowns / qualityRisks).
#   * Enrichment only runs for Swedish briefs that carry the kor-1b positioning
#     blueprint, so a legacy brief (no positioning) stays byte-identical and the
#     "mock without key == identical contract" rule holds.

# Industry detection tokens (most specific first). Mirrors the baseline
# detection in ``brief/extract.py`` so the mock brief and the derived blueprint
# agree on the industry. Matched as a lowercased substring over
# businessTypeGuess + servicesMentioned + positioning text.
_INDUSTRY_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("electrician", ("electrician", "elektr", "elinstallation", "elarbete")),
    ("hair-salon", ("hair-salon", "hairdress", "frisör", "frisor", "salong", "barber")),
    ("naprapath", ("naprapath", "naprapat")),
    ("ceramics", ("ceramics", "ceramic", "keramik", "lergods", "drej", "pottery")),
)

# Per-service summary + bullets, keyed by the normalised service token the brief
# lists in ``servicesMentioned``. Mirrors the hand-authored kor-2 baseline
# fixtures (tests/fixtures/blueprints/*.blueprint.json) so the deterministic
# mock output matches "what a real briefModel/planning enrichment produces".
# Every value is an honest description of the service category, not a claim
# about the specific business.
_SERVICE_COPY_SV: dict[str, tuple[str, tuple[str, ...]]] = {
    # electrician
    "elinstallationer": ("Säkra installationer för hem och företag.", ("nyinstallation", "ombyggnad")),
    "elinstallation": ("Säkra installationer för hem och företag.", ("nyinstallation", "ombyggnad")),
    "felsökning": ("Snabb felsökning när något slutar fungera.", ("jordfelsbrytare", "kortslutning")),
    "laddboxar": ("Installation av laddbox för elbil.", ("hemmaladdning", "föreningar")),
    "laddbox": ("Installation av laddbox för elbil.", ("hemmaladdning", "föreningar")),
    # hair-salon
    "klippning": ("Klippning för dam och herr.", ("dam", "herr")),
    "färgning": ("Färg som håller och ser naturlig ut.", ("helfärg", "toning")),
    "slingor": ("Slingor för dimension och lyster.", ("folieslingor", "balayage")),
    # naprapath
    "naprapati": ("Behandling av besvär i muskler och leder.", ("rygg", "nacke")),
    "massage": ("Avspännande och behandlande massage.", ("triggerpunkter", "spänningar")),
    "rehabträning": ("Övningar för att förebygga återfall.", ("hemträning", "uppföljning")),
    "rehabilitering": ("Övningar för att förebygga återfall.", ("hemträning", "uppföljning")),
    # ceramics
    "skålar": ("Handdrejade skålar för vardagsbruk.", ("seladon", "matt glasyr")),
    "vaser": ("Stillsamma vaser för snitt och kvistar.", ("lergods", "unik form")),
    "muggar": ("Muggar som tål vardag och diskmaskin.", ("öra", "stengods")),
}

# Honest per-industry fallback summary for a service the lexicon does not key
# individually, so every item in a baseline offer list carries a summary (the
# renderer's offer override requires it) without fabricating a claim.
_INDUSTRY_GENERIC_SUMMARY_SV: dict[str, str] = {
    "electrician": "El- och installationsarbete utfört på ett säkert sätt.",
    "hair-salon": "Behandling hos frisör efter dina önskemål.",
    "naprapath": "Behandling anpassad efter dina besvär.",
    "ceramics": "Handgjord keramik tillverkad i liten skala.",
}

# FAQ question for the conversion pair, keyed by the brief's primary action /
# conversion goal. The ANSWER is grounded copy that never promises a channel
# (phone) or value (price) the brief does not state.
_FAQ_CONVERSION_SV: dict[str, tuple[str, str]] = {
    "request_quote": ("Hur får jag en offert?", "Berätta vad du behöver så återkommer vi med ett tydligt förslag."),
    "quote-request": ("Hur får jag en offert?", "Berätta vad du behöver så återkommer vi med ett tydligt förslag."),
    "book": ("Hur bokar jag tid?", "Hör av dig så hittar vi en tid som passar dig."),
    "booking": ("Hur bokar jag tid?", "Hör av dig så hittar vi en tid som passar dig."),
    "purchase": ("Hur handlar jag?", "Lägg det du vill ha i varukorgen och följ stegen i kassan."),
    "call": ("Hur kommer jag i kontakt?", "Hör av dig via kontaktsidan så återkopplar vi så snart vi kan."),
    "contact": ("Hur kommer jag i kontakt?", "Hör av dig via kontaktsidan så återkopplar vi så snart vi kan."),
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


def _norm_service(value: Any) -> str:
    """Whitespace/case-normalised key for matching a service to the lexicon."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip().casefold()


def _detect_industry(brief: dict[str, Any]) -> str | None:
    """Return a baseline industry key from the brief, else None.

    Reads businessTypeGuess first (the sharpest signal), then services and the
    positioning angle, mirroring ``brief/extract.py``'s keyword detection so the
    mock brief and the derived blueprint agree on the industry.
    """
    positioning = _obj(brief, "positioning")
    haystack = " ".join(
        [
            _str(brief.get("businessTypeGuess")) or "",
            " ".join(_list_str(brief.get("servicesMentioned"))),
            _str(positioning.get("oneLiner")) or "",
            _str(positioning.get("tone")) or "",
        ]
    ).lower()
    for key, tokens in _INDUSTRY_TOKENS:
        if any(token in haystack for token in tokens):
            return key
    return None


def _enrichment_enabled(brief: dict[str, Any]) -> bool:
    """Whether to emit the rich story/FAQ/offer-summary copy for this brief.

    Gated on a Swedish brief that carries the kor-1b positioning blueprint. A
    legacy brief without positioning (e.g. the builder's dossier-derived mock
    brief) therefore stays byte-identical, and non-Swedish briefs keep the
    template rather than risk mismatched-language copy - the same conservative
    rule ``brief/extract.py`` uses for its rich profiles.
    """
    if not _is_swedish(brief):
        return False
    positioning = _obj(brief, "positioning")
    return bool(
        _str(positioning.get("oneLiner"))
        or _str(positioning.get("differentiator"))
        or _str(positioning.get("audienceNeed"))
        or _str(positioning.get("localAngle"))
    )


def _service_summary_and_bullets(
    service: str, industry: str
) -> tuple[str, list[str]]:
    """Honest summary + bullets for one offered service in a baseline industry.

    Uses the per-service lexicon when the token is known, else the industry's
    generic-but-honest description so every offer item carries a summary (the
    renderer only overrides the dossier offer list when each item has one).
    """
    keyed = _SERVICE_COPY_SV.get(_norm_service(service))
    if keyed is not None:
        summary, bullets = keyed
        return summary, list(bullets)
    return _INDUSTRY_GENERIC_SUMMARY_SV[industry], []


def _sentence(text: str) -> str:
    """Capitalise and terminate one fragment as a standalone sentence."""
    cleaned = text.strip().rstrip(".")
    if not cleaned:
        return ""
    return f"{cleaned[:1].upper()}{cleaned[1:]}."


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
    # List (not set) comprehension: preserve route_plan order so the chosen
    # about-story address is deterministic across runs (set iteration order of
    # strings varies with hash randomization). Mirrors _primary_offer_section.
    route_ids = [r.get("id") for r in route_plan if isinstance(r, dict)]
    for route_id in route_ids:
        for section_id in _ABOUT_STORY_SECTION_IDS:
            address = f"{route_id}.{section_id}"
            if address in valid:
                return address
    return None


def _story_block_address(scaffold: dict[str, Any], route_plan: list[dict[str, Any]]) -> str | None:
    """Return the ``<routeId>.<sectionId>`` to carry the company story block.

    Prefers a dedicated about-story section (the canonical home for a story)
    over the home story teaser, across the routes actually planned. Only
    addresses the renderer reads (home/about x story sections) are considered,
    and every candidate is validated against the scaffold's sections.json.
    """
    valid = section_addresses(scaffold)
    route_ids = [r.get("id") for r in route_plan if isinstance(r, dict)]
    for section_id in _STORY_BLOCK_SECTION_IDS:
        for route_id in route_ids:
            address = f"{route_id}.{section_id}"
            if address in valid:
                return address
    return None


def _faq_block_address(scaffold: dict[str, Any]) -> str | None:
    """Return the ``<routeId>.<sectionId>`` to carry the FAQ block, else None.

    The renderer only reads an FAQ block on the home or faq route, so a scaffold
    whose home route has no FAQ section (ecommerce-lite) honestly carries no
    blueprint FAQ rather than addressing a section the renderer never reads.
    """
    valid = section_addresses(scaffold)
    for route_id in _FAQ_BLOCK_ROUTE_IDS:
        for section_id in _FAQ_BLOCK_SECTION_IDS:
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
# Gap 3a: keep the company offer/tagline out of the offer service cards
# ---------------------------------------------------------------------------
#
# briefModel occasionally files the hero offer/tagline line (the
# ``positioning.oneLiner`` headline or the hero subheadline) under
# ``servicesMentioned``. derive_content_blocks would then turn that line into an
# offer-list item, so the tagline renders as a bogus service card next to the
# real services. The guard below drops a servicesMentioned entry whose
# normalised text is ~equal to a company offer/tagline phrase. It only ever
# REMOVES an item - it never fabricates copy - so the honesty engine
# (quality_gate/critic.py, docs/heavy-llm-flow/04 §9) is respected by
# construction, and it is a no-op for a brief that carries no tagline.


def _norm_phrase(value: Any) -> str:
    """Normalised key for matching free-text phrases (~equality).

    Lowercases, collapses internal whitespace and strips surrounding quotes plus
    trailing sentence punctuation so a tagline that differs from a
    ``servicesMentioned`` entry only by case, spacing or a trailing period still
    compares equal. Returns "" for non-strings / empty input.
    """
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split()).strip().casefold()
    return text.strip(" \t\"'“”«».,!?:;–—-")


def _offer_tagline_phrases(brief: dict[str, Any]) -> set[str]:
    """Normalised company offer/tagline phrases an offer card must never echo.

    Collects the hero one-liner (``positioning.oneLiner``) and the hero
    subheadline (the offer tagline). Deliberately excludes the ``_hero_headline``
    company-name fallback so a real service that happens to match a company name
    is never dropped.
    """
    phrases: set[str] = set()
    one_liner = _str(_obj(brief, "positioning").get("oneLiner"))
    for candidate in (one_liner, _hero_subheadline(brief)):
        key = _norm_phrase(candidate)
        if key:
            phrases.add(key)
    return phrases


def _drop_offer_tagline_services(services: list[str], brief: dict[str, Any]) -> list[str]:
    """Drop ``servicesMentioned`` entries that are ~equal to the offer/tagline.

    Honesty-preserving: only removes a service whose normalised text equals a
    company offer/tagline phrase (hero one-liner / subheadline). Real services
    are kept unchanged and nothing is fabricated. A no-op when the brief carries
    no offer/tagline phrase (e.g. a legacy brief without positioning), so that
    path stays byte-identical.
    """
    tagline_phrases = _offer_tagline_phrases(brief)
    if not tagline_phrases:
        return services
    return [service for service in services if _norm_phrase(service) not in tagline_phrases]


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


def derive_story(brief: dict[str, Any]) -> str | None:
    """Compose an honest, branschnära company story from the Site Brief.

    Built purely from the kor-1b positioning blueprint (``oneLiner`` /
    ``differentiator`` / ``localAngle``, falling back to
    ``contentStrategy.heroAngle`` for the lead sentence). Every sentence is a
    grounded angle the brief already states - never a fabricated fact and never
    the raw prompt. Returns None when there is no positioning to ground a story
    (so a legacy brief keeps the dossier/template story unchanged).
    """
    if not _enrichment_enabled(brief):
        return None
    positioning = _obj(brief, "positioning")
    content_strategy = _obj(brief, "contentStrategy")

    # Gap 2 (story-vs-hero repetition): the hero already renders the headline
    # (``oneLiner``/``heroAngle``) and the subheadline (``differentiator`` ->
    # ``audienceNeed`` -> ``localAngle`` -> ``offerStrategy``). The old story
    # led with the same ``oneLiner`` + ``differentiator``, so the /om-oss and
    # home "story" card echoed the hero nearly verbatim. Build the story from
    # the COMPLEMENTARY grounded angles instead - exclude whatever the hero
    # already consumed so the story deepens the page rather than restating it.
    def _key(text: str | None) -> str:
        return (text or "").strip().rstrip(".").casefold()

    hero_used = {_key(_hero_headline(brief)), _key(_hero_subheadline(brief))}
    hero_used.discard("")

    # Only customer-safe positioning angles feed the story. ``offerStrategy``
    # is deliberately excluded: it is an INTERNAL content-strategy instruction
    # ("Lyft tre till fem konkreta tjänster") that must never render as
    # customer copy, even though the hero subheadline may use it as a last
    # resort.
    hero_angle = _str(content_strategy.get("heroAngle"))
    candidates = [
        _str(positioning.get("differentiator")),
        _str(positioning.get("localAngle")),
        _str(positioning.get("audienceNeed")),
        _str(positioning.get("oneLiner")),
        _capitalise(hero_angle) if hero_angle else None,
    ]
    sentences: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        key = _key(candidate)
        if key in hero_used or key in seen:
            continue
        seen.add(key)
        sentences.append(_sentence(candidate))
        if len(sentences) >= 3:
            break

    if sentences:
        return " ".join(sentences)

    # Every grounded angle collapsed into the hero: ground the story on the
    # lead so a thin brief still gets a story instead of None (it may echo the
    # hero, but that is the only honest content available).
    lead = _hero_headline(brief)
    return _sentence(lead) if lead else None


def derive_faq(brief: dict[str, Any]) -> list[dict[str, str]]:
    """Branschrelevanta, grundade ``(question, answer)`` pairs from the brief.

    Three pairs, each grounded in a field the brief already carries:

    1. the concrete services from ``servicesMentioned``;
    2. the conversion intent (request a quote / book / shop / contact) - the
       answer never promises a phone, price or channel the brief did not state;
    3. the positioning differentiator.

    Returns ``[]`` when enrichment is disabled or there is nothing grounded to
    say, so the renderer keeps its honest template FAQ.
    """
    if not _enrichment_enabled(brief):
        return []
    pairs: list[dict[str, str]] = []

    services = _list_str(brief.get("servicesMentioned"))
    if services:
        pairs.append(
            {
                "question": "Vad kan ni hjälpa till med?",
                "answer": f"Vi hjälper dig bland annat med {_join_sv(services)}.",
            }
        )

    conversion = _obj(brief, "conversion")
    action = _str(conversion.get("primaryAction"))
    convo = _FAQ_CONVERSION_SV.get(action or "")
    if convo is None:
        for goal in _list_str(brief.get("conversionGoals")):
            convo = _FAQ_CONVERSION_SV.get(goal)
            if convo is not None:
                break
    if convo is not None:
        pairs.append({"question": convo[0], "answer": convo[1]})

    differentiator = _str(_obj(brief, "positioning").get("differentiator"))
    if differentiator:
        pairs.append(
            {
                "question": "Vad kan jag förvänta mig av er?",
                "answer": _sentence(differentiator),
            }
        )

    return pairs


def _join_sv(items: list[str]) -> str:
    """Join a list as a natural Swedish enumeration ('a, b och c')."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} och {items[-1]}"


def derive_content_blocks(
    brief: dict[str, Any],
    scaffold: dict[str, Any],
    route_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-section copy keyed by ``<routeId>.<sectionId>`` (the kor-2 work order).

    Emits, when the brief grounds them:

    * a hero block (only with an honest headline source);
    * an offer-list block from ``servicesMentioned`` - with honest per-service
      ``summary`` + ``bullets`` for the four baseline industries (kor-1c-copy),
      else title-only so the renderer keeps the dossier's summaries;
    * a company ``story`` block composed from positioning (kor-1c-copy);
    * a branschrelevant ``faq`` block grounded in the brief (kor-1c-copy).

    Nothing the brief did not state becomes copy. Always schema-valid and every
    key validated against the scaffold's sections.json. The story/FAQ/summary
    enrichment only runs when :func:`_enrichment_enabled`, so a legacy brief
    (no positioning) is byte-identical to before kor-1c-copy.
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
    services = _drop_offer_tagline_services(
        _list_str(brief.get("servicesMentioned")), brief
    )
    if offer is not None and services:
        industry = _detect_industry(brief) if _enrichment_enabled(brief) else None
        items = [_offer_item(service, industry) for service in services]
        _dedupe_offer_summaries(items)
        blocks[offer] = items

    story_address = _story_block_address(scaffold, route_plan)
    story = derive_story(brief)
    if story_address is not None and story:
        blocks[story_address] = {"body": story}

    faq_address = _faq_block_address(scaffold)
    faq = derive_faq(brief)
    if faq_address is not None and faq:
        blocks[faq_address] = faq

    return blocks


def _dedupe_offer_summaries(items: list[dict[str, Any]]) -> None:
    """Ensure no two offer cards render an identical summary (gap 3).

    Unknown services in a known industry all fall back to the same generic
    industry summary (e.g. naprapath -> "Behandling anpassad efter dina
    besvär."), so two such services would show identical copy on two cards - a
    clear "fake AI" repetition (inbox msg-0026). When a summary repeats, qualify
    the duplicate with its own service title so each card carries distinct, still
    honest copy (no fabricated claim - only the service's own name is added).
    The first occurrence keeps the clean generic line. Mutates ``items`` in
    place. Known/keyed service summaries are already distinct, so the four
    baselines are unaffected.
    """
    seen: set[str] = set()
    for item in items:
        summary = item.get("summary")
        if not isinstance(summary, str) or not summary:
            continue
        key = summary.strip().casefold()
        if key not in seen:
            seen.add(key)
            continue
        title = _str(item.get("title"))
        if not title:
            continue
        lowered = summary[:1].lower() + summary[1:]
        qualified = f"{title} – {lowered}"
        item["summary"] = qualified
        seen.add(qualified.strip().casefold())


def _offer_item(service: str, industry: str | None) -> dict[str, Any]:
    """One offer-list item: title always, summary + bullets for baselines.

    Outside the four baseline industries (``industry is None``) the item stays
    title-only - the same shape as before kor-1c-copy - so the renderer keeps
    the dossier's own (often operator-authored) service summaries rather than
    overriding them with generic copy.
    """
    item: dict[str, Any] = {"title": _capitalise(service)}
    if industry is not None:
        summary, bullets = _service_summary_and_bullets(service, industry)
        item["summary"] = summary
        if bullets:
            item["bullets"] = bullets
    return item


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
