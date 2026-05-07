"""briefModel: extract a structured Site Brief from a raw prompt.

Uses OpenAI structured output (response_format=SiteBrief) when OPENAI_API_KEY
is available. Otherwise returns a deterministic mock so dev_generate.py and
tests can run without an API key.

The Site Brief schema is intentionally narrow: only fields that subsequent
phases actually read. Adding new fields requires a naming-dictionary entry.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


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
    """Structured Site Brief produced by Phase 1 Understand."""

    language: str = Field(description="ISO 639-1 code, e.g. sv or en.")
    business_type: Optional[str] = Field(
        default=None,
        description="A short slug describing the business (e.g. 'electrician', 'dental-clinic').",
    )
    target_audience: list[str] = Field(
        default_factory=list,
        description="Who the site is meant to convert. 0-5 items.",
    )
    page_count: Optional[int] = Field(
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
    location_hint: Optional[str] = Field(
        default=None,
        description="City or region if mentioned in the prompt.",
    )
    raw_prompt: str = Field(description="The original prompt as received.")
    notes_for_planner: Optional[str] = Field(
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


def extract_site_brief(
    prompt: str,
    *,
    model: str = "gpt-5.4",
    language_hint: str | None = None,
) -> SiteBrief:
    """Phase 1 Understand entry point.

    Returns a SiteBrief. If OPENAI_API_KEY is missing, returns a mock brief
    so callers don't need to branch on environment.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return _mock_brief(prompt, language_hint)

    try:
        return _real_brief(prompt, model=model, language_hint=language_hint)
    except Exception as exc:  # noqa: BLE001
        # Soft-fall back to mock so the pipeline doesn't die mid-run.
        mock = _mock_brief(prompt, language_hint)
        mock.notes_for_planner = (
            f"Mock brief efter LLM-fel: {type(exc).__name__}: {exc}"
        )
        return mock


def site_brief_to_artifact(
    brief: SiteBrief,
    *,
    run_id: str,
    model: str,
    used_real_llm: bool,
) -> dict[str, Any]:
    """Serialise a SiteBrief into the artifact shape that dev_generate.py writes."""
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
        "notesForPlanner": brief.notes_for_planner,
        "sourceModelRole": "briefModel",
        "modelUsed": model if used_real_llm else "mock",
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "_status": "real" if used_real_llm else "mock - real briefModel call wired but no key set",
    }
