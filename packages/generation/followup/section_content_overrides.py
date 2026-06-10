"""Section content overrides (ADR 0043) - blueprint-content-utföraren.

This is the sanctioned bridge that turns a validated ``copy_change`` patch
(KÖR-7b) into a *visible* section-text edit on the next immutable Project Input
version (KÖR-7c apply) without ever writing a free file patch.

The KÖR-7b planner proposes copy targets on the form
``contentBlocks.<routeId>.<sectionId>.<field>`` with ``value=None`` (the planner
never invents copy - honesty rule). The new copy the operator asked for lives in
the follow-up prompt, so apply derives it here, deterministically and guarded by
the SAME public-copy guards as ``copyDirectives`` (so the raw instruction can
never become customer copy). The result is stored on
``directives.sectionContentOverrides`` (a ``"<route>.<section>.<field>" -> text``
map); the renderer prefers it over the regenerated blueprint copy, mirroring the
``company.heroHeadline`` pin.

Only the three whitelisted text fields are accepted (``headline`` /
``subheadline`` / ``body``); anything else stays an honest unmapped no-op so
apply never invents a new runtime contract.

Mock-safe + deterministic: pure string extraction over the prompt, no LLM, no
``OPENAI_API_KEY``. A vibe rewrite with no literal/explicit value the operator
supplied stays an honest no-op (generating brand-new section copy from an
instruction is copyModel work, tracked as a follow-up).
"""

from __future__ import annotations

from typing import Any

from packages.generation.followup.copy_directives import (
    _extract_explicit_replace_value,
    _extract_replace_value,
    _safe_copy_payload,
)
from packages.generation.followup.text import (
    _contains_any,
    _normalise_followup_text,
)

__all__ = [
    "SECTION_OVERRIDE_FIELDS",
    "build_section_override_key",
    "derive_section_edit",
    "parse_section_content_field",
    "render_section_override_text",
]

# The artefakt root the KÖR-7b planner addresses (contentBlocks.<route>.<section>.<leaf>).
_CONTENT_BLOCKS_ROOT = "contentBlocks"

# The only section text fields apply may write as an override. A closed
# whitelist keeps a copy_change from ever touching anything but section copy.
SECTION_OVERRIDE_FIELDS: tuple[str, ...] = ("headline", "subheadline", "body")

# Per-field caps (stricter than the schema's uniform maxLength 600, mirroring how
# copyDirectives caps per target in code). headline/subheadline are short display
# lines; body is paragraph copy.
_FIELD_MAX_LENGTH: dict[str, int] = {
    "headline": 200,
    "subheadline": 200,
    "body": 600,
}

# "Mention/include" markers for a body edit: "...så den nämner X", "ta upp X",
# "ha med X". These signal the operator wants to ADD a fact to the existing
# section copy rather than replace it, so the override appends the guarded
# fragment to the current body instead of overwriting it. Kept narrow and
# body-only (a headline/subheadline edit is always a replace). Matched as a
# substring of the normalised prompt; the value is the text AFTER the marker.
_BODY_MENTION_MARKERS: tuple[str, ...] = (
    "så den nämner",
    "sa den namner",
    "så att den nämner",
    "så den tar upp",
    "så den lyfter",
    "som nämner",
    "nämner att",
    "nämner",
    "namner",
    "ta upp",
    "ha med",
    "mention",
    "mentions",
)


def parse_section_content_field(patch_field: str) -> tuple[str, str, str] | None:
    """Parse ``contentBlocks.<route>.<section>.<field>`` into its parts.

    Returns ``(routeId, sectionId, field)`` only when the address is a
    4-segment contentBlocks path whose leaf is one of the whitelisted section
    text fields; otherwise ``None`` (so apply reports it unmapped instead of
    inventing an override). Mirrors the planner/validator addressing contract
    (``packages/generation/orchestration/patch/validate.py``).
    """
    segments = patch_field.split(".") if patch_field else []
    if len(segments) != 4:
        return None
    root, route_id, section_id, leaf = segments
    if root != _CONTENT_BLOCKS_ROOT:
        return None
    if leaf not in SECTION_OVERRIDE_FIELDS:
        return None
    if not route_id or not section_id:
        return None
    return route_id, section_id, leaf


def build_section_override_key(route_id: str, section_id: str, field: str) -> str:
    """The ``directives.sectionContentOverrides`` map key for a section field."""
    return f"{route_id}.{section_id}.{field}"


def _extract_mention_value(follow_up_prompt: str) -> str | None:
    """Pull the fragment AFTER a body "mention" marker (raw, unguarded).

    Returns the text following the first mention marker found in the prompt, or
    ``None`` when no marker is present. The caller guards the fragment through
    ``_safe_copy_payload`` before it is ever used as copy.
    """
    lowered = follow_up_prompt.lower()
    best_pos = -1
    best_marker = ""
    for marker in _BODY_MENTION_MARKERS:
        pos = lowered.find(marker)
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos
            best_marker = marker
    if best_pos == -1:
        return None
    tail = follow_up_prompt[best_pos + len(best_marker) :]
    tail = tail.strip().strip(":-–—").strip()
    return tail or None


def derive_section_edit(
    field: str, follow_up_prompt: str
) -> tuple[str, str] | None:
    """Derive ``(operation, value)`` for a section text edit from the prompt.

    ``operation`` is ``"replace"`` (set the field to ``value``) or ``"include"``
    (append ``value`` to the current section copy - body only). ``value`` is the
    guarded, capped customer copy. Returns ``None`` when nothing safe can be
    derived (no literal value the operator supplied), which keeps the build an
    honest no-op instead of fabricating copy.

    - headline / subheadline: an explicit replace value (``till X`` / quoted /
      colon / ``"X" istället för "Y"``) - never a bare trailing vibe.
    - body: a strict explicit replace value (quoted / colon / marker), or a
      ``...så den nämner X`` mention that appends X to the existing body.
    """
    if field not in SECTION_OVERRIDE_FIELDS:
        return None
    cap = _FIELD_MAX_LENGTH[field]

    if field == "body":
        # A paragraph rewrite must come from an EXPLICIT value (quoted/colon),
        # exactly like copyDirectives about-text - a bare trailing "till mer
        # personligt" is a vibe, not literal copy.
        raw_value = _extract_explicit_replace_value(follow_up_prompt)
        payload = _safe_copy_payload(
            raw_value, follow_up_prompt=follow_up_prompt, max_length=cap
        )
        if payload is not None:
            return "replace", payload
        # No literal replace value: a "mention" marker lets the operator ADD a
        # fact to the existing body ("gör om om-oss-texten så den nämner X").
        mention = _extract_mention_value(follow_up_prompt)
        payload = _safe_copy_payload(
            mention, follow_up_prompt=follow_up_prompt, max_length=cap
        )
        if payload is not None:
            return "include", payload
        return None

    # headline / subheadline: short display lines. A loose trailing "till X" is
    # accepted (short labels are commonly given unquoted), guarded the same way.
    raw_value = _extract_replace_value(follow_up_prompt)
    payload = _safe_copy_payload(
        raw_value, follow_up_prompt=follow_up_prompt, max_length=cap
    )
    if payload is not None:
        return "replace", payload
    return None


def render_section_override_text(
    field: str,
    operation: str,
    value: str,
    *,
    base_text: str | None,
) -> str | None:
    """Compose the final override text for a derived section edit.

    ``replace`` returns the value verbatim. ``include`` appends the value to the
    existing ``base_text`` (the current section copy) so a "mention" edit adds a
    fact instead of dropping the story; when there is no base it falls back to
    the value alone. The result is capped to the field's max length. Returns
    ``None`` when nothing usable remains.
    """
    value = value.strip()
    if not value:
        return None
    cap = _FIELD_MAX_LENGTH.get(field, 600)
    if operation == "include" and isinstance(base_text, str) and base_text.strip():
        base = base_text.strip()
        # Idempotency / honesty: do not append a fact the body already states.
        if _normalise_followup_text(value) and _contains_any(
            _normalise_followup_text(base), (_normalise_followup_text(value),)
        ):
            text = base
        else:
            text = f"{base} {value}".strip()
    else:
        text = value
    text = text[:cap].strip()
    return text or None


def section_base_text(
    project_input: dict[str, Any], route_id: str, section_id: str, field: str
) -> str | None:
    """Resolve the current copy a section field renders, for an ``include`` edit.

    Reuses the structured Project Input copy fields the renderer already reads:
    a story/about ``body`` is ``company.story``; a hero ``headline`` is
    ``company.heroHeadline`` or ``company.name``; a hero ``subheadline`` is
    ``company.tagline``. Returns ``None`` when no base copy is available (the
    caller then falls back to the value alone).
    """
    company = project_input.get("company")
    company = company if isinstance(company, dict) else {}
    if field == "body":
        story = company.get("story")
        return story.strip() if isinstance(story, str) and story.strip() else None
    if field == "subheadline":
        tagline = company.get("tagline")
        return tagline.strip() if isinstance(tagline, str) and tagline.strip() else None
    if field == "headline":
        for key in ("heroHeadline", "name"):
            value = company.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
