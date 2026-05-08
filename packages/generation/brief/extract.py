"""briefModel: extract a structured Site Brief from a raw prompt.

Uses OpenAI structured output (response_format=SiteBrief) when OPENAI_API_KEY
is available. Otherwise returns a deterministic mock so dev_generate.py and
tests can run without an API key.

The Site Brief schema is intentionally narrow: only fields that subsequent
phases actually read. Adding new fields requires a naming-dictionary entry.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("sajtbyggaren.brief")


SWEDISH_HINTS = {
    "skapa", "för", "hemsida", "sajt", "och", "att", "med", "på",
    "elektriker", "rörmokare", "tandläkare", "restaurang", "i", "av",
    "ett", "en", "kontakt", "tjänster", "om", "oss",
}


def detect_language(prompt: str) -> str:
    tokens = {t.lower().strip(",.!?:;") for t in prompt.split() if t}
    if tokens & SWEDISH_HINTS:
        return "sv"
    return "en"


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
            "Specific services/products the user mentioned (e.g. 'akut-elservice', "
            "'paneldragning', 'laddbox-installation'). Drives concrete copy."
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
    "the user did not ask for. Slugs are kebab-case English even if prompt is in another "
    "language."
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
    if not os.environ.get("OPENAI_API_KEY"):
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
    """Serialise a BriefResult into the artifact shape that dev_generate.py writes.

    Reads source from the BriefResult so modelUsed/_status reflects the actual
    code path (real, mock-no-key, mock-llm-error). Never claims real when fallback occurred.
    """
    brief = result.brief
    is_real = result.source == "real"
    return {
        "runId": run_id,
        "language": brief.language,
        "rawPrompt": brief.raw_prompt,
        "businessTypeGuess": brief.business_type,
        "pageCount": brief.page_count,
        "tone": brief.tone,
        "targetAudience": brief.target_audience,
        "requestedCapabilities": brief.requested_capabilities,
        "locationHint": brief.location_hint,
        "conversionGoals": brief.conversion_goals,
        "servicesMentioned": brief.services_mentioned,
        "contentDepth": brief.content_depth,
        "notesForPlanner": brief.notes_for_planner,
        "sourceModelRole": "briefModel",
        "modelUsed": model if is_real else "mock",
        "briefSource": result.source,
        "briefError": result.error,
        "createdAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "_status": result.source,
    }
