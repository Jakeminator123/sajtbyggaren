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
    "rubrik",
    "rubriken",
    "huvudrubrik",
    "huvudrubriken",
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
    "rubrik",
    "rubriken",
    "huvudrubrik",
    "huvudrubriken",
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


def _classify_copy_target(text_norm: str) -> str | None:
    """Decide which structured field a copy directive targets.

    ``text_norm`` is the output of ``_normalise_followup_text`` (lower-case,
    quotes stripped). Tagline-specific signals win over the generic name
    signals; a bare ``hero`` mention maps to the hero tagline.
    """
    if _contains_any(text_norm, _COPY_DIRECTIVE_TAGLINE_KEYWORDS):
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
    if _contains_any(
        text_norm, _COPY_DIRECTIVE_SERVICES_KEYWORDS
    ) and not _contains_any_word(text_norm, _COPY_DIRECTIVE_EXPLICIT_NAME_KEYWORDS):
        return "services"
    if _contains_any_word(text_norm, _COPY_DIRECTIVE_NAME_KEYWORDS):
        # A generic "namn/namnet" must not hijack company.name when the
        # operator scoped the rename to a service/product/page (Codex-fynd
        # 2026-06-01): "byt namnet på tjänsten till X" renames a service, not
        # the company. An explicit company-name keyword (företagsnamn,
        # header, rubrik, rename, ...) still wins over the scope words.
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


def _extract_replace_value(follow_up_prompt: str) -> str | None:
    """Pull the new value after a ``till``/``to`` marker (colon, quoted, trailing)."""
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
    """
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


def _extract_copy_directives(
    follow_up_prompt: str,
    *,
    language: str,
) -> list[dict[str, Any]]:
    """Translate a follow-up prompt into a narrow, leak-safe copy-directive list.

    V1 understands two phrasings, both validated through the public-copy
    guards so the raw instruction can never become customer copy:

    - "byt/ändra/gör om <namnet|headern|...> till '<Y>'" -> replace-text on
      company-name (the operator's reported failing case: the company name in
      the nav header + hero H1).
    - "inkludera '<TOKEN>' i hero/rubriken" -> include-token on the hero
      tagline (ADR 0034 acceptance case).

    Returns ``[]`` when nothing safe is recognised, so the honest no-op path
    (B155) still fires.
    """
    _ = language  # reserved for the LLM-backed extractor (copyDirectiveModel)
    text = _normalise_followup_text(follow_up_prompt)
    if not text or len(text) < 4:
        return []
    target = _classify_copy_target(text)
    if target is None:
        return []
    # Detect command verbs as WHOLE words/phrases, not substrings:
    # "Jag bytte företagsnamnet till X" is past-tense narration and must not
    # trigger replace-mode via the substring "byt" inside "bytte".
    has_include = _contains_any_word(text, _COPY_DIRECTIVE_INCLUDE_KEYWORDS)
    has_replace = _contains_any_word(text, _COPY_DIRECTIVE_REPLACE_KEYWORDS)
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


def _build_site_state_for_copy_planning(merged: dict[str, Any]) -> dict[str, Any]:
    """Read-only snapshot of the editable copy fields for the planner context."""
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
    return {
        "language": merged.get("language", "sv"),
        "company": {
            "name": company.get("name"),
            "tagline": company.get("tagline"),
            "story": company.get("story"),
        },
        "services": services,
    }


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
    """
    try:
        from packages.generation.brief.extract import plan_copy_directives_llm

        site_state = _build_site_state_for_copy_planning(merged)
        company_state = site_state["company"]
        model = resolve_copy_directive_model()
        raw_directives = plan_copy_directives_llm(
            follow_up_prompt,
            company_name=str(company_state.get("name") or ""),
            tagline=str(company_state.get("tagline") or ""),
            story=str(company_state.get("story") or ""),
            services=site_state["services"],
            language=language,
            model=model,
        )
    except Exception:  # noqa: BLE001
        return []
    grounding_text = _site_state_grounding_text(site_state, follow_up_prompt)
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
        applied.append(
            {
                key: directive[key]
                for key in ("target", "operation", "payload", "source")
                if key in directive
            }
        )
    _store(applied)
