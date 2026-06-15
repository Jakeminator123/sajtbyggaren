"""Directive-leak signal: detect builder/instruction text that must not render.

The real ``briefModel`` occasionally files META/INSTRUCTION text into the
positioning / contentStrategy fields instead of customer-ready angle copy -
observed live on a café brief: ``localAngle`` "Göteborg som lokal förankring
bör synas tydligt i copy och kontaktsektion" and ``differentiator`` "Lyft Kafé
Solrosen som ...". ``derive_story`` / the hero composers / the FAQ would then
render that instruction verbatim as the visible "Om oss" body or hero copy.

This is the SINGLE SOURCE of the directive-leak signal, shared by two stages so
the rule can never drift between prevention and detection:

* planning (``packages/generation/planning/blueprint.py``) DROPS a
  directive-shaped string from the customer-copy candidates BEFORE render
  (prevention, #322 - the four deterministic mock baselines stay byte-identical
  because hand-authored mock positioning is honest angle copy);
* quality_gate (``packages/generation/quality_gate/critic.py``) REPORTS any
  directive text that still reached ``contentBlocks`` as a warning-lane critic
  finding (defense in depth - catches a leak the prevention missed instead of
  silently rendering it).

It only ever CLASSIFIES (never rewrites or fabricates). Deliberately
high-precision (a few unambiguous directive signals) over high-recall: a false
positive costs one candidate sentence (the story falls back to another angle or
the company name), while a false negative re-leaks the exact bug. Returns
``False`` for empty / non-string input and for ordinary customer-ready copy.

Stdlib-only (``re``) so both planning and quality_gate can import it with no
dependency cycle (``packages/shared`` is a leaf importable by both per
``governance/policies/repo-boundaries.v1.json``).
"""

from __future__ import annotations

import re
from typing import Any

# Composite craft/meta terms a genuine customer-facing sentence never uses
# about itself. Their presence means the string is talking ABOUT the page/copy
# (a builder directive), not to the visitor. Word-boundary matched. English
# mirrors ("contact section"/"hero section") are added (#322 review: English/
# mixed briefModel output can leak the same way) - kept to UNAMBIGUOUS craft
# nouns; bare "copy"/"cta"/"the hero" are deliberately excluded because they can
# appear in legitimate customer copy (precision over recall, same as the
# Swedish set).
_DIRECTIVE_CRAFT_TERM_RE = re.compile(
    r"\b(?:kontaktsektion(?:en)?|hero[-\s]?sektion(?:en)?|subheadline"
    r"|contact[-\s]?section|hero[-\s]?section)\b",
    re.IGNORECASE,
)

# Imperative directive verbs that, as the FIRST word of a positioning/story
# string, mark it as an instruction to the builder ("Lyft X som ...",
# "Framhäv ...", "Betona ..."). Only ever applied to positioning/story/FAQ
# candidates - never to conversion.primaryCta - so real CTA labels
# ("Boka tid", "Ring oss") are untouched. Imperative + the bare infinitive
# both count (a model may write "Lyfta fram ..." too).
_DIRECTIVE_LEAD_VERBS: frozenset[str] = frozenset(
    {
        "lyft", "lyfta",
        "framhäv", "framhäva", "framhav", "framhava",
        "betona",
        "understryk", "understryka",
        "poängtera", "poangtera",
        "spegla",
        "signalera",
        "förmedla", "formedla",
        "kommunicera",
        "undvik", "undvika",
        "säkerställ", "säkerställa", "sakerstall", "sakerstalla",
        "tydliggör", "tydliggor",
        "prioritera",
    }
)

_LEAD_TOKEN_RE = re.compile(r"[a-zåäöA-ZÅÄÖ]+")

# "<modal> ... <craft-verb>" inside ONE sentence is a directive ABOUT the copy
# ("Göteborg ... bör synas tydligt i copy"). The modal alone is NOT enough -
# the mock oneLiner "...när elen måste bli rätt" must stay - so a copy-craft
# verb has to follow within the same sentence (no .!? in between).
_DIRECTIVE_MODAL_CRAFT_RE = re.compile(
    r"\b(?:b[öo]r|ska|m[åa]ste|beh[öo]ver)\b[^.!?]*?\b(?:"
    r"synas|syns|lyftas|framh[äa]vas|betonas|speglas|[åa]terspeglas|"
    r"kommuniceras|genomsyra(?:s)?|po[äa]ngteras|understrykas|framg[åa]"
    r")\b",
    re.IGNORECASE,
)


def _starts_with_directive_verb(text: str) -> bool:
    """True when the first word is an imperative copy-direction verb."""
    match = _LEAD_TOKEN_RE.match(text)
    if match is None:
        return False
    return match.group(0).casefold() in _DIRECTIVE_LEAD_VERBS


def looks_like_directive(text: Any) -> bool:
    """True when a positioning/strategy/copy string reads as a builder directive.

    Detects three high-precision signals seen in real briefModel leaks:

    * a composite craft/meta term ("kontaktsektion", "hero-sektion",
      "subheadline") a customer sentence never uses about itself;
    * an imperative copy-direction lead verb ("Lyft ...", "Framhäv ...");
    * a "<modal> ... <copy-craft verb>" construction ("... bör synas tydligt
      i copy").

    Returns ``False`` for empty / non-string input and for ordinary
    customer-ready copy (including every deterministic mock positioning value),
    so applying it is a no-op on the honest baseline path.
    """
    if not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if _DIRECTIVE_CRAFT_TERM_RE.search(stripped):
        return True
    if _starts_with_directive_verb(stripped):
        return True
    return bool(_DIRECTIVE_MODAL_CRAFT_RE.search(stripped))


__all__ = ["looks_like_directive"]
