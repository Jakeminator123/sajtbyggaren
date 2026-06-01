"""Phase 1 Understand: turn a raw prompt into a structured Site Brief.

Public API:
    extract_site_brief(prompt: str, *, model: str = ..., language_hint: str | None = None) -> BriefResult
        Always returns a BriefResult that wraps a SiteBrief plus a
        truth-field `source` (`real` / `mock-no-key` / `mock-llm-error`).
        Never raises on an OpenAI failure - the failure is captured in
        `source` + `error` so callers can write deterministic artefakter.

    site_brief_to_artifact(result: BriefResult, *, run_id: str, model: str) -> dict
        Serialises a BriefResult into the canonical site-brief.json shape
        locked by governance/schemas/site-brief.schema.json.

    resolve_brief_model() -> str
        Returns the briefModel model string from llm-models.v1.json. Strict.

    detect_language(prompt: str) -> str
        ISO 639-1 (sv/en) inference from prompt content.

Mock fallback runs when OPENAI_API_KEY is not set (or whitespace-only).
"""

from .extract import (
    BriefResult,
    SiteBrief,
    detect_language,
    extract_site_brief,
    site_brief_to_artifact,
)
from .models import (
    BRIEF_ROLE_ID,
    COPY_DIRECTIVE_ROLE_ID,
    BriefModelResolutionError,
    has_openai_api_key,
    resolve_brief_model,
    resolve_copy_directive_model,
)

__all__ = [
    "BRIEF_ROLE_ID",
    "COPY_DIRECTIVE_ROLE_ID",
    "BriefModelResolutionError",
    "BriefResult",
    "SiteBrief",
    "detect_language",
    "extract_site_brief",
    "has_openai_api_key",
    "resolve_brief_model",
    "resolve_copy_directive_model",
    "site_brief_to_artifact",
]
