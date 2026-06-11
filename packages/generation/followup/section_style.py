"""Section-scoped colour overrides — "Färglägg sektionen" (Verktyg fas 3).

The preview section menu lets the operator pick a background or text
colour for ONE marked section. The dialog emits a deterministic prompt
("Ändra bakgrundsfärgen i den markerade sektionen till #aabbcc.") plus
the structured ``markedSections`` signal (ADR 0046). This module owns:

- :func:`extract_section_style_directive` — deterministic prompt
  parsing (no LLM): a section reference + an explicit colour target
  (bakgrund/textfärg) + a colour (hex literal or lexicon colour word)
  must ALL be present, otherwise ``None`` (honest no-op).
- :func:`apply_section_style_directive` — upserts the override into
  ``project_input["directives"]["sectionStyleOverrides"]`` for every
  VALIDATED marked section. Without marked sections nothing is applied
  — the directive alone never guesses a section.

The render side lives in ``scripts/build_site.py`` (the
``sajtbyggaren-section-style`` region in globals.css): selector
``[data-section-id="<sectionId>"]`` for the background and its
heading/paragraph descendants for the text colour. v1 limitation: the
selector is global, so the same sectionId on several routes gets the
same colour — routeId is persisted for future route scoping.

Conventions: code identifiers in English, operator-facing strings in
Swedish (governance/rules/code-in-english.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .color_lexicon import any_color_hex
from .text import _normalise_followup_text
from .theme_directives import (
    _COLOR_TOKEN_RE,
    _HEX_LITERAL_RE,
    _expand_short_hex,
)

__all__ = [
    "SectionStyleDirective",
    "apply_section_style_directive",
    "extract_section_style_directive",
]

# Schema cap (project-input.schema.json directives.sectionStyleOverrides
# maxItems). Oldest entries are evicted first when the cap is reached.
MAX_SECTION_STYLE_OVERRIDES = 16

# The prompt must actually talk about a section/marking — a plain
# theme-level "byt bakgrundsfärg till grön" (no marking context) keeps
# flowing through the theme extractor unchanged.
_SECTION_REFERENCE_WORDS: tuple[str, ...] = (
    "sektion",
    "markerade",
    "markering",
)

# Explicit colour-target words. "texten" alone is intentionally NOT a
# text-colour target — "ändra texten i sektionen ..." is a copy edit and
# must never be hijacked into a recolour just because the new copy
# happens to mention a colour word.
_BACKGROUND_TARGET_WORDS: tuple[str, ...] = (
    "bakgrundsfärg",
    "bakgrundsfarg",
    "bakgrund",
    "background",
)
_TEXT_TARGET_PHRASES: tuple[str, ...] = (
    "textfärg",
    "textfarg",
    "färgen på texten",
    "färgen på text",
    "färg på texten",
    "textens färg",
    "text color",
    "text colour",
)


@dataclass(frozen=True)
class SectionStyleDirective:
    """One validated section recolour request from a follow-up prompt."""

    target: str  # "background" | "text"
    color_hex: str  # normalised lower-case #rrggbb


def _first_color_in_text(text: str) -> str | None:
    """Hex literal first, then the first lexicon colour word (in order)."""
    hex_match = _HEX_LITERAL_RE.search(text)
    if hex_match:
        return _expand_short_hex(hex_match.group(0))
    for token_match in _COLOR_TOKEN_RE.finditer(text):
        hex_value = any_color_hex(token_match.group(0))
        if hex_value:
            return hex_value.lower()
    return None


def _target_in_text(text: str) -> str | None:
    """Return ``"background"``/``"text"`` for the target mentioned LAST
    before the colour — or the only one present. ``None`` without an
    explicit target (the directive never guesses)."""
    background_index = max(
        (text.rfind(word) for word in _BACKGROUND_TARGET_WORDS), default=-1
    )
    text_index = max(
        (text.rfind(phrase) for phrase in _TEXT_TARGET_PHRASES), default=-1
    )
    if background_index < 0 and text_index < 0:
        return None
    return "background" if background_index >= text_index else "text"


def extract_section_style_directive(
    prompt: str,
    *,
    language: str = "sv",
) -> SectionStyleDirective | None:
    """Deterministically parse a section recolour request, else ``None``.

    Requires all three of: a section reference (sektion/markerade), an
    explicit colour target (bakgrund/textfärg), and a colour (hex
    literal or lexicon colour word). ``language`` is accepted for parity
    with the sibling extractors; the word lists already cover the
    Swedish + English phrasings the dialog emits.
    """
    del language  # word lists are bilingual; kept for extractor parity
    text = _normalise_followup_text(prompt)
    if not text:
        return None
    if not any(word in text for word in _SECTION_REFERENCE_WORDS):
        return None
    target = _target_in_text(text)
    if target is None:
        return None
    color_hex = _first_color_in_text(text)
    if color_hex is None:
        return None
    return SectionStyleDirective(target=target, color_hex=color_hex)


def apply_section_style_directive(
    project_input: dict[str, Any],
    directive: SectionStyleDirective | None,
    marked_sections: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    """Upsert the directive into ``directives.sectionStyleOverrides``.

    One override entry per VALIDATED marked section (routeId+sectionId
    already checked against the base run's facit by
    ``validate_marked_sections``). Returns the list of upserted entries
    so the merge can report what was applied — empty when the directive
    is ``None`` or no marking exists (honest no-op, never a guess).
    """
    if directive is None or not marked_sections:
        return []
    field = (
        "backgroundColorHex" if directive.target == "background" else "textColorHex"
    )
    directives_block = project_input.setdefault("directives", {})
    overrides = directives_block.setdefault("sectionStyleOverrides", [])
    applied: list[dict[str, str]] = []
    for marking in marked_sections:
        route_id = marking.get("routeId")
        section_id = marking.get("sectionId")
        if not route_id or not section_id:
            continue
        entry = next(
            (
                existing
                for existing in overrides
                if existing.get("routeId") == route_id
                and existing.get("sectionId") == section_id
            ),
            None,
        )
        if entry is None:
            if len(overrides) >= MAX_SECTION_STYLE_OVERRIDES:
                overrides.pop(0)
            entry = {"routeId": route_id, "sectionId": section_id}
            overrides.append(entry)
        entry[field] = directive.color_hex
        applied.append(dict(entry))
    return applied
