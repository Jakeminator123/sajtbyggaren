"""Phase 1 Understand: turn a raw prompt into a structured Site Brief.

Public API:
    extract_site_brief(prompt: str, *, model: str = ..., language_hint: str | None = None) -> SiteBrief

Falls back to a deterministic mock when OPENAI_API_KEY is not set.
"""

from .extract import (
    BriefResult,
    SiteBrief,
    detect_language,
    extract_site_brief,
    site_brief_to_artifact,
)

__all__ = [
    "BriefResult",
    "SiteBrief",
    "detect_language",
    "extract_site_brief",
    "site_brief_to_artifact",
]
