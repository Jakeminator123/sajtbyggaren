"""Central colour lexicon for the stylist role (free + compound colour -> hex).

Single source of truth shared by:

* the deterministic theme extractor
  (``packages/generation/followup/theme_directives.py``), which maps a colour
  word to ``brand.primaryColorHex`` (+ ``accentColorHex``), and
* the router (``packages/generation/orchestration/router/classify.py``), whose
  colour-name set decides whether a colour word reads as a ``visual_style``
  edit.

Keeping one lexicon means a new colour - or a compound like ``"grönvit"`` -
is understood by BOTH the classifier and the extractor from a single edit, so a
free colour expression can never classify as a restyle yet resolve to no hex
(or vice versa).

Two tiers:

* :data:`PRIMARY_COLOR_HEX` - mid/dark, contrast-safe brand tones used for
  ``brand.primaryColorHex`` (the auto-contrast foreground stays readable).
* :data:`ACCENT_COLOR_HEX` - light / neutral words (white, cream, beige,
  silver, light grey) that are SAFE only as an accent. A near-white primary
  breaks button/CTA contrast, so these never become the primary on their own;
  they only fill the accent slot of a two-colour or compound expression
  ("grönvit" -> green primary + white accent, "blå och vit" -> blue + white).

Conventions: identifiers + comments in English
(governance/rules/code-in-english.md). The lexicon carries Swedish, English and
ASCII-folded spellings so casing/diacritics never create a gap.
"""

from __future__ import annotations

import re

# Mid-to-dark brand tones - safe as ``brand.primaryColorHex``. The hexes for
# colours that already existed in theme_directives.py are preserved verbatim so
# the locked extractor tests keep passing; the rest are additive.
PRIMARY_COLOR_HEX: dict[str, str] = {
    "rosa": "#db2777",
    "pink": "#db2777",
    "magenta": "#be185d",
    "röd": "#dc2626",
    "rött": "#dc2626",
    "röda": "#dc2626",
    "rod": "#dc2626",
    "red": "#dc2626",
    "mörkröd": "#b91c1c",
    "morkrod": "#b91c1c",
    "blå": "#2563eb",
    "blått": "#2563eb",
    "blåa": "#2563eb",
    "bla": "#2563eb",
    "blue": "#2563eb",
    "ljusblå": "#0ea5e9",
    "ljusbla": "#0ea5e9",
    "mörkblå": "#1e3a8a",
    "morkbla": "#1e3a8a",
    "marinblå": "#1e3a8a",
    "marinblått": "#1e3a8a",
    "navy": "#1e3a8a",
    "grön": "#16a34a",
    "grönt": "#16a34a",
    "gröna": "#16a34a",
    "gron": "#16a34a",
    "green": "#16a34a",
    "ljusgrön": "#22c55e",
    "ljusgron": "#22c55e",
    "mörkgrön": "#166534",
    "morkgron": "#166534",
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
    "grå": "#4b5563",
    "grått": "#4b5563",
    "gråa": "#4b5563",
    "gra": "#4b5563",
    "gray": "#4b5563",
    "grey": "#4b5563",
}

# Light / neutral words - safe only as an accent (never the primary, contrast).
ACCENT_COLOR_HEX: dict[str, str] = {
    "vit": "#ffffff",
    "vitt": "#ffffff",
    "vita": "#ffffff",
    "white": "#ffffff",
    "grädde": "#faf7f0",
    "gradde": "#faf7f0",
    "gräddvit": "#faf7f0",
    "graddvit": "#faf7f0",
    "kräm": "#faf7f0",
    "kram": "#faf7f0",
    "cream": "#faf7f0",
    "elfenben": "#f5f0e6",
    "ivory": "#f5f0e6",
    "beige": "#e7ddc8",
    "silver": "#c0c5ce",
    "ljusgrå": "#e5e7eb",
    "ljusgra": "#e5e7eb",
}

# Every single-word colour, both tiers. Used for single-word lookups and the
# router's colour-name recognition.
ALL_COLOR_HEX: dict[str, str] = {**PRIMARY_COLOR_HEX, **ACCENT_COLOR_HEX}

# All colour NAMES (primary + accent) - the router unions this into its
# ``_STYLE_COLORS`` set so every lexicon colour reads as a style adjective.
COLOR_NAMES: frozenset[str] = frozenset(ALL_COLOR_HEX)

# A token must split into two parts each >= this many characters to be treated
# as a compound colour ("grönvit" = grön + vit). Keeps accidental two-letter
# fragments from matching.
_MIN_COMPOUND_PART = 3

_WORD_RE = re.compile(r"[a-zåäöéü0-9]+")


def primary_hex(word: str) -> str | None:
    """Return the brand-primary hex for ``word`` or ``None`` (accent-only words
    return ``None`` here - they are not safe as a primary)."""
    return PRIMARY_COLOR_HEX.get(word)


def any_color_hex(word: str) -> str | None:
    """Return the hex for any known colour word (primary or accent) or ``None``."""
    return ALL_COLOR_HEX.get(word)


def split_compound_color(
    token: str,
) -> tuple[str, str, str | None, str | None] | None:
    """Split a single compound colour token into ``(primary_hex, primary_word,
    accent_hex, accent_word)`` or return ``None``.

    A compound like ``"grönvit"`` / ``"svartvit"`` / ``"blåvit"`` is a single
    word that fuses two colours. The first colour that is primary-eligible
    becomes the primary; the other fills the accent slot (so the white in
    "grönvit" is an accent, never a near-white primary). Returns ``None`` when
    the token is not two known colours, or when neither half is a safe primary
    (e.g. "vitbeige" - two light tones - has no contrast-safe primary).

    ``accent_*`` are ``None`` when both halves resolve to the same hex, so a
    degenerate "rödröd" yields just the primary.
    """
    token = token.strip().lower()
    if len(token) < 2 * _MIN_COMPOUND_PART:
        return None
    # Longest leading colour first so multi-syllable colours win
    # ("marinblåvit" -> "marinblå" + "vit", not "marin..." nonsense).
    for split in range(len(token) - _MIN_COMPOUND_PART, _MIN_COMPOUND_PART - 1, -1):
        prefix, suffix = token[:split], token[split:]
        if prefix not in ALL_COLOR_HEX or suffix not in ALL_COLOR_HEX:
            continue
        if prefix in PRIMARY_COLOR_HEX:
            primary_word, accent_word = prefix, suffix
        elif suffix in PRIMARY_COLOR_HEX:
            primary_word, accent_word = suffix, prefix
        else:
            # Two accent-only tones -> no contrast-safe primary, skip.
            continue
        p_hex = ALL_COLOR_HEX[primary_word]
        a_hex = ALL_COLOR_HEX[accent_word]
        if a_hex == p_hex:
            return p_hex, primary_word, None, None
        return p_hex, primary_word, a_hex, accent_word
    return None


def contains_compound_color(text: str) -> bool:
    """True when ``text`` contains a compound colour token (e.g. "grönvit").

    Used by the router so a free compound colour reads as a ``visual_style``
    adjective even though neither half matches as a standalone word.
    """
    return any(
        split_compound_color(token) is not None for token in _WORD_RE.findall(text.lower())
    )
