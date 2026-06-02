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
    "The services_mentioned field is the EXCEPTION: return short natural-language phrases "
    "in the prompt's original language so the generated website renders readable labels."
)


def _mock_brief(prompt: str, language_hint: str | None) -> SiteBrief:
    """Deterministic fallback when no API key is available."""
    language = language_hint or detect_language(prompt)
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


def site_brief_to_artifact(
    result: BriefResult,
    *,
    run_id: str,
    model: str,
) -> dict[str, Any]:
    """Serialise a BriefResult into the canonical Site Brief artefakt.

    Shape locked by ``governance/schemas/site-brief.schema.json`` (ADR 0013).
    Reads source from the BriefResult so modelUsed/briefSource reflects the
    actual code path (real, mock-no-key, mock-llm-error). Never claims real
    when fallback occurred.
    """
    brief = result.brief
    is_real = result.source == "real"
    return {
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
