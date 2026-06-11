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

from packages.generation.followup.color_lexicon import (
    ACCENT_COLOR_HEX,
    PRIMARY_COLOR_HEX,
    split_compound_color,
)
from packages.generation.followup.text import (
    _contains_word,
    _normalise_followup_text,
)

# Natural-language colour word -> hex lives in the central colour lexicon
# (packages/generation/followup/color_lexicon.py), shared with the router so a
# new colour is understood by both the classifier and this extractor from one
# edit. PRIMARY tones are contrast-safe brand colours; ACCENT tones (white,
# cream, beige, ...) only ever fill the accent slot of a two-colour or compound
# expression - a near-white primary breaks button/CTA contrast.
_COLOR_TOKEN_RE = re.compile(r"[a-zåäöéü0-9]+")

# Literal hex tokens in the prompt ("ändra primärfärgen till #2d5f3f").
# Until 2026-06-11 a hex literal was ONLY understood via the
# styleDirectiveModel LLM fallback — the colour-tools dialog in viewser
# emits exactly this prompt shape, so without an OPENAI_API_KEY the
# dialog was a silent no-op. Deterministic now: ``#rgb``/``#rrggbb``
# tokens are extracted directly, with the nearest PRECEDING target word
# (primärfärg/accentfärg) deciding which slot the hex fills.
_HEX_LITERAL_RE = re.compile(r"#(?:[0-9a-f]{6}|[0-9a-f]{3})(?![0-9a-f])")

# Target words searched BACKWARDS from each hex literal. Substring match
# is intentional ("primärfärgen"/"accentfärgen" inflections); the two
# sets share no substring so the nearest match is unambiguous.
_PRIMARY_TARGET_WORDS: tuple[str, ...] = (
    "primärfärg",
    "primarfarg",
    "huvudfärg",
    "huvudfarg",
    "primary",
)
_ACCENT_TARGET_WORDS: tuple[str, ...] = (
    "accentfärg",
    "accentfarg",
    "accent",
)


def _expand_short_hex(token: str) -> str:
    """``#rgb`` -> ``#rrggbb`` (``#rrggbb`` passes through unchanged)."""
    if len(token) == 4:
        return "#" + "".join(channel * 2 for channel in token[1:])
    return token


def _nearest_target_before(text: str, position: int) -> str | None:
    """Return ``"primary"``/``"accent"`` for the target word closest before
    ``position``, or ``None`` when neither appears before it."""
    best_kind: str | None = None
    best_index = -1
    for word in _PRIMARY_TARGET_WORDS:
        index = text.rfind(word, 0, position)
        if index > best_index:
            best_index = index
            best_kind = "primary"
    for word in _ACCENT_TARGET_WORDS:
        index = text.rfind(word, 0, position)
        if index > best_index:
            best_index = index
            best_kind = "accent"
    return best_kind


def _resolve_hex_literals(text: str) -> tuple[str | None, str | None]:
    """Resolve ``(primary_hex, accent_hex)`` from literal hex tokens.

    Each hex is assigned by the nearest preceding target word. A hex with
    no target word defaults to the primary slot when it is still free,
    otherwise the accent slot — so "byt färg till #aabbcc" recolours the
    brand primary and "primärfärg till #x och accentfärg till #y" fills
    both. Later mentions of the same slot win (operator's last word).
    """
    primary: str | None = None
    accent: str | None = None
    for match in _HEX_LITERAL_RE.finditer(text):
        hex_value = _expand_short_hex(match.group(0))
        kind = _nearest_target_before(text, match.start())
        if kind is None:
            kind = "primary" if primary is None else "accent"
        if kind == "primary":
            primary = hex_value
        else:
            accent = hex_value
    return primary, accent


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


def _resolve_colors(
    text: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Resolve ``(primary_hex, primary_word, accent_hex, accent_word)`` from text.

    Priority:

    1. A compound colour token ("grönvit"/"svartvit"/"blåvit") splits into a
       primary + accent in one word (the white half is the accent, never a
       near-white primary).
    2. Otherwise the colour words present, in order: the first
       primary-eligible word is the primary and the next distinct colour
       (primary OR accent-only, e.g. "vit"/"white") is the accent - so
       "gör den rosa och blå" -> pink + blue and "blå och vit" -> blue + white.

    An accent-only colour on its own (a bare "vit") yields no primary - a
    near-white primary breaks contrast - so it stays an honest no-op.
    """
    # 1. compound single token wins (resolves primary + accent at once).
    for token in _COLOR_TOKEN_RE.findall(text):
        split = split_compound_color(token)
        if split is not None:
            return split

    # 2. ordered single colour words, de-duplicated by hex.
    matches: list[tuple[int, str, str, bool]] = []
    for word, hex_value in PRIMARY_COLOR_HEX.items():
        position = _color_word_position(text, word)
        if position is not None:
            matches.append((position, hex_value, word, True))
    for word, hex_value in ACCENT_COLOR_HEX.items():
        position = _color_word_position(text, word)
        if position is not None:
            matches.append((position, hex_value, word, False))
    matches.sort(key=lambda item: (item[0], -len(item[2])))
    ordered: list[tuple[str, str, bool]] = []
    seen_hex: set[str] = set()
    for _position, hex_value, word, is_primary in matches:
        if hex_value in seen_hex:
            continue
        seen_hex.add(hex_value)
        ordered.append((hex_value, word, is_primary))
    if not ordered:
        return None, None, None, None

    primary = next((item for item in ordered if item[2]), None)
    if primary is None:
        # Only accent-only tones present (e.g. a bare "vit") -> no safe primary.
        return None, None, None, None
    primary_hex, primary_word, _ = primary
    accent = next((item for item in ordered if item[0] != primary_hex), None)
    accent_hex, accent_word = (accent[0], accent[1]) if accent else (None, None)
    return primary_hex, primary_word, accent_hex, accent_word


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

    color_hex, color_word, accent_hex, accent_word = _resolve_colors(text)
    vibe, vibe_word = _match_font_vibe(text)

    # Literal hex tokens win per slot over word-resolved colours — an
    # explicit "#2d5f3f" is the operator's exact intent (the colour-tools
    # dialog emits this shape), a colour word is an approximation. The
    # matched literal is recorded as the source word for honest summaries.
    hex_primary, hex_accent = _resolve_hex_literals(text)
    if hex_primary is not None:
        color_hex, color_word = hex_primary, hex_primary
    if hex_accent is not None:
        accent_hex, accent_word = hex_accent, hex_accent

    # A bare "ändra typsnittet" (font trigger, no vibe) gets a tasteful default
    # so the request is honoured visibly instead of silently dropped.
    if vibe is None and _font_change_requested(text):
        vibe = _DEFAULT_FONT_VIBE

    # An explicit accent hex may stand alone (the operator chose the slot
    # deliberately in the colour-tools dialog); the word path still requires
    # a primary so a bare "vit" stays an honest no-op.
    if color_hex is None and accent_hex is None and vibe is None:
        return None

    return ThemeDirective(
        primaryColorHex=color_hex,
        accentColorHex=accent_hex,
        toneVibe=vibe,
        colorWord=color_word,
        accentWord=accent_word,
        vibeWord=vibe_word,
    )


# --- stylist role: model-driven fallback (parallel to the copyDirective A1) ---
# When the deterministic extractor misses a free/unknown style expression
# ("gör den i höstfärger", "samma känsla som en solnedgång"), the styleDirective
# model interprets it into the SAME structured ThemeDirective shape. Output is
# never trusted blindly: it is re-validated here exactly like a copyDirective
# candidate - hex must be a real hex, toneVibe must be a known vibe key - and an
# all-empty / invalid result is an honest no-op (None). The model never writes a
# field directly; apply_theme_directive remains the single, deterministic seam.

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# The vibe keys the deterministic extractor + _TONE_TYPOGRAPHY already
# understand. The model may only return one of these (never a free string), so a
# hallucinated vibe is dropped, not rendered.
_ALLOWED_TONE_VIBES: frozenset[str] = frozenset(_FONT_VIBE_TONE.values())


def _normalise_hex(value: Any) -> str | None:
    """Return a lower-case ``#rrggbb`` hex or ``None`` for an invalid value.

    Accepts ``#rgb`` (expanded to ``#rrggbb``) and ``#rrggbb``. This is the
    security boundary for the model path: a non-hex/garbage value never reaches
    ``brand.primaryColorHex``.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not _HEX_RE.match(candidate):
        return None
    if len(candidate) == 4:  # #rgb -> #rrggbb
        candidate = "#" + "".join(channel * 2 for channel in candidate[1:])
    return candidate


def extract_theme_directive_via_llm(
    prompt: str,
    *,
    language: str = "sv",
    focus_sections: list[dict[str, str]] | None = None,
) -> ThemeDirective | None:
    """stylist role: model-driven theme fallback for a free/unknown style request.

    Resolves the ``styleDirectiveModel`` role and asks it to interpret the
    follow-up into a structured theme mutation, then RE-VALIDATES every field:
    ``primaryColorHex``/``accentColorHex`` must be a valid hex and ``toneVibe``
    must be a known vibe key. An accent with no primary is dropped (a lone
    light accent could break contrast). An all-empty / invalid result is an
    honest no-op (``None``). Fail-safe: any resolution/call error yields
    ``None`` so a missing key never breaks the follow-up loop.

    ``focus_sections`` (ADR 0046): validated preview markings appended as a
    Swedish prioritisation note to the model context. Purely soft signal —
    the re-validation of every returned field is unchanged.
    """
    try:
        from packages.generation.brief.extract import extract_style_directive_llm
        from packages.generation.brief.models import resolve_style_directive_model
        from packages.generation.followup.marked_sections import focus_note_for_llm

        focus_note = focus_note_for_llm(focus_sections or [])
        stylist_prompt = f"{prompt}\n\n{focus_note}" if focus_note else prompt
        model = resolve_style_directive_model()
        raw = extract_style_directive_llm(
            stylist_prompt, language=language, model=model
        )
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(raw, dict):
        return None

    primary = _normalise_hex(raw.get("primaryColorHex"))
    accent = _normalise_hex(raw.get("accentColorHex"))
    raw_vibe = raw.get("toneVibe")
    vibe = raw_vibe if isinstance(raw_vibe, str) and raw_vibe in _ALLOWED_TONE_VIBES else None

    # An accent only makes sense alongside a primary; drop a lone accent.
    if primary is None and accent is not None:
        accent = None
    if primary is None and vibe is None:
        return None

    return ThemeDirective(
        primaryColorHex=primary,
        accentColorHex=accent,
        toneVibe=vibe,
        colorWord=None,
        accentWord=None,
        vibeWord=None,
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
