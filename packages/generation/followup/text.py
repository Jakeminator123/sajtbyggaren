"""Shared low-level text helpers for follow-up processing.

Extracted verbatim from ``scripts/prompt_to_project_input.py`` (behavior-
preserving module extraction 2026-06-02, ADR 0034). These helpers are used by
BOTH the follow-up intent classification / semantic patch path (which stays in
``scripts.prompt_to_project_input``) AND the copyDirective subsystem
(``packages.generation.followup.copy_directives``).

Keeping them here breaks the import cycle: both ``prompt_to_project_input`` and
``copy_directives`` import from this module, and this module imports from
neither of them.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_PLANNER_NOTE_BLOCKLIST = frozenset(
    {
        "likely",
        "prompt",
        "brief",
        "planner",
        "project input",
        "phase",
        "keep scope",
        "minimal",
        "replace this",
        "site",
        "website",
        "webbplats",
        "hemsida",
        "sajt",
        "företagswebb",
        "selling",
        "focus on",
        "byt ut",
        "uppdatera",
        # B128 (re-Verifierings-Scout 2026-05-19): Swedish operator/
        # planner-lingo som lät en instruktion av typen "Bygg en liten
        # e-handel ... med fokus på köpkonvertering." passera B99-grindens
        # blocklist och landa rakt på /om-oss. "konvertering" och
        # "köpkonvertering" är operator-terminologi som småföretagskunder
        # inte använder om sig själva i kundcopy; "på svenska" / "på
        # engelska" är ren språk-direktiv från operatör till modell.
        "konvertering",
        "köpkonvertering",
        "på svenska",
        "på engelska",
        "in english",
        "in swedish",
    }
)

# B128 (re-Verifierings-Scout 2026-05-19): planner-noten startar ofta med
# en svensk/engelsk imperativ ("Bygg en liten e-handel ...", "Skapa en
# hemsida för ...", "Make a clean shop..."). Ingen riktig /om-oss-copy
# inleds med en order till modellen, så vi avvisar hela noten när första
# tokenet är en känd build-imperativ. Token-listan är medvetet tajt så
# legitima fraser som "Bygger fortfarande på 10 års erfarenhet" passerar
# - imperativen står typiskt utan utfyllnad efteråt och första bokstaven
# är ofta versal, men vi nfkc-foldar och lowercaser innan vi jämför så
# stavning inte skapar gap.
_PLANNER_IMPERATIVE_TOKENS: frozenset[str] = frozenset(
    {
        # Svensk build-imperativ
        "bygg",
        "skapa",
        "gör",
        "gor",
        "generera",
        "designa",
        "skriv",
        "tillverka",
        "konstruera",
        "producera",
        "utveckla",
        "forma",
        "programmera",
        "rita",
        # Engelsk build-imperativ
        "build",
        "create",
        "make",
        "design",
        "write",
        "develop",
        "generate",
        "construct",
        "produce",
        "draft",
    }
)

_PLANNER_IMPERATIVE_PHRASES: tuple[str, ...] = (
    "lägg upp",
    "sätt upp",
    "set up",
)


def _normalise_followup_text(text: str) -> str:
    """Collapse operator formatting before deterministic intent matching."""
    normalised = unicodedata.normalize("NFKC", text or "").lower()
    normalised = re.sub(r"[\[\]()`*_\"'“”‘’]+", " ", normalised)
    normalised = re.sub(r"\s+", " ", normalised)
    return normalised.strip()


# Quote characters an operator may wrap OLD copy in (straight + curly, single
# + double). Kept local to this shared module so ``_text_outside_quotes`` has
# no dependency on ``copy_directives`` (which imports FROM here). The
# copyDirective value extractors keep their own quote handling because they
# need the quoted spans verbatim; this constant is classification-only.
_QUOTE_CHARS = "'\"\u201c\u201d\u2018\u2019"
_PAIRED_QUOTE_RE = re.compile(rf"[{_QUOTE_CHARS}][^{_QUOTE_CHARS}]*[{_QUOTE_CHARS}]")


def _text_outside_quotes(text: str) -> str:
    """Normalised follow-up text with fully-quoted spans removed.

    A follow-up like ``ändra denna text "…exklusiv och modern känsla…" till
    "…"`` must not let the OLD copy inside the quotes drive intent/target
    keyword matching: words such as ``känsla``/``modern``/``tjänsteföretag``
    belong to the text being REPLACED, not to the operator's instruction. We
    drop every fully paired quote span first, then apply the same
    normalisation as ``_normalise_followup_text`` so callers keyword-match the
    instruction skeleton only.

    Only fully paired spans are removed; a lone stray quote leaves the rest of
    the instruction intact so a legitimate instruction is never eaten. When the
    operator quoted their ENTIRE message (nothing left outside the quotes) the
    result is empty and the caller should fall back to the full normalised
    text rather than treat the message as unclassifiable.
    """
    without_quotes = _PAIRED_QUOTE_RE.sub(" ", text or "")
    return _normalise_followup_text(without_quotes)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _contains_word(text: str, keyword: str) -> bool:
    pattern = rf"(?<![a-zåäöéü0-9]){re.escape(keyword)}(?![a-zåäöéü0-9])"
    return bool(re.search(pattern, text))


def _contains_any_word(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_contains_word(text, keyword) for keyword in keywords)


def _string_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _customer_safe_planner_note(note: str | None) -> str | None:
    """Return planner note text only when it is safe public copy.

    B128 (re-Verifierings-Scout 2026-05-19): noten avvisas också om den
    inleds med en svensk/engelsk build-imperativ (``"Bygg en liten
    e-handel ..."``, ``"Skapa en hemsida ..."``, ``"Make a clean shop
    ..."``). B99-blocklistan fokuserar på arbets-/dev-jargong och fångade
    inte rena planner-direktiv som tonade ner sig själva. En riktig
    /om-oss-copy börjar aldrig med ett verb i imperativ riktat till
    modellen, så grinden är säker att stänga.
    """
    cleaned = " ".join((note or "").split())
    if not cleaned:
        return None
    lower = cleaned.lower()
    if any(token in lower for token in _PLANNER_NOTE_BLOCKLIST):
        return None
    if _starts_with_planner_imperative(lower):
        return None
    if not cleaned.endswith((".", "!", "?")):
        cleaned = f"{cleaned}."
    return cleaned


def _starts_with_planner_imperative(lower_note: str) -> bool:
    """Return True when ``lower_note`` opens with a build-imperative.

    Called by ``_customer_safe_planner_note`` for B128. The helper takes
    the already lower-cased note (the caller has done ``.lower()`` once
    on a whitespace-collapsed string) so we can token-match without
    re-folding case here. Single-word tokens are checked with a word
    boundary so ``"byggfirma"`` does not match ``"bygg"``; multi-word
    phrases (``"lägg upp"``) are matched as prefix strings.

    B128 hardening (post-Composer-2.5-review 2026-05-19): a leading
    run of non-letter characters (markdown markers, list dashes,
    numerals, parentheses) used to bypass the guard because
    ``re.match(r"[a-zåäöéü]+", ...)`` returns ``None`` when the very
    first character is punctuation. We now strip one run of leading
    non-letter characters before the token match so a build-imperative
    sitting behind a leading dash, bold-marker or list numeral is
    blocked identically to a build-imperative at position 0. We do not
    scan further into the note (e.g. past a sentence preamble like
    "OK. Bygg ...") because that broadens the imperative surface
    enough to risk false-blocking present-tense customer copy that
    legitimately mentions a build-verb mid-sentence.
    """
    if not lower_note:
        return False
    stripped = lower_note.lstrip()
    if not stripped:
        return False
    head = re.sub(r"^[^a-zåäöéü]+", "", stripped, count=1)
    if not head:
        return False
    for phrase in _PLANNER_IMPERATIVE_PHRASES:
        if head.startswith(phrase + " ") or head == phrase:
            return True
    first_token_match = re.match(r"[a-zåäöéü]+", head)
    if first_token_match is None:
        return False
    return first_token_match.group(0) in _PLANNER_IMPERATIVE_TOKENS
