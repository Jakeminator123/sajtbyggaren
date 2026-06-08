"""briefModel: extract a structured Site Brief from a raw prompt.

Uses OpenAI structured output (response_format=SiteBrief) when OPENAI_API_KEY
is available. Otherwise returns a deterministic mock so dev_generate.py and
tests can run without an API key.

The Site Brief schema is intentionally narrow: only fields that subsequent
phases actually read. Adding new fields requires a naming-dictionary entry.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import has_openai_api_key

logger = logging.getLogger("sajtbyggaren.brief")


SWEDISH_HINTS = {
    "skapa", "för", "hemsida", "sajt", "och", "att", "med", "på",
    "elektriker", "rörmokare", "tandläkare", "restaurang", "i", "av",
    "ett", "en", "kontakt", "tjänster", "om", "oss",
}

# English stop-words used to refuse the Swedish-default fallback when the
# prompt clearly reads as English. The list is intentionally tiny: short
# function words that operators rarely typo into a Swedish prompt plus a
# handful of common website-shaped verbs/nouns ("create", "build",
# "website", "site") that show up in nearly every English brief in this
# domain. Keeping it small avoids fighting the Swedish-default in
# mixed-vocabulary prompts; we rather lean Swedish than mistakenly
# translate a Swedish prompt to English (B62, demo-baseline-fix 1A-hotfix).
#
# B90 (2026-05-26): "a" and "an" removed because they false-positive on
# Swedish company names that contain a single-letter token: "A & O El
# Malmö" tokenises to {"a", "&", "o", "el", "malmö"} and "a" used to
# match here. The å/ä/ö check still catches that case via "malmö", and
# the remaining stop-word set is more than sufficient for the genuine
# English-brief cases.
ENGLISH_HINTS = {
    "the", "and", "or", "but",
    "in", "on", "at", "for", "of", "with", "to", "from",
    "is", "are", "was", "were", "be", "been",
    "create", "build", "make", "need", "want",
    "website", "site", "page", "store", "shop",
    "my", "our", "your",
}

# å/ä/ö (case-insensitive) are strong Swedish-language signals: even
# English prompts that mention a Swedish city ("Malmö", "Göteborg") can
# match here, but the cascade ordering puts ENGLISH_HINTS BEFORE this
# check so "electrician website in Malmö" still resolves to "en".
SWEDISH_CHARS = frozenset("åäöÅÄÖ")


def detect_language(prompt: str) -> str:
    """Return the prompt language as an ISO 639-1 code (sv/en).

    Cascading heuristic so short Swedish prompts ("frisör Göteborg",
    "naprapatklinik Stockholm") no longer slip through as English just
    because they lack any of the SWEDISH_HINTS stop-words. The cascade:

    1. Swedish stop-word match -> "sv".
    2. English stop-word match (and no Swedish stop-word match above)
       -> "en". Refuses the Swedish-default for clearly English prompts
       even when they mention Swedish characters in a city name.
    3. Any token contains å/ä/ö -> "sv". Catches "frisör Göteborg".
    4. Otherwise -> "sv". The operator population is ~95% Swedish-
       speaking, so an unknown short prompt is far more likely to be
       Swedish than English ("naprapatklinik Stockholm").

    The previous heuristic returned "en" by default, which generated
    fully English customer copy for two of four Verifierings-Scout
    cases (B62, demo-baseline-fix 1A-hotfix).
    """
    tokens = {t.lower().strip(",.!?:;") for t in prompt.split() if t}
    if tokens & SWEDISH_HINTS:
        return "sv"
    if tokens & ENGLISH_HINTS:
        return "en"
    if any(ch in SWEDISH_CHARS for ch in prompt):
        return "sv"
    return "sv"


# --- Blueprint sub-models (kor-1b) ------------------------------------------
#
# Optional blueprint fields added to Site Brief in the kor-1a schema skeleton
# (docs/heavy-llm-flow/01 §2). Shapes mirror governance/schemas/site-brief.
# schema.json exactly; field names are the snake_case form of the camelCase
# JSON keys (one_liner -> oneLiner) and are mapped back to camelCase in
# site_brief_to_artifact. Every field is optional so a brief without a
# blueprint stays valid (the additive contract from kor-1a).


class BusinessFacts(BaseModel):
    """Confirmed facts vs deliberate unknowns - the honesty engine.

    An item in ``unknowns`` must never be rendered as invented copy: it binds
    briefModel's understanding to the deterministic contact/trust rules
    (contact_placeholders, B158/B159). Anything the prompt does not state goes
    in ``unknowns``, never into a fabricated fact or customer-facing claim.
    """

    facts: list[str] = Field(
        default_factory=list,
        description=(
            "Facts confirmed from the prompt/wizard (e.g. 'verksam i Malmö'). "
            "Only include what the prompt actually states; never invent."
        ),
    )
    unknowns: list[str] = Field(
        default_factory=list,
        description=(
            "Slots the model does NOT know (e.g. 'telefonnummer', "
            "'certifieringar'). Anything not stated in the prompt goes here so "
            "the renderer never fabricates it as copy."
        ),
    )


class Positioning(BaseModel):
    """How the site should position the business: angle and tone, not facts."""

    one_liner: str | None = Field(
        default=None, description="One-sentence positioning statement."
    )
    differentiator: str | None = Field(
        default=None, description="What sets the business apart, in plain language."
    )
    audience_need: str | None = Field(
        default=None, description="The core need the target audience has."
    )
    local_angle: str | None = Field(
        default=None, description="Local/geographic angle when relevant."
    )
    tone: str | None = Field(
        default=None,
        description=(
            "Free-form tone phrase for positioning copy, distinct from the "
            "top-level tone[] tone words."
        ),
    )
    avoid: list[str] = Field(
        default_factory=list,
        description=(
            "Things the copy must avoid (e.g. 'påhittade certifieringar', "
            "'generiska superlativ')."
        ),
    )


class ContentStrategy(BaseModel):
    """High-level content strategy for the site."""

    hero_angle: str | None = Field(
        default=None, description="Angle the hero section should take."
    )
    trust_strategy: str | None = Field(
        default=None,
        description="How trust is built honestly, without fake claims.",
    )
    offer_strategy: str | None = Field(
        default=None, description="How services/offers are surfaced."
    )
    avoid_generic_claims: bool | None = Field(
        default=None,
        description="When true, generic superlatives/claims should be avoided.",
    )


class Conversion(BaseModel):
    """Conversion intent that binds to the deterministic contact/CTA rules.

    Additive to the existing top-level conversion_goals[] field - this is the
    richer blueprint conversion object, never a replacement for conversion_goals.
    """

    primary_action: str | None = Field(
        default=None,
        description=(
            "Primary conversion action slug (e.g. 'request_quote', 'book', "
            "'call', 'purchase'). Kebab/snake English slug, not customer copy."
        ),
    )
    primary_cta: str | None = Field(
        default=None,
        description="Label for the primary call to action (customer copy, prompt language).",
    )
    secondary_cta: str | None = Field(
        default=None,
        description="Label for the secondary call to action (customer copy, prompt language).",
    )
    contact_priority: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered contact channel preference, slug-shaped "
            "(e.g. 'phone_if_real', 'form', 'email_if_real')."
        ),
    )
    cta_rules: list[str] = Field(
        default_factory=list,
        description=(
            "Honesty/availability rules for CTAs (e.g. 'do not show phone if "
            "missing', 'no booking unless booking exists')."
        ),
    )


class SiteBrief(BaseModel):
    """Structured Site Brief produced by Phase 1 Understand.

    The schema covers what Phase 2 (Plan) and Phase 3 (Build) need to reach
    9/10 on the page-quality-traits scorecard. Conversion goals and listed
    services are crucial for `conversion_clarity` and `content_specificity`.
    """

    language: str = Field(description="ISO 639-1 code, e.g. sv or en.")
    business_type: str | None = Field(
        default=None,
        description="A short slug describing the business (e.g. 'electrician', 'dental-clinic').",
    )
    company_name: str | None = Field(
        default=None,
        description="Company name if the prompt explicitly mentions one. Null otherwise.",
    )
    target_audience: list[str] = Field(
        default_factory=list,
        description="Who the site is meant to convert. 0-5 items.",
    )
    page_count: int | None = Field(
        default=None,
        description="Number of pages the site should have. Omit if unclear.",
    )
    tone: list[str] = Field(
        default_factory=list,
        description="Tone words like 'trustworthy', 'premium', 'local'. 0-5 items.",
    )
    requested_capabilities: list[str] = Field(
        default_factory=list,
        description="Slugs of capabilities the user explicitly asked for (e.g. 'contact-form', 'reviews').",
    )
    location_hint: str | None = Field(
        default=None,
        description="City or region if mentioned in the prompt.",
    )
    contact_phone: str | None = Field(
        default=None,
        description="Phone number if explicitly mentioned in the prompt. Null otherwise.",
    )
    contact_email: str | None = Field(
        default=None,
        description="Email address if explicitly mentioned in the prompt. Null otherwise.",
    )
    contact_address: str | None = Field(
        default=None,
        description="Street/postal address if explicitly mentioned in the prompt. Null otherwise.",
    )
    contact_opening_hours: str | None = Field(
        default=None,
        description=(
            "Opening hours ONLY when the prompt explicitly states them "
            "(e.g. 'öppet tisdag–söndag 07–16', 'mån-fre 9-17'). Copy them "
            "as a short natural-language string in the prompt's original "
            "language. Null otherwise. Never invent or guess business hours."
        ),
    )
    conversion_goals: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete actions the site should drive: 'call', 'quote-request', "
            "'booking', 'newsletter-signup', 'purchase'. 0-3 items."
        ),
    )
    services_mentioned: list[str] = Field(
        default_factory=list,
        description=(
            "Specific services/products the user mentioned, as short "
            "natural-language phrases IN THE PROMPT'S ORIGINAL LANGUAGE "
            "(e.g. on Swedish prompts: 'akut elservice', 'paneldragning', "
            "'färska ägg direkt från gården'; on English prompts: "
            "'emergency electrical', 'panel installation'). These drive "
            "customer-facing copy on the generated services grid; "
            "kebab-case English slugs would surface as unreadable labels. "
            "The Project Input mapping ASCII-folds the phrase to produce "
            "the service slug separately from the rendered label."
        ),
    )
    content_depth: str | None = Field(
        default=None,
        description="One of: 'shallow', 'medium', 'rich'. How detailed the copy should feel.",
    )
    raw_prompt: str = Field(description="The original prompt as received.")
    notes_for_planner: str | None = Field(
        default=None,
        description="One-line summary that Phase 2 Plan can use as orientation.",
    )
    business_facts: BusinessFacts | None = Field(
        default=None,
        description=(
            "Blueprint field (kor-1b): confirmed facts vs deliberate unknowns. "
            "Fill `unknowns` with anything the prompt does not state (phone, "
            "certifications, prices, opening hours) so nothing is invented."
        ),
    )
    positioning: Positioning | None = Field(
        default=None,
        description=(
            "Blueprint field (kor-1b): how to position the business - angle and "
            "tone, never fabricated facts."
        ),
    )
    content_strategy: ContentStrategy | None = Field(
        default=None,
        description=(
            "Blueprint field (kor-1b): high-level content strategy (hero angle, "
            "honest trust, how offers are surfaced)."
        ),
    )
    conversion: Conversion | None = Field(
        default=None,
        description=(
            "Blueprint field (kor-1b): conversion intent (primary action, CTA "
            "labels, honest CTA rules). Additive to conversion_goals[], not a "
            "replacement."
        ),
    )


_SYSTEM_INSTRUCTIONS = (
    "You are the briefModel for Sajtbyggaren. You receive a raw user prompt about a "
    "website to build. Extract a structured Site Brief. Be conservative: only fill "
    "fields you have evidence for. Use ISO 639-1 language codes. Do not invent "
    "businessType if the prompt is ambiguous - leave it null. Do not add capabilities "
    "the user did not ask for. Slug-shaped fields (business_type, requested_capabilities, "
    "conversion_goals) are kebab-case English even if the prompt is in another language. "
    "Extract company_name only when the prompt names a real company or brand. "
    "Extract contact_phone, contact_email and contact_address only when the prompt "
    "explicitly includes those details; never invent contact data. "
    "Extract contact_opening_hours ONLY when the prompt explicitly states opening "
    "hours (e.g. 'öppet tisdag–söndag 07–16'); copy them as a short natural-language "
    "string in the prompt's original language. Leave it null otherwise and never "
    "invent or guess business hours. "
    "The services_mentioned field is the EXCEPTION: return short natural-language phrases "
    "in the prompt's original language so the generated website renders readable labels. "
    "Also fill the blueprint fields - this is where the site gets its angle and soul, but "
    "honesty is non-negotiable. "
    "business_facts: put ONLY facts the prompt actually states into facts; put everything "
    "the prompt does NOT state (phone number, certifications, prices, opening hours, "
    "reviews, team size) into unknowns. An item in unknowns must NEVER be turned into "
    "customer copy or a fabricated claim. "
    "positioning (one_liner, differentiator, audience_need, local_angle, tone, avoid): an "
    "angle and tone for the copy, derived from the apparent business and place - never an "
    "invented fact. Use avoid to list pitfalls the copy must steer clear of (e.g. invented "
    "certifications, generic superlatives). "
    "content_strategy: heroAngle, an honest trust_strategy (build credibility without fake "
    "claims), offer_strategy, and set avoid_generic_claims true. "
    "conversion: primary_action is a kebab/snake slug ('request_quote', 'book', 'call', "
    "'purchase'); primary_cta and secondary_cta are short labels in the prompt's language; "
    "contact_priority is an ordered list of slugs ('phone_if_real', 'form', "
    "'email_if_real'); cta_rules are honesty rules such as 'do not show phone if missing' "
    "and 'no booking unless booking exists'. conversion is additive to conversion_goals; "
    "fill both. Never invent contact details, certifications, reviews or prices anywhere."
)


# --- Mock blueprint (kor-1b) ------------------------------------------------
#
# When no API key is set the mock still fills the blueprint so the four
# baseline branches render a site "with soul" offline, while staying honest:
# positioning is an ANGLE (never a fabricated fact) and business_facts.unknowns
# carries whatever the prompt does not state (phone, certifications, prices) so
# the renderer/verifier never invent it. Industry detection is a small keyword
# match; the rich Swedish profiles only apply to Swedish prompts (the operator
# population is ~95% Swedish) - other languages get a neutral default so the
# mock never emits mismatched-language copy. Everything here is a pure function
# of (prompt, language), so the fallback stays byte-deterministic
# (test_builder_fallback_is_deterministic_for_examples).


@dataclass(frozen=True)
class _MockProfile:
    """Honest, industry-reasonable blueprint defaults for the mock fallback.

    one_liner/local_angle may contain a ``{loc}`` placeholder filled with the
    detected location (or removed when none). Everything is an angle/tone, not a
    fabricated fact; unknowns carries what the prompt does not state.
    """

    one_liner: str
    differentiator: str
    audience_need: str
    local_angle: str
    pos_tone: str
    avoid: tuple[str, ...]
    hero_angle: str
    trust_strategy: str
    offer_strategy: str
    primary_action: str
    primary_cta: str
    secondary_cta: str
    contact_priority: tuple[str, ...]
    cta_rules: tuple[str, ...]
    unknowns: tuple[str, ...]
    fact_label: str | None = None


# Most-specific first; first profile with any matching keyword (lowercased
# substring of the prompt) wins.
_INDUSTRY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("electrician", ("elektriker", "elinstallation", "elarbete", "electrician")),
    ("hair-salon", ("frisör", "frisor", "salong", "barber", "hairdress")),
    ("naprapath", ("naprapat",)),
    ("ceramics", ("keramik", "lergods", "drej", "pottery", "ceramic")),
)

_CITY_HINTS: tuple[str, ...] = (
    "Malmö", "Göteborg", "Stockholm", "Uppsala", "Lund", "Helsingborg",
    "Örebro", "Linköping", "Västerås", "Norrköping", "Umeå", "Gävle",
)

_SV_PROFILES: dict[str, _MockProfile] = {
    "electrician": _MockProfile(
        fact_label="elektriker",
        one_liner="Trygg elektriker{loc} när elen måste bli rätt.",
        differentiator="lokal och rak kommunikation utan krångliga offerter",
        audience_need="få eljobbet löst säkert och i tid",
        local_angle="snabbt på plats{loc}",
        pos_tone="trygg, kunnig, rak",
        avoid=("påhittade certifieringar", "överdrivet teknisk jargong", "tomma superlativ"),
        hero_angle="trygg lokal elektriker som svarar snabbt",
        trust_strategy="ärlig trovärdighet utan påhittade claims",
        offer_strategy="lyft tre till fem konkreta tjänster",
        primary_action="request_quote",
        primary_cta="Be om offert",
        secondary_cta="Se våra tjänster",
        contact_priority=("phone_if_real", "form", "email_if_real"),
        cta_rules=("visa inte telefon om telefonnummer saknas", "använd inte bokning om bokning saknas"),
        unknowns=("telefonnummer", "certifieringar", "antal anställda"),
    ),
    "hair-salon": _MockProfile(
        fact_label="frisörsalong",
        one_liner="Personlig frisörsalong{loc} för en look som känns som du.",
        differentiator="tid att lyssna och ett varmt bemötande",
        audience_need="en frisör som förstår vad kunden vill ha",
        local_angle="lätt att boka tid{loc}",
        pos_tone="varm, personlig, stilren",
        avoid=("stressig säljton", "påhittade priser", "tomma superlativ"),
        hero_angle="varm personlig salong med enkel bokning",
        trust_strategy="äkta känsla genom ton och bilder, inga påhittade omdömen",
        offer_strategy="lyft de vanligaste behandlingarna tydligt",
        primary_action="book",
        primary_cta="Boka tid",
        secondary_cta="Se behandlingar",
        contact_priority=("form", "phone_if_real"),
        cta_rules=("använd inte bokning om bokning saknas", "visa inte priser om priser saknas"),
        unknowns=("telefonnummer", "prislista", "öppettider"),
    ),
    "naprapath": _MockProfile(
        fact_label="naprapat",
        one_liner="Naprapat{loc} som hjälper dig tillbaka till rörelse.",
        differentiator="tydlig behandlingsplan och uppföljning",
        audience_need="lindra besvär och förstå orsaken",
        local_angle="lätt att nå{loc}",
        pos_tone="lugn, professionell, omtänksam",
        avoid=("ohållbara medicinska löften", "påhittade certifieringar", "skrämselton"),
        hero_angle="lugnt och kunnigt stöd tillbaka till rörelse",
        trust_strategy="trovärdighet genom tydlighet, inga ohållbara löften",
        offer_strategy="förklara behandlingar och vad som ingår",
        primary_action="book",
        primary_cta="Boka behandling",
        secondary_cta="Läs om behandlingar",
        contact_priority=("form", "phone_if_real", "email_if_real"),
        cta_rules=("använd inte bokning om bokning saknas", "lova inga medicinska resultat"),
        unknowns=("telefonnummer", "legitimation", "öppettider"),
    ),
    "ceramics": _MockProfile(
        fact_label="handgjord keramik",
        one_liner="Handgjord keramik med själ, gjord för vardagsbruk.",
        differentiator="varje pjäs är unik och tillverkad i liten skala",
        audience_need="vacker keramik som tål att användas",
        local_angle="tillverkad i en liten verkstad{loc}",
        pos_tone="jordnära, hantverksstolt, stillsam",
        avoid=("massproducerad känsla", "påhittade recensioner", "uppblåsta löften"),
        hero_angle="hantverk och känsla framför snabb försäljning",
        trust_strategy="förtroende genom berättelse och bilder, inga påhittade omdömen",
        offer_strategy="lyft ett urval produkter och hänvisa till hela sortimentet",
        primary_action="purchase",
        primary_cta="Handla nu",
        secondary_cta="Läs om verkstaden",
        contact_priority=("form", "email_if_real"),
        cta_rules=("lova inga leveranstider om de inte är kända", "visa inte lagersaldo om det saknas"),
        unknowns=("telefonnummer", "leveranstider", "fraktpriser"),
    ),
}

_SV_DEFAULT_PROFILE = _MockProfile(
    one_liner="Tydlig och trovärdig hemsida{loc} för verksamheten.",
    differentiator="ärlig och konkret presentation utan tomma löften",
    audience_need="snabbt förstå vad företaget erbjuder",
    local_angle="lokalt förankrad verksamhet{loc}",
    pos_tone="trovärdig, tydlig, professionell",
    avoid=("påhittade certifieringar", "påhittade omdömen", "generiska superlativ"),
    hero_angle="tydligt erbjudande och trovärdig ton",
    trust_strategy="ärlig trovärdighet utan påhittade claims",
    offer_strategy="lyft de viktigaste tjänsterna konkret",
    primary_action="contact",
    primary_cta="Kontakta oss",
    secondary_cta="Läs mer",
    contact_priority=("form", "phone_if_real", "email_if_real"),
    cta_rules=("visa inte telefon om telefonnummer saknas", "lova inget som inte kan hållas"),
    unknowns=("telefonnummer", "e-postadress", "öppettider"),
)

_EN_DEFAULT_PROFILE = _MockProfile(
    one_liner="A clear, trustworthy website{loc} for the business.",
    differentiator="honest, concrete presentation without empty promises",
    audience_need="quickly understand what the business offers",
    local_angle="a locally grounded business{loc}",
    pos_tone="trustworthy, clear, professional",
    avoid=("invented certifications", "invented reviews", "generic superlatives"),
    hero_angle="a clear offer in a trustworthy tone",
    trust_strategy="honest credibility without fake claims",
    offer_strategy="surface the most important services concretely",
    primary_action="contact",
    primary_cta="Contact us",
    secondary_cta="Learn more",
    contact_priority=("form", "phone_if_real", "email_if_real"),
    cta_rules=("do not show phone if missing", "do not promise anything that cannot be kept"),
    unknowns=("phone number", "email address", "opening hours"),
)


def _detect_location(prompt: str) -> str | None:
    """Return a known Swedish city mentioned in the prompt, else None."""
    low = prompt.lower()
    for city in _CITY_HINTS:
        if city.lower() in low:
            return city
    return None


def _detect_industry(prompt: str) -> str | None:
    """Return a baseline industry key from prompt keywords, else None."""
    low = prompt.lower()
    for key, keywords in _INDUSTRY_KEYWORDS:
        if any(keyword in low for keyword in keywords):
            return key
    return None


def _loc_phrase(location: str | None, language: str) -> str:
    if not location:
        return ""
    preposition = "i" if language == "sv" else "in"
    return f" {preposition} {location}"


def _build_mock_blueprint(
    prompt: str, language: str
) -> tuple[BusinessFacts, Positioning, ContentStrategy, Conversion]:
    """Honest, deterministic blueprint for the mock fallback.

    Positioning is an angle derived from the apparent industry/place; it never
    asserts a fact the prompt did not state. unknowns carries the missing
    contact/credentials so they are never rendered as invented copy.
    """
    location = _detect_location(prompt)
    if language == "sv":
        industry = _detect_industry(prompt)
        profile = _SV_PROFILES.get(industry or "", _SV_DEFAULT_PROFILE)
    else:
        profile = _EN_DEFAULT_PROFILE

    loc = _loc_phrase(location, language)

    facts: list[str] = []
    if profile.fact_label:
        facts.append(profile.fact_label)
    if location:
        facts.append(
            f"verksam i {location}" if language == "sv" else f"operates in {location}"
        )

    business_facts = BusinessFacts(facts=facts, unknowns=list(profile.unknowns))
    positioning = Positioning(
        one_liner=profile.one_liner.format(loc=loc),
        differentiator=profile.differentiator,
        audience_need=profile.audience_need,
        local_angle=profile.local_angle.format(loc=loc),
        tone=profile.pos_tone,
        avoid=list(profile.avoid),
    )
    content_strategy = ContentStrategy(
        hero_angle=profile.hero_angle,
        trust_strategy=profile.trust_strategy,
        offer_strategy=profile.offer_strategy,
        avoid_generic_claims=True,
    )
    conversion = Conversion(
        primary_action=profile.primary_action,
        primary_cta=profile.primary_cta,
        secondary_cta=profile.secondary_cta,
        contact_priority=list(profile.contact_priority),
        cta_rules=list(profile.cta_rules),
    )
    return business_facts, positioning, content_strategy, conversion


def _mock_brief(prompt: str, language_hint: str | None) -> SiteBrief:
    """Deterministic fallback when no API key is available.

    Still fills the blueprint fields (kor-1b) with honest, industry-reasonable
    values; the existing scalar fields keep their conservative mock defaults so
    the briefSource=mock-no-key contract is unchanged.
    """
    language = language_hint or detect_language(prompt)
    business_facts, positioning, content_strategy, conversion = _build_mock_blueprint(
        prompt, language
    )
    return SiteBrief(
        language=language,
        business_type=None,
        target_audience=[],
        page_count=None,
        tone=[],
        requested_capabilities=[],
        location_hint=None,
        conversion_goals=[],
        services_mentioned=[],
        content_depth=None,
        raw_prompt=prompt,
        notes_for_planner=(
            "Mock brief - OPENAI_API_KEY saknades, ingen riktig extraktion utförd."
        ),
        business_facts=business_facts,
        positioning=positioning,
        content_strategy=content_strategy,
        conversion=conversion,
    )


def _real_brief(prompt: str, model: str, language_hint: str | None) -> SiteBrief:
    """Call OpenAI with structured output. Requires OPENAI_API_KEY."""
    from openai import OpenAI

    client = OpenAI()

    user_message = prompt
    if language_hint:
        user_message = f"[language hint: {language_hint}]\n\n{prompt}"

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_message},
        ],
        text_format=SiteBrief,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("briefModel returned no structured output")
    if not parsed.raw_prompt:
        parsed.raw_prompt = prompt
    return parsed


class BriefResult(BaseModel):
    """Resultatet av extract_site_brief: brief plus källinformation."""

    brief: SiteBrief
    source: str  # "real" | "mock-no-key" | "mock-llm-error"
    error: str | None = None


def extract_site_brief(
    prompt: str,
    *,
    model: str = "gpt-5.4",
    language_hint: str | None = None,
) -> BriefResult:
    """Phase 1 Understand entry point.

    Returns a BriefResult that always contains a valid SiteBrief plus a
    transparent `source` field so callers (and artefakter) inte ljuger om
    huruvida riktig LLM användes.
    """
    if not has_openai_api_key():
        return BriefResult(
            brief=_mock_brief(prompt, language_hint),
            source="mock-no-key",
        )

    try:
        return BriefResult(
            brief=_real_brief(prompt, model=model, language_hint=language_hint),
            source="real",
        )
    except Exception as exc:  # noqa: BLE001
        # Log to stderr so operators see this in terminal/CI output.
        message = f"briefModel error: {type(exc).__name__}: {exc}"
        logger.warning(message)
        sys.stderr.write(f"[briefModel] {message}\n")
        sys.stderr.flush()
        mock = _mock_brief(prompt, language_hint)
        mock.notes_for_planner = f"Mock brief efter LLM-fel: {type(exc).__name__}: {exc}"
        return BriefResult(
            brief=mock,
            source="mock-llm-error",
            error=f"{type(exc).__name__}: {exc}",
        )


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    """Drop None entries so optional non-nullable schema leaves are omitted.

    site-brief.schema.json types the blueprint leaf strings/bool as
    non-nullable, so a missing value must be omitted, never serialised as null.
    """
    return {key: value for key, value in values.items() if value is not None}


def _attach_blueprint_fields(artifact: dict[str, Any], brief: SiteBrief) -> None:
    """Emit the optional blueprint fields (kor-1b) in camelCase, schema-valid.

    Each blueprint object is optional, so a None object is omitted entirely and
    a None leaf is dropped (never null). Lists are always valid arrays. Purely
    additive: it never touches the existing conversionGoals field.
    """
    if brief.business_facts is not None:
        artifact["businessFacts"] = {
            "facts": list(brief.business_facts.facts),
            "unknowns": list(brief.business_facts.unknowns),
        }
    if brief.positioning is not None:
        artifact["positioning"] = _drop_none(
            {
                "oneLiner": brief.positioning.one_liner,
                "differentiator": brief.positioning.differentiator,
                "audienceNeed": brief.positioning.audience_need,
                "localAngle": brief.positioning.local_angle,
                "tone": brief.positioning.tone,
                "avoid": list(brief.positioning.avoid),
            }
        )
    if brief.content_strategy is not None:
        artifact["contentStrategy"] = _drop_none(
            {
                "heroAngle": brief.content_strategy.hero_angle,
                "trustStrategy": brief.content_strategy.trust_strategy,
                "offerStrategy": brief.content_strategy.offer_strategy,
                "avoidGenericClaims": brief.content_strategy.avoid_generic_claims,
            }
        )
    if brief.conversion is not None:
        artifact["conversion"] = _drop_none(
            {
                "primaryAction": brief.conversion.primary_action,
                "primaryCta": brief.conversion.primary_cta,
                "secondaryCta": brief.conversion.secondary_cta,
                "contactPriority": list(brief.conversion.contact_priority),
                "ctaRules": list(brief.conversion.cta_rules),
            }
        )


def site_brief_to_artifact(
    result: BriefResult,
    *,
    run_id: str,
    model: str,
) -> dict[str, Any]:
    """Serialise a BriefResult into the canonical Site Brief artefakt.

    Shape locked by ``governance/schemas/site-brief.schema.json`` (ADR 0013,
    blueprint fields from kor-1a). Reads source from the BriefResult so
    modelUsed/briefSource reflects the actual code path (real, mock-no-key,
    mock-llm-error). Never claims real when fallback occurred.
    """
    brief = result.brief
    is_real = result.source == "real"
    artifact: dict[str, Any] = {
        "runId": run_id,
        "language": brief.language,
        "rawPrompt": brief.raw_prompt,
        "businessTypeGuess": brief.business_type,
        "companyName": brief.company_name,
        "pageCount": brief.page_count,
        "tone": brief.tone,
        "targetAudience": brief.target_audience,
        "requestedCapabilities": brief.requested_capabilities,
        "locationHint": brief.location_hint,
        "contactPhone": brief.contact_phone,
        "contactEmail": brief.contact_email,
        "contactAddress": brief.contact_address,
        "contactOpeningHours": brief.contact_opening_hours,
        "conversionGoals": brief.conversion_goals,
        "servicesMentioned": brief.services_mentioned,
        "contentDepth": brief.content_depth,
        "notesForPlanner": brief.notes_for_planner,
        "sourceModelRole": "briefModel",
        "modelUsed": model if is_real else "mock",
        "briefSource": result.source,
        "briefError": result.error,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _attach_blueprint_fields(artifact, brief)
    return artifact


# --- copyDirective extraction (ADR 0034 path A) -----------------------------
#
# Follow-up copy edits ("byt namnet i headern till X", "lägg in TEST-JAKOB i
# hero") go through the dedicated copyDirectiveModel role (llm-models.v1.json
# v5) - a separate role from briefModel so the two purposes stay distinct. The
# model only proposes a structured target+operation+payload triple; the caller
# (scripts/prompt_to_project_input.py) re-validates every payload through the
# public-copy guards before anything is applied, so a hallucinated or
# instruction-shaped payload can never become customer copy. Targets grow in
# slices: company-name + tagline (nivå 1), about-text -> company.story (slice
# 2a), services -> services[].summary (slice 2c, via targetRef); about-text and
# services are replace-only. This module hosts the call (it already owns the
# OpenAI structured-output plumbing); the role is what governance tracks, not
# the file location.


class CopyDirectiveCandidate(BaseModel):
    """One structured copy edit proposed by the model from a follow-up prompt."""

    target: Literal["company-name", "tagline", "about-text", "services"] = Field(
        description=(
            "Which field to change. 'company-name' = the business name shown "
            "in the nav header and hero H1. 'tagline' = the hero subheading. "
            "'about-text' = the company story / 'om oss' about copy. "
            "'services' = the summary of ONE specific service (set targetRef)."
        )
    )
    operation: Literal["replace-text", "include-token"] = Field(
        description=(
            "'replace-text' = set the field to payload. 'include-token' = add "
            "the payload to the existing field (for 'include X in the hero'). "
            "'about-text' and 'services' only support 'replace-text'."
        )
    )
    targetRef: str | None = Field(
        default=None,
        description=(
            "Only for target 'services': the id or label of the existing "
            "service whose summary to replace, exactly as it appears in the "
            "provided services list. Leave null for other targets. Never "
            "invent a service that is not in the list."
        ),
    )
    payload: str = Field(
        description=(
            "ONLY the resulting copy: the new name, new tagline, new "
            "about/story copy, or token to include. Never the operator's "
            "instruction phrasing or any verb like 'change'/'rename'. Keep it "
            "tight - a name or one line for name/tagline, at most a short "
            "paragraph for about-text."
        )
    )


class CopyDirectiveExtraction(BaseModel):
    """Structured output: zero or more copy directives, empty when unclear."""

    directives: list[CopyDirectiveCandidate] = Field(default_factory=list)


_COPY_DIRECTIVE_SYSTEM = (
    "You are the follow-up copy interpreter for Sajtbyggaren. The operator "
    "already has a generated website and typed a short follow-up asking for a "
    "change. Decide whether the follow-up asks to change the company NAME "
    "(target 'company-name'), the hero TAGLINE/subheading (target 'tagline'), "
    "the ABOUT / 'om oss' company story (target 'about-text'), or the SUMMARY "
    "of one specific SERVICE (target 'services'). Emit at most one directive "
    "per target (one per service for 'services'). payload must contain ONLY "
    "the resulting customer-facing copy - the new name, tagline, about copy, "
    "service summary, or the exact token to include - never the operator's "
    "instruction wording and never a verb such as 'change', 'rename', 'byt' or "
    "'ändra'. 'about-text' and 'services' only support 'replace-text' and the "
    "operator must have given the actual new copy; if they only described a "
    "vibe ('make it more personal') without providing the text, return an "
    "empty list. For 'services' set targetRef to the id or label of an "
    "existing service from the provided list - never invent or add a new "
    "service. If the follow-up is about anything else (tone, colours, layout, "
    "adding pages, adding new services) or is unclear, return an empty "
    "directives list. Do not invent content the operator did not ask for."
)


# Planner mandate (ADR 0034 väg A nivå 3a): the planner reads the current
# editable site-state and MAY GENERATE new copy for about-text/services when
# the operator asks to rewrite/improve them without supplying literal text.
# It still never echoes the raw instruction, never invents facts, and
# company-name/tagline stay extraction-only. Output is re-validated through the
# same public-copy guards and applied to structured fields (never .generated/).
_COPY_DIRECTIVE_PLAN_SYSTEM = (
    "You are the follow-up edit planner for Sajtbyggaren. The operator already "
    "has a generated website (its current editable fields are provided) and "
    "typed a short follow-up asking to rewrite or improve some copy. Produce an "
    "edit plan as a list of directives. You MAY write new customer-facing copy "
    "for target 'about-text' (the company story / 'om oss') and target "
    "'services' (a specific service summary, set targetRef to an existing "
    "service id or label from the list). Base the rewrite on the CURRENT copy "
    "shown - keep the real meaning, improve the wording per the operator's "
    "intent (e.g. 'more personal'). Hard rules: payload contains ONLY the "
    "finished copy, never the operator's instruction wording or a verb like "
    "'rewrite'/'skriv om'; never invent facts (founding years, dates, names, "
    "numbers, places) that are not in the current copy or the follow-up; never "
    "rewrite the company NAME or the TAGLINE (return nothing for those); for "
    "'services' you must name an existing service via targetRef - if the "
    "operator names a service that is not in the list, return an empty list. "
    "If the target is unclear or the request is not a copy rewrite, return an "
    "empty directives list."
)


def _build_copy_directive_context(
    *,
    company_name: str,
    tagline: str,
    story: str,
    services: list[dict[str, object]] | None,
    follow_up_prompt: str,
    language: str,
) -> str:
    """Compact, read-only site-state context shared by extract + plan paths."""
    services_block = ""
    if services:
        lines = [
            f"- id={svc.get('id')!r} label={svc.get('label')!r} "
            f"summary={svc.get('summary')!r}"
            for svc in services
            if isinstance(svc, dict)
        ]
        if lines:
            services_block = (
                "Current services (targetRef must match an id or label here):\n"
                + "\n".join(lines)
                + "\n"
            )
    return (
        f"Language: {language}\n"
        f"Current company name: {company_name}\n"
        f"Current hero tagline: {tagline}\n"
        f"Current about/story copy: {story}\n"
        f"{services_block}\n"
        f"Operator follow-up: {follow_up_prompt}"
    )


def _run_copy_directive_model(
    *, system: str, context: str, model: str
) -> list[dict[str, str]]:
    """Shared OpenAI structured-output call for extract + plan paths.

    Returns ``[]`` when no API key is configured or on any error - follow-up
    generation must never fail because this optional understanding step did.
    The caller re-validates every payload, so this is not the security
    boundary.
    """
    if not has_openai_api_key():
        return []
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
            text_format=CopyDirectiveExtraction,
        )
        parsed = response.output_parsed
    except Exception as exc:  # noqa: BLE001
        message = f"copyDirective model error: {type(exc).__name__}: {exc}"
        logger.warning(message)
        sys.stderr.write(f"[copyDirective] {message}\n")
        sys.stderr.flush()
        return []
    if parsed is None:
        return []
    results: list[dict[str, str]] = []
    for directive in parsed.directives:
        item: dict[str, str] = {
            "target": directive.target,
            "operation": directive.operation,
            "payload": directive.payload,
            "source": "llm",
        }
        # Only carry targetRef when the model set it (services); a stray None on
        # other targets would fail the strict copyDirectives schema downstream.
        if directive.targetRef:
            item["targetRef"] = directive.targetRef
        results.append(item)
    return results


def extract_copy_directives_llm(
    follow_up_prompt: str,
    *,
    company_name: str,
    tagline: str,
    story: str = "",
    services: list[dict[str, object]] | None = None,
    language: str,
    model: str,
) -> list[dict[str, str]]:
    """Best-effort LLM extraction of explicit copy directives from a follow-up.

    Extraction-only: the model pulls a value the operator already supplied. It
    is told NOT to invent content. Used when the deterministic rules miss but
    the follow-up still carries an explicit copy edit.
    """
    context = _build_copy_directive_context(
        company_name=company_name,
        tagline=tagline,
        story=story,
        services=services,
        follow_up_prompt=follow_up_prompt,
        language=language,
    )
    return _run_copy_directive_model(
        system=_COPY_DIRECTIVE_SYSTEM, context=context, model=model
    )


def plan_copy_directives_llm(
    follow_up_prompt: str,
    *,
    company_name: str,
    tagline: str,
    story: str = "",
    services: list[dict[str, object]] | None = None,
    language: str,
    model: str,
) -> list[dict[str, str]]:
    """Planner path (ADR 0034 väg A nivå 3a): may GENERATE new about/service copy.

    Reads the current site-state and produces an edit plan (list of copy
    directives) for a rewrite/improve request that lacks an explicit value.
    Generation is limited to about-text + services by the system prompt; the
    caller additionally re-validates every payload and enforces scope.
    """
    context = _build_copy_directive_context(
        company_name=company_name,
        tagline=tagline,
        story=story,
        services=services,
        follow_up_prompt=follow_up_prompt,
        language=language,
    )
    return _run_copy_directive_model(
        system=_COPY_DIRECTIVE_PLAN_SYSTEM, context=context, model=model
    )


# ---------------------------------------------------------------------------
# styleDirectiveModel: free/compound style follow-up -> structured theme mutation
# ---------------------------------------------------------------------------
#
# The stylist role (llm-models.v1.json v9) interprets a free or compound style
# follow-up ("gör den i höstfärger", "samma känsla som en solnedgång") into a
# structured theme mutation: a primary brand colour hex, an optional accent hex
# and an optional tone vibe. It is the model-driven understanding layer that
# kicks in only when the deterministic colour lexicon misses. The model only
# PROPOSES; the caller (packages/generation/followup/theme_directives.py) then
# re-validates every field (hex must be a real hex, vibe must be a known key)
# before anything is applied, exactly like the copyDirective guards. The model
# never writes a field directly and never does per-element styling.


class StyleDirectiveCandidate(BaseModel):
    """A structured theme mutation proposed by the model from a follow-up."""

    primaryColorHex: str | None = Field(
        default=None,
        description=(
            "The main brand colour as a hex string like '#1e7a46', or null if "
            "the operator did not ask to change the colour. Choose a "
            "mid/dark, contrast-safe tone (it becomes the primary button/link "
            "colour). For a compound like 'grönvit' this is the saturated half "
            "(green); the light half goes in accentColorHex."
        ),
    )
    accentColorHex: str | None = Field(
        default=None,
        description=(
            "An optional secondary/accent colour as a hex string, or null. "
            "Only set this when the operator clearly named two colours (e.g. "
            "'grönvit', 'blå och vit'); it may be a light tone (white/cream)."
        ),
    )
    toneVibe: str | None = Field(
        default=None,
        description=(
            "An optional typography/feel vibe, or null. MUST be exactly one of: "
            "'editorial' (elegant/beautiful serif), 'luxury' (exclusive), "
            "'playful' (friendly/rounded), 'modern' (clean/minimal), 'tech' "
            "(technical/cool), 'calm' (soft serif), 'bold'. Use it for "
            "'lyxig'/'modern'/'lekfull'-style requests; return null otherwise."
        ),
    )


_STYLE_DIRECTIVE_SYSTEM = (
    "You are the visual stylist for Sajtbyggaren. The operator already has a "
    "generated website and typed a short follow-up asking to restyle it "
    "(colours, palette, feel/typography) for the WHOLE site. Interpret the "
    "request into a structured theme mutation: primaryColorHex (a hex like "
    "'#0f766e'), an optional accentColorHex (only when two colours are named), "
    "and an optional toneVibe from the fixed set "
    "editorial|luxury|playful|modern|tech|calm|bold. Map free or compound "
    "colour expressions to a sensible hex (e.g. 'korall' -> a coral hex, "
    "'höstfärger' -> a warm autumnal hex, 'grönvit' -> green primary + white "
    "accent). Pick a mid/dark, contrast-safe primary so button text stays "
    "readable. Hard rules: return ONLY colours/vibe the operator actually "
    "asked for; if the follow-up is not a global style/colour change (it is a "
    "question, a copy edit, adding a component, or per-element styling like "
    "'only the header'), or is unclear, return all nulls. Never invent a brand "
    "colour the operator did not ask for."
)


def extract_style_directive_llm(
    follow_up_prompt: str,
    *,
    language: str,
    model: str,
) -> dict[str, str] | None:
    """Best-effort LLM interpretation of a free/compound style follow-up.

    Returns ``{"primaryColorHex"?, "accentColorHex"?, "toneVibe"?}`` (only the
    fields the model set) or ``None`` when no API key is configured, on any
    error, or when the model returns nothing usable. The caller re-validates
    every field, so this is not the security boundary.
    """
    if not has_openai_api_key():
        return None
    context = f"Language: {language}\nOperator follow-up: {follow_up_prompt}"
    try:
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": _STYLE_DIRECTIVE_SYSTEM},
                {"role": "user", "content": context},
            ],
            text_format=StyleDirectiveCandidate,
        )
        parsed = response.output_parsed
    except Exception as exc:  # noqa: BLE001
        message = f"styleDirective model error: {type(exc).__name__}: {exc}"
        logger.warning(message)
        sys.stderr.write(f"[styleDirective] {message}\n")
        sys.stderr.flush()
        return None
    if parsed is None:
        return None
    result: dict[str, str] = {}
    if parsed.primaryColorHex:
        result["primaryColorHex"] = parsed.primaryColorHex
    if parsed.accentColorHex:
        result["accentColorHex"] = parsed.accentColorHex
    if parsed.toneVibe:
        result["toneVibe"] = parsed.toneVibe
    return result or None
