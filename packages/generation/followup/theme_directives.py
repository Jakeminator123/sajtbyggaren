"""Follow-up theme directives: colour + font/style restyle from a prompt.

A follow-up like ``"gör färgen rosa och typsnittet snyggt"`` is a ``visual_style``
edit that NO path applied before this module: the copyDirective subsystem only
touches text targets (company-name / tagline / about-text / services) and the
KÖR-7 patch planner only handles ``component_add`` / ``copy_change``
(``packages/generation/orchestration/patch/planner.py`` lists ``visual_style``
as out of scope). The router classifies the intent, but nothing downstream acted
on it, so the follow-up was a silent no-op.

This module closes that gap WITHOUT a schema change and WITHOUT a new render
path. It maps:

* a natural-language colour word -> ``brand.primaryColorHex`` (already rendered
  by ``scripts/build_site.py:_token_overrides_from_project_input`` into the
  ``--primary`` CSS token, with an auto-contrast ``--primary-foreground``), and
* a font / style vibe -> ``tone.primary`` (already rendered by
  ``_typography_overlay_for_tone`` -> ``_TONE_TYPOGRAPHY``, which swaps in a real
  Google Font such as Playfair Display / Space Grotesk / Quicksand).

``patch_globals_css`` re-applies both on the follow-up rebuild, so the change is
visible in the preview after one prompt.

Canonical model (governance/rules/site-mutation-layers.md + project-dna.v1.json):
this IS the ``restyle`` follow-up intent (router ``editKind`` ``visual_style`` ==
DNA intent ``restyle``). ``brand.primaryColorHex`` / ``tone.primary`` on
``Project Input`` is the sanctioned PER-SITE override surface until the
``Project DNA`` ``themeTokens`` field is implemented at runtime; when it lands,
this seam moves to ``themeTokens`` (same intent, canonical field). We never edit
the shared ``Variant`` to restyle a single site - that would restyle every site
on that variant.

Honest by construction:

* Returns ``None`` when the prompt carries no colour/font intent, so a non-theme
  follow-up is byte-identical to before (legacy behaviour preserved).
* Only ever sets two well-known, schema-declared fields
  (``brand.primaryColorHex`` is ``string``; ``tone.primary`` is ``string``) from
  a CLOSED allowlist - never invented copy, never an arbitrary value.
* The chosen font vibe keys deliberately avoid the colour-token keys consumed by
  ``_TONE_COLOR_TOKENS`` (``warm`` / ``premium``), so a font-only request never
  silently shifts the colour via the tone fallback.

Conventions: identifiers + comments in English (governance/rules/code-in-english.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from packages.generation.followup.text import (
    _contains_word,
    _normalise_followup_text,
)

# Natural-language colour word -> hex applied to ``brand.primaryColorHex``.
# Values are mid-to-dark brand tones so the auto-contrast foreground stays
# readable; light/neutral words (white/grey) are intentionally excluded because
# a near-white primary breaks button/CTA contrast. Swedish + English + common
# ASCII-folded spellings (rod/bla/gron) are covered so casing/diacritics don't
# create a gap.
_COLOR_WORD_HEX: dict[str, str] = {
    "rosa": "#db2777",
    "pink": "#db2777",
    "magenta": "#be185d",
    "röd": "#dc2626",
    "rött": "#dc2626",
    "röda": "#dc2626",
    "rod": "#dc2626",
    "red": "#dc2626",
    "blå": "#2563eb",
    "blått": "#2563eb",
    "blåa": "#2563eb",
    "bla": "#2563eb",
    "blue": "#2563eb",
    "marinblå": "#1e3a8a",
    "marinblått": "#1e3a8a",
    "navy": "#1e3a8a",
    "grön": "#16a34a",
    "grönt": "#16a34a",
    "gröna": "#16a34a",
    "gron": "#16a34a",
    "green": "#16a34a",
    "lila": "#7c3aed",
    "violett": "#7c3aed",
    "purple": "#7c3aed",
    "orange": "#ea580c",
    "gul": "#ca8a04",
    "gult": "#ca8a04",
    "gula": "#ca8a04",
    "yellow": "#ca8a04",
    "turkos": "#0d9488",
    "turkost": "#0d9488",
    "teal": "#0d9488",
    "mint": "#10b981",
    "petrol": "#0e7490",
    "korall": "#f43f5e",
    "coral": "#f43f5e",
    "vinröd": "#9f1239",
    "vinrott": "#9f1239",
    "bordeaux": "#9f1239",
    "brun": "#92400e",
    "brunt": "#92400e",
    "bruna": "#92400e",
    "brown": "#92400e",
    "guld": "#b45309",
    "gyllene": "#b45309",
    "gold": "#b45309",
    "svart": "#171717",
    "svarta": "#171717",
    "black": "#171717",
}

# Whole-word match with the same boundary rule as ``text._contains_word`` (so a
# colour word is never matched inside a longer word, e.g. "blå" inside "marinblå").
def _color_word_position(text: str, word: str) -> int | None:
    match = re.search(
        rf"(?<![a-zåäöéü0-9]){re.escape(word)}(?![a-zåäöéü0-9])", text
    )
    return match.start() if match else None

# Font / style vibe word -> ``tone.primary`` key understood by
# ``_TONE_TYPOGRAPHY`` (via ``_normalize_tone_key``). Kept off the
# ``_TONE_COLOR_TOKENS`` keys (warm/premium) so a font-only request does not
# leak a colour change through the tone->colour fallback.
_FONT_VIBE_TONE: dict[str, str] = {
    # Elegant / beautiful / luxurious -> Playfair Display (serif, high contrast).
    "elegant": "editorial",
    "elegantare": "editorial",
    "stilren": "editorial",
    "stilrent": "editorial",
    "snygg": "editorial",
    "snyggt": "editorial",
    "snyggare": "editorial",
    "svinsnygg": "editorial",
    "svinsnyggt": "editorial",
    "fin": "editorial",
    "fint": "editorial",
    "finare": "editorial",
    "exklusiv": "luxury",
    "exklusivt": "luxury",
    "lyxig": "luxury",
    "lyxigt": "luxury",
    "gorgeous": "editorial",
    "beautiful": "editorial",
    "fancy": "luxury",
    # Playful / friendly -> Quicksand + Nunito (rounded).
    "lekfull": "playful",
    "lekfullt": "playful",
    "lekfullare": "playful",
    "rolig": "playful",
    "roligt": "playful",
    "mjuk": "playful",
    "mjukt": "playful",
    "playful": "playful",
    # Modern / tech -> Space Grotesk (geometric, tight tracking).
    "modern": "modern",
    "modernt": "modern",
    "modernare": "modern",
    "minimalistisk": "modern",
    "minimalistiskt": "modern",
    "minimalistic": "modern",
    "clean": "modern",
    "teknisk": "tech",
    "tekniskt": "tech",
    "cool": "tech",
    "coolt": "tech",
    "häftig": "tech",
    "haftig": "tech",
    "häftigt": "tech",
    "haftigt": "tech",
    "tech": "tech",
    # Calm / editorial serif -> Cormorant Garamond.
    "lugn": "calm",
    "lugnt": "calm",
    "rofylld": "calm",
    "harmonisk": "calm",
    # Bold.
    "bold": "bold",
    "kraftfull": "bold",
    "kraftfullt": "bold",
}

_FONT_VIBE_WORDS_BY_SPECIFICITY: tuple[str, ...] = tuple(
    sorted(_FONT_VIBE_TONE, key=len, reverse=True)
)

# Words that signal "change the typeface" even without a vibe word. When one of
# these is present but no vibe word resolved, we apply a pleasant default vibe so
# a bare "ändra typsnittet" still produces a visible, tasteful change instead of
# a silent no-op.
_FONT_TRIGGER_WORDS: tuple[str, ...] = (
    "typsnitt",
    "typsnittet",
    "typsnitten",
    "font",
    "fonten",
    "fonts",
    "typografi",
    "typografin",
    "fontfamilj",
    "teckensnitt",
    "teckensnittet",
)

# Default vibe when a font change is requested without a recognised vibe word.
# Playfair Display is an obviously different, attractive serif - a clear visible
# delta from the Geist-sans default that reads as "snyggt".
_DEFAULT_FONT_VIBE = "editorial"


@dataclass(frozen=True)
class ThemeDirective:
    """A resolved theme change derived from a follow-up prompt.

    ``primaryColorHex`` / ``accentColorHex`` / ``toneVibe`` are ``None`` when
    that dimension carried no intent. ``colorWord`` / ``accentWord`` / ``vibeWord``
    record the matched source word for honest UI summaries and tests. At least
    one value field is set whenever :func:`extract_theme_directive` returns a
    directive (it returns ``None`` otherwise).
    """

    primaryColorHex: str | None = None
    accentColorHex: str | None = None
    toneVibe: str | None = None
    colorWord: str | None = None
    accentWord: str | None = None
    vibeWord: str | None = None


def _ordered_colors(text: str) -> list[tuple[str, str]]:
    """Return ``(hex, word)`` pairs for colour words present in ``text``, in the
    order they appear, de-duplicated by hex (so "rosa" and "pink" don't both
    count). The first is treated as the primary colour, the second (if any) as
    the accent - so "gör den rosa och blå" yields a pink primary + blue accent.
    """
    matches: list[tuple[int, str, str]] = []
    for word, hex_value in _COLOR_WORD_HEX.items():
        position = _color_word_position(text, word)
        if position is not None:
            matches.append((position, hex_value, word))
    matches.sort(key=lambda item: (item[0], -len(item[2])))
    ordered: list[tuple[str, str]] = []
    seen_hex: set[str] = set()
    for _position, hex_value, word in matches:
        if hex_value in seen_hex:
            continue
        seen_hex.add(hex_value)
        ordered.append((hex_value, word))
    return ordered


def _match_font_vibe(text: str) -> tuple[str | None, str | None]:
    for word in _FONT_VIBE_WORDS_BY_SPECIFICITY:
        if _contains_word(text, word):
            return _FONT_VIBE_TONE[word], word
    return None, None


def _font_change_requested(text: str) -> bool:
    return any(_contains_word(text, word) for word in _FONT_TRIGGER_WORDS)


def extract_theme_directive(
    prompt: str,
    *,
    language: str = "sv",
) -> ThemeDirective | None:
    """Return a :class:`ThemeDirective` for ``prompt`` or ``None``.

    Deterministic, offline, no LLM. ``language`` is accepted for signature
    parity with the copyDirective extractor; the allowlist already covers both
    Swedish and English so the parameter is not consulted today.
    """
    text = _normalise_followup_text(prompt)
    if not text:
        return None

    colors = _ordered_colors(text)
    color_hex, color_word = colors[0] if colors else (None, None)
    accent_hex, accent_word = colors[1] if len(colors) > 1 else (None, None)
    vibe, vibe_word = _match_font_vibe(text)

    # A bare "ändra typsnittet" (font trigger, no vibe) gets a tasteful default
    # so the request is honoured visibly instead of silently dropped.
    if vibe is None and _font_change_requested(text):
        vibe = _DEFAULT_FONT_VIBE

    if color_hex is None and vibe is None:
        return None

    return ThemeDirective(
        primaryColorHex=color_hex,
        accentColorHex=accent_hex,
        toneVibe=vibe,
        colorWord=color_word,
        accentWord=accent_word,
        vibeWord=vibe_word,
    )


def apply_theme_directive(
    project_input: dict[str, Any],
    directive: ThemeDirective | None,
) -> bool:
    """Apply ``directive`` onto ``project_input`` in place. Return whether it
    changed anything.

    Sets only ``brand.primaryColorHex`` and/or ``tone.primary`` - both already
    declared in ``governance/schemas/project-input.schema.json`` and already
    rendered by the existing builder, so no schema bump or new render path is
    needed. A ``None`` directive is a no-op (legacy follow-ups stay identical).
    """
    if directive is None:
        return False

    applied = False
    if directive.primaryColorHex or directive.accentColorHex:
        brand = project_input.get("brand")
        if not isinstance(brand, dict):
            brand = {}
            project_input["brand"] = brand
        if directive.primaryColorHex:
            brand["primaryColorHex"] = directive.primaryColorHex
            applied = True
        if directive.accentColorHex:
            brand["accentColorHex"] = directive.accentColorHex
            applied = True

    if directive.toneVibe:
        tone = project_input.get("tone")
        if not isinstance(tone, dict):
            tone = {}
            project_input["tone"] = tone
        tone["primary"] = directive.toneVibe
        applied = True

    return applied
