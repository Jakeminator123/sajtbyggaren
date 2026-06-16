"""copyDirective subsystem (ADR 0034 väg A, nivå 1-3a).

Extracted verbatim from ``scripts/prompt_to_project_input.py`` (behavior-
preserving module extraction 2026-06-02). This is the deterministic extractor +
copyDirectiveModel extraction + editPlan planner + validation + grounding guard
+ apply chain for the follow-up copyDirectives passthrough.

Import discipline (cycle break): this module must NOT import from
``scripts.prompt_to_project_input``. Shared low-level text helpers come from
``packages.generation.followup.text``; the ``copyDirectiveModel`` resolver from
``packages.generation.brief.models``; and the LLM extract/plan plumbing is
imported lazily from ``packages.generation.brief.extract`` exactly as before
(``extract_copy_directives_llm`` / ``plan_copy_directives_llm`` stay in that
module). The follow-up orchestration (``merge_followup_project_input``) and the
intent-coupled ``_copy_directive_llm_eligible`` stay in
``scripts.prompt_to_project_input``.
"""

from __future__ import annotations

import re
from typing import Any

from packages.generation.brief.models import resolve_copy_directive_model
from packages.generation.followup.text import (
    _contains_any,
    _contains_any_word,
    _customer_safe_planner_note,
    _normalise_followup_text,
    _string_value,
    _text_outside_quotes,
)

_COPY_DIRECTIVE_TAGLINE_KEYWORDS: tuple[str, ...] = (
    "tagline",
    "taglinen",
    "slogan",
    "sloganen",
    "underrubrik",
    "underrubriken",
    "undertext",
    "undertexten",
    "hero-text",
    "hero text",
    "herotext",
    "subtitle",
    "subheading",
)
# "rubrik"/"huvudrubrik" mean the hero H1, not the company name. An operator who
# says "byt rubriken på startsidan till X" wants the hero heading, not a company
# rename (the brand sits in the nav header + hero brand line, addressed by the
# explicit "företagsnamn"/"header"/"heter"/"rename" keywords). These are matched
# on WORD boundaries (not substring) so a compound like "rubriktext" inside a
# vibe-rewrite ("skriv om rubriktexten så den välkomnar") does NOT become a
# literal tagline replace - it stays an honest no-op surfaced via
# unappliedFollowupIntents. Fixes the 2026-06-08 demo where "byt rubriken"
# renamed the company instead of editing the hero heading.
_COPY_DIRECTIVE_HEADING_KEYWORDS: tuple[str, ...] = (
    "rubrik",
    "rubriken",
    "huvudrubrik",
    "huvudrubriken",
)
_COPY_DIRECTIVE_NAME_KEYWORDS: tuple[str, ...] = (
    "företagsnamn",
    "foretagsnamn",
    "företagsnamnet",
    "foretagsnamnet",
    "namnet",
    "namn",
    "heter",
    "kallas",
    "döp om",
    "dop om",
    "döpa om",
    "dopa om",
    "header",
    "headern",
    "titeln",
    "company name",
    "business name",
    "rename",
)
_COPY_DIRECTIVE_HERO_KEYWORDS: tuple[str, ...] = ("hero",)
# About / "om oss" scope (slice 2a, ADR 0034 väg A nivå 2): these signal that
# the operator wants to change the company STORY (company.story, rendered as
# the about/"om oss" copy), not the name or tagline. Kept specific on purpose -
# a bare "text"/"texten" is NOT here, so an ambiguous "ändra texten till X"
# stays an honest no-op rather than hijacking the about section.
_COPY_DIRECTIVE_ABOUT_KEYWORDS: tuple[str, ...] = (
    "om oss",
    "om-oss",
    "omoss",
    "om foretaget",
    "om företaget",
    "om verksamheten",
    "berättelse",
    "berattelse",
    "berättelsen",
    "berattelsen",
    "historia",
    "historien",
    "vår historia",
    "var historia",
    "story",
    "storyn",
    "about",
    "about us",
    "our story",
)
# about / story copy is longer free text than a name or a tagline; the schema
# payload cap is raised to match (still validated through the same public-copy
# guards). Name stays capped at 80 and tagline at 140 in code.
_COPY_DIRECTIVE_ABOUT_MAX_LENGTH = 600
# Services scope (slice 2c, ADR 0034 väg A nivå 2): these signal that the
# operator wants to change a specific service's summary (services[].summary).
# Which service is resolved separately (targetRef -> matched against existing
# services by id/label); no match is an honest no-op. Service summaries are
# short, so the code cap is tighter than the about cap.
_COPY_DIRECTIVE_SERVICES_KEYWORDS: tuple[str, ...] = (
    "tjänst",
    "tjänsten",
    "tjänster",
    "tjänsterna",
    "tjänstbeskrivning",
    "tjänstbeskrivningen",
    "tjänsttext",
    "tjänstetext",
    "service description",
    "services description",
    "service",
    "services",
)
_COPY_DIRECTIVE_SERVICES_MAX_LENGTH = 300
# Additive "add a new service" phrasings. A services copyDirective only ever
# REPLACES an existing service summary; creating a service is the semantic
# service merge's job, so these phrasings force an honest no-op even when a
# replace verb is also present ("uppdatera ... och lägg till ny tjänst").
_COPY_DIRECTIVE_NEW_SERVICE_GUARD: tuple[str, ...] = (
    "ny tjänst",
    "ny tjanst",
    "nya tjänster",
    "nya tjanster",
    "new service",
    "new services",
)
# Rewrite/improve verbs that mark a *content rewrite request* (slice 3a): the
# operator wants existing copy rewritten without supplying the literal text.
# These trigger the editPlan planner (LLM generation) for about-text/services
# only. Deliberately narrower than the full replace-verb set - plain
# byt/ändra/uppdatera (rename-style) are NOT here so they cannot pull a vibe
# prompt into the generation path.
_COPY_CONTENT_REWRITE_VERBS: tuple[str, ...] = (
    "skriv om",
    "formulera om",
    "omformulera",
    "förbättra",
    "forbattra",
    "snygga till",
    "rewrite",
    "reword",
    "improve",
)
# Multi-digit number tokens used by the planner hallucination guard: a generated
# payload must not introduce a number (founding year, price, count, percentage)
# that is absent from the current site-state and the follow-up prompt. Matches a
# whole run of >= 2 digits (single digits are too noisy to guard) with an
# optional decimal part, so "1962", "499", "100", "12,5" are each checked as a
# whole token rather than as substrings of a longer number.
_PLANNED_NUMBER_RE = re.compile(r"(?<!\d)\d{2,}(?:[.,]\d+)?(?!\d)")
_COPY_DIRECTIVE_INCLUDE_KEYWORDS: tuple[str, ...] = (
    "inkludera",
    "inkluderar",
    "lägg in",
    "lagg in",
    "lägg till",
    "lagg till",
    "ha med",
    "infoga",
    "include",
    "add",
)
_COPY_DIRECTIVE_REPLACE_KEYWORDS: tuple[str, ...] = (
    "byt",
    "byta",
    "ändra",
    "andra",
    "gör om",
    "gor om",
    "göra om",
    "gora om",
    "döp om",
    "dop om",
    "sätt",
    "satt",
    "uppdatera",
    "ersätt",
    "ersatt",
    "kalla",
    "rename",
    "change",
    "replace",
    "set",
    "update",
    "skriv om",
    "formulera om",
    "omformulera",
    "rewrite",
    "reword",
)
# Media nouns that mark a follow-up as an ASSET change, not a copy edit
# (bildbyte-guard, 2026-06-11). The operator prompt "Byt ut hero-bilden till
# en unsplash bild" used to be classified as a text replace and spliced
# "en unsplash bild" into public copy. Free-text image/video changes have no
# deterministic consumer yet (asset_set-konsumenten is the structured path),
# so a prompt that mentions one of these as a WORD outside quoted spans must
# stay an honest no-op in the copyDirective subsystem - surfaced via
# unappliedFollowupIntents instead of mangling copy. Matched with
# ``_contains_any_word`` on ``_text_outside_quotes``: a quoted payload like
# 'ändra taglinen till "En bild säger mer än tusen ord"' is untouched.
# Swedish closed compounds ("bakgrundsbilden") do not hit the word boundary
# of the bare stem, so the common -bild compounds are listed explicitly;
# hyphenated forms ("hero-bilden") already match via the boundary at "-".
_MEDIA_CHANGE_NOUNS: tuple[str, ...] = (
    "bild",
    "bilden",
    "bilder",
    "bilderna",
    "bakgrundsbild",
    "bakgrundsbilden",
    "herobild",
    "herobilden",
    "omslagsbild",
    "omslagsbilden",
    "profilbild",
    "profilbilden",
    "produktbild",
    "produktbilden",
    "produktbilder",
    "produktbilderna",
    "galleribild",
    "galleribilden",
    "galleribilder",
    "galleribilderna",
    "foto",
    "fotot",
    "foton",
    "fotona",
    "fotografi",
    "fotografiet",
    "fotografier",
    "fotografierna",
    "logga",
    "loggan",
    "logotyp",
    "logotypen",
    "film",
    "filmen",
    "filmer",
    "filmerna",
    "video",
    "videon",
    "videor",
    "videos",
    "unsplash",
    "image",
    "images",
    "photo",
    "photos",
    "picture",
    "pictures",
    "logo",
)
# Explicit TEXT nouns that exempt a prompt from the media guard: "byt
# rubriken under bilden till 'X'" names a copy target and merely uses the
# image as a LOCATION, so the copy rules must still run. Deliberately
# narrow - "hero" is NOT here because it word-matches inside "hero-bilden"
# (the original bug prompt) and would reopen the splice. Closed compounds
# like "bildtexten" (caption) never trigger the media nouns in the first
# place (no word boundary inside a compound), so captions are edit-safe
# without an entry here.
_MEDIA_GUARD_TEXT_NOUNS: tuple[str, ...] = (
    "text",
    "texten",
    "texter",
    "texterna",
    "rubrik",
    "rubriken",
    "huvudrubrik",
    "huvudrubriken",
    "underrubrik",
    "underrubriken",
    "tagline",
    "taglinen",
    "slogan",
    "sloganen",
    "namnet",
    "företagsnamn",
    "foretagsnamn",
    "företagsnamnet",
    "foretagsnamnet",
    "heading",
    "headline",
    "title",
)
# If the extracted payload still contains one of these as a WORD the
# extraction grabbed instruction text, not a value - reject it (leak guard).
# Matched with word/phrase boundaries (``_contains_any_word``), not substring:
# a legitimate company name like "Changemakers" merely *contains* "change" but
# is not an instruction, so substring matching wrongly no-op:ed it (Codex-fynd
# 2026-06-01). Swedish change-verbs carry their common inflections (``ändrar``/
# ``byter``) so the inflected instruction forms are still caught as words.
_COPY_DIRECTIVE_REJECT_WORDS: tuple[str, ...] = (
    "byt",
    "byta",
    "byter",
    "bytte",
    "byt ut",
    "ändra",
    "ändrar",
    "ändrade",
    "ändrat",
    "andra",
    "andrar",
    "andrade",
    "andrat",
    "gör om",
    "gor om",
    "inkludera",
    "inkluderar",
    "lägg",
    "lagg",
    "uppdatera",
    "uppdaterar",
    "ersätt",
    "ersätter",
    "ersatt",
    "ersatter",
    "change",
    "changes",
    "replace",
    "replaces",
    "include",
    "includes",
    "rename",
    "renames",
)
# Name keywords that *explicitly* mean the company name (header/title/rename
# idioms). A generic "namn"/"namnet" is NOT in here: on its own it is
# ambiguous and must not hijack ``company.name`` when the operator scoped the
# rename to a service/product/page (Codex-fynd 2026-06-01).
_COPY_DIRECTIVE_EXPLICIT_NAME_KEYWORDS: tuple[str, ...] = (
    "företagsnamn",
    "foretagsnamn",
    "företagsnamnet",
    "foretagsnamnet",
    "heter",
    "kallas",
    "döp om",
    "dop om",
    "döpa om",
    "dopa om",
    "header",
    "headern",
    "titeln",
    "company name",
    "business name",
    "rename",
)
# Scope words that mean the operator is renaming a service/product/page, not
# the company. When one of these is present and no explicit company-name
# keyword is, a generic "namn/namnet" must NOT map to ``company-name``.
_COPY_DIRECTIVE_NONCOMPANY_SCOPE_KEYWORDS: tuple[str, ...] = (
    "tjänst",
    "tjänsten",
    "tjänster",
    "tjänsterna",
    "produkt",
    "produkten",
    "produkter",
    "produkterna",
    "sida",
    "sidan",
    "sidor",
    "sidorna",
    "service",
    "services",
    "product",
    "products",
    "page",
    "pages",
)
# Lead words that mark an UNQUOTED trailing ``till``/``to`` value as an
# instruction (a desired quality/state) rather than literal new copy:
# "change the hero to be more premium" must not publish "be more premium" as a
# tagline (Codex-fynd 2026-06-01). Operators who want such words as literal
# copy can quote them - the quoted branch is respected verbatim.
_TRAILING_INSTRUCTION_LEADS: tuple[str, ...] = (
    "att ",
    "be ",
    "become ",
    "look ",
    "feel ",
    "seem ",
    "appear ",
    "sound ",
    "make ",
    "get ",
    "stay ",
    "have ",
    "vara ",
    "bli ",
    "kännas ",
    "verka ",
    "se ut",
)
_COPY_TITLE_CASE_SKIP: frozenset[str] = frozenset(
    {"och", "i", "på", "pa", "av", "för", "for", "the", "of", "and", "a", "an", "&"}
)
_QUOTE_CHARS = "'\"\u201c\u201d\u2018\u2019"
_TILL_VALUE_QUOTED_RE = re.compile(
    rf"(?:\btill\b|\bto\b)\s+[{_QUOTE_CHARS}]([^{_QUOTE_CHARS}]+)[{_QUOTE_CHARS}]",
    re.IGNORECASE,
)
_TILL_VALUE_COLON_RE = re.compile(
    r"(?:\btill\b|\bto\b)\s*[:：]\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_TILL_VALUE_TRAILING_RE = re.compile(
    r"(?:\btill\b|\bto\b)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_QUOTED_SPAN_RE = re.compile(rf"[{_QUOTE_CHARS}]([^{_QUOTE_CHARS}]+)[{_QUOTE_CHARS}]")

# "instead of"-style replace markers. A natural rephrasing like
# "gör herotexten 'X' istället för 'Y'" carries the NEW value as the quoted
# span BEFORE the marker (the OLD value follows it and is ignored). This is a
# replace intent even without a "byt/ändra ... till" pattern, so the gate +
# value extractors treat the marker like a "till" value marker.
_REPLACE_MARKERS: tuple[str, ...] = (
    "istället för",
    "i stället för",
    "istallet for",
    "i stallet for",
    "instead of",
)

# Section-add intent: a "ny ... sektion"/"new ... section" phrasing (the
# section_builder's additive ask). Matched on the instruction skeleton (quoted
# OLD/NEW copy removed) so a quoted value that merely mentions "ny sektion"
# (e.g. ``ändra rubriken till "Ny sektion om oss"``) is NOT mistaken for a
# section add. ``[^.!?]*`` keeps the match inside one sentence; ``avsnitt`` is
# the common Swedish synonym for "section".
_SECTION_ADD_INTENT_RE = re.compile(
    r"\bny(?:tt|a)?\b[^.!?]*\b(?:sektion|sektionen|sektioner|avsnitt|section|sections)\b"
)


def _title_case_company_name(value: str) -> str:
    """Capitalise an all-lowercase company name without mangling intended case.

    Only called when the operator typed an all-lowercase payload (e.g.
    "jakobs örhängen" -> "Jakobs Örhängen"). Words that already carry an
    uppercase letter (``iPhone``, ``AB``) are preserved verbatim, and small
    Swedish/English connector words stay lowercase unless first.
    """
    words = value.split()
    out: list[str] = []
    for idx, word in enumerate(words):
        if any(ch.isupper() for ch in word):
            out.append(word)
        elif idx != 0 and word.lower() in _COPY_TITLE_CASE_SKIP:
            out.append(word.lower())
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def _safe_copy_payload(
    value: Any,
    *,
    follow_up_prompt: str,
    max_length: int,
) -> str | None:
    """Validate a candidate copy payload through the public-copy guards.

    Returns ``None`` when the candidate is empty, looks like the raw
    instruction, still contains a change-verb (extraction grabbed too much)
    or trips the existing B99/B128 planner-note blocklist. This is the single
    choke point that keeps the operator's instruction text from ever becoming
    customer copy.
    """
    cleaned = _string_value(value)
    if not cleaned:
        return None
    cleaned = cleaned.strip().strip(_QUOTE_CHARS).strip()
    cleaned = cleaned.strip(".:,;!? ").strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if _contains_any_word(lowered, _COPY_DIRECTIVE_REJECT_WORDS):
        return None
    safe = _customer_safe_planner_note(cleaned)
    if not safe:
        return None
    safe = safe.removesuffix(".").strip()
    if not safe:
        return None
    # A normal extracted value IS a substring of the prompt, so the usual
    # "is a substring of" leak check (_looks_like_raw_followup_prompt) would
    # reject everything. Reject only when the candidate is essentially the
    # entire instruction (extraction failed to narrow it down).
    if _normalise_followup_text(safe) == _normalise_followup_text(follow_up_prompt):
        return None
    return safe[:max_length].strip() or None


def is_media_change_request(follow_up_prompt: str) -> bool:
    """True when the follow-up is about images/photos/video/logo, not copy.

    The bildbyte-guard (2026-06-11): evaluated on the instruction skeleton
    OUTSIDE quoted spans so media words inside a quoted NEW/OLD value never
    trigger it. Used to (a) bail out of ``_extract_copy_directives`` before
    the replace/include rules can splice an asset request into public copy,
    (b) block the copyDirectiveModel fallback for the same prompts, and
    (c) drive the unappliedFollowupIntents honesty report. Pure read - it
    never classifies what the asset change IS (that is the structured
    asset_set path's job).
    """
    skeleton = _text_outside_quotes(follow_up_prompt)
    if not skeleton:
        return False
    if not _contains_any_word(skeleton, _MEDIA_CHANGE_NOUNS):
        return False
    # An explicit text noun outside quotes means the operator named a COPY
    # target and the media word is location/context ("byt rubriken under
    # bilden till 'Ny rubrik'") - let the copy rules run.
    return not _contains_any_word(skeleton, _MEDIA_GUARD_TEXT_NOUNS)


# Page-add cues (route_add): an add/create/new verb paired with a page noun.
# Mirrors classify_message's route_add signal set (packages/generation/
# orchestration/router/classify.py: _ADD_VERBS/_CREATE_VERBS/_NEW_PAGE_CUES +
# _PAGE_NOUNS) but is kept self-contained here so the followup layer never has
# to import from the orchestration/router layer. The page nouns list the
# "-sida"/"-sidan" compounds explicitly because word-boundary matching means a
# bare "sida" never matches inside "kontaktsida".
_PAGE_ADD_VERB_CUES: tuple[str, ...] = (
    "lägg till", "lagg till", "lägg in", "lagg in", "lägga till", "lagga till",
    "skapa", "skapar", "bygg", "bygga", "ny", "nytt", "ytterligare", "extra",
    "add", "create", "new",
)
_PAGE_ADD_PAGE_NOUNS: tuple[str, ...] = (
    "undersida", "undersidor", "kontaktsida", "kontaktsidan", "landningssida",
    "tjänstesida", "tjanstesida", "prissida", "webbsida", "sida", "sidan",
    "sidor", "page", "pages",
)


def is_page_add_request(follow_up_prompt: str) -> bool:
    """True when the follow-up asks to ADD A PAGE ("lägg till en sida [som heter X]").

    A page-add's trailing "...som heter X" names the NEW PAGE, not the company,
    so the copy extractor must never steal that quoted name as a company rename
    (the 2026-06-16 "Jakobs sida" honesty bug). The router classifies these as
    ``route_add`` - an editKind with no executor yet (ADR 0062 §4), so the honest
    outcome is a no-op, never a silent company-name change.

    Evaluated on the instruction skeleton OUTSIDE quoted spans (same guard shape
    as ``is_media_change_request``) so a company literally named "Lägg till en
    sida AB" inside quotes never trips it. Requires BOTH an add/create/new verb
    and a page noun, mirroring ``classify_message``'s route_add cue set.
    """
    skeleton = _text_outside_quotes(follow_up_prompt)
    if not skeleton:
        return False
    if not _contains_any_word(skeleton, _PAGE_ADD_PAGE_NOUNS):
        return False
    return _contains_any_word(skeleton, _PAGE_ADD_VERB_CUES)


def _classify_copy_target(text_norm: str) -> str | None:
    """Decide which structured field a copy directive targets.

    ``text_norm`` is the output of ``_normalise_followup_text`` (lower-case,
    quotes stripped). Tagline-specific signals win over the generic name
    signals; a bare ``hero`` mention maps to the hero tagline.
    """
    if _contains_any(text_norm, _COPY_DIRECTIVE_TAGLINE_KEYWORDS):
        return "tagline"
    # A standalone "rubrik"/"huvudrubrik" (hero H1) maps to the tagline. Matched
    # on word boundaries so the compound "rubriktext" does not trigger a literal
    # replace (that stays an honest no-op). Placed right after the explicit
    # tagline keywords and before the name branch so a heading rename never
    # hijacks company.name (2026-06-08 demo fix).
    if _contains_any_word(text_norm, _COPY_DIRECTIVE_HEADING_KEYWORDS):
        return "tagline"
    # about / "om oss" scope wins over the generic name signals so a follow-up
    # like "ändra om-oss-texten till '...'" edits company.story, not the name.
    if _contains_any(text_norm, _COPY_DIRECTIVE_ABOUT_KEYWORDS):
        return "about-text"
    # services scope (slice 2c) edits a specific service summary. It must NOT
    # fire when the operator used an explicit company-name keyword
    # ("ändra företagsnamnet (inte tjänsten) till X" is a company rename). The
    # actual service is resolved via targetRef at extract/apply time; an
    # unnamed or unknown service is an honest no-op. Placed before the generic
    # name branch so "byt namnet på tjänsten till X" is service-scoped, not a
    # company rename.
    # Services keywords are matched on WORD boundaries (not substring) so a
    # compound noun like "tjänsteföretag" inside the operator's prompt (or
    # inside quoted OLD copy) does NOT misroute a generic edit to a services
    # no-op. "ändra tjänsten till X" still matches ("tjänsten" is a whole
    # word); "tjänsteföretag" does not. ``_contains_any_word`` handles the
    # multi-word phrases ("service description") too - the boundary anchors
    # wrap the whole phrase. Fixes the 2026-06-09 lask-ab misroute.
    if _contains_any_word(
        text_norm, _COPY_DIRECTIVE_SERVICES_KEYWORDS
    ) and not _contains_any_word(text_norm, _COPY_DIRECTIVE_EXPLICIT_NAME_KEYWORDS):
        return "services"
    if _contains_any_word(text_norm, _COPY_DIRECTIVE_NAME_KEYWORDS):
        # A generic "namn/namnet" must not hijack company.name when the
        # operator scoped the rename to a service/product/page (Codex-fynd
        # 2026-06-01): "byt namnet på tjänsten till X" renames a service, not
        # the company. An explicit company-name keyword (företagsnamn,
        # header, rename, ...) still wins over the scope words.
        has_explicit_name = _contains_any_word(
            text_norm, _COPY_DIRECTIVE_EXPLICIT_NAME_KEYWORDS
        )
        has_noncompany_scope = _contains_any_word(
            text_norm, _COPY_DIRECTIVE_NONCOMPANY_SCOPE_KEYWORDS
        )
        if has_noncompany_scope and not has_explicit_name:
            return None
        return "company-name"
    if _contains_any_word(text_norm, _COPY_DIRECTIVE_HERO_KEYWORDS):
        return "tagline"
    return None


def _looks_like_trailing_instruction(value: str) -> bool:
    """True when an UNQUOTED trailing ``till``/``to`` value reads as instruction.

    The bare ``<...> till/to <rest>`` branch is the most permissive value
    extractor. A phrasing like "change the hero to be more premium" should
    shift tone, not publish the literal words "be more premium" as a tagline.
    We reject the capture when it opens with an infinitive / quality
    construction (Codex-fynd 2026-06-01).
    """
    head = _normalise_followup_text(value)
    if not head:
        return False
    return any(
        head == lead.strip() or head.startswith(lead)
        for lead in _TRAILING_INSTRUCTION_LEADS
    )


def _value_before_replace_marker(follow_up_prompt: str) -> str | None:
    """New value from a ``"NEW" istället för "OLD"`` phrasing.

    Returns the quoted span immediately before an ``istället för``/``instead
    of`` marker (the operator's NEW value); the text after the marker is the
    OLD value and is ignored. Returns ``None`` when no marker is present or no
    quoted span precedes it, so a bare/unquoted ``istället för`` stays an
    honest no-op (we never guess the new value). 2026-06-08 phrasing slice.
    """
    lowered = follow_up_prompt.lower()
    positions = [pos for pos in (lowered.find(m) for m in _REPLACE_MARKERS) if pos != -1]
    if not positions:
        return None
    head = follow_up_prompt[: min(positions)]
    matches = list(_QUOTED_SPAN_RE.finditer(head))
    return matches[-1].group(1) if matches else None


def _extract_replace_value(follow_up_prompt: str) -> str | None:
    """Pull the new value after a ``till``/``to`` marker (colon, quoted, trailing).

    Also handles the ``"NEW" istället för "OLD"`` phrasing (the new value is the
    quoted span before the marker) so a natural rephrasing lands the same edit.
    """
    marker_value = _value_before_replace_marker(follow_up_prompt)
    if marker_value is not None:
        return marker_value
    colon = _TILL_VALUE_COLON_RE.search(follow_up_prompt.strip())
    if colon:
        return colon.group(1)
    quoted = _TILL_VALUE_QUOTED_RE.search(follow_up_prompt)
    if quoted:
        return quoted.group(1)
    trailing = _TILL_VALUE_TRAILING_RE.search(follow_up_prompt)
    if trailing:
        # Only the unquoted trailing branch needs the instruction guard; the
        # colon/quoted branches are explicit operator intent and respected.
        value = trailing.group(1)
        if _looks_like_trailing_instruction(value):
            return None
        return value
    return None


def _extract_explicit_replace_value(follow_up_prompt: str) -> str | None:
    """Strict new value: only quoted or colon, NOT a bare trailing ``till <rest>``.

    Used for about-text and services (paragraph-style copy) where a bare
    trailing value like "till mer personligt" is almost always a vibe
    instruction, not literal copy - forcing a quote/colon keeps an instruction
    from being published as customer copy and lets the editPlan planner handle
    the rewrite instead (reviewer-fynd 2026-06-02). company-name/tagline keep
    the looser ``_extract_replace_value`` because short labels are commonly
    given unquoted ("byt namnet till Volvo").

    Also accepts the quoted ``"NEW" istället för "OLD"`` phrasing (the new value
    is the quoted span before the marker), matching ``_extract_replace_value``.
    """
    marker_value = _value_before_replace_marker(follow_up_prompt)
    if marker_value is not None:
        return marker_value
    colon = _TILL_VALUE_COLON_RE.search(follow_up_prompt.strip())
    if colon:
        return colon.group(1)
    quoted = _TILL_VALUE_QUOTED_RE.search(follow_up_prompt)
    if quoted:
        return quoted.group(1)
    return None


# --- services target ref (slice 2c) -----------------------------------------
# The operator must name WHICH service to edit. We capture the reference (a
# service label or id) either quoted right after a service anchor word
# ("tjänsten 'Klippning'") or unquoted between the anchor and the value marker
# ("tjänsten Klippning till '...'"). The reference is never rendered - it is
# only matched against the existing services list at apply time, so a fuzzy or
# wrong reference is an honest no-op, never a hijack of another service.
_SERVICE_ANCHOR = (
    r"(?:\btjänsterna\b|\btjänsten\b|\btjänster\b|\btjänst\b"
    r"|\bservices\b|\bservicen\b|\bservice\b)"
)
_SERVICE_REF_QUOTED_RE = re.compile(
    rf"{_SERVICE_ANCHOR}\s+[{_QUOTE_CHARS}]([^{_QUOTE_CHARS}]+)[{_QUOTE_CHARS}]",
    re.IGNORECASE,
)
_SERVICE_REF_UNQUOTED_RE = re.compile(
    rf"{_SERVICE_ANCHOR}\s+([^{_QUOTE_CHARS}:]+?)\s+(?:\btill\b|\bto\b)",
    re.IGNORECASE,
)


def _extract_service_target_ref(follow_up_prompt: str) -> str | None:
    """Pull the service the operator scoped a services edit to (label or id).

    Prefers a quoted reference right after a service anchor word; falls back to
    an unquoted reference between the anchor and the ``till``/``to`` value
    marker. Returns ``None`` when no specific service is named, so a generic
    "ändra tjänsten till X" stays an honest no-op (we never guess which
    service). Capped at 80 chars to match the schema targetRef bound.
    """
    match = _SERVICE_REF_QUOTED_RE.search(follow_up_prompt)
    if not match:
        match = _SERVICE_REF_UNQUOTED_RE.search(follow_up_prompt)
    if not match:
        return None
    ref = match.group(1).strip().strip(_QUOTE_CHARS).strip()
    ref = ref.strip(".:,;!? ").strip()
    if not ref:
        return None
    return ref[:80]


def _match_service_by_ref(services: Any, target_ref: str) -> dict[str, Any] | None:
    """Find the service whose id or label matches ``target_ref`` (normalised).

    Returns ``None`` when there is no exact normalised match, so an unknown
    reference never creates a phantom service or hijacks an unrelated one.
    """
    if not isinstance(services, list):
        return None
    ref = _normalise_followup_text(target_ref)
    if not ref:
        return None
    for service in services:
        if not isinstance(service, dict):
            continue
        for key in ("id", "label"):
            value = service.get(key)
            if isinstance(value, str) and _normalise_followup_text(value) == ref:
                return service
    return None


# Token-like words for the UNQUOTED include path: a string with at least one
# uppercase letter or a digit (e.g. ``TEST-JAKOB`` or a campaign code) reads as
# a deliberate token; a plain lowercase word ("mer", "text") does not.
# Keyword/target words are excluded so "inkludera X i hero" never returns
# "hero" as the token.
_UNQUOTED_INCLUDE_TOKEN_RE = re.compile(r"[A-Za-zÅÄÖåäö0-9][A-Za-zÅÄÖåäö0-9-]*")
_COPY_DIRECTIVE_TOKEN_STOPWORDS: frozenset[str] = frozenset(
    word.strip().lower()
    for group in (
        _COPY_DIRECTIVE_TAGLINE_KEYWORDS,
        _COPY_DIRECTIVE_HEADING_KEYWORDS,
        _COPY_DIRECTIVE_NAME_KEYWORDS,
        _COPY_DIRECTIVE_HERO_KEYWORDS,
        _COPY_DIRECTIVE_INCLUDE_KEYWORDS,
        _COPY_DIRECTIVE_REPLACE_KEYWORDS,
    )
    for word in group
)


def _first_unquoted_include_token(text: str) -> str | None:
    """Return the first token-like word in ``text`` or ``None``.

    Token-like = contains an uppercase letter or a digit and is not a
    copy-directive keyword/target word. This keeps a natural unquoted prompt
    like "inkludera TEST-JAKOB i hero" working while a vague "inkludera mer
    text" stays an honest no-op rather than grabbing a stray word.
    """
    for candidate in _UNQUOTED_INCLUDE_TOKEN_RE.findall(text):
        token = candidate.strip("-")
        if len(token) < 2:
            continue
        if not any(ch.isupper() or ch.isdigit() for ch in token):
            continue
        if token.lower() in _COPY_DIRECTIVE_TOKEN_STOPWORDS:
            continue
        return token
    return None


def _extract_include_token(follow_up_prompt: str) -> str | None:
    """Pull a token to include, preferring a quoted span after an include keyword.

    Falls back to an UNQUOTED token-like word after the include keyword
    (B-Codex 2026-06-01): "inkludera TEST-JAKOB i hero" without quotes is the
    natural way operators phrase the ADR 0034 acceptance case, and used to be a
    silent no-op because only quoted spans were extracted.
    """
    lowered = follow_up_prompt.lower()
    for keyword in _COPY_DIRECTIVE_INCLUDE_KEYWORDS:
        position = lowered.find(keyword.strip())
        if position == -1:
            continue
        after = follow_up_prompt[position + len(keyword.strip()) :]
        match = _QUOTED_SPAN_RE.search(after)
        if match:
            return match.group(1)
        token = _first_unquoted_include_token(after)
        if token:
            return token
    match = _QUOTED_SPAN_RE.search(follow_up_prompt)
    return match.group(1) if match else None


# --- literal find-and-replace (ADR 0034 vag A, literal slice) ----------------
# "andra denna text \"X\" till \"Y\"" is the simplest follow-up an operator can
# write: quote the visible OLD text X and give the NEW value Y. The classifier
# has no stable target keyword for a bare "denna text", so this path locates X
# in the CURRENT copy fields (tagline / heroHeadline / story / services[].
# summary) and replaces it verbatim. No field matches X -> honest no-op (we
# never guess a target or fabricate copy). The rendered hero H1 is regenerated
# from the blueprint, so an operator who quotes the big hero line (which is not
# a stored field) correctly gets an honest no-op surfaced via
# appliedVisibleEffect rather than a silent paraphrase (2026-06-09 lask-ab).
_LITERAL_TEXT_ANCHOR_KEYWORDS: tuple[str, ...] = (
    "denna text",
    "den har texten",
    "den här texten",
    "texten",
    "text",
    "this text",
    "the text",
)

# DEMONSTRATIVE text anchors: an operator pointing at a specific visible string
# they want swapped ("denna text: X ska bli Y"). Strictly narrower than
# _LITERAL_TEXT_ANCHOR_KEYWORDS (which includes a bare "text"/"texten"): only
# these explicit demonstratives engage the anchor-led UNQUOTED replace (B178)
# and the honest-effect signal, so a style ("sajten ska bli mörkblå") or section
# ("lägg till en sektion") follow-up - which carries no demonstrative anchor -
# is never mis-read as a copy-replace.
_DEMONSTRATIVE_TEXT_ANCHORS: tuple[str, ...] = (
    "denna text",
    "den har texten",
    "den här texten",
    "det har texten",
    "det här texten",
    "this text",
    "the text",
)


def _extract_literal_old_new(
    follow_up_prompt: str,
) -> tuple[str | None, str | None]:
    """Pull ``(OLD, NEW)`` from a literal replace phrasing, or ``(None, None)``.

    Handles three shapes:
      - ``"NEW" istallet for "OLD"`` (NEW precedes the marker, OLD follows it);
      - two quoted spans separated by a replace verb/marker (OLD first, NEW
        last) - e.g. ``andra "X" til att saga "Y"``;
      - a single quoted OLD span followed by an unquoted/colon ``till``/``to``
        value - e.g. ``andra denna text "X" till Y``.
    """
    marker_new = _value_before_replace_marker(follow_up_prompt)
    spans = list(_QUOTED_SPAN_RE.finditer(follow_up_prompt))
    if marker_new is not None:
        lowered = follow_up_prompt.lower()
        marker_pos = min(
            pos for pos in (lowered.find(m) for m in _REPLACE_MARKERS) if pos != -1
        )
        old_after = next(
            (m.group(1) for m in spans if m.start() > marker_pos), None
        )
        return (
            (old_after.strip() if old_after else None),
            (marker_new.strip() or None),
        )
    if not spans:
        return None, None
    old_value = spans[0].group(1).strip()
    if len(spans) >= 2:
        return (old_value or None), (spans[-1].group(1).strip() or None)
    tail = follow_up_prompt[spans[0].end() :]
    new_value = _extract_replace_value(tail)
    return (old_value or None), (new_value.strip() if new_value else None)


def _extract_literal_replace_directives(
    follow_up_prompt: str,
    merged: dict[str, Any],
    *,
    previous_rendered_story: str | None = None,
) -> list[dict[str, Any]]:
    """Literal find-and-replace on the current copy fields.

    Returns a single targeted ``replace-text`` directive when the operator
    quoted an OLD value that exactly matches (normalised) a current
    ``tagline``/``heroHeadline``/``story`` or a service ``summary``, else
    ``[]`` (honest no-op). The NEW value runs through ``_safe_copy_payload`` so
    the raw instruction can never become customer copy. Needs the merged
    Project Input (the current site state), so it is wired into
    ``merge_followup_project_input``, not the stateless ``_extract_copy_directives``.

    ``previous_rendered_story`` (Track B / ADR 0043 + 0034) is the about/story
    copy the PREVIOUS build actually rendered. The operator almost always quotes
    the text they SEE, which for the om-oss/story block is ``derive_story(brief)``
    (planning blueprint) - regenerated every build and shadowing the stored
    ``company.story`` at render (``apply_blueprint_to_dossier``), so it is NOT
    equal to the stored field. Matching it too lets "ändra '<den text jag ser>'
    till X" land; ``_apply_copy_directives`` then pins the result to
    ``directives.sectionContentOverrides`` so it wins over the regenerated
    blueprint copy and survives later rebuilds.
    """
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return []
    # #318 review fix: an ADDITIVE follow-up that merely quotes NEW content
    # ("lägg till en knapp som säger 'X' och en som säger 'Y'") is never a
    # copy-REPLACE, even though it carries two quoted spans. Without this guard
    # the bare quoted pair (``has_quoted_pair`` below, kept for B204-mangled
    # leading verbs) could pass the gate and - if the first quote happened to
    # match an existing copy field - silently MUTATE that field. Guard on the
    # instruction skeleton (quoted spans removed) so a quoted NEW value that
    # merely reads additively never drives it. Mirrors the additive guard
    # already in ``_followup_requested_copy_replace`` and
    # ``_resolve_unquoted_literal_replace`` so the three stay consistent.
    skeleton = _text_outside_quotes(follow_up_prompt) or text
    if _followup_is_additive_request(skeleton):
        return []
    old_value, new_value = _extract_literal_old_new(follow_up_prompt)
    # A clear quoted/marker OLD->NEW pair is a literal replace REQUEST on its
    # own, even when the leading verb never reached us intact: the viewser-chat
    # -> CLI boundary can mangle a leading "Ä" to "*" ("Ändra" -> "*ndra", B204),
    # which strips the verb keyword from the normalised text. Keying the gate on
    # the explicit pair (not only the verb/anchor) keeps the literal edit landing
    # under that mangling instead of silently dropping to a paraphrase/no-op.
    has_quoted_pair = bool(old_value and new_value)
    has_replace = _contains_any_word(
        text, _COPY_DIRECTIVE_REPLACE_KEYWORDS
    ) or _contains_any(text, _REPLACE_MARKERS)
    has_text_anchor = _contains_any(text, _LITERAL_TEXT_ANCHOR_KEYWORDS)
    if not (has_replace or has_text_anchor or has_quoted_pair):
        return []
    if not old_value or not new_value:
        # No QUOTED OLD/NEW pair: try the UNQUOTED substring path (B155). A
        # quoted prompt that merely failed to yield a complete pair is bounced
        # back out by the unquoted resolver's no-quote guard, so the two paths
        # never double-process the same follow-up.
        return _resolve_unquoted_literal_replace(follow_up_prompt, merged)[
            "directives"
        ]
    old_norm = _normalise_followup_text(old_value)
    if not old_norm:
        return []
    company = merged.get("company")
    company = company if isinstance(company, dict) else {}
    # Editable single-value copy fields, in priority order. tagline +
    # heroHeadline both feed the hero line; story is the about copy.
    for target, field, cap in (
        ("tagline", "tagline", 140),
        ("tagline", "heroHeadline", 140),
        ("about-text", "story", _COPY_DIRECTIVE_ABOUT_MAX_LENGTH),
    ):
        current = company.get(field)
        if isinstance(current, str) and _normalise_followup_text(current) == old_norm:
            payload = _safe_copy_payload(
                new_value, follow_up_prompt=follow_up_prompt, max_length=cap
            )
            if payload is None:
                return []
            return [
                {
                    "target": target,
                    "operation": "replace-text",
                    "payload": payload,
                    # "prompt-rule": deterministic, prompt-derived (the schema
                    # enum allows prompt-rule | llm | explicit). The literal
                    # find-and-replace is a deterministic rule, not an LLM call.
                    "source": "prompt-rule",
                }
            ]
    # Track B: the operator quoted the RENDERED/derived om-oss text (not the
    # stored company.story). Match it as an about-text replace so the edit lands
    # and - via the _apply_copy_directives story pin - survives the next build's
    # derive_story regeneration. Lower priority than an exact stored-field match
    # above; never fires without a non-empty previous rendered story.
    if previous_rendered_story and (
        _normalise_followup_text(previous_rendered_story) == old_norm
    ):
        payload = _safe_copy_payload(
            new_value,
            follow_up_prompt=follow_up_prompt,
            max_length=_COPY_DIRECTIVE_ABOUT_MAX_LENGTH,
        )
        if payload is None:
            return []
        return [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": payload,
                "source": "prompt-rule",
            }
        ]
    for service in merged.get("services") or []:
        if not isinstance(service, dict):
            continue
        summary = service.get("summary")
        if isinstance(summary, str) and _normalise_followup_text(summary) == old_norm:
            ref = service.get("id") or service.get("label")
            if not (isinstance(ref, str) and ref.strip()):
                return []
            payload = _safe_copy_payload(
                new_value,
                follow_up_prompt=follow_up_prompt,
                max_length=_COPY_DIRECTIVE_SERVICES_MAX_LENGTH,
            )
            if payload is None:
                return []
            return [
                {
                    "target": "services",
                    "operation": "replace-text",
                    "payload": payload,
                    "targetRef": ref.strip()[:80],
                    "source": "prompt-rule",
                }
            ]
    return []


# --- unquoted literal find-and-replace (B155) -------------------------------
# "ändra <OLD> till <NEW>" WITHOUT quotes is the most natural way an operator
# asks for a verbatim swap. The quoted path above cannot see it (no quoted
# span), so before this slice it paraphrased (semantic patch) or silently
# no-op:ed. This path extracts OLD/NEW from the unquoted phrasing and matches
# OLD as an EXACT (normalised, case-insensitive) SUBSTRING of a known stored
# copy field (company.tagline / company.story / each services[].summary). A
# single match applies a literal substitution; zero matches stay an honest
# no-op; OLD present in >= 2 distinct copy fields is an honest AMBIGUOUS no-op
# (surfaced with a reason via the unappliedFollowupIntents observer). We NEVER
# guess a target or paraphrase. company.heroHeadline is intentionally NOT a
# separate match target here: it is a derived mirror of company.tagline (set by
# _apply_copy_directives), so matching the tagline both avoids a false
# "ambiguous" with its own mirror and lets the apply step keep the H1 in sync.
# Service LABEL/name rename is out of scope this slice: the copyDirective schema
# only models services[].summary (no field for a label rename, and adding one
# would be a schema change). A label-only hit is reported honestly via the
# observer instead (detection-only, no new directive type).
# Operator-facing reason (Swedish) surfaced via unappliedFollowupIntents when an
# unquoted OLD matches more than one editable copy field. We refuse to guess
# which one the operator meant, so the build is an honest no-op instead of a
# silent (possibly wrong) edit.
_UNQUOTED_AMBIGUOUS_REASON = (
    "Texten du ville byta finns i flera fält, så ingen ändring gjordes. "
    "Var mer specifik (t.ex. ange rubrik, om-oss-text eller tjänst) eller "
    "citera hela stycket du vill ersätta."
)
_UNQUOTED_REPLACE_VERBS_ALT = "|".join(
    re.escape(verb)
    for verb in sorted(_COPY_DIRECTIVE_REPLACE_KEYWORDS, key=len, reverse=True)
)
_UNQUOTED_REPLACE_ANCHOR_ALT = "|".join(
    re.escape(anchor)
    for anchor in sorted(_LITERAL_TEXT_ANCHOR_KEYWORDS, key=len, reverse=True)
)
_UNQUOTED_REPLACE_RE = re.compile(
    rf"\b(?:{_UNQUOTED_REPLACE_VERBS_ALT})\b\s+"
    rf"(?:(?:{_UNQUOTED_REPLACE_ANCHOR_ALT})\s+)?"
    rf"(?P<old>.+?)\s+(?:\btill\b|\bto\b)\s+(?P<new>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)

# Anchor-led demonstrative form WITHOUT a leading replace verb:
# "denna text: <OLD> ska bli <NEW>" (B178). The operator points at a specific
# visible string and states what it should BECOME. A "become" separator
# (ska bli / blir / ska vara / så den blir / vill jag (bara) ska bli) is the
# natural Swedish phrasing here; restricting that wider separator vocabulary to
# the demonstrative-anchored form keeps a style ask ("sajten ska bli mörkblå",
# no demonstrative anchor) out of the copy-replace path. ``till``/``to`` are
# kept too so "denna text: X till Y" also works. An optional colon/dash right
# after the anchor is consumed.
_DEMONSTRATIVE_ANCHOR_ALT = "|".join(
    re.escape(anchor)
    for anchor in sorted(_DEMONSTRATIVE_TEXT_ANCHORS, key=len, reverse=True)
)
_BECOME_SEPARATOR_ALT = (
    r"vill\s+jag\s+(?:bara\s+)?ska\s+bli"
    r"|ska\s+bli|ska\s+vara|s[åa]\s+den\s+blir|s[åa]\s+det\s+blir"
    r"|\bblir\b|\bbli\b|\btill\b|\bto\b"
)
_UNQUOTED_ANCHOR_REPLACE_RE = re.compile(
    rf"\b(?:{_DEMONSTRATIVE_ANCHOR_ALT})\b\s*[:\-\u2013\u2014]?\s*"
    rf"(?P<old>.+?)\s+(?:{_BECOME_SEPARATOR_ALT})\s+(?P<new>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _clean_unquoted_fragment(value: str | None) -> str:
    """Trim a captured OLD/NEW fragment (quotes + edge punctuation/whitespace)."""
    if not value:
        return ""
    cleaned = value.strip().strip(_QUOTE_CHARS).strip()
    return cleaned.strip(".:,;!? ").strip()


def _extract_unquoted_old_new(
    follow_up_prompt: str,
) -> tuple[str | None, str | None]:
    """Pull ``(OLD, NEW)`` from an UNQUOTED ``<verb> <OLD> till <NEW>`` phrasing.

    Returns ``(None, None)`` when the prompt carries any quoted span (the quoted
    path owns that case) or when neither unquoted pattern matches. Two phrasings
    are understood:

    - verb-led: ``<verb> <OLD> till/to <NEW>`` (first ``till``/``to`` after a
      replace verb is the separator; an optional literal-text anchor right after
      the verb is dropped so it never becomes part of OLD);
    - anchor-led demonstrative: ``denna text: <OLD> ska bli <NEW>`` - no leading
      verb, a wider "become" separator, only when an explicit demonstrative text
      anchor is present (B178).
    """
    if _QUOTED_SPAN_RE.search(follow_up_prompt):
        return None, None
    match = _UNQUOTED_REPLACE_RE.search(follow_up_prompt)
    if match is None:
        match = _UNQUOTED_ANCHOR_REPLACE_RE.search(follow_up_prompt)
    if match is None:
        return None, None
    old_value = _clean_unquoted_fragment(match.group("old"))
    new_value = _clean_unquoted_fragment(match.group("new"))
    return (old_value or None), (new_value or None)


def _unquoted_replace_candidates(
    merged: dict[str, Any],
) -> list[tuple[str, str | None, str, int]]:
    """Editable copy fields the unquoted path may substring-match against.

    Each entry is ``(target, targetRef, raw_value, max_length)``. heroHeadline is
    deliberately excluded (mirror of tagline). Service entries require both a
    non-empty summary and a resolvable ref (id/label).
    """
    company = merged.get("company")
    company = company if isinstance(company, dict) else {}
    candidates: list[tuple[str, str | None, str, int]] = []
    tagline = company.get("tagline")
    if isinstance(tagline, str) and tagline.strip():
        candidates.append(("tagline", None, tagline, 140))
    story = company.get("story")
    if isinstance(story, str) and story.strip():
        candidates.append(("about-text", None, story, _COPY_DIRECTIVE_ABOUT_MAX_LENGTH))
    for service in merged.get("services") or []:
        if not isinstance(service, dict):
            continue
        summary = service.get("summary")
        ref = service.get("id") or service.get("label")
        if (
            isinstance(summary, str)
            and summary.strip()
            and isinstance(ref, str)
            and ref.strip()
        ):
            candidates.append(
                (
                    "services",
                    ref.strip()[:80],
                    summary,
                    _COPY_DIRECTIVE_SERVICES_MAX_LENGTH,
                )
            )
    return candidates


def _resolve_unquoted_literal_replace(
    follow_up_prompt: str,
    merged: dict[str, Any],
) -> dict[str, Any]:
    """Resolve an UNQUOTED literal replace into a status + directive list.

    Returns ``{"status", "directives", "reason"}`` where ``status`` is one of:
      - ``"none"``   - not an engaged unquoted literal-replace form;
      - ``"no_match"`` - engaged but OLD matches no stored copy field;
      - ``"ambiguous"`` - OLD matches >= 2 distinct copy fields (honest no-op);
      - ``"applied"`` - exactly one field matched and a directive was built.

    Engagement is deliberately narrow so target-keyword prompts ("ändra taglinen
    till X") still flow through ``_extract_copy_directives`` and additive /
    section-add prompts are never treated as a replace.
    """
    empty: dict[str, Any] = {"status": "none", "directives": [], "reason": None}
    if _QUOTED_SPAN_RE.search(follow_up_prompt):
        return empty
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return empty
    has_replace = _contains_any_word(
        text, _COPY_DIRECTIVE_REPLACE_KEYWORDS
    ) or _contains_any(text, _REPLACE_MARKERS)
    # A demonstrative text anchor ("denna text: X ska bli Y") engages the
    # anchor-led form even without a leading replace verb (B178). The narrow
    # demonstrative set keeps style/section asks (no such anchor) out.
    has_demo_anchor = _contains_any(text, _DEMONSTRATIVE_TEXT_ANCHORS)
    if not (has_replace or has_demo_anchor):
        return empty
    # A recognised target keyword ("taglinen"/"namnet"/"hero"/"tjänsten"/...) is
    # owned by _extract_copy_directives; an additive/section-add ask is never a
    # replace. Both gates run on the instruction skeleton so a target/section
    # word inside the OLD/NEW copy never drives them.
    skeleton = _text_outside_quotes(follow_up_prompt) or text
    if _classify_copy_target(skeleton) is not None:
        return empty
    if _followup_is_additive_request(skeleton):
        return empty
    old_value, new_value = _extract_unquoted_old_new(follow_up_prompt)
    if not old_value or not new_value:
        return empty
    old_norm = _normalise_followup_text(old_value)
    if len(old_norm) < 2:
        return empty
    candidates = _unquoted_replace_candidates(merged)
    matches = [
        candidate
        for candidate in candidates
        if old_norm in _normalise_followup_text(candidate[2])
    ]
    if not matches:
        return {"status": "no_match", "directives": [], "reason": None}
    distinct_keys = {(target, target_ref) for target, target_ref, _, _ in matches}
    if len(distinct_keys) >= 2:
        return {
            "status": "ambiguous",
            "directives": [],
            "reason": _UNQUOTED_AMBIGUOUS_REASON,
        }
    target, target_ref, raw_value, cap = matches[0]
    # Leak-guard the INSERTED fragment only (the surrounding field is already
    # public copy that passed the guards when first written) - validating the
    # whole reconstructed string would false-reject when the existing copy
    # happens to contain a change-verb word.
    if _safe_copy_payload(
        new_value, follow_up_prompt=follow_up_prompt, max_length=cap
    ) is None:
        return {"status": "no_match", "directives": [], "reason": None}
    pattern = re.compile(re.escape(old_value), re.IGNORECASE)
    new_raw = pattern.sub(lambda _match: new_value, raw_value, count=1)
    if new_raw == raw_value:
        # Normalised match but the raw substitution found nothing (whitespace /
        # punctuation drift) - never guess, stay an honest no-op.
        return {"status": "no_match", "directives": [], "reason": None}
    payload = new_raw.strip()[:cap].strip()
    if not payload:
        return {"status": "no_match", "directives": [], "reason": None}
    directive: dict[str, Any] = {
        "target": target,
        "operation": "replace-text",
        "payload": payload,
        "source": "prompt-rule",
    }
    if target == "services" and target_ref:
        directive["targetRef"] = target_ref
    return {"status": "applied", "directives": [directive], "reason": None}


def unquoted_literal_replace_status(
    follow_up_prompt: str,
    source_project_input: dict[str, Any],
) -> dict[str, Any]:
    """Public wrapper around the unquoted resolver (observer + test entry point).

    ``source_project_input`` is the site state whose copy fields OLD is matched
    against (the previous version in the honest-no-op observer). Returns the same
    ``{"status", "directives", "reason"}`` shape as
    ``_resolve_unquoted_literal_replace``.
    """
    return _resolve_unquoted_literal_replace(follow_up_prompt, source_project_input)


def _followup_is_additive_request(skeleton_text: str) -> bool:
    """True when the instruction skeleton is an ADDITIVE (add/include) request.

    ``skeleton_text`` is the normalised follow-up with the quoted OLD/NEW copy
    removed (``_text_outside_quotes``), so a quoted value that happens to read
    additively never drives this. Additive = an include keyword (``lägg
    till``/``inkludera``/...) OR a section-add phrasing (``ny ... sektion``).
    An additive follow-up is never a copy-REPLACE even when it quotes the NEW
    content (the quoted span is the new copy, not an OLD string to swap).
    """
    if _contains_any_word(skeleton_text, _COPY_DIRECTIVE_INCLUDE_KEYWORDS):
        return True
    return bool(_SECTION_ADD_INTENT_RE.search(skeleton_text))


def _followup_requested_copy_replace(follow_up_prompt: str) -> bool:
    """True when the follow-up asked to REPLACE a specific quoted copy string.

    Used by the build's honest-effect signal (ROW 3): when the operator clearly
    asked to SWAP visible text (a genuine replace verb / replace marker PLUS a
    quoted OLD span) but no copyDirective actually applied, an unrelated byte
    diff must NOT be reported as a successful edit. The signal answers "did the
    operator's REPLACE intent land?".

    Tightened (#224 P2): an ADDITIVE follow-up that merely quotes the NEW copy -
    e.g. ``lägg till en FAQ-sektion med texten "Vanliga frågor"`` - is NOT a
    copy-replace. Such a prompt may well have added a visible section, so it
    must report the honest visible change, never a phantom
    ``copy_directive_not_applied`` no-op. Two guards make this honest:

    1. additive phrasing (include keyword / ``ny ... sektion``) -> not a replace;
    2. a genuine REPLACE signal is required - a replace verb or replace marker,
       NOT a bare ``texten`` anchor (which is exactly what mis-fired on the
       additive ``... med texten "..."`` phrasing).

    Both run on the instruction skeleton (quoted spans removed) so a verb or
    section noun inside the quoted OLD/NEW copy never drives the signal. The
    legitimate literal copy-replace honesty case (a quoted OLD span + replace
    verb that truly no-ops) still returns ``True``.

    Broadened (B178): an UNQUOTED demonstrative free-text replace -
    ``Denna text: <OLD> ska bli <NEW>`` - also counts as a replace REQUEST so a
    regenerated paraphrase never masquerades as a successful edit when the
    operator wrote no quotes. It is gated on an explicit demonstrative anchor
    (``denna text``/``den här texten``/...) plus a matched OLD->NEW pair, so a
    style ("sajten ska bli mörkblå") or section ("lägg till en sektion")
    follow-up - which carries no demonstrative anchor - never trips the signal.
    """
    text = _normalise_followup_text(follow_up_prompt)
    if not text:
        return False
    if not _QUOTED_SPAN_RE.search(follow_up_prompt):
        return _unquoted_anchor_replace_requested(follow_up_prompt)
    # Match the operator's instruction skeleton, not the quoted OLD/NEW copy.
    # Fall back to the full text only when the entire message was quoted.
    skeleton = _text_outside_quotes(follow_up_prompt) or text
    if _followup_is_additive_request(skeleton):
        return False
    if _contains_any_word(
        skeleton, _COPY_DIRECTIVE_REPLACE_KEYWORDS
    ) or _contains_any(skeleton, _REPLACE_MARKERS):
        return True
    # Encoding-robust honesty (B204): a clear quoted OLD->NEW pair is a replace
    # REQUEST even when the leading verb was mangled at the viewser-chat -> CLI
    # boundary ("Ändra" -> "*ndra" strips the verb keyword from the skeleton).
    # Key on the explicit pair, never on the verb keyword alone, so the honest
    # no-op gate (copy_directive_not_applied) still fires under that mangling
    # instead of letting an unrelated rebuild byte-diff pose as a successful
    # edit. The additive guard above already excluded section-add phrasings.
    old_value, new_value = _extract_literal_old_new(follow_up_prompt)
    return bool(old_value and new_value)


def _unquoted_anchor_replace_requested(follow_up_prompt: str) -> bool:
    """True when an UNQUOTED follow-up points at a demonstrative copy string to
    swap (``Denna text: X ska bli Y``) - the B178 honesty case.

    Narrow by construction: requires an explicit demonstrative text anchor AND a
    matched anchor-led OLD->NEW pair, and bails on additive/target-keyword asks.
    A style or section follow-up (no demonstrative anchor) returns ``False`` so
    it is never mis-reported as a failed copy-replace.
    """
    text = _normalise_followup_text(follow_up_prompt)
    if not _contains_any(text, _DEMONSTRATIVE_TEXT_ANCHORS):
        return False
    skeleton = _text_outside_quotes(follow_up_prompt) or text
    if _followup_is_additive_request(skeleton):
        return False
    if _classify_copy_target(skeleton) is not None:
        return False
    old_value, new_value = _extract_unquoted_old_new(follow_up_prompt)
    return bool(old_value and new_value)


def _extract_copy_directives(
    follow_up_prompt: str,
    *,
    language: str,
) -> list[dict[str, Any]]:
    """Translate a follow-up prompt into a narrow, leak-safe copy-directive list.

    V1 understands two phrasings, both validated through the public-copy
    guards so the raw instruction can never become customer copy:

    - "byt/ändra/gör om <företagsnamnet|headern|...> till '<Y>'" -> replace-text
      on company-name (the company brand in the nav header + hero brand line).
    - "byt/ändra <rubriken|huvudrubriken|underrubriken|hero-texten> till '<Y>'"
      -> replace-text on the hero tagline (the H1 the operator actually means
      when they say "byt rubriken på startsidan").
    - "inkludera '<TOKEN>' i hero/rubriken" -> include-token on the hero
      tagline (ADR 0034 acceptance case).

    Returns ``[]`` when nothing safe is recognised, so the honest no-op path
    (B155) still fires.
    """
    _ = language  # reserved for the LLM-backed extractor (copyDirectiveModel)
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return []
    # bildbyte-guard: an asset request ("byt ut hero-bilden till en unsplash
    # bild") must never reach the replace/include rules - the trailing
    # "till"-value would be spliced into public copy. Honest no-op here;
    # compute_unapplied_followup_intents names the miss in build-result.json.
    if is_media_change_request(follow_up_prompt):
        return []
    target = _classify_copy_target(text)
    if target is None:
        return []
    # page-add honesty guard (2026-06-16): "lägg till en sida som heter 'X'" is a
    # route_add - the quoted "...som heter X" names the NEW PAGE, not the company.
    # The explicit name keyword ("heter") otherwise wins in _classify_copy_target
    # and "X" is published as a company rename (the confident-wrong "Jakobs sida"
    # bug: an add-a-page request silently became a company-name change + "Klart!").
    # Scoped to company-name so genuine renames ("ändra företagsnamnet till X")
    # and every other copy target stay byte-identical; route_add itself is an
    # honest no-op (full page-adding is a noted follow-up).
    if target == "company-name" and is_page_add_request(follow_up_prompt):
        return []
    # Detect command verbs as WHOLE words/phrases, not substrings:
    # "Jag bytte företagsnamnet till X" is past-tense narration and must not
    # trigger replace-mode via the substring "byt" inside "bytte".
    has_include = _contains_any_word(text, _COPY_DIRECTIVE_INCLUDE_KEYWORDS)
    has_replace = _contains_any_word(text, _COPY_DIRECTIVE_REPLACE_KEYWORDS)
    # An "instead of"-style marker is a replace intent even without a
    # byt/ändra/sätt verb (e.g. "gör herotexten 'X' istället för 'Y'"). The
    # value extractors pull the quoted span before the marker.
    if not has_replace and _contains_any(text, _REPLACE_MARKERS):
        has_replace = True
    if not has_include and not has_replace:
        return []
    # about-text is replace-only in slice 2a (operator decision): the operator
    # must supply the new copy via an explicit "till '<X>'"/colon/quote. A
    # vibe-only rewrite ("skriv om om oss så det låter mer personligt") has no
    # literal payload and stays an honest no-op here - generating new about
    # copy from an instruction is later-level LLM work (site-state rewrite),
    # not this deterministic slice. include-token on about-text is unsupported.
    if target == "about-text":
        if not has_replace:
            return []
        payload = _safe_copy_payload(
            _extract_explicit_replace_value(follow_up_prompt),
            follow_up_prompt=follow_up_prompt,
            max_length=_COPY_DIRECTIVE_ABOUT_MAX_LENGTH,
        )
        if payload is None:
            return []
        return [
            {
                "target": "about-text",
                "operation": "replace-text",
                "payload": payload,
                "source": "prompt-rule",
            }
        ]
    # services is replace-only (slice 2c): the operator must name WHICH service
    # (targetRef) and supply the new summary via an explicit "till '<X>'". An
    # additive "lägg till ny tjänst" is handled by the semantic service merge,
    # never a copy replace, so we bail on the additive phrasing. No named
    # service -> honest no-op (we never guess which service to rewrite).
    if target == "services":
        if not has_replace or _contains_any(text, _COPY_DIRECTIVE_NEW_SERVICE_GUARD):
            return []
        target_ref = _extract_service_target_ref(follow_up_prompt)
        if not target_ref:
            return []
        payload = _safe_copy_payload(
            _extract_explicit_replace_value(follow_up_prompt),
            follow_up_prompt=follow_up_prompt,
            max_length=_COPY_DIRECTIVE_SERVICES_MAX_LENGTH,
        )
        if payload is None:
            return []
        return [
            {
                "target": "services",
                "operation": "replace-text",
                "payload": payload,
                "targetRef": target_ref,
                "source": "prompt-rule",
            }
        ]
    # include-token wins when both are present ("ändra texten ... till att
    # inkludera 'TEST-JAKOB'") because the operator named a token to add.
    if has_include:
        payload = _safe_copy_payload(
            _extract_include_token(follow_up_prompt),
            follow_up_prompt=follow_up_prompt,
            max_length=60,
        )
        if payload is None:
            return []
        return [
            {
                "target": target,
                "operation": "include-token",
                "payload": payload,
                "source": "prompt-rule",
            }
        ]
    # A rewrite-vibe verb ("skriv om hero till mer premium") on name/tagline must
    # not publish an unquoted trailing vibe as literal copy - require an explicit
    # quoted/colon value, else no-op (reviewer P2 2026-06-02). A plain set verb
    # ("byt taglinen till Mer än bara kaffe") keeps the loose trailing so a real
    # short label that happens to start with "mer" is not rejected.
    is_rewrite_vibe = _contains_any_word(text, _COPY_CONTENT_REWRITE_VERBS)
    raw_value = (
        _extract_explicit_replace_value(follow_up_prompt)
        if is_rewrite_vibe
        else _extract_replace_value(follow_up_prompt)
    )
    payload = _safe_copy_payload(
        raw_value,
        follow_up_prompt=follow_up_prompt,
        max_length=80 if target == "company-name" else 140,
    )
    if payload is None:
        return []
    if target == "company-name" and payload == payload.lower():
        payload = _title_case_company_name(payload)
    return [
        {
            "target": target,
            "operation": "replace-text",
            "payload": payload,
            "source": "prompt-rule",
        }
    ]


def _validate_copy_directive_candidate(
    candidate: dict[str, Any],
    *,
    follow_up_prompt: str,
) -> dict[str, Any] | None:
    """Re-validate a model-proposed copy directive through the public guards.

    This is the single security boundary for the LLM path: target/operation
    must be known enums and the payload must survive ``_safe_copy_payload``
    (change-verb reject + planner-note blocklist + length cap). A hallucinated
    or instruction-shaped payload is dropped here, never rendered.
    """
    target = candidate.get("target")
    operation = candidate.get("operation")
    if target not in {"company-name", "tagline", "about-text", "services"}:
        return None
    if operation not in {"replace-text", "include-token"}:
        return None
    # about-text and services are replace-only; a model-proposed include-token
    # on those fields is dropped rather than guessed at.
    if target in {"about-text", "services"} and operation != "replace-text":
        return None
    # services must name a concrete service (targetRef); without it the apply
    # step cannot resolve which summary to change, so the candidate is dropped.
    target_ref: str | None = None
    if target == "services":
        raw_ref = candidate.get("targetRef")
        if not isinstance(raw_ref, str) or not raw_ref.strip():
            return None
        target_ref = raw_ref.strip()[:80]
    max_length = {
        "company-name": 80,
        "tagline": 140,
        "about-text": _COPY_DIRECTIVE_ABOUT_MAX_LENGTH,
        "services": _COPY_DIRECTIVE_SERVICES_MAX_LENGTH,
    }[target]
    payload = _safe_copy_payload(
        candidate.get("payload"),
        follow_up_prompt=follow_up_prompt,
        max_length=max_length,
    )
    if payload is None:
        return None
    if target == "company-name" and payload == payload.lower():
        payload = _title_case_company_name(payload)
    validated: dict[str, Any] = {
        "target": target,
        "operation": operation,
        "payload": payload,
        "source": "llm",
    }
    if target_ref is not None:
        validated["targetRef"] = target_ref
    return validated


def _extract_copy_directives_via_llm(
    follow_up_prompt: str,
    *,
    company: dict[str, Any],
    services: list[dict[str, Any]] | None = None,
    language: str,
) -> list[dict[str, Any]]:
    """LLM fallback for copy directives when the deterministic rules miss.

    Uses the dedicated copyDirectiveModel role (llm-models.v1.json v6).
    Fail-safe: any resolution/call error yields ``[]`` so the honest no-op
    path still fires. Every candidate is re-validated through
    ``_validate_copy_directive_candidate`` (which requires a non-empty
    targetRef for services); the actual service existence is resolved later in
    ``_apply_copy_directives`` (unknown ref -> no-op).
    """
    try:
        from packages.generation.brief.extract import extract_copy_directives_llm

        model = resolve_copy_directive_model()
        raw_directives = extract_copy_directives_llm(
            follow_up_prompt,
            company_name=str(company.get("name") or ""),
            tagline=str(company.get("tagline") or ""),
            story=str(company.get("story") or ""),
            services=services or [],
            language=language,
            model=model,
        )
    except Exception:  # noqa: BLE001
        return []
    validated: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    for candidate in raw_directives:
        directive = _validate_copy_directive_candidate(
            candidate if isinstance(candidate, dict) else {},
            follow_up_prompt=follow_up_prompt,
        )
        if directive is None:
            continue
        # The extraction path only carries copy the operator already supplied:
        # restrict it to company-name/tagline. Generated about-text/services copy
        # must come from the planner path (rewrite-verb gate + grounding guard),
        # never from the extraction fallback - otherwise a vague non-rewrite
        # prompt ("fixa om oss-texten lite") could apply model-generated about
        # copy with no grounding (reviewer P2 2026-06-02).
        if directive["target"] not in {"company-name", "tagline"}:
            continue
        # Dedupe on (target, targetRef) so distinct services can each be edited,
        # while a target like tagline still collapses to one directive.
        dedupe_key = (directive["target"], directive.get("targetRef", ""))
        if dedupe_key in seen_targets:
            continue
        seen_targets.add(dedupe_key)
        validated.append(directive)
    return validated


# --- editPlan planner (ADR 0034 väg A nivå 3a) ------------------------------
# A content-rewrite request ("skriv om om oss så det låter mer personligt") has
# no literal value, so the deterministic + extraction paths stay honest no-ops.
# The planner reads the current site-state and asks copyDirectiveModel to
# GENERATE new copy for about-text/services only, then re-validates every
# candidate through the same guards. It runs in a dedicated branch so the
# extraction path's behaviour (and tone-shift/story-emphasize intents) are
# untouched.


def _has_explicit_copy_value(follow_up_prompt: str) -> bool:
    """True when the operator supplied a literal new value (quoted or colon).

    Strict on purpose: a bare trailing ``till <vibe>`` does NOT count, so a
    rewrite-by-vibe ("skriv om om oss till mer personligt") routes to the
    planner instead of publishing the instruction as customer copy.
    """
    return _extract_explicit_replace_value(follow_up_prompt) is not None


def _content_rewrite_target(follow_up_prompt: str) -> str | None:
    """Return the rewrite target ('about-text'|'services') or None.

    A content-rewrite request needs a rewrite/improve verb, NO explicit literal
    value (those are handled deterministically), and an about-text or services
    target. A services rewrite still requires a named existing service
    (targetRef). This is the only gate that activates LLM copy generation, kept
    separate from the extraction eligibility so the deterministic/extraction
    behaviour does not change.
    """
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return None
    if _has_explicit_copy_value(follow_up_prompt):
        return None
    if _contains_any(text, _COPY_DIRECTIVE_NEW_SERVICE_GUARD):
        return None
    if not _contains_any_word(text, _COPY_CONTENT_REWRITE_VERBS):
        return None
    target = _classify_copy_target(text)
    if target not in {"about-text", "services"}:
        return None
    if target == "services" and not _extract_service_target_ref(follow_up_prompt):
        return None
    return target


def _is_content_rewrite_request(follow_up_prompt: str) -> bool:
    """True when the follow-up asks to rewrite existing about/service copy."""
    return _content_rewrite_target(follow_up_prompt) is not None


def _build_site_state_for_copy_planning(
    merged: dict[str, Any],
    focus_sections: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Read-only snapshot of the editable copy fields for the planner context.

    ``focus_sections`` (ADR 0046) carries the operator's validated preview
    markings as a soft prioritisation signal — included in the snapshot so
    the planner can bind an ambiguous "skriv om texten här" to the right
    field. Never an instruction: the scope/target guards downstream are
    unchanged.
    """
    company = merged.get("company") if isinstance(merged.get("company"), dict) else {}
    services: list[dict[str, Any]] = []
    for service in merged.get("services") or []:
        if isinstance(service, dict):
            services.append(
                {
                    "id": service.get("id"),
                    "label": service.get("label"),
                    "summary": service.get("summary"),
                }
            )
    state: dict[str, Any] = {
        "language": merged.get("language", "sv"),
        "company": {
            "name": company.get("name"),
            "tagline": company.get("tagline"),
            "story": company.get("story"),
        },
        "services": services,
    }
    if focus_sections:
        state["focusSections"] = [dict(entry) for entry in focus_sections]
    return state


def _site_state_grounding_text(
    site_state: dict[str, Any], follow_up_prompt: str
) -> str:
    """Concatenate the facts the planner is allowed to reuse (for the number guard)."""
    parts = [follow_up_prompt]
    company = site_state.get("company") or {}
    parts.extend(str(company.get(key) or "") for key in ("name", "tagline", "story"))
    for service in site_state.get("services") or []:
        parts.append(str(service.get("summary") or ""))
        parts.append(str(service.get("label") or ""))
    return " ".join(parts)


def _planned_payload_grounded(payload: str, grounding_text: str) -> bool:
    """Reject a generated payload that introduces an ungrounded number.

    Any multi-digit number (founding year, price, count, percentage) that
    appears in neither the current site-state nor the follow-up prompt is
    treated as a hallucinated fact and drops the candidate (honest no-op).
    Numbers already present are allowed through. Non-numeric facts (names,
    places, certifications) are guarded by the planner system prompt + remain a
    documented limitation - a deterministic check there is too false-positive
    prone (ADR 0034).

    Matching is whole-token (the grounding numbers are tokenised with the same
    regex), so a shorter ungrounded number does not slip through as a substring
    of a longer grounded one (e.g. payload "500" is NOT grounded by "5000").
    """
    grounded_numbers = set(_PLANNED_NUMBER_RE.findall(grounding_text))
    return all(
        number in grounded_numbers
        for number in _PLANNED_NUMBER_RE.findall(payload)
    )


def _plan_copy_directives_via_llm(
    merged: dict[str, Any],
    follow_up_prompt: str,
    *,
    language: str,
    target: str,
    focus_sections: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Generate an edit plan (validated copyDirectives) for a rewrite request.

    Uses the copyDirectiveModel planner prompt. Fail-safe: any error yields
    ``[]``. Every candidate is re-validated through
    ``_validate_copy_directive_candidate`` and passed through the
    ungrounded-year guard. ``target`` is the requested rewrite target
    (``about-text`` or ``services``); the planner only fulfils THAT target, so
    an about rewrite can never apply a services directive (or vice versa) and
    company-name/tagline are never generated - the scope-leak guard is locked
    in code, not just the system prompt (reviewer P1 2026-06-02).

    ``focus_sections`` (ADR 0046): the operator's validated preview markings
    are appended to the planner's prompt context as a Swedish focus note (a
    soft prioritisation signal). The note is also part of the grounding text
    for the ungrounded-number guard, since its content (section heading text)
    comes from the rendered site itself.
    """
    try:
        from packages.generation.brief.extract import plan_copy_directives_llm
        from packages.generation.followup.marked_sections import focus_note_for_llm

        site_state = _build_site_state_for_copy_planning(merged, focus_sections)
        company_state = site_state["company"]
        focus_note = focus_note_for_llm(focus_sections or [])
        planner_prompt = (
            f"{follow_up_prompt}\n\n{focus_note}" if focus_note else follow_up_prompt
        )
        model = resolve_copy_directive_model()
        raw_directives = plan_copy_directives_llm(
            planner_prompt,
            company_name=str(company_state.get("name") or ""),
            tagline=str(company_state.get("tagline") or ""),
            story=str(company_state.get("story") or ""),
            services=site_state["services"],
            language=language,
            model=model,
        )
    except Exception:  # noqa: BLE001
        return []
    grounding_text = _site_state_grounding_text(site_state, planner_prompt)
    # For a services rewrite, resolve the service the operator actually named so
    # the planner can only edit THAT service - a model return pointing at a
    # different (even existing) service is dropped (reviewer P1 2026-06-02).
    # Resolved by service identity so an id-vs-label mismatch is not a false
    # rejection.
    requested_service = (
        _match_service_by_ref(
            merged.get("services"), _extract_service_target_ref(follow_up_prompt) or ""
        )
        if target == "services"
        else None
    )
    validated: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str]] = set()
    for candidate in raw_directives:
        directive = _validate_copy_directive_candidate(
            candidate if isinstance(candidate, dict) else {},
            follow_up_prompt=follow_up_prompt,
        )
        if directive is None:
            continue
        # Only fulfil the requested rewrite target - drop a directive the model
        # returned for a different field (about<->services) or a non-rewrite
        # target (company-name/tagline are extraction-only).
        if directive["target"] != target:
            continue
        if target == "services":
            directive_service = _match_service_by_ref(
                merged.get("services"), directive.get("targetRef") or ""
            )
            if requested_service is None or directive_service is not requested_service:
                continue
        if not _planned_payload_grounded(directive["payload"], grounding_text):
            continue
        dedupe_key = (directive["target"], directive.get("targetRef", ""))
        if dedupe_key in seen_targets:
            continue
        seen_targets.add(dedupe_key)
        validated.append(directive)
    return validated


# Section-content override keys an applied about-text/story edit pins so the
# rendered om-oss/home-story copy actually changes. The renderer matches an
# override on its ``.<sectionId>.<field>`` suffix
# (resolve_section_content_override) and requires EXACTLY one match, so we both
# write a canonical route key and drop any sibling sharing the same suffix (e.g.
# an "om-oss.about-story.body" left by the apply-bridge path) to keep that
# single-match rule satisfied. ``home.story`` is the home story teaser body;
# ``about.about-story`` is the /om-oss story card body - the two surfaces the
# renderers resolve (render_section_home_story / render_section_about_story).
_STORY_OVERRIDE_KEYS: tuple[tuple[str, str], ...] = (
    ("home.story.body", ".story.body"),
    ("about.about-story.body", ".about-story.body"),
)


def _pin_story_section_overrides(
    directives_block: dict[str, Any], story_text: str
) -> None:
    """Pin an applied about-text/story edit as section-content overrides.

    Mirrors the company.heroHeadline pin: the rendered home-story and /om-oss
    about-story bodies come from the planning blueprint (``derive_story``),
    regenerated every build and shadowing the stored ``company.story`` at
    render. Writing the new copy to ``directives.sectionContentOverrides`` for
    both story surfaces makes the renderer prefer it over the regenerated
    blueprint copy and survive later rebuilds (the map is carried forward by the
    follow-up merge deep-copy). Mutates ``directives_block`` in place; the caller
    (``_store``) attaches it to ``merged['directives']``.
    """
    overrides = directives_block.get("sectionContentOverrides")
    overrides = dict(overrides) if isinstance(overrides, dict) else {}
    for canonical_key, suffix in _STORY_OVERRIDE_KEYS:
        for existing in [
            key
            for key in overrides
            if isinstance(key, str) and key != canonical_key and key.endswith(suffix)
        ]:
            overrides.pop(existing, None)
        overrides[canonical_key] = story_text
    directives_block["sectionContentOverrides"] = overrides


def _apply_copy_directives(
    merged: dict[str, Any],
    directives: list[dict[str, Any]],
) -> None:
    """Apply validated copy directives to structured Project Input fields.

    Mutates ``merged`` in place (company.name / company.tagline /
    company.story) and records
    the applied directives under ``directives.copyDirectives`` for
    traceability - ``build_site.py:_has_copy_directives`` reads it for honest
    no-op detection. The list is REPLACED, not accumulated, so each version's
    Project Input reflects exactly the directives interpreted for that
    follow-up (a later unrelated follow-up must not re-claim an old rename).
    """
    directives_block = merged.get("directives")
    if not isinstance(directives_block, dict):
        directives_block = {}

    def _store(applied_directives: list[dict[str, Any]]) -> None:
        if applied_directives:
            directives_block["copyDirectives"] = applied_directives
            merged["directives"] = directives_block
            return
        # No directive applied this version: drop any inherited copyDirectives
        # so _has_copy_directives reflects only the current follow-up. Keep the
        # directives block iff it still carries other keys (layoutHint etc.).
        directives_block.pop("copyDirectives", None)
        if directives_block:
            merged["directives"] = directives_block
        else:
            merged.pop("directives", None)

    if not directives:
        _store([])
        return

    company = merged.setdefault("company", {})
    applied: list[dict[str, Any]] = []
    for directive in directives:
        target = directive.get("target")
        operation = directive.get("operation")
        payload = directive.get("payload")
        if not isinstance(payload, str) or not payload.strip():
            continue
        # services (slice 2c): replace a specific existing service's summary,
        # resolved by targetRef against the already-merged services list. No
        # match -> skip (honest no-op; never create or hijack a service).
        if target == "services":
            if operation != "replace-text":
                continue
            target_ref = directive.get("targetRef")
            if not isinstance(target_ref, str) or not target_ref.strip():
                continue
            service = _match_service_by_ref(merged.get("services"), target_ref)
            if service is None:
                continue
            service["summary"] = payload
            applied.append(
                {
                    key: directive[key]
                    for key in ("target", "operation", "payload", "targetRef", "source")
                    if key in directive
                }
            )
            continue
        field = {
            "company-name": "name",
            "tagline": "tagline",
            "about-text": "story",
        }.get(target or "")
        if field is None:
            continue
        if operation == "replace-text":
            company[field] = payload
        elif operation == "include-token":
            current = company.get(field) if isinstance(company.get(field), str) else ""
            if payload.lower() in current.lower():
                pass  # token already present; record directive but no field change
            elif current:
                company[field] = f"{current} {payload}".strip()
            else:
                company[field] = payload
        else:
            continue
        # Hero-copy decoupling fix (2026-06-08): the rendered hero H1 comes from
        # the planning blueprint (contentBlocks.home.hero.headline, derived from
        # briefModel positioning.oneLiner and REGENERATED every build), NOT from
        # company.tagline - which only feeds the meta description, footer and a
        # subheadline fallback the blueprint always overrides. So an operator
        # "change the hero text"/tagline edit landed in a field that never shows
        # in the big hero text. Mirror an explicit tagline edit into
        # company.heroHeadline, an operator override the renderer prefers over the
        # regenerated blueprint headline; it lives in the carried-forward company
        # block so the edit survives later rebuilds/follow-ups. Only tagline edits
        # set it - a company rename keeps the nav/footer brand and must never
        # hijack the hero H1.
        if target == "tagline":
            tagline_value = company.get("tagline")
            if isinstance(tagline_value, str) and tagline_value.strip():
                company["heroHeadline"] = tagline_value.strip()
        # About-copy decoupling (mirror of the hero pin, ADR 0043 + 0034): the
        # rendered om-oss/home-story copy comes from the planning blueprint
        # (derive_story), regenerated every build and shadowing company.story at
        # render (apply_blueprint_to_dossier). So a company.story edit lands in a
        # field the renderer overwrites. Pin the new story to
        # directives.sectionContentOverrides for both story surfaces - the
        # override the renderer prefers over the regenerated blueprint copy
        # (resolve_section_content_override) - so the edit actually shows AND
        # survives later rebuilds (the map rides the follow-up merge deep-copy).
        if target == "about-text":
            story_value = company.get("story")
            if isinstance(story_value, str) and story_value.strip():
                _pin_story_section_overrides(directives_block, story_value.strip())
        applied.append(
            {
                key: directive[key]
                for key in ("target", "operation", "payload", "source")
                if key in directive
            }
        )
    _store(applied)
