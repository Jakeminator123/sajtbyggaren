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
    _COPY_CONTENT_REWRITE_VERBS,
    _extract_explicit_replace_value,
    _extract_replace_value,
    _followup_is_additive_request,
    _planned_payload_grounded,
    _safe_copy_payload,
)
from packages.generation.followup.text import (
    _contains_any,
    _contains_any_word,
    _normalise_followup_text,
)

__all__ = [
    "SECTION_OVERRIDE_FIELDS",
    "build_section_override_key",
    "current_section_text",
    "derive_section_edit",
    "is_section_content_rewrite_request",
    "parse_section_content_field",
    "plan_section_edit_via_llm",
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


# Section ids whose copy genuinely lives in the structured Project Input
# company fields. Mirrors the renderer's own mapping:
# ``_STORY_SECTION_IDS`` i packages/generation/build/blueprint_render.py
# (story-body <- company.story) och render_section_hero i renderers.py
# (hero-H1 <- company.heroHeadline/name, hero-underrubrik <- company.tagline).
# Sektions-id:n är scaffold-unika (samma antagande som
# ``resolve_section_content_override``), så route_id behövs inte för matchen.
_HERO_SECTION_IDS: tuple[str, ...] = ("hero",)
_STORY_SECTION_IDS: tuple[str, ...] = ("story", "about-story", "about-story-block")


def section_base_text(
    project_input: dict[str, Any], route_id: str, section_id: str, field: str
) -> str | None:
    """Resolve the current copy a section field renders, for an ``include`` edit.

    Reuses the structured Project Input copy fields the renderer already reads
    — but ONLY for the sections where that mapping is semantically true
    (review-fynd #283 / ADR 0047 "läs aktuell copy för exakt sektion/fält"):
    a story/about ``body`` is ``company.story``; a hero ``headline`` is
    ``company.heroHeadline`` or ``company.name``; a hero ``subheadline`` is
    ``company.tagline``. Every OTHER section (faq, contact, services, ...)
    renders blueprint copy that does not live in Project Input, so this
    honestly returns ``None`` — the previous behaviour handed e.g. a
    ``home.faq.body`` edit ``company.story`` as its base, which appended/
    rewrote the wrong text. ``None`` means: an ``include`` falls back to the
    value alone and the generative editPlan stays an honest no-op.
    """
    company = project_input.get("company")
    company = company if isinstance(company, dict) else {}
    if field == "body":
        if section_id not in _STORY_SECTION_IDS:
            return None
        story = company.get("story")
        return story.strip() if isinstance(story, str) and story.strip() else None
    if field == "subheadline":
        if section_id not in _HERO_SECTION_IDS:
            return None
        tagline = company.get("tagline")
        return tagline.strip() if isinstance(tagline, str) and tagline.strip() else None
    if field == "headline":
        if section_id not in _HERO_SECTION_IDS:
            return None
        for key in ("heroHeadline", "name"):
            value = company.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def current_section_text(
    project_input: dict[str, Any], route_id: str, section_id: str, field: str
) -> str | None:
    """The section's CURRENT effective copy (base for a generative rewrite).

    Prefers a carried-forward ``directives.sectionContentOverrides`` value for
    this exact ``<route>.<section>.<field>`` target (so a later rewrite builds on
    the operator's previous edit), else the structured blueprint copy the
    renderer reads (``section_base_text``). Returns ``None`` when no base copy is
    available. Used by the apply-side editPlan reader (ADR 0047) both as the
    rewrite base shown to the model and as the grounding source for the number
    guard.
    """
    directives = project_input.get("directives")
    if isinstance(directives, dict):
        overrides = directives.get("sectionContentOverrides")
        if isinstance(overrides, dict):
            prior = overrides.get(
                build_section_override_key(route_id, section_id, field)
            )
            if isinstance(prior, str) and prior.strip():
                return prior.strip()
    return section_base_text(project_input, route_id, section_id, field)


# Quality / tone-shift hints that mark a *vibe rewrite* of section copy even
# without an explicit "skriv om"-style verb. The task's canonical phrasing
# "gör om-oss-texten varmare" is a make-verb + a comparative quality word, not
# one of the ADR 0034 rewrite verbs, so the gate must also recognise a
# make-verb paired with such a hint. Matched as substrings of the normalised
# prompt (NFKC + lower-case, diacritics preserved), so both Swedish and English
# comparatives are caught. Kept narrow + paired with a make-verb so a bare
# adjective never engages generation on its own.
_SECTION_REWRITE_MAKE_VERBS: tuple[str, ...] = (
    "gör",
    "gor",
    "göra",
    "gora",
    "make",
    "låt",
    "lat",
    "fräscha",
    "frascha",
    "piffa",
    "pimpa",
    "modernisera",
)
_SECTION_REWRITE_QUALITY_HINTS: tuple[str, ...] = (
    "varmare",
    "kallare",
    "coolare",
    "snyggare",
    "tydligare",
    "enklare",
    "kortare",
    "längre",
    "langre",
    "personligare",
    "lyxigare",
    "modernare",
    "fräschare",
    "fraschare",
    "vassare",
    "mjukare",
    "premium",
    "lyxig",
    "exklusiv",
    "professionell",
    "säljande",
    "saljande",
    "levande",
    "personlig",
    "inbjudande",
    "modern",
    "fräsch",
    "frasch",
    "mer ",
    "mindre ",
    "more ",
    "less ",
    "warmer",
    "cooler",
    "punchier",
    "catchier",
)


def is_section_content_rewrite_request(field: str, follow_up_prompt: str) -> bool:
    """True when the follow-up is a vibe rewrite of a whitelisted section field.

    A generative editPlan (ADR 0047) only fires when the deterministic
    ``derive_section_edit`` already returned ``None`` (no literal value the
    operator supplied). This gate requires a transformation intent - either a
    rewrite/improve verb (the ADR 0034 nivå 3a set) OR a make-verb paired with a
    comparative/quality hint ("gör om-oss-texten varmare", "gör hero-texten mer
    premium") - and rejects an additive / section-add phrasing, so a plain "add a
    section" or a literal replace never routes into generation. A still-explicit
    value also bails (the deterministic path owns it).
    """
    if field not in SECTION_OVERRIDE_FIELDS:
        return False
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return False
    # An explicit literal value is the deterministic path's job, not the
    # planner's - never generate when the operator already gave the words.
    if _extract_explicit_replace_value(follow_up_prompt) is not None:
        return False
    if _followup_is_additive_request(text):
        return False
    has_rewrite_verb = _contains_any_word(text, _COPY_CONTENT_REWRITE_VERBS)
    has_quality_shift = _contains_any_word(
        text, _SECTION_REWRITE_MAKE_VERBS
    ) and _contains_any(text, _SECTION_REWRITE_QUALITY_HINTS)
    return has_rewrite_verb or has_quality_shift


def plan_section_edit_via_llm(
    field: str,
    follow_up_prompt: str,
    *,
    base_text: str | None,
    language: str,
) -> tuple[str, str] | None:
    """Generative editPlan for ONE whitelisted section field (ADR 0047).

    Returns ``("replace", text)`` with guarded, grounded, capped customer copy,
    or ``None`` when nothing safe can be generated. ``None`` is returned without
    an ``OPENAI_API_KEY`` (honest no-op / mock parity), when the gate rejects the
    request, on any model error, or when the generated payload trips the same
    public-copy guard (`_safe_copy_payload`) or     grounding guard
    (`_planned_payload_grounded`) as copyDirectives - the raw instruction can
    never become customer copy and an ungrounded number is dropped. ``base_text``
    is the section's current copy (resolved by the caller via
    ``current_section_text``); it is the rewrite base shown to the model and the
    grounding source. An EMPTY base is an honest no-op (review-fynd #283 /
    ADR 0047): an editPlan REWRITES the section's current copy — with nothing
    to rewrite, generation would be invented copy with no grounding source, so
    the model is never called. Generation is always a ``replace`` (full new
    text), like the about-text editPlan precedent.
    """
    if field not in SECTION_OVERRIDE_FIELDS:
        return None
    if not is_section_content_rewrite_request(field, follow_up_prompt):
        return None
    base = (base_text or "").strip()
    if not base:
        return None
    # Lazy import (cycle break): mirrors copy_directives._plan_copy_directives_via_llm.
    try:
        from packages.generation.brief.extract import plan_section_copy_rewrite_llm
        from packages.generation.brief.models import resolve_copy_directive_model

        model = resolve_copy_directive_model()
        text = plan_section_copy_rewrite_llm(
            follow_up_prompt,
            field=field,
            current_text=base,
            language=language,
            model=model,
        )
    except Exception:  # noqa: BLE001
        return None
    if not text:
        return None
    payload = _safe_copy_payload(
        text, follow_up_prompt=follow_up_prompt, max_length=_FIELD_MAX_LENGTH[field]
    )
    if payload is None:
        return None
    # Grounding guard: a generated payload must not introduce a multi-digit
    # number (founding year, price, count, percentage) absent from the current
    # section copy and the follow-up prompt. Same whole-token guard as the
    # copyDirectives editPlan (ADR 0034); non-numeric facts stay a documented
    # limitation held by the system prompt.
    grounding_text = f"{base} {follow_up_prompt}"
    if not _planned_payload_grounded(payload, grounding_text):
        return None
    return "replace", payload
